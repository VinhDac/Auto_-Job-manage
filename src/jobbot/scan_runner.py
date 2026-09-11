"""Một lần quét — dùng chung cho cả dòng lệnh và vòng chạy nền.

Trước đây logic này nằm trong scripts/scan.py. Tách ra để scheduler gọi được
mà không phải chạy tiến trình con.
"""

from __future__ import annotations

import tomllib
from typing import Callable

from .core import db, halt, postings
from .core.journal import SEARCH, log as jlog
from .core.paths import PROJECT_ROOT

STAGE = "search"      # tên khúc, dùng chung với cờ dừng và nút trên thanh
from .ingest import ashby, greenhouse, lever
from .profile import store

Log = Callable[[str], None]


def seed_boards() -> dict[str, list[str]]:
    """Board Vin tự chọn, gõ tay trong config/boards.toml."""
    path = PROJECT_ROOT / "config" / "boards.toml"
    raw = tomllib.loads(path.read_text()) if path.exists() else {}
    return {k: v.get("boards", []) for k, v in raw.items()}


def load_boards(conn) -> dict[str, list[str]]:
    """GỘP hai nguồn board: người chọn + máy học được.

    LỖI ĐÃ SỬA: trước đây file chỉ là DỰ PHÒNG khi bảng công ty rỗng. Bảng có
    53 dòng nên file không bao giờ được đọc — 5 board gõ tay (aqr, cohere,
    palantir, ramp, synthesia) chưa từng được quét lần nào. Sửa boards.toml
    xong không có gì xảy ra, mà cũng không báo gì.

    Danh sách người chọn phải LUÔN được tôn trọng: đó là chỗ duy nhất Vin nói
    được "tôi muốn theo dõi nhà này", kể cả khi nó chưa từng đăng tin nào.
    """
    from .ingest.web import companies as co
    out = {k: list(v) for k, v in seed_boards().items()}
    for ats, slugs in co.boards(conn).items():
        out.setdefault(ats, [])
        out[ats] += [s for s in slugs if s not in out[ats]]
    return out


def _run_source(conn, name: str, fn, *args, log: Log) -> tuple[int, int]:
    """Một nguồn hỏng KHÔNG được làm hỏng cả lần quét."""
    try:
        items = fn(*args)
    except Exception as exc:                          # noqa: BLE001
        postings.record_run(conn, name, ok=False, error=f"{type(exc).__name__}: {exc}")
        jlog.error(SEARCH, f"{name}: {type(exc).__name__} — {str(exc)[:60]}")
        log(f"  {name:26} FAILED  {type(exc).__name__}: {str(exc)[:50]}")
        return 0, 0
    seen, new = postings.save_batch(conn, name, items)
    postings.record_run(conn, name, ok=True, fetched=seen, new_rows=new)
    # Chỉ ghi khi CÓ tin mới. 62 board chạy mỗi giờ, ghi cả 62 dòng "0 tin mới"
    # thì nhật ký thành rác và người đọc bỏ qua luôn cả dòng thật.
    if new:
        jlog.emit(SEARCH, f"{name}: {seen} tin, {new} mới")
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

    jlog.progress(SEARCH, "mở Chrome")
    try:
        chrome.launch(headless=False)          # headed: trang chặn headless
    except chrome.ChromeError as exc:
        jlog.error(SEARCH, f"không mở được Chrome: {exc}")
        log(f"  chrome                     FAILED  {exc}")
        return 0, 0

    # eFinancialCareers đã BỎ: 67% tin của nó là môi giới (LinkedIn 24%), mà chỉ
    # cho 5 tin đạt 75+ so với 20 của LinkedIn. Bẩn gấp ba, ít hơn bốn lần.
    # titles[:5] ĐÃ BỎ: nó cắt 7/12 chức danh của hồ sơ mà không báo gì, và
    # nó tồn tại chỉ vì vòng đọc kỹ chạy quá lâu. Sửa gốc rồi thì không cần
    # cắt nữa — trần bây giờ nằm ở li.MAX_QUERIES và có ghi nhật ký khi chạm.
    places = li.places_for(answers.get("markets") or [])
    seen = postings.already_read(conn, li.NAME)
    jlog.emit(SEARCH, f"linkedin: {len(titles)} chức danh × {len(places)} nơi"
                      f" · bỏ qua {len(seen)} tin đã đọc")
    sources = [
        (li.NAME, lambda tab: li.fetch(tab, titles, location=places,
                                       levels=levels, pages=4, deep=deep,
                                       skip=frozenset(seen),
                                       stop=lambda: halt.wanted(STAGE))),
    ]

    total_seen = total_new = 0
    for name, run in sources:
        tab = None
        try:
            tab = cdp.open_tab()
            items, health = run(tab)
            seen, new = postings.save_batch(conn, name, items)
            # health.ok chứ không phải True cứng: nguồn bị chặn giữa chừng vẫn
            # trả về tin (những tin đọc kịp), nhưng lần quét đó KHÔNG lành.
            postings.record_run(conn, name, ok=health.ok, fetched=seen, new_rows=new,
                                error="" if health.ok else f"blocked: {health.summary}",
                                attempted=health.attempted, failed=health.failed)
            bad = f"  ⚠ {health.summary}" if health.failed else ""
            (jlog.ok if health.ok else jlog.warn)(
                SEARCH, f"{name}: {seen} tin, {new} mới"
                        + (f" · {health.summary}" if health.summary else ""))
            log(f"  {name:26} {seen:5} tin, {new:5} mới{bad}")
            total_seen += seen; total_new += new
        except Blocked as exc:
            # Trang từ chối truy cập tự động. Ghi nhận rồi thôi — không cãi lại.
            postings.record_run(conn, name, ok=False, error=f"blocked: {exc}")
            postings.log(conn, "source_blocked", f"{name}: {exc}")
            jlog.warn(SEARCH, f"{name}: BỊ CHẶN — {str(exc)[:60]}")
            log(f"  {name:26} BLOCKED {str(exc)[:44]}")
        except Exception as exc:                # noqa: BLE001
            postings.record_run(conn, name, ok=False,
                                error=f"{type(exc).__name__}: {exc}")
            jlog.error(SEARCH, f"{name}: {type(exc).__name__} — {str(exc)[:60]}")
            log(f"  {name:26} FAILED  {type(exc).__name__}: {str(exc)[:40]}")
        finally:
            if tab is not None:
                tab.close()

    # Đóng Chrome khi xong việc. Không đóng thì nó nằm trên màn hình cho tới
    # lần quét sau — mà lần quét sau là MỘT TIẾNG nữa. Chrome chỉ tồn tại để
    # phục vụ vòng quét, hết vòng là hết việc.
    # Mở lại tốn ~2 giây, không đáng để đánh đổi một cửa sổ nằm lì cả tiếng.
    if not chrome.shutdown():
        jlog.warn(SEARCH, "không đóng được Chrome — nó vẫn đang mở")
    return total_seen, total_new


