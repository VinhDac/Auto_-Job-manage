"""Khuôn dựng project — KHÔNG dùng LLM.

Project không cần MỚI, nó cần là BẰNG CHỨNG. Bằng chứng là cái mẫu điền vào,
không phải ý tưởng nghĩ ra. Nuôi một LLM đủ thông minh để nghĩ ý mới là trả
tiền cho thứ mình không cần — và trả bằng: chờ 8 giây, chép prompt dán câu trả
lời, kẹt cứng sau 4 phương án, rồi vẫn phải tin lời nó khai về kỹ năng.

    JD quyết định NỘI DUNG    (research.study đọc ra: kỹ năng, khái niệm, dữ liệu)
    khuôn quyết định HÌNH DẠNG (ba bước dưới đây, không đổi)

HAI hình dạng, và cả hai đọc ra TỪ CHÍNH JD chứ không phải tôi nghĩ ra. Bóc
phần VIỆC PHẢI LÀM của 176 tin (extract.duties) được 306 dòng; chúng dồn vào
đúng hai việc:

    change  PHÁT HIỆN cái vừa đổi bất thường, kiểm nó thật hay nhiễu, TRUY
            XUẤT về đâu.  "Identify trends, patterns and meaningful insights"
            "Analyse market data and yield curve to identify opportunity"

    signal  DỰNG một tín hiệu dự đoán, kiểm ngoài mẫu, trừ chi phí, xem còn
            lại bao nhiêu.  "Conduct original quantitative alpha signal
            research"  ·  "Design, test, and validate alpha models"
            "Develop and refine quantitative models to predict and trade"

Hình dạng này TỰ NÓ bác bỏ được và TỰ NÓ ra một con số, nên mấy cái cổng trong
brief.validate không còn là chỗ chặn — chúng thành chỗ KIỂM LẠI rằng khuôn
chưa mục.

Đề bài cũng mang theo NỬA DƯỚI: thứ giao nộp. Đo trên 178 tin — 30% đòi cách
làm (test, CI, tài liệu) và 47% đòi số năm / track record. Cả hai không phụ
thuộc project HỎI gì, chúng phụ thuộc project TRÔNG THẾ NÀO lúc giao. Nên thứ
giao nộp cố định: repo · test · chạy lại được · một con số · một trang.
"""

from __future__ import annotations

from pathlib import Path

from .brief import Brief
from .shelf import Source, for_skill

DAYS = 2.0

SCAFFOLD = Path(__file__).parent / "scaffold"

# BƯỚC 1 đổi theo kỹ năng — đây là chỗ chữa lỗi "kỹ năng chỉ là lời khai".
# Khuôn dựng CHO kỹ năng nào thì thân nó làm đúng việc đó, không phải khai rồi
# để đấy: chọn `machine learning` thì bộ phát hiện là một mô hình thật, chọn
# `sql` thì phép tính viết bằng hàm cửa sổ SQL thật.
# HÌNH DẠNG theo ô. Đọc ra từ dòng việc phải làm của chính nhóm tin đó.
SHAPE = {
    "alpha research": "signal", "backtesting": "signal", "portfolio": "signal",
}
DEFAULT_SHAPE = "change"

# BƯỚC 1 đổi theo kỹ năng — chỗ chữa lỗi "kỹ năng chỉ là lời khai". Khuôn dựng
# CHO kỹ năng nào thì thân nó làm đúng việc đó: chọn `machine learning` thì
# bước 1 là một mô hình thật, chọn `sql` thì phép tính viết bằng SQL thật.
STEP_ONE = {
    "change": {"machine learning": "detect_model", "sql": "detect_sql"},
    "signal": {"machine learning": "signal_model"},
}
DEFAULT_STEP_ONE = {"change": "detect_stat", "signal": "signal_momentum"}

# Tên NGẮN của bước 1, để viết câu hỏi. `how` là câu dài mô tả cách làm; nhét
# câu dài vào giữa câu hỏi thì đọc không ra tiếng người.
STEP_SHORT = {
    "detect_stat": "rolling-sigma", "detect_model": "isolation-forest",
    "detect_sql": "SQL-window", "signal_momentum": "12-month momentum",
    "signal_model": "ridge-regression",
}

