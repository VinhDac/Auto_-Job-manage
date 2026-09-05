"""Dữ liệu THẬT từ DB — thay dần cho mock.py.

Mỗi hàm ở đây trả về ĐÚNG hình dạng hàm cùng tên trong mock.py.
Đó là lý do trang không phải sửa gì khi chuyển từ giả sang thật.

Đã nối thật:  run_status · counters · jobs · job_detail · activity
Còn dùng giả: proposals · pipeline · projects · stats   (bước 4-6)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..core import postings
from ..dedup import group


def _ago(stamp: str) -> str:
    """Nguồn trả ngày theo 2 kiểu: ISO (Greenhouse/Lever) và Unix (Arbeitnow)."""
    if not stamp:
        return ""
    try:
        then = (datetime.fromtimestamp(int(stamp), timezone.utc)
                if str(stamp).isdigit() else datetime.fromisoformat(stamp))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OSError, OverflowError):
        return ""
    seconds = (datetime.now(timezone.utc) - then).total_seconds()
    if seconds < 90:
        return "just now"
    if seconds < 5400:
        return f"{int(seconds // 60)} min ago"
    if seconds < 172800:
        return f"{int(seconds // 3600)} hours ago"
    return f"{int(seconds // 86400)} days ago"


def run_status(conn: sqlite3.Connection) -> dict:
    runs = postings.last_runs(conn)
    failed = [f"{r['source']} — {r['error'][:60]}" for r in runs if not r["ok"]]
    last = max((r["at"] for r in runs), default="")
    return {
        "state": "idle" if runs else "never run",
        "last_scan": _ago(last) if last else "never",
        "next_scan": "manual — run scripts/scan.py",
        "window": "08:00 – 22:00 (human-paced sources)",
        "sources_ok": sum(1 for r in runs if r["ok"]),
        "sources_total": len(runs),
        "sources_failed": failed or ["Adzuna GB — no API key (biggest UK source)"],
    }


def counters(conn: sqlite3.Connection) -> list[dict]:
    total = postings.count(conn)
    kept = postings.count(conn, kept_only=True)
    unique = postings.count_groups(conn)
    return [
        {"value": f"{total:,}", "label": "Postings pulled", "note": "all sources"},
        {"value": f"{kept:,}", "label": "Match your titles", "note": f"{total - kept:,} filtered out"},
        {"value": f"{unique:,}", "label": "Unique jobs", "note": f"{kept - unique} duplicates merged"},
        {"value": "—", "label": "Scored", "note": "step 2"},
        {"value": "—", "label": "Applications", "note": "step 5"},
        {"value": "—", "label": "Replies", "note": "step 6"},
    ]


def jobs(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for g in group.groups(conn):
        p = g["posting"]
        out.append({
            "id": str(p["id"]),
            "title": p["title"], "company": p["company"],
            "location": p["location"] or "not stated",
            "salary": p["salary"] or "not stated",
            "score": None,                      # chưa chấm — bước 2
            "posted": _ago(p["posted_at"]) if p["posted_at"] else "",
            "closes": "",
            "sources": g["sources"],
            "merged": g["count"],
            "state": "new",
            "url": p["url"],
        })
    return out


def job_detail(conn: sqlite3.Connection, job_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM posting WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    same = conn.execute(
        "SELECT source, url FROM posting WHERE group_id = ? ORDER BY id",
        (row["group_id"] or str(row["id"]),)).fetchall()
    return {
        "id": str(row["id"]), "title": row["title"], "company": row["company"],
        "location": row["location"] or "not stated",
        "salary": row["salary"] or "not stated",
        "score": None, "posted": _ago(row["posted_at"]) if row["posted_at"] else "",
        "sources": sorted({r["source"] for r in same}),
        "merged": len(same), "url": row["url"],
        "jd": row["description"] or "(no description from this source)",
        "requirements": [],                     # bước 2
        "cv_changes": [],                       # bước 3
        "project": None,                        # bước 4
    }


def needs_you(conn: sqlite3.Connection) -> list[dict]:
    """Chỉ nói những việc CÓ THẬT. Chưa tới bước nào thì nói thẳng chưa tới."""
    out: list[dict] = []
    unique = postings.count_groups(conn)

    if postings.count(conn) == 0:
        out.append({"kind": "approve", "text": "No postings yet — run the first scan",
                    "href": "/settings", "note": "python3 scripts/scan.py"})
        return out

    out.append({
        "kind": "approve",
        "text": f"{unique} jobs found and waiting to be scored",
        "href": "/jobs",
        "note": "Scoring is step 2 — it needs your full CV, especially the WorldQuant detail",
    })
    out.append({
        "kind": "mail",
        "text": "Adzuna GB is off — the biggest UK source",
        "href": "/settings",
        "note": "Free key at developer.adzuna.com, about 2 minutes. Without it, UK "
                "graduate schemes are largely invisible to the system.",
    })
    return out


def activity(conn: sqlite3.Connection) -> list[dict]:
    kind_map = {"scan_started": "scan", "scan_finished": "scan",
                "source_failed": "warn"}
    return [
        {"time": _ago(r["at"]), "kind": kind_map.get(r["kind"], "check"),
         "text": f"{r['kind'].replace('_', ' ')}" + (f" — {r['detail']}" if r["detail"] else "")}
        for r in postings.recent_audit(conn, 12)
    ]
