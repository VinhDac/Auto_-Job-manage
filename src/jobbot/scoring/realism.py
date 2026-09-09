"""Tách "KHỚP" khỏi "CÓ CỬA".

Điểm khớp trả lời: hồ sơ này có đúng thứ JD đòi không.
Nó KHÔNG trả lời: nộp vào có cửa nào không.

Một tin Quantitative Researcher ở Jane Street có thể khớp 84 điểm, nhưng đòi
PhD và 500 người có PhD cùng nộp. Một tin Graduate Analyst khớp 74 điểm lại là
chương trình tuyển người mới ra trường, nhận 40 người.

Hai con số khác nhau, và chỉ dùng một con số là đọc sai bảng xếp hạng.

Không dùng LLM. Toàn bộ là dấu hiệu đọc thẳng từ JD.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

# Dấu hiệu tin TUYỂN NGƯỜI MỚI RA TRƯỜNG — cửa rộng nhất
OPEN_DOOR = re.compile(
    r"\b(graduate (?:programme|program|scheme|role|opportunit)|"
    r"campus (?:hire|recruit)|entry[- ]level|no (?:prior )?experience (?:is )?"
    r"(?:required|necessary)|intern(?:ship)? (?:programme|program)|"
    r"placement year|training (?:programme|program)|"
    r"final[- ]year (?:student|undergraduate)|recent graduate|"
    r"we welcome applications from students)\b", re.I)

# Dấu hiệu CỬA HẸP
PHD_HARD = re.compile(r"\b(phd (?:is )?(?:required|essential)|must have a phd|"
                      r"phd in|doctorate (?:required|in))\b", re.I)
PHD_SOFT = re.compile(r"\bph\.?d\b", re.I)
YEARS = re.compile(r"(\d+)\s*\+?\s*(?:or more\s*)?years?[^.]{0,40}"
                   r"(?:experience|exp\b)", re.I)
SENIOR_TITLE = re.compile(r"\b(senior|snr|lead|principal|staff|head of|vp|"
                          r"vice president|director|manager|architect)\b", re.I)

YEARS_HAVE = {"0-1": 0.5, "1-3": 2, "3-5": 4, "5-8": 6.5, "8+": 10}

# Hạn nộp viết trong JD
DEADLINE = re.compile(
    r"(?:deadline|closing date|applications? close|apply by|closes on|"
    r"last day to apply)\D{0,24}"
    r"(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", re.I)

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def find_deadline(text: str) -> tuple[str, int]:
    """(chữ hạn nộp, unix). Không có thì ('', 0)."""
    found = DEADLINE.search(text or "")
    if not found:
        return "", 0
    raw = found.group(1).strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
                "%Y-%m-%d", "%d/%m/%Y"):
        try:
            when = datetime.strptime(raw.replace(",", ""), fmt).replace(tzinfo=timezone.utc)
            return raw, int(when.timestamp())
        except ValueError:
            continue
    return raw, 0


def assess(title: str, description: str, explain: dict | None,
           answers: dict) -> dict:
    """Phán 'có cửa không', kèm lý do. Không đoán được thì nói không đoán được."""
    text = description or ""
    reasons: list[str] = []
    score = 0                       # âm = cửa hẹp, dương = cửa rộng

    if OPEN_DOOR.search(text) or OPEN_DOOR.search(title):
        score += 2
        reasons.append("explicitly a graduate or entry-level opening")

    if SENIOR_TITLE.search(title):
        score -= 3
        reasons.append("the title itself is a senior role")

    if PHD_HARD.search(text):
        score -= 3
        reasons.append("a PhD is stated as required")
    elif PHD_SOFT.search(text):
        score -= 1
        reasons.append("a PhD is mentioned — you would be competing with PhDs")

    have = YEARS_HAVE.get(str(answers.get("years_real") or ""), 0)
    asked = [int(m.group(1)) for m in YEARS.finditer(text)]
    worst = max(asked) if asked else 0
    if worst >= 5 and have < worst:
        score -= 3
        reasons.append(f"asks for {worst}+ years; you have about {have:g}")
    elif worst >= 3 and have < worst:
        score -= 2
        reasons.append(f"asks for {worst}+ years; you have about {have:g}")
    elif worst and have >= worst:
        score += 1
        reasons.append(f"asks for {worst}+ years and you meet it")

    if explain and explain.get("capped"):
        score -= 1

    if not description or len(description) < 300:
        return {"band": "unknown", "why": "no description to judge from",
                "score": 0}

    band = "likely" if score >= 2 else "unlikely" if score <= -2 else "possible"
    return {"band": band, "why": " · ".join(reasons[:3]) or "nothing decisive either way",
            "score": score}
