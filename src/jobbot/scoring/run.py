"""Chấm điểm mọi tin đang giữ, lưu kết quả kèm lời giải thích.

Chạy sau mỗi lần quét. Chỉ chấm tin `kept=1` — chấm cả 4.000 tin thì tốn công
mà 3.976 cái trong đó đã bị loại từ vòng lọc rồi.

Chấm lại từ đầu mỗi lần: rẻ (thuần chuỗi, ~20ms cho 24 tin) và hồ sơ đổi thì
điểm phải đổi theo. Cache ở đây sẽ chỉ khiến điểm cũ mắc kẹt.
"""

from __future__ import annotations

import json
import sqlite3

from ..profile import store
from .score import score_job


def score_all(conn: sqlite3.Connection) -> dict:
    answers = store.load(conn)
    rows = conn.execute(
        "SELECT id, title, description FROM posting WHERE kept = 1").fetchall()

    scored = unscorable = 0
    updates = []
    for row in rows:
        result = score_job(row["title"], row["description"], answers)
        if result["score"] is None:
            unscorable += 1
        else:
            scored += 1
        updates.append((result["score"], result["confidence"],
                        json.dumps(result, ensure_ascii=False), row["id"]))

    conn.executemany(
        "UPDATE posting SET score=?, score_conf=?, score_json=? WHERE id=?", updates)
    conn.commit()
    return {"scored": scored, "unscorable": unscorable, "total": len(rows)}


def explanation(conn: sqlite3.Connection, posting_id: int) -> dict | None:
    row = conn.execute("SELECT score_json FROM posting WHERE id = ?",
                       (posting_id,)).fetchone()
    if not row or not row["score_json"]:
        return None
    return json.loads(row["score_json"])
