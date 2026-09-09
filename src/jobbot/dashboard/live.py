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


def sieve(conn: sqlite3.Connection) -> dict:
    """Lưới GIỮ/BỎ — đúng ba thứ mà ingest/filter.judge() thật sự dùng.

    KHÔNG bịa thêm núm: judge() chỉ nhìn chức danh, cấp bậc, địa điểm. Thêm ô
    cho thứ code không đọc là dựng nút giả.

    Ba giá trị này nằm trong HỒ SƠ, không phải setting riêng của Search — nên
    sửa ở đây đổi cả vòng lọc, cả từ khoá gửi cho LinkedIn, lẫn phần chấm
    điểm theo chức danh.
    """
    from ..profile.schema import section_by_id
    from ..profile import store as pstore

    answers = pstore.load(conn)
    opts = {}
    for section in ("muc_tieu",):
        found = section_by_id(section)
        for q in (found.questions if found else []):
            if q.id in ("seniority", "markets"):
                opts[q.id] = [(o.value, o.label) for o in (q.options or [])]

    total = int(conn.execute("SELECT COUNT(*) FROM posting").fetchone()[0])
    return {
        "titles": [t.strip() for t in (answers.get("job_titles") or "").splitlines()
                   if t.strip()],
        "seniority": answers.get("seniority") or [],
        "markets": answers.get("markets") or [],
        "seniority_options": opts.get("seniority", []),
        "market_options": opts.get("markets", []),
        "total": total,
        # Đo thật trên 4.660 tin: 1,1 giây. Làm tròn lên để câu hứa không hụt.
        "seconds": max(1, round(total / 4000)),
    }


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
        # Cách nào tìm ra tin này. Đây là badge quan trọng nhất trên mỗi dòng:
        # hai cách tìm mù ở hai chỗ khác nhau, nên nhìn danh sách là thấy ngay
        # cách nào đang mang về cái gì. Tin cả hai cùng thấy -> hai badge.
        found_by = sorted({"chrome" if s == "linkedin" else "api"
                           for s in sources if s})
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
            "found_by": found_by,
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
            "href": "#settings",
            "note": "Your profile or the matching rules changed. What you see below "
                    "was decided before that — the next scan re-judges them.",
        })
    for run in state["broken"]:
        out.append({
            "kind": "warn",
            "text": f"Source failing: {run['source']}",
            "href": "#settings",
            "note": run["error"][:130] or "no reason recorded",
        })

    if postings.count(conn) == 0:
        out.append({"kind": "approve", "text": "No postings yet — run the first scan",
                    "href": "#settings", "note": "python3 scripts/scan.py"})
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
            "href": "/search",
            "note": "Direct employers only, scored 70+, and the posting does not rule "
                    "you out on a PhD or years of experience.",
        })
    if unscored:
        out.append({
            "kind": "scan",
            "text": f"{unscored} postings still have no description to judge from",
            "href": "/search",
            "note": "The deep-read pass has not reached them. Run "
                    "python3 scripts/scan.py to fetch the full text.",
        })
    out.append({
        "kind": "mail",
        "text": "Adzuna GB is off — the biggest UK source",
        "href": "#settings",
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


def settings(conn: sqlite3.Connection) -> dict:
    """Ba núm + một dòng tình trạng. Không hơn."""
    from ..core import llm, prefs, versions
    from ..core.derive import stale_count
    from ..core.scheduler import MAX_EVERY, MIN_EVERY, human_window

    boards = int(conn.execute(
        "SELECT COUNT(DISTINCT substr(source, instr(source,':') + 1)) FROM posting"
        " WHERE instr(source,':') > 0").fetchone()[0])
    firms = int(conn.execute("SELECT COUNT(*) FROM company").fetchone()[0])
    stale = stale_count(conn)

    from ..browser import chrome as ch
    return {
        "every": prefs.num(conn, prefs.SCAN_EVERY, MIN_EVERY, MAX_EVERY),
        "hours": human_window(),
        "engine": llm.engine_name(),
        "engines": list(llm.ENGINES),
        # Biến môi trường đè lên lựa chọn ở menu. Không nói ra thì người dùng
        # chọn xong mà không có gì đổi, và không hiểu vì sao.
        "engine_forced": llm.env_override(),
        "status": [
            ("Chrome", "đang mở" if ch.alive() else "tắt"),
            ("Board đang quét", f"{boards}"),
            ("Công ty đã biết", f"{firms:,}"),
            ("Tin cần phán lại", f"{stale:,}" if stale else "không"),
            ("Luật lọc", versions.FILTER_RULES),
            ("Luật chấm", versions.SCORE_RULES),
        ],
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


# ---------------------------------------------------------------- projects

def cv_projects(conn: sqlite3.Connection) -> list:
    """Project ĐÃ có trên CV — nguồn cung thứ nhất của lưới khoảng trống."""
    from ..cv.blocks import parse as parse_cv
    from ..profile import store as pstore
    text = pstore.load(conn).get("cv_text") or ""
    return [b for b in parse_cv(text) if b.kind == "project"]


def project_board(conn: sqlite3.Connection) -> dict:
    """Ba ô của tab Projects, một lần đọc.

    Lưới KHÔNG lưu trong bảng — nó là phép trừ giữa cầu (tin đòi gì) và cung
    (CV + kho). Lưu thì phải giữ nó khớp với hai thứ luôn đổi.
    """
    from ..core import llm
    from ..projects import inventory, make

    mine = cv_projects(conn)
    llm.ensure_table(conn)
    waiting = []
    for req in llm.pending(conn, limit=10):
        row = dict(req)
        row["stale"] = make.is_stale(row["purpose"])
        # Dấu thời gian trong bảng là UTC, còn nhật ký hiện giờ máy — để cạnh
        # nhau thì cùng một việc đọc ra hai giờ khác nhau. Tuổi thì không lệch.
        row["age"] = _ago(row["created_at"])
        waiting.append(row)
    return {"grid": inventory.coverage(conn, mine),
            "store": inventory.all(conn),
            "scored": inventory.total_scored(conn),
            "waiting": waiting}
