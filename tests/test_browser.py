"""Test tầng Chrome — WebSocket, CDP, và luật an toàn.  python3 tests/test_browser.py

Phần cần Chrome thật sẽ tự bỏ qua nếu Chrome chưa chạy.
"""

import struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.browser import chrome, ws
from jobbot.ingest.web import base as webbase

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

print("\n[bắt tay: khung về CHUNG gói với 101 không được rơi]")
# Mọi bài test ở trên đều đi vòng qua __init__ (dùng __new__), nên không cái
# nào thấy được rằng __init__ gán self._buf = b"" NGAY SAU _handshake — tức là
# ném đi đúng những byte khung mà _handshake vừa giữ lại. Chrome gửi 101 và
# sự kiện đầu tiên chung một gói TCP là mất frame.
class HandshakeSock:
    """Trả 101 và một khung 'hello' trong CÙNG một lần đọc."""
    RESPONSE = (b"HTTP/1.1 101 Switching Protocols\r\n"
                b"Upgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
                + bytes([0x81, 5]) + b"hello")

    def __init__(self): self.sent, self.given = b"", False
    def sendall(self, b): self.sent += b
    def settimeout(self, t): pass
    def close(self): pass
    def recv(self, n):
        if self.given:
            return b""
        self.given = True
        return self.RESPONSE

made = HandshakeSock()
real_create = ws.socket.create_connection
ws.socket.create_connection = lambda *a, **k: made
try:
    live = ws.WebSocket("ws://127.0.0.1:9222/devtools/browser/abc")
    check("bắt tay xong vẫn giữ được khung đi kèm", live.recv() == "hello")
finally:
    ws.socket.create_connection = real_create

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
      not webbase.BLOCKED.search("Quantitative Analyst jobs in London | LinkedIn"))

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
check("chạy trọn vẹn thì lành", Health(10, 0).ok)

# LỖI THẬT: linkedin.fetch gặp Blocked giữa vòng đọc kỹ thì chỉ note() rồi
# break — failed vẫn 0, record_run thấy 0/193 hỏng nên ghi ok=1, và màn hình
# Settings hiện huy hiệu XANH cho một lần quét bị cắt từ tin thứ ba.
blocked = Health(attempted=193, failed=0)
check("chưa chặn thì lành", blocked.ok)
blocked.block("bị chặn ở tin 3/193", unread=191)
check("bị chặn -> KHÔNG còn lành", not blocked.ok)
check("và số tin chưa đọc được tính là hỏng", blocked.failed == 191)
check("và nói thẳng ra là bị chặn", "BỊ CHẶN" in blocked.summary)
early = Health(attempted=5)
early.block("chặn ngay từ tin đầu", unread=5)
check("bị chặn ngay tin đầu vẫn không lành", not early.ok)

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
sys.exit(1 if fail else 0)
