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

print("\n[lọc môi giới]")
check("mặc định chỉ hiện chủ việc trực tiếp", "via_agency = 0" in Q().where()[0])
check("'all' thì không lọc", "via_agency" not in Q(via="all").where()[0])
check("'agency' thì chỉ hiện môi giới", "via_agency = 1" in Q(via="agency").where()[0])
check("giá trị lạ -> về mặc định direct", Q(via="hack").via == "direct")

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
# Danh sách việc chuyển vào tab Search — tab Jobs đã bỏ.
check("bỏ giá trị mặc định khỏi URL", f.url(q="", loc="", page=1) == "/search")
check("chip tắt được từng cái", any(u == "/search?loc=london&page=3" or "q=" not in u
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
    conn.execute("UPDATE posting SET kept = 1, drop_reason = ''")
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

print("\n[phân trang phải LỢP KÍN số đếm — không thiếu, không lặp]")
# LỖI THẬT: jobs() cắt trang theo DÒNG rồi mới gộp trùng bằng Python, còn
# job_counts() đếm theo NHÓM. Trên máy thật đầu trang ghi 139 việc, đi hết
# các trang đếm được 144 thẻ: 5 nhóm bị cắt đôi qua ranh giới trang.
with tempfile.TemporaryDirectory() as tmp:
    import jobbot.dashboard.filters as filters_mod
    from jobbot.core.derive import derive
    from jobbot.profile import store

    conn = db.connect(Path(tmp) / "p.db")
    store.save(conn, {"job_titles": "Data Scientist", "seniority": ["grad", "junior"],
                      "markets": ["uk_onsite"], "work_auth": "citizen"}, "t")
    JD = ("Requirements:\n· Python and pandas\n· SQL\n" + "detail " * 80)
    items = []
    for n in range(11):
        # cứ hai tin lại có một tin TRÙNG (cùng công ty + chức danh) -> một nhóm
        # hai dòng, đúng chỗ phân trang hay cắt đôi.
        items.append(Posting(source_id=f"a{n}", title="Data Scientist",
                             company=f"Co{n}", location="London",
                             url=f"https://x/a{n}", description=JD))
        if n % 2 == 0:
            items.append(Posting(source_id=f"b{n}", title="Data Scientist",
                                 company=f"Co{n}", location="London",
                                 url=f"https://y/b{n}", description=JD))
    postings.save_batch(conn, "greenhouse:t", items)
    derive(conn)

    real_per = filters_mod.PER_PAGE
    filters_mod.PER_PAGE = 3                    # trang nhỏ -> nhiều ranh giới
    try:
        total = live.job_counts(conn, Q())["matched"]
        seen, sizes = [], []
        for page in range(1, 40):
            got = live.jobs(conn, Q(page=page))
            if not got:
                break
            sizes.append(len(got))
            seen += [j["id"] for j in got]
        check("đi hết các trang ra ĐÚNG số đếm trên đầu trang", len(seen) == total)
        check("không thẻ nào hiện hai lần", len(seen) == len(set(seen)))
        check("mọi trang đều đầy, trừ trang cuối",
              all(n == 3 for n in sizes[:-1]) and 0 < sizes[-1] <= 3)
        check("tin trùng được gộp, không đếm hai lần", total < len(items))
        merged = [j for j in live.jobs(conn, Q()) if j["merged"] > 1]
        check("nhóm gộp vẫn giữ số dòng của nó", bool(merged))
    finally:
        filters_mod.PER_PAGE = real_per
    conn.close()

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
