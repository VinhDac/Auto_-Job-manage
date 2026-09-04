"""Jobs — phễu tin đã tìm được, sau khi gộp trùng và chấm điểm."""

from __future__ import annotations

from html import escape as esc

from ..layout import badge, card, empty, h1, page, score_bar

STATE_BADGE = {
    "new": ("new", ""),
    "queued": ("in queue", "ok"),
    "rejected": ("rejected", "muted"),
    "applied": ("applied", "ok"),
}


def _row(job: dict) -> str:
    label, kind = STATE_BADGE.get(job["state"], (job["state"], ""))
    sponsor = (badge("licensed sponsor", "ok") if job["sponsor"]
               else badge("not a sponsor", "warn"))
    sources = "".join(badge(s, "src") for s in job["sources"])
    dup = (f"<span class=muted>merged from {len(job['sources'])} sources</span>"
           if len(job["sources"]) > 1 else "")
    closes = f"<span class=warn-t>closes {esc(job['closes'])}</span>" if job["closes"] else ""
    return card(
        f"<a class=jobhead href='/jobs/{esc(job['id'])}'>"
        f"<span class=jt>{esc(job['title'])}</span>"
        f"<span class=jc>{esc(job['company'])} · {esc(job['location'])}</span></a>"
        f"<div class=jmeta>{score_bar(job['score'])}{sponsor}{badge(label, kind)}"
        f"<span class=spacer></span>"
        f"<span class=muted>{esc(job['salary'])}</span></div>"
        f"<div class=jfoot>{sources}{dup}<span class=spacer></span>"
        f"<span class=muted>{esc(job['posted'])}</span>{closes}</div>",
        "job",
    )


def render(jobs: list[dict], pending: int) -> str:
    body = "".join(_row(j) for j in jobs) if jobs else empty("Nothing found yet.")
    filters = (
        "<div class=filters>"
        "<span class='chip on'>All</span><span class=chip>Score &gt; 75</span>"
        "<span class=chip>Licensed sponsors</span><span class=chip>Closing soon</span>"
        "<span class=chip>New today</span><span class=spacer></span>"
        "<span class=muted>6 of 892 shown</span></div>"
    )
    return page(
        "Jobs",
        h1("Jobs", "Deduplicated and scored against your profile. Newest first.")
        + filters + body,
        active="/jobs", pending=pending,
    )


def render_detail(job: dict, pending: int) -> str:
    reqs = "".join(
        f"<li class='{'met' if r['met'] else 'miss'}'><b>{esc(r['text'])}</b>"
        f"<span>{esc(r['evidence'])}</span></li>"
        for r in job["requirements"]
    )
    changes = "".join(f"<li>{esc(c)}</li>" for c in job["cv_changes"])
    proj = job["project"]
    sponsor = (badge("licensed sponsor", "ok") if job["sponsor"]
               else badge("not a sponsor — cannot keep you past your visa", "warn"))

    return page(
        job["title"],
        f"<a class=back href='/jobs'>← Jobs</a>"
        + h1(job["title"], f"{job['company']} · {job['location']} · {job['salary']}")
        + f"<div class=jmeta>{score_bar(job['score'])}{sponsor}"
          f"<span class=spacer></span><span class=muted>{esc(job['posted'])}</span></div>"
        + "<h2>Why this score</h2>"
        + card(f"<ul class=reqs>{reqs}</ul>")
        + "<h2>What would change in your CV</h2>"
        + card(f"<ul class=changes>{changes}</ul>"
               "<a class=ghost href='#'>Preview the tailored CV</a>")
        + "<h2>Project to attach</h2>"
        + card(f"<b>{esc(proj['title'])}</b>"
               f"<div class=muted>Cluster: {esc(proj['cluster'])} · {esc(proj['status'])}</div>"
               f"<p>{esc(proj['why'])}</p>"
               "<a class=ghost href='/projects'>See the write-up</a>")
        + "<h2>The posting</h2>"
        + card(f"<pre class=jd>{esc(job['jd'])}</pre>")
        + "<div class=actbar><button class=primary>Queue for approval</button>"
          "<button class=ghostbtn>Reject…</button>"
          "<span class=muted>Nothing is sent until you approve it in the queue.</span></div>",
        active="/jobs", pending=pending,
    )
