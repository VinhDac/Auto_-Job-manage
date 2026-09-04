"""Dashboard — mở app ra thấy ngay: máy đang làm gì, và cần mình làm gì."""

from __future__ import annotations

from html import escape as esc

from ..layout import badge, card, h1, page, stat

KIND_LABEL = {"approve": "Decision", "mail": "Inbox", "follow": "Follow-up"}


def render(status: dict, counters: list[dict], needs: list[dict],
           activity: list[dict], pending: int) -> str:
    dot = "on" if status["state"] == "running" else "off"
    failed = "".join(
        f"<li class=warn>{esc(s)}</li>" for s in status["sources_failed"]
    )
    head = card(
        f"<div class=runline><span class='dot {dot}'></span>"
        f"<b>{esc(status['state'].title())}</b>"
        f"<span class=muted>last scan {esc(status['last_scan'])} · "
        f"next {esc(status['next_scan'])}</span>"
        f"<span class=spacer></span>"
        f"<span class=muted>{status['sources_ok']}/{status['sources_total']} sources</span>"
        "</div>"
        + (f"<ul class=mini>{failed}</ul>" if failed else "")
        + f"<div class=muted style='margin-top:6px'>Human-paced window "
          f"{esc(status['window'])}</div>",
        "run",
    )

    tiles = "".join(stat(c["value"], c["label"], c["note"]) for c in counters)

    items = "".join(
        f"<a class='need {esc(n['kind'])}' href='{esc(n['href'])}'>"
        f"<span class=tag>{esc(KIND_LABEL.get(n['kind'], ''))}</span>"
        f"<b>{esc(n['text'])}</b><span class=muted>{esc(n['note'])}</span></a>"
        for n in needs
    )

    feed = "".join(
        f"<li class='ev {esc(a['kind'])}'><span class=t>{esc(a['time'])}</span>"
        f"<span>{esc(a['text'])}</span></li>"
        for a in activity
    )

    return page(
        "Dashboard",
        h1("Dashboard")
        + head
        + f"<div class=stats>{tiles}</div>"
        + "<h2>Needs you</h2>"
        + f"<div class=needs>{items}</div>"
        + "<h2>Recent activity</h2>"
        + f"<ul class=feed>{feed}</ul>",
        active="/",
        pending=pending,
    )
