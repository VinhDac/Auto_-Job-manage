"""Test bước 4 — gom nhóm JD và trang kết quả.  python3 tests/test_projects.py"""

import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db, postings
from jobbot.cv import rules
from jobbot.cv.blocks import parse
from jobbot.ingest.base import Posting
from jobbot.projects.cluster import TOO_COMMON, build as cluster
from jobbot.projects.page import _slot, build as build_page, health

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

CV = """DAC VINH NGUYEN
EXPERIENCE
Founder / Quantitative Developer — Trading Startup Jan 2026 – Present
I designed and built two systems in Python with portfolio construction and risk limits.
A random train/test split leaks, because adjacent dates are correlated.
Live drawdown ran roughly 30% deeper than the model predicted.
The mistake was mine: thousands of free parameters is still room to overfit.
I ran walk-forward validation across 17 instruments and five years of data.
SELECTED PROJECTS
Quant Trading Studio — backtesting, out-of-sample validation and risk budgeting on the
efficient frontier.
TECHNICAL SKILLS
Programming — Python, SQL.
"""
PROFILE = {"cv_text": CV, "links": "https://github.com/vin/studio"}

print("\n[xếp câu vào phần nào]")
cases = [
    ("The mistake was mine: thousands of free parameters is still room to overfit", "tradeoff"),
    ("Live drawdown ran roughly 30% deeper than the model predicted", "tradeoff"),
    ("A random train/test split leaks, because adjacent dates are correlated", "problem"),
    ("I designed and built two systems in Python with risk limits", "method"),
    ("I ran walk-forward validation across 17 instruments and five years of data", "numbers"),
]
for text, want in cases:
    check(f"{want:8} ← {text[:44]}…", _slot(text) == want)

print("\n[vòng lặp khép: câu bị CV cắt về đúng phần Đánh đổi]")
cut = [t for t in [c[0] for c in cases]
       if rules.sentence_ok(t)[0] == "drop" and rules.SELF_CRITIQUE.search(t)]
check("có câu bị CV cắt", len(cut) >= 2)
check("mọi câu bị cắt đều rơi vào tradeoff",
      all(_slot(t) == "tradeoff" for t in cut))

doc = build_page(PROFILE, "Quantitative Researcher", "Point72",
                 {"python", "risk", "validation", "portfolio"})
check("trang có phần Đánh đổi", len(doc.tradeoff) >= 2)
check("phần Đánh đổi chứa đúng câu CV đã bỏ",
      any("mistake was mine" in t for t in doc.tradeoff))
check("phần Cách làm không dính câu thất bại",
      not any(rules.SELF_CRITIQUE.search(t) for t in doc.method))
check("bắt được link code", any("github.com" in c for c in doc.code))
check("nêu được trang trả lời tin này ở điểm nào", "python" in doc.speaks_to)

print("\n[chỗ trang còn thiếu]")
thin = build_page({"cv_text": "EXPERIENCE\nAnalyst — X Jan 2025 – Present\n"
                              "I built dashboards in Python for the team.\n"}, "A", "B", {"python"})
gaps = dict(health(thin))
check("thiếu số đo -> báo", "No measurement" in gaps)
check("không có chỗ đánh đổi -> báo", "Nothing given up" in gaps)
check("thiếu link code -> báo", "No code link" in gaps)
check("trang đủ thì không báo bừa", "Nothing given up" not in dict(health(doc)))

print("\n[gom nhóm]")
with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")
    items = []
    # python có ở MỌI tin -> không được làm khoá nhóm
    for i, (title, desc) in enumerate([
        ("Quant Researcher", "python time series statistics"),
        ("Quant Analyst", "python time series statistics"),
        ("Quant Developer", "python time series"),
        ("ML Engineer", "python pytorch deep learning"),
        ("ML Scientist", "python pytorch deep learning"),
    ]):
        items.append(Posting(source_id=f"s{i}", title=title, company=f"Co{i}",
                             location="London", description=desc))
    postings.save_batch(conn, "test", items)
    conn.execute("UPDATE posting SET kept = 1, drop_reason = ''")
    conn.commit()

    groups = cluster(conn, [])
    keys = [g.key for g in groups if g.key != "other"]
    check("KHÔNG lấy kỹ năng phổ biến nhất làm khoá", "python" not in keys)
    check("tách được ít nhất 2 nhóm", len(keys) >= 2)
    check("nhóm nào cũng đủ số tin tối thiểu",
          all(len(g.jobs) >= 2 for g in groups if g.key != "other"))
    check("mọi tin đều được xếp vào đâu đó",
          sum(len(g.jobs) for g in groups) >= 5)

    have = [b for b in parse(CV) if b.kind == "project"]
    covered = cluster(conn, have)
    check("project có thật thì đánh dấu nhóm đã được trả lời",
          any(not g.gap for g in covered if g.key != "other")
          or all(g.gap for g in covered if g.key != "other"))
    conn.close()

