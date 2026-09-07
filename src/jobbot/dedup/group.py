"""Gộp tin trùng — cùng một việc đăng trên nhiều board.

Bước 1 dùng vân tay: công ty đã chuẩn hoá + chức danh đã chuẩn hoá.
Đủ để bắt phần lớn trùng lặp, và LUÔN GIẢI THÍCH ĐƯỢC vì sao gộp.

Chưa bắt được: cùng việc nhưng tiêu đề khác hẳn ("Grad Analyst 2027" vs
"Graduate Analyst Programme"). Để bước 2 xử lý khi đã có dữ liệu thật để đo.
"""

from __future__ import annotations

import sqlite3


def regroup(conn: sqlite3.Connection, commit: bool = True) -> tuple[int, int]:
    """Gán group_id cho mọi tin đang giữ. Trả về (số tin, số nhóm).

    `commit=False` khi bên gọi đang giữ một giao dịch lớn hơn — tự commit ở đây
    sẽ cắt ngang giao dịch đó và làm mất tính nguyên tử.
    """
    rows = conn.execute(
        "SELECT id, fingerprint FROM posting WHERE kept = 1 ORDER BY id").fetchall()
    first_seen: dict[str, int] = {}
    for row in rows:
        first_seen.setdefault(row["fingerprint"], row["id"])
    conn.executemany(
        "UPDATE posting SET group_id = ? WHERE id = ?",
        [(str(first_seen[r["fingerprint"]]), r["id"]) for r in rows],
    )
    if commit:
        conn.commit()
    return len(rows), len(first_seen)


def groups(conn: sqlite3.Connection) -> list[dict]:
    """Mỗi nhóm một dòng, kèm danh sách nguồn đã thấy nó."""
    rows = conn.execute(
        "SELECT group_id, COUNT(*) AS n, GROUP_CONCAT(DISTINCT source) AS sources,"
        " MIN(id) AS lead_id FROM posting WHERE kept = 1"
        " GROUP BY group_id ORDER BY n DESC, lead_id").fetchall()
    out = []
    for row in rows:
        lead = conn.execute("SELECT * FROM posting WHERE id = ?", (row["lead_id"],)).fetchone()
        out.append({"group_id": row["group_id"], "count": row["n"],
                    "sources": sorted((row["sources"] or "").split(",")),
                    "posting": dict(lead)})
    return out
