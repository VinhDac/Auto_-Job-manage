"""Test bước 5-6: nộp và theo dõi.  python3 tests/test_track.py

Trọng tâm là RÀNG BUỘC, không phải tính năng: hộp thư là thứ Vin quan tâm
nhất, nên "chỉ đọc" phải là điều kiểm được, không phải lời hứa trong tài liệu.
"""

import inspect, os, re, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db
from jobbot.track import board, mail, scan, sort

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")


print("\n[hộp thư — CHỈ ĐỌC, và ràng buộc nằm trong code]")
src = inspect.getsource(mail)
code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
check("mở hộp thư ở chế độ readonly", "readonly=True" in code)
check("lấy thư bằng BODY.PEEK — không đặt cờ đã đọc", "BODY.PEEK" in code)
# Kiểm CHÍNH XÁC: mọi lệnh gọi lên đối tượng IMAP (biến `box`), không phải
# tìm chuỗi ký tự — `out.append(...)` của list từng bị bắt nhầm là lệnh APPEND
# của IMAP.
import ast as _ast
calls = set()
for node in _ast.walk(_ast.parse(src)):
    if (isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute)
            and isinstance(node.func.value, _ast.Name)
            and node.func.value.id == "box"):
        calls.add(node.func.attr)
check(f"chỉ gọi {sorted(calls)} lên hộp thư",
      calls <= {"login", "select", "search", "fetch", "logout", "close"})
for danger in ("store", "append", "copy", "expunge", "uid", "setacl",
               "create", "delete", "rename", "subscribe"):
    check(f"KHÔNG gọi box.{danger}()", danger not in calls)
check("KHÔNG import smtp", "smtplib" not in code)
check("giới hạn 30 ngày", mail.SINCE_DAYS == 30 and "since_days" in code)
check("có trần số thư, hộp to không treo vòng quét", mail.MAX_MESSAGES > 0)
check("chưa cấu hình thì báo lỗi rõ, không nổ vu vơ",
      "config.toml" in code)

print("\n[nối hộp thư từ giao diện — mật khẩu không được rò ra]")
from jobbot.core import config as _cfg
from jobbot.dashboard.views import track as _tv

_keep = _cfg.PATH.read_text() if _cfg.PATH.exists() else None
try:
    _cfg.write_value("mail", "address", "a@b.c")
    _cfg.write_value("mail", "password", 'p"w\\d')
    check("ghi rồi đọc lại ra đúng", _cfg.section("mail")["password"] == 'p"w\\d')
    check("không đụng khoá khác", _cfg.section("mail")["address"] == "a@b.c")
    # config.toml có phần chú thích dài giải thích vì sao dùng hộp thư riêng.
    # Dựng lại cả tệp là xoá mất phần đó.
    check("giữ nguyên chú thích", "app password" in _cfg.PATH.read_text())
    check("chỉ chủ máy đọc được", (_cfg.PATH.stat().st_mode & 0o777) == 0o600)
    _cfg.write_value("mail", "password", "")
    check("xoá được", _cfg.section("mail")["password"] == "")
finally:
    if _keep is not None:
        _cfg.PATH.write_text(_keep)

# Trang Quản lí Vin mở hàng ngày. Một ô password có sẵn giá trị nghĩa là mật
# khẩu nằm trong HTML, đọc được bằng View Source.
_html = _tv.render(rows=[], asks=[], counts={}, mail_ready=False,
                   mail_address="a@b.c")
check("có ô nhập hộp thư", "/api/mail/setup" in _html)
check("ô mật khẩu là type=password", "type=password" in _html)
check("KHÔNG vẽ giá trị mật khẩu ra HTML",
      not re.search(r"type=password[^>]*value=", _html))
check("địa chỉ thì vẽ ra được", "a@b.c" in _html)
_on = _tv.render(rows=[], asks=[], counts={}, mail_ready=True, mail_address="a@b.c")
check("nối rồi thì hiện nút quét", "/api/track/mail/scan" in _on)
check("và nút xoá mật khẩu", "/api/mail/forget" in _on)

# Thông báo lỗi của imaplib là nguyên văn máy chủ trả lời, và nó đi thẳng vào
# nhật ký — một lần lọt là lọt vĩnh viễn.
check("mật khẩu bị bịt trong thông báo lỗi",
      mail._hide("login failed for hunter2", "hunter2") == "login failed for ***")
check("chưa điền thì nói ngay, không gọi mạng",
      mail.check("", "") == "chưa điền đủ địa chỉ và app password")
