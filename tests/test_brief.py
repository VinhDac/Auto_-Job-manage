"""Test CỔNG kiểm đề bài, và chặng kiểm dữ liệu.

Đề bài do khuôn trong projects/frame.py dựng chứ không do LLM sinh, nên cổng
đổi vai: từ CHẶN LLM sang KIỂM LẠI KHUÔN. Nó vẫn phải đứng đây — URL vẫn chết,
tệp vẫn đổi định dạng, khuôn vẫn mục.

    python3 tests/test_brief.py
"""

import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db
from jobbot.projects.brief import Brief, validate
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

# ---------------------------------------------------------------- feasibility

from jobbot.projects.feasible import DataCheck, inspect, judge

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

# --- tệp thật ngoài đời không sạch như tệp mẫu -------------------------------
# Cả ba tình huống dưới đây đều ĐÃ xảy ra khi chạy thật, và tình huống đầu làm
# vỡ CẢ lượt dựng đề bài chứ không phải chỉ loại một đề bài.

import io, zipfile
from jobbot.projects.feasible import _delimiter, _table_start

PREAMBLE = (b"This file was created using the 202607 CRSP database.\r\n"
            b"Missing data are indicated by -99.99.\r\n\r\n"
            b"  Average Value Weighted Returns -- Daily\r\n")
TABLE = (b",Agric,Food,Beer\r\n" + b"\r\n".join(
    f"1926{i%12+1:02d}{i%28+1:02d},0.{i},1.{i},2.{i}".encode() for i in range(300)))

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("49_Industry_Portfolios_Daily.csv", PREAMBLE + TABLE)
zipped = buf.getvalue()

def zip_fetch(body):
    """Bắt chước _fetch: lần đầu bị cắt theo Range, lần hai lấy trọn."""
    def go(_u, timeout=0, limit=96_000, ranged=True):
        return (body[:2000] if ranged else body), "application/zip", len(body)
    return go

c3 = inspect("https://x/ff.zip", fetch=zip_fetch(zipped))
check("mở được .zip (cả thư viện Fama-French chỉ có zip)", c3.kind == "csv")
check("nói rõ đã đọc tệp nào bên trong zip", "trong zip" in c3.note)
check("bỏ được phần lời tựa phía trên bảng", c3.columns[1:4] == ["Agric", "Food", "Beer"])
check("cột ngày KHÔNG TÊN vẫn nhận ra nhờ giá trị", c3.has_date)
check("không nhầm là bảng tra cứu", not c3.lookup_table)
check("đếm đúng số cột số", c3.numeric_cols == 3)
check("dùng được", c3.ok)

check("dấu phân cách Sniffer đoán bừa thì bỏ, quay về dấu phẩy",
      _delimiter("Some prose about the file\r\nMore prose here\r\na,b\r\n1,2\r\n") == ",")
check("lấy dòng NHIỀU ô nhất làm tiêu đề, không lấy câu văn lọt lưới",
      _table_start(["The rate is simple, over the days",
                    "and it compounds, across the year",
                    ",a,b,c", "1,2,3,4", "5,6,7,8", "9,1,2,3"], ",") == 2)

# Tệp đọc không ra bảng chỉ được phép loại ĐỀ BÀI ĐÓ, không được ném ra ngoài.
junk = b"PKnot-a-zip\x00\x01" + b'"unclosed\nquote,\n' * 500
c4 = inspect("https://x/junk.csv", fetch=lambda _u, timeout=0, limit=0, ranged=True:
             (junk, "text/csv", len(junk)))
check("tệp đọc không nổi -> báo lỗi, KHÔNG ném ngoại lệ", not c4.ok and c4.problems)

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

print("\n[ba luật cũ giờ là CỔNG, không phải thước]")
def gate(b, seen=()):
    return {p.field for p in validate(b, WANTED, list(seen), YES)}

check("câu hỏi không bác bỏ được -> LOẠI, không phải trừ điểm",
      "question" in gate(broken(question="An analysis of market data using ML.")))
check("bài mẫu phổ biến -> LOẠI",
      "dataset" in gate(broken(question="Does the Titanic dataset predict survival?",
                               dataset="titanic")))
check("trùng project cũ -> LOẠI",
      "question" in gate(broken(), seen=["How much does a random split inflate "
                                         "out-of-sample Sharpe"]))

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
