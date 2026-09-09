"""Sinh ĐỀ BÀI cho một project nhỏ — và kiểm tra nó trước khi tin.

Vì sao cần project mới thay vì dùng project cũ: project lớn có CHI PHÍ ĐỌC cao.
Không ai trả cái giá đó cho ứng viên chưa quyết định thích. Project nhỏ đọc 5
phút, và quan trọng hơn — **nó không có chỗ nào để nấp**. Người có kinh nghiệm
đọc xong là biết ngay có làm thật hay không.

Đây là chỗ DUY NHẤT trong hệ thống mà LLM được nghĩ ra cái mới. Ở CV và trang
kết quả nó chỉ được chọn và sắp xếp. Ở đây nó đang đề xuất *việc nên làm*, không
khai *việc đã làm*, nên không có sự thật nào để bịa.

Nhưng KHÔNG tin thẳng. Mọi đề bài phải qua `validate()`:

    câu hỏi phải là câu hỏi           dataset phải TRUY CẬP ĐƯỢC (kiểm HTTP thật)
    số đo phải kèm cách đo            phải ≤ 3 ngày
    phải chạm kỹ năng nhóm JD đòi     không được trùng project đã có

Đề bài trượt là trượt, không dùng. LLM giỏi hay dở không đổi được điều đó.
"""

from __future__ import annotations

import json
import re
import sqlite3
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field

from ..core import llm
from ..ingest.base import UA, norm

MAX_DAYS = 3.0
MIN_SKILL_OVERLAP = 2

# Một số ĐO ĐƯỢC. Ba dạng, và phải nhận đủ cả ba — bản cũ chỉ có từ vựng tài
# chính (sharpe/auc/rmse/error) nên nó LOẠI OAN mọi đề bài học máy: đo bằng
# R-squared, accuracy hay Brier score đều trượt. Chạy thật ngày 09/09: ba trong
# bốn đề bài tốt nhất bị chặn ở đây, và máy chọn mất cái yếu hơn.
MEASURE_NUMBER = re.compile(
    r"\d"                                            # 1 · con số thẳng
    r"|\bhow (?:much|many|often|far)\b"
    # 2 · chỉ số CÓ TÊN — thứ tra ra được một con số
    r"|\b(?:ratio|rate|percent\w*|sharpe|sortino|calmar|drawdown|turnover"
    r"|auc|roc|rmse|mae|mse|error|r[- ]?squared|r2|accuracy|precision|recall"
    r"|f1|log[- ]?loss|brier|correlation|p[- ]value|t[- ]stat\w*|hit rate"
    r"|count|share of|proportion)\b"
    # 3 · phép SO SÁNH nói rõ hai vế. Cố ý KHÔNG nhận "better"/"worse": nói
    # "nó chạy tốt hơn" không phải một số đo, đó là một ý kiến.
    r"|\b(?:difference|minus|change in|delta|gap between|ratio of"
    r"|before and after|improvement in|reduction in|lift|versus|vs)\b", re.I)
# Câu hỏi CÓ THỂ SAI — mở ra hai kết cục, không phải chỉ một.
#
# Đây là CỔNG, không phải thước. Trước đây nó là một chiều chấm điểm: câu hỏi
# không kiểm chứng được thì trừ 20 điểm rồi vẫn có thể được chọn. Nhưng chính
# code tự nói ra bản chất của nó — "không phải nghiên cứu, là quảng cáo" — và
# đó là câu của một cái cổng. Trừ điểm một thứ đáng loại là nói nước đôi.
FALSIFIABLE = re.compile(
    r"\b(how much|how far|does|do |whether|is it|are they|compared? (?:to|with)|"
    r"versus|vs\b|difference between|instead of|better than|worse than|"
    r"how many|to what extent|what happens (?:if|when))\b", re.I)

# Bài mẫu ai cũng làm — làm lại thì không chứng minh được gì. Cũng là CỔNG.
TUTORIAL = re.compile(
    r"\b(titanic|iris dataset|mnist|house prices?|boston housing|"
    r"sentiment analysis of tweets|movie recommend\w*|churn prediction demo|"
    r"hello world|stock price prediction with lstm)\b", re.I)

