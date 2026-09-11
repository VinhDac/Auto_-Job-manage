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


ROUTES = ["/", "/search", "/projects", "/cv", "/profile",
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

    def post_form(path, body):
        return post(path, body.encode())
    check("POST /profile/muc_tieu",
          post("/profile/muc_tieu", b"job_titles=Analyst&markets=uk_onsite") == 200)
    check("POST /profile/import rỗng -> không sập",
          post("/profile/import", b"") in (200, 303))

    print("\n[nút gọi việc nền phải THẬT SỰ tới được trình nghe]")
    # Trình nghe [data-post] nằm ở `document`. Một nút gắn stopPropagation là
    # nút chết: bấm không làm gì, không báo lỗi, không có dấu vết. Đã xảy ra
    # với nút Nộp ở tab Search.
    for page in ("/search", "/cv", "/track", "/projects"):
        _s, body = get(page)
        if _s != 200:
            continue
        for chunk in body.split("data-post=")[1:]:
            head = chunk[:220]
            check(f"{page:<10} nút data-post không chặn lan truyền",
                  "stopPropagation" not in head)

    # Nút trỏ vào route KHÔNG TỒN TẠI cũng là nút chết, và im lặng y hệt:
    # fetch trả 404, .json() nổ, .catch() nuốt. Đối chiếu mọi đích data-post
    # trên trang với danh sách route máy chủ thật sự xử lý.
    import re as _re
    _server = (Path(__file__).resolve().parent.parent
               / "src/jobbot/dashboard/server.py").read_text(encoding="utf-8")
    # Route có thể khai bằng `path == "x"` HOẶC `path in ("x", "y")` —
    # bộ dò chỉ nhận dạng thứ nhất thì báo nhầm route thật là không tồn tại.
    _known = set(_re.findall(r'path == "([^"]+)"', _server))
    for _grp in _re.findall(r'path in \(([^)]*)\)', _server):
        _known |= set(_re.findall(r'"([^"]+)"', _grp))
    _known |= set(_re.findall(r'path\.startswith\("([^"]+)"\)', _server))
    _wired = set()
    for page in ("/search", "/cv", "/track", "/projects", "/"):
        _s, body = get(page)
        if _s != 200:
            continue
        _wired |= set(_re.findall(r"data-post='([^']+)'", body))
        _wired |= set(_re.findall(r'data-post="([^"]+)"', body))
    # Vẽ thẳng tab Quản lí với ĐỦ MỌI loại dòng: DB thử không có dòng nộp nào
    # nên nút "Gửi đơn", "bỏ", "đổi chặng", "quét thư" không hiện, và những nút
    # đó chính là những nút mới nhất — tức là những nút dễ sai đích nhất.
    from jobbot.dashboard.views import track as _track
    from jobbot.track import board as _board
    _row = dict(id=1, stage=_board.DRAFT, company="X", role="R", days=1,
                event_days=None, last_event="", silent=False, cv_file="c.pdf",
                posting_id=9, url="u", score=90)
    for _ready in (False, True):
        for _stage in _board.STAGES:
            _html = _track.render(rows=[{**_row, "stage": _stage}],
                                  asks=[dict(id=2, company="X", company_guess="X",
                                             stage=_stage, kind="rejected",
                                             subject="s", snippet="n", app_id=1)],
                                  counts={"total": 1}, mail_ready=_ready,
                                  mail_address="a@b.c")
            _wired |= set(_re.findall(r"data-post='([^']+)'", _html))
            _wired |= set(_re.findall(r'data-post="([^"]+)"', _html))

    check("có nút data-post để mà kiểm", len(_wired) >= 8, str(sorted(_wired)))
    for _target in sorted(_wired):
        check(f"route {_target} có thật", _target in _known)

    print("\n[PDF: bản in KHÔNG phải bản màn hình thu nhỏ]")
    css = (Path("src/jobbot/dashboard/web/app.css")).read_text()
    rule = css[css.index("@media print"):] if "@media print" in css else ""
    check("có khối @media print", bool(rule))
    # Ẩn `nav` thôi thì chưa đủ: thanh bên là <aside class=side>, nên dấu ◆ và
    # chữ "jobbot" vẫn in ra. Và `.lead` là ghi chú CHO VIN ("Built for … the
    # system selects and orders"), không phải cho nhà tuyển dụng.
    for gone in (".side", ".lead", ".topbar", "button"):
        check(f"bản in giấu {gone}", gone in rule.split("}")[1] or gone in rule)
    check("nền giấy trắng, không nền tối của app", "#fff !important" in rule)
    check("khổ A4", "size: A4" in rule)
    check("không cắt đôi một mục qua hai trang", "break-inside:avoid" in rule)

    check("POST /cv/pdf thiếu id -> 400", post_form("/cv/pdf", "arg=") == 400)
    _s, body = get("/cv")
    check("có nút in hàng loạt", "data-post='/cv/pdf/all'" in body)
    # MỘT tệp mỗi BẢN, không phải mỗi tin: 117 tin nhưng chỉ ~41 bản khác nhau,
    # in đủ 117 là đẻ ra 76 tệp trùng nội dung.
    check("in theo BẢN, không theo tin",
          "In tất cả" in body and " bản ra PDF" in body)
    check("POST /cv/pdf id không phải số -> 400",
          post_form("/cv/pdf", "arg=abc") == 400)

    print("\n[tấm phủ: mỗi form phải đi đúng action của nó]")
    # live.js từng chặn MỌI .setform rồi gửi cứng tới '/settings'. Hậu quả:
    # bấm "Xoá khối" trong tấm phủ soạn CV lại mở ra Cài đặt. Thử bằng
    # form.submit() không lộ, vì cách đó bỏ qua trình nghe submit.
    js = (Path("src/jobbot/dashboard/web/live.js")).read_text()
    check("live.js chỉ chặn form có action /settings",
          "pathname !== '/settings'" in js)
    for url in ("/cv/block?title=", "/cv/draft?id=1"):
        _s, frag = get(url)
        if _s != 200:
            continue
        check(f"{url:<22} form trỏ đúng action của mình",
              "action='/settings'" not in frag)

    print("\n[CV: project xong -> dòng CV]")
    # Lỗi trong một route POST làm ĐỨT kết nối, không trả gì cả — curl báo
    # "empty reply", trình duyệt hiện 404, nhật ký im lặng. Đã xảy ra thật với
    # /cv/draft (thiếu `self.`). Mọi route POST phải được gọi ít nhất một lần.
    check("GET /cv/draft với id lạ -> 404, không sập",
          get("/cv/draft?id=999999")[0] == 404)
    check("POST /cv/draft rỗng -> không sập",
          post_form("/cv/draft", "id=0&head=&line=") in (200, 303))

    print("\n[CV: mọi bản sẽ gửi, xem trước khi gửi]")
    _s, body = get("/cv")
    check("/cv có trong thanh bên", 'href="/cv"' in body or "href='/cv'" in body)
    check("gộp bản trùng, không liệt kê từng tin",
          body.count("class=cvrow") <= 60)
    check("nói THẲNG mức may đo thật, không khoe số bản",
          "giống hệt nhau ở mọi bản" in body)
    check("mỗi dòng trỏ tới bản CV đọc được", "/cv'" in body and "cvrow" in body)
    check("nói ra kỹ năng hồ sơ KHÔNG nói được câu nào",
          "KHÔNG nói được câu nào" in body)

    from jobbot.dashboard import live as live2
    data = live2.cv_versions(db.connect(Path(tmp) / "jobbot.db"))
    if data["versions"]:
        check("phần RIÊNG của mỗi bản không lẫn vào phần lõi",
              all(len(v["only"]) == v["lines"] - data["core"]
                  for v in data["versions"]))
        check("bản nhiều tin nhất đứng đầu",
              [len(v["jobs"]) for v in data["versions"]]
              == sorted((len(v["jobs"]) for v in data["versions"]), reverse=True))

    print("\n[Projects: ba nút phải thật sự làm gì đó]")
    # Cả bốn đường này mới có. Không test qua HTTP thì lỗi kiểu "quên định
    # nghĩa hàm" chỉ lộ ra lúc người dùng bấm — đúng bốn lần đã xảy ra.
    status, body = get("/projects")
    check("/projects vẽ được lưới khoảng trống", "KHOẢNG TRỐNG" in body.upper())
    check("/projects vẽ được kho", ">Kho<" in body or "KHO" in body.upper())
    check("ít tin thì lưới nói thẳng là chưa đo được, không vẽ ô rỗng",
          "chưa có tin nào được chấm điểm" in body)

    # Máy chủ chạy CÙNG tiến trình với bài test, nên hạ ngưỡng ở đây là hạ
    # luôn bên trong nó. Sáu tin mẫu không đủ MIN_DEMAND thật (15 tin), mà
    # dựng đủ 15 tin chỉ để thấy một cái nút là đắt hơn giá trị nó kiểm.
    from jobbot.projects import inventory as inv2
    real_min = inv2.MIN_DEMAND
    inv2.MIN_DEMAND = 1
    _s, body = get("/projects")
    check("mỗi ô trống có một nút Dựng", "data-post='/api/project/build'" in body)
    check("số nút Dựng đúng bằng số ô còn trống",
          body.count("data-post='/api/project/build'") == body.count("gaprow open"))

    check("POST /api/project/build thiếu kỹ năng -> 400",
          post_form("/api/project/build", "arg=") == 400)

    from jobbot.projects.brief import Brief as B2
    conn2 = db.connect(Path(tmp) / "jobbot.db")
    made = inv2.add(conn2, B2(question="Does a cost model change a backtest?",
                              dataset_url="https://x/y.csv",
                              method=["a" * 30] * 3, measure="Sharpe, measured daily",
                              days=2, skills=["backtesting"],
                              deliverable="one notebook"), ["hedge fund"])
    conn2.close()

    _s, body = get("/projects")
    check("đề bài vừa cất hiện trong kho", "Does a cost model change" in body)
    check("kho có nút đổi trạng thái", "data-post='/api/project/state'" in body)
    check("ô được đề bài đó nhận làm thì hiện ◐, KHÔNG hiện ✓",
          f"◐ đề bài #{made}" in body and f"✓ #{made}" not in body)
    check("và ô đó không còn mời dựng thêm lần nữa",
          "data-post='/api/project/build' data-arg='backtesting'" not in body)
    check("làm XONG rồi mới thành dấu ✓",
          post_form("/api/project/state", f"arg={made}:xong") == 200
          and f"✓ #{made}" in get("/projects")[1])
    inv2.MIN_DEMAND = real_min

    check("POST /api/project/state đổi được trạng thái",
          post_form("/api/project/state", f"arg={made}:dang_lam") == 200)
    conn2 = db.connect(Path(tmp) / "jobbot.db")
    check("trạng thái mới thực sự vào cơ sở dữ liệu",
          inv2.all(conn2)[0]["state"] == inv2.DANG_LAM)
    check("POST /api/project/state với id rác -> 400",
          post_form("/api/project/state", "arg=xyz:dang_lam") == 400)

    print("\n[tấm phủ KHÔNG được chắn cả trang khi đang đóng]")
    # LỖI THẬT, và là loại tệ nhất: cả app không bấm được gì.
    # `hidden` chỉ là luật [hidden]{display:none} của trình duyệt.
    # `.sheet{display:flex}` cùng độ ưu tiên nhưng là CSS của mình nên THẮNG —
    # tấm phủ nằm trên cùng vĩnh viễn, phủ đen cả trang, nuốt mọi cú bấm.
    css = get("/static/app.css")[1]
    check("có luật .sheet[hidden] để hidden thật sự ăn",
          ".sheet[hidden]{display:none}" in css)
    # Đặt display trên .sheet mà KHÔNG có luật [hidden] đi kèm là tái hiện lỗi.
    body_rule = css.split(".sheet{")[1].split("}")[0]
    check("và luật đó đứng SAU luật .sheet gốc",
          css.index(".sheet[hidden]") > css.index(".sheet{"))
    check("tấm phủ có nền che thật (nên nếu hở là chắn cả trang)",
          "rgba(0,0,0,.5)" in body_rule or "z-index:60" in body_rule)

    print("\n[sắc độ — thang xám kiểu VS Code]")
    # Lỗi cũ: --mute (màu chữ dùng nhiều nhất app, 84 chỗ) chỉ đạt 3.1:1 trên
    # --panel-2, dưới ngưỡng 4.5 của chữ thường mà lại toàn cỡ 10-12px. Chốt
    # luật ở đây để không ai hạ bậc chữ xuống dưới ngưỡng nữa.
    def _cr(a, b):
        def _lin(c):
            c /= 255
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        def _lum(h):
            h = h.lstrip("#")
            r, g, bl = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            return .2126 * _lin(r) + .7152 * _lin(g) + .0722 * _lin(bl)
        x, y = _lum(a), _lum(b)
        return (max(x, y) + .05) / (min(x, y) + .05)

    import re as _rec
    _cssv = (Path(__file__).resolve().parent.parent
             / "src/jobbot/dashboard/web/app.css").read_text(encoding="utf-8")
    _root = _rec.search(r":root\{(.*?)\n\}", _cssv, _rec.S)
    _var = dict(_rec.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", _root.group(1)))
    _mat = [v for v in ("side", "bg", "panel", "panel-2") if v in _var]
    _txt = [v for v in ("ink", "dim", "mute", "acc", "warn", "bad") if v in _var]
    check("đọc được đủ 4 mặt nền và 6 bậc chữ", len(_mat) == 4 and len(_txt) == 6)
    _low = [f"{t} trên {m} = {_cr(_var[t], _var[m]):.2f}"
            for t in _txt for m in _mat if _cr(_var[t], _var[m]) < 4.5]
    check("mọi bậc chữ đọc được trên mọi mặt nền (>=4.5:1)", not _low, str(_low))
    # Tự chứng: đắp lại giá trị CŨ thì luật trên PHẢI gãy. Không có dòng này
    # thì một hôm nào đó :root đổi tên biến, vòng lặp quét 0 cặp và vẫn xanh.
    check("luật này bắt được đúng lỗi cũ (#717976)",
          _cr("#717976", _var["panel-2"]) < 4.5)
    # Xám phải TRUNG TÍNH — xám ngả màu thì cãi nhau với màu nhấn.
    _amm = {k: max(int(_var[k][i:i + 2], 16) for i in (1, 3, 5))
            - min(int(_var[k][i:i + 2], 16) for i in (1, 3, 5)) for k in _mat}
    check("mặt nền là xám trung tính, không ám màu", max(_amm.values()) == 0, str(_amm))

    # KHUNG NÓI NHỎ, NỘI DUNG NÓI TO. Trước đây ngược: thanh bên 8.1:1 và
    # thanh trạng thái 12.2:1 trong khi nội dung chỉ 6.8:1 — đồ phụ hét to hơn
    # việc đang làm. Chữ khung đo trên --side, chữ nội dung đo trên --panel.
    # BẬC NỀN: tương phản phải dồn vào chỗ LÀM VIỆC, không dồn vào đồ phụ.
    # VS Code chỉ có hai mặt phẳng: khung nằm dưới editor 3.5 điểm L* (yếu),
    # mặt nổi bật lên 8.6 điểm (mạnh). Bản cũ của ta chia đều +3.5 / +3.9 nên
    # thanh bên nặng ngang nội dung — thẻ không nổi lên được.
    def _ls(h):
        def _lin(c):
            c /= 255
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        h = h.lstrip("#")
        r, g, bl = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        y = .2126 * _lin(r) + .7152 * _lin(g) + .0722 * _lin(bl)
        return 116 * y ** (1 / 3) - 16 if y > 0.008856 else 903.3 * y

    def _luat(var):
        """(nền main có đen không, khung có xám-sáng-hơn-main không, thẻ bật bao nhiêu)"""
        return (_ls(var["bg"]) <= 5.0,
                _ls(var["side"]) - _ls(var["bg"]) >= 3.0,
                _ls(var["panel"]) - _ls(var["bg"]))
    _den, _xam, _bat = _luat(_var)
    check(f"nền vùng main là ĐEN (L*{_ls(_var['bg']):.1f} <= 5)", _den)
    check(f"khung phụ là XÁM, sáng hơn main "
          f"(+{_ls(_var['side']) - _ls(_var['bg']):.1f})", _xam)
    check(f"thẻ bật hẳn khỏi nền main (+{_bat:.1f} >= 8)", _bat >= 8.0)
    # Tự chứng: bộ CŨ (khung tối hơn main, thẻ bật yếu) phải phá cả ba luật.
    _cu = {"side": "#161616", "bg": "#1D1D1D", "panel": "#252525"}
    check("luật này bắt được đúng bộ cũ (khung tối hơn main)",
          not any((_luat(_cu)[0], _luat(_cu)[1], _luat(_cu)[2] >= 8.0)))

    _sc = _rec.search(r"\.side,\.statusbar\{(.*?)\}", _cssv, _rec.S)
    _cvar = dict(_rec.findall(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", _sc.group(1)))
    check("khung app khai lại đủ ba bậc chữ của riêng nó",
          sorted(_cvar) == ["dim", "ink", "mute"])
    _khung = max(_cr(v, _var["side"]) for v in _cvar.values())
    _noidung = min(_cr(_var[t], _var["panel"]) for t in ("ink", "dim", "mute"))
    check(f"chữ khung nhạt hơn chữ nội dung ({_khung:.2f} < {_noidung:.2f})",
          _khung < _noidung)
    check("nhưng chữ khung vẫn đọc được (>=4.5:1)",
          min(_cr(v, _var["side"]) for v in _cvar.values()) >= 4.5)
    # Tự chứng: bậc chữ khung CŨ (dùng chung --dim của nội dung) phải phá luật.
    check("luật này bắt được đúng lỗi cũ (khung dùng chung --dim)",
          not _cr(_var["dim"], _var["side"]) < _noidung)

    print("\n[Cài đặt là MENU, không phải tab]")
    _, home = get("/")
    check("Settings không còn trong thanh bên", "href='/settings'" not in home)
    check("có nút bánh răng ở đáy thanh bên", "data-appset" in home)
    check("và có sẵn tấm phủ rỗng để nạp vào", "data-sheet" in home)
    check("tấm phủ mặc định ĐANG ĐÓNG", "class=sheet hidden" in home)

    code, panel = get("/settings")
    check(f"/settings trả 200", code == 200)
    # Trả MẢNH, không phải cả trang: nếu trả cả trang thì nhét vào tấm phủ sẽ
    # lồng nguyên một trang trong trang.
    check("/settings trả MẢNH html, không phải cả trang",
          panel.lstrip().startswith("<form") and "<!doctype" not in panel.lower())

    # Ba núm — và ĐÚNG ba. Trang cũ có 18 dòng mà chỉ 2 dòng là setting thật.
    for name in ("every", "from", "to"):
        check(f"có ô {name}", f"name={name}" in panel)
    check("có nút Lưu", "Lưu" in panel)
    check("nói rõ hậu quả: chỉ đổi CÁCH CHẠY, không đụng phán quyết",
          "lần quét sau" in panel and "không đụng" in panel)
    check("số máy tự báo tách riêng, ghi rõ chỉ để xem",
          "chỉ để xem" in panel.lower() or "CHỈ ĐỂ XEM" in panel)

    # Núm "Máy LLM" ĐÃ BỎ cùng cả đường sinh đề bài bằng LLM. Đề bài giờ do
    # khuôn dựng, nên núm đó không điều khiển gì — mà một cái nút không điều
    # khiển gì còn tệ hơn không có nút: người dùng bấm rồi tưởng app hỏng.
    check("không còn núm giả nào trong Cài đặt",
          "name=engine" not in panel and "JOBBOT_LLM" not in panel)

    print("\n[Cài đặt: lưu xong phải ĂN NGAY, không cần mở lại app]")
    from jobbot.core.scheduler import scan_every_min, human_window
    before = scan_every_min()
    body = b"every=25&from=9&to=21"
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
    for junk in (b"every=abc&from=x&to=y",
                 b"every=-5&from=99&to=-1"):
        req = urllib.request.Request(base.rstrip("/") + "/settings", data=junk)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=25) as r:
            r.read()
        low, high = human_window()
        check(f"giá trị rác {junk[:14].decode():14} -> vẫn hợp lệ",
              5 <= scan_every_min() <= 1440 and 0 <= low <= 23 and 1 <= high <= 24)

    req = urllib.request.Request(base.rstrip("/") + "/settings",
                                 data=f"every={before}&from=8&to=22".encode())
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
    # navfoot ở thanh bên ĐÃ BỎ: nó hiện đúng thông tin mà thanh trạng thái
    # đáy app đang hiện — hai chỗ một sự thật thì có ngày lệch nhau.
    _, _with_status = get("/profile")
    check("thanh trạng thái nằm ở ĐÁY APP, không trong thanh bên",
          "class=statusbar" in _with_status and "class=navfoot" not in _with_status)

    print("\n[thanh của KHÚC — một khối cho mọi chức năng]")
    _, _srch = get("/search")
    check("Search có thanh khúc", "<header class=topbar>" in _srch)
    check("có nút Chạy của riêng nó", "/api/stage/start" in _srch)
    check("có nút Dừng của riêng nó", "/api/stage/stop" in _srch)
    check("nút chạy/dừng mang tên khúc", "data-arg='search'" in _srch)
    check("có nút Điều chỉnh ⚟", "data-settings='/adjust/search'" in _srch)
    check("có số liệu, không phải câu văn", _srch.count("class=metric") >= 3)
    # MỘT viên pill căn giữa, không phải dải kéo hết bề ngang: trên màn 1900px
    # dải đẩy tên khúc sang trái và nút sang phải cách nhau cả gang tay.
    check("có viên thuốc điều khiển", "class=deckpill" in _srch)
    # .pill ĐÃ CÓ SẴN: huy hiệu trạng thái trên bảng Quản lí (.pill.applied,
    # .pill.interview…). Đặt trùng tên là đúng lớp lỗi .frow/.prow đã sửa.
    # Vẽ thẳng view với một dòng mẫu: DB thử không có lần nộp nào nên bảng
    # thật không vẽ huy hiệu, và bài test sẽ xanh mà chẳng kiểm gì.
    from jobbot.dashboard.views import track as _tk
    from jobbot.track import board as _bd2
    _trk = _tk.render(
        rows=[dict(id=1, stage=_bd2.SENT, company="X", role="R", days=1,
                   event_days=None, last_event="", silent=False, cv_file="",
                   posting_id=None, url="", score=0)],
        asks=[], counts={"total": 1}, mail_ready=False, mail_address="")
    check("bảng Quản lí vẫn vẽ huy hiệu .pill", "class='pill " in _trk)
    check("và huy hiệu KHÔNG dính kiểu của viên thuốc",
          "class=deckpill" not in _trk)
    _cssP = (Path(__file__).resolve().parent.parent
             / "src/jobbot/dashboard/web/app.css").read_text(encoding="utf-8")
    check("viên thuốc căn giữa", "align-items:center" in _cssP)
    check("viên thuốc bo tròn", ".deckpill{" in _cssP)
    # NẰM NGANG, không bao giờ xếp cao: cho xuống dòng thì màn hẹp nó phình
    # thành khối 211px, hết còn là viên thuốc.
    _pl = _cssP[_cssP.index(".deckpill{"):_cssP.index(".deckpill{") + 320]
    check("viên thuốc KHÔNG xuống dòng", "flex-wrap:nowrap" in _pl)
    # Màn quá hẹp thì cuộn ngang, KHÔNG giấu nút: một nút bấm không tới được
    # thì cũng như không có.
    check("quá hẹp thì cuộn ngang", "overflow-x:auto" in _pl)
    # Tất cả trong MỘT viên: tên khúc, số liệu, nút. Đẩy số liệu ra ngoài thì
    # thanh vỡ thành ba tầng rời rạc.
    _pillhtml = _srch[_srch.index("class=deckpill"):]
    _pillhtml = _pillhtml[:_pillhtml.index("</div>")]
    check("số liệu nằm TRONG viên thuốc", "class=metric" in _pillhtml)
    check("nút cũng trong viên thuốc", "/api/stage/start" in _pillhtml)
    # `nowrap` trần thì màn hẹp là dòng trạng thái chạy quá mép pill rồi bị
    # cắt cụt giữa chữ.

    print("\n[thanh TRẠNG THÁI đáy app]")
    # Tin CHUNG của cả app, không thuộc tab nào. Dòng "tự động: TẮT · quét lần
    # cuối…" trước nằm trong thanh của tab — sai chỗ: nó không phải số liệu của
    # khúc, nó là trạng thái của app.
    for _pg2 in ("/", "/search", "/track", "/profile"):
        _b2 = get(_pg2)[1]
        check(f"{_pg2} có thanh trạng thái", "class=statusbar" in _b2)
    # Thanh trạng thái chạy HẾT bề ngang, kể cả dưới thanh bên — nó là tin của
    # cả app. Kèm đó thanh bên phải chừa chỗ, không thì nút Cài đặt bị che.
    _cssb = (Path(__file__).resolve().parent.parent
             / "src/jobbot/dashboard/web/app.css").read_text(encoding="utf-8")
    check("thanh trạng thái tràn hết bề ngang",
          ".statusbar{position:fixed;left:0;right:0" in _cssb)
    check("thanh bên chừa chỗ cho nó", "calc(10px + var(--status-h))" in _cssb)
    check("thanh đáy có ô trạng thái sống", "data-state" in _srch)
    check("và ô tin gần nhất", "data-lastmsg" in _srch)
    # Một trang chỉ được nói trạng thái chung MỘT lần. live.js ghi vào MỌI
    # [data-state], nên hai ô là hai dòng chữ y hệt nhau nằm hai đầu màn.
    for _pg3 in ("/", "/search", "/cv", "/track", "/profile", "/projects"):
        _, _b3 = get(_pg3)
        check(f"{_pg3} chỉ có một ô trạng thái", _b3.count("data-state") == 1)
    # live.js đổ vào từ dòng SSE — không luồn tham số qua chục hàm render.
    _js2 = (Path(__file__).resolve().parent.parent
            / "src/jobbot/dashboard/web/live.js").read_text(encoding="utf-8")
    check("live.js có hàm đổ tin", "function setLastMessage" in _js2)
    check("gọi khi có sự kiện mới", _js2.count("setLastMessage(") >= 3)
    check("nội dung không nấp sau thanh đáy", "var(--status-h)" in _cssP)
    # navfoot cũ hiện đúng thông tin đó ở thanh bên — hai chỗ một sự thật.
    _lay2 = (Path(__file__).resolve().parent.parent
             / "src/jobbot/dashboard/layout.py").read_text(encoding="utf-8")
    check("bỏ hẳn navfoot ở thanh bên", "navfoot" not in _lay2)
    check("và bỏ tham số status= đã chết", "status: str" not in _lay2)
    # Hai nút "Chạy ngay"/"Bật tự quét" cũ nằm trên thanh TOÀN APP nhưng chỉ
    # điều khiển đúng khúc Search. Thanh mang danh cả app mà làm việc một khúc.
    check("bỏ hẳn nút toàn app", "data-act=run" not in _srch
          and "data-act=pause" not in _srch)
    # ⚟ dùng LẠI tấm phủ của Cài đặt — mỗi đường mới là một nút có thể chết.
    _cA, _adj = get("/adjust/search")
    check("/adjust/search trả mảnh HTML", _cA == 200 and "Điều chỉnh" in _adj)
    check("và chứa lưới sàng", "/api/sieve" in _adj)
    check("khúc lạ thì 404", get("/adjust/khong-co-that")[0] == 404)
    # Lọc (bấm vài giây một lần) phải ở NGAY trên trang, không giấu vào menu.
    check("bộ lọc vẫn ở trên trang", "?show=" in _srch or "show=" in _srch)

    print("\n[dừng phải dừng THẬT, không phải nút cho có]")
    _run = (Path(__file__).resolve().parent.parent
            / "src/jobbot/scan_runner.py").read_text(encoding="utf-8")
    _li = (Path(__file__).resolve().parent.parent
           / "src/jobbot/ingest/web/linkedin.py").read_text(encoding="utf-8")
    # `stop()` của lịch trình chỉ chặn lần chạy SAU. Một vòng quét chạy 8-16
    # phút vì mở Chrome đọc từng tin — nút Dừng mà không ngắt được là nút chết.
    check("ngắt giữa hai nguồn API", "halt.wanted(STAGE)" in _run)
    check("truyền cờ xuống LinkedIn", "stop=lambda: halt.wanted(STAGE)" in _run)
    check("ngắt trong vòng ĐỌC KỸ (chỗ tốn 8-16 phút)", "đã đọc kỹ" in _li)
    check("ngắt cả trong vòng tìm", "mới xong" in _li)
    _halt = (Path(__file__).resolve().parent.parent
             / "src/jobbot/core/halt.py").read_text(encoding="utf-8")
    # Dừng vòng quét KHÔNG được dừng luôn việc quét thư đang chạy song song.
    check("cờ theo TỪNG khúc, không phải một cờ chung", "stage: str" in _halt)
    _srv = (Path(__file__).resolve().parent.parent
            / "src/jobbot/dashboard/server.py").read_text(encoding="utf-8")
    # Thêm một chức năng mới thì không được đẻ thêm route.
    check("hai route dùng chung cho mọi khúc",
          '"/api/stage/start", "/api/stage/stop"' in _srv)
    check("khúc lạ bị từ chối", 'stage not in STAGES' in _srv)

    print("\n[khung không được bỏ phí — MỌI trang, không riêng trang nào]")
    import re as _re9
    _css9 = (Path(__file__).resolve().parent.parent
             / "src/jobbot/dashboard/web/app.css").read_text(encoding="utf-8")
    _bare = _re9.sub(r"/\*.*?\*/", "", _css9, flags=_re9.S)

    # Lỗi gốc: `.inner{max-width:840px}` chặn cứng MỌI trang kiểu dòng chảy.
    # Đo trên màn 1900px: khung 1684, nội dung 840 -> bỏ trống 844px, ở BỐN
    # trang cùng lúc. Vá một trang là để ba trang kia y nguyên.
    _inner = _re9.search(r"\.inner\{([^}]*)\}", _bare)
    check("có luật .inner", bool(_inner))
    _mw = _re9.search(r"max-width:([^;}]+)", _inner.group(1)) if _inner else None
    check(".inner KHÔNG còn trần cố định",
          bool(_mw) and _mw.group(1).strip() == "none",
          _mw.group(1).strip() if _mw else "không có max-width")
    # Bề rộng là tính chất của NỘI DUNG: chỉ đoạn văn mới cần bề rộng đọc được.
    check("nhưng đoạn văn vẫn giữ bề rộng đọc được",
          bool(_re9.search(r"\.inner p[^{]*\{[^}]*max-width:\d+ch", _bare)))
    # Cờ `wide=` là nút mà mỗi trang phải NHỚ bật — sẽ có trang quên. Đã bỏ.
    _lay = (Path(__file__).resolve().parent.parent
            / "src/jobbot/dashboard/layout.py").read_text(encoding="utf-8")
    check("bỏ hẳn cờ wide (đường dễ quên)", "wide" not in _lay)
    check("và không còn luật CSS .wide", "main.wide" not in _bare)

    # Duyệt THẬT mọi trang trong thanh bên, không chỉ trang vừa sửa.
    _c9, _nav = get("/")
    _pages = set(_re9.findall(r"<a class='navlink[^']*' href='([^']+)'", _nav))
    _pages |= {"/profile/health", "/profile/import", f"/jobs/{job_id}"}
    check("tìm được đủ trang để kiểm", len(_pages) >= 7, str(sorted(_pages)))
    for _pg in sorted(_pages):
        _code, _body = get(_pg)
        if _code != 200:
            check(f"{_pg} mở được", False, f"HTTP {_code}")
            continue
        _m = _re9.search(r"<main class='([^']*)'", _body)
        check(f"{_pg} không mang lớp cố định bề rộng",
              bool(_m) and "wide" not in _m.group(1))

    # Bảng: `width` trên ô chỉ là GỢI Ý khi bảng tự dàn cột — nhãn dài kéo cột
    # ra 650px. Và dàn cột cố định thì Chrome BỎ QUA min()/clamp() (đo được:
    # rơi về 803px), chỉ nhận px hoặc phần trăm.
    check("bảng hồ sơ dàn cột cố định", "table-layout:fixed" in _bare)
    _th = _bare[_bare.index(".sum th{"):_bare.index(".sum th{") + 260]
    check("cột nhãn dùng bề rộng trần, không min()/clamp()",
          "width:340px" in _th and "min(" not in _th and "clamp(" not in _th)
    check("màn hẹp có luật riêng cho cột nhãn", ".sum th{width:40%}" in _bare)

    print("\n[Home đang để trống, chờ thiết kế lại]")
    _, _blank = get("/")
    check("Home vẫn mở được", "Home" in _blank)
    check("và nói rõ là đang trống", "đang trống" in _blank)
    # Gỡ nội dung mà để lại đống code nuôi nó thì mới là bẩn.
    for _gone in ("class=funnel", "class=needs", "class=stats", "class=plot"):
        check(f"không còn {_gone}", _gone not in _blank)
    _live8 = (Path(__file__).resolve().parent.parent
              / "src/jobbot/dashboard/live.py").read_text(encoding="utf-8")
    for _fn in ("def run_status", "def counters", "def needs_you", "def activity",
                "def per_day", "def chances", "def funnel"):
        check(f"live.py đã gỡ {_fn[4:]}", _fn not in _live8)
    check("dashboard/plot.py đã xoá",
          not (Path(__file__).resolve().parent.parent
               / "src/jobbot/dashboard/plot.py").exists())

    print("\n[Search: ba ô — danh sách · lưới lọc · nhật ký dẹt]")
    from jobbot.dashboard.views.runtime import _rows_needed
    check("đếm hàng: nhật ký dưới đáy nên không có ô 'Đang chạy' hàng 1",
          _rows_needed([("a", "", 1, 4), ("b", "", 2, 4)], 3, 0) == 4)

    _, search_html = get("/search")
    _, adj_html = get("/adjust/search")
    check("ô danh sách việc", "Việc tìm được" in search_html)
    check("ô nhật ký dạng dẹt", "class=jflat" in search_html)
    check("tiến độ gộp vào dải nhật ký", "data-progress='search'" in search_html)
    # Lưới sàng đã chuyển vào ⚟ nên cột trái hết việc: danh sách — thứ Vin
    # thật sự đọc — lấy cả bề ngang, nhật ký về dải dẹt dưới đáy.
    check("danh sách ăn cả bề ngang", "Lưới lọc" not in search_html)
    check("nhật ký là dải dưới đáy, không phải ô góc",
          "wid flat corner" not in search_html)

    # Lưới sàng phải SỬA ĐƯỢC — và giờ nó nằm sau nút ⚟, không chiếm chỗ
    # thường trực trên trang. LỌC thì vẫn ở trên trang (bấm vài giây một lần);
    # SÀNG đổi vài tháng một lần và mỗi lần là phán lại toàn kho.
    check("lưới sàng là FORM thật", "form class=sieve" in adj_html)
    check("và KHÔNG còn chiếm chỗ trên trang", "form class=sieve" not in search_html)
    # Chức danh là Ô THẺ, không phải khối chữ: gõ rồi Enter là thêm, bấm ×
    # là bỏ. Khối chữ bắt người dùng tự nhớ luật "mỗi dòng một cái", và một
    # dòng trống hay dấu phẩy thừa là ra chức danh rác.
    check("chức danh là ô thẻ, KHÔNG phải khối chữ",
          "class=tagbox" in adj_html and "<textarea" not in adj_html)
    n_tags = adj_html.count("<span class=tag>")
    check("có ít nhất một thẻ", n_tags > 0)
    check("mỗi thẻ có đúng một dấu × để bỏ",
          adj_html.count("data-untag") == n_tags)
    check("mỗi thẻ mang đúng một giá trị gửi lên",
          adj_html.count("name=job_titles") == n_tags)
    check("nút × là type=button, không gửi nhầm cả form",
          "<button type=button class=untag" in adj_html)
    check("có ô để gõ thêm", "class=taginput" in adj_html)
    check("có ô tích cấp bậc và thị trường",
          "name=seniority" in adj_html and "name=markets" in adj_html)
    check("có nút Áp dụng", "Áp dụng" in adj_html)
    # Nút phải nói TRƯỚC hậu quả, không phải "Lưu" trống không.
    check("nút nói rõ sẽ phán lại bao nhiêu tin", "phán lại" in adj_html)
    check("và nói rõ đây là hồ sơ, sửa là đổi cả điểm",
          "hồ sơ" in adj_html and "đổi cả điểm" in adj_html)

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

    # MỌI trang trong thanh bên. Đã sập trắng vì một tham số thừa ở chỗ gọi
    # (`mail.account(conn)` sau khi hàm bỏ tham số) — 906 bài test xanh mà
    # trang /track chết, vì không bài nào mở nó.
    for page in ("/", "/search", "/track", "/projects", "/cv", "/profile",
                 "/settings"):
        code, body = get(page)
        check(f"{page} mở được", code == 200, f"HTTP {code}")
        check(f"{page} không trả trang lỗi", "Traceback" not in body)

    print("\n[mọi liên kết trong trang phải tới được]")
    _links = set()
    # Không tìm thấy link nào nghĩa là bài test này KHÔNG kiểm gì —
    # tệ hơn không có, vì nó vẫn xanh.
    for _page in ("/", "/search", "/track", "/projects", "/cv", "/profile"):
        _s3, _b3 = get(_page)
        if _s3 != 200:
            continue
        _links |= set(_re2.findall(r"href='(/[^'#?]*)", _b3))
        _links |= set(_re2.findall(r'href="(/[^"#?]*)', _b3))
    for _href in sorted(_links):
        if _href.startswith("/static") or _re2.search(r"/\d+", _href):
            continue
        _c4, _ = get(_href)
        check(f"liên kết {_href} tới được", _c4 in (200, 303), f"HTTP {_c4}")
    check("có liên kết để mà kiểm", len(_links) >= 5, str(len(_links)))

    print("\n[thanh bên: logo và mục Cài đặt ở đáy]")
    _c7, _home = get("/")
    check("mục Cài đặt có trong thanh bên", "navend" in _home)
    # Là <button>, KHÔNG phải <a>: /settings trả về MẢNH HTML cho tấm phủ,
    # link tới đó là ra trang trắng.
    import re as _re7
    _end = _re7.search(r"<div class=navend>(.*?)</div>", _home, _re7.S)
    check("Cài đặt là nút, không phải link", bool(_end) and "<button" in _end.group(1))
    check("và không phải thẻ <a>", bool(_end) and "<a " not in _end.group(1))
    # Dùng CHUNG data-settings với bánh răng trên thanh master: một trình nghe
    # lo cả hai, không thêm đường nào mới để mà chết.
    # Dùng CHUNG `data-settings` với bánh răng trên thanh master: một trình
    # nghe lo cả hai, không thêm đường nào mới để mà chết. Đếm theo VÙNG, không
    # đếm cả trang — vài trang còn nút mở tấm phủ khác cũng dùng thuộc tính đó.
    # Nút Cài đặt KHÔNG dùng chung đường với nút ⚟ của khúc: ⚟ chỉnh khúc,
    # Cài đặt chỉnh cả app. Chung một thuộc tính thì sớm muộn chung luôn nội
    # dung, rồi lại thành "một thanh vừa của app vừa của khúc" như thanh cũ.
    check("mục Cài đặt mang data-appset",
          bool(_end) and "data-appset" in _end.group(1))
    check("và KHÔNG dính vào khung ⚟ của khúc",
          bool(_end) and "data-settings" not in _end.group(1))
    # Bánh răng ĐÃ RỜI thanh trên cùng: Cài đặt (toàn app) về đáy thanh bên,
    # còn thanh trên cùng giờ là thanh của KHÚC đang mở, mang nút ⚟ Điều chỉnh
    # của riêng khúc đó. Một thanh không thể vừa là của app vừa là của khúc.
    # Trang chưa có khúc thì KHÔNG vẽ thanh trên cùng: trạng thái chung đã ở
    # thanh đáy, vẽ thêm dòng y hệt trên đầu là nói hai lần.
    check("trang chưa có khúc thì không có thanh trên cùng",
          "class='topbar" not in _home and "class=runstate" not in _home)
    _, _s2 = get("/search")
    _bar2 = _re7.search(r"<header class=topbar>(.*?)</header>", _s2, _re7.S)
    check("trang có khúc thì thanh mang nút ⚟ của khúc",
          bool(_bar2) and "data-settings='/adjust/search'" in _bar2.group(1))
    _css7 = (Path(__file__).resolve().parent.parent
             / "src/jobbot/dashboard/web/app.css").read_text(encoding="utf-8")
    _, _sv = get("/")
    check("logo là chìa khoá vẽ bằng SVG", "<svg class=logo" in _sv)
    check("ba vòng chìa là vòng THẬT — có lỗ, không phải chấm đặc",
          _sv.count("<circle") == 3 and "fill=none" in _sv)
    check("logo ăn màu từ CSS, không đóng cứng trong hình",
          "currentColor" in _sv and ".logo{" in _css7)
    check("navend bị đẩy xuống đáy", "margin-top:auto" in _css7)

    print("\n[đường PHÁ HOẠI không được là đường mặc định]")
    # Một POST rỗng tới /api/sieve đã XOÁ SẠCH lưới lọc chức danh: mọi tin lọt
    # lưới (đo được 197 -> 4660 tin), tab Search đầy rác, và không có cảnh báo
    # nào. Cùng lớp lỗi với /api/mail/forget xoá app password.
    for _bad in (b"", b"arg=abc", b"seniority=junior"):
        _c5 = post("/api/sieve", _bad)
        check(f"POST rỗng tới /api/sieve bị từ chối ({_bad[:12]!r})", _c5 == 400,
              f"HTTP {_c5}")
    _conn5 = db.connect(Path(tmp) / "jobbot.db")
    _titles5 = (store.load(_conn5).get("job_titles") or "")
    _conn5.close()
    check("lưới lọc còn nguyên sau mấy cú POST đó", bool(_titles5.strip()))

    print("\n[tab CV phải mở NHANH]")
    import time as _t5
    from jobbot.dashboard import live as _live5
    _conn6 = db.connect(Path(tmp) / "jobbot.db")
    _live5._BLOCK_CACHE.clear()
    _t0 = _t5.perf_counter(); _live5.cv_blocks(_conn6); _cold = _t5.perf_counter() - _t0
    _t0 = _t5.perf_counter(); _live5.cv_blocks(_conn6); _warm = _t5.perf_counter() - _t0
    # Đo trên máy Vin: 7,8 giây MỖI LẦN gọi, và tab CV gọi nó mỗi lần mở.
    check("cv_blocks có cache", _warm < _cold / 5 or _warm < 0.01,
          f"lạnh {_cold:.3f}s · ấm {_warm:.3f}s")
    _conn6.close()

    print("\n[thoát HTML — dữ liệu cào về không được thành mã]")
    conn = db.connect(Path(tmp) / "jobbot.db")
    conn.execute("UPDATE posting SET company = ? WHERE kept = 1",
                 ("<script>alert(1)</script>",))
    conn.commit(); conn.close()
    _, hacked = get(f"/jobs/{job_id}")
    check("thẻ script bị thoát", "<script>alert(1)</script>" not in hacked)
    check("và vẫn hiện dạng chữ", "&lt;script&gt;" in hacked)

    print("\n[tên tệp PDF — một bản CV một tệp]")
    # Lỗi thật: Jane Street có HAI bản CV khác nhau cùng ra tên
    # "jane-street-machine-learning-researcher.pdf". Bản sau đè bản trước, và
    # 7 tin thì có tin cầm nhầm CV. In ra 43 bản mà `ls` chỉ đếm được 42 —
    # không ai để ý, vì không có gì báo.
    from jobbot.dashboard import live as _live
    conn = db.connect(Path(tmp) / "jobbot.db")
    plan = _live.cv_pdf_plan(conn)
    names = [item["file"].name for item in plan]
    check("mỗi bản CV một tên tệp riêng", len(names) == len(set(names)),
          f"{len(names)} bản, {len(set(names))} tên")
    covered = [pid for item in plan for pid in item["ids"]]
    check("một tin chỉ thuộc đúng một bản", len(covered) == len(set(covered)))
    check("tra ngược ra đúng tệp",
          all(_live.cv_pdf_for(conn, item["ids"][0]) == item["file"] for item in plan))
    conn.close()

    httpd.shutdown(); httpd.server_close()
    os.environ.pop("JOBBOT_DATA_DIR", None)

print("\n[CSS: hai class cùng tên KHÔNG được đá nhau về bố cục]")
import re as _re2
from collections import Counter as _C
_css = (Path(__file__).resolve().parent.parent
        / "src/jobbot/dashboard/web/app.css").read_text(encoding="utf-8")
_depth, _seen = 0, {}
for _line in _css.splitlines():
    _m = _re2.match(r"\s*(\.[a-zA-Z][\w-]*)\s*\{(.*)$", _line)
    if _m and _depth == 0:
        _disp = _re2.search(r"display\s*:\s*([a-z-]+)", _m.group(2))
        if _disp:
            _seen.setdefault(_m.group(1), set()).add(_disp.group(1))
    _depth += _line.count("{") - _line.count("}")
_clash = {k: v for k, v in _seen.items() if len(v) > 1}
# .frow từng vừa là hàng lọc (flex) vừa là hàng phễu (grid): ô tải CV lên và
# hàng lọc hồ sơ bị bẻ thành lưới 3 cột. .prow tương tự với thanh tiến độ.
check("không class nào có hai kiểu display", not _clash, str(_clash))

print("\n[nút trong form — bấm không được nuốt mất form]")
_js = (Path(__file__).resolve().parent.parent
       / "src/jobbot/dashboard/web/live.js").read_text(encoding="utf-8")
# FORM cũng mang [data-post] và nút Gửi nằm TRONG nó, nên closest() từ nút đi
# ngược lên gặp form. Nhánh nút gán `post.textContent = ...` — gán textContent
# lên một form là XOÁ SẠCH RUỘT NÓ. Bấm Nối một cái là ô nhập biến mất.
check("nhánh nút bỏ qua thẻ FORM", "post.tagName === 'FORM'" in _js)
check("và bỏ qua TRƯỚC khi gán textContent",
      _js.index("post.tagName === 'FORM'") < _js.index("post.textContent = s.note"))
check("form có trình nghe submit riêng", "form[data-post]" in _js)
# Form Cài đặt là trường hợp riêng, không được nuốt mọi form khác.
check("trình nghe Cài đặt vẫn chỉ nhận đúng /settings",
      "!== '/settings'" in _js)
_track = (Path(__file__).resolve().parent.parent
          / "src/jobbot/dashboard/views/track.py").read_text(encoding="utf-8")
check("nút Nối là type=submit, không phải data-post riêng",
      "type=submit" in _track)

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
