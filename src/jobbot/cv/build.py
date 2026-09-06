"""Dựng CV riêng cho một JD — CHỌN và SẮP XẾP, không viết mới.

Mọi câu trên CV sinh ra đều là câu Vin đã viết trong hồ sơ. Hệ thống chỉ quyết
định câu nào lên, theo thứ tự nào, và bỏ câu nào — kèm lý do bỏ, để kiểm chứng.

Không có LLM ở đây. LLM (bước 2b) sau này chỉ dùng để VIẾT LẠI cho gọn,
không bao giờ để thêm sự thật mới.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..ingest.base import norm
from ..scoring.vocab import ALIASES
from . import rules
from .blocks import Block, parse, sentences


@dataclass
class Line:
    text: str
    weight: float = 0.0
    hits: list[str] = field(default_factory=list)   # kỹ năng JD đòi mà câu này trúng
    review: str = ""                                # giữ nhưng cần Vin xem lại


@dataclass
class Section:
    kind: str
    title: str
    meta: str
    lines: list[Line] = field(default_factory=list)


@dataclass
class TailoredCV:
    header: list[str]
    summary: str
    sections: list[Section]
    dropped: list[tuple[str, str]]      # (câu, lý do bỏ)
    wanted: list[str]                   # kỹ năng JD đòi
    covered: list[str]                  # trong đó CV này nói được
    missing: list[str]                  # JD đòi mà hồ sơ không có


def skills_in(text: str) -> set[str]:
    low = f" {norm(text)} "
    return {c for a, c in ALIASES.items()
            if (f" {a.strip()} " if len(a.strip()) <= 3 else a.strip()) in low}


def wanted_skills(explain: dict | None, jd_text: str = "") -> set[str]:
    """Kỹ năng tin này quan tâm.

    Quét CẢ tin, không chỉ mấy dòng gạch đầu dòng: Jane Street nhắc
    "time series analysis, feature engineering" ở đoạn mở đầu chứ không
    nằm trong phần "About You".
    """
    out: set[str] = set(skills_in(jd_text))
    for req in (explain or {}).get("requirements", []):
        out |= skills_in(req["text"])
    return out


def _pick(block: Block, wanted: set[str], cap: int,
          dropped: list) -> list[Line]:
    kept: list[Line] = []
    for text in sentences(block):
        text = rules.clean(text)
        tags = sorted(skills_in(text))
        verdict, why = rules.sentence_ok(text, tags)
        if verdict == "drop":
            dropped.append((text, why))
            continue
        kept.append(Line(text, rules.sentence_weight(text, wanted, tags),
                         sorted(set(tags) & wanted),
                         why if verdict == "review" else ""))
    kept.sort(key=lambda l: -l.weight)
    return kept[:cap]


def build(profile: dict, explain: dict | None, jd_text: str = "") -> TailoredCV:
    blocks = parse(profile.get("cv_text") or "")
    wanted = wanted_skills(explain, jd_text)
    dropped: list[tuple[str, str]] = []

    header = [profile.get("full_name") or "",
              " · ".join(x for x in [profile.get("location"), profile.get("phone"),
                                     profile.get("email")] if x)]
    links = (profile.get("links") or "").splitlines()
    if links:
        header.append(" · ".join(l.strip() for l in links if l.strip()))
    visa = next((" ".join(b.lines) for b in blocks
                 if b.kind == "header" and "visa" in " ".join(b.lines).lower()), "")
    if visa:
        header.append(visa)

    # --- tóm tắt: ghép từ SỰ THẬT, không viết câu mới ---
    facts = []
    education = (profile.get("education") or "").splitlines()
    if education:
        facts.append(education[0].split("—")[0].strip())
    certs = (profile.get("certifications") or "").splitlines()
    if certs:
        facts.append(certs[0].split("—")[0].strip() if "—" in certs[0] else certs[0])
    # Kỹ năng JD đòi lên trước, rồi bù thêm cho đủ — không để tóm tắt trơ trọi
    strong = [s.strip() for s in (profile.get("skills_strong") or "").split(",") if s.strip()]
    want_norm = {norm(w) for w in wanted}
    hit = [s for s in strong if norm(s) in want_norm]
    rest = [s for s in strong if norm(s) not in want_norm]
    lead = (hit + rest)[:6]
    if lead:
        facts.append(" · ".join(lead))
    summary = " · ".join(f for f in facts if f)

    # --- các phần ---
    sections: list[Section] = []
    for kind, cap in (("experience", rules.BUDGET["experience"]),
                      ("project", rules.BUDGET["project"])):
        chosen = [b for b in blocks if b.kind == kind]
        chosen.sort(key=lambda b: -len(set(b.tags) & wanted))
        for block in chosen[:cap]:
            lines = _pick(block, wanted, rules.BUDGET["exp_bullets"], dropped)
            if lines:
                sections.append(Section(kind, block.title, block.meta, lines))

    for block in [b for b in blocks if b.kind == "education"]:
        sections.append(Section("education", block.title, block.meta,
                                [Line(l) for l in block.lines]))
    for block in [b for b in blocks if b.kind == "cert"]:
        sections.append(Section("cert", "", "", [Line(l) for l in block.lines]))

    skills = [b for b in blocks if b.kind == "skill"
              and b.title.lower() not in rules.DROP_SKILL_GROUPS]
    for block in blocks:
        if block.kind == "skill" and block.title.lower() in rules.DROP_SKILL_GROUPS:
            dropped.append((f"{block.title} section",
                            "teaches the reader basics — reads as junior"))
    skills.sort(key=lambda b: -len(set(b.tags) & wanted))
    for block in skills[:rules.BUDGET["skill"]]:
        sections.append(Section("skill", block.title, "",
                                [Line(" ".join(block.lines))]))

    covered = sorted({h for s in sections for l in s.lines for h in l.hits})
    have: set[str] = set()
    for block in blocks:
        have |= set(block.tags)
    have |= skills_in(profile.get("skills_strong", "") + " "
                      + profile.get("skills_weak", ""))

    return TailoredCV(header, summary, sections, dropped,
                      sorted(wanted), covered, sorted(_real_missing(explain, wanted, have)))


def _real_missing(explain: dict | None, wanted: set[str], have: set[str]) -> set[str]:
    """Kỹ năng THẬT SỰ thiếu — bỏ qua danh sách 'hoặc'.

    JD viết "Programming in any of the following: C++, Java, MATLAB, R, Python"
    mà mình có C++ và Python thì Java/MATLAB/R KHÔNG phải là thiếu. Báo thiếu ở
    đây là báo động giả, và báo động giả thì lần sau không ai đọc nữa.
    """
    missing = wanted - have
    if not explain:
        return missing
    for req in explain.get("requirements", []):
        in_line = skills_in(req["text"])
        if in_line & have:                 # dòng này đã có ít nhất một cái đáp ứng
            missing -= in_line
    return missing