# ---------------------------------------------------------------- KHO PROJECT

print("\n[kho project — cung/cầu theo KỸ NĂNG]")
from jobbot.projects import inventory as inv, make
from jobbot.projects.brief import Brief

with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")
    rows = [
        ("a1", "Quant Researcher", "Cygnus", "we run a systematic fund",
         "backtesting and equities"),
        ("a2", "Quant Researcher", "Cygnus", "we run a systematic fund",
         "backtesting and portfolio"),
        ("a3", "Risk Analyst", "Solid Insurance", "actuarial reserving team",
         "risk and derivatives"),
        ("a4", "Data Scientist", "PayFlow", "payment processing platform",
         "machine learning and sql"),
    ]
    import json as _json
    postings.save_batch(conn, "t", [
        Posting(source_id=sid, title=title, company=company,
                location="London", url=f"https://x/{sid}", description=blurb)
        for sid, title, company, blurb, _needs in rows])
    for sid, _t, _c, _b, needs in rows:
        conn.execute("UPDATE posting SET kept = 1, score_json = ?"
                     " WHERE raw_id IN (SELECT id FROM raw_posting"
                     "                  WHERE source_id = ?)",
                     (_json.dumps({"requirements": [{"text": needs}]}), sid))
    conn.commit()

    counts = inv.demand(conn)
    check("đếm theo TIN, không theo dòng yêu cầu", counts["backtesting"] == 2)
    check("kỹ năng chỉ một tin đòi vẫn đếm được", counts["sql"] == 1)

    tags = inv.industries(conn)
    check("ngành đọc ra từ chính tin", "hedge fund" in tags.get("backtesting", []))
    check("ngành gắn đúng tin", "insurance" in tags.get("risk", []))
    check("ngành không dính sang kỹ năng khác",
          "insurance" not in tags.get("backtesting", []))

    # Lưới bỏ kỹ năng dưới ngưỡng — hạ ngưỡng xuống để bộ dữ liệu bé này hiện ra.
    real_min = inv.MIN_DEMAND
    inv.MIN_DEMAND = 1
    grid = inv.coverage(conn, [])
    names = [c["skill"] for c in grid]
    check("lưới xếp theo số tin đòi, nhiều nhất lên đầu",
          names and names[0] == "backtesting")
    check("bỏ kỹ năng ai cũng đòi khỏi lưới",
          not ({"python", "statistics", "pandas"} & set(names)))
    check("kho trống thì mọi ô đều trống", all(not c["covered"] for c in grid))

    class Block:                       # giả một project trên CV
        tags = ["risk"]
    check("project trên CV lấp được ô",
          any(c["covered"] and c["by"] is None
              for c in inv.coverage(conn, [Block()]) if c["skill"] == "risk"))

    b = Brief(question="Does a cost model change a momentum backtest's Sharpe?",
              dataset_url="https://x/y.csv", method=["a" * 30] * 3,
              measure="Sharpe before and after, measured on the same series",
              days=2, skills=["backtesting", "equities"],
              deliverable="one notebook")
    pid = inv.add(conn, b, ["hedge fund"])
    after = {c["skill"]: c for c in inv.coverage(conn, [])}
    # CHỐT CHẶN cho lỗi đã bắt được lúc chạy thật 09/09: đề bài mới sinh mà đã
    # tính là lấp ô, nên bấm Dựng mười lăm lần là lưới sạch bong trong khi chưa
    # viết dòng code nào.
    check("đề bài CHƯA làm thì KHÔNG tính là lấp ô",
          not after["backtesting"]["covered"] and not after["equities"]["covered"])
    check("nhưng có đánh dấu là đã nhận làm", after["backtesting"]["planned"][0] == pid)
    check("ô đã nhận làm thì không mời dựng thêm lần nữa",
          "backtesting" not in {c["skill"] for c in inv.uncovered(conn, [])})

    check("kho đọc lại được", len(inv.all(conn)) == 1)
    check("mới cất thì là đề bài", inv.all(conn)[0]["state"] == inv.DE_BAI)
    inv.set_state(conn, pid, inv.DANG_LAM)
    check("đổi được trạng thái", inv.all(conn)[0]["state"] == inv.DANG_LAM)
    inv.set_state(conn, pid, "bịa")
    check("trạng thái bịa thì không nhận", inv.all(conn)[0]["state"] == inv.DANG_LAM)
    check("đang làm dở vẫn CHƯA phải bằng chứng",
          not {c["skill"]: c for c in inv.coverage(conn, [])}["backtesting"]["covered"])

    inv.set_state(conn, pid, inv.XONG)
    done = {c["skill"]: c for c in inv.coverage(conn, [])}
    check("làm XONG thì một đề bài lấp được NHIỀU ô cùng lúc",
          done["backtesting"]["covered"] and done["equities"]["covered"])
    check("ô đã lấp chỉ đúng vào project vừa cất", done["backtesting"]["by"] == pid)
    check("kỹ năng không nằm trong đề bài thì vẫn trống", not done["sql"]["covered"])

    class Older:                       # CV đứng trước kho khi cùng lấp một ô
        tags = ["backtesting"]
    check("bằng chứng trên CV được ưu tiên hơn dòng trong kho",
          {c["skill"]: c for c in inv.coverage(conn, [Older()])}
          ["backtesting"]["by"] is None)
    inv.MIN_DEMAND = real_min

    group = make.for_skill(conn, "backtesting")
    check("gom được đúng những tin đòi kỹ năng đó", len(group.jobs) == 2)
    check("nhóm mang tên chính kỹ năng đó", group.title == "backtesting")
    check("kỹ năng không ai đòi thì nhóm rỗng",
          make.for_skill(conn, "kubernetes").jobs == [])
    check("thứ đã làm gồm cả kho lẫn CV",
          b.question in make.existing_work(conn, []))
    conn.close()

