"""Test bước 2 — chấm điểm khớp.  python3 tests/test_scoring.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.scoring import extract
from jobbot.scoring.score import _degrees_needed, _years_needed, build_index, score_job

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

PROFILE = {
    "job_titles": "Quantitative Analyst\nData Scientist",
    "seniority": ["grad", "junior"],
    "years_real": "0-1",
    "education": "MSc Computational Finance — Royal Holloway, 2026\nBA Finance, GPA 3.59",
    "certifications": "CFA Level I — top 10% of global candidates",
    "skills_strong": "Python, pandas, SQL",
    "search_keywords": "machine learning, backtesting",
}

JD = """About the role
We do things.

Requirements:
· Strong knowledge of Python and pandas
· Degree in a quantitative discipline
· 5+ years of commercial experience
· Exceptional communication skills

Nice to have:
· Experience with kdb+

What we offer
· 25 days holiday
· Private healthcare
"""

print("\n[tách yêu cầu]")
reqs = extract.requirements(JD)
texts = [r.text for r in reqs]
check("lấy được gạch đầu dòng", len(reqs) == 5)
check("bỏ phần phúc lợi", not any("holiday" in t or "healthcare" in t for t in texts))
check("nhận ra điểm cộng", any(t.startswith("Experience with kdb") and not r.must
                               for t, r in zip(texts, reqs)))
check("còn lại là bắt buộc", sum(1 for r in reqs if r.must) == 4)
check("độ tin cậy cao khi có gạch đầu dòng", extract.confidence(reqs) == "high")
check("JD rỗng -> không chấm được", extract.confidence(extract.requirements("")) == "none")

prose = ("We are a research firm. If you have experience in time series analysis "
         "and knowledge of Python we would like to hear from you. "
         "You will have 25 days holiday and private healthcare.")
preqs = extract.requirements(prose)
check("văn xuôi vẫn nhặt được yêu cầu", len(preqs) >= 1)
check("văn xuôi -> độ tin cậy thấp", extract.confidence(preqs) == "low")
check("văn xuôi vẫn bỏ câu phúc lợi",
      not any("holiday" in r.text for r in preqs))

print("\n[bằng cấp — lỗi đã sửa]")
check("'MS or PhD' nhận CẢ HAI, không chỉ cái cao nhất",
      set(_degrees_needed("Undergraduate, MS, or PhD candidates")) >= {"phd", "masters"})
check("'PhD required' chỉ ra PhD", _degrees_needed("PhD required") == ["phd"])
check("'database' KHÔNG bị nhận là bằng BA", _degrees_needed("experience with databases") == [])
check("'systems' KHÔNG bị nhận là MS", "masters" not in _degrees_needed("distributed systems"))

print("\n[số năm]")
check("đọc được '5+ years'", _years_needed("5+ years of experience") == 5)
check("đọc được '3-5 years'", _years_needed("3-5 years required") == 3)
check("không có năm -> None", _years_needed("Strong Python") is None)

print("\n[bằng chứng mạnh / yếu]")
index = build_index(PROFILE)
labels = [e.where for e in index]
check("kỹ năng mạnh đứng trước từ khoá", labels.index("your strong skills") < labels.index(
    "a keyword you set (not proof)"))
check("từ khoá bị đánh dấu là yếu",
      not next(e for e in index if "keyword" in e.where).strong)

print("\n[chấm điểm]")
result = score_job("Graduate Quantitative Analyst", JD, PROFILE)
by_text = {r["text"]: r for r in result["requirements"]}
check("Python có trong hồ sơ -> đạt",
      by_text["Strong knowledge of Python and pandas"]["met"] is True)
check("bằng cấp định lượng -> đạt",
      by_text["Degree in a quantitative discipline"]["met"] is True)
check("5+ năm mà mới 0-1 -> trượt",
      by_text["5+ years of commercial experience"]["met"] is False)
check("kỹ năng mềm -> KHÔNG phán (không tính vào mẫu số)",
      by_text["Exceptional communication skills"]["met"] is None)
check("bằng chứng trích từ hồ sơ thật",
      "Python" in by_text["Strong knowledge of Python and pandas"]["evidence"])
check("thiếu số năm -> chặn trần 55", result["score"] <= 55 and result["capped"])
check("có nêu dòng chặn", len(result["blockers"]) == 1)
check("điểm cộng cách biệt với bắt buộc", result["breakdown"]["nice"]["total"] == 1)

soft = score_job("Graduate Quantitative Analyst",
                 JD.replace("· 5+ years of commercial experience\n", ""), PROFILE)
check("bỏ yêu cầu số năm thì điểm vọt lên", soft["score"] > result["score"])
check("nhắm junior mà tin ghi Senior -> trừ nặng",
      score_job("Senior Quantitative Analyst", JD, PROFILE)["breakdown"]["level"]["points"] == 0)
check("tin ghi Graduate -> cộng đủ", soft["breakdown"]["level"]["points"] == 20)

blank = score_job("Analyst", "We are a great company. Join us.", PROFILE)
check("JD không có yêu cầu -> KHÔNG bịa điểm", blank["score"] is None)
check("và nói rõ vì sao", "Could not read" in blank["reason"])

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
