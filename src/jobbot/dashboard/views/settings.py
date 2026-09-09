"""Settings — nguồn, Chrome, nhịp chạy, ranh giới an toàn.

Trang này phải trả lời được: hệ thống ĐANG làm gì, với ai, và cái gì nó
KHÔNG được phép làm. Không giấu gì.
"""

from __future__ import annotations

from html import escape as esc

from ..layout import badge, card, h1, page


def _srow(label: str, value: str, note: str = "") -> str:
    return (f"<div class=srow><span>{esc(label)}</span><span>{value}</span>"
            + (f"<span class=muted>{esc(note)}</span>" if note else "") + "</div>")


def _rate(run: dict) -> str:
    """Tỉ lệ đọc hỏng. Không đo được thì nói thẳng là không đo được."""
    if not run.get("attempted"):
        return "<span class=muted>not measured</span>"
    bad = run["failed"] * 100 // run["attempted"]
    kind = "warn" if bad > 30 else ("" if bad else "ok")
    return badge(f"{run['failed']}/{run['attempted']} failed ({bad}%)", kind)


def render(sources: list[dict], chrome: dict, companies: dict,
           runs: list[dict], health: dict) -> str:
    rows = "".join(
        f"<tr><td>{esc(s['name'])}</td>"
        f"<td>{badge(s['kind'], 'ok' if s['kind'] == 'api' else '')}</td>"
        f"<td>{badge('on', 'ok') if s['on'] else badge('off', 'muted')}</td>"
        f"<td class=muted>{esc(s['last'])}</td>"
        f"<td>{s['found']:,}</td>"
        f"<td class=muted>{esc(s['note'])}</td></tr>"
        for s in sources)

    live = badge("running", "ok") if chrome["alive"] else badge("not running", "muted")
    chrome_card = card(
        "<b>Chrome</b>"
        + _srow("Status", live, chrome["version"])
        + _srow("Profile", f"<code>{esc(chrome['profile'])}</code>",
                "separate from your everyday Chrome — it is never touched")
        + _srow("Signed in", badge("no — public pages only", "ok"),
                "no account means no account to lose")
        + _srow("Window", "headed", "headless is blocked by Cloudflare on these sites")
        + _srow("Port", str(chrome["port"]), "not the default 9222")
        + "<div class=note>A Chrome window appearing is the system actually working. "
          "It reads public pages at human pace, the same pages you would open yourself."
          "</div>", "notice")

    limits = card(
        "<b>What Chrome is allowed to do</b>"
        + _srow("Read public job pages", badge("yes", "ok"), "")
        + _srow("Sign in to your accounts", badge("never", "warn"),
                "LinkedIn, eFC — no credentials are stored or entered")
        + _srow("Read profiles, connections, messages", badge("never", "warn"),
                "job postings only")
        + _srow("Cookie banners", badge("reject only", "ok"),
                "never Accept — the system cannot agree to terms for you")
        + _srow("When a site blocks it", badge("stop and log", "ok"),
                "it does not retry or work around the block")
        + _srow("Hours", esc(chrome["window"]),
                "outside these hours only public APIs run; a manual scan ignores this")
        + _srow("Pace", esc(chrome["pace"]), "")
        , "safety")

    comp = card(
        "<b>Target companies</b>"
        + _srow("Known", f"{companies['total']:,}", "grows itself from postings found")
        + _srow("Resolved to an ATS", f"{companies['resolved']:,}",
                "these are read directly, bypassing job boards")
        + _srow("Marked as agencies", f"{companies['agencies']:,}",
                "hidden by default on the Jobs page")
        + "<div class=note>Every real employer seen in a posting is added here and "
          "probed for its own careers board. The seed list is only a starting point."
          "</div>")

    last = "".join(
        f"<tr><td>{esc(r['source'])}</td>"
        f"<td>{badge('ok', 'ok') if r['ok'] else badge('failed', 'warn')}</td>"
        f"<td>{r['fetched']:,}</td><td>{r['new_rows']:,}</td>"
        f"<td>{_rate(r)}</td>"
        f"<td class=muted>{esc(r['error'][:60])}</td></tr>" for r in runs)

    warn = ""
    if health["stale"]:
        warn = card(
            f"<b>{health['stale']:,} postings need re-judging</b>"
            "<div class=muted>Your profile or the rules changed since these were last "
            "judged, so what you are looking at was decided by an older version. "
            "The next scan fixes it, or run <code>python3 scripts/rebuild.py</code>."
            "</div>", "notice")
    if health["unjudged"]:
        warn += card(f"<b>{health['unjudged']:,} postings never judged</b>"
                     "<div class=muted>Pulled in but the filter has not run over them "
                     "yet — they are hidden until it does.</div>", "notice")

    versions_card = card(
        "<b>Rule versions</b>"
        + _srow("Filter rules", f"<code>{esc(health['filter_rules'])}</code>",
                "title matching, seniority, location")
        + _srow("Scoring rules", f"<code>{esc(health['score_rules'])}</code>",
                "vocabulary, requirement extraction, weights")
        + "<div class=note>Every verdict records which version produced it. Change a "
          "rule and the affected postings are re-judged automatically — nothing goes "
          "quietly stale.</div>")

    return page(
        "Settings",
        h1("Settings", "What the system is doing, and what it is not allowed to do.")
        + warn
        + "<h2>Chrome</h2>" + chrome_card
        + "<h2>Boundaries</h2>" + limits
        + "<h2>Companies</h2>" + comp
        + "<h2>Sources</h2>"
        + "<table class=data><tr><th>Source</th><th>Kind</th><th></th>"
          "<th>Last run</th><th>Found</th><th></th></tr>" + rows + "</table>"
        + "<h2>Last run per source</h2>"
        + "<table class=data><tr><th>Source</th><th></th><th>Seen</th>"
          "<th>New</th><th>Deep read</th><th>Error</th></tr>" + last + "</table>"
        + "<h2>Rules</h2>" + versions_card,
        active="/settings", status="Running")
