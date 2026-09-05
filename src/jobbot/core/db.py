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
    # 2 — tin tuyển dụng: raw (nguyên văn) / posting (đã chuẩn hoá) / nhật ký
    """
    CREATE TABLE raw_posting (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source      TEXT    NOT NULL,     -- 'arbeitnow' | 'greenhouse:monzo'
        source_id   TEXT    NOT NULL,     -- id bên nguồn
        url         TEXT,
        fetched_at  TEXT    NOT NULL,
        payload     TEXT    NOT NULL,     -- JSON nguyên văn, không đụng vào
        UNIQUE (source, source_id)
    );

    CREATE TABLE posting (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_id       INTEGER NOT NULL REFERENCES raw_posting(id) ON DELETE CASCADE,
        source       TEXT    NOT NULL,
        title        TEXT    NOT NULL,
        company      TEXT    NOT NULL,
        location     TEXT    NOT NULL DEFAULT '',
        remote       INTEGER NOT NULL DEFAULT 0,
        salary       TEXT    NOT NULL DEFAULT '',
        url          TEXT    NOT NULL DEFAULT '',
        posted_at    TEXT    NOT NULL DEFAULT '',
        description  TEXT    NOT NULL DEFAULT '',
        fingerprint  TEXT    NOT NULL,    -- công ty + chức danh đã chuẩn hoá
        group_id     TEXT,                -- cùng group_id = cùng một việc
        kept         INTEGER NOT NULL DEFAULT 1,   -- 0 = bị lọc bỏ
        drop_reason  TEXT    NOT NULL DEFAULT '',
        UNIQUE (raw_id)
    );
    CREATE INDEX posting_fp    ON posting(fingerprint);
    CREATE INDEX posting_group ON posting(group_id);
    CREATE INDEX posting_kept  ON posting(kept);

    CREATE TABLE source_run (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        source     TEXT    NOT NULL,
        started_at TEXT    NOT NULL,
        ok         INTEGER NOT NULL,
        fetched    INTEGER NOT NULL DEFAULT 0,
        new_rows   INTEGER NOT NULL DEFAULT 0,
        error      TEXT    NOT NULL DEFAULT ''
    );

    -- Ghi từ BƯỚC 1. Thiếu thì đến bước 6 không có gì để đếm và không lấy lại được.
    CREATE TABLE audit (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        at     TEXT NOT NULL,
        kind   TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX audit_at ON audit(at);
    """,
    # 3 — vòng đời ứng tuyển + thư đọc từ hộp thư
    """
    CREATE TABLE application (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        company       TEXT    NOT NULL,
        company_key   TEXT    NOT NULL,          -- tên đã chuẩn hoá, để khớp
        role          TEXT    NOT NULL DEFAULT '',
        posting_id    INTEGER REFERENCES posting(id),
        origin        TEXT    NOT NULL DEFAULT 'mail',   -- mail | manual | auto
        applied_at    TEXT    NOT NULL,
        stage         TEXT    NOT NULL DEFAULT 'applied',
        last_event_at TEXT    NOT NULL DEFAULT '',
        last_event    TEXT    NOT NULL DEFAULT '',
        UNIQUE (company_key, role)
    );
    CREATE INDEX application_stage ON application(stage);

    CREATE TABLE message (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        msg_id         TEXT    NOT NULL UNIQUE,  -- Message-ID của thư
        from_addr      TEXT    NOT NULL DEFAULT '',
        from_name      TEXT    NOT NULL DEFAULT '',
        subject        TEXT    NOT NULL DEFAULT '',
        received_at    TEXT    NOT NULL DEFAULT '',
        snippet        TEXT    NOT NULL DEFAULT '',
        kind           TEXT    NOT NULL DEFAULT 'other',
        company_guess  TEXT    NOT NULL DEFAULT '',
        application_id INTEGER REFERENCES application(id),
        needs_you      INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX message_kind ON message(kind);
    CREATE INDEX message_app  ON message(application_id);
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
