"""Test bước 5-6: nộp và theo dõi.  python3 tests/test_track.py

Trọng tâm là RÀNG BUỘC, không phải tính năng: hộp thư là thứ Vin quan tâm
nhất, nên "chỉ đọc" phải là điều kiểm được, không phải lời hứa trong tài liệu.
"""

import inspect, sys, tempfile
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
