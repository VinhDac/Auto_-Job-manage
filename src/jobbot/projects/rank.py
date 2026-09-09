"""Chấm và xếp hạng nhiều đề bài — vì ý đầu tiên hiếm khi là ý tốt nhất.

Sáu chiều, mỗi chiều đo được:

    phủ         chạm bao nhiêu thứ nhóm JD đòi
    bác bỏ được  câu hỏi có thể ra kết quả NGƯỢC với mong đợi không.
                 Đề bài chỉ có thể xác nhận thì không phải nghiên cứu, là quảng cáo.
    cụ thể       các bước có nêu cơ chế thật hay chỉ "phân tích dữ liệu"
    dữ liệu sẵn  tải về dùng ngay, hay phải cào và làm sạch trước (ăn hết 2 ngày)
    gọn          càng ít ngày càng tốt — nhỏ là ưu điểm, không phải hạ tiêu chuẩn
    mới          không lặp thứ đã làm, không phải bài mẫu Kaggle ai cũng biết
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..cv.build import skills_in
from ..ingest.base import norm

# Câu hỏi CÓ THỂ SAI — mở ra hai kết cục, không phải chỉ một
FALSIFIABLE = re.compile(
    r"\b(how much|how far|does|do |whether|is it|are they|compared? (?:to|with)|"
    r"versus|vs\b|difference between|instead of|better than|worse than|"
    r"how many|to what extent|what happens (?:if|when))\b", re.I)

# Bước nói cơ chế, không nói chung chung
VAGUE_STEP = re.compile(
    r"^(analyse|analyze|explore|investigate|look at|study|review|examine|"
    r"understand|clean|prepare|visualise|visualize)\b.{0,40}$", re.I)

# Bài mẫu ai cũng làm — làm lại thì không chứng minh được gì
TUTORIAL = re.compile(
    r"\b(titanic|iris dataset|mnist|house prices?|boston housing|"
    r"sentiment analysis of tweets|movie recommend\w*|churn prediction demo|"
    r"hello world|stock price prediction with lstm)\b", re.I)


@dataclass
class Score:
    total: float = 0.0
    parts: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


WEIGHTS = {"coverage": 30, "falsifiable": 20, "concrete": 20,
           "data_ready": 15, "lean": 10, "novel": 5}


def score(brief, wanted_skills: list[str], data_problems: list[str],
          existing: list[str]) -> Score:
    parts: dict[str, float] = {}
    notes: list[str] = []

    want = {norm(s) for s in wanted_skills}
    hit = {norm(s) for s in brief.skills} & want
    parts["coverage"] = min(1.0, len(hit) / 3)
    if len(hit) < 2:
        notes.append(f"mới chạm {len(hit)} kỹ năng nhóm cần")

    ok_question = bool(FALSIFIABLE.search(brief.question or ""))
    parts["falsifiable"] = 1.0 if ok_question else 0.0
    if not ok_question:
        notes.append("câu hỏi không thể ra kết quả ngược — chỉ xác nhận, không kiểm chứng")

    steps = [s for s in brief.method if s.strip()]
    vague = sum(1 for s in steps if VAGUE_STEP.match(s.strip()))
    named = sum(1 for s in steps if skills_in(s) or re.search(r"\d", s))
    parts["concrete"] = max(0.0, (named - vague) / max(len(steps), 1))
    if vague:
        notes.append(f"{vague} bước nói chung chung, không nêu cơ chế")

    parts["data_ready"] = 0.0 if data_problems else 1.0
    if data_problems:
        notes.append(data_problems[0][:70])

    parts["lean"] = 1.0 if brief.days <= 1 else 0.7 if brief.days <= 2 else 0.35

    blob = f"{brief.question} {brief.dataset}"
    tutorial = bool(TUTORIAL.search(blob))
    overlap = any(len(set(norm(brief.question).split()) & set(norm(e).split()))
                  / max(len(set(norm(e).split())), 1) > 0.5 for e in existing)
    parts["novel"] = 0.0 if (tutorial or overlap) else 1.0
    if tutorial:
        notes.append("là bài mẫu phổ biến — làm lại không chứng minh được gì")
    if overlap:
        notes.append("trùng thứ đã làm")

    total = sum(WEIGHTS[k] * v for k, v in parts.items())
    return Score(round(total, 1), {k: round(v, 2) for k, v in parts.items()}, notes)


def rank(candidates: list[tuple]) -> list[tuple]:
    """candidates = [(brief, problems, data_problems, score)] -> xếp giảm dần.

    Đề bài còn lỗi cứng (`problems`) luôn xếp sau, dù điểm cao.
    """
    return sorted(candidates,
                  key=lambda c: (len(c[1]) == 0, c[3].total), reverse=True)
