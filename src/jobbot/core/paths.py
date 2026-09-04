"""Đường dẫn — phải chạy giống nhau trên macOS / Windows / Linux.

Luật: không bao giờ ghép đường dẫn bằng chuỗi. Chỉ dùng pathlib.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent      # src/jobbot
PROJECT_ROOT = PACKAGE_DIR.parent.parent                  # gốc repo


def data_dir() -> Path:
    """Nơi chứa DB và cache. Đổi được bằng biến môi trường JOBBOT_DATA_DIR."""
    override = os.environ.get("JOBBOT_DATA_DIR")
    path = Path(override).expanduser() if override else PROJECT_ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "jobbot.db"


def web_dir() -> Path:
    return PACKAGE_DIR / "dashboard" / "web"
