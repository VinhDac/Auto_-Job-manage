"""Test bước 1 — lọc theo hồ sơ và gộp trùng.  python3 tests/test_ingest.py"""

import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db, postings
from jobbot.dedup import group
from jobbot.ingest import filter as jf
from jobbot.ingest.base import Posting, norm_company, norm_title, strip_html

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

def P(title, company="Acme", location="London", remote=False):
    return Posting(source_id="x", title=title, company=company,
                   location=location, remote=remote)

PROFILE = {"job_titles": "Quantitative Analyst\nData Scientist\nGraduate Analyst",
           "seniority": ["grad", "junior"], "markets": ["uk_onsite", "uk_remote"]}

print("\n[chuẩn hoá]")
check("bỏ đuôi công ty", norm_company("Monzo Bank Ltd") == norm_company("Monzo Bank"))
check("bỏ ngoặc trong chức danh", norm_title("Analyst (London)") == "analyst")
check("bỏ mã tin", norm_title("Analyst - REQ1042") == "analyst")
check("bỏ thẻ HTML", strip_html("<p>a<br>b</p>").replace("\n", " ").strip() == "a b")

print("\n[lọc]")
keep, why = jf.judge(P("Quantitative Analyst"), PROFILE)
check("khớp chức danh -> giữ", keep)
check("giải thích được vì sao giữ", "matched target title" in why)

keep, why = jf.judge(P("Product Manager"), PROFILE)
check("không khớp -> bỏ", not keep and "does not match" in why)

# LỖI ĐÃ TỪNG CÓ: 'analyst' nằm trong JUNIOR_WORDS làm mọi tin Senior lọt qua
for t in ["Senior Data Scientist", "Senior Quantitative Analyst", "Head of Data Scientist"]:
    keep, why = jf.judge(P(t), PROFILE)
    check(f"bỏ cấp cao: {t}", not keep and "senior level" in why)

keep, _ = jf.judge(P("Graduate Analyst to Senior Analyst"), PROFILE)
check("tin ghi cả grad lẫn senior -> vẫn giữ", keep)

keep, why = jf.judge(P("Data Scientist", location="New York"), PROFILE)
check("ngoài thị trường -> bỏ", not keep and "outside your markets" in why)

keep, _ = jf.judge(P("Data Scientist", location="London, United Kingdom"), PROFILE)
check("nhiều địa điểm có London -> giữ", keep)

keep, _ = jf.judge(P("Data Scientist", location="Remote - Europe", remote=True), PROFILE)
check("remote châu Âu -> giữ", keep)

keep, why = jf.judge(P("Anything At All"), {})
check("chưa có job_titles -> giữ hết", keep and "no job_titles" in why)

print("\n[cache + gộp trùng]")
with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")
    batch = [P("Quantitative Analyst", "Monzo Bank Ltd"),
             P("Quantitative Analyst", "Monzo Bank"),      # cùng việc, tên khác
             P("Data Scientist", "Wise")]
    for i, item in enumerate(batch):
        item.source_id = f"s{i}"
    seen, new = postings.save_batch(conn, "test", batch)
    check("ghi lần đầu", (seen, new) == (3, 3))

    seen, new = postings.save_batch(conn, "test", batch)
    check("chạy lại KHÔNG ghi trùng (đây là cache)", (seen, new) == (3, 0))
    check("số tin không đổi", postings.count(conn) == 3)

    # LỖI ĐÃ SỬA: cache chặn cả việc bổ sung. Vòng quét nhanh ghi tin không mô tả,
    # vòng đọc kỹ lấy được mô tả nhưng không ghi vào đâu được.
    deep = P("Quantitative Analyst", "Monzo Bank Ltd")
    deep.source_id, deep.description = "s0", "x" * 900
    seen, new = postings.save_batch(conn, "test", [deep])
    check("bổ sung KHÔNG tạo dòng mới", (seen, new) == (1, 0))
    got = conn.execute("SELECT p.description FROM posting p"
                       " JOIN raw_posting r ON p.raw_id = r.id"
                       " WHERE r.source_id = 's0'").fetchone()[0]
    check("mô tả được ghi vào tin đã có", len(got) == 900)

    deep2 = P("Quantitative Analyst", "Monzo Bank Ltd")
    deep2.source_id, deep2.description = "s0", "ngắn hơn nhiều"
    postings.save_batch(conn, "test", [deep2])
    kept_long = conn.execute("SELECT p.description FROM posting p"
                             " JOIN raw_posting r ON p.raw_id = r.id"
                             " WHERE r.source_id = 's0'").fetchone()[0]
    check("KHÔNG đè mô tả dài bằng mô tả ngắn", len(kept_long) == 900)

    # kept mặc định 0 (chưa phán) — vòng lọc thật mới bật lên
    conn.execute("UPDATE posting SET kept = 1, drop_reason = ''")
    conn.commit()
    n_rows, n_groups = group.regroup(conn)
    check("gộp Monzo Bank Ltd + Monzo Bank", (n_rows, n_groups) == (3, 2))

    groups = group.groups(conn)
    merged = next(g for g in groups if g["count"] == 2)
    check("nhóm gộp giải thích được nguồn", merged["sources"] == ["test"])

    postings.log(conn, "test_event", "chi tiết")
    check("nhật ký ghi được", len(postings.recent_audit(conn)) == 1)
    conn.close()

print("\n[địa điểm khớp theo TỪ, không theo chuỗi con]")
from jobbot.ingest.filter import location_ok as _loc
_P = lambda loc, co="", rm=False: Posting(source_id="x", title="t", company=co,
                                          location=loc, remote=rm)
for _loc_text, _co in [("London", ""), ("Manchester, UK", ""),
                       ("United Kingdom", ""), ("Edinburgh", "")]:
    check(f"giữ {_loc_text!r}", _loc(_P(_loc_text, _co), []))
# 17 tin thật lọt qua vì 'uk' nằm trong 'ukraine', 'gb' nằm trong 'gbagada'
for _loc_text, _co in [("Kyiv, Ukraine", ""), ("Köln", "teamZUKUNFT gGmbH"),
                       ("Paris", "Bigblue"), ("Bremen", "GBC Group"),
                       ("Gbagada, Lagos", "")]:
    check(f"loại {_loc_text!r} {_co}", not _loc(_P(_loc_text, _co), []))
check("remote toàn cầu vẫn giữ", _loc(_P("Anywhere", "", True), []))

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
