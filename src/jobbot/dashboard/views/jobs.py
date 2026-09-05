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


def _score(job: dict) -> str:
    """Chưa chấm điểm (bước 2) thì nói thẳng, không hiện số 0 giả."""
    return score_bar(job["score"]) if job.get("score") is not None else \
        '<span class=muted>not scored yet</span>'


def _row(job: dict) -> str:
    label, kind = STATE_BADGE.get(job["state"], (job["state"], ""))
    sources = "".join(badge(s, "src") for s in job["sources"])
    merged = job.get("merged", len(job["sources"]))
    dup = (f"<span class=muted>{merged} postings merged</span>" if merged > 1 else "")
    closes = f"<span class=warn-t>closes {esc(job['closes'])}</span>" if job["closes"] else ""
    return card(
        f"<a class=jobhead href='/jobs/{esc(job['id'])}'>"
        f"<span class=jt>{esc(job['title'])}</span>"
        f"<span class=jc>{esc(job['company'])} · {esc(job['location'])}</span></a>"
        f"<div class=jmeta>{_score(job)}{badge(label, kind)}"
        f"<span class=spacer></span>"
        f"<span class=muted>{esc(job['salary'])}</span></div>"
        f"<div class=jfoot>{sources}{dup}<span class=spacer></span>"
        f"<span class=muted>{esc(job['posted'])}</span>{closes}</div>",
        "job",
    )


def render(jobs: list[dict], pending: int) -> str:
    body = "".join(_row(j) for j in jobs) if jobs else empty("Nothing found yet.")
    filters = (
        "<div class=filters><span class='chip on'>All</span>"
        "<span class=chip>Graduate / junior</span><span class=chip>London</span>"
        "<span class=spacer></span>"
        f"<span class=muted>{len(jobs)} unique jobs</span></div>"
    )
    return page(
        "Jobs",
        h1("Jobs", "Pulled from every source, deduplicated, filtered to your target "
                  "titles. Scoring is step 2.")
        + filters + body,
        active="/jobs", pending=pending, status="Running",
    )


def render_detail(job: dict, pending: int) -> str:
    reqs = "".join(
        f"<li class='{'met' if r['met'] else 'miss'}'><b>{esc(r['text'])}</b>"
        f"<span>{esc(r['evidence'])}</span></li>"
        for r in job["requirements"]
    )
    changes = "".join(f"<li>{esc(c)}</li>" for c in job["cv_changes"])
    proj = job.get("project")
    return page(
        job["title"],
        f"<a class=back href='/jobs'>← Jobs</a>"
        + h1(job["title"], f"{job['company']} · {job['location']} · {job['salary']}")
        + f"<div class=jmeta>{_score(job)}"
          f"<span class=spacer></span><span class=muted>{esc(job['posted'])}</span></div>"
        + "<h2>Why this score</h2>"
        + (card(f"<ul class=reqs>{reqs}</ul>") if reqs
           else empty("Not scored yet — that is step 2."))
        + "<h2>What would change in your CV</h2>"
        + (card(f"<ul class=changes>{changes}</ul>") if changes
           else empty("No CV variant yet — that is step 3."))
        + "<h2>Project to attach</h2>"
        + (card(f"<b>{esc(proj['title'])}</b>"
                f"<div class=muted>Cluster: {esc(proj['cluster'])} · {esc(proj['status'])}</div>"
                f"<p>{esc(proj['why'])}</p>"
                "<a class=ghost href='/projects'>See the write-up</a>") if proj
           else empty("No project yet — that is step 4."))
        + "<h2>The posting</h2>"
        + card(f"<pre class=jd>{esc(job['jd'])}</pre>")
        + "<div class=actbar><button class=primary>Queue for approval</button>"
          "<button class=ghostbtn>Reject…</button>"
          "<span class=muted>Nothing is sent until you approve it in the queue.</span></div>",
        active="/jobs", pending=pending, status="Running",
    )