# Khuôn TỰ chứng minh, ở mọi ô: bước kiểm ngoài mẫu, và nó luôn vẽ hình.
ALWAYS = ["validation", "visualisation"]

# Thứ chính DỮ LIỆU chứng minh, bất kể bước 1 nào: repo nào cũng tải về và làm
# sạch dữ liệu thị trường thật, và dữ liệu nào thì ra ngành đó.
INHERIT = {"equities", "fixed income", "market data", "data pipeline"}

# Ô nào hai hình dạng này chứng minh được. Cố ý liệt kê ra chứ không lấy bừa
# từ shelf.Source.skills — nguồn PHỤC VỤ một kỹ năng không có nghĩa là project
# CHỨNG MINH kỹ năng đó.
#
# Còn ngoài: optimisation · derivatives · nlp. Nói thẳng ra còn hơn khai bừa
# rồi lưới lại tự lừa mình lần nữa.
PROVES = {
    "change": {"validation", "visualisation", "probability", "statistics",
               "machine learning", "sql", "data pipeline", "market data",
               "equities", "fixed income", "risk"},
    "signal": {"alpha research", "backtesting", "portfolio", "validation",
               "visualisation", "machine learning", "equities", "fixed income",
               "market data"},
}

WORDING = {
    "change": dict(
        ask=("How much of the largest abnormal change in {watch} since {since} "
             "is explained by a single {unit}?"),
        measure=("the share of the largest abnormal change explained by one "
                 "{unit}, measured with the detector refit on data before each "
                 "day it scores"),
        steps=[
            "Download {name} with the script in the repo and drop rows with "
            "missing values instead of filling them in",
            "Compute the day-over-day change in {watch} across all {parts} {units}",
            "Flag abnormal days with {how}, fitting it only on data before each "
            "day it scores",
            "For the largest flagged day, hold each {unit} at its previous value "
            "in turn and measure how much of the change disappears",
            "Report the share of that change carried by the single biggest {unit}",
        ]),
    "signal": dict(
        ask=("How much of a {short} signal's backtested Sharpe on {parts} "
             "{units} survives being held out and paying costs?"),
        measure=("the held-out net Sharpe divided by the in-sample gross "
                 "Sharpe, measured on the same series with the last third of "
                 "history never used to choose anything"),
        steps=[
            "Download {name} with the script in the repo and drop rows with "
            "missing values instead of filling them in",
            "Build a cross-sectional score over the {parts} {units} from {how}",
            "Go long the top few and short the bottom few, equal weight, zero "
            "net, holding weights formed on one day to earn the next",
            "Hold out the last third of history and never use it to choose "
            "anything, then charge 10 bps of round-trip cost on realised turnover",
            "Report what share of the in-sample gross Sharpe the held-out net "
            "Sharpe keeps",
        ]),
}


def shape_for(skill: str) -> str:
    return SHAPE.get(skill, DEFAULT_SHAPE)


def build(skill: str, findings=None) -> tuple[Brief, Source] | None:
    """Một ô trên lưới -> một đề bài. Không dựng được thì trả None, không bịa."""
    shape = shape_for(skill)
    if skill not in PROVES[shape]:
        return None
    src = for_skill(skill)
    if src is None:
        return None

    words = WORDING[shape]
    slot = dict(name=src.name, watch=src.watch, unit=src.unit, units=src.units,
                parts=src.parts, since=src.since, how=_how(skill),
                short=STEP_SHORT[STEP_ONE[shape].get(skill,
                                                     DEFAULT_STEP_ONE[shape])])

    skills = [skill] + [s for s in ALWAYS if s != skill]
    skills += [s for s in src.skills if s in INHERIT and s not in skills][:2]

    return Brief(
        question=words["ask"].format(**slot),
        # Lấy CHÍNH CHỮ của JD, không tóm tắt lại: đây là chỗ nói ra project
        # này mô phỏng việc gì. Tóm tắt là thêm một tầng tôi tự diễn giải.
        answers_jd=" · ".join(duty_lines(findings)[:2]) or skill,
        dataset=src.name,
        dataset_url=src.url,
        method=[step.format(**slot) for step in words["steps"]],
        measure=words["measure"].format(**slot),
        days=DAYS,
        skills=[s for s in skills if s in PROVES[shape] or s in INHERIT],
        deliverable="one repo with tests + a one-page write-up",
    ), src