MEASURE_METHOD = re.compile(
    r"\b(measured|compared?|across|over|against|baseline|out[- ]of[- ]sample|"
    r"holdout|walk[- ]forward|repeated|trials?|folds?|split)\b", re.I)


@dataclass
class Brief:
    question: str = ""
    answers_jd: str = ""
    dataset: str = ""
    dataset_url: str = ""
    method: list[str] = field(default_factory=list)
    measure: str = ""
    days: float = 0.0
    skills: list[str] = field(default_factory=list)
    deliverable: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Problem:
    field: str
    why: str


def url_ok(url: str, timeout: float = 12.0) -> bool:
    """Dataset có thật không. Đây là hàng rào mạnh nhất — LLM không bịa được
    một URL vừa trông hợp lý vừa trả về 200."""
    if not re.match(r"^https?://", url or ""):
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 405):                 # chặn HEAD nhưng trang có thật
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return 200 <= resp.status < 400
            except Exception:                      # noqa: BLE001
                return False
        return False
    except Exception:                              # noqa: BLE001
        return False


def validate(brief: Brief, wanted_skills: list[str], existing: list[str],
             check_url=url_ok) -> list[Problem]:
    """Mọi lý do đề bài này không dùng được. Rỗng = dùng được."""
    out: list[Problem] = []

    q = (brief.question or "").strip()
    if not q.endswith("?"):
        out.append(Problem("question", "phải là một câu hỏi, kết thúc bằng dấu ?"))
    if not 20 <= len(q) <= 220:
        out.append(Problem("question", "một câu, 20–220 ký tự"))

    # Luật CẤU TRÚC tách khỏi luật MẠNG. Trước đây kiểm định dạng nằm trong
    # url_ok(), nên thay url_ok bằng bản giả là mất luôn luật — test không bắt
    # được, mà thực tế thì một chuỗi "my_file.csv" vẫn lọt qua.
    url = (brief.dataset_url or "").strip()
    if not url:
        out.append(Problem("dataset_url", "phải nêu nguồn dữ liệu công khai"))
    elif not re.match(r"^https?://", url):
        out.append(Problem("dataset_url", "phải là địa chỉ http(s) công khai, "
                                          "không phải file trên máy"))
    elif not check_url(url):
        out.append(Problem("dataset_url", f"không truy cập được: {url[:60]}"))

    steps = [s for s in brief.method if len(s.strip()) >= 20]
    if not 3 <= len(steps) <= 6:
        out.append(Problem("method", f"cần 3–6 bước thực chất, đang có {len(steps)}"))

    if not MEASURE_NUMBER.search(brief.measure or ""):
        out.append(Problem("measure", "số đo phải có con số hoặc phép so sánh"))
    if not MEASURE_METHOD.search(brief.measure or ""):
        out.append(Problem("measure",
                           "phải nói CÁCH ĐO — thiếu nó thì con số vô nghĩa"))

    if not 0 < brief.days <= MAX_DAYS:
        out.append(Problem("days", f"phải trong {MAX_DAYS:g} ngày, đang là {brief.days:g}"))

    hit = {norm(s) for s in brief.skills} & {norm(s) for s in wanted_skills}
    if len(hit) < MIN_SKILL_OVERLAP:
        out.append(Problem("skills",
                           f"mới chạm {len(hit)} kỹ năng nhóm JD đòi, cần ≥{MIN_SKILL_OVERLAP}"))

    if not re.search(r"\b(notebook|repo|page|write[- ]up|report|script)\b",
                     brief.deliverable or "", re.I):
        out.append(Problem("deliverable", "phải nói rõ nộp cái gì"))

    if not FALSIFIABLE.search(q):
        out.append(Problem("question", "không thể ra kết quả NGƯỢC với mong đợi "
                                       "— chỉ xác nhận được, không kiểm chứng được"))
    if TUTORIAL.search(f"{q} {brief.dataset}"):
        out.append(Problem("dataset", "là bài mẫu phổ biến — làm lại không "
                                      "chứng minh được gì"))

    qn = set(norm(q).split())
    for old in existing:
        on = set(norm(old).split())
        if on and len(qn & on) / len(on) > 0.6:
            out.append(Problem("question", f"trùng project đã có: {old[:50]}"))
            break
    return out


