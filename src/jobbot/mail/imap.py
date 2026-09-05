"""Đọc Gmail qua IMAP — `imaplib` có sẵn trong Python, không cài gì.

BA RÀNG BUỘC AN TOÀN, cố ý:

1. Mở hộp thư ở chế độ **CHỈ ĐỌC** (readonly=True). Module này KHÔNG THỂ
   xoá, chuyển, hay đánh dấu bất cứ thư nào — kể cả khi có lỗi.
2. Mật khẩu đọc từ **biến môi trường**, không bao giờ nằm trong code hay DB.
3. Chỉ lấy tiêu đề và ~2000 ký tự đầu thân thư. Không tải đính kèm.

Cách lấy App Password cho Gmail:
    myaccount.google.com/apppasswords   (cần bật 2FA trước)
Rồi đặt biến môi trường:
    export JOBBOT_GMAIL_USER="ban@gmail.com"
    export JOBBOT_GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
"""

from __future__ import annotations

import email
import email.utils
import imaplib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

HOST = "imap.gmail.com"
PORT = 993


@dataclass
class Message:
    msg_id: str
    from_name: str
    from_addr: str
    subject: str
    received_at: str
    body: str


class NotConfigured(RuntimeError):
    pass


def credentials() -> tuple[str, str]:
    user = os.environ.get("JOBBOT_GMAIL_USER", "").strip()
    password = os.environ.get("JOBBOT_GMAIL_APP_PASSWORD", "").strip()
    if not user or not password:
        raise NotConfigured(
            "Chưa có JOBBOT_GMAIL_USER / JOBBOT_GMAIL_APP_PASSWORD.\n"
            "  1. Bật 2FA cho Gmail\n"
            "  2. Tạo App Password ở myaccount.google.com/apppasswords\n"
            "  3. export JOBBOT_GMAIL_USER=\"ban@gmail.com\"\n"
            "     export JOBBOT_GMAIL_APP_PASSWORD=\"xxxx xxxx xxxx xxxx\"")
    return user, password


def _decode(raw: str | None) -> str:
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    out = []
    for chunk, enc in parts:
        out.append(chunk.decode(enc or "utf-8", "replace") if isinstance(chunk, bytes) else chunk)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _body(msg: email.message.Message, limit: int = 2000) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", "replace")[:limit]
        for part in msg.walk():                       # không có plain thì lấy html thô
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True) or b""
                html = payload.decode(part.get_content_charset() or "utf-8", "replace")
                return re.sub(r"<[^>]+>", " ", html)[:limit]
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", "replace")[:limit]


def fetch_recent(days: int = 90, limit: int = 400) -> list[Message]:
    """Lấy thư trong N ngày gần đây. Mở CHỈ ĐỌC — không đụng gì vào hộp thư."""
    user, password = credentials()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")

    conn = imaplib.IMAP4_SSL(HOST, PORT)
    try:
        conn.login(user, password)
        conn.select("INBOX", readonly=True)          # <- không thể ghi
        status, data = conn.search(None, f'(SINCE {since})')
        if status != "OK":
            return []
        uids = (data[0] or b"").split()[-limit:]

        out: list[Message] = []
        for uid in uids:
            status, raw = conn.fetch(uid, "(RFC822)")
            if status != "OK" or not raw or not isinstance(raw[0], tuple):
                continue
            msg = email.message_from_bytes(raw[0][1])
            name, addr = email.utils.parseaddr(msg.get("From", ""))
            date = msg.get("Date", "")
            try:
                received = email.utils.parsedate_to_datetime(date).astimezone(
                    timezone.utc).isoformat(timespec="seconds")
            except (TypeError, ValueError):
                received = ""
            out.append(Message(
                msg_id=(msg.get("Message-ID") or f"uid:{uid.decode()}").strip("<> "),
                from_name=_decode(name), from_addr=addr.lower(),
                subject=_decode(msg.get("Subject")),
                received_at=received, body=_body(msg),
            ))
        return out
    finally:
        try:
            conn.logout()
        except Exception:                             # noqa: BLE001
            pass
