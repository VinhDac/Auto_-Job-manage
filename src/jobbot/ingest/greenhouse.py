"""Greenhouse — theo từng công ty, không cần key.

Nhiều quỹ và fintech ở London dùng Greenhouse: Man Group, Marshall Wace,
Jane Street, Optiver, IMC, Point72, Monzo, Wise, Tide.
Danh sách board nằm trong config, không nằm cứng ở đây.
"""

from __future__ import annotations

from .base import Posting, get_json, strip_html

NAME = "greenhouse"
URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"


def fetch_board(board: str) -> list[Posting]:
    data = get_json(URL.format(board=board))
    out: list[Posting] = []
    for row in data.get("jobs") or []:
        out.append(Posting(
            source_id=f"{board}:{row.get('id')}",
            title=(row.get("title") or "").strip(),
            company=(row.get("company_name") or board).strip(),
            location=((row.get("location") or {}).get("name") or "").strip(),
            url=row.get("absolute_url", ""),
            # updated_at, KHÔNG phải first_published: nhiều quỹ để tin mở nhiều năm
            # (Jane Street có tin first_published 2020). updated_at mới cho biết còn sống.
            posted_at=str(row.get("updated_at") or row.get("first_published") or ""),
            description=strip_html(row.get("content", ""))[:20000],
            raw_body=(row.get("content") or "")[:60000],
            payload={"board": board, "id": row.get("id"),
                     "departments": [d.get("name") for d in row.get("departments") or []],
                     "deadline": row.get("application_deadline"),
                     "first_published": row.get("first_published")},
        ))
    return out
