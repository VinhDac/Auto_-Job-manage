"""Stats — đo thật. Đây cũng là nguyên liệu cho chính personal project."""

from __future__ import annotations

from html import escape as esc

from ..layout import card, h1, page


def _table(title: str, head: str, rows: str) -> str:
    return f"<h2>{esc(title)}</h2><table class=data><tr>{head}</tr>{rows}</table>"


def render(data: dict, pending: int) -> str:
    src = "".join(
        f"<tr><td>{esc(r['name'])}</td><td>{r['sent']}</td><td>{r['replies']}</td>"
        f"<td><span class=ratebar style='width:{max(r['rate'],2)}%'></span>{r['rate']}%</td></tr>"
        for r in data["by_source"])
    band = "".join(
        f"<tr><td>{esc(r['band'])}</td><td>{r['sent']}</td><td>{r['replies']}</td>"
        f"<td><span class=ratebar style='width:{max(r['rate'],2)}%'></span>{r['rate']}%</td></tr>"
        for r in data["by_score"])

    top = data["funnel"][0][1]
    funnel = "".join(
        f"<div class=frow><span class=fl>{esc(n)}</span>"
        f"<span class=ftrack><span class=ffill style='width:{max(v*100//top,1)}%'></span></span>"
        f"<b>{v:,}</b></div>" for n, v in data["funnel"])

    return page(
        "Stats",
        h1("Stats", "Real measurements on real applications. These numbers are also the "
                    "raw material for your own portfolio write-up.")
        + f"<div class=funnel>{funnel}</div>"
        + card(f"<b>What the data says</b><p>{esc(data['insight'])}</p>", "notice")
        + _table("Response rate by source",
                 "<th>Source</th><th>Sent</th><th>Replies</th><th>Rate</th>", src)
        + _table("Response rate by match score",
                 "<th>Score band</th><th>Sent</th><th>Replies</th><th>Rate</th>", band),
        active="/stats", pending=pending,
    )
