"""Thông báo macOS — qua osascript, không cần cài gì.

Luật: BÁO ÍT THÔI. Báo nhiều thì bị phớt lờ, và lúc đó cổng Yes/No thành vô dụng.
Chỉ báo khi CẦN NGƯỜI LÀM GÌ ĐÓ, không báo "đã quét xong 47 tin".
"""

from __future__ import annotations

import shlex
import subprocess


def send(title: str, message: str, subtitle: str = "") -> bool:
    parts = [f'display notification {shlex.quote(message)}',
             f'with title {shlex.quote(title)}']
    if subtitle:
        parts.append(f'subtitle {shlex.quote(subtitle)}')
    try:
        subprocess.run(["osascript", "-e", " ".join(parts)],
                       check=True, capture_output=True, timeout=10)
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False
