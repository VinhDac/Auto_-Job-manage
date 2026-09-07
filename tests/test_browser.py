"""Test tầng Chrome — WebSocket, CDP, và luật an toàn.  python3 tests/test_browser.py

Phần cần Chrome thật sẽ tự bỏ qua nếu Chrome chưa chạy.
"""

import struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.browser import chrome, ws
from jobbot.ingest.web import base as webbase
from jobbot.ingest.web.efinancialcareers import WORK_MODE, _from_row

ok = fail = skip = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

print("\n[khung WebSocket]")
class FakeSock:
    def __init__(self): self.sent = b""
    def sendall(self, b): self.sent += b
    def settimeout(self, t): pass
    def close(self): pass

conn = ws.WebSocket.__new__(ws.WebSocket)
conn.sock, conn._buf = FakeSock(), b""
conn.send("hi")
frame = conn.sock.sent
check("bit FIN + opcode text", frame[0] == 0x81)
check("client BẮT BUỘC mask", frame[1] & 0x80 == 0x80)
check("độ dài đúng", (frame[1] & 0x7F) == 2)
mask, body = frame[2:6], frame[6:]
check("giải mask ra đúng chữ",
      bytes(b ^ mask[i % 4] for i, b in enumerate(body)) == b"hi")

conn2 = ws.WebSocket.__new__(ws.WebSocket)
conn2.sock, conn2._buf = FakeSock(), bytes([0x81, 5]) + b"hello"
check("đọc được frame server (không mask)", conn2.recv() == "hello")

conn3 = ws.WebSocket.__new__(ws.WebSocket)
conn3.sock = FakeSock()
conn3._buf = bytes([0x01, 3]) + b"abc" + bytes([0x80, 3]) + b"def"
check("nối lại frame bị chia mảnh", conn3.recv() == "abcdef")

conn4 = ws.WebSocket.__new__(ws.WebSocket)
conn4.sock, conn4._buf = FakeSock(), bytes([0x81, 126]) + struct.pack(">H", 300) + b"x" * 300
check("đọc được payload dài (16-bit)", len(conn4.recv()) == 300)

print("\n[an toàn — cookie]")
js = webbase.REJECT_JS.lower()
check("KHÔNG có 'accept' trong danh sách nút bấm", "accept all" not in js)
check("có 'reject'", "reject" in js)
check("có 'only necessary'", "only necessary" in js)
for word in ("agree", "allow all", "consent to", "i accept"):
    check(f"không bao giờ bấm '{word}'", word not in js)

print("\n[an toàn — không cãi tường chặn]")
for text in ("Just a moment...", "Attention Required! | Cloudflare",
             "Access Denied", "Verify you are human", "403 Forbidden"):
    check(f"nhận ra chặn: {text[:28]}", bool(webbase.BLOCKED.search(text)))
check("trang bình thường KHÔNG bị nhận nhầm",
      not webbase.BLOCKED.search("Quantitative jobs in London | eFinancialCareers"))

print("\n[tách dữ liệu thẻ tin]")
row = {"title": "Quant Analyst", "url": "https://x/jobs-Abc-123",
       "company": "Citi", "location": "London, United Kingdom",
       "contract": "Permanent", "salary": "Hybrid", "posted": "2 days ago"}
p = _from_row(row)
check("hình thức làm việc KHÔNG lọt vào cột lương", p.salary == "")
check("và được lưu riêng", p.payload["work_mode"] == "Hybrid")
p2 = _from_row({**row, "salary": "£65,000"})
check("lương thật thì vẫn vào cột lương", p2.salary == "£65,000")
p3 = _from_row({**row, "salary": "Remote"})
check("Remote -> đánh dấu cờ remote", p3.remote is True)
check("thiếu công ty -> 'unknown', không rỗng",
      _from_row({**row, "company": ""}).company == "unknown")

print("\n[LinkedIn — ranh giới an toàn]")
from jobbot.ingest.web import linkedin as li
src = Path("src/jobbot/ingest/web/linkedin.py").read_text()
check("KHÔNG có mã đăng nhập", not any(
    w in src.lower() for w in ("password", "login(", "signin", "sign_in", "credential")))
