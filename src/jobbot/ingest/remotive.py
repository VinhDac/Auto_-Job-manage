"""Remotive — remote toàn cầu, không cần key. Ít việc grad ở London, nhưng rẻ."""

from __future__ import annotations

from .base import Posting, get_json, strip_html

NAME = "remotive"
URL = "https://remotive.com/api/remote-jobs?limit=200"


def fetch() -> list[Posting]:
    data = get_json(URL)
    out: list[Posting] = []
    for row in data.get("jobs") or []:
        out.append(Posting(
            source_id=str(row.get("id")),
            title=(row.get("title") or "").strip(),
            company=(row.get("company_name") or "").strip(),
            location=(row.get("candidate_required_location") or "").strip(),
            remote=True,
            salary=(row.get("salary") or "").strip(),
            url=row.get("url", ""),
            posted_at=str(row.get("publication_date") or ""),
            description=strip_html(row.get("description", ""))[:20000],
            payload={"id": row.get("id"), "category": row.get("category"),
                     "tags": row.get("tags"), "job_type": row.get("job_type")},
        ))
    return out
