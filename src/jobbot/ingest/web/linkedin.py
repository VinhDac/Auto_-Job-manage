"""LinkedIn — chỉ tin tuyển dụng CÔNG KHAI, KHÔNG đăng nhập.

Ranh giới, cố ý và không thoả hiệp:

    ĐƯỢC   trang tin công khai, xem khi chưa đăng nhập, nhịp người
    KHÔNG  đăng nhập tài khoản người dùng   -> đó là thứ mất được, và mất là
                                               mất luôn mạng lưới nghề nghiệp
    KHÔNG  hồ sơ cá nhân, kết nối, tin nhắn -> đó là thứ LinkedIn kiện Proxycurl
    KHÔNG  cãi lại khi bị chặn              -> chặn thì dừng, ghi nhận, đi tiếp

Chạy trên profile Chrome riêng, không đăng nhập gì cả. Không có tài khoản thì
không có tài khoản nào để mất.

Dùng đúng endpoint LinkedIn tự phục vụ khách chưa đăng nhập
(`/jobs-guest/jobs/api/seeMoreJobPostings/search`), 10 tin một trang.

LƯU Ý: việc này vẫn nằm ngoài Điều khoản sử dụng của LinkedIn (mục 8.2). Vin đã
được nói rõ điều đó và tự quyết định. Ghi lại ở đây để người đọc code sau này biết.
"""

from __future__ import annotations

import random
import re
import time
import urllib.parse

from ..base import Posting, strip_html
from .base import Blocked, Health, grab, open_page

NAME = "linkedin"
GUEST = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
         "?keywords={q}&location={loc}&f_E={exp}&start={start}")
# Mô tả đầy đủ, vẫn là đường LinkedIn phục vụ khách chưa đăng nhập.
GUEST_JOB = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
VIEW = "https://www.linkedin.com/jobs/view/{jid}/"
PER_PAGE = 10

# f_E: 1=internship 2=entry 3=associate 4=mid-senior
EXPERIENCE = {"intern": "1", "grad": "2", "grad_scheme": "2", "junior": "2,3",
              "mid": "3,4", "senior": "4", "lead": "4"}

# Nhịp chậm hơn hẳn nguồn khác. Không phải để né — mà vì đây là bên duy nhất
# mình đang ở nhờ, nên đi nhẹ chân.
PAUSE = (2.5, 5.0)

LIST_JS = """
(() => {
  try {
    const out = [];
    for (const li of document.querySelectorAll('li')) {
      const a = li.querySelector('a[href*="/jobs/view/"]');
      if (!a) continue;
      const pick = s => (li.querySelector(s) || {}).innerText || '';
      const t = li.querySelector('time');
      out.push({
        title: pick('h3').trim(),
        company: pick('a.hidden-nested-link').trim() || pick('h4').trim(),
        location: pick('[class*=location]').trim(),
        url: a.getAttribute('href').split('?')[0],
        posted: t ? (t.getAttribute('datetime') || t.innerText.trim()) : ''
      });
    }
    return JSON.stringify(out);
  } catch (e) { return "[]"; }
})()
"""

DETAIL_JS = """
(() => {
  try {
    const box = document.querySelector('[class*=show-more-less-html__markup]')
             || document.querySelector('[class*=description__text]')
             || document.querySelector('section[class*=description]');
    const crit = [...document.querySelectorAll('[class*=job-criteria__item]')]
        .map(e => e.innerText.replace(/\\s+/g, ' ').trim());
    return JSON.stringify([{
      description: box ? box.innerText.trim().slice(0, 20000) : '',
      criteria: crit.join(' | ').slice(0, 400)
    }]);
  } catch (e) { return "[]"; }
})()
"""

JOB_ID = re.compile(r"-(\d{6,})/?$")


def _pause() -> None:
    time.sleep(random.uniform(*PAUSE))


def _from_row(row: dict) -> Posting | None:
    url = row.get("url") or ""
    found = JOB_ID.search(url)
    if not found or not row.get("title"):
        return None
    # LỖI ĐÃ SỬA: href trong kết quả tìm kiếm trỏ về tên miền theo nước
    # (uk.linkedin.com), và tên miền đó đá thẳng sang trang đăng ký — nên vòng
    # đọc kỹ chỉ nhận được "Sign Up | LinkedIn". Dựng lại URL từ id trên www.
    jid = found.group(1)
    return Posting(
        source_id=jid,
        title=row["title"].strip(),
        company=(row.get("company") or "unknown").strip(),
        location=(row.get("location") or "").strip(),
        url=VIEW.format(jid=jid),
        posted_at=row.get("posted", ""),
        payload={"guest": True})


def fetch(tab, queries: list[str], location: str = "London",
          levels: list[str] | None = None, pages: int = 3,
          deep: bool = True) -> list[Posting]:
    exp = ",".join(sorted({e for lv in (levels or ["grad", "junior"])
                           for e in EXPERIENCE.get(lv, "2").split(",")}))
    found: dict[str, Posting] = {}

    for query in queries:
        for page in range(pages):
            url = GUEST.format(q=urllib.parse.quote(query),
                               loc=urllib.parse.quote(location),
                               exp=urllib.parse.quote(exp), start=page * PER_PAGE)
            open_page(tab, url, timeout=30)          # Blocked -> ném lên trên, không cãi
            rows = grab(tab, LIST_JS)
            if not rows:
                break
            for row in rows:
                item = _from_row(row)
                if item:
                    found.setdefault(item.source_id, item)
            _pause()

    if not deep:
        return list(found.values()), Health(0, 0)

    health = Health(attempted=len(found), failed=0)
    for item in found.values():
        try:
            open_page(tab, GUEST_JOB.format(jid=item.source_id), timeout=30)
            detail = grab(tab, DETAIL_JS)
            raw = detail[0].get("description", "") if detail else ""
            if len(raw) < 200:            # mở được trang nhưng không có mô tả = hỏng
                health.failed += 1
                health.note(f"{item.source_id}: mô tả rỗng")
            else:
                item.raw_body = raw[:60000]
                item.description = strip_html(raw)[:20000]
                item.payload["criteria"] = detail[0].get("criteria", "")
        except Blocked:
            health.note("bị chặn giữa chừng")
            break                          # bị chặn -> dừng hẳn, không cãi lại
        except Exception as exc:           # noqa: BLE001
            health.failed += 1
            health.note(f"{type(exc).__name__}: {str(exc)[:44]}")
        _pause()
    return list(found.values()), health
