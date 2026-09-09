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


ROUTES = ["/", "/search", "/projects", "/profile",
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
                 "/queue", "/pipeline", "/stats",      # trang giả đã xoá hẳn
                 "/jobs", "/score"]:                   # tab đã bỏ, đang dựng lại
        status, _ = get(path)
        check(f"{path:24} -> 404", status == 404)

    # Khối "mọi tổ hợp lọc đều phải sống" đã bỏ cùng trang /jobs. Logic lọc
    # KHÔNG mất kiểm: tests/test_filters.py gọi thẳng live.jobs() với đủ tổ
    # hợp, kể cả chuỗi độc và phân trang. Khi danh sách quay lại trong Search,
    # dựng lại khối này để kiểm qua HTTP.

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

    print("\n[Cài đặt là MENU, không phải tab]")
    _, home = get("/")
    check("Settings không còn trong thanh bên", "href='/settings'" not in home)
    check("có nút bánh răng trên thanh trên", "data-settings" in home)
    check("và có sẵn tấm phủ rỗng để nạp vào", "data-sheet" in home)

    code, panel = get("/settings")
    check(f"/settings trả 200", code == 200)
    # Trả MẢNH, không phải cả trang: nếu trả cả trang thì nhét vào tấm phủ sẽ
    # lồng nguyên một trang trong trang.
    check("/settings trả MẢNH html, không phải cả trang",
          panel.lstrip().startswith("<form") and "<!doctype" not in panel.lower())

    # Ba núm — và ĐÚNG ba. Trang cũ có 18 dòng mà chỉ 2 dòng là setting thật.
    for name in ("every", "from", "to", "engine"):
        check(f"có ô {name}", f"name={name}" in panel)
    check("có nút Lưu", "Lưu" in panel)
    check("nói rõ hậu quả: chỉ đổi CÁCH CHẠY, không đụng phán quyết",
          "lần quét sau" in panel and "không đụng" in panel)
    check("số máy tự báo tách riêng, ghi rõ chỉ để xem",
          "chỉ để xem" in panel.lower() or "CHỈ ĐỂ XEM" in panel)

    # Biến môi trường ĐÈ lên lựa chọn ở menu — nếu không nói ra thì người dùng
    # chọn xong mà không có gì đổi, và không hiểu vì sao.
    import os as _os3
    _os3.environ["JOBBOT_LLM"] = "none"
    _, forced = get("/settings")
    check("bị biến môi trường ép -> nói thẳng ra", "JOBBOT_LLM" in forced)
    check("và khoá ô chọn lại, không cho bấm hụt", "select name=engine disabled" in forced)
    _os3.environ.pop("JOBBOT_LLM", None)
    _, free = get("/settings")
    check("bỏ biến đi thì ô chọn dùng được lại",
          "select name=engine disabled" not in free and "JOBBOT_LLM" not in free)

    print("\n[Cài đặt: lưu xong phải ĂN NGAY, không cần mở lại app]")
    from jobbot.core.scheduler import scan_every_min, human_window
    before = scan_every_min()
    body = b"every=25&from=9&to=21&engine=none"
    req = urllib.request.Request(base.rstrip("/") + "/settings", data=body)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=25) as r:
        saved = r.read().decode("utf-8")
    check("lưu xong trả lại mảnh có giá trị MỚI", "value='25'" in saved)
    # Đọc lúc chạy, không phải lúc nạp module — nếu không thì đổi nhịp xong
    # phải khởi động lại app mới ăn.
    check("nhịp quét đổi ngay trong tiến trình", scan_every_min() == 25)
    check("khung giờ cũng vậy", human_window() == (9, 21))

    # Người dùng gõ gì cũng không được làm chết vòng quét nền.
    for junk in (b"every=abc&from=x&to=y&engine=hack",
                 b"every=-5&from=99&to=-1&engine="):
        req = urllib.request.Request(base.rstrip("/") + "/settings", data=junk)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=25) as r:
            r.read()
        low, high = human_window()
        check(f"giá trị rác {junk[:14].decode():14} -> vẫn hợp lệ",
              5 <= scan_every_min() <= 1440 and 0 <= low <= 23 and 1 <= high <= 24)

    req = urllib.request.Request(base.rstrip("/") + "/settings",
                                 data=f"every={before}&from=8&to=22&engine=".encode())
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    urllib.request.urlopen(req, timeout=25).read()

    print("\n[gập thanh bên]")
    _, home_html = get("/")
    check("có nút gập", "data-nav" in home_html)
    # Đọc localStorage phải nằm trong <head>, TRƯỚC khi vẽ. Để cuối trang thì
    # mỗi lần chuyển tab thanh bên bung ra rồi mới co lại — nháy một cái.
    head = home_html.split("</head>")[0]
    check("đọc lựa chọn ngay trong <head>, không nháy", "navmin" in head)
    check("và trước cả <body>", "navmin" not in home_html.split("<body>")[1][:200]
          or home_html.index("navmin") < home_html.index("<body>"))
    import re as _re2
    _navlinks = _re2.findall(r"<a class='navlink[^>]*>", home_html)
    check("mọi mục nav có title để lúc gập còn biết là gì",
          bool(_navlinks) and all("title=" in a for a in _navlinks),
          f"{sum('title=' not in a for a in _navlinks)}/{len(_navlinks)} thiếu")
    check("dòng trạng thái dưới cùng cũng có title",
          "class=navfoot title=" in home_html)
    css = get("/static/app.css")[1]
    check("gập thì ĐỔI --nav-w, không chỉnh sidebar rời khỏi nội dung",
          ":root.navmin{--nav-w:" in css)
    check("gập thì giấu chữ, giữ icon",
          ".navmin .navlink span{display:none}" in css)

    print("\n[Search: ba ô — danh sách · lưới lọc · nhật ký dẹt]")
    from jobbot.dashboard.views.runtime import _rows_needed
    check("đếm hàng: nhật ký dưới đáy nên không có ô 'Đang chạy' hàng 1",
          _rows_needed([("a", "", 1, 4), ("b", "", 2, 4)], 3, 0) == 4)

    _, search_html = get("/search")
    check("ô danh sách việc", "Việc tìm được" in search_html)
    check("ô lưới lọc", "Lưới lọc" in search_html)
    check("ô nhật ký dạng dẹt", "class=jflat" in search_html)
    check("tiến độ gộp vào dải nhật ký", "data-progress='search'" in search_html)
    # Nhật ký nằm GÓC DƯỚI TRÁI, không kéo hết bề ngang — nó là thứ liếc mắt,
    # chiếm cả chiều ngang là ăn mất chỗ của danh sách.
    check("nhật ký ở góc, không full width",
          "wid flat corner" in search_html)
    check("và ghim đúng ô (1,2)", "grid-column:1 / span 1;grid-row:2" in search_html)
    # Danh sách kéo suốt hai hàng -> chạm đáy màn hình.
    check("danh sách việc kéo suốt chiều cao",
          "grid-column:2 / span 1;grid-row:1 / span 2" in search_html)
    # Cột lưới rộng hơn kiểu chia đều ba cột (366px).
    check("cột lưới được nới rộng", "minmax(360px, 1fr) 1.75fr" in search_html)

    # Lưới lọc phải SỬA ĐƯỢC — không phải bảng đọc như bản trước.
    check("lưới lọc là FORM thật", "form class=sieve" in search_html)
    # Chức danh là Ô THẺ, không phải khối chữ: gõ rồi Enter là thêm, bấm ×
    # là bỏ. Khối chữ bắt người dùng tự nhớ luật "mỗi dòng một cái", và một
    # dòng trống hay dấu phẩy thừa là ra chức danh rác.
    check("chức danh là ô thẻ, KHÔNG phải khối chữ",
          "class=tagbox" in search_html and "<textarea" not in search_html)
    # KHÔNG so với PROFILE của fixture: khối POST phía trên đã sửa job_titles,
    # nên số chức danh lúc này khác lúc nạp. Kiểm tính nhất quán nội tại —
    # bao nhiêu thẻ thì bấy nhiêu dấu × và bấy nhiêu giá trị gửi lên.
    n_tags = search_html.count("<span class=tag>")
    check("có ít nhất một thẻ", n_tags > 0)
    check("mỗi thẻ có đúng một dấu × để bỏ",
          search_html.count("data-untag") == n_tags)
    check("mỗi thẻ mang đúng một giá trị gửi lên",
          search_html.count("name=job_titles") == n_tags)
    check("nút × là type=button, không gửi nhầm cả form",
          "<button type=button class=untag" in search_html)
    check("có ô để gõ thêm", "class=taginput" in search_html)
    check("có ô tích cấp bậc và thị trường",
          "name=seniority" in search_html and "name=markets" in search_html)
    check("có nút Áp dụng", "Áp dụng" in search_html)
    # Nút phải nói TRƯỚC hậu quả, không phải "Lưu" trống không.
    check("nút nói rõ sẽ phán lại bao nhiêu tin", "phán lại" in search_html)
    check("và nói rõ đây là hồ sơ, sửa là đổi cả điểm",
          "hồ sơ" in search_html and "đổi cả điểm" in search_html)

    # Nút XEM tách khỏi lưới: bấm là đổi ngay, không qua Áp dụng.
    check("nút XEM là link, không nằm trong form",
          "class='vchip" in search_html
          and search_html.index("class=jlist") > search_html.index("class=vbar"))
    check("nút XEM trỏ về /search, không phải /jobs đã xoá",
          "href='/search?" in search_html and "href='/jobs?" not in search_html)

    # Badge nguồn — thứ nói cách nào tìm ra tin nào.
    check("mỗi dòng có badge nguồn",
          "class='src api'" in search_html or "class='src chrome'" in search_html)
    check("badge ghi rõ chữ chrome / api",
          ">api<" in search_html or ">chrome<" in search_html)

    print("\n[Search: đổi cách xem KHÔNG cần Áp dụng]")
    _, dropped = get("/search?show=dropped")
    check("xem được tin đã bỏ", "bỏ vì" in dropped)
    check("và kèm lý do bỏ thật",
          "title does not match" in dropped or "senior level" in dropped)
    for q in ("?show=all", "?chance=likely", "?via=all", "?band=75",
              "?sort=company", "?q=%27%20OR%201%3D1--", "?page=99"):
        code, body = get("/search" + q)
        check(f"/search{q:24} {code}", code == 200, body[:60])

    print("\n[Search: phân trang — 132 việc không được kẹt ở 50]")
    # Không có nút sang trang thì 82 việc còn lại có tồn tại cũng như không.
    import re as _re3
    import jobbot.dashboard.filters as _filters
    rows = lambda html: len(_re3.findall(r"class='jrow", html))
    real_per = _filters.PER_PAGE
    _filters.PER_PAGE = 2            # fixture chỉ có vài tin -> ép nhiều trang
    _, p1 = get("/search?show=all")
    _, p2 = get("/search?show=all&page=2")
    check("trang 1 đầy", rows(p1) > 0)
    check("có nút sang trang", "class=pager" in p1 and "sau →" in p1)
    check("trang 2 ra thẻ KHÁC trang 1", rows(p2) > 0 and p1 != p2)
    check("nói rõ đang ở trang mấy trên mấy", "trang 1/" in p1 and "trang 2/" in p2)
    _, far = get("/search?page=9999")
    check("trang vượt quá thì rỗng, không sập", far and rows(far) == 0)
    _filters.PER_PAGE = real_per

    print("\n[trang chi tiết một tin PHẢI sống dù tab Jobs đã bỏ]")
    # /jobs danh sách bỏ rồi, nhưng /jobs/<id> là chỗ đọc VÌ SAO một tin được
    # chấm ngần ấy điểm — danh sách mới trong Search sẽ trỏ vào đây.
    code, detail = get(f"/jobs/{job_id}")
    check("chi tiết một tin vẫn mở được", code == 200, detail[:80])
    check("và hiện tin thật của DB", "Man Group" in detail or "Monzo" in detail)
    check("kèm bằng chứng từng yêu cầu", "requirement" in detail.lower()
          or "yêu cầu" in detail.lower() or "evidence" in detail.lower())
    for sub in ("cv", "project"):
        code, _ = get(f"/jobs/{job_id}/{sub}")
        check(f"/jobs/<id>/{sub} vẫn sống", code == 200)

    print("\n[thoát HTML — dữ liệu cào về không được thành mã]")
    conn = db.connect(Path(tmp) / "jobbot.db")
    conn.execute("UPDATE posting SET company = ? WHERE kept = 1",
                 ("<script>alert(1)</script>",))
    conn.commit(); conn.close()
    _, hacked = get(f"/jobs/{job_id}")
    check("thẻ script bị thoát", "<script>alert(1)</script>" not in hacked)
    check("và vẫn hiện dạng chữ", "&lt;script&gt;" in hacked)

    httpd.shutdown(); httpd.server_close()
    os.environ.pop("JOBBOT_DATA_DIR", None)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
