"""Test tầng suy diễn — tính lại được, gắn phiên bản, một giao dịch.

    python3 tests/test_derive.py
"""

import sqlite3, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db, postings, versions
from jobbot.core.derive import derive, rebuild, stale_count
from jobbot.ingest.base import Posting, strip_html
from jobbot.profile import store

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

PROFILE = {"job_titles": "Quantitative Analyst\nData Scientist",
           "seniority": ["grad", "junior"], "markets": ["uk_onsite"],
           "work_auth": "citizen"}

def fresh(tmp):
    conn = db.connect(Path(tmp) / "t.db")
    store.save(conn, PROFILE, "test")
    # Nguồn thật bóc HTML TRƯỚC khi giao cho save_batch (xem linkedin.py), nên
    # fixture cũng phải làm vậy — đưa thẳng HTML vào là dựng ra một thế giới
    # không tồn tại, và bài test bên dưới sẽ kiểm nhầm thứ.
    RAW_A = "<p>Requirements:</p><ul><li>Strong Python and SQL</li></ul>"
    RAW_B = "<p>Manage products</p>"
    items = [
        Posting(source_id="a", title="Quantitative Analyst", company="Man Group",
                location="London", description=strip_html(RAW_A), raw_body=RAW_A),
        Posting(source_id="b", title="Product Manager", company="Acme",
                location="London", description=strip_html(RAW_B), raw_body=RAW_B),
    ]
    postings.save_batch(conn, "test", items)
    return conn

print("\n[tầng raw thật sự raw]")
with tempfile.TemporaryDirectory() as tmp:
    conn = fresh(tmp)
    body = conn.execute("SELECT body FROM raw_posting WHERE source_id='a'").fetchone()[0]
    # So body với description chỉ nói "hai chuỗi khác nhau" — yếu. Điều cần
    # bảo đảm là body ĐÚNG BẰNG chuỗi đã đưa vào, không sứt một ký tự.
    check("raw giữ NGUYÊN VĂN từng ký tự",
          body == "<p>Requirements:</p><ul><li>Strong Python and SQL</li></ul>")
    stripped = conn.execute(
        "SELECT description FROM posting WHERE title='Quantitative Analyst'"
    ).fetchone()[0]
    check("bản đã bóc thì sạch thẻ", "<li>" not in stripped and "<p>" not in stripped)
    check("và giữ được dấu gạch đầu dòng", "·" in stripped)
    conn.close()

print("\n[gắn phiên bản]")
with tempfile.TemporaryDirectory() as tmp:
    conn = fresh(tmp)
    check("tin mới nạp -> cần phán", stale_count(conn) == 2)
    derive(conn)
    check("phán xong -> hết cũ", stale_count(conn) == 0)

    real = versions.FILTER_RULES
    versions.FILTER_RULES = "đổi-luật"
    check("ĐỔI LUẬT -> tự phát hiện cần tính lại", stale_count(conn) == 2)
    derive(conn)
    check("tính lại xong -> hết cũ", stale_count(conn) == 0)
    versions.FILTER_RULES = real
    check("trả lại luật cũ -> lại thành cần tính lại", stale_count(conn) == 2)
    derive(conn)

    store.save(conn, {"salary_floor": "£50,000"}, "đổi hồ sơ")
    check("ĐỔI HỒ SƠ -> tự phát hiện cần tính lại", stale_count(conn) == 2)
    derive(conn)
    check("xong -> hết cũ", stale_count(conn) == 0)
    conn.close()

print("\n[lọc và chấm]")
with tempfile.TemporaryDirectory() as tmp:
    conn = fresh(tmp)
    result = derive(conn)
    check("giữ đúng tin khớp chức danh", result["kept"] == 1)
    check("số đếm là TỔNG đang giữ, không phải phần vừa phán",
          derive(conn)["kept"] == 1)
    row = conn.execute("SELECT kept, drop_reason FROM posting"
                       " WHERE title='Product Manager'").fetchone()
    check("tin không khớp -> bỏ, có lý do", row["kept"] == 0 and row["drop_reason"])
    check("tin giữ được chấm điểm", result["scored"] == 1)
    check("ghi lại luật đã dùng để chấm", conn.execute(
        "SELECT scored_rules FROM posting WHERE kept=1").fetchone()[0] == versions.SCORE_RULES)
    conn.close()

