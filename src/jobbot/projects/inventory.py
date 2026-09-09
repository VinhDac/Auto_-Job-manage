"""Kho project — tích tiểu thành đại.

Vì sao cần: một project làm mất 2-3 ngày. Trước đây pipeline sinh đề bài rồi
vẽ ra màn hình và VỨT — mỗi lần mở trang chạy lại cả bảy chặng từ đầu. Đo
được ngày 09/09: 9 lần hỏi LLM, 4 câu trả lời, và cả 4 đều thuộc một nhóm ma
đã biến mất. Không có gì tích lại.

Trục là KỸ NĂNG, không phải nhóm JD:

    nhóm JD   sinh ra từ dữ liệu -> dữ liệu đổi là nhóm đổi là đề bài mồ côi
    kỹ năng   từ vựng cố định trong scoring/vocab.py, 44 cái, không tự đổi

Ngành là NHÃN chứ không phải trục thứ hai: 44 kỹ năng × 5 ngành = 220 ô, mà
làm được ~1 project/tuần thì ba tháng mới có 12 cái. Ngành không đổi KỸ NĂNG
một project chứng minh được, nó đổi CÂU CHUYỆN lúc đem đi nộp.

KHOẢNG TRỐNG không lưu thành dòng — nó là phép trừ, tính lúc đọc:

    demand   kỹ năng đó bao nhiêu tin đòi
    supply   tag project trên CV  ∪  skills của project trong kho
    gap      demand trừ supply, xếp theo demand
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter

from ..ingest.base import norm
from ..scoring.vocab import alias_hits

# Trạng thái một project. Ba cái, không hơn.
DE_BAI, DANG_LAM, XONG = "de_bai", "dang_lam", "xong"
STATES = (DE_BAI, DANG_LAM, XONG)
STATE_LABEL = {DE_BAI: "đề bài", DANG_LAM: "đang làm", XONG: "xong"}

# Lưới hỏi "project này CHỨNG MINH được gì", nên nó chỉ chứa NĂNG LỰC.
# Hai loại bị loại ra:
#   · có ở gần như mọi tin  -> python 125/178, statistics 97/178: không phải
#     lợi thế, đưa lên chỉ tạo ô luôn xanh mà không nói lên điều gì
#   · là CÔNG CỤ, không phải năng lực -> không ai làm một project để "chứng
#     minh pandas"; pandas là cách làm, không phải thứ làm được
TABLE_STAKES = {"python", "statistics",          # có ở khắp nơi
                "pandas", "numpy", "r", "linux", "cloud"}   # công cụ

# Dưới ngần này tin thì chưa đáng bỏ 2-3 ngày làm một project.
MIN_DEMAND = 15

# Chỉ đọc ĐẦU tin để đoán ngành. Công ty tự giới thiệu ở trên, phúc lợi nằm ở
# dưới cùng — mà phúc lợi công ty nào cũng có "medical, dental and vision
# INSURANCE". Đo ngày 09/09 trên 178 tin: đọc 4.000 ký tự thì nhãn `insurance`
# dính 27 tin, trong đó Jump Trading (quỹ tự doanh) dính vì đúng câu phúc lợi
# đó, và 89% chỗ khớp nằm ở 30% CUỐI tin. Cắt còn 1.500 ký tự: insurance còn 4,
# mà crypto 12->11, fintech 14->11 — bỏ gần hết cái sai, giữ gần hết cái đúng.
ABOUT_CHARS = 1500

# NGÀNH — nhãn, không phải trục. Đoán bằng chữ trong chính tin: tên công ty,
# chức danh, thân tin. Không có bộ phân loại nào khác trong app, và bịa ra một
# cái to hơn là tự phức tạp hoá — bảy nhãn này là bảy chỗ Vin thật sự nộp.
#
# Ngành không đổi KỸ NĂNG một project chứng minh được. Nó đổi CÂU CHUYỆN: cùng
# một bài backtest, kể cho quỹ đầu cơ khác hẳn kể cho công ty bảo hiểm.
INDUSTRY: dict[str, set[str]] = {
    "hedge fund": {"hedge fund", "systematic fund", "multi-strategy",
                   "multi strategy", "prop trading", "proprietary trading",
                   "market making", "market maker", "quant fund"},
    # "structuring" trần bị bỏ: đo được nó khớp vào "cleansing and structuring
    # for downstream" — cấu trúc DỮ LIỆU, không phải cấu trúc sản phẩm tài chính.
    "investment bank": {"investment bank", "sell-side", "sell side",
                        "trading desk", "front office", "deal structuring",
                        "product structuring"},
    "asset management": {"asset management", "asset manager", "buy-side",
                         "buy side", "wealth management", "pension fund",
                         "fund management", "institutional investor"},
    "fintech": {"fintech", "payment", "neobank", "challenger bank",
                "lending platform", "e-money"},
    "insurance": {"insurance", "insurer", "actuarial", "reinsurance",
                  "underwriting"},
    "crypto": {"crypto", "cryptocurrency", "cryptocurrencies", "cryptoasset",
               "digital asset", "blockchain", "defi"},
    "energy": {"energy trading", "commodity trading", "commodities trading",
               "power trading", "carbon market"},
}

# Khớp theo BIÊN TỪ, không phải chuỗi con. Cùng một lỗi đã một lần sinh ra cả
# một nhóm ma: 'excel' nằm trong 'excellent'. Đo lại ở đây: 'defi' dính 19 tin,
# cả 19 đều là 'defining' / 'definitions' / 'redefining'.
_INDUSTRY_RE = {
    name: re.compile(r"\b(?:" + "|".join(sorted((re.escape(w) for w in words),
                                                key=len, reverse=True)) + r")s?\b")
    for name, words in INDUSTRY.items()
}


def _now() -> str:
    from ..core.postings import now
    return now()


def add(conn: sqlite3.Connection, brief, industries: list[str] | None = None) -> int:
    """Cất một đề bài đã qua kiểm vào kho."""
    cur = conn.execute(
        "INSERT INTO project (question, skills, industries, state, brief_json, made_at)"
        " VALUES (?,?,?,?,?,?)",
        (brief.question, ",".join(brief.skills or []),
         ",".join(industries or []), DE_BAI,
         json.dumps(brief.as_dict(), ensure_ascii=False), _now()))
    conn.commit()
    return int(cur.lastrowid)


def all(conn: sqlite3.Connection) -> list[dict]:
    """Cả kho, đề bài mới nhất lên trước, nhưng XONG xếp trên cùng."""
    order = {XONG: 0, DANG_LAM: 1, DE_BAI: 2}
    rows = [dict(r) for r in conn.execute(
        "SELECT id, question, skills, industries, state, link, made_at"
        " FROM project ORDER BY id DESC")]
    for row in rows:
        row["skills"] = [s for s in row["skills"].split(",") if s]
        row["industries"] = [s for s in row["industries"].split(",") if s]
    rows.sort(key=lambda r: order.get(r["state"], 9))
    return rows


def set_state(conn: sqlite3.Connection, project_id: int, state: str,
              link: str = "") -> None:
    if state not in STATES:
        return
    conn.execute("UPDATE project SET state = ?, link = ? WHERE id = ?",
                 (state, link, project_id))
    conn.commit()


def _scan(conn: sqlite3.Connection):
    """Mỗi tin đang giữ -> (dòng tin, tập kỹ năng nó ĐÒI).

    Kỹ năng lấy từ phần YÊU CẦU đã tách, không phải toàn văn tin: toàn văn có
    cả đoạn giới thiệu công ty và đoạn phúc lợi, đọc vào là tin nào cũng đòi
    mọi thứ.
    """
    for row in conn.execute(
            "SELECT id, company, title, description, score_json FROM posting"
            " WHERE kept = 1 AND score_json != ''"):
        try:
            reqs = json.loads(row["score_json"]).get("requirements", [])
        except (TypeError, ValueError):
            continue
        skills = {h for r in reqs for h in alias_hits(norm(r.get("text", "")))}
        if skills:
            yield row, skills


def demand(conn: sqlite3.Connection) -> Counter:
    """Kỹ năng nào bao nhiêu TIN đòi. Đếm theo tin, không theo dòng yêu cầu —
    một tin nhắc 'python' năm lần vẫn chỉ là một tin."""
    return _market(conn)[0]


def industries(conn: sqlite3.Connection, top: int = 3) -> dict[str, list[str]]:
    """Kỹ năng nào hay được ngành nào đòi."""
    return {s: [n for n, _ in c.most_common(top)]
            for s, c in _market(conn)[1].items()}


def total_scored(conn: sqlite3.Connection) -> int:
    """Mẫu số của lưới: bao nhiêu tin đang giữ ĐÃ được chấm điểm.

    Không có mẫu số thì "55 tin" là con số trôi nổi — 55 trên bao nhiêu? Có
    mẫu số thì Vin đọc ra ngay đó là 31% thị trường, và tự kiểm được.
    """
    return int(conn.execute(
        "SELECT COUNT(*) FROM posting WHERE kept = 1 AND score_json != ''"
    ).fetchone()[0])


def _market(conn: sqlite3.Connection) -> tuple[Counter, dict[str, Counter]]:
    """MỘT vòng quét ra cả hai con số. Tách làm hai hàm quét riêng thì mỗi lần
    vẽ lưới là đọc lại toàn bộ thân tin hai lượt — đo được 565ms, giờ 285ms.
    """
    counts: Counter = Counter()
    tags: dict[str, Counter] = {}
    for row, skills in _scan(conn):
        counts.update(skills)
        blob = norm(f"{row['company']} {row['title']} "
                    f"{(row['description'] or '')[:ABOUT_CHARS]}")
        here = [name for name, pat in _INDUSTRY_RE.items() if pat.search(blob)]
        for skill in skills if here else ():
            tags.setdefault(skill, Counter()).update(here)
    return counts, tags


def supply(conn: sqlite3.Connection, cv_projects: list) -> dict[str, int | None]:
    """Kỹ năng nào ĐÃ CÓ BẰNG CHỨNG THẬT, và bằng chứng đó là project nào.

    Chỉ tính thứ ĐÃ LÀM XONG. Một đề bài chưa làm không phải bằng chứng — nó
    là ý định. Tính nó là lấp ô thì bấm Dựng mười lăm lần là lưới sạch bong
    trong khi chưa viết dòng code nào, và cả cái lưới thành trò tự lừa mình.

    Hợp hai nguồn lúc ĐỌC, không chép CV vào bảng: chép là tự tạo hai bản rồi
    phải ngồi giữ chúng khớp nhau. CV đứng trước — project trên CV là thứ đã
    nộp đi rồi, chắc hơn một dòng vừa đánh dấu xong trong kho.
    """
    out: dict[str, int | None] = {}
    for block in cv_projects:                      # None = có sẵn trên CV
        for tag in getattr(block, "tags", []) or []:
            out.setdefault(tag, None)
    for row in conn.execute("SELECT id, skills FROM project WHERE state = ?",
                            (XONG,)):
        for skill in row["skills"].split(","):
            if skill:
                out.setdefault(skill, row["id"])
    return out


def planned(conn: sqlite3.Connection) -> dict[str, tuple[int, str]]:
    """Kỹ năng nào ĐANG có người nhắm tới — đề bài hoặc đang làm dở.

    Tách hẳn khỏi supply(): nó không lấp ô, nhưng nó là lý do KHÔNG dựng thêm
    một đề bài nữa cho cùng một kỹ năng.
    """
    out: dict[str, tuple[int, str]] = {}
    for row in conn.execute(
            "SELECT id, skills, state FROM project WHERE state != ?"
            " ORDER BY id", (XONG,)):
        for skill in row["skills"].split(","):
            if skill:
                out.setdefault(skill, (row["id"], row["state"]))
    return out


def coverage(conn: sqlite3.Connection, cv_projects: list) -> list[dict]:
    """Lưới: kỹ năng · bao nhiêu tin đòi · đã có gì đỡ chưa.

    Bỏ TABLE_STAKES và bỏ kỹ năng dưới MIN_DEMAND tin — còn lại khoảng mười ô,
    đủ để ba tháng phủ kín, thay vì 44 ô không bao giờ đầy.
    """
    have = supply(conn, cv_projects)
    doing = planned(conn)
    counts, tag_counts = _market(conn)
    tags = {s: [n for n, _ in c.most_common(3)] for s, c in tag_counts.items()}
    out = []
    for skill, n in counts.most_common():
        if skill in TABLE_STAKES or n < MIN_DEMAND:
            continue
        out.append({"skill": skill, "demand": n,
                    "covered": skill in have,          # đã có bằng chứng thật
                    "planned": doing.get(skill),       # (id, trạng thái) hoặc None
                    "industries": tags.get(skill, []),
                    "by": have.get(skill)})     # None = trên CV, số = id trong kho
    return out


def uncovered(conn: sqlite3.Connection, cv_projects: list) -> list[dict]:
    """Ô chưa ai đụng tới — chưa có bằng chứng VÀ chưa ai nhận làm."""
    return [c for c in coverage(conn, cv_projects)
            if not c["covered"] and not c["planned"]]
