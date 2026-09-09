"""Tách yêu cầu ra khỏi văn bản JD.

Cách làm, theo đúng cấu trúc quan sát được trên 24 JD thật:
    1. Cắt JD theo tiêu đề phần
    2. Bỏ hẳn phần KHÔNG phải yêu cầu (phúc lợi, giới thiệu công ty)
    3. Lấy gạch đầu dòng trong phần yêu cầu và phần điểm cộng
    4. Không có tiêu đề nào -> lấy mọi gạch đầu dòng, coi là bắt buộc

Mỗi yêu cầu giữ nguyên văn để còn hiện lên cho người đọc kiểm chứng.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .vocab import MUST_WORDS, NICE_HEADS, NICE_WORDS, REQ_HEADS, STOP_HEADS

BULLET = re.compile(r"^\s*(?:[·•\-–*]|\d+[.)])\s+(.{6,400})$")

# Vòng dự phòng cho JD viết bằng văn xuôi (GSA, Zopa...): câu nào NGHE như
# một yêu cầu thì lấy. Không bịa gì — vẫn là câu nguyên văn trong JD.
PROSE_HINT = re.compile(
    r"\b(you (?:will )?(?:have|need|bring|possess)|if you have|we(?:'re| are) looking for|"
    r"experience (?:in|of|with)|knowledge of|degree in|background in|familiar(?:ity)? with|"
    r"proficien|strong (?:understanding|grasp|skills)|ability to|comfortable with|"
    r"academic credentials|track record)\b", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+")

# Câu về phúc lợi hay lọt vào vòng dự phòng ("you'll have 25 days holiday").
# Chấm điểm dựa trên phúc lợi công ty là vô nghĩa.
BENEFIT_WORDS = re.compile(
    r"\b(holiday|annual leave|days off|pension|insurance|healthcare|wellbeing|"
    r"gym|parental leave|maternity|paternity|salary|bonus scheme|share options|"
    r"equity package|working from abroad|flexible working|hybrid working|"
    r"office|snacks|socials?|perks?|discount)\b", re.I)
MAX_REQS = 18            # JD dài lê thê thì cắt — 18 dòng đầu đã đủ để phán


@dataclass
class Requirement:
    text: str
    must: bool           # bắt buộc hay chỉ là điểm cộng
    source: str = "bullet"   # bullet = tin cậy | prose = đoán từ văn xuôi


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not (3 < len(stripped) < 80):
        return False
    if BULLET.match(line):
        return False
    # tiêu đề thường ngắn, không kết thúc bằng dấu chấm
    return bool(REQ_HEADS.match(stripped) or NICE_HEADS.match(stripped)
                or STOP_HEADS.match(stripped))


def sections(text: str) -> list[tuple[str, list[str]]]:
    """Cắt thành (loại phần, các dòng). Loại: req | nice | stop | body."""
    out: list[tuple[str, list[str]]] = []
    kind, buffer = "body", []
    for line in (text or "").splitlines():
        if _is_heading(line):
            if buffer:
                out.append((kind, buffer))
            stripped = line.strip()
            kind = ("nice" if NICE_HEADS.match(stripped)
                    else "stop" if STOP_HEADS.match(stripped)
                    else "req")
            buffer = []
        else:
            buffer.append(line)
    if buffer:
        out.append((kind, buffer))
    return out


def _bullets(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        found = BULLET.match(line)
        if found:
            item = re.sub(r"\s+", " ", found.group(1)).strip(" .;")
            if len(item) > 6:
                out.append(item)
    return out


MIN_RUN = 3              # dưới 3 dòng liền nhau thì chưa gọi là danh sách


def _runs(lines: list[str]) -> list[str]:
    """Danh sách KHÔNG có dấu gạch đầu dòng — nhận diện bằng chỗ xuống dòng.

    Vì sao cần: LinkedIn trả về JD dưới dạng chữ đã dựng sẵn, <li> mất sạch dấu
    '·'. Bốn mươi sáu tin đang giữ có nguyên một danh sách yêu cầu đọc được mà
    bộ tách trả về rỗng, chỉ vì thiếu một ký tự.

    Dấu hiệu phân biệt: khi HTML được bóc ra chữ, '</p>' thành hai dòng trống
    còn '<li>' chỉ thành một dòng — nên đoạn văn xuôi đứng LẺ giữa hai dòng
    trống, còn mục danh sách đi thành CHUỖI LIỀN. Lấy chuỗi, bỏ đoạn lẻ.
    """
    out: list[str] = []
    run: list[str] = []

    def flush():
        if len(run) >= MIN_RUN:
            out.extend(run)
        run.clear()

    for line in lines:
        item = re.sub(r"\s+", " ", line).strip(" .;")
        if 20 < len(item) < 400 and not BULLET.match(line):
            run.append(item)
        else:
            flush()
    flush()
    return out


def requirements(text: str) -> list[Requirement]:
    parts = sections(text)
    out: list[Requirement] = []

    for kind, lines in parts:
        if kind == "stop":
            continue                       # phúc lợi, giới thiệu — không phải yêu cầu
        if kind == "body":
            continue                       # đoạn văn mở đầu, để vòng dự phòng lo
        for item in _bullets(lines):
            must = kind == "req"
            if NICE_WORDS.search(item):
                must = False
            elif MUST_WORDS.search(item):
                must = True
            out.append(Requirement(item, must))

    if not out:                            # JD không chia phần -> lấy hết gạch đầu dòng
        for kind, lines in parts:
            if kind == "stop":
                continue
            for item in _bullets(lines):
                out.append(Requirement(item, not NICE_WORDS.search(item)))

    if not out:                            # không có dấu gạch nào -> tìm danh sách
        for kind, lines in parts:          #    nhận ra bằng xuống dòng (LinkedIn)
            if kind == "stop":
                continue
            for item in _runs(lines):
                # Danh sách phúc lợi cũng là danh sách. Chấm điểm dựa trên
                # "competitive salary" thì con số ra là vô nghĩa.
                if BENEFIT_WORDS.search(item):
                    continue
                must = kind != "nice" and not NICE_WORDS.search(item)
                out.append(Requirement(item, must, "list"))

    if not out:                            # vẫn không có -> JD viết bằng văn xuôi
        out = _from_prose(parts)

    # bỏ trùng, giữ thứ tự
    seen, unique = set(), []
    for req in out:
        key = req.text.lower()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(req)
    return unique[:MAX_REQS]


def _from_prose(parts: list[tuple[str, list[str]]]) -> list[Requirement]:
    """JD không có gạch đầu dòng: nhặt câu nghe như yêu cầu. Vẫn là câu thật."""
    out: list[Requirement] = []
    for kind, lines in parts:
        if kind == "stop":
            continue
        blob = re.sub(r"\s+", " ", " ".join(lines))
        for sentence in SENTENCE.split(blob):
            sentence = sentence.strip(" .;")
            if not (25 < len(sentence) < 320):
                continue
            if not PROSE_HINT.search(sentence) or BENEFIT_WORDS.search(sentence):
                continue
            out.append(Requirement(sentence, not NICE_WORDS.search(sentence), "prose"))
    return out


def confidence(reqs: list[Requirement]) -> str:
    """Tin được bao nhiêu vào những gì vừa tách ra.

    Không đọc được yêu cầu thì NÓI THẲNG là không chấm được — điểm bịa
    còn tệ hơn không có điểm.
    """
    if not reqs:
        return "none"
    if any(r.source == "prose" for r in reqs):
        return "low"
    if any(r.source == "list" for r in reqs):
        # Đọc được cả danh sách nhưng ranh giới do xuống dòng đoán ra, không do
        # dấu gạch nói thẳng — tin vừa phải, đừng tin như gạch đầu dòng.
        return "medium"
    return "high" if len(reqs) >= 4 else "medium"
