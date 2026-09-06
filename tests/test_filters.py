"""Test bộ lọc do người dùng điều khiển.  python3 tests/test_filters.py"""

import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db, postings
from jobbot.dashboard import live
from jobbot.dashboard.filters import PER_PAGE, JobFilter
from jobbot.dedup import group
from jobbot.ingest.base import Posting, to_ts

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

Q = lambda **kw: JobFilter.from_query({k: [str(v)] for k, v in kw.items()})

print("\n[đọc URL]")
check("mặc định là 'matched'", Q().show == "matched")
check("giá trị lạ bị vứt", Q(show="'; DROP TABLE--").show == "matched")
check("loc lạ bị vứt", Q(loc="mars").loc == "")
check("sort lạ về mặc định", Q(sort="hack").sort == "score")
check("page âm -> 1", Q(page="-5").page == 1)
check("page không phải số -> 1", Q(page="abc").page == 1)
check("q bị cắt độ dài", len(Q(q="x" * 500).q) == 120)

print("\n[dựng SQL — luôn dùng tham số ràng buộc]")
where, args = Q(q="quant'; DROP TABLE posting;--").where()
check("chuỗi độc đi vào ARGS, không vào SQL", "DROP" not in where and any("drop" in str(a).lower() for a in args))
check("kept=1 khi show=matched", "kept = 1" in Q().where()[0])
check("kept=0 khi show=dropped", "kept = 0" in Q(show="dropped").where()[0])
check("show=all không lọc kept", "kept" not in Q(show="all").where()[0])
check("days sinh mốc thời gian", Q(days="7").where()[1][-1] > 0)

print("\n[dựng URL]")
f = Q(q="quant", loc="london", page="3")
check("giữ bộ lọc khi đổi trang", "q=quant" in f.url(page=4) and "page=4" in f.url(page=4))
check("đổi bộ lọc thì về trang 1", "page" not in f.url(loc="uk"))
check("bỏ giá trị mặc định khỏi URL", f.url(q="", loc="", page=1) == "/jobs")
check("chip tắt được từng cái", any(u == "/jobs?loc=london&page=3" or "q=" not in u
                                    for _, u in f.active()))

print("\n[lọc trên dữ liệu thật]")
with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")
    items = []
    for i, (title, comp, loc, when) in enumerate([
        ("Quantitative Analyst", "Man Group", "London", "2026-09-01T00:00:00+00:00"),
        ("Data Scientist", "Monzo", "London", "2026-01-01T00:00:00+00:00"),
        ("Product Manager", "Acme", "New York", "2026-09-01T00:00:00+00:00"),
    ]):
        p = Posting(source_id=f"s{i}", title=title, company=comp, location=loc, posted_at=when)
        items.append(p)
    postings.save_batch(conn, "greenhouse:test", items)
    conn.execute("UPDATE posting SET kept=0, drop_reason='title does not match'"
                 " WHERE title='Product Manager'")
    conn.commit()
    group.regroup(conn)

    check("mặc định chỉ hiện tin giữ", len(live.jobs(conn, Q())) == 2)
    check("show=dropped hiện tin bị bỏ", len(live.jobs(conn, Q(show="dropped"))) == 1)
    check("show=all hiện hết", len(live.jobs(conn, Q(show="all"))) == 3)
    check("tin bị bỏ mang theo lý do",
          live.jobs(conn, Q(show="dropped"))[0]["drop_reason"] == "title does not match")
    check("tìm theo chữ", len(live.jobs(conn, Q(q="quantitative"))) == 1)
    check("tìm cả tên công ty", len(live.jobs(conn, Q(q="monzo"))) == 1)
    check("lọc theo công ty", len(live.jobs(conn, Q(company="Man Group"))) == 1)
    check("lọc theo địa điểm", len(live.jobs(conn, Q(show="all", loc="london"))) == 2)
    check("lọc ngoài UK", len(live.jobs(conn, Q(show="all", loc="other"))) == 1)
    check("lọc theo ngày", len(live.jobs(conn, Q(days="30"))) == 1)
    check("sắp theo công ty", live.jobs(conn, Q(sort="company"))[0]["company"] == "Man Group")
    check("mặc định sắp theo điểm", Q().sort == "score")
    check("lọc theo ngưỡng điểm sinh SQL đúng", "score >= ?" in Q(band="75").where()[0])
    check("band=none tìm tin không chấm được", "score IS NULL" in Q(band="none").where()[0])

    counts = live.job_counts(conn, Q())
    check("đếm đúng cho từng tab", (counts["matched"], counts["dropped"], counts["all"]) == (2, 1, 3))
    check("facets lấy nguồn thật", live.facets(conn)["sources"] == ["greenhouse"])
    check("trang 2 rỗng khi chỉ có 2 tin", len(live.jobs(conn, Q(page="2"))) == 0)
    conn.close()

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
