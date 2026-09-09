"""Test tách 'khớp' khỏi 'có cửa'.  python3 tests/test_realism.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.scoring.realism import assess, find_deadline

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

GRAD = {"years_real": "0-1"}
MID = {"years_real": "3-5"}
LONG = "x" * 400

print("\n[có cửa hay không]")
cases = [
    ("Graduate Analyst", "Our graduate programme welcomes final-year students. " + LONG,
     GRAD, "likely"),
    ("Quantitative Researcher", "A PhD is required in a quantitative field. " + LONG,
     GRAD, "unlikely"),
    ("Quantitative Analyst", "You will need 7+ years of experience. " + LONG,
     GRAD, "unlikely"),
    ("Senior Data Scientist", "Join our team building models. " + LONG, GRAD, "unlikely"),
    ("Data Analyst", "You will build dashboards and reports. " + LONG, GRAD, "possible"),
]
for title, text, profile, want in cases:
    got = assess(title, text, None, profile)["band"]
    check(f"{want:9} ← {title[:34]}", got == want)

check("cùng tin, người có 5 năm thì cửa rộng hơn người mới ra trường",
      assess("Quant Analyst", "Requires 4+ years of experience. " + LONG, None, MID)["score"]
      > assess("Quant Analyst", "Requires 4+ years of experience. " + LONG, None, GRAD)["score"])

print("\n[không đoán bừa]")
blank = assess("Analyst", "", None, GRAD)
check("không có mô tả -> 'unknown'", blank["band"] == "unknown")
check("và nói rõ vì sao", "no description" in blank["why"])
check("mô tả quá ngắn cũng 'unknown'",
      assess("Analyst", "Join us!", None, GRAD)["band"] == "unknown")

print("\n[luôn giải thích được]")
phd = assess("Quant Researcher", "A PhD is required here. " + LONG, None, GRAD)
check("nêu lý do PhD", "PhD" in phd["why"])
yrs = assess("Quant Analyst", "We need 6+ years experience. " + LONG, None, GRAD)
check("nêu số năm cụ thể", "6+" in yrs["why"] and "0.5" in yrs["why"])
grad = assess("Graduate Analyst", "Our graduate programme. " + LONG, None, GRAD)
check("nêu lý do có cửa", "graduate" in grad["why"].lower())

print("\n[hạn nộp]")
for text, want in [
    ("Applications close 15 November 2026.", "15 November 2026"),
    ("Deadline: 2026-11-30 for all candidates.", "2026-11-30"),
    ("Apply by 01/12/2026 please.", "01/12/2026"),
]:
    got, ts = find_deadline(text)
    check(f"đọc được '{want}'", got == want and ts > 0)
check("không có hạn -> rỗng", find_deadline("We hire all year round.") == ("", 0))
check("không nhặt bừa ngày khác",
      find_deadline("Founded in 2015, we now have 400 staff.")[0] == "")

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
