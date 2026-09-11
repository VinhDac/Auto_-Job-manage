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

    print("\n[khung giờ qua đêm]")
    from datetime import datetime as _dt
    from jobbot.core import prefs as _prefs
    from jobbot.core.db import connect as _connect
    from jobbot.core.scheduler import in_human_window as _win
    _c = _connect()
    # 22:00–08:00 là khung HỢP LỆ (quét ban đêm). Công thức `low <= h < high`
    # cho ra RỖNG — vòng quét im lặng không chạy giờ nào, không cảnh báo.
    _prefs.put(_c, _prefs.HOURS_FROM, "22"); _prefs.put(_c, _prefs.HOURS_TO, "8")
    _night = [h for h in range(24) if _win(_dt(2026, 9, 10, h, 0))]
    check("khung qua đêm quét được", len(_night) == 10, str(len(_night)))
    check("và đúng các giờ đêm", 23 in _night and 2 in _night and 12 not in _night)
    _prefs.put(_c, _prefs.HOURS_FROM, "8"); _prefs.put(_c, _prefs.HOURS_TO, "22")
    check("khung thường vẫn đúng",
          len([h for h in range(24) if _win(_dt(2026, 9, 10, h, 0))]) == 14)
    # HOURS_TO bị kẹp về [1,24] nên "0/0" ra 0–1; dùng 5/5 mới chạm được
    # nhánh hai-đầu-bằng-nhau.
    _prefs.put(_c, _prefs.HOURS_FROM, "5"); _prefs.put(_c, _prefs.HOURS_TO, "5")
    check("hai đầu bằng nhau = cả ngày",
          len([h for h in range(24) if _win(_dt(2026, 9, 10, h, 0))]) == 24)
    _c.close()

    print("\n[không chạy chồng hai vòng quét]")
    s4 = Scheduler()
    # Giả lập "đang quét dở" bằng chính KHOÁ, không phải một cờ riêng: sự thật
    # nằm ở khoá. Bản cũ dùng `if self.running: ... running = True` — hai bước
    # — nên bấm RUN đúng lúc lịch trình kích hoạt thì cả hai luồng cùng vào.
    s4._gate.acquire()
    try:
        out = Scheduler.scan_once(s4)
        check("đang quét dở thì bỏ qua yêu cầu mới", out == s4.last_result)
        check("và vẫn báo là đang chạy", s4.running is True)
    finally:
        s4._gate.release()
    check("thả khoá thì hết bận", s4.running is False)

    # Cuộc đua thật: hai luồng vào cùng lúc, chỉ MỘT được chạy.
    import threading as _th
    s5 = Scheduler()
    entered = []
    def _slow():
        entered.append(1)
        time.sleep(0.25)
    s5._real = _slow
    orig = Scheduler.scan_once
    def _wrapped(self):
        return orig(self)
    import jobbot.scan_runner as _sr
    _sr.run_scan = lambda: (_slow(), {"summary": "x", "kept": 0, "new": 0})[1]
    threads = [_th.Thread(target=lambda: _wrapped(s5)) for _ in range(2)]
    for t in threads: t.start()
    for t in threads: t.join()
    check("hai luồng cùng lúc -> chỉ một vòng quét chạy", len(entered) == 1,
          str(len(entered)))

    os.environ.pop("JOBBOT_DATA_DIR", None)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
