"""Lưu hồ sơ theo phiên bản.

Mỗi lần lưu tạo MỘT PHIÊN BẢN MỚI = ảnh chụp đầy đủ (câu cũ mang sang + câu vừa sửa).
Không ghi đè. Vì hồ sơ là dữ liệu sống — sau 50 lần bị từ chối thì mong muốn sẽ khác
lúc đầu, và ta cần nhìn lại được nó đã đổi thế nào.

Giá phải trả: tốn chỗ. Với vài chục phiên bản text thì không đáng kể.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .schema import ROUNDS, Round, all_questions

Answers = dict[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def latest_version_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT MAX(id) AS id FROM profile_version").fetchone()
    return row["id"] if row and row["id"] is not None else None


def load(conn: sqlite3.Connection) -> Answers:
    """Hồ sơ hiện tại = phiên bản mới nhất. Chưa có gì thì trả về rỗng."""
    version_id = latest_version_id(conn)
    if version_id is None:
        return {}
    rows = conn.execute(
        "SELECT question_id, value_json FROM profile_answer WHERE version_id = ?",
        (version_id,),
    ).fetchall()
    return {r["question_id"]: json.loads(r["value_json"]) for r in rows}


def save(conn: sqlite3.Connection, changed: Answers, note: str = "") -> int:
    """Tạo phiên bản mới = hồ sơ cũ + phần vừa sửa. Trả về id phiên bản."""
    known = all_questions()
    merged = load(conn)
    merged.update({k: v for k, v in changed.items() if k in known})

    cursor = conn.execute(
        "INSERT INTO profile_version (created_at, note) VALUES (?, ?)", (_now(), note)
    )
    version_id = int(cursor.lastrowid)
    conn.executemany(
        "INSERT INTO profile_answer (version_id, question_id, value_json) VALUES (?, ?, ?)",
        [(version_id, qid, json.dumps(val, ensure_ascii=False)) for qid, val in merged.items()],
    )
    conn.commit()
    return version_id


def history(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, created_at, note FROM profile_version ORDER BY id DESC"
    ).fetchall()


def _has_value(answers: Answers, question_id: str) -> bool:
    value = answers.get(question_id)
    if value is None:
        return False
    if isinstance(value, (list, str)):
        return len(value) > 0
    return True


def missing_in_round(answers: Answers, round_: Round) -> list[str]:
    """Câu bắt buộc còn thiếu trong một vòng."""
    return [q.id for q in round_.questions if q.required and not _has_value(answers, q.id)]


def is_round_done(answers: Answers, round_: Round) -> bool:
    return not missing_in_round(answers, round_)


def next_unfinished_round(answers: Answers) -> Round | None:
    """Vòng tiếp theo cần làm. Xong hết thì None."""
    return next((r for r in ROUNDS if not is_round_done(answers, r)), None)


def can_ingest(answers: Answers) -> bool:
    """Đã đủ điều kiện cho phép kéo tin về chưa. Vòng 1 là cổng chặn."""
    return is_round_done(answers, ROUNDS[0])
