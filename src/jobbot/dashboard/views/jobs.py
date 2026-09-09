"""Jobs — phễu tin đã tìm được, sau khi gộp trùng và chấm điểm."""

from __future__ import annotations

from html import escape as esc

from ..filters import (BAND, CHANCE, DAYS, LOC, PER_PAGE, SHOW, SORT, VIA,
                       JobFilter)
from ..layout import badge, card, empty, h1, page, score_bar

STATE_BADGE = {
    "new": ("new", ""),
    "dropped": ("filtered out", "warn"),
    "queued": ("in queue", "ok"),
    "rejected": ("rejected", "muted"),
    "applied": ("applied", "ok"),
}


def _chips(label: str, name: str, options, current: str, flt) -> str:
    """Hàng chip chọn-một. Là radio thật nên bàn phím và trình đọc màn hình vẫn dùng được."""
    items = "".join(
        f"<label class=chip><input type=radio name={esc(name)} value='{esc(v)}'"
        f"{' checked' if v == current else ''} onchange='this.form.submit()'>"
        f"<span>{esc(l)}</span></label>" for v, l in options)
    return f"<div class=frow><b class=flabel>{esc(label)}</b>{items}</div>"


def _ticks(label: str, name: str, options, flt) -> str:
    """Cột ô tích chọn-nhiều, kèm số lượng."""
    items = "".join(
        f"<label class='tick{' on' if flt.has(name, v) else ''}'>"
        f"<input type=checkbox name={esc(name)} value='{esc(v)}'"
        f"{' checked' if flt.has(name, v) else ''} onchange='this.form.submit()'>"
        f"<span>{esc(l)}</span>{f'<b>{n}</b>' if n else ''}</label>"
        for v, l, n in options)
    return (f"<div class=tickcol><b class=flabel>{esc(label)}</b>"
            f"<div class=ticklist>{items}</div></div>")


CHANCE_BADGE = {"likely": ("worth applying", "ok"),
                "possible": ("maybe", ""),
                "unlikely": ("long shot", "warn"),
                "unknown": ("can't tell", "muted")}

CONF_NOTE = {"high": "", "medium": "few requirements found",
             "low": "requirements guessed from prose", "none": ""}


def _score(job: dict) -> str:
    """Không chấm được thì NÓI THẲNG. Điểm bịa còn tệ hơn không có điểm."""
    if job.get("score") is None:
        return "<span class=noscore>can&#39;t read requirements — judge it yourself</span>"
    note = CONF_NOTE.get(job.get("confidence", ""), "")
    tail = f"<span class=conf>{esc(note)}</span>" if note else ""
    return score_bar(job["score"]) + tail


def _row(job: dict) -> str:
    label, kind = STATE_BADGE.get(job["state"], (job["state"], ""))
    chance = job.get("realism") or ""
    chip = badge(*CHANCE_BADGE[chance]) if chance in CHANCE_BADGE else ""
    sources = "".join(badge(s, "src") for s in job["sources"])
    merged = job.get("merged", len(job["sources"]))
    dup = (f"<span class=muted>{merged} postings merged</span>" if merged > 1 else "")
    reason = (f"<div class=chancewhy>{esc(job['realism_why'])}</div>"
              if chance in ("unlikely", "likely") and job.get("realism_why") else "")
    why = (f"<div class=dropwhy>Filtered out — {esc(job['drop_reason'])}</div>"
           if job.get("drop_reason") else "")
    agency = badge("via agency", "warn") if job.get("via_agency") else ""
    age = job.get("age_days")
    stale = (badge(f"{age}d old", "warn") if age is not None and age >= 45
             else badge("no date", "muted") if age is None else "")
    # 'closes' từng là ô rỗng cứng trong live.jobs — hạn nộp tính ra được thì
    # nằm ở khoá 'deadline' mà không view nào đọc, nên chưa bao giờ hiện lên.
    closes = (f"<span class=warn-t>closes {esc(job['deadline'])}</span>"
              if job.get("deadline") else "")
    return card(
        f"<a class=jobhead href='/jobs/{esc(job['id'])}'>"
        f"<span class=jt>{esc(job['title'])}</span>"
        f"<span class=jc>{esc(job['company'])} · {esc(job['location'])}</span></a>"
        f"<div class=jmeta>{_score(job)}{chip}{badge(label, kind)}{agency}{stale}"
        f"<span class=spacer></span>"
        f"<span class=muted>{esc(job['salary'])}</span></div>"
        f"<div class=jfoot>{sources}{dup}<span class=spacer></span>"
        f"<span class=muted>{esc(job['posted'])}</span>{closes}</div>{reason}{why}",
        "job" + (" out" if job.get("drop_reason") else ""),
    )


def _range(flt: JobFilter, shown: int, total: int) -> str:
    if not shown:
        return "0 results"
    start = (flt.page - 1) * PER_PAGE + 1
    return f"{start}–{start + shown - 1} of {total:,}"


