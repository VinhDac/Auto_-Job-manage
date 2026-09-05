"""Projects — một project cho mỗi NHÓM JD, một trang kết quả cho mỗi JD.

200 JD mà 200 project thì không cái nào sâu. 200 JD thật ra chỉ có 5-8 nhóm.
Xem docs/strategy.md §6.
"""

from __future__ import annotations

from html import escape as esc

from ..layout import badge, card, h1, page

STATUS = {"ready": ("ready", "ok"), "building": ("building", "hi"),
          "proposed": ("proposed", "")}


def render(clusters: list[dict], sample: dict, pending: int) -> str:
    cards = ""
    for c in clusters:
        label, kind = STATUS.get(c["status"], (c["status"], ""))
        number = (f"<div class=num>{esc(c['number'])}</div>"
                  if c["number"] != "—" else "")
        pages = (f"<span class=muted>{c['pages']} tailored pages</span>"
                 if c["pages"] else "<span class=muted>no pages yet</span>")
        cards += card(
            f"<div class=prow><b>{esc(c['cluster'])}</b>{badge(label, kind)}"
            f"<span class=spacer></span>"
            f"<span class=muted>covers {c['jobs']} postings</span></div>"
            f"<div class=ptitle>{esc(c['title'])}</div>{number}"
            f"<div class=pfoot>{pages}</div>", "proj")

    parts = "".join(f"<li>{esc(m)}</li>" for m in sample["method"])
    example = card(
        f"<div class=muted>Written for: {esc(sample['for_job'])}</div>"
        f"<h3>Problem</h3><p>{esc(sample['problem'])}</p>"
        f"<h3>What I did</h3><ul class=changes>{parts}</ul>"
        f"<h3>The number</h3><p class=num>{esc(sample['number'])}</p>"
        f"<h3>What I traded away</h3><p>{esc(sample['tradeoff'])}</p>"
        f"<h3>Code</h3><p class=muted>{esc(sample['code'])}</p>", "onepage")

    return page(
        "Projects",
        h1("Projects", "One real project per cluster of similar postings — "
                       "and a separate one-page write-up per posting.")
        + cards
        + "<h2>What a write-up looks like</h2>"
        + "<p class=lead>Five parts, fits one screen, reads in 90 seconds. "
          "The last two parts are the ones experienced readers actually trust.</p>"
        + example,
        active="/projects", pending=pending, mock=True, status="Running",
    )
