"""SQLite — một file, không cần server, restart không mất dữ liệu.

Migration chạy tiến, không lùi. Mỗi thay đổi schema thêm một phần tử vào
MIGRATIONS, không bao giờ sửa phần tử cũ — DB đang chạy thật ngoài kia.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .paths import db_path

# Chỉ THÊM vào cuối. Không sửa, không xoá phần tử đã có.
MIGRATIONS: list[str] = [
    # 1 — hồ sơ người dùng, lưu theo phiên bản (M0)
    """
    CREATE TABLE profile_version (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT    NOT NULL,
        note       TEXT
    );
    CREATE TABLE profile_answer (
        version_id  INTEGER NOT NULL REFERENCES profile_version(id) ON DELETE CASCADE,
        question_id TEXT    NOT NULL,
        value_json  TEXT    NOT NULL,
        PRIMARY KEY (version_id, question_id)
    );
    """,
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # đọc được trong lúc đang ghi (chạy 24/7)
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Chạy các migration còn thiếu. Trả về số migration vừa chạy."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    ran = 0
    for index in range(current, len(MIGRATIONS)):
        conn.executescript(MIGRATIONS[index])
        conn.execute(f"PRAGMA user_version = {index + 1}")
        conn.commit()
        ran += 1
    return ran
