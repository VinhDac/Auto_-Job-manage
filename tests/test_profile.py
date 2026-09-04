"""Test M0 — hồ sơ người dùng. Chạy: python3 tests/test_profile.py"""

import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db
from jobbot.profile import store
from jobbot.profile.schema import ROUNDS, all_questions

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")

    check("DB trống -> hồ sơ rỗng", store.load(conn) == {})
    check("DB trống -> chưa được kéo tin", store.can_ingest(conn and store.load(conn)) is False)
    check("DB trống -> vòng cần làm là vòng 1", store.next_unfinished_round({}).id == "dinh_vi")

    v1 = store.save(conn, {"target_roles": ["backend"], "years_real": "1-3"}, "test")
    check("lưu ra phiên bản 1", v1 == 1)
    check("đọc lại đúng", store.load(conn)["target_roles"] == ["backend"])
    check("vòng 1 thiếu câu -> chưa xong", not store.can_ingest(store.load(conn)))

    v2 = store.save(conn, {"markets": ["remote_global"], "doc_language": "en"}, "test")
    answers = store.load(conn)
    check("phiên bản mới", v2 == 2)
    check("câu cũ được mang sang", answers["years_real"] == "1-3")
    check("vòng 1 đủ -> mở cổng ingest", store.can_ingest(answers))
    check("vòng tiếp theo là vòng 2", store.next_unfinished_round(answers).id == "rang_buoc")

    store.save(conn, {"years_real": "3-5"}, "sửa")
    check("sửa thì ghi đè giá trị mới", store.load(conn)["years_real"] == "3-5")
    check("lịch sử giữ đủ 3 phiên bản", len(store.history(conn)) == 3)

    store.save(conn, {"khong_ton_tai": "x"}, "rác")
    check("bỏ qua câu không có trong schema", "khong_ton_tai" not in store.load(conn))

    ids = [q.id for r in ROUNDS for q in r.questions]
    check("không trùng id câu hỏi", len(ids) == len(set(ids)))
    check("mọi câu chọn đều có option", all(
        q.options for q in all_questions().values() if q.kind in ("single", "multi")))
    conn.close()

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
