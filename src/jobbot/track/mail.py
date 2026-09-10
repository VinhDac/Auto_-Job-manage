"""Đọc hộp thư việc làm qua IMAP — CHỈ ĐỌC, và ràng buộc nằm trong code.

Vì sao hộp thư RIÊNG chứ không phải hộp chính: app password của Google là chìa
khoá TOÀN QUYỀN — đọc, gửi, xoá, cả hộp thư, vĩnh viễn tới khi thu hồi. Google
không cho tạo loại chỉ-đọc, cũng không giới hạn được theo ngày. Chìa đó nằm
dạng chữ trong config.toml. Đặt nó lên hộp thư chính là đặt sai chỗ; đặt lên
một hộp chỉ chứa thư từ chối việc làm thì mất cũng chẳng sao.

BỐN RÀNG BUỘC, viết thành code chứ không thành lời hứa:

    1. chỉ SELECT chế độ readonly=True — thư không bị đánh dấu đã đọc
    2. KHÔNG có hàm nào gửi, xoá, hay đổi cờ. Không tồn tại thì không gọi nhầm.
    3. chỉ lấy thư trong SINCE_DAYS ngày gần nhất
    4. chỉ lấy TIÊU ĐỀ và mấy dòng đầu — không tải toàn văn, không tải đính kèm

Xem tests/test_track.py: mỗi ràng buộc một bài test.
"""

from __future__ import annotations

import email
import imaplib
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from email.header import decode_header

HOST = "imap.gmail.com"
PORT = 993
SINCE_DAYS = 30
MAX_MESSAGES = 400          # trần cứng, để một hộp thư to không treo vòng quét
SNIPPET = 400               # ký tự lấy từ thân thư


class MailError(RuntimeError):
    pass


def account(conn: sqlite3.Connection | None = None) -> tuple[str, str]:
    """(địa chỉ, app password) từ config.toml. Chưa điền thì trả rỗng."""
    from ..core.config import section
    cfg = section("mail")          # KHÔNG đặt tên `box` — `box` là hộp thư IMAP
    return (str(cfg.get("address") or "").strip(),
            str(cfg.get("password") or "").strip())


def _text(raw) -> str:
    out = []
    for part, enc in decode_header(raw or ""):
        out.append(part.decode(enc or "utf-8", "replace")
                   if isinstance(part, bytes) else part)
    return " ".join(out).strip()


def _body(msg) -> str:
    """Mấy dòng đầu của phần chữ. KHÔNG đụng đính kèm."""
    for part in (msg.walk() if msg.is_multipart() else [msg]):
        if part.get_content_type() != "text/plain":
            continue
        if part.get_filename():          # là đính kèm, bỏ qua
            continue
        try:
            body = part.get_payload(decode=True) or b""
        except Exception:                # noqa: BLE001
            continue
        text = body.decode(part.get_content_charset() or "utf-8", "replace")
        return re.sub(r"\s+", " ", text).strip()[:SNIPPET]
    return ""


def fetch(address: str, password: str, since_days: int = SINCE_DAYS,
          limit: int = MAX_MESSAGES) -> list[dict]:
    """Thư trong `since_days` ngày gần nhất. Không đổi gì trên máy chủ."""
    if not address or not password:
        raise MailError("chưa điền [mail] address/password trong config.toml")

    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%d-%b-%Y")
    box = imaplib.IMAP4_SSL(HOST, PORT)
    try:
        box.login(address, password)
        # readonly=True: máy chủ KHÔNG đánh dấu thư đã đọc.
        box.select("INBOX", readonly=True)
        ok, data = box.search(None, f'(SINCE "{since}")')
        if ok != "OK":
            raise MailError(f"tìm thư hỏng: {ok}")
        ids = (data[0] or b"").split()[-limit:]

        out = []
        for num in ids:
            # BODY.PEEK: lấy mà KHÔNG đặt cờ \Seen. BODY[] thường thì có.
            ok, chunk = box.fetch(num, "(BODY.PEEK[])")
            if ok != "OK" or not chunk or not isinstance(chunk[0], tuple):
                continue
            msg = email.message_from_bytes(chunk[0][1])
            addr = email.utils.parseaddr(msg.get("From", ""))
            when = email.utils.parsedate_to_datetime(msg.get("Date", "")) \
                if msg.get("Date") else None
            out.append({
                "msg_id": msg.get("Message-ID") or f"no-id-{num.decode()}",
                "from_addr": addr[1], "from_name": _text(addr[0]),
                "subject": _text(msg.get("Subject")),
                "received_at": when.isoformat(timespec="seconds") if when else "",
                "snippet": _body(msg),
            })
        return out
    finally:
        try:
            box.logout()
        except Exception:                # noqa: BLE001
            pass
