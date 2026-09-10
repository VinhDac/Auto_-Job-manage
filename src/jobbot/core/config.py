"""Đọc config/config.toml — MỘT chỗ.

Trước đây mỗi module tự mở tệp bằng tomllib. Hai bộ đọc là hai cách hiểu về
cùng một tệp, và chúng trôi xa nhau mà không ai biết — đúng bệnh vừa chữa ở
tầng chấm điểm và tầng dựng CV.

Không có tệp thì trả {} chứ không nổ: app phải chạy được khi Vin chưa cấu
hình gì, chỉ là mấy tính năng cần cấu hình thì tự tắt.
"""

from __future__ import annotations

import tomllib

from .paths import PROJECT_ROOT

PATH = PROJECT_ROOT / "config" / "config.toml"


def load() -> dict:
    if not PATH.exists():
        return {}
    try:
        return tomllib.loads(PATH.read_text())
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def section(name: str) -> dict:
    got = load().get(name)
    return got if isinstance(got, dict) else {}
