"""Settings — nguồn, nhịp chạy, engine LLM, và ranh giới an toàn."""

from __future__ import annotations

from html import escape as esc

from ..layout import badge, card, h1, page


def render(sources: list[dict], pending: int) -> str:
    rows = "".join(
        f"<tr><td>{esc(s['name'])}</td>"
        f"<td>{badge('on', 'ok') if s['on'] else badge('off', 'muted')}</td>"
        f"<td>{badge('needs key', 'warn') if s['key'] else '<span class=muted>no key</span>'}</td>"
        f"<td class=muted>{esc(s['last'])}</td><td>{s['found']:,}</td></tr>"
        for s in sources)

    engines = card(
        "<b>Matching engine</b>"
        "<label class=opt><input type=radio name=engine value=none>"
        "<span><span class=lbl>Keywords only — no LLM</span>"
        "<span class=note>Deterministic, testable, free. Runs 24/7.</span></span></label>"
        "<label class=opt><input type=radio name=engine value=claude_code checked>"
        "<span><span class=lbl>Claude in this session</span>"
        "<span class=note>No API key. Requests queue up and are answered in-session.</span></span></label>"
        "<label class=opt><input type=radio name=engine value=api>"
        "<span><span class=lbl>Anthropic API</span>"
        "<span class=note>Needs a key. For running unattended, or sharing the app.</span></span></label>",
        "engine")

    safety = card(
        "<b>Safety boundary</b>"
        "<div class=muted>Which actions stop for your approval. "
        "Anything that cannot be undone should stay on.</div>"
        "<table class=data>"
        "<tr><td>Search, dedup, score, measure</td><td>" + badge("runs freely", "ok") + "</td></tr>"
        "<tr><td>Build a CV variant</td><td>" + badge("runs freely", "ok") + "</td></tr>"
        "<tr><td>Send an application</td><td>" + badge("always asks", "warn") + "</td></tr>"
        "<tr><td>Send a follow-up email</td><td>" + badge("always asks", "warn") + "</td></tr>"
        "<tr><td>Post or connect on LinkedIn</td><td>" + badge("always asks", "warn") + "</td></tr>"
        "</table>", "safety")

    schedule = card(
        "<b>When it runs</b>"
        "<div class=srow><span>Public APIs</span>"
        "<span class=muted>24/7 — no reason to hold back</span></div>"
        "<div class=srow><span>Sources without an API (Chrome)</span>"
        "<span class=muted>08:00 – 22:00, with gaps and days off</span></div>"
        "<div class=note>Nobody browses at 3am every night. The rhythm gives it away "
        "long before the click speed does.</div>", "sched")

    sponsor = card(
        "<b>UK sponsor register</b>"
        "<div class=muted>143,082 organisations · downloaded from gov.uk · "
        "updated daily</div>"
        "<div class=srow><span>Last synced</span><span class=muted>today, 09:12</span></div>"
        "<div class=note>Every employer is checked against this. On a Graduate visa, "
        "a company that cannot sponsor is a company that cannot keep you.</div>", "notice")

    return page(
        "Settings",
        h1("Settings")
        + "<h2>Sources</h2>"
        + "<table class=data><tr><th>Source</th><th></th><th>API key</th>"
          "<th>Last run</th><th>Found</th></tr>" + rows + "</table>"
        + "<h2>Engine</h2>" + engines
        + "<h2>Schedule</h2>" + schedule
        + "<h2>Visa</h2>" + sponsor
        + "<h2>Safety</h2>" + safety,
        active="/settings", pending=pending,
    )
