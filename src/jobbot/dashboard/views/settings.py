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


def render(sources: list[dict], chrome: dict, companies: dict,
           runs: list[dict], pending: int) -> str:
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
        f"<td class=muted>{esc(r['error'][:70])}</td></tr>" for r in runs)

    return page(
        "Settings",
        h1("Settings", "What the system is doing, and what it is not allowed to do.")
        + "<h2>Chrome</h2>" + chrome_card
        + "<h2>Boundaries</h2>" + limits
        + "<h2>Companies</h2>" + comp
        + "<h2>Sources</h2>"
        + "<table class=data><tr><th>Source</th><th>Kind</th><th></th>"
          "<th>Last run</th><th>Found</th><th></th></tr>" + rows + "</table>"
        + "<h2>Last run per source</h2>"
        + "<table class=data><tr><th>Source</th><th></th><th>Seen</th>"
          "<th>New</th><th>Error</th></tr>" + last + "</table>",
        active="/settings", pending=pending, status="Running")
