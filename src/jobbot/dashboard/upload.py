"""Nhận file tải lên — multipart, bằng thư viện chuẩn.

`cgi.FieldStorage` đã bị bỏ khỏi Python 3.13, nên dùng `email.parser`:
multipart/form-data về bản chất là một thông điệp MIME.
"""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import default

MAX_BYTES = 8 * 1024 * 1024        # 8MB — CV nào cũng nhỏ hơn nhiều


class TooBig(RuntimeError):
    pass


def parse(content_type: str, body: bytes) -> dict[str, tuple[str, bytes]]:
    """Trả về {tên ô: (tên file, nội dung)}. Ô chữ thường thì tên file rỗng."""
    if len(body) > MAX_BYTES:
        raise TooBig(f"File quá lớn (giới hạn {MAX_BYTES // 1024 // 1024}MB)")

    head = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
    message = BytesParser(policy=default).parsebytes(head + body)
    out: dict[str, tuple[str, bytes]] = {}
    if not message.is_multipart():
        return out
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        out[str(name)] = (part.get_filename() or "", payload)
    return out
