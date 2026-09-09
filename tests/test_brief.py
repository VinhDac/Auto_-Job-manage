"""Test sinh đề bài project — chủ yếu test BỘ KIỂM TRA.

Không test được LLM sáng tạo hay dở. Test được: đề bài không đạt chuẩn thì
KHÔNG BAO GIỜ lọt qua. Đó mới là thứ giữ chất lượng.

    python3 tests/test_brief.py
"""

import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db, llm
from jobbot.projects.brief import (Brief, build_prompt, generate, parse_brief,
                                   validate)
from jobbot.projects.research import Findings

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

WANTED = ["python", "backtesting", "validation", "statistics", "time series"]
YES = lambda _u: True          # giả lập URL sống, không đụng mạng trong test
NO = lambda _u: False

GOOD = Brief(
    question="Does a random train/test split inflate out-of-sample Sharpe on UK equities?",
    answers_jd="statistical modelling and validation",
    dataset="FTSE 350 daily closes",
    dataset_url="https://example.com/ftse.csv",
    method=["Build 40 momentum signals on ten years of daily closes",
            "Score each one with a random split and with a time-ordered split",
            "Compare the two out-of-sample Sharpe distributions across all 40"],
    measure="Mean out-of-sample Sharpe under each split, measured across 40 signals",
    days=2, skills=["python", "backtesting", "validation"],
    deliverable="one notebook plus a one-page write-up")

def broken(**kw):
    from dataclasses import replace
    return replace(GOOD, **kw)

print("\n[đề bài tốt thì qua]")
check("không lỗi nào", validate(GOOD, WANTED, [], YES) == [])

print("\n[câu hỏi]")
check("không phải câu hỏi -> chặn",
      any(p.field == "question" for p in validate(broken(question="Test momentum signals."), WANTED, [], YES)))
check("dài lê thê -> chặn",
      any(p.field == "question" for p in validate(broken(question="?" * 300), WANTED, [], YES)))

print("\n[dữ liệu phải CÓ THẬT — hàng rào mạnh nhất]")
check("URL không truy cập được -> chặn",
      any(p.field == "dataset_url" for p in validate(GOOD, WANTED, [], NO)))
check("thiếu URL -> chặn",
      any(p.field == "dataset_url" for p in validate(broken(dataset_url=""), WANTED, [], YES)))
check("URL không phải http -> chặn",
      any(p.field == "dataset_url" for p in validate(broken(dataset_url="my_local_file.csv"),
                                                     WANTED, [], YES)))

print("\n[cách làm]")
check("2 bước -> chặn", any(p.field == "method" for p in
      validate(broken(method=GOOD.method[:2]), WANTED, [], YES)))
check("bước rỗng tuếch không tính",
      any(p.field == "method" for p in validate(broken(method=["a", "b", "c", "d"]), WANTED, [], YES)))
check("9 bước -> quá to, chặn",
      any(p.field == "method" for p in validate(broken(method=GOOD.method * 3), WANTED, [], YES)))

print("\n[số đo phải kèm CÁCH ĐO]")
check("số đo không có số -> chặn",
      any(p.field == "measure" for p in
          validate(broken(measure="It performs better overall, measured across runs"), WANTED, [], YES)))
check("có số nhưng KHÔNG nói cách đo -> chặn",
      any(p.field == "measure" for p in
          validate(broken(measure="Sharpe goes from 0.7 to 1.2"), WANTED, [], YES)))
check("có cả hai -> qua", validate(GOOD, WANTED, [], YES) == [])

print("\n[kích thước]")
for days, want in [(0.5, True), (3, True), (5, False), (0, False), (14, False)]:
    passed = not any(p.field == "days" for p in validate(broken(days=days), WANTED, [], YES))
    check(f"{days:g} ngày -> {'nhận' if want else 'chặn'}", passed == want)

print("\n[phải chạm đúng thứ nhóm JD đòi]")
check("chỉ chạm 1 kỹ năng -> chặn",
      any(p.field == "skills" for p in
          validate(broken(skills=["python", "cooking"]), WANTED, [], YES)))
check("chạm 3 kỹ năng -> qua",
      not any(p.field == "skills" for p in validate(GOOD, WANTED, [], YES)))
check("kỹ năng đúng nhưng nhóm không đòi -> chặn",
      any(p.field == "skills" for p in validate(GOOD, ["kubernetes", "terraform"], [], YES)))

print("\n[không trùng project đã có]")
dup = ["Does a random train/test split inflate out-of-sample Sharpe on UK equities"]
check("trùng project cũ -> chặn",
      any("trùng project" in p.why for p in validate(GOOD, WANTED, dup, YES)))
