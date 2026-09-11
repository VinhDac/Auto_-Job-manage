"""Moi đường nộp THẬT ra khỏi một tin LinkedIn. CẦN ĐĂNG NHẬP.

Tách khỏi `ingest/web/linkedin.py` có chủ ý: tệp kia hứa ngay dòng đầu là
không đăng nhập, và lời hứa đó vẫn đúng — vòng quét chạy bằng endpoint khách,
không tài khoản nào để mất. Tệp NÀY chỉ chạy khi Vin bấm Nộp một tin, trên
trình duyệt nộp, đọc ĐÚNG MỘT trang. Hai ranh giới khác nhau thì hai tệp.

Đo được (trang khách so với trang đã đăng nhập, cùng một tin):

    khách        0 thẻ apply trong 262 KB, chỉ "sign in to apply"
    đăng nhập    <a>Apply</a> -> linkedin.com/safety/go/?url=<URL công ty>

Nên 111 tin LinkedIn không phải ngõ cụt — chỉ là cái cửa khoá bằng đăng nhập.

LinkedIn mã hoá cả dấu chấm thành %2E trong tham số `url`, nên phải giải mã
chứ không cắt chuỗi bằng tay.
"""

from __future__ import annotations

import re
import urllib.parse

# Nút nộp trên trang đã đăng nhập. Lớp CSS của LinkedIn là chuỗi băm, đổi liên
# tục — bám vào CHỮ và vào đường dẫn, hai thứ đó ổn định hơn nhiều.
FIND_JS = r"""
(() => {
  const out = [];
  for (const a of document.querySelectorAll('a[href]')) {
    const text = (a.innerText || '').trim();
    const href = a.href || '';
    if (!/^apply\b/i.test(text) && !/\/safety\/go\?|\/safety\/go\//.test(href)) continue;
    out.push(href);
  }
  return JSON.stringify(out.slice(0, 6));
})()
"""

SAFETY = re.compile(r"linkedin\.com/safety/go", re.I)
JOBS = re.compile(r"linkedin\.com/(jobs|job)/", re.I)


def unwrap(href: str) -> str:
    """'linkedin.com/safety/go/?url=https%3A%2F%2Fcông-ty…' -> URL công ty."""
    if not href:
        return ""
    if not SAFETY.search(href):
        # CHỈ nhận http/https. Nút Apply trên LinkedIn rất hay là
        # <a href="javascript:void(0)"> mở hộp thoại; trả nguyên si thì
        # tab.go() điều hướng tới một lược đồ không phải web.
        low = href.lower()
        if "linkedin.com" in low or not low.startswith(("http://", "https://")):
            return ""
        return href
    query = urllib.parse.urlparse(href).query
    found = urllib.parse.parse_qs(query).get("url") or []
    out = urllib.parse.unquote(found[0]) if found else ""
    return out if out.lower().startswith(("http://", "https://")) else ""


def apply_url(tab) -> str:
    """Đường nộp thật của tin đang mở. Không moi được thì trả rỗng."""
    import json
    try:
        found = json.loads(tab.eval(FIND_JS) or "[]")
    except Exception:                                # noqa: BLE001
        return ""
    for href in found:
        out = unwrap(href)
        if out and not JOBS.search(out):
            return out
    return ""
