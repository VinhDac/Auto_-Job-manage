"""Phần nộp — sổ trả lời, phân giỏ, so khớp, và RANH GIỚI.

Mọi con số trong tệp này đến từ form THẬT (Point72/Greenhouse, cohere/Ashby,
zopa/Lever), không phải từ tưởng tượng. Mỗi lỗi từng xảy ra một lần đều để
lại đúng một ca ở đây.

    python3 tests/test_apply.py
"""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.apply import fields as F, run
from jobbot.apply.answer import Ans, LEVEL_WORDS, book, education

ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ok   {name}")
    else:
        fail += 1
        print(f"  FAIL {name}{' — ' + extra if extra else ''}")


VIN = {
    "full_name": "Dac Vinh Nguyen",
    "email": "davin.work268@gmail.com",
    "phone": "+44 7454 070297",
    "location": "London, UK",
    "links": "https://vinhdac.github.io\nLinkedIn\nGitHub",
    "education": ("MSc Computational Finance — Royal Holloway, University of "
                  "London, 2025–2026\n  Investment 86\n\nBA (Hons) Advanced "
                  "Finance — National Economics University, Vietnam"),
}

print("\n== sổ trả lời ==")
edu = education(VIN["education"])
check("học vị", edu.degree == "MSc" and edu.level == "master", edu.degree)
check("ngành", edu.discipline == "Computational Finance", edu.discipline)
check("trường", edu.school == "Royal Holloway, University of London", edu.school)
check("năm", (edu.start_year, edu.end_year) == (2025, 2026), str(edu.start_year))
check("thiếu tháng thì NÓI ra", any("tháng" in m for m in edu.missing), str(edu.missing))
check("lấy bằng MỚI NHẤT, không phải bằng đầu", "Royal Holloway" in edu.school)

edu2 = education("MSc Data Science — Imperial College, Sep 2025 – Sep 2026")
check("đọc được tháng khi hồ sơ có ghi",
      (edu2.start_month, edu2.end_month) == (9, 9) and not edu2.missing,
      str(edu2.missing))

b = book(VIN)
# Lỗi thật: cắt theo tiếng ĐẦU thì họ thành "Vinh Nguyen".
check("họ là tiếng cuối cùng", b["last_name"].value == "Nguyen", b["last_name"].value)
check("tên gọi là phần còn lại", b["first_name"].value == "Dac Vinh", b["first_name"].value)
check("nước suy ra từ nơi ở", b["country"].value == "United Kingdom", b["country"].value)
# Hồ sơ ghi trần chữ "LinkedIn" — đó là nhãn, không phải địa chỉ.
check("không nhận chữ 'LinkedIn' làm URL", not b["linkedin"].value, b["linkedin"].value)
check("website là URL thật", b["website"].value.startswith("https://"), b["website"].value)
check("thiếu thì để RỖNG, không bịa", not b["edu_end_month"].value)

print("\n== phân giỏ ==")
CASES = [
    # (nhãn, tên ô, kiểu, giỏ mong đợi, khoá mong đợi)
    ("First Name *", "first_name", "text", F.FILL, "first_name"),
    ("Last Name", "last_name", "text", F.FILL, "last_name"),
    ("Email", "email", "email", F.FILL, "email"),
    ("Resume/CV", "resume", "file", F.FILL, "resume"),
    ("School*", "school--0", "combo", F.FILL, "school"),
    ("Degree*", "degree--0", "combo", F.FILL, "degree"),
    ("End date year*", "end-year--0", "number", F.FILL, "edu_end_year"),
    ("End date month*", "end-month--0", "combo", F.FILL, "edu_end_month"),
    ("LinkedIn URL", "urls[LinkedIn]", "text", F.FILL, "linkedin"),
    ("GitHub URL", "urls[GitHub]", "text", F.FILL, "github"),
    # Ba câu KHÔNG được đoán — sai là hỏng đơn.
    ("Will you now or in the future require sponsorship?", "q1", "combo", F.ASK, None),
    ("What is your current cumulative GPA?", "question_68932242", "text", F.ASK, None),
    ("Will you graduate from January 2028-Summer 2028?", "q3", "combo", F.ASK, None),
    ("Expected salary", "q4", "text", F.ASK, None),
    ("I agree to the privacy policy", "consent", "checkbox", F.ASK, None),
    ("Cover Letter", "cover_letter", "file", F.ASK, None),
    ("", "opportunityLocationId", "text", F.ASK, None),
    # Đặc điểm được bảo vệ — không chạm, dù form bắt buộc.
    ("Gender", "gender", "combo", F.SKIP, None),
    ("Are you Hispanic/Latino?", "hispanic", "combo", F.SKIP, None),
    ("Race", "race", "combo", F.SKIP, None),
    ("Veteran Status", "veteran", "combo", F.SKIP, None),
    ("Have you served in the military?*", "q5", "combo", F.SKIP, None),
    ("Disability Status", "disability", "combo", F.SKIP, None),
    ("She/her", "pronouns", "checkbox", F.SKIP, None),
]
for label, name, kind, want_bucket, want_key in CASES:
    got_bucket, got_key = F.classify(
        {"label": label, "name": name, "dom_id": "", "kind": kind})
    fine = got_bucket == want_bucket and (want_key is None or got_key == want_key)
    check(f"{want_bucket:<4} {(label or name)[:44]}", fine, f"ra {got_bucket}/{got_key}")

