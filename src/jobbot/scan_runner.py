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


def load_boards() -> dict:
    path = PROJECT_ROOT / "config" / "boards.toml"
    return tomllib.loads(path.read_text()) if path.exists() else {}


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


def run_scan(pages: int = 3, log: Log | None = None) -> dict:
    say: Log = log or (lambda _msg: None)
    conn = db.connect()
    try:
        answers = store.load(conn)
        if not store.can_ingest(answers):
            return {"ok": False, "summary": "hồ sơ chưa đủ",
                    "missing": store.missing_for_ingest(answers)}

        before_kept = postings.count(conn, kept_only=True)
        boards = load_boards()
        postings.log(conn, "scan_started")

        total_seen = total_new = 0
        for name, fn, args in ((arbeitnow.NAME, arbeitnow.fetch, (pages,)),
                               (remotive.NAME, remotive.fetch, ())):
            s, n = _run_source(conn, name, fn, *args, log=say)
            total_seen += s; total_new += n

        for mod, key in ((greenhouse, "greenhouse"), (lever, "lever"), (ashby, "ashby")):
            for board in boards.get(key, {}).get("boards", []):
                s, n = _run_source(conn, f"{key}:{board}", mod.fetch_board, board, log=say)
                total_seen += s; total_new += n

        # --- lọc theo hồ sơ ---
        rows = conn.execute("SELECT * FROM posting").fetchall()
        kept = 0
        for row in rows:
            item = Posting(source_id="", title=row["title"], company=row["company"],
                           location=row["location"], remote=bool(row["remote"]),
                           description=row["description"])
            keep, reason = jobfilter.judge(item, answers)
            conn.execute("UPDATE posting SET kept = ?, drop_reason = ? WHERE id = ?",
                         (int(keep), "" if keep else reason, row["id"]))
            kept += int(keep)
        conn.commit()
        say(f"\n  lọc: {len(rows)} tin -> giữ {kept}, bỏ {len(rows) - kept}")

        n_rows, n_groups = group.regroup(conn)
        say(f"  gộp: {n_rows} tin -> {n_groups} việc duy nhất")

        marks = score_all(conn)
        say(f"  chấm: {marks['scored']} tin có điểm, "
            f"{marks['unscorable']} không đọc được yêu cầu")

        summary = (f"thấy {total_seen} · mới {total_new} · "
                   f"giữ {kept} · {n_groups} việc duy nhất")
        postings.log(conn, "scan_finished", summary)
        return {"ok": True, "summary": summary, "seen": total_seen, "new": total_new,
                "kept": kept, "groups": n_groups, "scored": marks["scored"],
                "new_matches": max(0, kept - before_kept)}
    finally:
        conn.close()
