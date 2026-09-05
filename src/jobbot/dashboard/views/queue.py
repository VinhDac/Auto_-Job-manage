"""Queue — trái tim của hệ thống: nơi duy nhất người quyết định.

Mọi hành động không đảo ngược được đều phải dừng ở đây.
Duyệt theo LÔ: một màn hình, 30 giây, rồi máy chạy hàng giờ không cần ngồi canh.
"""

from __future__ import annotations

from html import escape as esc

from ..layout import badge, card, empty, h1, page, score_bar

KIND = {
    "apply":    ("Send application", "risky"),
    "followup": ("Follow-up email",  "risky"),
    "project":  ("Build project",    "safe"),
    "profile":  ("Profile edit",     "safe"),
}


def _row(p: dict) -> str:
    label, risk = KIND.get(p["kind"], (p["kind"], ""))
    score = score_bar(p["score"]) if p["score"] else ""
    checked = " checked" if risk == "risky" else ""
    return (
        f"<label class='qrow {risk}'>"
        f"<input type=checkbox name=approve value='{esc(p['id'])}'{checked}>"
        f"<span class=qbody>"
        f"<span class=qhead>{badge(label, risk)}<b>{esc(p['target'])}</b>{score}</span>"
        f"<span class=muted>{esc(p['summary'])}</span>"
        f"<span class='risk {risk}'>{esc(p['risk'])}</span>"
        f"</span></label>"
    )


def render(proposals: list[dict], pending: int) -> str:
    if not proposals:
        return page("Queue", h1("Queue") + empty("Nothing waiting. The system is working."),
                    active="/queue", pending=pending)

    risky = sum(1 for p in proposals if KIND.get(p["kind"], ("", ""))[1] == "risky")
    rows = "".join(_row(p) for p in proposals)

    return page(
        "Queue",
        h1("Queue", "The only place decisions are made. Nothing leaves this machine "
                    "without a tick here.")
        + card(
            f"<div class=qsum><b>{len(proposals)} waiting</b>"
            f"<span class=muted>{risky} of them cannot be undone once sent</span>"
            "<span class=spacer></span>"
            "<span class=muted>Approving a batch takes about 30 seconds. "
            "The system then works through it over the next few hours.</span></div>", "qsum")
        + f"<form method=post action='/queue'><div class=qlist>{rows}</div>"
          "<div class=actbar><button class=primary type=submit>Approve selected</button>"
          "<button class=ghostbtn>Reject selected…</button>"
          "<span class=muted>Rejecting asks why — the reason becomes a filter rule.</span>"
          "</div></form>",
        active="/queue", pending=pending, mock=True, status="Running",
    )
