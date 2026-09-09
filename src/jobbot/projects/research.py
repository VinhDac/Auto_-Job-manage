"""Đọc kỹ một nhóm JD để biết họ THẬT SỰ cần gì.

Từ khoá chỉ nói "python, statistics". Nó không nói bài toán là gì.
Ở đây rút ra thứ dùng được để nghĩ đề bài:

    - yêu cầu nào lặp lại ở NHIỀU tin trong nhóm (đó mới là cốt lõi)
    - công cụ / dữ liệu / khái niệm được gọi tên
    - ngành các công ty này làm gì

Toàn bộ đọc từ JD đã có trong DB. Chrome chỉ thêm phần "công ty này làm gì"
khi cần — và chỉ khi cần, vì JD thường đã tự nói.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from ..cv.build import skills_in
from ..ingest.base import norm
from ..scoring import extract
from ..core.journal import PROJECT, log as jlog

# Khái niệm chuyên môn hay xuất hiện trong JD quant/data mà vocab chưa gọi tên
CONCEPTS = re.compile(
    r"\b(alpha|signal|backtest\w*|out[- ]of[- ]sample|overfit\w*|regime|"
    r"factor model\w*|risk model\w*|portfolio construction|execution|slippage|"
    r"market microstructure|order book|tick data|time series|forecast\w*|"
    r"feature engineering|cross[- ]validation|hyperparameter|"
    r"stress test\w*|scenario analysis|var\b|drawdown|sharpe|attribution|"
    r"pnl|pricing model\w*|calibration|monte carlo|stochastic)\b", re.I)

# Dữ liệu / nguồn được gọi tên
DATA_HINT = re.compile(
    r"\b(tick data|order book|market data|bloomberg|refinitiv|reuters|"
    r"crsp|compustat|wrds|yahoo finance|quandl|fred|kaggle|"
    r"alternative data|satellite|credit card|web scraping|news sentiment)\b", re.I)


@dataclass
class Findings:
    cluster: str
    jobs: int = 0
    core_needs: list[tuple[str, int]] = field(default_factory=list)
    concepts: list[tuple[str, int]] = field(default_factory=list)
    data_named: list[tuple[str, int]] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    skill_counts: list[tuple[str, int]] = field(default_factory=list)
    sample_lines: list[str] = field(default_factory=list)
    web_notes: list = field(default_factory=list)          # đọc từ trang công ty
    web_vocabulary: list[tuple[str, int]] = field(default_factory=list)

    @property
    def thin(self) -> bool:
        """Không đủ để nghĩ đề bài. Nói thẳng còn hơn sinh bừa."""
        return self.jobs < 2 or not self.core_needs


def _normalise_req(text: str) -> str:
    """Rút một dòng yêu cầu về dạng so sánh được giữa các tin."""
    low = re.sub(r"[^a-z ]+", " ", text.lower())
    stop = {"and", "or", "the", "a", "an", "of", "in", "to", "with", "for",
            "you", "we", "our", "your", "is", "are", "be", "have", "has",
            "strong", "experience", "knowledge", "ability", "skills", "good",
            "excellent", "working", "understanding", "proven", "solid"}
    words = [w for w in low.split() if w not in stop and len(w) > 2]
    return " ".join(sorted(set(words))[:6])


def study(conn: sqlite3.Connection, cluster) -> Findings:
    """Đọc mọi JD trong nhóm, rút ra cái chung."""
    ids = [j["id"] for j in cluster.jobs]
    if not ids:
        return Findings(cluster.title)
    marks = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT title, company, description, via_agency FROM posting"
        f" WHERE id IN ({marks})", ids).fetchall()

    need_counts: Counter[str] = Counter()
    need_text: dict[str, str] = {}
    concepts: Counter[str] = Counter()
    data: Counter[str] = Counter()
    skills: Counter[str] = Counter()
    lines: list[str] = []

    for row in rows:
        text = row["description"] or ""
        if len(text) < 300:
            continue
        seen_here: set[str] = set()
        for req in extract.requirements(text):
            key = _normalise_req(req.text)
            if not key or key in seen_here:
                continue
            seen_here.add(key)
            need_counts[key] += 1
            need_text.setdefault(key, req.text.strip())
        for m in CONCEPTS.finditer(text):
            concepts[m.group().lower()] += 1
        for m in DATA_HINT.finditer(text):
            data[m.group().lower()] += 1
        skills.update(skills_in(text))

    # Yêu cầu chỉ đáng gọi là "cốt lõi" khi (a) xuất hiện ở NHIỀU tin VÀ
    # (b) có nội dung kỹ thuật.
    #
    # Không lọc (b) thì phần này toàn câu khuôn mẫu — "commitment to the highest
    # ethical standards", "intellectually curious" — lặp y hệt ở mọi công ty vì
    # ai cũng chép của nhau, trong khi yêu cầu kỹ thuật thì mỗi nơi viết một kiểu.
    def technical(text: str) -> bool:
        return bool(skills_in(text) or CONCEPTS.search(text))

    core = [(need_text[k], n) for k, n in need_counts.most_common(60)
            if n >= 2 and technical(need_text[k])][:8]
    for text, _n in core[:5]:
        lines.append(text[:220])

    return Findings(
        cluster=cluster.title, jobs=len(rows),
        core_needs=core,
        concepts=concepts.most_common(10),
        data_named=data.most_common(6),
        # CHỦ VIỆC thật, không phải hãng môi giới. Đọc trang của một hãng tuyển
        # dụng chỉ biết được họ tuyển dụng giỏi thế nào — không biết gì về công
        # việc. Xếp theo số tin: công ty đăng nhiều tin trong nhóm là công ty
        # định hình nhóm đó.
        companies=[c for c, _ in Counter(
            r["company"] for r in rows
            if not r["via_agency"] and r["company"] not in ("", "unknown")
        ).most_common(10)],
        skills=[s for s, _ in skills.most_common(12)],
        # GIỮ cả số đếm. Đây là tín hiệu cầu ĐÁNG TIN duy nhất trong Findings:
        # nó gộp trên toàn bộ nhóm. Còn core_needs thì gom theo câu chữ nên vụn
        # — đo ngày 09/09 trên nhóm 'machine learning': 571 khoá khác nhau trên
        # 696 dòng yêu cầu, dòng lặp nhiều nhất chỉ có ở 3/55 tin.
        skill_counts=skills.most_common(12),
        sample_lines=lines,
    )


# ---------------------------------------------------------------- Chrome

DOMAIN_SKIP = {"unknown", "confidential"}
ABOUT_PATHS = ["/about", "/what-we-do", "/research", "/technology", "/engineering",
               "/blog", "/insights", "/", "/about-us"]

# Đoạn về cookie / quyền riêng tư. Trang nào cũng có, và nó là đoạn dài đầu
# tiên trên trang — nên nếu chỉ lấy "đoạn dài đầu tiên" thì lấy đúng nó.
COOKIE_NOISE = re.compile(
    r"\b(cookie|privacy polic|personal data|third[- ]party|consent|"
    r"your agreement|store, access|advertis|gdpr|opt[- ]out|"
    r"we and our \d+ partners)\b", re.I)

# Trang rao bán tên miền / đỗ tạm. quberesearch.com là HugeDomains, không phải
# Qube Research — nạp nó vào là đề bài sinh ra từ mô tả của một công ty bán domain.
PARKED = re.compile(
    r"\b(hugedomains|godaddy|sedo|dan\.com|afternic|namecheap|"
    r"buy this domain|domain (?:is )?for sale|this domain (?:is|may be)|"
    r"the domain name .{0,30} is for sale|make an offer|parked (?:free )?courtesy)\b",
    re.I)

# Chữ chỉ CÁCH LÀM VIỆC, thứ JD hiếm khi nói mà trang công ty hay nói
HOW_THEY_WORK = re.compile(
    r"\b(systematic|discretionary|high[- ]frequency|market making|"
    r"long[- ]short|multi[- ]strategy|statistical arbitrage|"
    r"machine learning|research[- ]driven|data[- ]driven|"
    r"petabytes?|latency|colocation|tick[- ]level|intraday|"
    r"open[- ]source|python|c\+\+|kdb|gpu cluster)\b", re.I)


@dataclass
class WebNote:
    company: str
    url: str = ""
    what_they_do: str = ""
    vocabulary: list[str] = field(default_factory=list)
    failed: str = ""


def _domains(name: str) -> list[str]:
    base = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())
    base = re.sub(r"\b(ltd|limited|llp|plc|inc|llc|group|capital|partners?|"
                  r"management|technologies|securities)\b", " ", base)
    words = base.split()
    if not words:
        return []
    joined = "".join(words)
    out = [f"{joined}.com"]
    if len(words) > 1:
        out.append(f"{'-'.join(words)}.com")
        out.append(f"{words[0]}.com")
    out += [f"{joined}.co.uk", f"{joined}.ai"]
    return [d for d in dict.fromkeys(out) if 5 < len(d) < 40]


def web_study(tab, findings: Findings, limit: int = 3) -> list[WebNote]:
    """Mở trang công ty đọc xem họ THẬT SỰ làm gì.

    JD viết bởi bộ phận tuyển dụng và chép lẫn nhau. Trang công ty viết bởi
    chính họ, và nói những thứ JD không nói: làm systematic hay discretionary,
    tần suất nào, dùng dữ liệu gì.

    Chậm — vài chục giây một công ty. Không sao: nó chạy một lần cho cả nhóm,
    và kết quả dùng cho hàng chục tin.
    """
    from ..ingest.web.base import Blocked, open_page

    notes: list[WebNote] = []
    wanted = [c for c in findings.companies[:limit] if norm(c) not in DOMAIN_SKIP]
    for index, company in enumerate(wanted, 1):
        # Vài chục giây một công ty, mở Chrome thật — không báo tiến độ thì
        # màn hình im lặng suốt và người dùng tưởng treo.
        jlog.progress(PROJECT, f"đọc trang công ty — {company}", index, len(wanted))
        note = WebNote(company=company)
        for domain in _domains(company)[:3]:
            for path in ABOUT_PATHS[:5]:
                url = f"https://{domain}{path}"
                try:
                    open_page(tab, url, timeout=20)
                except Blocked:
                    note.failed = "trang chặn truy cập tự động"
                    break
                except Exception:                       # noqa: BLE001
                    continue
                text = (tab.text() or "").strip()
                if len(text) < 400:
                    continue
                # Trang có nói về họ không, hay chỉ là trang lỗi
                if not re.search(r"\b(we|our|the firm|the company)\b", text[:1500], re.I):
                    continue
                if PARKED.search(text[:2500]):
                    continue                        # trang rao bán tên miền

                # ĐÚNG công ty này chứ? "Man Group" đoán ra man.ai — một công ty
                # hoàn toàn khác. Nạp nhầm là đề bài sinh ra từ mô tả của người lạ.
                #
                # Phải so theo RANH GIỚI TỪ: "man" nằm trong "permanent",
                # "management", "human" — so chuỗi con thì trang nào cũng khớp.
                words = [w for w in norm(company).split() if len(w) > 2]
                key = max(words, key=len) if words else ""
                head = f" {norm(text[:5000])} "
                if key and f" {key} " not in head and f" {key}s " not in head:
                    continue

                # Bỏ đoạn cookie — nó luôn là đoạn dài đầu tiên trên trang
                paras = [x.strip() for x in text.split("\n")
                         if 120 < len(x.strip()) < 600 and not COOKIE_NOISE.search(x)]
                if not paras:
                    continue
                note.url = url
                note.what_they_do = paras[0][:400]
                note.vocabulary = sorted({m.group().lower()
                                          for m in HOW_THEY_WORK.finditer(text)})[:12]
                break
            if note.url or note.failed:
                break
        if not note.url and not note.failed:
            note.failed = "không tìm được trang công ty"
        notes.append(note)
    jlog.done(PROJECT)
    return notes


def merge_web(findings: Findings, notes: list[WebNote]) -> Findings:
    """Ghép hiểu biết từ trang công ty vào kết quả đọc JD."""
    extra: Counter[str] = Counter()
    for note in notes:
        for word in note.vocabulary:
            extra[word] += 1
    findings.web_notes = [n for n in notes if n.url]
    findings.web_vocabulary = extra.most_common(10)
    return findings
