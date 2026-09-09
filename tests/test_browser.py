"""Test tầng Chrome — WebSocket, CDP, và luật an toàn.  python3 tests/test_browser.py

Phần cần Chrome thật sẽ tự bỏ qua nếu Chrome chưa chạy.
"""

import re, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.browser import chrome, ws
from jobbot.ingest.web import base as webbase

ok = fail = skip = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}{' — ' + extra if extra else ''}")

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

print("\n[vòng đọc kỹ KHÔNG được đọc lại thứ đã đọc]")
# GỐC RỄ của cả chuỗi lỗi bước 1. Trên máy thật 194/196 tin LinkedIn đã có mô
# tả, mà vòng đọc kỹ vẫn mở lại tất cả — 97% công là làm lại. Chính chỗ thừa
# đó đẻ ra: 17 phút mỗi vòng -> ~5.000 lượt gọi/ngày -> bị bóp 40-82% -> phải
# nghỉ lâu hơn -> phải cắt 12 chức danh còn 5. Sửa một chỗ, cả chuỗi tan.
from jobbot.ingest.web import linkedin as li

class FakeTab:
    """Trả danh sách 3 tin, và đếm xem vòng đọc kỹ mở bao nhiêu trang chi tiết."""
    def __init__(self): self.detail_opens = []
    def eval(self, js, timeout=None):
        if "show-more-less-html__markup" in js:      # DETAIL_JS
            return '[{"description":"' + "x" * 400 + '","criteria":""}]'
        return ('[{"title":"Quant Analyst","company":"A","location":"London",'
                '"url":"https://x/jobs/view/a-1000001","posted":""},'
                '{"title":"Data Scientist","company":"B","location":"London",'
                '"url":"https://x/jobs/view/b-1000002","posted":""},'
                '{"title":"Risk Analyst","company":"C","location":"London",'
                '"url":"https://x/jobs/view/c-1000003","posted":""}]')

real_open, real_pause = li.open_page, li._pause
opened = []
li.open_page = lambda tab, url, timeout=30: opened.append(url)
li._pause = lambda: None
try:
    opened.clear()
    li.fetch(FakeTab(), ["Quant Analyst"], pages=1, deep=True)
    all_read = sum(1 for u in opened if "jobPosting" in u)
    check("chưa biết gì -> đọc kỹ cả 3 tin", all_read == 3, f"đọc {all_read}")

    opened.clear()
    li.fetch(FakeTab(), ["Quant Analyst"], pages=1, deep=True,
             skip=frozenset({"1000001", "1000002"}))
    again = sum(1 for u in opened if "jobPosting" in u)
    check("đã đọc 2 tin -> chỉ đọc kỹ 1 tin còn lại", again == 1, f"đọc {again}")

    opened.clear()
    out = li.fetch(FakeTab(), ["Quant Analyst"], pages=1, deep=True,
                   skip=frozenset({"1000001", "1000002", "1000003"}))
    check("đã đọc hết -> KHÔNG mở trang chi tiết nào",
          sum(1 for u in opened if "jobPosting" in u) == 0)
    check("nhưng vẫn TRẢ VỀ đủ tin tìm được", len(out[0]) == 3)
finally:
    li.open_page, li._pause = real_open, real_pause

print("\n[địa điểm đọc từ hồ sơ, không phải chuỗi cứng]")
check("uk_onsite + uk_remote -> United Kingdom (rộng hơn London)",
      li.places_for(["uk_onsite", "uk_remote"]) == ["United Kingdom"])
check("bỏ trùng", len(li.places_for(["uk_onsite", "uk_remote", "uk_onsite"])) == 1)
check("global_remote -> để trống, LinkedIn tìm toàn cầu",
      li.places_for(["global_remote"]) == [""])
check("nhiều thị trường -> nhiều nơi",
      li.places_for(["uk_onsite", "us_remote"]) == ["United Kingdom", "United States"])
