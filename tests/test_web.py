"""Smoke test tầng web — thứ đáng lẽ phải có từ đầu.

Trong một phiên làm việc, tầng web sập trắng BỐN lần:
    settings 500  cột attempted/failed thiếu trong câu GROUP BY
    jobs 500      biến `chance` dùng trước khi gán
    jobs 500      job['cv_changes'] đã bị bỏ khỏi tầng dữ liệu
    projects 500  view gọi hàm chưa tồn tại

Không lần nào bị test bắt, vì KHÔNG test nào gọi hàm render và KHÔNG test nào
bấm vào server. Cả bốn đều là lỗi một dòng, và một smoke test bắt được cả bốn.

    python3 tests/test_web.py
"""

import sys, tempfile, threading, urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db, postings
from jobbot.ingest.base import Posting
from jobbot.profile import store

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}{' — ' + extra if extra else ''}")

PROFILE = {
    "job_titles": "Quantitative Analyst\nData Scientist",
    "markets": ["uk_onsite"], "work_auth": "citizen",
    "seniority": ["grad", "junior"], "years_real": "0-1",
    "full_name": "Test User", "email": "t@example.com",
    "education": "MSc Computational Finance — Somewhere, 2026",
    "certifications": "CFA Level I",
    "skills_strong": "Python, pandas, SQL",
    "cv_text": ("TEST USER\nLondon, UK · t@example.com\n"
                "EXPERIENCE\nAnalyst — Acme Jan 2025 – Present\n"
                "I built pipelines in Python and SQL across 17 datasets.\n"
                "SELECTED PROJECTS\nThing — a small study of validation.\n"
                "EDUCATION\nMSc Computational Finance — Somewhere 2025 – 2026\n"
                "TECHNICAL SKILLS\nProgramming — Python, SQL.\n"),
}

def seeded(path: Path):
    conn = db.connect(path)
    store.save(conn, PROFILE, "test")
    items = [
        Posting(source_id="a", title="Quantitative Analyst", company="Man Group",
                location="London", url="https://x/a",
                description="Requirements:\n· Strong Python and pandas\n"
                            "· A degree in a quantitative discipline\n"
                            "· Comfortable with SQL\n" + "detail " * 80,
                raw_body="<p>Requirements</p>"),
        Posting(source_id="b", title="Data Scientist", company="Monzo",
                location="London", url="https://x/b",
                description="What we're looking for:\n· Python and machine learning\n"
                            "· Time series analysis\n· SQL\n" + "detail " * 80),
        Posting(source_id="c", title="Product Manager", company="Acme",
                location="Berlin", url="https://x/c", description="unrelated " * 60),
        # Ba tin dưới đây có mặt để tầng project ĐẺ RA nhóm: dưới MIN_JOBS thì
        # cluster.build trả về rỗng, trang /projects không in liên kết nào, và
        # bài test đi-theo-liên-kết ở dưới sẽ không kiểm được gì cả.
        Posting(source_id="d", title="Data Scientist", company="Wintermute",
                location="London", url="https://x/d",
                description="Requirements:\n· Machine learning in production\n"
                            "· Python and PyTorch\n· Time series forecasting\n"
                            + "detail " * 80),
        Posting(source_id="e", title="Quantitative Analyst", company="Cubist Systematic",
                location="London", url="https://x/e",
                description="Requirements:\n· Machine learning research\n"
                            "· Alpha research and backtesting\n· Python\n"
                            + "detail " * 80),
        Posting(source_id="f", title="Data Scientist", company="Ebury",
                location="London", url="https://x/f",
                description="Requirements:\n· Alpha research exposure\n"
                            "· Time series analysis\n· SQL and Excel\n"
                            + "detail " * 80),
    ]
    postings.save_batch(conn, "greenhouse:test", items)
    from jobbot.core.derive import derive
    derive(conn)
    return conn


ROUTES = ["/", "/search", "/jobs", "/score", "/projects", "/profile",
          "/profile/muc_tieu", "/profile/import", "/profile/health",
          "/settings", "/api/profile", "/api/state"]