# ---------------------------------------------------------------- sinh

PROMPT = """You are helping a job applicant design ONE small portfolio project.

THE POSTINGS THEY ARE TARGETING ({jobs} of them, at {companies}) list these requirement lines more than once (each line's count is given;
most lines appear in only one posting, so treat these as samples, not consensus):
{needs}

Concepts these postings name most often: {concepts}
Data sources they name: {data}
Skills the cluster demands: {skills}

THE APPLICANT ALREADY BUILT (do not repeat these):
{existing}

Design ONE project that answers a single sharp question a reader can check in
five minutes. Hard constraints — a brief that breaks any of these is useless:

  - Finishable in at most {max_days:g} days by one person
  - Uses a PUBLIC dataset with a real, working URL
  - Produces ONE number, with the method of measuring stated
  - Touches at least 2 of the skills listed above
  - Small enough that there is nowhere to hide sloppiness

Reply with ONLY a JSON object, no prose around it:
{{"question": "...?",
  "answers_jd": "which requirement above it answers",
  "dataset": "name",
  "dataset_url": "https://...",
  "method": ["step 1", "step 2", "step 3"],
  "measure": "what number, and how it is measured",
  "days": 2,
  "skills": ["skill", "skill"],
  "deliverable": "one notebook + a one-page write-up"}}"""


def build_prompt(findings, existing: list[str]) -> str:
    return PROMPT.format(
        jobs=findings.jobs,
        companies=", ".join(findings.companies[:6]) or "several firms",
        needs="\n".join(f"  - ({n} postings) {t}" for t, n in findings.core_needs[:6])
              or "  - (nothing repeated clearly)",
        concepts=", ".join(k for k, _ in findings.concepts[:8]) or "—",
        data=", ".join(k for k, _ in findings.data_named[:5]) or "none named",
        skills=", ".join(findings.skills[:10]),
        existing="\n".join(f"  - {e}" for e in existing[:5]) or "  - nothing yet",
        max_days=MAX_DAYS)


def parse_brief(text: str) -> Brief | None:
    """Bóc JSON ra khỏi câu trả lời. LLM hay bọc thêm chữ quanh nó."""
    if not text:
        return None
    found = re.search(r"\{.*\}", text, re.S)
    if not found:
        return None
    try:
        data = json.loads(found.group())
    except ValueError:
        return None
    known = set(Brief.__dataclass_fields__)
    clean = {k: v for k, v in data.items() if k in known}
    try:
        clean["days"] = float(clean.get("days", 0) or 0)
    except (TypeError, ValueError):
        clean["days"] = 0.0
    clean["method"] = [str(s) for s in (clean.get("method") or [])]
    clean["skills"] = [str(s) for s in (clean.get("skills") or [])]
    return Brief(**clean)


def generate(conn: sqlite3.Connection, findings, existing: list[str],
             check_url=url_ok) -> dict:
    """Sinh đề bài rồi KIỂM. Trả về trạng thái, không bao giờ trả đề bài chưa kiểm."""
    if findings.thin:
        return {"state": "not_enough",
                "why": f"chỉ {findings.jobs} tin có mô tả trong nhóm này — "
                       "không đủ để biết họ cần gì"}

    prompt = build_prompt(findings, existing)
    answer = llm.ask(conn, f"project_brief:{findings.cluster}", prompt)

    if answer.pending:
        return {"state": "pending", "engine": answer.engine, "prompt": prompt,
                "why": "đã xếp hàng chờ Claude trả lời trong phiên"}
    if not answer.text:
        return {"state": "no_llm", "engine": answer.engine, "prompt": prompt,
                "why": "chưa bật LLM — xem Settings"}

    brief = parse_brief(answer.text)
    if brief is None:
        return {"state": "unreadable", "engine": answer.engine,
                "why": "câu trả lời không phải JSON đọc được"}

    problems = validate(brief, findings.skills, existing, check_url)
    return {"state": "ok" if not problems else "rejected",
            "engine": answer.engine, "brief": brief,
            "problems": [asdict(p) for p in problems]}