# Dán nhầm MẬT KHẨU TÀI KHOẢN là chuyện thường. Bắt bằng hình dạng, TRƯỚC khi
# gửi nó qua mạng — không thì mật khẩu thật đã bay đi rồi mới biết là vô ích.
check("mật khẩu tài khoản bị chặn tại chỗ",
      "không phải app password" in mail.check("a@b.c", "Work123@"))
check("và không hề gọi mạng", "Gmail từ chối" not in mail.check("a@b.c", "Work123@"))
check("app password đúng hình dạng thì cho qua vòng kiểm hình dạng",
      "không phải app password" not in mail.check.__doc__ or
      bool(mail.APP_PASSWORD.fullmatch("abcdefghijklmnop")))
check("Google hiện theo nhóm 4 — bỏ dấu cách vẫn nhận",
      bool(mail.APP_PASSWORD.fullmatch("abcd efgh ijkl mnop".replace(" ", ""))))
# Thứ đem đi KIỂM phải đúng bằng thứ đem đi ĐĂNG NHẬP. Route bỏ dấu cách ngay
# lúc lưu; nếu không, check() so chuỗi đã bỏ cách còn login() gửi chuỗi có cách.
_srv = (Path(__file__).resolve().parent.parent
        / "src/jobbot/dashboard/server.py").read_text(encoding="utf-8")
check("lưu app password thì bỏ dấu cách", '.replace(" ", "")' in _srv)

print("\n[xếp loại thư]")
def m(subject, snippet="", name="", addr=""):
    return {"subject": subject, "snippet": snippet,
            "from_name": name, "from_addr": addr, "msg_id": subject}

check("thư xác nhận", sort.kind(m("Thank you for applying")) == board.SENT)
check("thư từ chối",
      sort.kind(m("Update", "we will not be moving forward")) == board.REJECTED)
check("thư mời phỏng vấn",
      sort.kind(m("Next steps", "we would like to invite you to a call")) == board.INTERVIEW)
check("bài kiểm tra online cũng tính là phỏng vấn",
      sort.kind(m("Assessment", "please complete the HackerRank test")) == board.INTERVIEW)
check("thư mời việc", sort.kind(m("Offer", "we are pleased to offer you")) == board.OFFER)
check("thư khác thì để yên", sort.kind(m("5 new jobs for you")) == "other")
# Thư mời phỏng vấn thường VẪN mở đầu bằng "thank you for applying". Xét từ
# kết cục mạnh nhất xuống, nếu không thì thư quan trọng nhất bị xếp thành xác nhận.
check("mời phỏng vấn thắng xác nhận khi cùng một thư",
      sort.kind(m("Your application",
                  "Thank you for applying. We would like to invite you to a call."))
      == board.INTERVIEW)

print("\n[đoán công ty]")
for want, msg in (("Point72", m("x", name="Careers at Point72")),
                  ("Jump Trading", m("x", name="Jump Trading Recruiting")),
                  ("Schonfeld", m("x", name="Schonfeld Talent Acquisition Team")),
                  ("Qube Research", m("Interview - Qube Research", addr="a@greenhouse.io")),
                  ("Jane Street", m("Your application to Jane Street", addr="a@lever.co"))):
    got = sort.company_of(msg)
    check(f"{want:<14} <- {got[:26]}", want.lower() in got.lower())

