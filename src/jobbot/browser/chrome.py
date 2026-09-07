"""Khởi động và quản lý một Chrome RIÊNG.

BA RÀNG BUỘC, cố ý:

1. **Profile riêng.** Chrome không cho hai tiến trình mở cùng một profile, nên
   dùng profile chính thì mỗi lần app chạy bạn phải đóng hết Chrome đang lướt.
   Profile riêng -> đăng nhập một lần, sau đó chạy nền độc lập.
2. **Cổng riêng** (9333), không phải 9222 mặc định — tránh đụng công cụ khác.
3. **Không bao giờ đụng vào Chrome người dùng đang mở.**
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..core.paths import data_dir

PORT = 9333
CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


class ChromeError(RuntimeError):
    pass


def binary() -> str:
    for path in CANDIDATES:
        if Path(path).is_file():
            return path
    found = shutil.which("google-chrome") or shutil.which("chromium")
    if found:
        return found
    raise ChromeError("Không tìm thấy Chrome. Cài Google Chrome rồi thử lại.")


def profile_dir() -> Path:
    path = data_dir() / "chrome-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def alive(port: int = PORT) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version",
                                    timeout=2) as resp:
            return json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return None


def launch(headless: bool = True, port: int = PORT,
           wait: float = 15.0) -> subprocess.Popen | None:
    """Mở Chrome riêng. Đã chạy sẵn thì dùng lại, không mở thêm cái nữa."""
    if alive(port):
        return None

    args = [
        binary(),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir()}",
        "--no-first-run", "--no-default-browser-check",
        "--disable-background-networking", "--disable-sync",
        "--mute-audio", "--window-size=1440,900",
    ]
    if headless:
        args.append("--headless=new")

    process = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    deadline = time.time() + wait
    while time.time() < deadline:
        if alive(port):
            return process
        time.sleep(0.4)
    process.terminate()
    raise ChromeError(f"Chrome không lên trong {wait:g}s")


def shutdown(port: int = PORT) -> None:
    """Đóng Chrome RIÊNG. Không đụng tới Chrome người dùng đang mở."""
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/close", timeout=2)
    except Exception:                              # noqa: BLE001
        pass
