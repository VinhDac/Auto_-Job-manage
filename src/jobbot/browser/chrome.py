"""Khởi động và quản lý một Chrome RIÊNG.

BA RÀNG BUỘC, cố ý:

1. **Profile riêng.** Chrome không cho hai tiến trình mở cùng một profile, nên
   dùng profile chính thì mỗi lần app chạy bạn phải đóng hết Chrome đang lướt.
   Profile riêng -> đăng nhập một lần, sau đó chạy nền độc lập.
2. **Cổng riêng** (9333), không phải 9222 mặc định — tránh đụng công cụ khác.
3. **Không bao giờ đụng vào Chrome người dùng đang mở.**
4. **Một cổng = một profile.** Chrome khoá thư mục profile: hai tiến trình cùng
   một `--user-data-dir` thì cái thứ hai lặng lẽ chết, cổng debug không bao giờ
   mở. Đo được: 9333 lên, 9334 cùng profile -> "Chrome không lên trong 8s".
   Nên profile suy ra TỪ CỔNG, không phải tham số ai đó phải nhớ truyền.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..core.paths import data_dir

PORT = 9333          # vòng quét — có cửa sổ, Vin nhìn được
PDF_PORT = 9334      # in CV — ẩn
APPLY_PORT = 9335    # điền form nộp — có cửa sổ, Vin bấm cú cuối

# Một cổng một profile. Xem ràng buộc 4 ở đầu tệp.
PROFILE = {PORT: "chrome-profile", PDF_PORT: "chrome-pdf",
           APPLY_PORT: "chrome-apply"}


def _candidates() -> list[str]:
    """Chỗ Chrome hay nằm, theo từng hệ điều hành.

    Windows: đường dẫn có biến môi trường (%LOCALAPPDATA% khi cài cho riêng
    một tài khoản, Program Files khi cài cho cả máy) nên phải dựng lúc chạy,
    không hằng số hoá được.
    """
    if sys.platform == "win32":
        roots = [os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                 os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                 os.environ.get("LOCALAPPDATA", "")]
        out = []
        for root in filter(None, roots):
            out += [str(Path(root) / "Google/Chrome/Application/chrome.exe"),
                    str(Path(root) / "Chromium/Application/chrome.exe"),
                    str(Path(root) / "BraveSoftware/Brave-Browser/Application/brave.exe"),
                    str(Path(root) / "Microsoft/Edge/Application/msedge.exe")]
        return out
    if sys.platform == "darwin":
        return ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    return ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium", "/usr/bin/chromium-browser",
            "/snap/bin/chromium"]


CANDIDATES = _candidates()


class ChromeError(RuntimeError):
    pass


# Tên lệnh để dò trong PATH, khi Chrome cài ở chỗ lạ.
ON_PATH = ["google-chrome", "google-chrome-stable", "chromium",
           "chromium-browser", "chrome", "msedge"]


def binary() -> str:
    for path in _candidates():
        if Path(path).is_file():
            return path
    for name in ON_PATH:
        found = shutil.which(name)
        if found:
            return found
    raise ChromeError(
        "Không tìm thấy Chrome. Cài Google Chrome rồi thử lại "
        f"(đã dò {len(_candidates())} chỗ quen thuộc trên {sys.platform}).")


def profile_dir(port: int = PORT) -> Path:
    path = data_dir() / PROFILE.get(port, f"chrome-{port}")
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
        f"--user-data-dir={profile_dir(port)}",
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


def shutdown(port: int = PORT, wait: float = 6.0) -> bool:
    """Đóng Chrome RIÊNG. Không đụng tới Chrome người dùng đang mở.

    Trả True nếu nó thật sự tắt.

    LỖI ĐÃ SỬA: bản cũ gọi GET /json/close — endpoint đó cần kèm target id
    (/json/close/<id>) nên trả 404, và lỗi bị nuốt trong except. Hàm chạy êm
    ru, trả None, mà Chrome vẫn nguyên đó. Cách đúng là lệnh CDP Browser.close
    trên WebSocket của TRÌNH DUYỆT, không phải của tab.

    Vì sao không kill thẳng tiến trình: Chrome cá nhân của người dùng cũng là
    tiến trình "Google Chrome". Đi qua cổng debug 9333 thì chỉ chạm đúng bản
    chạy bằng profile riêng của app.
    """
    from .ws import WebSocket, WSError

    if not alive(port):
        return True
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=3) as r:
            browser_ws = json.load(r)["webSocketDebuggerUrl"]
        control = WebSocket(browser_ws)
        try:
            control.send(json.dumps({"id": 1, "method": "Browser.close"}))
            # Không chờ trả lời: Chrome đóng kết nối NGAY khi nhận lệnh, nên
            # recv() ở đây sẽ ném lỗi — đó là dấu hiệu thành công, không phải hỏng.
            try:
                control.recv()
            except (WSError, OSError):
                pass
        finally:
            try:
                control.close()
            except Exception:                      # noqa: BLE001
                pass
    except Exception:                              # noqa: BLE001
        return False

    deadline = time.time() + wait
    while time.time() < deadline:
        if not alive(port):
            return True
        time.sleep(0.3)
    return not alive(port)
