"""Vỏ cửa sổ — chọn cách tốt nhất mà máy này làm được.

    macOS + PyObjC   cửa sổ NSWindow thật, có icon Dock, icon thanh menu
    còn lại          cửa sổ Chrome ở chế độ --app: không thanh địa chỉ,
                     không tab, có icon riêng trên taskbar

Vì sao Chrome --app chứ không phải mở trình duyệt bình thường: mở tab trình
duyệt thì nó là một trang web nằm lẫn giữa hai chục tab khác. --app cho một
cửa sổ đứng riêng, đóng mở như một ứng dụng. Không phải NSWindow, nhưng là
thứ gần nhất mà KHÔNG phải cài gói nào — mà cả app này không cài gói nào.

Chrome đã là thứ bắt buộc phải có (bước 1 điều khiển nó để đọc LinkedIn), nên
dùng nó làm vỏ không thêm ràng buộc mới.

QUAN TRỌNG: cửa sổ giao diện dùng PROFILE RIÊNG, khác profile đi cào. Chung
profile thì cửa sổ người dùng đang mở và tab máy đang lái tranh nhau, và
đóng cái này là chết cái kia.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .core.paths import data_dir

WINDOW = (1440, 900)


def ui_profile_dir() -> Path:
    path = data_dir() / "chrome-ui"
    path.mkdir(parents=True, exist_ok=True)
    return path


def has_mac_native() -> bool:
    """macOS có PyObjC không. Không có thì lùi về cửa sổ Chrome."""
    if sys.platform != "darwin":
        return False
    try:
        import objc                                        # noqa: F401
        from AppKit import NSApplication                   # noqa: F401
    except Exception:                                      # noqa: BLE001
        return False
    return True


def open_window(url: str) -> subprocess.Popen | None:
    """Mở cửa sổ app trỏ vào url. Trả về tiến trình, hoặc None nếu không mở được."""
    from .browser import chrome

    try:
        binary = chrome.binary()
    except chrome.ChromeError:
        return None

    args = [
        binary,
        f"--app={url}",
        f"--user-data-dir={ui_profile_dir()}",
        f"--window-size={WINDOW[0]},{WINDOW[1]}",
        "--no-first-run", "--no-default-browser-check",
        "--disable-background-networking", "--disable-sync",
        # KHÔNG bật --remote-debugging-port ở đây: cổng đó dành cho cửa sổ đi
        # cào. Mở hai cửa sổ cùng cổng thì cdp.open_tab() có thể lái nhầm vào
        # cửa sổ người dùng đang xem.
    ]
    try:
        return subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError:
        return None


def describe() -> str:
    """Một dòng cho người dùng biết đang chạy vỏ nào."""
    if has_mac_native():
        return "cửa sổ macOS (PyObjC)"
    try:
        from .browser import chrome
        return f"cửa sổ Chrome --app ({Path(chrome.binary()).name})"
    except Exception:                                      # noqa: BLE001
        return "không có vỏ — chỉ chạy server, tự mở trình duyệt"
