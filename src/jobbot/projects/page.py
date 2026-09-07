"""Dựng trang kết quả một mặt giấy cho MỘT tin cụ thể.

Khuôn 5 phần (docs/strategy.md §5), đọc hết trong 90 giây:

    Vấn đề    một câu, bằng ngôn ngữ của JD
    Cách làm  cơ chế thật, không buzzword
    Số đo     trước -> sau, KÈM CÁCH ĐO
    Đánh đổi  cái đã hy sinh, và chỗ làm sai
    Link code

Vòng lặp khép ở đây: những câu `cv/rules.py` CẮT khỏi CV — tự phê bình, kể
thất bại — chính là nguyên liệu cho phần "Đánh đổi". Không mất gì, chỉ đổi tầng:

    CV            -> qua vòng lọc      (bỏ chỗ làm sai)
    Trang này     -> được gọi phỏng vấn (chỗ làm sai là điểm mạnh nhất)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..cv import rules
from ..cv.blocks import parse, sentences
from ..cv.build import skills_in

# Câu mang SỐ ĐO: có số VÀ có từ chỉ phép đo
MEASURED = re.compile(
    r"\b(sharpe|drawdown|ratio|%|percent|basis points?|bps|"
    r"from .{1,30} to |went from|deeper|faster|slower|reduced|improved|"
    r"instruments?|years? of data|samples?|rows?|models?)\b", re.I)

# Câu ĐẶT VẤN ĐỀ: nêu một cái sai hoặc một câu hỏi chưa trả lời
PROBLEM = re.compile(
    r"\b(only measures|means nothing|can be faked|leaks?\b|because|"
    r"rewards luck|inflates|is still|are correlated|"
    r"teaches you|not how|wrong (?:everywhere|answer))\b", re.I)


@dataclass
class Page:
    for_job: str
    project: str
    problem: list[str] = field(default_factory=list)
    method: list[str] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)
    tradeoff: list[str] = field(default_factory=list)
    code: list[str] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)
    wanted: list[str] = field(default_factory=list)
    speaks_to: list[str] = field(default_factory=list)


def _slot(text: str) -> str:
    """Câu này thuộc phần nào của trang."""
    if rules.SELF_CRITIQUE.search(text):
        return "tradeoff"                      # chỗ bị CV cắt -> về đây
    if rules.HAS_NUMBER.search(text) and MEASURED.search(text):
        return "numbers"
    if PROBLEM.search(text):
        return "problem"
    if rules.ACTION_VERB.match(text.strip()):
        return "method"
    return "unused"


def build(profile: dict, job_title: str, company: str, wanted: set[str],
          project_title: str = "") -> Page:
    blocks = parse(profile.get("cv_text") or "")

    # chọn khối nói nhiều nhất về thứ tin này đòi
    candidates = [b for b in blocks if b.kind in ("experience", "project")]
    if project_title:
        candidates.sort(key=lambda b: (b.title != project_title,
                                       -len(set(b.tags) & wanted)))
    else:
        candidates.sort(key=lambda b: -len(set(b.tags) & wanted))
    if not candidates:
        return Page(f"{company} — {job_title}", "", wanted=sorted(wanted))

    lead = candidates[0]
    page = Page(f"{company} — {job_title}", lead.title or "Untitled",
                wanted=sorted(wanted))

    pool = []
    for block in candidates[:2]:               # khối chính + khối bổ trợ
        pool += [rules.clean(s) for s in sentences(block)]

    seen = set()
    for text in pool:
        key = text.lower()[:60]
        if key in seen or len(text) < 25:
            continue
        seen.add(key)
        getattr(page, _slot(text)).append(text)

    # github.io / trang cá nhân cũng là nơi đọc được code, không chỉ github.com
    links = re.findall(
        r"(?:https?://)?(?:[\w-]+\.)?(?:github\.(?:com|io)|gitlab\.com)[\w./-]*",
        profile.get("links", "") + " " + (profile.get("cv_text") or ""))
    page.code = sorted(dict.fromkeys(links))[:3]

    covered = set()
    for text in page.problem + page.method + page.numbers + page.tradeoff:
        covered |= skills_in(text)
    page.speaks_to = sorted(covered & wanted)
    return page


def health(page: Page) -> list[tuple[str, str]]:
    """Trang này còn thiếu gì. Nói thẳng, đừng để người đọc tự phát hiện."""
    out = []
    if not page.numbers:
        out.append(("No measurement",
                    "A write-up without a number is an opinion. Even one before/after "
                    "figure, with the method of measuring, changes how this reads."))
    elif not any(re.search(r"measur|method|across|over \d", n, re.I) for n in page.numbers):
        out.append(("Numbers without a method",
                    "State how each number was measured — without it the number "
                    "means nothing to an experienced reader."))
    if not page.tradeoff:
        out.append(("Nothing given up",
                    "A project with no scars reads as one that never ran for real. "
                    "What did you decide not to solve?"))
    if not page.code:
        out.append(("No code link", "The last 5% of readers will want to open it."))
    if not page.speaks_to:
        out.append(("Does not answer this posting",
                    "None of the skills this posting asks for appear in these lines."))
    return out