def _pager(flt: JobFilter, total: int) -> str:
    pages = max(1, -(-total // PER_PAGE))
    if pages < 2:
        return ""
    prev = (f"<a class=chip href='{esc(flt.url(page=flt.page - 1))}'>← Previous</a>"
            if flt.page > 1 else "<span class='chip off'>← Previous</span>")
    nxt = (f"<a class=chip href='{esc(flt.url(page=flt.page + 1))}'>Next →</a>"
           if flt.page < pages else "<span class='chip off'>Next →</span>")
    return (f"<div class=pager>{prev}"
            f"<span class=muted>Page {flt.page} of {pages:,}</span>{nxt}</div>")


def render(jobs: list[dict], flt: JobFilter, counts: dict, facets: dict) -> str:
    total = counts.get(flt.show, len(jobs))
    body = "".join(_row(j) for j in jobs) if jobs else empty(
        "Nothing matches these filters. Try widening them, or switch Show to "
        "\"Filtered out\" to see what the scan discarded and why.")

    show_opts = [(v, f"{l}  {counts.get(v, 0):,}") for v, l in SHOW]
    company_opts = [(c, c, n) for c, n in facets["companies"]]
    source_opts = [(s, s, 0) for s in facets["sources"]]

    panel = (
        "<form class=filters method=get action='/jobs'>"
        f"<div class=frow><input class=search type=search name=q value='{esc(flt.q)}' "
        f"placeholder='Search title or company…'>"
        f"<button class=primary type=submit>Search</button></div>"
        + _chips("Show", "show", show_opts, flt.show, flt)
        + _chips("Where", "loc", LOC, flt.loc, flt)
        + _chips("When", "days", DAYS, flt.days, flt)
        + _chips("Score", "band", BAND, flt.band, flt)
        + _chips("Chance", "chance", CHANCE, flt.chance, flt)
        + _chips("Posted by", "via", VIA, flt.via, flt)
        + _chips("Sort", "sort", SORT, flt.sort, flt)
        + "<div class=tickwrap>"
        + _ticks("Company", "company", company_opts, flt)
        + _ticks("Source", "source", source_opts, flt)
        + "</div></form>")

    chips = flt.active()
    active = ("<div class=activebar><span class=muted>Filtering by</span>" + "".join(
        f"<a class='chip on' href='{esc(url)}'>{esc(label)} ✕</a>" for label, url in chips)
        + f"<a class=clear href='/jobs'>Clear all</a></div>") if chips else ""

    return page(
        "Jobs",
        h1("Jobs", "Everything pulled, deduplicated, and filtered. Nothing is deleted — "
                   "switch Show to see what the scan discarded and why.")
        + panel + active
        + f"<div class=resultcount>{_range(flt, len(jobs), total)}</div>"
        + body + _pager(flt, total),
        active="/jobs", status="Running",
    )


def _breakdown(job: dict) -> str:
    """Điểm đến từ đâu. Không giải thích được thì không dùng để quyết định nộp."""
    data = job.get("explain")
    if not data or data.get("score") is None:
        return ""
    b = data["breakdown"]
    rows = "".join(
        f"<div class=bdrow><span class=bdl>{esc(label)}</span>"
        f"<span class=bdtrack><span class=bdfill style='width:{pts / cap * 100:.0f}%'></span></span>"
        f"<b>{pts:g}<i>/{cap}</i></b><span class=muted>{esc(why)}</span></div>"
        for label, pts, cap, why in [
            ("Must-have requirements", b["must"]["points"], 55,
             f"{b['must']['met']}/{b['must']['total']} met"),
            ("Nice-to-haves", b["nice"]["points"], 15,
             f"{b['nice']['met']}/{b['nice']['total']} met"),
            ("Level fit", b["level"]["points"], 20, b["level"]["why"]),
            ("Title match", b["title"]["points"], 10, b["title"]["why"]),
        ])
    notes = []
    if data.get("capped"):
        notes.append("Score capped at 55 — this posting asks for experience or a "
                     "qualification you do not have, so it is unlikely to pass screening "
                     "however well the rest matches.")
    if data.get("unknown"):
        notes.append(f"{data['unknown']} lines could not be judged automatically "
                     "(soft skills, culture fit) — left out of the maths entirely "
                     "rather than guessed at.")
    if data.get("weak_evidence"):
        notes.append(f"{data['weak_evidence']} matches rest on keywords you set rather than "
                     "evidence in your CV. Filling in your skills and CV would firm these up.")
    tail = "".join(f"<div class=note>{esc(n)}</div>" for n in notes)
    return card(f"<div class=bd>{rows}</div>{tail}", "bdcard")


def render_detail(job: dict) -> str:
    reqs = "".join(
        f"<li class='{'met' if r['met'] else ('unk' if r['met'] is None else 'miss')}'>"
        f"<b>{esc(r['text'])}</b>"
        f"<span>{esc(r['evidence'])}</span></li>"
        for r in job["requirements"]
    )
    proj = job.get("project")
    return page(
        job["title"],
        f"<a class=back href='/jobs'>← Jobs</a>"
        + h1(job["title"], f"{job['company']} · {job['location']} · {job['salary']}")
        + f"<div class=jmeta>{_score(job)}"
          f"<span class=spacer></span><span class=muted>{esc(job['posted'])}</span></div>"
        + "<h2>Why this score</h2>"
        + _breakdown(job)
        + (card(f"<ul class=reqs>{reqs}</ul>") if reqs
           else empty("Could not read any requirements from this posting. "
                      "Read it yourself — the system will not guess."))
        + "<h2>Tailored CV</h2>"
        + card(f"<a class=ghost href='/jobs/{esc(job['id'])}/cv'>"
               "Build a CV for this posting →</a>"
               "<div class=muted style='margin-top:6px'>Selects and orders lines from your "
               "own profile against what this posting asks for. Writes nothing new.</div>")
        + "<h2>Project write-up</h2>"
        + card(f"<a class=ghost href='/jobs/{esc(job['id'])}/project'>"
               "Build a one-page write-up for this posting →</a>"
               "<div class=muted style='margin-top:6px'>Five parts, 90 seconds to read. "
               "Uses the lines the CV builder cut out — that is where they belong.</div>")
        + "<h2>The posting</h2>"
        + card(f"<pre class=jd>{esc(job['jd'])}</pre>")
        + "<div class=actbar><button class=primary>Queue for approval</button>"
          "<button class=ghostbtn>Reject…</button>"
          "<span class=muted>Nothing is sent until you approve it in the queue.</span></div>",
        active="/jobs", status="Running",
    )