check("project cũ khác hẳn -> qua",
      validate(GOOD, WANTED, ["A dashboard of London house prices"], YES) == [])

print("\n[nộp cái gì]")
check("không nói nộp gì -> chặn",
      any(p.field == "deliverable" for p in validate(broken(deliverable="something nice"),
                                                     WANTED, [], YES)))

print("\n[bóc JSON khỏi câu trả lời]")
check("JSON thuần", parse_brief('{"question":"a?","days":2}').question == "a?")
check("JSON bọc trong chữ",
      parse_brief('Sure! Here it is:\n{"question":"b?","days":1}\nHope that helps')
      .question == "b?")
check("không phải JSON -> None", parse_brief("xin lỗi tôi không làm được") is None)
check("JSON hỏng -> None", parse_brief('{"question": ') is None)
check("bỏ trường lạ", parse_brief('{"question":"c?","hack":"rm -rf"}').question == "c?")
check("days không phải số -> 0", parse_brief('{"question":"d?","days":"hai"}').days == 0.0)

print("\n[luồng sinh]")
F = Findings(cluster="quant", jobs=6,
             core_needs=[("Strong Python and validation", 3), ("Time series", 2)],
             concepts=[("backtesting", 5)], data_named=[("market data", 3)],
             companies=["Man Group"], skills=WANTED)
prompt = build_prompt(F, ["Quant Trading Studio"])
check("prompt có yêu cầu thật của nhóm", "Strong Python and validation" in prompt)
check("prompt cấm lặp project cũ", "Quant Trading Studio" in prompt)
check("prompt ép giới hạn 3 ngày", "3 days" in prompt)
check("prompt đòi URL thật", "working URL" in prompt)

with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "b.db")
    thin = Findings(cluster="x", jobs=1, core_needs=[])
    check("nhóm quá mỏng -> KHÔNG sinh bừa",
          generate(conn, thin, [], YES)["state"] == "not_enough")

    import os
    os.environ["JOBBOT_LLM"] = "none"
    check("không có LLM -> nói thẳng, không bịa đề bài",
          generate(conn, F, [], YES)["state"] == "no_llm")

    os.environ["JOBBOT_LLM"] = "claude_code"
    first = generate(conn, F, [], YES)
    check("claude_code -> xếp hàng chờ", first["state"] == "pending")
    check("và ghi lại yêu cầu", len(llm.pending(conn)) == 1)

    req = llm.pending(conn)[0]
    llm.answer_request(conn, req["id"], '{"question":"Too vague","days":30}')
    bad = generate(conn, F, [], YES)
    check("đề bài tệ -> BỊ TỪ CHỐI, không lọt", bad["state"] == "rejected")
    check("và nêu đủ lý do", len(bad["problems"]) >= 4)
    conn.close()
    os.environ.pop("JOBBOT_LLM", None)


# ---------------------------------------------------------------- feasibility

from jobbot.projects.feasible import DataCheck, inspect, judge
from jobbot.projects.rank import score as rank_score
from jobbot.projects.pipeline import _parse_many, run

def fake_fetch(body: bytes, ctype="text/csv", size=None):
    return lambda _u, timeout=0: (body, ctype, size)

print("\n[kiểm DỮ LIỆU — nhìn vào bên trong, không chỉ hỏi máy chủ]")
series = b"DATE,OPEN,CLOSE\n" + b"\n".join(
    f"2020-01-{i%28+1:02d},10.{i},11.{i}".encode() for i in range(300))
c = inspect("https://x/y.csv", fetch=fake_fetch(series, size=400000))
check("nhận ra chuỗi thời gian", c.has_date and c.date_cols == ["DATE"])
check("nhận ra cột giá", set(c.price_cols) == {"OPEN", "CLOSE"})
check("KHÔNG phải bảng tra cứu", not c.lookup_table)
check("dùng được", c.ok)

lookup = (b"Symbol,Security,Sector,Date added,CIK\n" +
          b"\n".join(f"S{i},Name{i},Tech,2015-01-01,{i}".encode() for i in range(300)))
c2 = inspect("https://x/z.csv", fetch=fake_fetch(lookup, size=30000))
check("'Date added' KHÔNG tính là trục thời gian", not c2.has_date)
check("nhận ra là bảng tra cứu", c2.lookup_table)

B = lambda: Brief(question="How much does survivorship bias inflate momentum returns?",
                  dataset_url="https://x/z.csv", method=["a"*30]*3,
                  measure="Sharpe difference measured over 20 years", days=2,
                  skills=["python"], deliverable="notebook")