check("hồ sơ chưa chọn gì -> vẫn có mặc định", li.places_for([]) == ["United Kingdom"])
check("KHÔNG còn 'London' cứng trong chữ ký hàm",
      'location: str = "London"' not in Path("src/jobbot/ingest/web/linkedin.py").read_text())

print("\n[trần chức danh: có, nhưng phải NÓI RA]")
runner = Path("src/jobbot/scan_runner.py").read_text()
# Bỏ dòng chú thích trước khi soi — nếu không thì chính lời giải thích về
# cái lỗi vừa sửa lại làm bài test đỏ.
code_only = "\n".join(l for l in runner.split("\n")
                       if not l.strip().startswith("#"))
check("bỏ hẳn titles[:5] khỏi CODE", "titles[:5]" not in code_only)
check("nhưng giữ lời giải thích vì sao bỏ", "titles[:5]" in runner)
li_src = Path("src/jobbot/ingest/web/linkedin.py").read_text()
check("trần đặt tên rõ ràng", "MAX_QUERIES" in li_src)
check("và chạm trần thì ghi nhật ký, không cắt lặng lẽ",
      "chỉ tìm" in li_src and "jlog.warn" in li_src)

print("\n[tắt Chrome: phải THẬT SỰ tắt, và chỉ tắt bản của app]")
# LỖI THẬT: bản cũ gọi GET /json/close — endpoint đó cần kèm target id nên
# trả 404, lỗi bị nuốt trong except, hàm trả None và Chrome vẫn nguyên đó.
# Hàm "tắt" mà không tắt gì, chạy êm ru suốt.
from jobbot.browser import chrome as ch
src_ch = Path("src/jobbot/browser/chrome.py").read_text()

def code_of(name, text=src_ch):
    """Thân hàm, BỎ chú thích và docstring — để không kiểm nhầm vào lời giải
    thích về chính cái lỗi đã sửa."""
    body = text.split(f"def {name}")[1]
    body = body.split("\ndef ")[0]
    body = re.sub(r'"""[\s\S]*?"""', "", body)
    return "\n".join(l for l in body.split("\n") if not l.strip().startswith("#"))

shut = code_of("shutdown")
check("KHÔNG gọi endpoint /json/close (cần target id, trả 404)",
      "/json/close" not in shut)
check("dùng lệnh CDP Browser.close", "Browser.close" in shut)
check("đi qua websocket của TRÌNH DUYỆT", "webSocketDebuggerUrl" in shut)
check("shutdown trả về bool để người gọi biết có tắt được không",
      "-> bool" in src_ch.split("def shutdown")[1].split("\n")[0])
check("và có chờ, không trả lời ngay khi chưa tắt xong", "alive(port)" in shut)
# Chrome cá nhân cũng là tiến trình "Google Chrome" — giết theo TÊN là quét
# luôn cả nó, mất việc người dùng đang làm dở. Giết tiến trình do CHÍNH MÌNH
# sinh ra (process.terminate() trong launch) thì không sao.
check("KHÔNG giết tiến trình theo tên",
      not any(w in src_ch for w in ("pkill", "killall", "pgrep")))
check("cổng debug riêng, không phải 9222 mặc định", ch.PORT != 9222)
check("profile riêng, không dùng profile người dùng",
      "chrome-profile" in str(ch.profile_dir()))
check("Chrome chưa chạy -> coi như đã tắt, không báo hỏng",
      ch.shutdown(port=1) is True or not ch.alive(1))

# Hàm tắt đúng vẫn vô dụng nếu KHÔNG AI GỌI. Trước đây không một chỗ nào gọi
# shutdown(), nên Chrome mở ra rồi nằm trên màn hình tới lần quét sau — một
# tiếng sau.
runner_src = Path("src/jobbot/scan_runner.py").read_text()
app_src = Path("src/jobbot/app.py").read_text()
check("quét xong thì đóng Chrome", "chrome.shutdown()" in runner_src)
check("và báo ra nếu đóng không được", "không đóng được Chrome" in runner_src)
check("thoát app cũng đóng Chrome", "chrome.shutdown()" in app_src)

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
