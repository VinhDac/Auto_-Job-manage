"""Trang CV tuỳ biến cho một tin cụ thể."""

from __future__ import annotations

from html import escape as esc

from ...cv.build import TailoredCV
from ...cv.render import audit, paper
from ..layout import card, h1, page


def render(job: dict, cv: TailoredCV) -> str:
    return page(
        f"CV — {job['title']}",
        f"<a class=back href='/jobs/{esc(job['id'])}'>← {esc(job['title'])}</a>"
        + h1("Tailored CV",
             f"Built for {job['company']} — {job['title']}. Every line is a sentence "
             f"from your own profile: the system selects and orders, it never writes.")
        + paper(cv)
        + audit(cv),
        active="/jobs", status="Running",
    )
