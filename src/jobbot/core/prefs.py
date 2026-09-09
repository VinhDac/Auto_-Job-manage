"""Tuỳ chọn của APP — nhớ qua các lần mở lại.

Khác profile_answer: đó là hồ sơ NGƯỜI DÙNG (có phiên bản, có lịch sử). Đây
chỉ là mấy cái công tắc của chính cái app, không cần lịch sử gì.

Đọc hỏng thì trả về mặc định. Một cái công tắc đọc không được KHÔNG được phép
làm app không mở lên nổi.
"""

from __future__ import annotations

import sqlite3

# Tự quét ngay khi mở app. MẶC ĐỊNH TẮT, cố ý:
# mở app lên mà nó tự mở Chrome đi quét LinkedIn trong lúc người dùng còn chưa
# kịp vào Settings là sai. Người dùng bật khi nào họ thấy đã cấu hình xong.
AUTORUN = "autorun"

DEFAULTS = {AUTORUN: "0"}


def get(conn: sqlite3.Connection, key: str) -> str:
    try:
        row = conn.execute("SELECT value FROM pref WHERE key = ?", (key,)).fetchone()
    except Exception:                       # noqa: BLE001
        return DEFAULTS.get(key, "")
    return row[0] if row else DEFAULTS.get(key, "")


def flag(conn: sqlite3.Connection, key: str) -> bool:
    return get(conn, key) == "1"


def put(conn: sqlite3.Connection, key: str, value: str) -> None:
    try:
        conn.execute("INSERT INTO pref (key, value) VALUES (?,?)"
                     " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (key, str(value)))
        conn.commit()
    except Exception:                       # noqa: BLE001
        pass


def set_flag(conn: sqlite3.Connection, key: str, on: bool) -> None:
    put(conn, key, "1" if on else "0")
