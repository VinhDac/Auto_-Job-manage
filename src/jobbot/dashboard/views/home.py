"""Home — mở app ra là thấy ngay TÌNH HÌNH, không phải bảng số.

Thứ tự cố ý: cần bạn làm gì -> máy đang làm gì -> con số -> đã làm gì.
Người mở app lên không hỏi "có bao nhiêu tin", họ hỏi "có gì cần tôi không".
"""

from __future__ import annotations

from html import escape as esc

from ..layout import card, empty, h1, page, stat

TAG = {"approve": "Decision", "mail": "Setup", "follow": "Follow-up",
       "scan": "Scan", "warn": "Attention"}

# Ô nào đáng làm nổi bật bằng màu nhấn
KEY_LABELS = {"Unique jobs", "Awaiting you", "Match your titles"}


def render(status: dict, counters: list[dict], needs: list[dict],
           activity: list[dict], pending: int) -> str:
    live = status["state"] == "running"

    items = "".join(
        f"<a class='need {esc(n['kind'])}' href='{esc(n['href'])}'>"
        f"<span class=tag>{esc(TAG.get(n['kind'], 'Note'))}</span>"
        f"<b>{esc(n['text'])}</b><span class=muted>{esc(n['note'])}</span></a>"
        for n in needs
    ) or empty("Nothing needs you right now.")

    failed = "".join(f"<li class=warn>{esc(s)}</li>" for s in status["sources_failed"])
    runcard = card(
        f"<div class=runline><span class='dot {'on' if live else ''}'></span>"
        f"<b>{esc(status['state'].title())}</b>"
        f"<span class=muted>last scan {esc(status['last_scan'])} · "
        f"next {esc(status['next_scan'])}</span><span class=spacer></span>"
        f"<span class=muted>{status['sources_ok']}/{status['sources_total']} sources</span></div>"
        + (f"<ul class=mini>{failed}</ul>" if failed else ""))

    tiles = "".join(
        stat(c["value"], c["label"], c["note"], key=c["label"] in KEY_LABELS)
        for c in counters)

    feed = "".join(
        f"<li class='ev {esc(a['kind'])}'><span class=t>{esc(a['time'])}</span>"
        f"<span>{esc(a['text'])}</span></li>" for a in activity)

    return page(
        "Home",
        h1("Home", "Everything running, and everything waiting on you.")
        + "<h2>Needs you</h2>" + f"<div class=needs>{items}</div>"
        + "<h2>Engine</h2>" + runcard
        + "<h2>Numbers</h2>" + f"<div class=stats>{tiles}</div>"
        + "<h2>Recent activity</h2>"
        + (f"<ul class=feed>{feed}</ul>" if feed else empty("Nothing logged yet.")),
        active="/", pending=pending,
        status=f"{status['state'].title()} · {status['sources_ok']} sources",
    )