check("KHÔNG đụng hồ sơ cá nhân", not any(
    w in src for w in ("linkedin.com/in/", "/voyager/", "profileView",
                       "connections", "invitation", "messaging")))
check("chỉ dùng endpoint dành cho khách", "jobs-guest" in src)
check("nhịp chậm hơn nguồn khác", li.PAUSE[0] >= 2.0)
check("bị chặn thì dừng, không thử lại",
      "except Blocked" in src and "break" in src)

rows = [{"title": "Quant Analyst", "company": "Citi", "location": "London",
         "url": "/jobs/view/quant-analyst-at-citi-4443885925", "posted": "2026-09-05"}]
p1 = li._from_row(rows[0])
check("tách được id tin", p1.source_id == "4443885925")
check("dựng URL đầy đủ", p1.url.startswith("https://www.linkedin.com/jobs/view/"))
check("bỏ dòng không có id", li._from_row({"title": "x", "url": "/jobs/view/no-id"}) is None)
check("bỏ dòng không có tiêu đề",
      li._from_row({"title": "", "url": "/jobs/view/a-1234567"}) is None)
check("cấp bậc -> mã kinh nghiệm LinkedIn", li.EXPERIENCE["grad"] == "2")

print("\n[Chrome]")
check("tìm được Chrome trên máy", Path(chrome.binary()).exists())
check("profile RIÊNG, không phải profile người dùng",
      "chrome-profile" in str(chrome.profile_dir())
      and "Application Support" not in str(chrome.profile_dir()))
check("cổng riêng, không phải 9222 mặc định", chrome.PORT != 9222)


print("\n[nguồn hỏng phải TRÔNG khác nguồn tốt]")
import tempfile
from jobbot.core import db as _db, postings as _po
from jobbot.ingest.web.base import Health

h = Health(attempted=10, failed=6)
h.note("TimeoutError"); h.note("mô tả rỗng")
check("Health đếm được hỏng", h.failed == 6)
check("Health tóm tắt được lý do", "6/10 hỏng" in h.summary and "TimeoutError" in h.summary)
check("không hỏng -> không báo gì", Health(10, 0).summary == "")

with tempfile.TemporaryDirectory() as tmp:
    conn = _db.connect(Path(tmp) / "h.db")
    _po.record_run(conn, "s1", ok=True, fetched=4, attempted=10, failed=6)
    row = conn.execute("SELECT ok, error FROM source_run WHERE source='s1'").fetchone()
    check("hỏng 60% -> đánh dấu nguồn HỎNG dù vẫn lấy được tin", row["ok"] == 0)
    check("và nói rõ tỉ lệ", "6/10" in row["error"])

    _po.record_run(conn, "s2", ok=True, fetched=10, attempted=10, failed=1)
    check("hỏng 10% -> vẫn coi là chạy tốt",
          conn.execute("SELECT ok FROM source_run WHERE source='s2'").fetchone()["ok"] == 1)

    _po.record_run(conn, "s3", ok=True, fetched=10)
    check("không đo được thì không phán bừa",
          conn.execute("SELECT ok FROM source_run WHERE source='s3'").fetchone()["ok"] == 1)
    conn.close()

print("\n[Posting và bảng DB không được lệch nhau]")
from dataclasses import fields as _fields
from jobbot.core.postings import FIELD_MAP, NOT_COLUMNS
from jobbot.ingest.base import Posting as _P
_attrs = {f.name for f in _fields(_P)}
check("mọi trường Posting đều được khai", not (_attrs - set(FIELD_MAP) - set(NOT_COLUMNS)))
check("không khai thừa trường không tồn tại",
      not ((set(FIELD_MAP) | set(NOT_COLUMNS)) - _attrs))
with tempfile.TemporaryDirectory() as tmp:
    conn = _db.connect(Path(tmp) / "c.db")
    cols = {x[1] for x in conn.execute("PRAGMA table_info(posting)")}
    check("mọi cột khai trong FIELD_MAP đều có thật trong bảng",
          set(FIELD_MAP.values()) <= cols)
    conn.close()

print(f"\n{ok} ok, {fail} fail")
