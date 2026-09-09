"""Thông báo macOS — qua osascript, không cần cài gì.

Luật: BÁO ÍT THÔI. Báo nhiều thì bị phớt lờ, và lúc đó cổng Yes/No thành vô dụng.
Chỉ báo khi CẦN NGƯỜI LÀM GÌ ĐÓ, không báo "đã quét xong 47 tin".

LỖI ĐÃ SỬA: trước đây dựng câu lệnh bằng shlex.quote — đó là cách rào chuỗi
cho SHELL, không phải cho AppleScript. shlex.quote("Jobbot") trả về Jobbot
trần, AppleScript đọc ra một danh từ nó không biết:

    display notification '5 new matches' with title Jobbot
    -> 21:22: syntax error ... found unknown token. (-2741)

Nghĩa là KHÔNG một thông báo nào từng hiện lên, và send() trả False mà không
ai đọc. AppleScript rào chuỗi bằng dấu nháy KÉP, thoát \\ và " bằng gạch chéo.
"""

from __future__ import annotations

import subprocess


def _as_string(text: str) -> str:
    """Một chuỗi AppleScript hợp lệ. Xuống dòng cũng phải thoát, nếu không câu
    lệnh bị cắt làm đôi."""
    escaped = (str(text).replace("\\", "\\\\").replace('"', '\\"')
               .replace("\n", "\\n").replace("\r", ""))
    return f'"{escaped}"'


def script(title: str, message: str, subtitle: str = "") -> str:
    parts = [f"display notification {_as_string(message)}",
             f"with title {_as_string(title)}"]
    if subtitle:
        parts.append(f"subtitle {_as_string(subtitle)}")
    return " ".join(parts)


def send(title: str, message: str, subtitle: str = "") -> bool:
    """True = đã hiện lên. False = KHÔNG hiện — người gọi phải xử lý, đừng nuốt."""
    try:
        subprocess.run(["osascript", "-e", script(title, message, subtitle)],
                       check=True, capture_output=True, timeout=10)
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False
