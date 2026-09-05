"""Adzuna GB — nhà UK, phủ thị trường UK rộng nhất. CẦN KEY MIỄN PHÍ.

Đăng ký ở developer.adzuna.com (2 phút), rồi điền app_id + app_key vào
config/config.toml. Chưa có key thì nguồn này tự tắt, không làm hỏng lần quét.
"""

from __future__ import annotations

import urllib.parse

from .base import Posting, get_json, strip_html

NAME = "adzuna"
URL = "https://api.adzuna.com/v1/api/jobs/gb/search/{page}"


def fetch(app_id: str, app_key: str, what: str, where: str = "london",
          pages: int = 3, max_days_old: int = 30) -> list[Posting]:
    out: list[Posting] = []
    for page in range(1, pages + 1):
        query = urllib.parse.urlencode({
            "app_id": app_id, "app_key": app_key, "results_per_page": 50,
            "what": what, "where": where, "max_days_old": max_days_old,
            "content-type": "application/json",
        })
        data = get_json(f"{URL.format(page=page)}?{query}")
        rows = data.get("results") or []
        if not rows:
            break
        for row in rows:
            salary_min, salary_max = row.get("salary_min"), row.get("salary_max")
            salary = (f"£{int(salary_min):,} – £{int(salary_max):,}"
                      if salary_min and salary_max else "")
            out.append(Posting(
                source_id=str(row.get("id")),
                title=(row.get("title") or "").strip(),
                company=((row.get("company") or {}).get("display_name") or "").strip(),
                location=((row.get("location") or {}).get("display_name") or "").strip(),
                salary=salary,
                url=row.get("redirect_url", ""),
                posted_at=str(row.get("created") or ""),
                description=strip_html(row.get("description", ""))[:20000],
                payload={"id": row.get("id"), "category":
                         (row.get("category") or {}).get("label"), "query": what},
            ))
    return out