print("\n[dựng lại từ raw]")
with tempfile.TemporaryDirectory() as tmp:
    conn = fresh(tmp)
    derive(conn)
    # giả lập bộ bóc HTML hỏng: mô tả bị phá
    conn.execute("UPDATE posting SET description = 'RÁC'")
    conn.commit()
    check("mô tả đã hỏng", conn.execute(
        "SELECT description FROM posting LIMIT 1").fetchone()[0] == "RÁC")
    rebuild(conn)
    fixed = conn.execute("SELECT description FROM posting"
                         " WHERE title='Quantitative Analyst'").fetchone()[0]
    check("dựng lại từ raw -> mô tả trở lại", "Python" in fixed and "RÁC" not in fixed)
    check("và không còn thẻ HTML", "<li>" not in fixed)
    conn.close()

print("\n[phán quyết phải CŨ ĐI khi đầu vào đổi]")
# Ba lỗi thật, cùng một gốc: điểm chỉ gắn phiên bản LUẬT, không gắn phiên bản
# HỒ SƠ, và mô tả về muộn không xoá dấu phiên bản nào cả. Hậu quả trên máy
# thật: 72/204 tin đang giữ đứng nguyên score=NULL vì chúng được chấm lúc mô
# tả còn rỗng, và derive(force=True) cũng không gỡ ra được.
with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")
    store.save(conn, dict(PROFILE, skills_strong="Python"), "v1")
    LATE = ("Requirements:\n· Python and pandas\n· SQL\n· Machine learning\n"
            + "detail " * 80)

    postings.save_batch(conn, "s", [Posting(source_id="x", title="Data Scientist",
        company="Monzo", location="London", url="u", description="")])
    derive(conn)
    check("chấm lúc chưa có mô tả -> nói thẳng là không chấm được",
          conn.execute("SELECT score_conf FROM posting").fetchone()[0] == "none")

    postings.save_batch(conn, "s", [Posting(source_id="x", title="Data Scientist",
        company="Monzo", location="London", url="u", description=LATE)])
    check("mô tả về muộn -> tin tự thành cần tính lại", stale_count(conn) == 1)
    derive(conn)
    first = conn.execute("SELECT score, score_conf FROM posting").fetchone()
    check("và được chấm lại bằng mô tả mới", first[0] is not None and first[1] != "none")

    store.save(conn, {"skills_strong": "Python, pandas, SQL, machine learning"}, "v2")
    check("đổi hồ sơ -> điểm cũ tự thành cần tính lại", stale_count(conn) == 1)
    derive(conn)
    second = conn.execute("SELECT score FROM posting").fetchone()[0]
    check("và điểm đổi theo hồ sơ mới", second > first[0])
    check("tính xong thì không còn gì cũ", stale_count(conn) == 0)

    # force phải xuyên qua CẢ vòng chấm, không chỉ vòng lọc
    conn.execute("UPDATE posting SET score = 1")
    conn.commit()
    derive(conn, force=True)
    check("force=True chấm lại cả tin không cũ",
          conn.execute("SELECT score FROM posting").fetchone()[0] == second)
    conn.close()

with tempfile.TemporaryDirectory() as tmp:
    conn = fresh(tmp)
    derive(conn)
    check("chấm xong thì sạch", stale_count(conn) == 0)
    conn.execute("UPDATE posting SET scored_rules = 'luật cũ' WHERE kept = 1")
    conn.commit()
    check("stale_count thấy luật CHẤM đổi, không chỉ luật LỌC", stale_count(conn) > 0)
    conn.close()

print("\n[một giao dịch]")
with tempfile.TemporaryDirectory() as tmp:
    conn = fresh(tmp)
    before = conn.execute("SELECT COUNT(*) FROM posting WHERE kept=1").fetchone()[0]

    import jobbot.core.derive as d
    real_score = d.score_job
    d.score_job = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("hỏng giữa chừng"))
    try:
        derive(conn)
        check("lỗi giữa chừng phải ném ra", False)
    except RuntimeError:
        check("lỗi giữa chừng ném ra ngoài", True)
    d.score_job = real_score

    after = conn.execute("SELECT COUNT(*) FROM posting WHERE kept=1").fetchone()[0]
    check("hỏng giữa chừng -> KHÔNG ghi nửa vời", before == after)
    check("và vẫn còn cần tính lại", stale_count(conn) == 2)
    conn.close()

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
