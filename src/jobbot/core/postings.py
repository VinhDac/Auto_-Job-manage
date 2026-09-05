"""Lưu và đọc tin tuyển dụng. Bốn tầng tách bạch (design.md §4).

    raw_posting  nguyên văn đã fetch — không đụng vào, fetch lại được
    posting      đã chuẩn hoá — tính lại được từ raw
    source_run   mỗi lần chạy một nguồn: được bao nhiêu, hỏng chỗ nào
    audit        đã làm gì, lúc nào — nguồn của mọi thống kê sau này

Cache nằm ở UNIQUE(source, source_id): tin đã có thì không ghi lại,
nên chạy lại nguồn nhiều lần không sinh rác và không tốn công xử lý.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Iterable

from ..ingest.base import Posting


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- nhật ký

def log(conn: sqlite3.Connection, kind: str, detail: str = "") -> None:
    conn.execute("INSERT INTO audit (at, kind, detail) VALUES (?,?,?)", (now(), kind, detail))
    conn.commit()


def recent_audit(conn: sqlite3.Connection, limit: int = 30) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT at, kind, detail FROM audit ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


# ---------------------------------------------------------------- ghi tin

def save_batch(conn: sqlite3.Connection, source: str, items: Iterable[Posting]) -> tuple[int, int]:
    """Ghi một lô tin. Trả về (số thấy, số mới).

    Tin đã có thì bỏ qua — đó chính là cache. Không ghi đè, không sinh bản trùng.
    """
    seen = new = 0
    for item in items:
        seen += 1
        cur = conn.execute(
            "INSERT OR IGNORE INTO raw_posting (source, source_id, url, fetched_at, payload)"
            " VALUES (?,?,?,?,?)",
            (source, item.source_id, item.url, now(),
             json.dumps(item.payload, ensure_ascii=False)),
        )
        if not cur.rowcount:            # đã có -> bỏ qua, không xử lý lại
            continue
        raw_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO posting (raw_id, source, title, company, location, remote,"
            " salary, url, posted_at, description, fingerprint)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (raw_id, source, item.title, item.company, item.location, int(item.remote),
             item.salary, item.url, item.posted_at, item.description, item.fingerprint()),
        )
        new += 1
    conn.commit()
    return seen, new


def record_run(conn: sqlite3.Connection, source: str, ok: bool,
               fetched: int = 0, new_rows: int = 0, error: str = "") -> None:
    conn.execute(
        "INSERT INTO source_run (source, started_at, ok, fetched, new_rows, error)"
        " VALUES (?,?,?,?,?,?)",
        (source, now(), int(ok), fetched, new_rows, error),
    )
    conn.commit()


# ---------------------------------------------------------------- đọc tin

def count(conn: sqlite3.Connection, kept_only: bool = False) -> int:
    sql = "SELECT COUNT(*) FROM posting" + (" WHERE kept = 1" if kept_only else "")
    return int(conn.execute(sql).fetchone()[0])


def count_groups(conn: sqlite3.Connection) -> int:
    return int(conn.execute(
        "SELECT COUNT(DISTINCT COALESCE(group_id, CAST(id AS TEXT)))"
        " FROM posting WHERE kept = 1").fetchone()[0])


def all_postings(conn: sqlite3.Connection, kept_only: bool = True) -> list[sqlite3.Row]:
    sql = "SELECT * FROM posting" + (" WHERE kept = 1" if kept_only else "") + " ORDER BY id"
    return conn.execute(sql).fetchall()


def source_stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT source, COUNT(*) AS n, SUM(kept) AS kept FROM posting"
        " GROUP BY source ORDER BY n DESC").fetchall()


def last_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT source, MAX(started_at) AS at, ok, fetched, new_rows, error"
        " FROM source_run GROUP BY source ORDER BY source").fetchall()
