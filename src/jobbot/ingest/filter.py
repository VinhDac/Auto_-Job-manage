"""Lọc tin theo hồ sơ — và LUÔN nói được vì sao bỏ.

Không bao giờ bỏ im lặng. Mỗi tin bị loại đều ghi drop_reason, để sau này
nhìn lại biết bộ lọc quá chặt ở đâu. Bỏ im lặng là cách chắc chắn nhất để
mất tin tốt mà không bao giờ biết.
"""

from __future__ import annotations

from .base import Posting, norm

# Dấu hiệu cấp cao. Chỉ loại khi thấy RÕ RÀNG — "Analyst" trong tài chính
# thường là entry level, không phải cấp cao.
SENIOR_WORDS = {
    "senior", "snr", "sr", "lead", "principal", "staff", "head", "director",
    "chief", "vp", "vice president", "manager", "architect", "expert", "specialist ii",
}
# LỖI ĐÃ SỬA: "analyst" từng nằm ở đây, làm mọi tin "Senior ... Analyst" lọt qua
# vì ngoại lệ luôn kích hoạt. Trong tài chính "Analyst" là chức danh phổ biến ở
# MỌI cấp, nên nó không phải dấu hiệu junior.
JUNIOR_WORDS = {
    "graduate", "grad", "junior", "jr", "intern", "internship", "placement",
    "entry", "trainee", "apprentice", "campus", "early career",
}

UK_WORDS = {"united kingdom", "uk", "london", "england", "britain", "scotland",
            "wales", "manchester", "edinburgh", "cambridge", "oxford", "bristol",
            "leeds", "birmingham", "glasgow", "gb"}
EU_REMOTE_WORDS = {"europe", "emea", "anywhere", "worldwide", "global", "remote"}


def _titles(answers: dict) -> list[str]:
    raw = answers.get("job_titles") or ""
    return [norm(line) for line in raw.splitlines() if line.strip()]


def title_hit(posting: Posting, targets: list[str]) -> str | None:
    """Chức danh tin có chứa chức danh nào mình nhắm không."""
    text = norm(posting.title)
    return next((t for t in targets if t and t in text), None)


def seniority_ok(posting: Posting, accepted: list[str]) -> bool:
    """Nhắm junior mà tin ghi rõ Senior/Lead/Head thì bỏ."""
    wants_junior = bool({"intern", "grad", "grad_scheme", "junior"} & set(accepted))
    if not wants_junior:
        return True
    text = norm(posting.title)
    if any(f" {w} " in f" {text} " for w in SENIOR_WORDS):
        # Trừ khi tin ghi CẢ hai — "Graduate to Senior Analyst" thì vẫn nhận.
        return any(f" {w} " in f" {text} " for w in JUNIOR_WORDS)
    return True


def location_ok(posting: Posting, markets: list[str]) -> bool:
    text = norm(f"{posting.location} {posting.company}")
    if any(w in text for w in UK_WORDS):
        return True
    if posting.remote and any(w in text for w in EU_REMOTE_WORDS):
        return True
    return False


def judge(posting: Posting, answers: dict) -> tuple[bool, str]:
    """Trả về (giữ, lý do). Lý do luôn có, kể cả khi giữ."""
    targets = _titles(answers)
    if not targets:
        return True, "no job_titles set — keeping everything"

    hit = title_hit(posting, targets)
    if not hit:
        return False, "title does not match any target title"
    if not seniority_ok(posting, answers.get("seniority") or []):
        return False, "title is senior level — you target graduate/junior"
    if not location_ok(posting, answers.get("markets") or []):
        return False, f"location '{posting.location or 'unknown'}' outside your markets"
    return True, f"matched target title '{hit}'"
