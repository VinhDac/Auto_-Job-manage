"""Dữ liệu THẬT từ DB.

mock.py đã bị xoá hẳn — không còn số bịa nào trong app.
Đó là lý do trang không phải sửa gì khi chuyển từ giả sang thật.

Đã nối thật:  run_status · counters · jobs · job_detail · activity
Còn dùng giả: proposals · pipeline · projects · stats   (bước 4-6)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..core import postings
from ..dedup import group


STALE_DAYS = 45          # quá ngần này thì nhiều khả năng đã tuyển xong


def _age_days(ts: int) -> int | None:
    """Tin đăng bao nhiêu ngày rồi. None = không biết ngày."""
    if not ts:
        return None
    return int((datetime.now(timezone.utc).timestamp() - ts) // 86400)


def _ago(stamp: str) -> str:
    """Nguồn trả ngày theo 2 kiểu: ISO (Greenhouse/Lever) và Unix (Arbeitnow)."""
    if not stamp:
        return ""
    try:
        then = (datetime.fromtimestamp(int(stamp), timezone.utc)
                if str(stamp).isdigit() else datetime.fromisoformat(stamp))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, OSError, OverflowError):
        return ""
    seconds = (datetime.now(timezone.utc) - then).total_seconds()
    if seconds < 90:
        return "just now"
    if seconds < 5400:
        return f"{int(seconds // 60)} min ago"
    if seconds < 172800:
        return f"{int(seconds // 3600)} hours ago"
    return f"{int(seconds // 86400)} days ago"


def run_status(conn: sqlite3.Connection) -> dict:
    runs = postings.last_runs(conn)
    failed = [f"{r['source']} — {r['error'][:60]}" for r in runs if not r["ok"]]
    last = max((r["at"] for r in runs), default="")
    return {
        "state": "idle" if runs else "never run",
        "last_scan": _ago(last) if last else "never",
        "next_scan": "manual — run scripts/scan.py",
        "window": "08:00 – 22:00 (human-paced sources)",
        "sources_ok": sum(1 for r in runs if r["ok"]),
        "sources_total": len(runs),
        "sources_failed": failed or ["Adzuna GB — no API key (biggest UK source)"],
    }


def counters(conn: sqlite3.Connection) -> list[dict]:
    total = postings.count(conn)
    kept = postings.count(conn, kept_only=True)
    unique = postings.count_groups(conn)
    strong = int(conn.execute("SELECT COUNT(*) FROM posting WHERE kept=1 AND score >= 75").fetchone()[0])
    return [
        {"value": f"{total:,}", "label": "Postings pulled", "note": "all sources"},
        {"value": f"{kept:,}", "label": "Match your titles", "note": f"{total - kept:,} filtered out"},
        {"value": f"{unique:,}", "label": "Unique jobs", "note": f"{kept - unique} duplicates merged"},
        {"value": f"{strong}", "label": "Scored 75+", "note": "strong matches"},
        {"value": "—", "label": "Applications", "note": "step 5"},
        {"value": "—", "label": "Replies", "note": "step 6"},
    ]


def per_day(conn: sqlite3.Connection, days: int = 14) -> list[tuple[str, int]]:
    """Mỗi ngày lấy về bao nhiêu tin MỚI — theo lúc CÀO VỀ, không phải lúc đăng.

    Dùng raw_posting.fetched_at vì đây là câu hỏi "máy làm được gì mỗi ngày",
    chứ không phải "thị trường đăng gì mỗi ngày". Ngày không có tin vẫn phải
    có cột 0, nếu không biểu đồ nói dối về nhịp chạy.
    """
    rows = dict(conn.execute(
        "SELECT substr(fetched_at, 1, 10) AS d, COUNT(*) FROM raw_posting"
        " WHERE d >= date('now', ?) GROUP BY d", (f"-{days - 1} days",)).fetchall())
    out = []
    for back in range(days - 1, -1, -1):
        day = conn.execute("SELECT date('now', ?)", (f"-{back} days",)).fetchone()[0]
        out.append((day[8:10] + "/" + day[5:7], rows.get(day, 0)))
    return out


def chances(conn: sqlite3.Connection) -> list[tuple[str, int, str]]:
    """Phân bố "có cửa không" — trả lời câu hỏi thật, không phải điểm khớp."""
    got = dict(conn.execute(
        "SELECT realism, COUNT(*) FROM posting WHERE kept = 1 GROUP BY realism").fetchall())
    return [("likely", got.get("likely", 0), "hi"),
            ("possible", got.get("possible", 0), "mid"),
            ("unlikely", got.get("unlikely", 0), "lo")]


def funnel(conn: sqlite3.Connection) -> list[dict]:
    """Phễu: mỗi bậc là một câu SQL đếm được, không bậc nào là số bịa.

    Bậc nào chưa làm thì ghi thẳng 'chưa làm' — để số 0 trần thì đọc ra là
    "đã chạy mà không ra gì", sai hẳn nghĩa.
    """
    one = lambda sql: int(conn.execute(sql).fetchone()[0])
    return [
        {"name": "tải về", "n": one("SELECT COUNT(*) FROM posting"), "todo": False},
        {"name": "qua bộ lọc", "n": one("SELECT COUNT(*) FROM posting WHERE kept=1"),
         "todo": False},
        {"name": "việc duy nhất",
         "n": one("SELECT COUNT(DISTINCT COALESCE(group_id, CAST(id AS TEXT)))"
                  " FROM posting WHERE kept=1"), "todo": False},
        {"name": "chấm được",
         "n": one("SELECT COUNT(*) FROM posting WHERE kept=1 AND score IS NOT NULL"),
         "todo": False},
        {"name": "đáng nộp",
         "n": one("SELECT COUNT(*) FROM posting WHERE kept=1 AND score>=70"
                  " AND realism!='unlikely'"), "todo": False},
        {"name": "đã gửi", "n": 0, "todo": True},
        {"name": "có hồi âm", "n": 0, "todo": True},
    ]


def jobs(conn: sqlite3.Connection, flt) -> list[dict]:
    """Lọc theo ý người dùng, RỒI mới gộp trùng — gộp trước thì lọc sai nhóm.

    LỖI ĐÃ SỬA: gộp bằng Python SAU khi đã LIMIT theo DÒNG. Trang thì cắt theo
    dòng, còn số đếm trên đầu trang lại đếm theo NHÓM, nên hai bên không bao
    giờ khớp: trên máy thật đầu trang ghi 139 việc, đi hết các trang đếm được
    144 thẻ — 5 nhóm bị cắt đôi qua ranh giới trang và hiện thành hai thẻ.
    Gộp phải xảy ra TRONG SQL, trước khi cắt trang.
    """
    where, args = flt.where()
    per, offset = flt.limit()
    rows = conn.execute(
        "SELECT * FROM ("
        "  SELECT *,"
        "         COUNT(*) OVER (PARTITION BY grp) AS merged,"
        "         GROUP_CONCAT(source) OVER (PARTITION BY grp) AS all_sources,"
        # Đại diện nhóm = tin chấm cao nhất, không phải tin gặp trước.
        "         ROW_NUMBER() OVER (PARTITION BY grp"
        "                            ORDER BY score DESC NULLS LAST, id ASC) AS rn"
        f"    FROM (SELECT *, COALESCE(group_id, CAST(id AS TEXT)) AS grp"
        f"            FROM posting{where})"
        f") WHERE rn = 1 ORDER BY {flt.order()} LIMIT ? OFFSET ?",
        [*args, per, offset]).fetchall()

    out = []
    for row in rows:
        sources = list(dict.fromkeys((row["all_sources"] or "").split(",")))
        out.append({
            "id": str(row["id"]),
            "title": row["title"], "company": row["company"],
            "location": row["location"] or "not stated",
            "salary": row["salary"] or "not stated",
            "score": row["score"],
            "confidence": row["score_conf"],
            "posted": _ago(row["posted_at"]) if row["posted_at"] else "",
            "age_days": _age_days(row["posted_ts"]),
            "sources": [s for s in sources if s],
            "merged": row["merged"],
            "state": "new" if row["kept"] else "dropped",
            "via_agency": bool(row["via_agency"]),
            "realism": row["realism"], "realism_why": row["realism_why"],
            "deadline": row["deadline"],
            "drop_reason": row["drop_reason"],
            "url": row["url"],
        })
    return out


def job_counts(conn: sqlite3.Connection, flt) -> dict:
    """Số lượng cho từng lựa chọn 'Show' — người dùng thấy trước khi bấm."""
    out = {}
    for value, _label in (("matched", ""), ("dropped", ""), ("all", "")):
        where, args = type(flt)(**{**flt.__dict__, "show": value}).where()
        out[value] = int(conn.execute(
            f"SELECT COUNT(DISTINCT COALESCE(group_id, CAST(id AS TEXT)))"
            f" FROM posting{where}", args).fetchone()[0])
    return out


def facets(conn: sqlite3.Connection) -> dict:
    """Giá trị có thật trong DB để đổ vào dropdown — không bịa lựa chọn rỗng."""
    sources = [r["s"] for r in conn.execute(
        "SELECT DISTINCT substr(source, 1, CASE WHEN instr(source,':')>0"
        " THEN instr(source,':')-1 ELSE length(source) END) AS s"
        " FROM posting ORDER BY s")]
    companies = [(r["company"], r["n"]) for r in conn.execute(
        "SELECT company, COUNT(*) n FROM posting WHERE kept=1"
        " GROUP BY company ORDER BY n DESC, LOWER(company) LIMIT 40")]
    return {"sources": sources, "companies": companies}


def job_detail(conn: sqlite3.Connection, job_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM posting WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    same = conn.execute(
        "SELECT source, url FROM posting WHERE group_id = ? ORDER BY id",
        (row["group_id"] or str(row["id"]),)).fetchall()
    return {
        "id": str(row["id"]), "title": row["title"], "company": row["company"],
        "location": row["location"] or "not stated",
        "salary": row["salary"] or "not stated",
        "score": row["score"], "confidence": row["score_conf"],
        "realism": row["realism"], "realism_why": row["realism_why"],
        "deadline": row["deadline"],
        "posted": _ago(row["posted_at"]) if row["posted_at"] else "",
        "sources": sorted({r["source"] for r in same}),
        "merged": len(same), "url": row["url"],
        "jd": row["description"] or "(no description from this source)",
        "requirements": _reqs(row),
        "explain": json.loads(row["score_json"]) if row["score_json"] else None,
        "score_json": row["score_json"],
        "project": None,                        # bước 4
    }


def _reqs(row) -> list[dict]:
    """Yêu cầu trong JD kèm bằng chứng — hình dạng đúng như views/jobs.py cần."""
    if not row["score_json"]:
        return []
    data = json.loads(row["score_json"])
    return [{"text": r["text"], "met": r["met"], "must": r["must"],
             "evidence": r["evidence"] or "—"} for r in data.get("requirements", [])]


def needs_you(conn: sqlite3.Connection) -> list[dict]:
    """Chỉ nói những việc CÓ THẬT. Chưa tới bước nào thì nói thẳng chưa tới."""
    out: list[dict] = []
    unique = postings.count_groups(conn)

    # Số liệu lỗi thời phải báo TRƯỚC mọi thứ khác — đọc số cũ mà tưởng mới
    # thì mọi quyết định phía sau đều dựa trên nền sai.
    waiting = llm_waiting(conn)
    if waiting:
        out.append({
            "kind": "approve",
            "text": f"{waiting} project brief request(s) waiting on Claude",
            "href": "/projects",
            "note": "The engine is set to answer in-session. Open a Claude Code session "
                    "and the queued request gets answered; or switch the engine in Settings.",
        })

    state = health(conn)
    if state["stale"]:
        out.append({
            "kind": "warn",
            "text": f"{state['stale']:,} postings were judged by older rules",
            "href": "/settings",
            "note": "Your profile or the matching rules changed. What you see below "
                    "was decided before that — the next scan re-judges them.",
        })
    for run in state["broken"]:
        out.append({
            "kind": "warn",
            "text": f"Source failing: {run['source']}",
            "href": "/settings",
            "note": run["error"][:130] or "no reason recorded",
        })

    if postings.count(conn) == 0:
        out.append({"kind": "approve", "text": "No postings yet — run the first scan",
                    "href": "/settings", "note": "python3 scripts/scan.py"})
        return out

    # Dòng này từng viết "waiting to be scored — scoring is step 2" và ở nguyên
    # đó rất lâu sau khi bước 2 xong. Chữ cứng trên màn hình mà không tính từ dữ
    # liệu thì nó chỉ đúng vào đúng ngày viết ra.
    worth = int(conn.execute(
        "SELECT COUNT(*) FROM posting WHERE kept = 1 AND via_agency = 0"
        " AND score >= 70 AND realism IN ('likely','possible')").fetchone()[0])
    strong = int(conn.execute(
        "SELECT COUNT(*) FROM posting WHERE kept = 1 AND via_agency = 0"
        " AND realism = 'likely'").fetchone()[0])
    unscored = int(conn.execute(
        "SELECT COUNT(*) FROM posting WHERE kept = 1 AND score IS NULL").fetchone()[0])

    if worth:
        out.append({
            "kind": "approve",
            "text": f"{worth} jobs are worth a look — {strong} of them are a real shot",
            "href": "/jobs?chance=likely",
            "note": "Direct employers only, scored 70+, and the posting does not rule "
                    "you out on a PhD or years of experience.",
        })
    if unscored:
        out.append({
            "kind": "scan",
            "text": f"{unscored} postings still have no description to judge from",
            "href": "/jobs?band=none",
            "note": "The deep-read pass has not reached them. Run "
                    "python3 scripts/scan.py to fetch the full text.",
        })
    out.append({
        "kind": "mail",
        "text": "Adzuna GB is off — the biggest UK source",
        "href": "/settings",
        "note": "Free key at developer.adzuna.com, about 2 minutes. Without it, UK "
                "graduate schemes are largely invisible to the system.",
    })
    return out


def activity(conn: sqlite3.Connection) -> list[dict]:
    kind_map = {"scan_started": "scan", "scan_finished": "scan",
                "source_failed": "warn"}
    return [
        {"time": _ago(r["at"]), "kind": kind_map.get(r["kind"], "check"),
         "text": f"{r['kind'].replace('_', ' ')}" + (f" — {r['detail']}" if r["detail"] else "")}
        for r in postings.recent_audit(conn, 12)
    ]


# ---------------------------------------------------------------- settings

CHROME_SOURCES = {"efinancialcareers", "linkedin"}


def sources(conn: sqlite3.Connection) -> list[dict]:
    """Mọi nguồn, kèm loại (api hay chrome) và lần chạy gần nhất."""
    counts = {r["source"]: r["n"] for r in conn.execute(
        "SELECT source, COUNT(*) n FROM posting GROUP BY source")}
    runs = {r["source"]: r for r in postings.last_runs(conn)}

    out = []
    for name in sorted(set(counts) | set(runs)):
        family = name.split(":")[0]
        run = runs.get(name)
        out.append({
            "name": name,
            "kind": "chrome" if family in CHROME_SOURCES else "api",
            "on": bool(run and run["ok"]),
            "last": _ago(run["at"]) if run else "never",
            "found": counts.get(name, 0),
            "note": (run["error"][:60] if run and not run["ok"] else ""),
        })
    out.sort(key=lambda s: (-s["found"], s["name"]))
    return out


def _warn(text: str) -> str:
    return f"<span class=warn-t>{text}</span>"


def chrome_settings(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """Câu hỏi Chrome gửi đi. Đây là cách tìm DUY NHẤT có truy vấn thật."""
    from ..core.scheduler import HUMAN_WINDOW
    from ..ingest.web.linkedin import PAUSE, PER_PAGE
    from ..profile import store as pstore

    answers = pstore.load(conn)
    titles = [t.strip() for t in (answers.get("job_titles") or "").splitlines()
              if t.strip()]
    return [
        ("Chức danh gửi đi",
         f"{min(len(titles), 5)}/{len(titles)} " + _warn("code cắt còn 5")
         if len(titles) > 5 else str(len(titles))),
        ("Địa điểm", "London " + _warn("cứng trong code")),
        ("Cấp bậc", ", ".join(answers.get("seniority") or []) or "—"),
        ("Mỗi chức danh", f"4 trang × {PER_PAGE} tin"),
        ("Nghỉ giữa hai tin", f"{PAUSE[0]}–{PAUSE[1]} giây"),
        ("Khung giờ người", f"{HUMAN_WINDOW[0]}:00 – {HUMAN_WINDOW[1]}:00"),
        ("Từ khoá kỹ năng", _warn("khai rồi nhưng không gửi đi")),
    ]


def api_settings(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """API KHÔNG có câu hỏi — nó tải trọn board rồi mới lọc.

    Nên BỘ LỌC chính là câu hỏi của nó: chức danh nào tính là khớp, cấp bậc
    nào nhận, địa điểm nào giữ. Đúng bộ tiêu chí đang hiện thành các nút lọc
    ở tab Jobs — chỉ khác tầm ảnh hưởng:

        ở đây      quyết định GIỮ hay BỎ  -> đổi là phải phán lại 4.488 tin
        ở tab Jobs quyết định HIỆN hay không -> đổi chỉ là đổi màn hình
    """
    from ..core.postings import FAIL_THRESHOLD
    from ..ingest.filter import UK_WORDS
    from ..profile import store as pstore
    from ..scan_runner import load_boards, seed_boards

    answers = pstore.load(conn)
    titles = [t.strip() for t in (answers.get("job_titles") or "").splitlines()
              if t.strip()]
    boards = load_boards(conn)
    mine = {s for v in seed_boards().values() for s in v}
    total = len({s for v in boards.values() for s in v})
    agencies = int(conn.execute(
        "SELECT COUNT(*) FROM posting WHERE kept = 1 AND via_agency = 1").fetchone()[0])

    return [
        ("Board đang quét", f"{total} — trong đó {len(mine)} bạn tự chọn"),
        ("Danh sách tự chọn", "config/boards.toml"),
        ("Nguồn hỏng quá bao nhiêu thì coi là chết", f"{int(FAIL_THRESHOLD * 100)}%"),

        ("— BỘ LỌC = CÂU HỎI —", ""),
        ("Chức danh phải khớp", f"{len(titles)} chức danh trong hồ sơ"),
        ("Cấp bậc nhận", ", ".join(answers.get("seniority") or []) or "—"),
        ("Địa điểm giữ", f"{len(UK_WORDS)} từ khoá UK "
                         + _warn("bỏ qua ô Thị trường của hồ sơ")),
        ("Môi giới", f"đánh dấu, KHÔNG bỏ — đang giữ {agencies} tin"),
        ("Cùng bộ tiêu chí này ở tab Jobs", "chỉ lọc HIỂN THỊ, không đổi giữ/bỏ"),
    ]

def score_hist(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """Phân bố điểm theo dải 10. Cột nào cao thì phần lớn tin nằm ở đó."""
    got = dict(conn.execute(
        "SELECT (score / 10) * 10 AS band, COUNT(*) FROM posting"
        " WHERE kept = 1 AND score IS NOT NULL GROUP BY band").fetchall())
    return [(f"{low}", got.get(low, 0)) for low in range(0, 101, 10)]


def score_settings(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    from ..core import versions
    from ..core.derive import stale_count
    from ..profile import store as pstore
    stale = stale_count(conn)
    return [
        ("Luật lọc", versions.FILTER_RULES),
        ("Luật chấm", versions.SCORE_RULES),
        ("Phiên bản hồ sơ", str(pstore.latest_version_id(conn) or 0)),
        ("Tin cần tính lại", f"{stale}" if not stale
                             else f"<span class=warn-t>{stale}</span>"),
        ("Ngưỡng 'đáng nộp'", "điểm ≥ 70 và cơ hội ≠ unlikely"),
    ]


def score_stats(conn: sqlite3.Connection) -> dict:
    one = lambda sql: int(conn.execute(sql).fetchone()[0])
    return {
        "kept": one("SELECT COUNT(*) FROM posting WHERE kept=1"),
        "scored": one("SELECT COUNT(*) FROM posting WHERE kept=1 AND score IS NOT NULL"),
        "blind": one("SELECT COUNT(*) FROM posting WHERE kept=1 AND score_conf='none'"),
        "strong": one("SELECT COUNT(*) FROM posting WHERE kept=1 AND score>=70"),
        "worth": one("SELECT COUNT(*) FROM posting WHERE kept=1 AND score>=70"
                     " AND realism!='unlikely'"),
    }


def project_stats(conn: sqlite3.Connection, clusters: list, mine: list) -> dict:
    """Bước 4 đang ở đâu: bao nhiêu nhóm, bao nhiêu nhóm CV chưa trả lời được."""
    real = [c for c in clusters if c.key != "other"]
    return {
        "clusters": len(real),
        "gaps": sum(1 for c in real if c.gap),
        "covered": sum(1 for c in real if not c.gap),
        "mine": len(mine),
        "jobs": sum(len(c.jobs) for c in real),
        "waiting": llm_waiting(conn),
    }


def project_settings(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    from ..core import llm
    from ..projects.cluster import MAX_CLUSTERS, MIN_JOBS, TOO_COMMON
    engine = llm.engine_name()
    return [
        ("Máy LLM", engine if engine != "none"
                    else "<span class=warn-t>chưa bật</span>"),
        ("Tin tối thiểu mỗi nhóm", str(MIN_JOBS)),
        ("Số nhóm tối đa", str(MAX_CLUSTERS)),
        ("Kỹ năng quá phổ biến", f"có mặt ở >{int(TOO_COMMON * 100)}% tin thì không làm khoá nhóm"),
        ("Nghiên cứu công ty", "đọc trang tuyển dụng qua Chrome, có cache"),
    ]


def cluster_sizes(conn: sqlite3.Connection, clusters: list) -> list[tuple[str, int]]:
    return [(c.key[:12], len(c.jobs)) for c in clusters if c.key != "other"]


def watchlist(conn: sqlite3.Connection, limit: int = 60) -> list[dict]:
    """Từng CÔNG TY đang theo dõi — không gộp thành một thanh 'greenhouse 1.9%'.

    Một thanh gộp thì Point72 (9 việc) nằm chung với Betsson (0 việc, 131 lần
    kéo về) rồi lấy trung bình. Nhìn vào không phân biệt được mỏ với hố.
    """
    from ..scan_runner import load_boards, seed_boards

    mine = {s for v in seed_boards().values() for s in v}
    got = {r["slug"]: r for r in conn.execute(
        "SELECT substr(source, instr(source,':') + 1) AS slug,"
        "       COUNT(*) AS pulled, SUM(kept) AS kept,"
        "       MAX(CASE WHEN kept = 1 THEN posted_at ELSE '' END) AS last_hit"
        " FROM posting WHERE instr(source,':') > 0 GROUP BY slug")}

    out = []
    for ats, slugs in load_boards(conn).items():
        for slug in dict.fromkeys(slugs):
            row = got.get(slug)
            out.append({
                "slug": slug, "ats": ats,
                "mine": slug in mine,          # tôi tự chọn, hay máy nhặt
                "pulled": row["pulled"] if row else 0,
                "kept": (row["kept"] or 0) if row else 0,
                "last_hit": _ago(row["last_hit"]) if row and row["last_hit"] else "",
                "state": ("chưa quét" if not row else
                          "im lặng" if not (row["kept"] or 0) else "có việc"),
            })
    out.sort(key=lambda c: (-c["kept"], not c["mine"], c["slug"]))
    return out[:limit]


def search_reach(conn: sqlite3.Connection) -> dict:
    """Hai cách tìm với nhau ra sao — đo bằng TẦM VỚI, không phải tỉ lệ.

    "greenhouse 1.9%" đọc ra là "nguồn kém", trong khi sự thật là nó phải tải
    trọn board rồi mới lọc — và chính nó mang về Jane Street, Point72, Jump
    Trading. Tỉ lệ là thước sai cho một danh sách theo dõi.

    Thước đúng cho một cách tìm: nó CÒN MÙ Ở ĐÂU.
    """
    from ..core import prefs
    from ..core.postings import FAIL_THRESHOLD
    from ..core.scheduler import HUMAN_WINDOW, SCAN_EVERY_MIN
    from ..ingest.web.linkedin import PER_PAGE, PAUSE
    from ..profile import store as pstore
    from ..scan_runner import load_boards, seed_boards

    answers = pstore.load(conn)
    titles = [t.strip() for t in (answers.get("job_titles") or "").splitlines()
              if t.strip()]
    used, pages = titles[:5], 4

    # Đóng góp RIÊNG của mỗi cách: việc chỉ nó tìm ra, cách kia không thấy.
    rows = conn.execute(
        "WITH g AS (SELECT COALESCE(group_id, CAST(id AS TEXT)) gid,"
        "                  MAX(source = 'linkedin') li,"
        "                  MAX(source <> 'linkedin') api,"
        "                  MAX(CASE WHEN score >= 70 AND realism <> 'unlikely'"
        "                           THEN 1 ELSE 0 END) worth"
        "           FROM posting WHERE kept = 1 GROUP BY gid)"
        " SELECT SUM(li = 1 AND api = 0) chrome_only,"
        "        SUM(api = 1 AND li = 0) api_only,"
        "        SUM(li = 1 AND api = 1) ca_hai,"
        "        SUM(worth = 1 AND li = 1 AND api = 0) chrome_worth,"
        "        SUM(worth = 1 AND api = 1 AND li = 0) api_worth"
        " FROM g").fetchone()

    def side(is_linkedin: bool) -> dict:
        op = "=" if is_linkedin else "<>"
        r = conn.execute(
            f"SELECT COUNT(*) pulled, SUM(kept) kept, SUM(kept * via_agency) ag"
            f" FROM posting WHERE source {op} 'linkedin'").fetchone()
        return {"pulled": r["pulled"], "kept": r["kept"] or 0, "agency": r["ag"] or 0}

    boards = load_boards(conn)
    seeded = {s for v in seed_boards().values() for s in v}
    all_slugs = {s for v in boards.values() for s in v}
    alive_slugs = {r[0] for r in conn.execute(
        "SELECT DISTINCT substr(source, instr(source,':') + 1) FROM posting"
        " WHERE instr(source,':') > 0 AND kept = 1")}
    scanned = {r[0] for r in conn.execute(
        "SELECT DISTINCT substr(source, instr(source,':') + 1) FROM posting"
        " WHERE instr(source,':') > 0")}

    return {
        "chrome": {**side(True),
                   "only": rows["chrome_only"] or 0,
                   "worth": rows["chrome_worth"] or 0,
                   "titles_used": len(used), "titles_all": len(titles),
                   "titles_missed": titles[5:],
                   "location": "London",
                   "cap": len(used) * pages * PER_PAGE,
                   "pause": f"{PAUSE[0]}–{PAUSE[1]}s",
                   "window": f"{HUMAN_WINDOW[0]}:00–{HUMAN_WINDOW[1]}:00"},
        "api": {**side(False),
                "only": rows["api_only"] or 0,
                "worth": rows["api_worth"] or 0,
                "boards": len(all_slugs),
                "mine": len(seeded),
                "silent": len(scanned - alive_slugs),
                "never_scanned": sorted(all_slugs - scanned),
                "fail_at": f"{int(FAIL_THRESHOLD * 100)}%"},
        "both": rows["ca_hai"] or 0,
        "every": SCAN_EVERY_MIN,
        "autorun": prefs.flag(conn, prefs.AUTORUN),
    }


def chrome_status() -> dict:
    from ..browser import chrome as ch
    from ..core.scheduler import HUMAN_WINDOW
    from ..ingest.web import linkedin as li
    alive = ch.alive()
    return {
        "alive": bool(alive),
        "version": (alive or {}).get("Browser", "—"),
        "profile": str(ch.profile_dir()),
        "port": ch.PORT,
        "window": f"{HUMAN_WINDOW[0]:02d}:00 – {HUMAN_WINDOW[1]:02d}:00",
        "pace": f"{li.PAUSE[0]:g}–{li.PAUSE[1]:g}s between pages on LinkedIn",
    }


def company_stats(conn: sqlite3.Connection) -> dict:
    from ..ingest.web import companies as co
    return co.stats(conn)


def last_runs(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in postings.last_runs(conn)]


def health(conn: sqlite3.Connection) -> dict:
    """Sức khoẻ hệ thống — thứ người dùng phải thấy, không phải chỉ nằm trong DB.

    `stale` > 0 nghĩa là phán quyết hiện tại sinh ra từ hồ sơ hoặc luật CŨ.
    Không hiện ra thì người dùng đọc số liệu đã lỗi thời mà tưởng là mới.
    """
    from ..core import versions
    from ..core.derive import stale_count

    runs = postings.last_runs(conn)
    broken = [dict(r) for r in runs if not r["ok"]]
    flaky = [dict(r) for r in runs
             if r["ok"] and r["attempted"] and r["failed"]]
    return {
        "stale": stale_count(conn),
        "unjudged": postings.unjudged(conn),
        "filter_rules": versions.FILTER_RULES,
        "score_rules": versions.SCORE_RULES,
        "broken": broken,
        "flaky": flaky,
    }


def llm_waiting(conn: sqlite3.Connection) -> int:
    """Yêu cầu LLM đang chờ Claude trả lời trong phiên."""
    from ..core import llm
    llm.ensure_table(conn)
    return int(conn.execute(
        "SELECT COUNT(*) FROM llm_request WHERE answer = ''").fetchone()[0])
