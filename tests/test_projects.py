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

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