with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")

    print("\n[bảng]")
    a = board.add(conn, "Point72", "Quantitative Researcher", cv_file="p.pdf")
    b = board.add(conn, "Point72", "Quantitative Researcher")
    check("nộp lại cùng vai trò KHÔNG đẻ dòng mới", a == b)
    check("nộp khác vai trò thì là dòng khác",
          board.add(conn, "Point72", "Data Scientist") != a)
    board.set_stage(conn, a, board.REJECTED, "not moving forward")
    check("đổi được trạng thái",
          [r for r in board.all(conn) if r["id"] == a][0]["stage"] == board.REJECTED)
    board.set_stage(conn, a, "bịa")
    check("trạng thái bịa thì không nhận",
          [r for r in board.all(conn) if r["id"] == a][0]["stage"] == board.REJECTED)

    # `im lặng` là PHÉP TRỪ, không phải cột. Lưu thì phải cập nhật mỗi ngày,
    # và sẽ có ngày quên — cùng lý do `khoảng trống` ở lưới project không lưu.
    check("im lặng không phải cột trong bảng",
          "silent" not in [r[1] for r in conn.execute("PRAGMA table_info(application)")])
    old = board.add(conn, "Old Firm", "Analyst",
                    applied_at="2020-01-01T00:00:00+00:00")
    row = [r for r in board.all(conn) if r["id"] == old][0]
    check("nộp lâu, chưa thư nào -> im lặng", row["silent"])
    board.set_stage(conn, old, board.INTERVIEW, "mời phỏng vấn")
    row = [r for r in board.all(conn) if r["id"] == old][0]
    check("có thư rồi thì hết im lặng", not row["silent"])

    print("\n[thư khớp vào dòng nào]")
    conn.execute("DELETE FROM message"); conn.execute("DELETE FROM application")
    conn.commit()
    p72 = board.add(conn, "Point72", "Quantitative Researcher")
    board.add(conn, "Man Group", "Quant Developer")
    check("khớp theo tên người gửi",
          sort.match(conn, m("x", name="Careers at Point72")) == p72)
    check("tên miền không có dấu cách vẫn khớp (mangroup <-> man group)",
          sort.match(conn, m("Application update", addr="careers@mangroup.com")) is not None)
    check("không khớp được thì nói không khớp, không đoán bừa",
          sort.match(conn, m("Interview - Some Firm Nobody Applied To",
                             addr="a@greenhouse.io")) is None)

    print("\n[thư ĐỀ XUẤT, không tự đổi]")
    conn.execute("DELETE FROM message"); conn.execute("DELETE FROM application")
    conn.commit()
    app = board.add(conn, "Point72", "Quantitative Researcher")
    note = m("Next steps", "we would like to invite you to a call",
             name="Careers at Point72")
    scan.store(conn, {**note, "received_at": "2026-09-08T10:00:00",
                      "from_addr": "", "from_name": "Careers at Point72"},
               sort.kind(note), sort.company_of(note), app)
    stage_now = [r for r in board.all(conn) if r["id"] == app][0]["stage"]
    check("thư về mà trạng thái CHƯA đổi", stage_now == board.SENT)
    asks = scan.proposals(conn)
    check("nó nằm ở dải chờ Vin quyết", len(asks) == 1)
    check("và nói rõ đổi sang gì", asks[0]["kind"] == board.INTERVIEW)
    scan.settle(conn, asks[0]["id"], accept=True)
    check("Vin nhận thì mới đổi",
          [r for r in board.all(conn) if r["id"] == app][0]["stage"] == board.INTERVIEW)
    check("trả lời xong thì không hỏi lại", scan.proposals(conn) == [])

    print("\n[dựng lại quá khứ từ thư]")
    # Xoá THƯ trước rồi mới xoá dòng nộp: message.application_id là khoá
    # ngoại, và nó KHÔNG có ON DELETE CASCADE. Nghĩa là sau này muốn cho Vin
    # xoá một dòng khỏi bảng thì phải gỡ thư trỏ vào nó trước.
    conn.execute("DELETE FROM message"); conn.execute("DELETE FROM application")
    conn.commit()
    past = m("Thank you for applying", "We have received your application.",
             name="Jump Trading Recruiting")
    kind, who = sort.kind(past), sort.company_of(past)
    got = sort.match(conn, past)
    if got is None and kind == board.SENT and who:
        got = board.add(conn, who, "", origin="mail",
                        applied_at="2026-08-20T09:00:00+00:00")
    check("thư xác nhận không khớp ai -> dựng lại một lần nộp", got is not None)
    row = board.all(conn)[0]
    check("và ghi rõ nó đến từ thư", row["origin"] == "mail")
    check("giữ đúng ngày trong thư", row["applied_at"].startswith("2026-08-20"))
    conn.close()

print("\n[nối hộp thư từ giao diện — mật khẩu không được rò ra]")
from jobbot.core import config as _cfg
from jobbot.dashboard.views import track as _tv

_keep = _cfg.PATH.read_text() if _cfg.PATH.exists() else None
try:
    _cfg.write_value("mail", "address", "a@b.c")
    _cfg.write_value("mail", "password", 'p"w\\d')
    check("ghi rồi đọc lại ra đúng", _cfg.section("mail")["password"] == 'p"w\\d')
    check("không đụng khoá khác", _cfg.section("mail")["address"] == "a@b.c")
    # config.toml có phần chú thích dài giải thích vì sao dùng hộp thư riêng.
    # Dựng lại cả tệp là xoá mất phần đó.
    check("giữ nguyên chú thích", "app password" in _cfg.PATH.read_text())
    check("chỉ chủ máy đọc được", (_cfg.PATH.stat().st_mode & 0o777) == 0o600)
    _cfg.write_value("mail", "password", "")
    check("xoá được", _cfg.section("mail")["password"] == "")
