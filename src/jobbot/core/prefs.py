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

# Ba núm người dùng thật sự đổi. Mọi thứ khác giữ nguyên trong code — bày ra
# một cái núm mà không ai muốn vặn thì đó là rác, không phải lựa chọn.
SCAN_EVERY = "scan_every_min"    # quét lại mỗi bao nhiêu phút
HOURS_FROM = "hours_from"        # Chrome chỉ chạy trong khung giờ này
HOURS_TO = "hours_to"

# NHỊP gọi LinkedIn. Đây là núm hiệu năng THẬT của vòng quét, và nó là một
# núm ĐÁNH ĐỔI chứ không phải núm "nhanh hơn miễn phí": đi nhanh là gọi dày
# hơn, mà LinkedIn là bên duy nhất app đang ở nhờ.
#
# Vì sao không làm "chạy nhiều tab song song": N tab với nhịp P giống hệt 1
# tab với nhịp P/N — cùng số lượt gọi mỗi giây, cùng rủi ro bị bóp. Song song
# chỉ là cách viết phức tạp hơn của một con số nhỏ hơn, cộng thêm N cửa sổ
# Chrome ăn RAM và N chỗ có thể chết nửa chừng.
PACE = "linkedin_pace"

DEFAULTS = {AUTORUN: "0", SCAN_EVERY: "60",
            HOURS_FROM: "8", HOURS_TO: "22", PACE: "thuong"}


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


def num(conn: sqlite3.Connection, key: str, low: int, high: int) -> int:
    """Số nguyên trong khoảng. Giá trị hỏng -> về mặc định, không nổ.

    Người dùng gõ được gì vào ô cũng không được làm chết vòng quét nền.
    """
    try:
        value = int(get(conn, key))
    except (TypeError, ValueError):
        value = int(DEFAULTS.get(key, low))
    return max(low, min(high, value))
