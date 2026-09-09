"""Xếp hạng nhiều đề bài ĐÃ QUA CỔNG — vì ý đầu tiên hiếm khi là ý tốt nhất.

Bốn chiều. Mỗi chiều phải TRẢ LỜI ĐƯỢC NHIỀU MỨC, không phải đúng/sai:

    phủ         chạm được bao nhiêu phần CẦU của nhóm — cân theo số tin đòi,
                không phải đếm đầu kỹ năng
    cụ thể      các bước nêu cơ chế thật hay chỉ "phân tích dữ liệu"
    gọn         càng ít ngày càng tốt — nhỏ là ưu điểm, không phải hạ tiêu chuẩn
    trong tầm   một mình · hai ngày · máy cá nhân — làm được thật, hay nghe oai

MỘT LUẬT CHỈ ĐỨNG Ở MỘT CHỖ: hoặc là cổng (loại), hoặc là thước (xếp hạng).
Ba chiều cũ đã bỏ khỏi đây vì chúng vốn là cổng, và đứng cả hai nơi thì điểm
số nói dối về việc nó phân loại được cái gì:

    dữ liệu sẵn  12 điểm CHẾT HẲN — pipeline.run đã loại thẳng đề bài có lỗi
                 dữ liệu từ trước khi nhìn tới điểm
    mới           nửa "trùng thứ đã làm" trùng với luật trong brief.validate;
                  nửa "bài mẫu Kaggle" giờ là cổng, cũng ở brief.py
    bác bỏ được   nhị phân 1/0, và chính lời chú của nó là lời của một cái cổng

Đo ngày 09/09 trên bốn đề bài thật của nhóm 'machine learning': cả bốn đều
được 1.0 ở năm trong bảy chiều. Khai 100 điểm, thực chạy 28.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..cv.build import skills_in
from ..ingest.base import norm

# Bước nói cơ chế, không nói chung chung
VAGUE_STEP = re.compile(
    r"^(analyse|analyze|explore|investigate|look at|study|review|examine|"
    r"understand|clean|prepare|visualise|visualize)\b.{0,40}$", re.I)

# QUÁ TẦM — chữ mô tả một HỆ THỐNG SẢN XUẤT, không phải một câu hỏi nghiên cứu.
#
# Vì sao không tin brief.days: con số ngày do chính LLM khai, mà nó khai "2
# ngày" cho cả đề bài "dựng nền tảng streaming real-time". Chữ thì nó không
# giấu được — muốn tả việc to là phải dùng từ của việc to.
#
# Đây là chỗ mã hoá vế thứ hai của câu hỏi gốc: có gặp được cung/cầu thị trường
# KHÔNG QUÁ KHẢ NĂNG. Vế đầu là `coverage`, vế này là đây.
OUT_OF_REACH = re.compile(
    r"\b(in production|production[- ](?:system|grade|ready|pipeline)|at scale|"
    r"real[- ]time (?:system|pipeline|platform|infrastructure)|"
    r"low[- ]latency|sub[- ]millisecond|distributed system|microservice|"
    r"kubernetes|docker swarm|deploy(?:ed|ing)? to (?:prod|aws|gcp|azure)|"
    r"streaming (?:pipeline|platform|architecture)|end[- ]to[- ]end platform|"
    r"petabytes?|terabytes?|gpu cluster|compute cluster|orchestration|"
    r"24/7|live trading|colocat\w+)\b", re.I)


@dataclass
class Score:
    total: float = 0.0
    parts: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# Cộng lại đúng 100. `phủ` nặng nhất vì nó là chính câu hỏi gốc của cả app:
# đề bài này chạm được bao nhiêu phần cầu của thị trường.
WEIGHTS = {"coverage": 40, "concrete": 30, "lean": 15, "in_reach": 15}


def score(brief, wanted_skills: list[str], demand: dict | None = None) -> Score:
    """Chấm một đề bài đã qua cổng. `demand` = {kỹ năng: số tin đòi}."""
    parts: dict[str, float] = {}
    notes: list[str] = []

    want = {norm(s) for s in wanted_skills}
    hit = {norm(s) for s in brief.skills} & want
    if demand:
        # CÂN THEO CẦU. Đếm đầu kỹ năng thì bão hoà ngay: LLM được dặn "chạm ít
        # nhất 2 kỹ năng" nên nó luôn kê 3-4 cái, và mọi đề bài đều 1.0. Cân
        # theo số tin đòi thì chạm `machine learning` (55 tin) khác hẳn chạm
        # `nlp` (15 tin) — đúng câu hỏi cung/cầu mà cả app đang hỏi.
        weight = {norm(k): v for k, v in demand.items()}
        # Mốc chuẩn: ba kỹ năng đòi nhiều nhất trong nhóm. Không lấy TỔNG cả
        # nhóm làm mốc — một đề bài hai ngày không thể chạm mười kỹ năng, lấy
        # tổng thì mọi đề bài đều tí hon và chiều này lại hết phân loại.
        base = sum(sorted(weight.values(), reverse=True)[:3]) or 1
        parts["coverage"] = min(1.0, sum(weight.get(s, 0) for s in hit) / base)
        # Ghi chú CHỈ khi phủ thật sự mỏng, và nói ra chỗ NÊN nhắm thay vì
        # chỗ đang sai. Bản đầu liệt kê từng kỹ năng ít tin đòi, nên nó viết
        # "chạm toàn kỹ năng ít tin đòi" lên một đề bài đang chạm cả
        # `machine learning` (55 tin) — ghi chú sai còn tệ hơn không có.
        if parts["coverage"] < 0.5:
            top = sorted(weight.items(), key=lambda kv: -kv[1])[:2]
            notes.append("phủ mỏng — nhóm này đòi nhiều nhất: "
                         + ", ".join(f"{k} ({n} tin)" for k, n in top))
    else:
        parts["coverage"] = min(1.0, len(hit) / 3)
    if len(hit) < 2:
        notes.append(f"mới chạm {len(hit)} kỹ năng nhóm cần")

    steps = [s for s in brief.method if s.strip()]
    vague = sum(1 for s in steps if VAGUE_STEP.match(s.strip()))
    named = sum(1 for s in steps if skills_in(s) or re.search(r"\d", s))
    parts["concrete"] = max(0.0, (named - vague) / max(len(steps), 1))
    if vague:
        notes.append(f"{vague} bước nói chung chung, không nêu cơ chế")

    parts["lean"] = 1.0 if brief.days <= 1 else 0.7 if brief.days <= 2 else 0.35

    # Quét CẢ đề bài, không riêng câu hỏi: chữ "production" hay nấp trong các
    # bước làm và trong phần sản phẩm giao ra.
    whole = " ".join([brief.question or "", brief.dataset or "",
                      getattr(brief, "deliverable", "") or ""] + list(brief.method))
    big = OUT_OF_REACH.findall(whole)
    parts["in_reach"] = 1.0 if not big else (0.4 if len(set(big)) == 1 else 0.0)
    if big:
        # Cắt theo SỐ MỤC, không cắt theo ký tự: cắt ký tự thì "orchestration"
        # cụt thành "or" và dòng ghi chú đọc ra vô nghĩa.
        words = sorted({b.lower() for b in big})
        notes.append(f"quá tầm làm một mình trong {brief.days} ngày: "
                     + ", ".join(words[:3])
                     + (f" (+{len(words) - 3})" if len(words) > 3 else ""))

    total = sum(WEIGHTS[k] * v for k, v in parts.items())
    return Score(round(total, 1), {k: round(v, 2) for k, v in parts.items()}, notes)


def rank(candidates: list[tuple]) -> list[tuple]:
    """candidates = [(brief, problems, data_problems, score)] -> xếp giảm dần.

    Đề bài còn lỗi luôn xếp sau, dù điểm cao — CẢ lỗi cứng LẪN lỗi dữ liệu.

    Trước đây chỉ xét lỗi cứng, nên một đề bài có lỗi dữ liệu vẫn leo lên đầu
    nếu điểm nó đủ cao; pipeline.run thấy đề bài đầu bảng có lỗi liền trả về
    "cả 4 đều trượt" — trong khi ngay dưới nó có một đề bài sạch. 12 điểm trừ
    của chiều `data_ready` cũ vừa đủ che chuyện đó, không đủ để chặn nó.
    """
    return sorted(candidates,
                  key=lambda c: (not (c[1] or c[2]), c[3].total), reverse=True)
