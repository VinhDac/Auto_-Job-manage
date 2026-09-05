"""Pipeline — đã gửi đi rồi thì sao. Chống gửi trùng, nhắc kiểm tra thư, nhắc follow-up."""

from __future__ import annotations

from html import escape as esc

from ..layout import badge, card, empty, h1, page

STAGE_LABEL = {
    "applied": ("Applied", ""), "acknowledged": ("Acknowledged", "ok"),
    "screening": ("Screening", "ok"), "interview": ("Interview", "hi"),
    "offer": ("Offer", "hi"), "rejected": ("Rejected", "muted"),
}


def render(rows: list[dict], stages: list[str], pending: int) -> str:
    if not rows:
        return page("Pipeline", h1("Pipeline") + empty("Nothing sent yet."),
                    active="/pipeline", pending=pending)

    counts = {s: sum(1 for r in rows if r["stage"] == s) for s in stages}
    strip = "".join(
        f"<div class='pstage {s}'><b>{counts[s]}</b><span>{esc(STAGE_LABEL[s][0])}</span></div>"
        for s in stages
    )

    body = ""
    for r in rows:
        label, kind = STAGE_LABEL.get(r["stage"], (r["stage"], ""))
        due = f"<span class=due>{esc(r['due'])}</span>" if r["due"] else ""
        body += card(
            f"<div class=prow><b>{esc(r['company'])}</b>"
            f"<span class=muted>{esc(r['role'])}</span>"
            f"<span class=spacer></span>{badge(label, kind)}"
            f"<span class=muted>{r['days']}d</span></div>"
            f"<div class=pfoot><span class=muted>{esc(r['last'])}</span>"
            f"<span class=spacer></span>{due}</div>", "prow")

    return page(
        "Pipeline",
        h1("Pipeline", "Everything already sent. Also what stops the system applying "
                       "to the same company twice.")
        + f"<div class=pstrip>{strip}</div>"
        + card("<b>Check your inbox</b><div class=muted>2 replies expected — Man Group and "
               "Revolut both acknowledged more than 5 days ago. The system reads replies "
               "but cannot read your personal inbox until you connect it in Settings.</div>",
               "notice")
        + body,
        active="/pipeline", pending=pending, mock=True, status="Running",
    )
