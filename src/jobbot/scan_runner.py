"""Một lần quét — dùng chung cho cả dòng lệnh và vòng chạy nền.

Trước đây logic này nằm trong scripts/scan.py. Tách ra để scheduler gọi được
mà không phải chạy tiến trình con.
"""

from __future__ import annotations

import tomllib
from typing import Callable

from .core import db, postings
from .core.paths import PROJECT_ROOT
from .dedup import group
from .ingest import arbeitnow, ashby, greenhouse, lever, remotive
from .ingest import filter as jobfilter
from .ingest.base import Posting
from .profile import store
from .scoring.run import score_all

Log = Callable[[str], None]


def load_boards(conn) -> dict[str, list[str]]:
    """Board lấy từ BẢNG CÔNG TY, không phải file gõ tay.

    Bảng đó tự lớn: chủ việc thật thấy trong tin -> thêm vào -> tự dò ATS.
    boards.toml chỉ còn là hạt giống ban đầu.
    """
    from .ingest.web import companies as co
    found = co.boards(conn)
    if found:
        return found
    path = PROJECT_ROOT / "config" / "boards.toml"           # lùi về file nếu bảng rỗng
    raw = tomllib.loads(path.read_text()) if path.exists() else {}
    return {k: v.get("boards", []) for k, v in raw.items()}


def _run_source(conn, name: str, fn, *args, log: Log) -> tuple[int, int]:
    """Một nguồn hỏng KHÔNG được làm hỏng cả lần quét."""
    try:
        items = fn(*args)
    except Exception as exc:                          # noqa: BLE001
        postings.record_run(conn, name, ok=False, error=f"{type(exc).__name__}: {exc}")
        postings.log(conn, "source_failed", f"{name}: {exc}")
        log(f"  {name:26} FAILED  {type(exc).__name__}: {str(exc)[:50]}")
        return 0, 0
    seen, new = postings.save_batch(conn, name, items)
    postings.record_run(conn, name, ok=True, fetched=seen, new_rows=new)
    log(f"  {name:26} {seen:5} tin, {new:5} mới")
    return seen, new


def _chrome_pass(conn, answers: dict, log: Log, deep: bool,
                 manual: bool = False) -> tuple[int, int]:
    """Nguồn phải qua Chrome. Chạy sau nguồn API, chỉ trong cửa sổ giờ người.

    Mỗi nguồn chạy độc lập: một nguồn bị chặn hay hỏng KHÔNG được làm chết
    các nguồn còn lại.
    """
    from .browser import cdp, chrome
    from .core.scheduler import in_human_window
    from .ingest.web import linkedin as li
    from .ingest.web.base import Blocked

    # Cửa sổ giờ tồn tại vì lướt web lúc 3 giờ sáng MỖI ĐÊM là nhịp máy, không
    # phải nhịp người. Nhưng khi chính người dùng bấm chạy thì đó LÀ người thật.
    if not manual and not in_human_window():
        log("  chrome: ngoài cửa sổ giờ người, bỏ tới lượt sau")
        return 0, 0

    titles = [t.strip() for t in (answers.get("job_titles") or "").splitlines() if t.strip()]
    if not titles:
        return 0, 0
    levels = answers.get("seniority") or ["grad", "junior"]

    try:
        chrome.launch(headless=False)          # headed: trang chặn headless
    except chrome.ChromeError as exc:
        log(f"  chrome                     FAILED  {exc}")
        return 0, 0

    # eFinancialCareers đã BỎ: 67% tin của nó là môi giới (LinkedIn 24%), mà chỉ
    # cho 5 tin đạt 75+ so với 20 của LinkedIn. Bẩn gấp ba, ít hơn bốn lần.
    # Module vẫn giữ trong ingest/web/efinancialcareers.py nếu cần bật lại.
    sources = [
        (li.NAME, lambda tab: li.fetch(tab, titles[:5], levels=levels,
                                       pages=4, deep=deep)),
    ]

    total_seen = total_new = 0
    for name, run in sources:
        tab = None
        try:
            tab = cdp.open_tab()
            items, health = run(tab)
            seen, new = postings.save_batch(conn, name, items)
            postings.record_run(conn, name, ok=True, fetched=seen, new_rows=new,
                                attempted=health.attempted, failed=health.failed)
            bad = f"  ⚠ {health.summary}" if health.failed else ""
            log(f"  {name:26} {seen:5} tin, {new:5} mới{bad}")
            total_seen += seen; total_new += new
        except Blocked as exc:
            # Trang từ chối truy cập tự động. Ghi nhận rồi thôi — không cãi lại.
            postings.record_run(conn, name, ok=False, error=f"blocked: {exc}")
            postings.log(conn, "source_blocked", f"{name}: {exc}")
            log(f"  {name:26} BLOCKED {str(exc)[:44]}")
        except Exception as exc:                # noqa: BLE001
            postings.record_run(conn, name, ok=False,
                                error=f"{type(exc).__name__}: {exc}")
            log(f"  {name:26} FAILED  {type(exc).__name__}: {str(exc)[:40]}")
        finally:
            if tab is not None:
                tab.close()
    return total_seen, total_new


def run_scan(pages: int = 3, log: Log | None = None, chrome_sources: bool = True,
             deep: bool = True, manual: bool = False) -> dict:
    say: Log = log or (lambda _msg: None)
    conn = db.connect()
    try:
        answers = store.load(conn)
        if not store.can_ingest(answers):
            return {"ok": False, "summary": "hồ sơ chưa đủ",
                    "missing": store.missing_for_ingest(answers)}

        before_kept = postings.count(conn, kept_only=True)
        boards = load_boards(conn)
        postings.log(conn, "scan_started")

        total_seen = total_new = 0
        for name, fn, args in ((arbeitnow.NAME, arbeitnow.fetch, (pages,)),
                               (remotive.NAME, remotive.fetch, ())):
            s, n = _run_source(conn, name, fn, *args, log=say)
            total_seen += s; total_new += n

        for mod, key in ((greenhouse, "greenhouse"), (lever, "lever"), (ashby, "ashby")):
            for board in boards.get(key, []):
                s, n = _run_source(conn, f"{key}:{board}", mod.fetch_board, board, log=say)
                total_seen += s; total_new += n

        if chrome_sources:
            s, n = _chrome_pass(conn, answers, say, deep, manual)
            total_seen += s; total_new += n

        # --- tầng suy diễn: lọc + gộp + chấm, MỘT giao dịch ---
        from .core.derive import derive
        result = derive(conn, log=say)
        kept, n_groups = result["kept"], result["groups"]
        agencies, marks = result["agencies"], {"scored": result["scored"]}

        # --- danh sách công ty tự lớn lên ---
        from .ingest.web import companies as co
        learned = co.learn_from_postings(conn)
        found = co.resolve_pending(conn, limit=12)
        if learned or found["found"]:
            say(f"  công ty: +{learned} mới, dò ra {found['found']}/{found['checked']}")

        summary = (f"thấy {total_seen} · mới {total_new} · giữ {kept} · "
                   f"{n_groups} việc duy nhất · {agencies} qua môi giới")
        postings.log(conn, "scan_finished", summary)
        return {"ok": True, "summary": summary, "seen": total_seen, "new": total_new,
                "kept": kept, "groups": n_groups, "scored": marks["scored"],
                "new_matches": max(0, kept - before_kept)}
    finally:
        conn.close()