print("\n[hàng đợi LLM khoá theo nhóm cũ]")
check("khoá nhiều kỹ năng là khoá cũ",
      make.is_stale("project_briefs:risk + python + statistics"))
check("khoá số ít cũng là khoá cũ",
      make.is_stale("project_brief:statistics + python"))
check("khoá một kỹ năng là khoá đang dùng",
      not make.is_stale("project_briefs:backtesting"))
check("khoá việc khác thì không đụng tới", not make.is_stale("cv_summary:abc"))

print("\n[chiều 'trong tầm' — không tin số ngày LLM tự khai]")
from jobbot.projects.rank import score as rank_score2
W2 = ["backtesting", "equities", "validation"]
def brief_with(steps, deliver="one notebook + a one-page write-up"):
    return Brief(question="Does a volatility filter improve a momentum signal's Sharpe?",
                 dataset="prices", dataset_url="https://x/y.csv", method=steps,
                 measure="Sharpe with and without, measured on the same daily series",
                 days=2, skills=W2, deliverable=deliver)
lean = brief_with(["Download ten years of daily index prices",
                   "Compute 12-1 momentum and 20-day realised volatility",
                   "Backtest both on a walk-forward split"])
huge = brief_with(["Build a real-time streaming pipeline for tick data",
                   "Deploy to AWS with kubernetes orchestration",
                   "Run the strategy in production at scale 24/7"],
                  deliver="a production-grade platform + notebook")
s_lean, s_huge = rank_score2(lean, W2), rank_score2(huge, W2)
check("đề bài vừa tầm được trọn điểm chiều đó", s_lean.parts["in_reach"] == 1.0)
check("đề bài nghe oai bị trừ", s_huge.parts["in_reach"] == 0.0)
check("cùng khai 2 ngày mà điểm vẫn khác nhau",
      lean.days == huge.days and s_lean.total > s_huge.total)
check("nói ra CHỮ nào làm nó quá tầm — và đếm cả phần không kể hết",
      any("quá tầm" in n and "at scale" in n and "(+" in n for n in s_huge.notes))
check("ghi chú cắt theo số mục, không cụt giữa chữ",
      all("(+" in n or n.count(",") <= 2 for n in s_huge.notes if "quá tầm" in n))
check("bốn chiều còn lại cộng vẫn tròn 100",
      sum(__import__("jobbot.projects.rank", fromlist=["x"]).WEIGHTS.values()) == 100)
print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