print("\n[mọi route phải trả 200 và KHÔNG có traceback]")
with tempfile.TemporaryDirectory() as tmp:
    import os
    os.environ["JOBBOT_DATA_DIR"] = tmp
    conn = seeded(Path(tmp) / "jobbot.db")
    job_id = conn.execute("SELECT id FROM posting WHERE kept=1 LIMIT 1").fetchone()[0]
    conn.close()

    from jobbot.dashboard.server import serve
    httpd, base = serve(port=8791)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def get(path):
        try:
            with urllib.request.urlopen(base.rstrip("/") + path, timeout=25) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:                       # noqa: BLE001
            return 0, f"{type(e).__name__}: {e}"

    for path in ROUTES + [f"/jobs/{job_id}", f"/jobs/{job_id}/cv",
                          f"/jobs/{job_id}/project"]:
        status, body = get(path)
        check(f"{path:24} {status}", status == 200, body[:90])
        if status == 200 and path != "/api/profile":
            check(f"{path:24} không lộ traceback",
                  "Traceback" not in body and "<class '" not in body)

    print("\n[404 đúng cách, không sập]")
    for path in ["/nope", "/jobs/999999", "/profile/khong-co", "/projects/khong-co",
                 "/queue", "/pipeline", "/stats"]:     # trang giả đã xoá hẳn
        status, _ = get(path)
        check(f"{path:24} -> 404", status == 404)

    print("\n[bộ lọc: mọi tổ hợp đều phải sống]")
    for q in ["?show=dropped", "?show=all", "?chance=likely", "?chance=unlikely",
              "?via=all", "?via=agency", "?band=75", "?band=none", "?days=7",
              "?sort=company", "?sort=title", "?sort=old", "?page=99",
              "?q=quant&loc=london&days=30&sort=title&band=60&chance=possible",
              "?q=%27%20OR%201%3D1--", "?page=-5", "?show=HACK&sort=HACK"]:
        status, body = get("/jobs" + q)
        check(f"/jobs{q[:44]:46} {status}", status == 200, body[:70])

    print("\n[POST không được sập]")
    def post(path, data=b""):
        try:
            req = urllib.request.Request(base.rstrip("/") + path, data=data)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:                            # noqa: BLE001
            return 0
    check("POST /profile/muc_tieu",
          post("/profile/muc_tieu", b"job_titles=Analyst&markets=uk_onsite") == 200)
    check("POST /profile/import rỗng -> không sập",
          post("/profile/import", b"") in (200, 303))

    print("\n[mọi liên kết trang tự vẽ ra đều phải mở được]")
    # Khoá cụm project là chữ thật ('machine learning'), trình duyệt mã hoá
    # khoảng trắng thành %20, còn server thì so khớp chuỗi thô -> 404.
    # Tự bịa đường dẫn trong test sẽ không bao giờ bắt được lỗi này; phải đi
    # theo đúng cái href mà trang in ra.
    import re as _re
    seen, broken = set(), []
    for src in ("/", "/jobs", "/projects", "/settings", "/profile"):
        _, html = get(src)
        for href in _re.findall(r"href=['\"]?(/[^'\" >]*)", html):
            if href.startswith("/static") or href in seen:
                continue
            seen.add(href)
            status, _body = get(href)
            if status != 200:
                broken.append((src, href, status))
    check(f"đi hết {len(seen)} liên kết", len(seen) > 15, f"chỉ thấy {len(seen)}")
    check("không liên kết nào hỏng", not broken, "; ".join(
        f"{a} -> {b} ({c})" for a, b, c in broken[:5]))

    print("\n[dữ liệu THẬT, không phải mock]")
    _, jobs_html = get("/jobs")
    # mock.py đã bị xoá hẳn — không còn dữ liệu bịa nào trong app để mà lẫn.
    # Vẫn giữ bài kiểm: trang phải hiện đúng tin trong DB.
    check("Jobs hiện tin thật của DB", "Wintermute" in jobs_html)
    check("và hiện đủ các công ty đã nạp",
          all(c in jobs_html for c in ("Man Group", "Monzo", "Ebury")))
    _, home = get("/")
    check("Home không còn banner dữ liệu giả", "mockbar" not in home)
    check("Jobs không còn banner dữ liệu giả", "mockbar" not in jobs_html)

    print("\n[thoát HTML — dữ liệu cào về không được thành mã]")
    conn = db.connect(Path(tmp) / "jobbot.db")
    conn.execute("UPDATE posting SET company = ? WHERE kept = 1",
                 ("<script>alert(1)</script>",))
    conn.commit(); conn.close()
    _, hacked = get("/jobs")
    check("thẻ script bị thoát", "<script>alert(1)</script>" not in hacked)
    check("và vẫn hiện dạng chữ", "&lt;script&gt;" in hacked)

    httpd.shutdown(); httpd.server_close()
    os.environ.pop("JOBBOT_DATA_DIR", None)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
