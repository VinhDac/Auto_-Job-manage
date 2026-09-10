"""Test bước 3 — dựng CV theo từng JD.  python3 tests/test_cv.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.cv import rules
from jobbot.cv.blocks import parse, sentences
from jobbot.cv.build import build

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

CV = """DAC VINH NGUYEN
London, UK · +44 7454 070297 · me@example.com
Eligible for UK Graduate visa — no employer sponsorship required.
I want to work on interesting problems.
EXPERIENCE
Founder / Quantitative Developer — Trading Startup Jan 2026 – Present
Self-funded, across 17 instruments and five years of data. I designed and built two
systems in Python: signals, validation and risk. I was optimising for peak profit in the
most recent window — which rewards luck. A random train/test split leaks, because
adjacent dates are correlated. Live drawdown ran roughly 30% deeper than the model
predicted. The mistake was mine.
Research Consultant — WorldQuant Jan 2025 – Sep 2025
Generated systematic alpha signals in Python, scored on Sharpe ratio and drawdown.
I trained deep learning models in PyTorch on five years of tick data.
I built portfolio construction on the efficient frontier with explicit risk limits.
I wrote backtesting and walk-forward validation harnesses in pandas and NumPy.
Profit on its own means nothing: an edge can be faked.
SELECTED PROJECTS
Quant Trading Studio — the whole pipeline you can run: backtesting and risk budgeting.
EDUCATION
MSc Computational Finance — Royal Holloway 2025 – 2026
Deep Learning 83 · Data Analysis 83
Certifications — CFA Level I, top 10% of global candidates
TECHNICAL SKILLS
Programming — Python (pandas, NumPy, PyTorch), C++, SQL.
Compute — a GPU is fast at many simple operations at once.
Method — I direct Claude Code and Copilot rather than prompt them.
"""

PROFILE = {"cv_text": CV, "full_name": "Dac Vinh Nguyen", "email": "me@example.com",
           "location": "London, UK", "skills_strong": "Python, pandas, PyTorch, C++, SQL",
           "education": "MSc Computational Finance — Royal Holloway 2025-2026",
           "certifications": "CFA Level I, top 10% of global candidates"}

print("\n[tách khối]")
bs = parse(CV)
kinds = [b.kind for b in bs]
check("nhận ra đủ loại khối", {"header", "experience", "project", "education", "skill"} <= set(kinds))
exp = [b for b in bs if b.kind == "experience"]
check("đúng 2 vai trò, không bị câu có gạch ngang xé đôi", len(exp) == 2)
check("đọc được ngày tháng", exp[0].meta == "Jan 2026 – Present")
check("tách nhóm kỹ năng riêng", len([b for b in bs if b.kind == "skill"]) == 3)

joined = sentences(exp[0])
check("nối lại dòng PDF bị ngắt giữa câu",
      any("adjacent dates are correlated" in s for s in joined))

print("\n[luật — phân biệt kiến thức với thất bại]")
keep_cases = [
    "A random train/test split leaks, because adjacent dates are correlated",
    "I designed and built two systems in Python: signals, validation and risk",
]
drop_cases = [
    "Live drawdown ran roughly 30% deeper than the model predicted",
    "The mistake was mine: the regime split was a valid partition",
    "I never budgeted the time a proof would take, and the capital ran out",
    "Profit on its own means nothing: an edge can be faked",
]
for text in keep_cases:
    check(f"GIỮ kiến thức: {text[:40]}…", rules.sentence_ok(text)[0] == "keep")
for text in drop_cases:
    check(f"BỎ thất bại: {text[:40]}…", rules.sentence_ok(text)[0] == "drop")

verdict, why = rules.sentence_ok("Self-funded, across 17 instruments and five years of data")
check("câu nhạy cảm NHƯNG có số -> đánh dấu xem lại, không vứt", verdict == "review")
check("và nói rõ vì sao", "your call" in why)
check("bỏ chữ nút bấm dính đầu câu",
      rules.clean("Demo MetaTrader's backtester only measures edge").startswith("MetaTrader"))

print("\n[dựng CV]")
JD_ML = {"requirements": [{"text": "Strong Python and PyTorch for deep learning", "met": True,
                           "must": True, "evidence": ""}]}
JD_RISK = {"requirements": [{"text": "Portfolio construction and risk management", "met": True,
                             "must": True, "evidence": ""}]}
ml = build(PROFILE, JD_ML, "deep learning pytorch python")
risk = build(PROFILE, JD_RISK, "portfolio risk management")

def top_of(cv, title_part):
    section = next(s for s in cv.sections if title_part in s.title)
    return section.lines[0].text.lower()

check("JD deep learning -> dòng đầu nói về PyTorch/deep learning",
      "pytorch" in top_of(ml, "WorldQuant") or "deep learning" in top_of(ml, "WorldQuant"))
check("JD risk -> dòng đầu nói về portfolio/risk",
      "risk" in top_of(risk, "WorldQuant") or "portfolio" in top_of(risk, "WorldQuant"))
check("hai JD khác nhau -> thứ tự khác nhau",
      [l.text for s in ml.sections for l in s.lines] !=
      [l.text for s in risk.sections for l in s.lines])

all_text = " ".join(l.text for s in ml.sections for l in s.lines)
check("KHÔNG bịa: mọi câu đều có trong CV gốc",
      all(line.strip()[:40] in CV.replace("\n", " ") for s in ml.sections
          for l in s.lines if s.kind in ("experience", "project")
          for line in [l.text]))
check("không đưa thất bại lên CV", "mistake was mine" not in all_text)
check("không đưa ý kiến lên CV", "means nothing" not in all_text)

skill_titles = [s.title for s in ml.sections if s.kind == "skill"]
check("bỏ phần Compute", "Compute" not in skill_titles)
check("bỏ phần Method", "Method" not in skill_titles)
check("giữ phần Programming", "Programming" in skill_titles)

check("có ghi lại những câu đã bỏ", len(ml.dropped) >= 4)
check("mỗi câu bỏ đều kèm lý do", all(why for _, why in ml.dropped))
check("tóm tắt ghép từ sự thật, không viết mới",
      "MSc Computational Finance" in ml.summary and "CFA Level I" in ml.summary)

print("\n[thiếu kỹ năng — danh sách 'hoặc']")
JD_OR = {"requirements": [{"text": "Programming in any of: C++, Java, MATLAB, R or Python",
                           "met": True, "must": True, "evidence": ""}]}
either = build(PROFILE, JD_OR, "C++ Java MATLAB R Python")
check("có C++/Python rồi thì Java/MATLAB/R KHÔNG tính là thiếu",
      not ({"java", "matlab", "r"} & set(either.missing)))

JD_GAP = {"requirements": [{"text": "Experience with equities and derivatives pricing",
                            "met": False, "must": True, "evidence": ""}]}
gap = build(PROFILE, JD_GAP, "equities derivatives")
check("thiếu thật thì vẫn báo", {"equities", "derivatives"} & set(gap.missing))


print("\n[soạn khối — sửa một khối, mọi khối khác NGUYÊN VẸN]")
from jobbot.cv.blocks import write_block

CV_IN = PROFILE["cv_text"]
base = [(b.kind, b.title, b.meta) for b in parse(CV_IN)]
check("hồ sơ mẫu có khối để sửa", len(base) >= 3)

for blk in parse(CV_IN):
    if blk.kind not in ("experience", "project"):
        continue
    out = write_block(CV_IN, blk.kind, blk.title, blk.meta, ["I built a walk-forward tester across 17 instruments.",
                        "Live drawdown ran 30% deeper than the model said."])
    got = [(b.kind, b.title, b.meta) for b in parse(out)]
    # BẤT BIẾN: đây là chỗ dễ hỏng nhất. parse() nhận ra khối mới bằng HÌNH
    # DẠNG dòng tiêu đề — project cần " — ", kinh nghiệm cần đuôi ngày tháng.
    # Ghi sai hình dạng thì khối bị nuốt vào khối trước và BIẾN MẤT; ghi mà
    # không định vị được thì đẻ thêm một khối trùng tên.
    check(f"[{blk.kind}] {blk.title[:26]} — danh sách khối không đổi", got == base)
    again = [b for b in parse(out) if b.title == blk.title]
    check(f"[{blk.kind}] {blk.title[:26]} — đọc lại đúng nội dung mới",
          bool(again) and again[0].lines == ["I built a walk-forward tester across 17 instruments.",
                        "Live drawdown ran 30% deeper than the model said."])

fresh = write_block(CV_IN, "project", "Regime Detector", "", ["I built a walk-forward tester across 17 instruments.",
                        "Live drawdown ran 30% deeper than the model said."])
made = [b for b in parse(fresh) if b.title == "Regime Detector"]
check("khối mới thêm được", bool(made))
check("khối mới nằm đúng mục project", bool(made) and made[0].kind == "project")
check("thêm khối KHÔNG đụng khối cũ",
      all(x in [(b.kind, b.title, b.meta) for b in parse(fresh)] for x in base))
check("khối mới vào được chỉ số bằng chứng ngay",
      any("Regime Detector" in e.where
          for e in __import__("jobbot.scoring.score", fromlist=["x"])
          .build_index({**PROFILE, "cv_text": fresh})))

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