def duty_lines(findings) -> list[str]:
    """Dòng VIỆC PHẢI LÀM hay gặp nhất trong nhóm tin này.

    Nửa JD này trước giờ bị vứt. Nó không dùng để chấm điểm — chấm ứng viên
    bằng mô tả công việc là sai — nhưng nó là thứ nói rõ project nên mô phỏng
    cái gì, nên nó đi thẳng vào README của repo.
    """
    return list(getattr(findings, "duties", []) or [])


def _how(skill: str) -> str:
    """Một câu mô tả bước 1, đọc từ chính tệp sẽ được chép vào repo, để đề bài
    và code không bao giờ nói hai chuyện khác nhau."""
    shape = shape_for(skill)
    pick = STEP_ONE[shape].get(skill, DEFAULT_STEP_ONE[shape])
    text = (SCAFFOLD / shape / f"{pick}.py").read_text()
    for line in text.splitlines():
        if line.startswith("HOW = "):
            break
    return {
        "detect_model": "an isolation forest, refit each year on the previous three",
        "detect_sql": "a rolling standard-deviation threshold written as a SQL "
                      "window function",
        "detect_stat": "a rolling 4-sigma threshold",
        "signal_momentum": "a trailing 12-month return skipping the last month",
        "signal_model": "a ridge regression on trailing returns, refit each year",
    }[pick]


def scaffold(brief: Brief, src: Source, out: Path, headline: str = "") -> list[str]:
    """Đẻ ra repo chạy được — nửa dưới của khuôn.

    Đo trên 178 tin: 30% đòi cách làm (test, CI, tài liệu), 47% đòi số năm /
    track record. Cả hai KHÔNG phụ thuộc project hỏi gì; chúng phụ thuộc
    project trông thế nào lúc giao. Viết một lần, mọi ô trên lưới ăn theo.
    """
    skill = brief.skills[0]
    shape = shape_for(skill)
    pick = STEP_ONE[shape].get(skill, DEFAULT_STEP_ONE[shape])
    duties = brief.answers_jd.split(" · ") if brief.answers_jd else []
    fill = {
        "{{title}}": f"{skill.title()} — {src.watch}",
        "{{question}}": brief.question,
        "{{headline}}": headline or "run `make run` for the number",
        "{{dataset}}": src.name,
        "{{url}}": src.url,
        "{{unit}}": src.unit,
        "{{units}}": src.units,
        "{{watch}}": src.watch,
        "{{parts}}": str(src.parts),
        "{{since}}": src.since,
        "{{how}}": _how(skill),
        "{{short}}": STEP_SHORT[pick],
        "{{side}}": str(max(2, src.parts // 6)),
        "{{cost}}": "10",
        "{{duties}}": "\n".join(f"> · {d}" for d in duties) or "> (the postings "
                      "for this skill list no explicit responsibilities)",
    }
    out.mkdir(parents=True, exist_ok=True)
    written = []
    sources = list((SCAFFOLD / "common").iterdir()) + \
              [f for f in (SCAFFOLD / shape).iterdir()
               if not f.name.startswith(("detect_", "signal_")) or f.stem == pick]
    for source in sorted(sources):
        text = source.read_text()
        for key, value in fill.items():
            text = text.replace(key, value)
        name = ("detect.py" if source.stem.startswith("detect_")
                else "signal_rule.py" if source.stem.startswith("signal_")
                else source.name)
        (out / name).write_text(text)
        written.append(name)
    (out / ".gitignore").write_text(
        "data/\n__pycache__/\n.pytest_cache/\nchange.png\nsignal.png\n")
    return sorted(written + [".gitignore"])
