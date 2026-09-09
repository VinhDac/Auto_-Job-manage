"""Test nhật ký chạy — thứ app 24/7 sống chết bằng nó.

    python3 tests/test_journal.py
"""

import os, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}{' — ' + extra if extra else ''}")


with tempfile.TemporaryDirectory() as tmp:
    os.environ["JOBBOT_DATA_DIR"] = tmp
    from jobbot.core import db
    from jobbot.core.journal import (ERROR, PROJECT, SEARCH, SCORE, SYSTEM,
                                     Journal, RING)

    db.connect().close()                      # dựng bảng audit

    print("[sự kiện: ghi thêm, không sửa]")
    j = Journal()
    j.emit(SEARCH, "bắt đầu quét")
    j.warn(SEARCH, "linkedin bị chặn")
    j.ok(SCORE, "chấm 208 tin")
    check("giữ lại đủ số dòng", len(j.tail(limit=99)) == 3)
    check("mới nhất lên đầu", j.tail(limit=99)[0].text == "chấm 208 tin")
    check("mức được ghi đúng",
          [e.level for e in j.tail(SEARCH, 9)] == ["warn", "info"])

    print("\n[luồng: mỗi tab chỉ thấy việc của mình]")
    check("lọc theo luồng search", len(j.tail(SEARCH, 99)) == 2)
    check("lọc theo luồng score", len(j.tail(SCORE, 99)) == 1)
    check("luồng chưa dùng thì rỗng", j.tail(PROJECT, 99) == [])
    check("không lọc thì thấy tất cả", len(j.tail(None, 99)) == 3)

    print("\n[tiến độ: ghi đè, KHÔNG ghi đĩa]")
    j.progress(SEARCH, "đọc kỹ LinkedIn", 47, 192)
    j.progress(SEARCH, "đọc kỹ LinkedIn", 48, 192)
    check("chỉ giữ giá trị mới nhất", j.running()[SEARCH]["done"] == 48)
    check("tính được phần trăm", j.running()[SEARCH]["percent"] == 25)
    check("tiến độ KHÔNG lẫn vào nhật ký sự kiện", len(j.tail(limit=99)) == 3)
    check("đang chạy thì busy", j.busy())
    j.done(SEARCH)
    check("xong thì xoá thanh tiến độ", SEARCH not in j.running())
    check("và hết busy", not j.busy())
    j.progress(SCORE, "chấm điểm", 5, 0)
    check("không biết tổng thì phần trăm là 0", j.running()[SCORE]["percent"] == 0)
    j.done(SCORE)

    print("\n[đẩy cho giao diện]")
    chan = j.subscribe()
    j.emit(SEARCH, "tin mới")
    j.progress(SEARCH, "đang chạy", 1, 10)
    got = [chan.get_nowait(), chan.get_nowait()]
    check("sự kiện được đẩy đi", got[0]["type"] == "event" and got[0]["text"] == "tin mới")
    check("tiến độ cũng được đẩy đi", got[1]["type"] == "progress")
    check("có kèm luồng để giao diện lọc", got[1]["stream"] == SEARCH)
    j.unsubscribe(chan)
    j.emit(SEARCH, "sau khi rời")
    check("rời rồi thì không nhận nữa", chan.empty())

    print("\n[người xem chậm KHÔNG được làm nghẽn việc đang chạy]")
    # Vòng quét đứng lại vì chờ một cái hàng đợi đầy là hỏng thật; giao diện
    # mất vài dòng là chuyện nhỏ.
    slow = j.subscribe()
    for n in range(400):                       # nhiều hơn maxsize=200
        j.progress(SEARCH, "đổ tràn", n, 400)
    check("hàng đợi đầy thì bỏ tin, không treo", slow.qsize() <= 200)
    check("và việc vẫn chạy tới cuối", j.running()[SEARCH]["done"] == 399)
    j.unsubscribe(slow)
    j.done(SEARCH)

    print("\n[bộ nhớ có trần — chạy 24/7 không được phình]")
    k = Journal()
    for n in range(RING + 250):
        k.emit(SYSTEM, f"dòng {n}", persist=False)
    check(f"giữ tối đa {RING} dòng", len(k.tail(limit=99999)) == RING)
    check("giữ dòng MỚI, bỏ dòng cũ",
          k.tail(limit=1)[0].text == f"dòng {RING + 249}")

    print("\n[còn lại sau khi tắt app]")
    m = Journal()
    m.open()                                # gắn vào DB tạm
    m.emit(PROJECT, "trước khi tắt")
    m.error(PROJECT, "một lỗi cần nhớ")
    after = Journal()                          # "mở app lại"
    after.open()
    texts = [e.text for e in after.tail(PROJECT, 99)]
    check("sự kiện được nạp lại từ đĩa", "trước khi tắt" in texts)
    check("và giữ đúng mức", after.tail(PROJECT, 1)[0].level == ERROR)
    check("gắn lần hai không nhân đôi", after.open() == 0)

    # Dòng đời trước ghi bằng postings.log() chỉ có `kind`, detail rỗng —
    # nạp thẳng thì nhật ký đầy dòng trống trơn chỉ có mỗi giờ.
    conn = db.connect()
    conn.execute("INSERT INTO audit (at, kind, detail) VALUES (?,?,?)",
                 ("2026-01-01T00:00:00+00:00", "scan_started", ""))
    conn.commit(); conn.close()
    legacy = Journal(); legacy.open()
    old_line = [e for e in legacy.tail(limit=999) if e.at.startswith("2026-01-01")]
    check("dòng cũ không có detail thì lấy kind", bool(old_line))
    check("và đọc ra được chữ", old_line and old_line[0].text == "scan started")

    print("\n[chưa gắn vào DB thì KHÔNG được đụng đĩa]")
    # Đây là lý do 24 dòng của bài test lọt vào nhật ký thật: nhật ký mặc
    # định ghi thẳng db_path(), bất kể bài test đang dùng DB tạm nào.
    quiet = Journal()
    quiet.emit(SEARCH, "chỉ trong bộ nhớ")
    check("chưa open() thì không mở kết nối nào", quiet._db() is None)
    check("nhưng vẫn ghi được vào bộ nhớ", len(quiet.tail(SEARCH, 9)) == 1)

    print("\n[nhật ký hỏng KHÔNG được giết việc đang chạy]")
    broken = Journal()
    broken.open()
    broken._conn = "không phải kết nối"        # ép mọi thao tác đĩa nổ
    try:
        broken.emit(SEARCH, "vẫn phải chạy")
        check("ghi đĩa hỏng vẫn emit được", True)
    except Exception as exc:                   # noqa: BLE001
        check("ghi đĩa hỏng vẫn emit được", False, f"{type(exc).__name__}: {exc}")
    check("và dòng đó vẫn có trong bộ nhớ", len(broken.tail(SEARCH, 9)) == 1)

    os.environ.pop("JOBBOT_DATA_DIR", None)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