def run_scan(log: Log | None = None, chrome_sources: bool = True,
             deep: bool = True, manual: bool = False) -> dict:
    say: Log = log or (lambda _msg: None)
    conn = db.connect()
    try:
        answers = store.load(conn)
        if not store.can_ingest(answers):
            return {"ok": False, "summary": "hồ sơ chưa đủ",
                    "missing": store.missing_for_ingest(answers)}

        # Mốc thời gian, KHÔNG phải con số tổng: "việc mới" là việc lần quét
        # NÀY mang về, không phải hiệu của hai lần đếm. Lấy hiệu thì một lần
        # quét mang về 10 việc mới mà đồng thời 10 việc cũ bị loại sẽ ra 0,
        # và người dùng không được báo gì cả.
        started_at = postings.now()
        boards = load_boards(conn)
        postings.log(conn, "scan_started")

        # arbeitnow + remotive ĐÃ BỎ: sai thị trường. Arbeitnow là job board
        # châu Âu, Remotive là remote toàn cầu — hai nguồn tải về 1.992 tin để
        # giữ lại đúng 1. Vin ở UK, visa không xin sponsor.
        # Board công ty thì giữ: tỉ lệ thấp là vì tải cả board rồi mới lọc,
        # nhưng đó là chủ việc TRỰC TIẾP và chỉ tốn HTTP.
        todo = [(f"{key}:{board}", mod.fetch_board, (board,))
                for mod, key in ((greenhouse, "greenhouse"), (lever, "lever"),
                                 (ashby, "ashby"))
                # dict.fromkeys: hai công ty tên khác nhau có thể ra CÙNG một
                # slug ("Ocado" và "Ocado Group" -> ocadogroup) -> gọi HTTP hai
                # lần cho một board và cộng đôi vào tổng "thấy".
                for board in dict.fromkeys(boards.get(key, []))]
        jlog.emit(SEARCH, f"bắt đầu quét — {len(todo)} nguồn API"
                          + (" + LinkedIn qua Chrome" if chrome_sources else ""))

        total_seen = total_new = 0
        stopped = False
        for index, (name, fn, args) in enumerate(todo, 1):
            # Điểm ngắt: GIỮA hai nguồn, không phải giữa một giao dịch. Nửa
            # giao dịch ghi vào DB còn tệ hơn chạy nốt nguồn đang dở.
            if halt.wanted(STAGE):
                stopped = True
                break
            jlog.progress(SEARCH, f"nguồn API — {name}", index, len(todo))
            s, n = _run_source(conn, name, fn, *args, log=say)
            total_seen += s; total_new += n

        if chrome_sources and not stopped and not halt.wanted(STAGE):
            s, n = _chrome_pass(conn, answers, say, deep, manual)
            total_seen += s; total_new += n
        elif chrome_sources:
            jlog.warn(SEARCH, "bỏ qua LinkedIn — đã xin dừng")

        if halt.wanted(STAGE):
            stopped = True

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

        fresh_matches = int(conn.execute(
            "SELECT COUNT(*) FROM posting p JOIN raw_posting r ON p.raw_id = r.id"
            " WHERE p.kept = 1 AND r.fetched_at >= ?", (started_at,)).fetchone()[0])

        summary = (f"thấy {total_seen} · mới {total_new} · giữ {kept} · "
                   f"{n_groups} việc duy nhất · {agencies} qua môi giới")
        postings.log(conn, "scan_finished", summary)
        jlog.done(SEARCH)
        jlog.ok(SEARCH, f"quét xong — {summary}")
        return {"ok": True, "summary": summary, "seen": total_seen, "new": total_new,
                "kept": kept, "groups": n_groups, "scored": marks["scored"],
                "new_matches": fresh_matches}
    finally:
        conn.close()
