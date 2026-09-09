"""Test vòng chạy nền — nhất là chuyện MỞ APP LÊN THÌ KHÔNG ĐƯỢC CHẠY LUÔN.

Lỗi thật: last_scan khởi tạo bằng 0.0, nên điều kiện

    time.time() - self.last_scan >= self.scan_every

luôn đúng ngay từ nhịp đầu -> app mở lên là 5 giây sau Chrome bật, LinkedIn
bị quét, trong khi người dùng còn chưa kịp vào Settings. Cấu hình chưa xong
thì tin quét về cũng là rác.

    python3 tests/test_scheduler.py
"""

import os, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}{' — ' + extra if extra else ''}")


with tempfile.TemporaryDirectory() as tmp:
    os.environ["JOBBOT_DATA_DIR"] = tmp
    from jobbot.core import db, prefs
    from jobbot.core.scheduler import SCAN_EVERY_MIN, Scheduler

    db.connect().close()

    print("[mở app lần đầu: KHÔNG được tự chạy]")
    s = Scheduler()
    scans = []
    s.scan_once = lambda: scans.append(time.time())    # đếm, không quét thật
    s.start(); time.sleep(0.3)
    check("mặc định là dừng", s.paused)
    check("state nói rõ là paused", s.state() == "paused")
    check("KHÔNG quét lần nào", scans == [], f"đã quét {len(scans)} lần")
    s.stop()

    print("\n[bật rồi thì nhớ, tắt rồi cũng nhớ]")
    s.resume()
    conn = db.connect()
    check("bật -> ghi vào pref", prefs.flag(conn, prefs.AUTORUN))
    conn.close()
    s.pause()
    conn = db.connect()
    check("tắt -> cũng ghi vào pref", not prefs.flag(conn, prefs.AUTORUN))
    conn.close()

    print("\n[mở app lại khi đã bật: chạy theo lịch, KHÔNG chạy ngay]")
    conn = db.connect(); prefs.set_flag(conn, prefs.AUTORUN, True); conn.close()
    s2 = Scheduler()
    scans2 = []
    s2.scan_once = lambda: scans2.append(time.time())
    s2.start(); time.sleep(0.3)
    check("đọc lại lựa chọn -> không còn dừng", not s2.paused)
    # Đây là bài kiểm quan trọng nhất: BẬT tự quét vẫn KHÔNG có nghĩa là quét
    # ngay lúc mở app. Mốc đếm phải bắt đầu từ lúc mở, không phải từ 0.
    check("vẫn KHÔNG quét ngay lúc mở app", scans2 == [],
          f"đã quét {len(scans2)} lần")
    check("lần quét đầu lùi lại gần đủ một chu kỳ",
          SCAN_EVERY_MIN - 1 <= s2.next_in() // 60 <= SCAN_EVERY_MIN,
          f"còn {s2.next_in() // 60} phút")
    s2.stop()

    print("\n[bấm Chạy ngay thì vẫn chạy, dù đang tắt tự quét]")
    s3 = Scheduler()
    ran = []
    s3.scan_once = lambda: ran.append(1)
    s3.start(); time.sleep(0.1)
    s3.pause()
    s3.scan_once()                                  # người dùng tự bấm
    check("nút tay không bị 'tắt tự quét' chặn", ran == [1])
    s3.stop()

    print("\n[không chạy chồng hai vòng quét]")
    s4 = Scheduler()
    s4.running = True                               # giả vờ đang quét dở
    out = Scheduler.scan_once(s4)
    check("đang quét dở thì bỏ qua yêu cầu mới", out == s4.last_result)
    check("và không đụng vào cờ running", s4.running is True)

    os.environ.pop("JOBBOT_DATA_DIR", None)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
