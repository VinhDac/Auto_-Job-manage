"""Test M0 — hồ sơ người dùng. Chạy: python3 tests/test_profile.py"""

import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db
from jobbot.profile import store
from jobbot.profile.schema import INGEST_GATE, SECTIONS, all_questions, section_by_id
from jobbot.dashboard.server import _form_to_answers

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

print("\n[schema]")
qs = all_questions()
ids = [q.id for s in SECTIONS for q in s.questions]
check("không trùng id câu hỏi", len(ids) == len(set(ids)))
check("mọi câu chọn đều có option", all(
    q.options for q in qs.values() if q.kind in ("single", "multi")))
check("cổng ingest tồn tại trong schema", all(q in qs for q in INGEST_GATE))
check("job_titles là câu tự do, không phải danh sách cố định",
      qs["job_titles"].kind == "longtext" and not qs["job_titles"].options)
check("phần project là tuỳ chọn", section_by_id("project").optional)
check("work_auth nằm trong phần mục tiêu, không phải danh tính",
      any(q.id == "work_auth" for q in section_by_id("muc_tieu").questions))
check("không còn lựa chọn riêng của thị trường VN",
      not any(o.value.startswith("vn_") for q in all_questions().values() for o in q.options))
check("không câu bắt buộc nào nằm ngoài cổng ingest",
      {q.id for q in qs.values() if q.required} == set(INGEST_GATE))

print("\n[lưu trữ]")
with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")

    check("DB trống -> hồ sơ rỗng", store.load(conn) == {})
    check("DB trống -> chưa tìm được", not store.can_ingest({}))
    check("nêu đúng cái còn thiếu", store.missing_for_ingest({}) == list(INGEST_GATE))

    store.save(conn, {"job_titles": "Backend Engineer"}, "t")
    check("thiếu markets + work_auth -> vẫn chặn",
          store.missing_for_ingest(store.load(conn)) == ["markets", "work_auth"])

    store.save(conn, {"markets": ["uk_remote"], "work_auth": "citizen"}, "t")
    answers = store.load(conn)
    check("đủ 3 câu -> mở cổng", store.can_ingest(answers))
    check("câu cũ được mang sang", answers["job_titles"] == "Backend Engineer")
    check("lịch sử giữ 2 phiên bản", len(store.history(conn)) == 2)

    store.save(conn, {"khong_ton_tai": "x"}, "rác")
    check("bỏ qua câu ngoài schema", "khong_ton_tai" not in store.load(conn))

    check("phần kế tiếp đúng thứ tự", store.next_section("muc_tieu").id == "rang_buoc")
    check("phần cuối -> hết", store.next_section(SECTIONS[-1].id) is None)
    conn.close()

print("\n[đọc form]")
a = _form_to_answers({"markets": ["uk_remote", "HACK"],
                      "markets__other": ["Ireland, Netherlands"]}, "muc_tieu")
check("bỏ giá trị không có trong option", "HACK" not in a["markets"])
check("giữ giá trị hợp lệ", "uk_remote" in a["markets"])
check("ô tự do được gộp vào", a["markets"] == ["uk_remote", "Ireland", "Netherlands"])

b = _form_to_answers({"work_auth__other": ["Graduate visa, hết hạn 03/2027"]}, "muc_tieu")
check("câu chọn-một cũng nhận ô tự do", b["work_auth"] == "Graduate visa, hết hạn 03/2027")

c = _form_to_answers({"job_titles": ["  Backend Engineer\nSWE  "]}, "muc_tieu")
check("text được cắt khoảng trắng", c["job_titles"] == "Backend Engineer\nSWE")



print("\n[cổng chặn phải NÓI RA, không lặng lẽ bỏ cuộc]")
# Người dùng mới bấm Chạy khi hồ sơ trống: trước đây run_scan `return` lặng lẽ,
# API vẫn đáp "đang chạy…", nhật ký trống, không tin nào về — ngồi chờ vô tận.
import os as _os
_tmp = tempfile.mkdtemp()
_os.environ["JOBBOT_DB"] = str(Path(_tmp) / "trong.db")
try:
    from jobbot.core import journal as _journal
    from jobbot import scan_runner as _sr
    _conn = db.connect()
    db.migrate(_conn)
    _journal.log.open()
    _noi = []
    _kq = _sr.run_scan(log=_noi.append, chrome_sources=False, deep=False)
    check("hồ sơ trống thì từ chối quét", _kq["ok"] is False)
    check("và NÓI RA lý do", bool(_noi) and "hồ sơ chưa đủ" in _noi[0])
    check("lý do nêu đúng tên câu còn thiếu",
          bool(_noi) and all(all_questions()[q].text[:20] in _noi[0]
                             for q in _kq["missing"]))
    _dong = _conn.execute(
        "SELECT COUNT(*) FROM audit WHERE level='warn' AND detail LIKE '%chưa quét được%'"
    ).fetchone()[0]
    check("và ghi vào nhật ký", _dong >= 1)
finally:
    _os.environ.pop("JOBBOT_DB", None)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