finally:
    if _keep is not None:
        _cfg.PATH.write_text(_keep)

# Trang Quản lí Vin mở hàng ngày. Một ô password có sẵn giá trị nghĩa là mật
# khẩu nằm trong HTML, đọc được bằng View Source.
_html = _tv.render(rows=[], asks=[], counts={}, mail_ready=False,
                   mail_address="a@b.c")
check("có ô nhập hộp thư", "/api/mail/setup" in _html)
check("ô mật khẩu là type=password", "type=password" in _html)
check("KHÔNG vẽ giá trị mật khẩu ra HTML",
      not re.search(r"type=password[^>]*value=", _html))
check("địa chỉ thì vẽ ra được", "a@b.c" in _html)
_on = _tv.render(rows=[], asks=[], counts={}, mail_ready=True, mail_address="a@b.c")
check("nối rồi thì hiện nút quét", "/api/track/mail/scan" in _on)
check("và nút xoá mật khẩu", "/api/mail/forget" in _on)

# Thông báo lỗi của imaplib là nguyên văn máy chủ trả lời, và nó đi thẳng vào
# nhật ký — một lần lọt là lọt vĩnh viễn.
check("mật khẩu bị bịt trong thông báo lỗi",
      mail._hide("login failed for hunter2", "hunter2") == "login failed for ***")
check("chưa điền thì nói ngay, không gọi mạng",
      mail.check("", "") == "chưa điền đủ địa chỉ và app password")
# Dán nhầm MẬT KHẨU TÀI KHOẢN là chuyện thường. Bắt bằng hình dạng, TRƯỚC khi
# gửi nó qua mạng — không thì mật khẩu thật đã bay đi rồi mới biết là vô ích.
check("mật khẩu tài khoản bị chặn tại chỗ",
      "không phải app password" in mail.check("a@b.c", "Work123@"))
check("và không hề gọi mạng", "Gmail từ chối" not in mail.check("a@b.c", "Work123@"))
check("app password đúng hình dạng thì cho qua vòng kiểm hình dạng",
      "không phải app password" not in mail.check.__doc__ or
      bool(mail.APP_PASSWORD.fullmatch("abcdefghijklmnop")))
check("Google hiện theo nhóm 4 — bỏ dấu cách vẫn nhận",
      bool(mail.APP_PASSWORD.fullmatch("abcd efgh ijkl mnop".replace(" ", ""))))
# Thứ đem đi KIỂM phải đúng bằng thứ đem đi ĐĂNG NHẬP. Route bỏ dấu cách ngay
# lúc lưu; nếu không, check() so chuỗi đã bỏ cách còn login() gửi chuỗi có cách.
_srv = (Path(__file__).resolve().parent.parent
        / "src/jobbot/dashboard/server.py").read_text(encoding="utf-8")
check("lưu app password thì bỏ dấu cách", '.replace(" ", "")' in _srv)

print("\n[xếp loại thư — đo trên tiêu đề thư thật]")
# Bản cũ đạt 10/13. Ba ca hụt, và ca hụt nặng nhất là THƯ TỪ CHỐI rơi xuống
# "other": needs_you=0 nên thư không bao giờ hiện ra, bảng báo "đang chờ" mãi
# cho một lần nộp đã chết.
MAIL_CASES = [
    (board.SENT,      "Thank you for applying to Man Group",       "We have received your application."),
    (board.SENT,      "We've received your application",            "Your application is with our team."),
    (board.SENT,      "Application received — Quantitative Analyst", "Thanks for your interest."),
    (board.INTERVIEW, "Invitation to interview — Point72",          "Thank you for applying. We'd like to meet."),
    (board.INTERVIEW, "Interview invitation",                       "Thank you for applying to IMC."),
    (board.INTERVIEW, "We'd like to invite you for an interview",   "Thanks for applying."),
    (board.INTERVIEW, "Next steps: online assessment",              "Please complete the HackerRank test."),
    (board.INTERVIEW, "Let's schedule a call",                      "Are you free next week?"),
    (board.REJECTED,  "Your application to IMC",                    "Unfortunately we will not be progressing."),
    (board.REJECTED,  "Update on your application",                 "We have decided not to move forward at this time."),
    (board.REJECTED,  "Thank you for your interest in Jane Street", "We won't be taking your application further."),
    (board.REJECTED,  "Application update",                         "You have not been successful on this occasion."),
    (board.REJECTED,  "Re: Quantitative Analyst",                   "We are unable to offer you a position."),
    (board.OFFER,     "Offer of employment — Prima",                "We are delighted to offer you the role."),
    ("other",         "Your Amazon order has shipped",              "Track your parcel"),
    ("other",         "LinkedIn: 5 new jobs for you",               "Jobs matching your profile"),
    ("other",         "Your monthly statement is ready",            "Barclays"),
    ("other",         "Newsletter: quant careers this week",        "Top stories"),
]
for want, subject, snippet in MAIL_CASES:
    got = sort.kind({"subject": subject, "snippet": snippet,
                     "from_name": "", "from_addr": "x@y.z"})
    check(f"{want:<9} {subject[:40]}", got == want)
