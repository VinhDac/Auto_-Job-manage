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

from ...core.journal import SEARCH, log as jlog
from ..base import Posting, strip_html
from .base import Blocked, Health, grab, open_page

NAME = "linkedin"
GUEST = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
         "?keywords={q}&location={loc}&f_E={exp}&start={start}")
# Mô tả đầy đủ, vẫn là đường LinkedIn phục vụ khách chưa đăng nhập.
GUEST_JOB = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
VIEW = "https://www.linkedin.com/jobs/view/{jid}/"
PER_PAGE = 10
# Cứ bấy nhiêu tin đọc kỹ thì nói một câu vào nhật ký. Không ghi từng tin:
# 2.297 dòng cho một lần quét thì nhật ký không đọc được nữa. Không ghi gì
# thì im lặng 27 phút — đã đo trên lượt quét 19:22. 25 tin ≈ 2 phút một câu.
NHIP_BAO = 25

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
      // innerHTML chứ KHÔNG phải innerText: innerText của <ul><li> trả về
      // các dòng trần, mất dấu gạch đầu dòng — mà bộ tách yêu cầu nhận
      // diện danh sách BẰNG dấu đó. strip_html() dựng lại '· ' từ <li>.
      description: box ? box.innerHTML.slice(0, 60000) : '',
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


# Thị trường trong hồ sơ -> chỗ LinkedIn hiểu. Trước đây địa điểm là chuỗi
# cứng "London" trong chữ ký hàm và KHÔNG ai truyền vào — nên ô Thị trường
# người dùng chọn chưa bao giờ đi tới đâu.
MARKET_PLACE = {
    "uk_onsite": "United Kingdom",
    "uk_remote": "United Kingdom",
    "eu_remote": "European Union",
    "us_remote": "United States",
    "global_remote": "",            # rỗng = LinkedIn tìm toàn cầu
    "relocate": "",
}


def places_for(markets: list[str]) -> list[str]:
    """Cần tìm ở mấy nơi. Giữ thứ tự khai trong hồ sơ, bỏ trùng.

    'United Kingdom' rộng hơn 'London' và bao cả London — chọn nơi rộng hơn
    vì hồ sơ nói uk_onsite + uk_remote, không nói riêng London.
    """
    out: list[str] = []
    for m in markets or []:
        place = MARKET_PLACE.get(m)
        if place is not None and place not in out:
            out.append(place)
    return out or ["United Kingdom"]


# Chức danh gửi đi mỗi vòng. Có TRẦN, và trần đó được GHI RA nhật ký khi
# chạm — không cắt lặng lẽ như `titles[:5]` trước đây.
MAX_QUERIES = 20


def signed_in(tab) -> bool:
    """Profile này có đang đăng nhập LinkedIn không.

    `li_at` là cookie phiên của LinkedIn. Đọc bằng JS không thấy (httpOnly),
    nên hỏi thẳng trình duyệt qua CDP.
    """
    try:
        got = tab.call("Network.getCookies",
                       {"urls": ["https://www.linkedin.com/"]})
    except Exception:                                # noqa: BLE001
        return False
    return any(c.get("name") == "li_at" for c in got.get("cookies", []))


