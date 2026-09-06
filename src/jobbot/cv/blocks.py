"""Tách CV thành các KHỐI rời để chọn và sắp lại theo từng JD.

Luật xuyên suốt thư mục này: **chỉ CHỌN và SẮP XẾP sự thật đã có.
Không thêm một chữ nào không có trong hồ sơ.**

Vì sao phải tách khối: không tách thì chỉ có một cục văn bản, mà một cục thì
hoặc lấy hết hoặc bỏ hết. Tách rồi mới trả lời được câu "JD này cần dòng nào".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..ingest.base import norm
from ..scoring.vocab import ALIASES

SECTION = re.compile(
    r"^(EXPERIENCE|SELECTED PROJECTS|PROJECTS|EDUCATION|TECHNICAL SKILLS|SKILLS|"
    r"CERTIFICATIONS?|PUBLICATIONS?|AWARDS?)\s*$")

# Ngày tháng bị dính vào cuối dòng chức danh khi trích từ PDF
DATE_TAIL = re.compile(
    r"\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}"
    r"(?:\s*[–—-]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*)?"
    r"(?:\d{4}|Present|present|Now))?"
    r"|\d{4}\s*[–—-]\s*(?:\d{4}|Present))\s*$")

CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.\w+|\+\d[\d ]{6,}|github\.io|linkedin|github", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Block:
    kind: str                 # header|summary|experience|project|education|cert|skill
    title: str = ""
    meta: str = ""            # ngày tháng, tổ chức
    lines: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)   # kỹ năng nhận ra trong khối

    def text(self) -> str:
        return " ".join([self.title, self.meta, *self.lines])


def _tags(text: str) -> list[str]:
    low = f" {norm(text)} "
    found = []
    for alias, canonical in ALIASES.items():
        needle = f" {alias.strip()} " if len(alias.strip()) <= 3 else alias.strip()
        if needle in low and canonical not in found:
            found.append(canonical)
    return found


def _split_role(line: str) -> tuple[str, str]:
    """'Research Consultant — WorldQuant Jan 2025 – Sep 2025' -> (chức danh, ngày)."""
    found = DATE_TAIL.search(line)
    if found:
        return line[:found.start()].strip(), found.group(1).strip()
    return line.strip(), ""


def _looks_like_role(line: str) -> bool:
    """Dòng chức danh, KHÔNG phải câu văn có gạch ngang.

    LỖI ĐÃ SỬA: chỉ cần thấy " — " là coi là chức danh, nên câu
    "...peak profit in the most recent window — which rewards luck" bị cắt
    thành một vai trò mới, xé đôi khối kinh nghiệm.
    """
    if DATE_TAIL.search(line):
        return True
    if len(line) > 90 or line.rstrip().endswith((".", ",", ";", ":")):
        return False
    if not (" — " in line or " – " in line):
        return False
    # dòng chức danh không mở đầu bằng chữ thường hay liên từ
    first = line.split()[0] if line.split() else ""
    return first[:1].isupper() and first.lower() not in {
        "the", "a", "an", "and", "but", "so", "then", "every", "one", "no", "it"}


def parse(cv_text: str) -> list[Block]:
    lines = [l.rstrip() for l in (cv_text or "").splitlines()]
    blocks: list[Block] = []
    section = "head"
    current: Block | None = None

    def flush():
        nonlocal current
        if current and (current.lines or current.title):
            current.tags = _tags(current.text())
            blocks.append(current)
        current = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        found = SECTION.match(line)
        if found:
            flush()
            name = found.group(1).lower()
            section = ("experience" if name == "experience"
                       else "project" if "project" in name
                       else "education" if name == "education"
                       else "cert" if name.startswith("certification")
                       else "skill")
            continue

        # --- phần đầu: tên, liên hệ, tóm tắt ---
        if section == "head":
            if not blocks and not current:
                blocks.append(Block("header", line))          # tên
                continue
            if CONTACT.search(line) or "visa" in line.lower():
                blocks.append(Block("header", "", "", [line]))
                continue
            if current is None:
                current = Block("summary")
            current.lines.append(line)
            continue

        # --- kinh nghiệm / project: dòng chức danh mở khối mới ---
        if section in ("experience", "project"):
            if section == "project":
                head = re.split(r"\s+[—–]\s+", line, maxsplit=1)[0]
                starts_new = (len(head) < 60 and head[:1].isupper()
                              and re.search(r"\s+[—–]\s+", line) is not None)
            else:
                starts_new = _looks_like_role(line) and (
                    current is None or len(current.lines) > 0)
            if starts_new:
                flush()
                title, meta = _split_role(line)
                # 'Tên project — mô tả' : phần mô tả là nội dung, không phải chức danh
                if section == "project" and " — " in title:
                    name, rest = title.split(" — ", 1)
                    current = Block("project", name.strip(), meta, [rest.strip()])
                else:
                    current = Block(section, title, meta)
                continue
            if current is None:
                current = Block(section)
            current.lines.append(line)
            continue

        # --- học vấn / chứng chỉ / kỹ năng: mỗi dòng một khối ---
        if line.lower().startswith("certification"):
            flush()
            blocks.append(Block("cert", "", "", [line]))
            continue
        # kỹ năng: mỗi nhóm ('Programming — ...') là một khối riêng
        if section == "skill":
            label = re.match(r"^([A-Z][A-Za-z /]{2,28})\s+[—–-]\s+(.+)$", line)
            if label:
                flush()
                current = Block("skill", label.group(1).strip(), "", [label.group(2).strip()])
            else:
                if current is None:
                    current = Block("skill")
                current.lines.append(line)
            continue

        if section in ("education", "cert"):
            if section == "education" and _looks_like_role(line):
                flush()
                title, meta = _split_role(line)
                current = Block("education", title, meta)
            else:
                if current is None:
                    current = Block(section)
                current.lines.append(line)
            continue

    flush()
    for block in blocks:
        if not block.tags:
            block.tags = _tags(block.text())
    return blocks


def sentences(block: Block) -> list[str]:
    """Bẻ văn xuôi trong khối thành từng câu — đơn vị nhỏ nhất để chọn.

    Không viết lại câu nào. Câu nào lên CV cũng là câu Vin đã viết.
    """
    # PDF ngắt dòng giữa câu ("...institutions combine\nthousands of simple alphas"),
    # nên phải nối hết lại rồi mới bẻ theo dấu câu.
    joined = re.sub(r"\s+", " ", " ".join(block.lines)).strip()
    return [part.strip() for part in SENTENCE.split(joined) if len(part.strip()) > 25]
