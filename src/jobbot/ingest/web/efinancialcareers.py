"""eFinancialCareers — board tài chính lớn nhất London. Không có API công khai.

Hai vòng, cố ý:
    1. Trang kết quả -> tiêu đề, công ty, địa điểm, link
    2. Mở TỪNG tin -> mô tả đầy đủ

Vòng 2 chậm (~3 giây một tin). Không sao: người ta mất một tuần mới trả lời,
nên vài phút của máy không đổi được gì. Đọc kỹ mới đổi được.
"""

from __future__ import annotations

import time
import urllib.parse

from ..base import Posting, strip_html
from .base import Blocked, Health, grab, open_page

NAME = "efinancialcareers"
BASE = "https://www.efinancialcareers.co.uk"
SEARCH = BASE + "/search?q={q}&location={loc}"

# Lấy thẻ tin từ trang kết quả. Bỏ link "Apply now" — nó trỏ cùng chỗ
# nhưng không mang tiêu đề.
# Selector thật, đọc từ DOM của trang (04/09/2026):
#   h3                       tiêu đề
#   div.company              tên công ty
#   span.dot-divider (1)     địa điểm
#   span.dot-divider (2)     loại hợp đồng
#   span.dot-divider-after   lương
#   span.font-helper-text    thời điểm đăng
# Bóc từ khối chữ gộp thì ra "Apply now Save Citi London" — sai hoàn toàn.
LIST_JS = """
(() => {
  try {
    const out = [], seen = new Set();
    for (const a of document.querySelectorAll('a[href*="/jobs-"]')) {
      const title = (a.innerText || '').trim();
      if (title.length < 9 || /^(apply now|save|view)$/i.test(title)) continue;
      const href = a.href.split('?')[0];
      if (seen.has(href)) continue;
      seen.add(href);
      const card = a.closest('article,li,div[class*=card],div[class*=job]');
      const pick = s => card ? (card.querySelector(s)||{}).innerText : '';
      const divs = card ? [...card.querySelectorAll('span[class*=dot-divider]')] : [];
      out.push({
        title: (pick('h3') || title).trim(),
        url: href,
        company: (pick('[class*=company]') || '').trim(),
        location: (divs[0] ? divs[0].innerText : '').trim(),
        contract: (divs[1] ? divs[1].innerText : '').trim(),
        salary: (pick('[class*=dot-divider-after]') || '').trim(),
        posted: (pick('[class*=font-helper-text]') || '').trim()
      });
    }
    return JSON.stringify(out);
  } catch (err) { return "[]"; }
})()
"""

DETAIL_JS = """
(() => {
  try {
    const pick = s => document.querySelector(s);
    const body = pick('[class*=job-description]') || pick('[class*=jobDescription]')
              || pick('article') || document.body;
    return JSON.stringify([{
      description: body ? body.innerText.replace(/\\n{3,}/g, '\\n\\n').trim().slice(0, 20000) : ''
    }]);
  } catch (err) { return "[]"; }
})()
"""


# Ô cuối thẻ khi thì lương ("Competitive", "£65,000"), khi thì hình thức làm
# việc ("Hybrid", "In-Office"). Không phân biệt thì cột lương ra rác.
WORK_MODE = {"hybrid", "in-office", "remote", "on-site", "onsite", "flexible"}


def _from_row(row: dict) -> Posting:
    tail = (row.get("salary") or "").strip()
    mode = tail if tail.lower().lstrip("£ ") in WORK_MODE else ""
    salary = "" if mode else tail
    return Posting(
        source_id=row["url"].rsplit("/", 1)[-1][:120],
        title=row["title"],
        company=row.get("company") or "unknown",
        location=row.get("location") or "London, United Kingdom",
        salary=salary,
        remote="remote" in mode.lower(),
        url=row["url"],
        payload={"contract": row.get("contract", ""), "work_mode": mode,
                 "posted_text": row.get("posted", "")})


def fetch(tab, queries: list[str], location: str = "London",
          per_query: int = 25, deep: bool = True) -> list[Posting]:
    """Tìm theo từng chức danh, rồi mở từng tin để lấy mô tả đầy đủ."""
    found: dict[str, Posting] = {}

    for query in queries:
        url = SEARCH.format(q=urllib.parse.quote(query),
                            loc=urllib.parse.quote(location))
        try:
            open_page(tab, url)
        except Blocked:
            raise
        for row in grab(tab, LIST_JS)[:per_query]:
            item = _from_row(row)
            found.setdefault(item.url, item)

    if not deep:
        return list(found.values()), Health(0, 0)

    health = Health(attempted=len(found), failed=0)
    for item in found.values():                    # vòng 2: đọc kỹ từng tin
        try:
            open_page(tab, item.url, wait_for="body", timeout=30)
            detail = grab(tab, DETAIL_JS)
            raw = detail[0].get("description", "") if detail else ""
            if len(raw) < 200:
                health.failed += 1
                health.note("mô tả rỗng")
            else:
                item.raw_body = raw[:60000]
                item.description = strip_html(raw)[:20000]
        except Blocked:
            health.note("bị chặn giữa chừng")
            break
        except Exception as exc:                   # noqa: BLE001
            health.failed += 1
            health.note(f"{type(exc).__name__}: {str(exc)[:44]}")
        time.sleep(0.5)
    return list(found.values()), health