def fetch(tab, queries: list[str], location: str = "United Kingdom",
          levels: list[str] | None = None, pages: int = 3,
          deep: bool = True, skip: frozenset[str] = frozenset(),
          stop=None) -> list[Posting]:
    """Tìm rồi đọc kỹ tin LinkedIn.

    skip = id những tin ĐÃ có mô tả. Vòng đọc kỹ bỏ qua chúng.

    Đây là chỗ sửa quan trọng nhất của cả bước 1: trước đây vòng đọc kỹ mở
    lại TOÀN BỘ tin tìm được, mỗi giờ. Trên máy thật 194/196 tin đã có mô tả
    từ trước, nên 97% thời gian là đọc lại thứ đã đọc — 8-16 phút mở Chrome
    liên tục mỗi tiếng, ~4.600 lượt gọi mỗi ngày, và LinkedIn bóp lại 40-82%.
    """
    # Ranh buộc ở đầu tệp — "không có tài khoản thì không có tài khoản nào để
    # mất" — giờ do MÁY canh, không do người nhớ. Đã xảy ra một lần: cửa sổ
    # quét và cửa sổ nộp trông giống hệt nhau, đăng nhập nhầm là mỗi lần quét
    # chạy dưới tài khoản thật.
    if signed_in(tab):
        raise Blocked(
            "profile QUÉT đang đăng nhập LinkedIn — quét bằng tài khoản thật là "
            "cách mất tài khoản. Đăng xuất ở cửa sổ quét; đăng nhập ở cửa sổ NỘP.")

    if len(queries) > MAX_QUERIES:
        jlog.warn(SEARCH, f"chỉ tìm {MAX_QUERIES}/{len(queries)} chức danh"
                          f" — bỏ: {', '.join(queries[MAX_QUERIES:])}")
        queries = queries[:MAX_QUERIES]
    exp = ",".join(sorted({e for lv in (levels or ["grad", "junior"])
                           for e in EXPERIENCE.get(lv, "2").split(",")}))
    found: dict[str, Posting] = {}
    dut = ""                  # lý do đứt giữa chừng; rỗng = chạy trọn

    # Ghép sẵn từng cặp (chức danh, nơi) rồi chạy MỘT vòng — lồng hai vòng
    # vào nhau thì thân vòng thụt thêm một tầng và lệch cả file.
    places = location if isinstance(location, list) else [location]
    pairs = [(q, p) for q in queries for p in places]

    for step, (query, place) in enumerate(pairs, 1):
        if stop and stop():
            jlog.warn(SEARCH, f"dừng theo yêu cầu — mới xong {step - 1}/{len(pairs)} lượt tìm")
            break
        # `place` rỗng nghĩa là LinkedIn tìm toàn cầu. Để nguyên thì màn hình
        # hiện "Operations Analyst · " — một dấu chấm giữa treo lơ lửng, người
        # đọc tưởng chữ bị cắt mất.
        o_dau = place or "toàn cầu"
        jlog.progress(SEARCH, f"tìm LinkedIn · {query} · {o_dau}",
                      step, len(pairs))
        truoc, so_trang = len(found), 0
        try:
            for page in range(pages):
                url = GUEST.format(q=urllib.parse.quote(query),
                                   loc=urllib.parse.quote(place),
                                   exp=urllib.parse.quote(exp), start=page * PER_PAGE)
                open_page(tab, url, timeout=30)
                rows = grab(tab, LIST_JS)
                if not rows:
                    break
                so_trang += 1
                for row in rows:
                    item = _from_row(row)
                    if item:
                        found.setdefault(item.source_id, item)
                _pause()
        except Exception as exc:                     # noqa: BLE001
            # ĐỨT GIỮA CHỪNG THÌ GIỮ LẠI THỨ ĐÃ TÌM ĐƯỢC, không ném lên trên.
            #
            # Trước đây lỗi ở đây bay thẳng ra ngoài fetch(), nên `items` không
            # bao giờ trả về và save_batch() không bao giờ chạy: cả kho tin đã
            # tìm được đổ đi sạch. Xảy ra thật lúc 17:18 — 48/76 lượt tìm xong,
            # một ConnectionResetError, fetched=0.
            #
            # Máy ngủ dậy là đúng cái lỗi này: socket CDP chết, mà app chạy
            # 24/7 nên chuyện đó là chuyện thường ngày, không phải tai nạn.
            dut = f"{type(exc).__name__}: {str(exc)[:50]}"
            jlog.warn(SEARCH, f"đứt ở lượt {step}/{len(pairs)} ({dut})"
                              f" — giữ lại {len(found)} tin đã tìm được")
            break
        # MỘT DÒNG CHO MỖI LƯỢT TÌM. Trước đây cả vòng này im lặng: đo trên
        # lượt quét 19:22 là 31 phút chạy mà nhật ký để lại đúng một dòng ở
        # đầu. Người dùng ngồi nhìn một thanh tiến độ nhích, không biết máy
        # đang gõ chức danh nào, ở đâu, được gì.
        con = jlog.remaining(SEARCH)
        jlog.emit(SEARCH,
                  f"tìm · {query} · {o_dau} — {len(found) - truoc} tin mới"
                  f" / {so_trang} trang · kho {len(found)}"
                  f"{f' · còn {con}' if con else ''}")

    if not deep or dut:
        # Đứt rồi thì đừng đọc kỹ nữa: cổng vừa từ chối mình xong, mở tiếp
        # 2.000 trang chỉ để nhận 2.000 lỗi. Trả tin về cho save_batch ghi
        # xuống, lần quét sau đọc kỹ tiếp — save_batch vá mô tả vào đúng dòng
        # cũ, nên chỗ dở không thành lỗ hổng.
        suc = Health(0, 0)
        if dut:
            suc.broke(f"đứt khi đang tìm: {dut}")
        return list(found.values()), suc

    items = list(found.values())
    fresh = [i for i in items if i.source_id not in skip]
    health = Health(attempted=len(fresh), failed=0)
    jlog.emit(SEARCH, f"linkedin: tìm được {len(items)} tin"
                      + (f", {len(items) - len(fresh)} đã đọc từ trước"
                         f" -> chỉ đọc kỹ {len(fresh)}" if skip else
                         f", đọc kỹ cả {len(fresh)}"))
    for index, item in enumerate(fresh):
        # Điểm ngắt THẬT: đây là vòng tốn 8-16 phút, mở Chrome đọc từng tin.
        # Đặt cờ dừng ở ngoài vòng này thì bấm Dừng xong vẫn phải chờ hết.
        if stop and stop():
            jlog.warn(SEARCH, f"dừng theo yêu cầu — đã đọc kỹ {index}/{len(fresh)} tin")
            break
        # Chỗ vòng quét đứng lâu nhất — mỗi tin nghỉ 2.5-5 giây. Không báo
        # tiến độ ở đây thì màn hình im lặng suốt.
        #
        # Viết TÊN TIN đang đọc vào thanh, không chỉ "đọc kỹ LinkedIn": người
        # dùng phải thấy máy đang mở cái gì, mới biết nó còn sống.
        jlog.progress(SEARCH, f"đọc kỹ · {item.title[:44]} — {item.company[:22]}",
                      index + 1, len(fresh))
        if index and index % NHIP_BAO == 0:
            con = jlog.remaining(SEARCH)
            jlog.emit(SEARCH, f"đọc kỹ {index}/{len(fresh)} tin"
                              f"{f' · còn {con}' if con else ''}"
                              f" · đang đọc: {item.title[:40]}")
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
            # Dừng hẳn, không cãi lại — nhưng phải NÓI RA là đã dừng, và số
            # tin còn lại chưa đọc được tính vào phần hỏng. Chỉ note() rồi
            # break thì failed=0 và lần quét này trông y hệt một lần thành công.
            health.block(f"bị chặn ở tin {index + 1}/{len(fresh)}",
                         unread=len(fresh) - index)
            break
        except Exception as exc:           # noqa: BLE001
            health.failed += 1
            health.note(f"{type(exc).__name__}: {str(exc)[:44]}")
        _pause()
    return items, health