probs = judge(B(), c2)
check("bảng tra cứu -> từ chối đề bài chuỗi thời gian", len(probs) >= 3)
check("nói rõ 'Date added' là siêu dữ liệu",
      any("siêu dữ liệu" in p for p in probs))
check("nói rõ thiếu cột giá", any("giá/lợi suất" in p for p in probs))
check("chuỗi thật -> không lỗi nào", judge(B(), c) == [])

html = b"<!doctype html><html><body>Sign in</body></html>"
c3 = inspect("https://x/page", fetch=fake_fetch(html, "text/html"))
check("trang web -> chặn", not c3.ok and c3.kind == "html")
check("URL không http -> chặn", not inspect("file.csv").ok)

print("\n[xếp hạng]")
W = ["python", "backtesting", "validation"]
GOODQ = Brief(question="How much does a random split inflate out-of-sample Sharpe?",
              method=["Build 40 momentum signals on daily closes",
                      "Score each with a random and a time-ordered split",
                      "Compare Sharpe across all 40 signals"],
              days=1, skills=["python", "backtesting", "validation"])
WEAKQ = Brief(question="An analysis of market data using machine learning.",
              method=["Explore the data", "Clean the data", "Build a model"],
              days=5, skills=["python"])
s_good, s_weak = rank_score(GOODQ, W, [], []), rank_score(WEAKQ, W, [], [])
check("đề bài tốt hơn hẳn đề bài yếu", s_good.total > s_weak.total + 30)
check("câu hỏi không bác bỏ được -> 0 điểm chiều đó",
      s_weak.parts["falsifiable"] == 0.0)
check("bước chung chung -> điểm cụ thể thấp", s_weak.parts["concrete"] < 0.3)
check("dữ liệu hỏng -> mất điểm data_ready",
      rank_score(GOODQ, W, ["bảng tra cứu"], []).parts["data_ready"] == 0.0)
check("bài mẫu phổ biến -> mất điểm mới",
      rank_score(Brief(question="Does the Titanic dataset predict survival?",
                       dataset="titanic", method=["x"], days=1, skills=W),
                 W, [], []).parts["novel"] == 0.0)
check("trùng project cũ -> mất điểm mới",
      rank_score(GOODQ, W, [], ["random split inflate out-of-sample Sharpe"])
      .parts["novel"] == 0.0)

print("\n[bóc nhiều phương án]")
check("mảng JSON", len(_parse_many('[{"question":"a?"},{"question":"b?"}]')) == 2)
check("object rời", len(_parse_many('{"question":"a?"}\n{"question":"b?"}')) == 2)
check("rác -> rỗng", _parse_many("sorry") == [])

print("\n[luồng đầy đủ]")
import json as _json, os as _os
with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "p.db")
    F2 = Findings(cluster="quant", jobs=8,
                  core_needs=[("Strong Python and validation", 3)],
                  concepts=[("backtesting", 5)], companies=["Man Group"],
                  skills=["python", "backtesting", "validation"])
    _os.environ["JOBBOT_LLM"] = "claude_code"
    first = run(conn, F2, [])
    check("chưa có câu trả lời -> chờ", first.state == "pending")

    req = llm.pending(conn)[0]
    llm.answer_request(conn, req["id"], _json.dumps([
        {"question": "An analysis of markets.", "dataset_url": "https://x/a.csv",
         "method": ["Explore"], "measure": "good", "days": 9,
         "skills": ["python"], "deliverable": "notebook"},
        {"question": "How much does a random split inflate out-of-sample Sharpe?",
         "dataset_url": "https://x/b.csv",
         "method": ["Build 40 momentum signals on daily closes",
                    "Score each with a random and a time-ordered split",
                    "Compare Sharpe across all 40 signals"],
         "measure": "Mean Sharpe under each split, measured across 40 signals",
         "days": 2, "skills": ["python", "backtesting", "validation"],
         "deliverable": "one notebook plus a write-up"}]))
    out = run(conn, F2, [], check_url=YES,
              inspect=lambda _u: inspect("https://x/y.csv", fetch=fake_fetch(series, size=400000)))
    check("chọn được đề bài tốt", out.state == "ok")
    check("chọn ĐÚNG cái tốt, không phải cái đầu tiên",
          "random split" in out.chosen.question)
    check("giữ lại cái bị loại kèm lý do", len(out.rejected) == 1)
    check("cái bị loại có nêu lỗi", len(out.rejected[0][1]) > 0)
    conn.close()
    _os.environ.pop("JOBBOT_LLM", None)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