# Thư mời phỏng vấn gần như luôn mở đầu bằng "thank you for applying" — luật
# mời PHẢI xét trước luật xác nhận, không thì thư quan trọng nhất bị hạ cấp.
_names = [name for name, _ in sort.RULES]
check("xét kết cục mạnh trước", _names.index(board.INTERVIEW) < _names.index(board.SENT))
check("từ chối xét trước xác nhận", _names.index(board.REJECTED) < _names.index(board.SENT))

print("\n[thư dựng lại quá khứ — MỌI kết cục, không riêng thư xác nhận]")
with tempfile.TemporaryDirectory() as tmp:
    os.environ["JOBBOT_DATA_DIR"] = tmp
    from jobbot.track import mail as _mail, scan as _scan
    conn = db.connect()
    board.add(conn, "Prima", "Quantitative Analyst", stage=board.DRAFT)

    def _m(sub, snip, name, addr):
        return {"msg_id": f"<{abs(hash(sub))}@x>", "from_addr": addr,
                "from_name": name, "subject": sub, "snippet": snip,
                "received_at": "2026-09-09T10:00:00+00:00"}

    _mail.fetch = lambda *a, **k: [
        _m("Thank you for applying to Prima", "We have received your application.",
           "Prima", "no-reply@jobs.lever.co"),
        _m("Interview invitation — Jane Street", "Thank you for applying. Let's schedule a call.",
           "Jane Street", "recruiting@janestreet.com"),
        _m("Your Amazon order has shipped", "Track your parcel", "Amazon", "ship@amazon.co.uk"),
    ]
    _mail.account = lambda: ("x@y.z", "pw")
    got = _scan.run(conn)
    check("đọc hết thư", got["seen"] == 3)
    # LỖI ĐÃ SỬA: chỉ thư xác nhận mới dựng lại dòng, nên thư mời phỏng vấn từ
    # công ty chưa có dòng thì Vin bấm Nhận và KHÔNG có gì xảy ra.
    rows = {r["company"]: r for r in board.all(conn)}
    check("thư mời phỏng vấn dựng ra dòng mới", "Jane Street" in rows)
    check("và dựng ở ĐÚNG chặng, không ép về 'đã nộp'",
          rows.get("Jane Street", {}).get("stage") == board.INTERVIEW)
    check("thư mua hàng KHÔNG đẻ ra dòng nào", "Amazon" not in rows)
    # dòng nháp gặp thư xác nhận -> đề xuất chuyển sang đã nộp
    moves = {p["company"]: p["kind"] for p in _scan.proposals(conn)}
    check("nháp + thư xác nhận -> đề xuất 'đã nộp'", moves.get("Prima") == board.SENT)
    conn.close()
    os.environ.pop("JOBBOT_DATA_DIR", None)

print("\n[máy điền, Vin bấm Gửi]")
# Luật CŨ ở đây là "chỉ mở trang, không điền". Đã đổi có chủ ý: máy điền phần
# chứng minh được, còn cú bấm Gửi thì không tồn tại trong đường code nào —
# ranh giới nằm ở `apply/run.py`, và `tests/test_apply.py` canh nó.
server = (Path(__file__).resolve().parent.parent
          / "src/jobbot/dashboard/server.py").read_text()
apply_block = server[server.index('if path == "/api/apply"'):
                     server.index('if path == "/api/track/state"')]
check("nút Nộp chạy phần điền", "_start_apply" in apply_block)
check("và ghi một dòng vào bảng", "board.add" in apply_block)
check("dùng CHUNG một nguồn tên PDF", "cv_pdf_for" in apply_block)
check("không mở trình duyệt mặc định nữa", "webbrowser" not in apply_block)
for danger in ("Input.dispatchKeyEvent", "form.submit", "click()", "Page.navigate"):
    check(f"không có {danger}", danger not in apply_block)
check("và ghi một dòng vào bảng", "board.add" in apply_block)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
