"""Thông báo hệ điều hành — macOS, Windows, Linux. Không cài gì thêm.

    macOS    osascript (AppleScript)
    Windows  PowerShell + WinRT toast — CHƯA thử trên máy Windows thật
    Linux    notify-send

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
import sys


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


def _mac(title: str, message: str, subtitle: str) -> list[str]:
    return ["osascript", "-e", script(title, message, subtitle)]


def _windows(title: str, message: str, subtitle: str) -> list[str]:
    """Toast của Windows 10/11 qua PowerShell — không cài thêm gì.

    Dùng WinRT có sẵn trong hệ. BurntToast tiện hơn nhưng phải cài module,
    mà cả app này không cài gói nào.

    CHƯA THỬ TRÊN MÁY WINDOWS THẬT — viết theo tài liệu. Hỏng thì send() trả
    False và scheduler ghi 'notify_failed' vào nhật ký, không im lặng.
    """
    body = message + (f"\n{subtitle}" if subtitle else "")
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager,"
        "Windows.UI.Notifications,ContentType=WindowsRuntime] > $null;"
        "$t=[Windows.UI.Notifications.ToastNotificationManager]::"
        "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        f"$x=$t.GetXml();$n=$t.GetElementsByTagName('text');"
        f"$n.Item(0).AppendChild($t.CreateTextNode({_ps_quote(title)}))>$null;"
        f"$n.Item(1).AppendChild($t.CreateTextNode({_ps_quote(body)}))>$null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::"
        "CreateToastNotifier('jobbot').Show("
        "[Windows.UI.Notifications.ToastNotification]::new($t))"
    )
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]


def _linux(title: str, message: str, subtitle: str) -> list[str]:
    body = message + (f"\n{subtitle}" if subtitle else "")
    return ["notify-send", title, body]


def _ps_quote(text: str) -> str:
    """Chuỗi PowerShell rào bằng nháy ĐƠN; bên trong, nháy đơn nhân đôi."""
    return "'" + str(text).replace("'", "''").replace("\r", "") + "'"


BUILDERS = {"darwin": _mac, "win32": _windows}


def command(title: str, message: str, subtitle: str = "") -> list[str]:
    """Lệnh sẽ chạy trên hệ hiện tại. Tách ra để test được mà không phải gọi."""
    build = BUILDERS.get(sys.platform, _linux)
    return build(title, message, subtitle)


def send(title: str, message: str, subtitle: str = "") -> bool:
    """True = đã hiện lên. False = KHÔNG hiện — người gọi phải xử lý, đừng nuốt."""
    try:
        subprocess.run(command(title, message, subtitle),
                       check=True, capture_output=True, timeout=10)
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False
