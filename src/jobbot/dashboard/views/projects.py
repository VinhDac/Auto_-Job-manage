"""Projects — nhóm JD, project nào trả lời được nhóm nào, và chỗ nào còn trống."""

from __future__ import annotations

from html import escape as esc

from ..layout import badge, card, empty, h1, page


def render(clusters: list, have: list, pending: int) -> str:
    if not clusters:
        return page("Projects", h1("Projects")
                    + empty("No scored postings yet — run a scan first."),
                    active="/projects", pending=pending, status="Running")

    mine = "".join(
        f"<div class=srow><span>{esc(b.title or 'untitled')}</span>"
        f"<span class=muted>{', '.join(esc(t) for t in sorted(set(b.tags))) or 'no recognisable skills — the write-up may be too vague'}</span></div>"
        for b in have)
    owned = card(f"<b>Projects already on your CV</b>{mine}"
                 if have else "<b>No projects on your CV yet</b>", "notice")

    cards = []
    for cluster in clusters:
        if cluster.key == "other":
            continue
        gap = (badge("no project answers this", "warn") if cluster.gap
               else badge(f"answered by {cluster.covered_by[0]}", "ok"))
        jobs = "".join(
            f"<li><a href='/jobs/{j['id']}'>{esc(j['title'])}</a>"
            f"<span class=muted>{esc(j['company'])}</span>"
            f"<b>{j['score'] if j['score'] is not None else '—'}</b></li>"
            for j in sorted(cluster.jobs, key=lambda x: -(x["score"] or 0))[:6])
        more = (f"<li class=muted>+{len(cluster.jobs) - 6} more</li>"
                if len(cluster.jobs) > 6 else "")
        cards.append(card(
            f"<div class=prow><b>{esc(cluster.title)}</b>{gap}"
            f"<span class=spacer></span>"
            f"<span class=muted>{len(cluster.jobs)} postings</span></div>"
            f"<ul class=cjobs>{jobs}{more}</ul>", "proj"))

    return page(
        "Projects",
        h1("Projects", "Postings grouped by what they actually ask for. One real project "
                       "per group beats one shallow project per posting.")
        + owned
        + "<h2>Groups</h2>" + "".join(cards),
        active="/projects", pending=pending, status="Running")


def render_page(job: dict, doc, gaps: list, pending: int) -> str:
    def part(label: str, items: list[str], note: str = "") -> str:
        if not items:
            return (f"<h4 class=cvsec>{esc(label)}</h4>"
                    f"<div class=empty-box>{esc(note or 'nothing in your profile fits here yet')}</div>")
        body = "".join(f"<li>{esc(x)}</li>" for x in items)
        return f"<h4 class=cvsec>{esc(label)}</h4><ul class=cvlist>{body}</ul>"

    links = "".join(f"<li>{esc(l)}</li>" for l in doc.code) or "<li>—</li>"
    warn = "".join(
        f"<div class=note><b>{esc(t)}</b> {esc(why)}</div>" for t, why in gaps)

    covered = set(doc.speaks_to)
    chips = "".join(
        f"<span class='badge {'ok' if w in covered else 'warn'}'>{esc(w)}</span>"
        for w in doc.wanted) or "<span class=muted>—</span>"

    return page(
        f"Write-up — {job['title']}",
        f"<a class=back href='/jobs/{esc(job['id'])}'>← {esc(job['title'])}</a>"
        + h1("One-page write-up",
             f"For {doc.for_job}. Built from lines already in your profile — including "
             f"the ones the CV builder cut out. Nothing here is written by the system.")
        + f"<div class=cvpaper><div class=cvhead><div class=cvline>{esc(doc.project)}</div>"
          f"<div class=cvline>written for {esc(doc.for_job)}</div></div>"
        + part("The problem", doc.problem)
        + part("What I did", doc.method)
        + part("The number", doc.numbers,
               "No measurement yet — this is the part that decides whether an "
               "experienced reader believes any of it.")
        + part("What I gave up, and got wrong", doc.tradeoff,
               "Nothing here yet. A project with no scars reads as one that never ran.")
        + f"<h4 class=cvsec>Code</h4><ul class=cvlist>{links}</ul></div>"
        + "<h4 class=cvsec>What this posting asks for</h4>"
        + f"<div class=chiprow>{chips}</div>" + warn,
        active="/projects", pending=pending, status="Running")
