"""Arbeitnow — không cần key, phủ UK/EU tốt.

Đã đo: 59/175 tin trang đầu là UK. Đây là nguồn miễn phí tốt nhất hiện có.
API trả về theo trang, mỗi trang ~100 tin.
"""

from __future__ import annotations

from .base import Posting, get_json, strip_html

NAME = "arbeitnow"
URL = "https://www.arbeitnow.com/api/job-board-api"


def fetch(pages: int = 3) -> list[Posting]:
    out: list[Posting] = []
    for page in range(1, pages + 1):
        data = get_json(f"{URL}?page={page}")
        rows = data.get("data") or []
        if not rows:
            break
        for row in rows:
            out.append(Posting(
                source_id=str(row.get("slug") or row.get("url", "")),
                title=row.get("title", "").strip(),
                company=row.get("company_name", "").strip(),
                location=row.get("location", "").strip(),
                remote=bool(row.get("remote")),
                url=row.get("url", ""),
                posted_at=str(row.get("created_at", "")),
                description=strip_html(row.get("description", ""))[:20000],
                payload={k: row.get(k) for k in
                         ("slug", "title", "company_name", "location", "remote", "tags", "job_types")},
            ))
    return out
