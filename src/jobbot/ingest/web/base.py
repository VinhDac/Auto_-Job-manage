"""Nền chung cho nguồn qua Chrome.

Hai luật:

1. **Hộp cookie: LUÔN từ chối, KHÔNG BAO GIỜ chấp nhận.** Chỉ bấm nút
   reject/decline/only-necessary. Không bấm "Accept all" trong bất kỳ trường
   hợp nào — hệ thống không có quyền đồng ý điều khoản thay người dùng.

2. **Không cố vượt tường chặn.** Trang nào trả về thử thách chống bot thì ghi
   nhận và bỏ qua. Trang đó đang nói không với máy — không cãi lại.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from ...browser.cdp import CDPError, Tab

# Chỉ nút TỪ CHỐI. Danh sách này cố tình không có từ nào mang nghĩa đồng ý.
#
# LỖI ĐÃ SỬA: trước đây danh sách nằm thẳng trong một regex literal xuống dòng
# giữa chừng, rồi cả khối bị .replace("\n", " "). Nhánh bị cắt qua dòng thành
# " strictly necessary" — dính một khoảng trắng ở đầu, mà nhãn nút thì đã
# .trim(), nên nhánh đó không bao giờ khớp. Tách ra thành DANH SÁCH thì xuống
# dòng kiểu gì cũng không hỏng được nữa.
REJECT_LABELS = [
    "reject all", "reject", "decline all", "decline", "refuse",
    "only necessary", "strictly necessary", "essential only",
    "necessary only", "continue without accepting",
]

REJECT_JS = ("""
(() => {
  const want = new RegExp('^(' + %s + ')$', 'i');
  for (const e of document.querySelectorAll('button,a[role=button],[role=button]')) {
    const t = (e.innerText || '').trim();
    if (want.test(t) && e.offsetParent !== null) { e.click(); return t; }
  }
  return "";
})()
""" % json.dumps("|".join(REJECT_LABELS))).replace("\n", " ")

BLOCKED = re.compile(
    r"just a moment|attention required|access denied|verify you are human|"
    r"unusual traffic|are you a robot|captcha|403 (page|forbidden)|"
    r"enable javascript and cookies", re.I)


@dataclass
class Health:
    """Sức khoẻ một lần đọc nguồn.

    Có nó thì nguồn hỏng TRÔNG KHÁC nguồn chạy tốt. Không có thì
    `except Exception: continue` biến hỏng 100% thành im lặng hoàn toàn.
    """
    attempted: int = 0
    failed: int = 0
    # Bị chặn là một trạng thái RIÊNG, không phải "hỏng vài tin". Trước đây
    # linkedin.fetch gặp Blocked giữa vòng đọc kỹ thì chỉ note() rồi break, nên
    # failed vẫn là 0, record_run thấy 0/193 hỏng và ghi ok=1 — màn hình
    # Settings hiện huy hiệu xanh cho một lần quét bị cắt ngang từ tin thứ ba.
    blocked: bool = False
    # ĐỨT khác BỊ CHẶN. Bị chặn là cổng từ chối mình; đứt là mất kết nối giữa
    # chừng — máy ngủ dậy, Chrome chết, mạng rớt. Hai thứ này cần cách xử lý
    # khác nhau (chặn thì đi nhẹ hơn, đứt thì chạy lại là được), nên nhật ký
    # phải gọi đúng tên. Nhưng cả hai đều là "lần đọc này KHÔNG trọn vẹn", nên
    # cả hai cùng làm ok = False.
    cut: str = ""
    samples: list[str] = field(default_factory=list)

    def note(self, message: str) -> None:
        if len(self.samples) < 5:
            self.samples.append(message)

    def block(self, message: str, unread: int = 0) -> None:
        """Bị chặn: ghi cờ, và tính số tin CHƯA đọc được vào phần hỏng."""
        self.blocked = True
        self.failed += max(0, unread)
        self.note(message)

    def broke(self, message: str) -> None:
        """Đứt giữa chừng (không phải bị chặn). Ghi lý do, và đánh dấu KHÔNG lành."""
        self.cut = message
        self.note(message)

    @property
    def ok(self) -> bool:
        return not (self.blocked or self.cut)

    @property
    def summary(self) -> str:
        if not (self.failed or self.blocked or self.cut):
            return ""
        head = "BỊ CHẶN · " if self.blocked else "ĐỨT · " if self.cut else ""
        return (f"{head}{self.failed}/{self.attempted} hỏng · "
                + " · ".join(self.samples[:2]))


class Blocked(RuntimeError):
    """Trang từ chối truy cập tự động. Ghi nhận rồi đi tiếp, không cãi."""


def reject_cookies(tab: Tab) -> str:
    try:
        clicked = tab.eval(REJECT_JS, timeout=10) or ""
    except CDPError:
        return ""
    if clicked:
        time.sleep(1.2)
    return clicked


def check_open(tab: Tab) -> None:
    """Trang có đang chặn không. Chặn thì dừng, không tìm cách lách."""
    title = (tab.eval("document.title") or "")[:120]
    head = (tab.text() or "")[:400]
    if BLOCKED.search(title) or BLOCKED.search(head):
        raise Blocked(f"trang từ chối truy cập tự động ({title.strip()[:50]})")


def open_page(tab: Tab, url: str, wait_for: str = "body", timeout: float = 35.0) -> None:
    tab.go(url, wait_for=wait_for, timeout=timeout)
    reject_cookies(tab)
    check_open(tab)


def grab(tab: Tab, js: str, timeout: float = 25.0) -> list[dict]:
    """Chạy JS trả về JSON. Lỗi thì trả danh sách rỗng, không làm chết cả lần quét."""
    try:
        raw = tab.eval(js, timeout=timeout)
        return json.loads(raw) if raw else []
    except (CDPError, ValueError, TypeError):
        return []
