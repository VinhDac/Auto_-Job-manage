"""Nhận diện thư tuyển dụng và đoán ý — bằng từ khoá, không cần LLM.

Từ khoá lo được phần lớn. LLM chỉ cần cho mấy ca mập mờ, và đó là bước sau.

THỨ TỰ KIỂM TRA RẤT QUAN TRỌNG: thư từ chối gần như luôn mở đầu bằng
"thank you for applying", nên nếu kiểm 'ack' trước thì mọi thư từ chối
đều bị xếp nhầm thành xác nhận.
"""

from __future__ import annotations

import re

# Các hệ ATS gửi thư thay công ty. Thấy tên miền này là gần như chắc thư tuyển dụng.
ATS_DOMAINS = {
    "greenhouse.io", "lever.co", "hire.lever.co", "ashbyhq.com", "workday.com",
    "myworkday.com", "myworkdayjobs.com", "smartrecruiters.com", "workable.com",
    "teamtailor.com", "breezy.hr", "recruitee.com", "jobvite.com", "icims.com",
    "taleo.net", "successfactors.com", "eightfold.ai", "applytojob.com",
    "bamboohr.com", "pinpointhq.com", "personio.de", "ripplematch.com",
    "hirevue.com", "codility.com", "hackerrank.com", "brightnetwork.co.uk",
}

# Xếp theo THỨ TỰ ƯU TIÊN. Trúng cái nào trước thì dừng.
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("rejection", (
        "unfortunately", "we regret", "regret to inform", "not be progressing",
        "not to proceed", "will not be moving forward", "unsuccessful",
        "decided not to", "other candidates", "not been selected",
        "no longer under consideration", "not shortlisted",
    )),
    ("offer", (
        "pleased to offer", "delighted to offer", "offer of employment",
        "job offer", "formal offer",
    )),
    ("interview", (
        "invite you to an interview", "interview", "schedule a call",
        "your availability", "book a time", "next stage", "speak with you",
        "meet the team", "final round", "superday",
    )),
    ("assessment", (
        "online assessment", "coding challenge", "technical test", "take-home",
        "hackerrank", "codility", "hirevue", "video interview", "aptitude test",
        "numerical reasoning", "situational judgement",
    )),
    ("ack", (
        "received your application", "thank you for applying",
        "application received", "we have received", "thanks for applying",
        "application confirmation", "successfully submitted",
    )),
]

# Loại thư cần Vin làm gì đó ngay
NEEDS_YOU = {"interview", "assessment", "offer"}

_SUBJECT_COMPANY = [
    re.compile(r"application (?:to|for|at)\s+([A-Z][\w&.\- ]{2,40})", re.I),
    re.compile(r"your application[^|\-–]*[|\-–]\s*([A-Z][\w&.\- ]{2,40})"),
    re.compile(r"^([A-Z][\w&.\- ]{2,40})\s*[|\-–]", re.M),
]


def is_job_mail(from_addr: str, subject: str, body: str) -> bool:
    domain = from_addr.rsplit("@", 1)[-1].lower()
    if any(domain == d or domain.endswith("." + d) for d in ATS_DOMAINS):
        return True
    text = f"{subject} {body[:1500]}".lower()
    return any(w in text for w in (
        "your application", "thank you for applying", "job application",
        "recruitment", "hiring team", "talent acquisition", "candidate",
    ))


def classify(subject: str, body: str) -> str:
    text = f"{subject}\n{body[:4000]}".lower()
    for kind, words in RULES:
        if any(w in text for w in words):
            return kind
    return "other"


def guess_company(from_name: str, from_addr: str, subject: str) -> str:
    for pattern in _SUBJECT_COMPANY:
        found = pattern.search(subject or "")
        if found:
            return found.group(1).strip(" -–|")
    # Tên hiển thị kiểu "Man Group Careers" -> "Man Group"
    name = re.sub(r"\b(careers?|recruit(ing|ment)?|talent|hr|team|no.?reply)\b", "",
                  from_name or "", flags=re.I).strip(" -–|")
    if name:
        return name
    domain = (from_addr or "").rsplit("@", 1)[-1].lower()
    if domain and not any(domain.endswith(d) for d in ATS_DOMAINS):
        return domain.split(".")[0].title()
    return ""
