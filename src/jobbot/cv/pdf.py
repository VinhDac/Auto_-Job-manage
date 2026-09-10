"""In một bản CV ra PDF — bằng chính Chrome đã có, không thêm thư viện.

Vì sao không dùng reportlab/weasyprint: cả app là stdlib, và thêm một bộ dựng
PDF nghĩa là có HAI cách vẽ cùng một tờ CV — bản màn hình và bản giấy sẽ trôi
xa nhau, mà bản giấy mới là bản nhà tuyển dụng đọc.

Chrome in ĐÚNG trang đang hiển thị, qua `@media print` trong app.css. Một
nguồn sự thật cho cả hai.

Chạy Chrome HEADLESS ở cổng riêng: cổng 9333 là của vòng quét, đang mở cửa sổ
thật để đọc LinkedIn. Bấm nút In mà cướp mất tab của vòng quét là hỏng việc
đang chạy.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

from ..browser import cdp, chrome

PORT = chrome.PDF_PORT   # cổng RIÊNG, profile RIÊNG — xem chrome.PROFILE

PAPER = {                                    # A4, lề 14mm — khớp @page trong CSS
    "paperWidth": 8.27, "paperHeight": 11.69,
    "marginTop": 0.55, "marginBottom": 0.55,
    "marginLeft": 0.59, "marginRight": 0.59,
    "printBackground": False,                # nền tối của app không được in ra
    "preferCSSPageSize": True,
}


def slug(text: str) -> str:
    keep = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return keep[:60] or "cv"


def _print_one(tab, url: str, out: Path, timeout: float) -> Path:
    tab.go(url, wait_for=".cvpaper", timeout=timeout)
    reply = tab.call("Page.printToPDF", PAPER, timeout=timeout)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(reply["data"]))
    return out


def render(url: str, out: Path, timeout: float = 45.0) -> Path:
    """In MỘT bản."""
    return next(iter(render_many([(url, out)], timeout=timeout)))


def render_many(jobs, timeout: float = 45.0, on_done=None):
    """In NHIỀU bản, dùng chung MỘT Chrome và MỘT tab.

    Mở/tắt Chrome chiếm gần hết thời gian một lần in. Mở lại cho từng bản thì
    41 bản mất mấy phút và bật tắt Chrome 41 lần; giữ một tab rồi điều hướng
    liên tiếp thì phần cố định trả đúng một lần.

    `jobs` = [(url, đường dẫn ra)]. `on_done(i, tổng, đường dẫn)` để báo tiến độ.
    """
    jobs = list(jobs)
    if not jobs:
        return []
    started = chrome.launch(headless=True, port=PORT)
    tab = cdp.open_tab("about:blank", port=PORT)
    made = []
    try:
        for index, (url, out) in enumerate(jobs, 1):
            try:
                made.append(_print_one(tab, url, Path(out), timeout))
            except Exception:                       # noqa: BLE001
                # Một bản hỏng KHÔNG được làm chết cả lô. Bản còn lại vẫn in.
                made.append(None)
            if on_done:
                on_done(index, len(jobs), made[-1])
    finally:
        try:
            tab.close()
        finally:
            if started is not None:
                chrome.shutdown(port=PORT)
    return [m for m in made if m]