check("mọi luật HỎI đều kèm lý do",
      all(reason.strip() for _, reason in F.ASK_RULES))
check("không luật nào vừa ĐIỀN vừa HỎI",
      not {k for _, k in F.FILL_RULES} & {"gpa", "sponsor", "salary"})

print("\n== gộp nhóm và ô bóng ==")
raw = [
    {"k": 0, "name": "", "dom_id": "first_name", "kind": "text", "label": "First Name",
     "option": "", "group": "", "required": True, "options": [], "value": ""},
    # 4 ô đánh dấu CÙNG name = MỘT câu hỏi, không phải bốn.
    *[{"k": i, "name": "question_271[]", "dom_id": "", "kind": "checkbox",
       "label": "Preferred office", "option": city, "group": "question_271[]",
       "required": True, "options": [], "value": ""}
      for i, city in enumerate(["London", "Paris", "Hong Kong", "Tokyo"], start=1)],
]


class FakeTab:
    def __init__(self, payload):
        self.payload = payload

    def eval(self, _js, timeout=30.0):
        import json
        return json.dumps(self.payload)


folded = F.read(FakeTab(raw))
check("4 ô đánh dấu gộp thành 1 câu", len(folded) == 2, f"ra {len(folded)}")
check("giữ đủ 4 lựa chọn",
      folded[1]["options"] == ["London", "Paris", "Hong Kong", "Tokyo"],
      str(folded[1]["options"]))

print("\n== so khớp danh sách ==")
DEG = ["Bachelor's Degree", "Master of Business Administration (M.B.A.)",
       "Master's Degree", "Doctorate"]
check("MSc -> Master's Degree, KHÔNG phải MBA",
      run.match(Ans("MSc", LEVEL_WORDS["master"]), DEG) == "Master's Degree",
      run.match(Ans("MSc", LEVEL_WORDS["master"]), DEG))
check("MBA vẫn ra MBA",
      run.match(Ans("MBA", LEVEL_WORDS["mba"]), DEG).startswith("Master of Business"))
check("UK không thành Ukraine",
      run.match(Ans("United Kingdom", ("GB", "UK")),
                ["Ukraine", "United Kingdom", "United Arab Emirates"]) == "United Kingdom")
LON = ["London, Ontario, Canada", "London, England, United Kingdom"]
check("London là London bên UK",
      run.match(Ans("London", ("London, UK",), ("United Kingdom", "England")), LON)
      == "London, England, United Kingdom")
check("không có gì khớp thì trả RỖNG, không lấy bừa",
      run.match(Ans("Royal Holloway"), ["Oxford", "Cambridge"]) == "")
check("gõ thử theo thứ tự: giá trị trước, cách gọi sau",
      run.queries(Ans("MSc", LEVEL_WORDS["master"]))[0] == "MSc")
check("cắt ở dấu phẩy",
      run.queries(Ans("Royal Holloway, University of London")) == ["Royal Holloway"])

