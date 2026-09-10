"""Thư này nói gì — và nó thuộc lần nộp nào.

Hộp thư RIÊNG cho việc làm nên bài toán nhẹ hẳn: gần như mọi thư đều là thư
tuyển dụng, nên đây là XẾP LOẠI, không phải LỌC. Hộp chính thì phải đoán giữa
hoá đơn, bạn bè, quảng cáo.

Thư ĐỀ XUẤT đổi trạng thái, KHÔNG tự đổi. Một thư "unfortunately" có thể là
từ chối, mà cũng có thể là câu mở đầu của một thư mời phỏng vấn đổi lịch.
Đoán sai mà tự ghi thì bảng thành sai, và Vin không có cách nào biết.
"""

from __future__ import annotations

import re

from ..ingest.base import norm
from .board import INTERVIEW, OFFER, REJECTED, SENT

# Thứ tự QUAN TRỌNG: xét từ kết cục mạnh nhất xuống. Một thư mời phỏng vấn
# thường vẫn mở đầu bằng "thank you for applying" — bắt "confirm" trước là
# xếp nhầm thư quan trọng nhất thành thư xác nhận.
RULES = [
    (OFFER, re.compile(
        r"\b(offer of employment|pleased to offer|we would like to offer|"
        r"offer letter|congratulations[^.]{0,40}offer)\b", re.I)),
    (INTERVIEW, re.compile(
        r"\b(invite you to|would like to invite|schedule (?:a |an )?"
        r"(?:call|interview|chat)|book a time|next (?:round|stage)|"
        r"first[- ]round|online assessment|coding (?:test|challenge)|"
        r"hackerrank|codility|karat)\b", re.I)),
    (REJECTED, re.compile(
        r"\b(not (?:be )?(?:moving|progressing) forward|unsuccessful|"
        r"will not be progressing|decided not to proceed|"
        r"not (?:to )?take your application further|"
        r"other candidates|unable to offer you|regret to inform)\b", re.I)),
    (SENT, re.compile(
        r"\b(thank you for (?:applying|your application)|"
        r"we(?:'ve| have) received your application|application received|"
        r"your application (?:to|for|has been received))\b", re.I)),
]

# Nơi gửi thư tuyển dụng, để đoán công ty khi tiêu đề không nói.
ATS_HOST = re.compile(
    r"(greenhouse|lever|ashbyhq|workday|myworkday|smartrecruiters|icims|"
    r"successfactors|teamtailor|pinpointhq|jobvite|bamboohr|ripplematch)",
    re.I)

# Chữ thừa trong tiêu đề, bỏ đi thì còn lại tên công ty / vai trò.
NOISE = re.compile(
    r"\b(re|fwd|your application|application (?:for|to|update|status)|"
    r"thank you for applying|update on your application)\b[:\s-]*", re.I)


def kind(msg: dict) -> str:
    """-> 'offer' | 'interview' | 'rejected' | 'applied' | 'other'."""
    blob = f"{msg.get('subject', '')} {msg.get('snippet', '')}"
    for name, pattern in RULES:
        if pattern.search(blob):
            return name
    return "other"


# Đuôi thừa trong tên người gửi: "Jump Trading Recruiting" -> "Jump Trading".
ROLE_TAIL = re.compile(
    r"\s*\b(recruit(ing|ment)?|talent( acquisition)?|careers?|hr|people|"
    r"hiring|no[- ]?reply|team|notifications?)\b\s*$", re.I)

ROLE_HEAD = re.compile(
    r"^(careers?|recruit(ing|ment)?|talent|no[- ]?reply|hr|hiring|jobs?)"
    r"\s*(at|@|-|\|)?\s*", re.I)


def _clean_name(text: str) -> str:
    out = ROLE_HEAD.sub("", text or "").strip(" .,|-")
    for _ in range(3):                       # "X Talent Acquisition Team"
        cut = ROLE_TAIL.sub("", out).strip(" .,|-")
        if cut == out:
            break
        out = cut
    return out


def company_of(msg: dict) -> str:
    """Đoán công ty. Tên người gửi trước, rồi tên miền, cuối cùng mới tiêu đề.

    Tiêu đề để CUỐI vì nó hay là câu chứ không phải tên: "Invitation to
    interview - Qube Research" thì tên nằm sau dấu gạch, còn "Your application
    to Jump Trading" thì nằm sau chữ "to".
    """
    name = _clean_name(msg.get("from_name") or "")
    if name and not ATS_HOST.search(name):
        return name[:60]

    host = (msg.get("from_addr") or "").split("@")[-1]
    if host and not ATS_HOST.search(host):
        return host.split(".")[0].replace("-", " ").title()[:60]

    head = NOISE.sub("", msg.get("subject") or "").strip(" -–—|:")
    after = re.search(r"\b(?:to|at|with|from)\s+([A-Z][\w&.\- ]{2,40})", head)
    if after:
        return _clean_name(after.group(1))[:60]
    if re.search(r"\s[-–—|]\s", head):      # "… - Qube Research"
        return _clean_name(re.split(r"\s[-–—|]\s", head)[-1])[:60]
    return _clean_name(head)[:60]


def match(conn, msg: dict) -> int | None:
    """Lần nộp nào ứng với thư này. Khớp theo TÊN CÔNG TY đã chuẩn hoá.

    So CẢ bản bỏ khoảng trắng: tên miền không có dấu phân cách nên đoán ra
    "Mangroup" trong khi bảng ghi "Man Group". Đoán vốn có sai số; chỗ khớp
    phải chịu được, chứ không bắt chỗ đoán phải hoàn hảo.

    Không khớp được thì trả None, và thư nằm lại ở dải "cần Vin" — chỉ chỗ,
    không đoán bừa rồi ghi vào nhầm dòng.
    """
    guess = norm(company_of(msg))
    if not guess:
        return None
    tight = guess.replace(" ", "")
    for row in conn.execute("SELECT id, company_key FROM application"):
        key = (row["company_key"] or "").strip()
        if not key:
            continue
        flat = key.replace(" ", "")
        if key in guess or guess in key or flat in tight or tight in flat:
            return int(row["id"])
    return None