print("\n== ranh giới: máy KHÔNG bấm Gửi ==")
source = Path(__file__).resolve().parent.parent / "src/jobbot/apply/run.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
calls = []
for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        fn = node.func
        calls.append(fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", ""))
check("không gọi .click() ở đâu cả", "click" not in calls)
check("không gọi .submit() ở đâu cả", "submit" not in calls)

body = source.read_text(encoding="utf-8")
check("không gõ phím Enter", '"Enter"' not in body and "'Enter'" not in body)
# Hai chốt phải còn nguyên: bấm mở danh sách và bấm chọn dòng.
check("chốt 1 — thẻ phải bọc chính ô đó", 'box.get("wraps")' in body)
check("chốt 1 — điểm bấm phải nằm trên thẻ đó", 'box.get("hits")' in body)
check("chốt 2 — chỉ bấm thẻ role=option", 'spot.get("role") != "option"' in body)
check("chốt 2 — điểm bấm phải nằm trên dòng đó", 'spot.get("hits")' in body)
check("mọi cú bấm đi qua đúng một hàm", body.count("Input.dispatchMouseEvent") == 1)

print("\n== nút Gửi: kiểm trước, bấm sau ==")
from jobbot.apply import send


class FormTab:
    """Tab giả: trả về đúng cái READ_JS sẽ trả về."""

    def __init__(self, items):
        self.items = items
        self.clicks = 0

    def eval(self, js, timeout=30.0):
        import json as _j
        return _j.dumps(self.items)

    def call(self, method, params=None, timeout=30.0):
        if method == "Input.dispatchMouseEvent":
            self.clicks += 1
        return {}


def _f(label, required, value, kind="text"):
    return {"k": 0, "name": label, "dom_id": "", "kind": kind, "label": label,
            "option": "", "group": "", "required": required, "options": [],
            "value": value}


full = FormTab([_f("First Name*", True, "Dac Vinh"), _f("Privacy *", True, "x")])
gap = FormTab([_f("First Name*", True, "Dac Vinh"), _f("Privacy *", True, ""),
               _f("Have you served in the military?*", True, "")])

check("form đủ -> không còn ô trống", send.missing(full) == [])
check("form thiếu -> chỉ ra đúng ô nào", send.missing(gap) ==
      ["Privacy *", "Have you served in the military?*"], str(send.missing(gap)))

refused = send.submit(gap)
check("thiếu thì TỪ CHỐI gửi", refused.ok is False)
check("và nói vì sao", "bắt buộc" in refused.why, refused.why)
check("KHÔNG bấm chuột lần nào", gap.clicks == 0, str(gap.clicks))
# Ô nhân khẩu học máy không bao giờ điền — nên nó phải nằm trong danh sách
# chặn, không phải bị bỏ qua cho trôi.
check("ô nhân khẩu học bắt buộc cũng chặn được",
      "Have you served in the military?*" in refused.missing)

body = (Path(__file__).resolve().parent.parent
        / "src/jobbot/apply/send.py").read_text(encoding="utf-8")
check("mọi cú bấm đi qua đúng một chỗ", body.count("Input.dispatchMouseEvent") == 1)
check("nút phải thuộc form đã điền", 'aim.get("inform")' in body)
check("điểm bấm phải nằm trên nút", 'aim.get("hits")' in body)
# Phần ĐIỀN không được biết cách gửi — đó là lý do gửi nằm ở tệp riêng.
fill_body = (Path(__file__).resolve().parent.parent
             / "src/jobbot/apply/run.py").read_text(encoding="utf-8")
check("run.py không gọi submit()", "send.submit" not in fill_body
      and "submit(" not in fill_body)

routes = (Path(__file__).resolve().parent.parent
          / "src/jobbot/dashboard/server.py").read_text(encoding="utf-8")
check("đúng MỘT đường tới phần gửi", routes.count("apply_send.submit") == 1)
check("gửi hụt thì KHÔNG đổi trạng thái",
      routes.index("if not done.ok") < routes.index("board.set_stage(conn, int(row[\"id\"])"))

print("\n== chưa đăng nhập thì NÓI, không im ==")
check("nhận ra trang login của LinkedIn",
      bool(run.LOGIN_WALL.search("https://www.linkedin.com/login/?session_redirect=x")))
check("nhận ra authwall",
      bool(run.LOGIN_WALL.search("https://www.linkedin.com/authwall?trk=y")))
check("KHÔNG nhầm trang nộp của Lever (đuôi /apply)",
      not run.LOGIN_WALL.search("https://jobs.lever.co/zopa/abc/apply"))
check("KHÔNG nhầm trang Greenhouse",
      not run.LOGIN_WALL.search("https://job-boards.greenhouse.io/point72/jobs/729"))
_wall = run.Report(needs_login="https://www.linkedin.com/login/")
check("báo cáo nói rõ lý do, không nói 'không thấy form'",
      "đăng nhập" in _wall.line(), _wall.line())
_routes = (Path(__file__).resolve().parent.parent
           / "src/jobbot/dashboard/server.py").read_text(encoding="utf-8")
check("máy chủ ghi LỖI ra nhật ký", "CHƯA ĐĂNG NHẬP" in _routes)
check("và dừng, không ghi tiếp như thể đã điền",
      _routes.index("CHƯA ĐĂNG NHẬP") < _routes.index('journal.log.ok(journal.SEARCH, f"{who} — {report.line()}")'))

print("\n== LinkedIn: moi đường nộp thật ==")
from jobbot.apply import linkedin as lk
_wrapped = ("https://www.linkedin.com/safety/go/?url=https%3A%2F%2Ftargetjobs%2Eco%2Euk"
            "%2Fjobs%2Fstructured-credit&urlhash=abcd")
check("giải mã được URL công ty",
      lk.unwrap(_wrapped) == "https://targetjobs.co.uk/jobs/structured-credit",
      lk.unwrap(_wrapped))
# LinkedIn mã hoá cả dấu chấm thành %2E — cắt chuỗi bằng tay là ra 'targetjobs%2Eco%2Euk'
check("dấu chấm mã hoá %2E cũng ra đúng", ".co.uk" in lk.unwrap(_wrapped))
check("link nội bộ LinkedIn thì bỏ",
      lk.unwrap("https://www.linkedin.com/jobs/view/123") == "")
check("link ra ngoài sẵn thì lấy luôn",
      lk.unwrap("https://jobs.lever.co/prima/x/apply") == "https://jobs.lever.co/prima/x/apply")
check("nhận ra trang tin LinkedIn",
      bool(lk.JOBS.search("https://www.linkedin.com/jobs/view/4449348217/")))
check("không nhầm trang khác",
      not lk.JOBS.search("https://job-boards.greenhouse.io/point72/jobs/729"))
_fill = (Path(__file__).resolve().parent.parent
         / "src/jobbot/apply/run.py").read_text(encoding="utf-8")
check("chưa đăng nhập thì dừng, không đi mò tiếp",
      _fill.index("if lk.JOBS.search(url)") < _fill.index("real = lk.apply_url(tab)"))

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
