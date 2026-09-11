"""Bấm Gửi — TÁCH RIÊNG khỏi phần điền, có chủ ý.

`run.py` điền form và trong đó KHÔNG có một lệnh bấm gửi nào; test canh điều
đó. Nghĩa là dù `run.py` hỏng kiểu gì, nó cũng không nộp thay Vin được. Việc
gửi nằm gọn trong tệp này, và chỉ một đường duy nhất gọi tới: Vin bấm nút Gửi
trên đúng dòng đó ở tab Quản lí. Một lần bấm, một lá đơn.

BA LUẬT TRƯỚC KHI BẤM — máy đọc lại form vừa điền và TỪ CHỐI gửi nếu:

    1. còn ô bắt buộc nào trống  (kể cả ô máy cố tình không điền:
       sponsorship, GPA, ngày tốt nghiệp, tick điều khoản)
    2. không tìm thấy đúng một nút gửi của CHÍNH form đã điền
    3. điểm sắp bấm không nằm trên nút đó

Vì sao đọc lại chứ không tin bản báo cáo lúc điền: giữa lúc điền và lúc bấm là
Vin ngồi trả lời mấy ô còn lại. Trạng thái đúng nằm trên trang, không nằm
trong bộ nhớ.

Tìm lại đúng tab bằng dấu `data-jbjob` mà lúc điền đã đóng lên trang — không
giữ tay cầm trong bộ nhớ máy chủ, nên khởi động lại web vẫn gửi được.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field as _field

from ..browser import cdp, chrome
from . import fields as F

PORT = chrome.APPLY_PORT

# Chữ trên nút gửi của các ATS đã đo: Greenhouse "Submit Application",
# Ashby "Submit Application", Lever "Submit application".
SUBMIT_TEXT = re.compile(r"^(submit|apply|send|nộp|gửi)\b", re.I)

# TÌM và NGẮM trong MỘT lần gọi. Trước đây tách làm hai khối JS lặp lại y hệt
# logic chọn nút: một khối duyệt, một khối lấy toạ độ. Hai bản sao của cùng một
# luật thì có ngày lệch nhau — và lệch ở đây nghĩa là duyệt nút này rồi bấm nút
# kia, trên một hành động không rút lại được.
#
# Nút gửi phải nằm trong ĐÚNG cái form chứa những ô ta vừa điền (`[data-jb]`),
# không phải một form bất kỳ nào khác trên trang.
AIM_JS = r"""
(() => {
  // Form nào chứa NHIỀU Ô ĐÃ ĐIỀN nhất mới là form của ta. Lấy
  // `querySelector('[data-jb]')` — ô ĐẦU TIÊN của cả trang — là sai: trang
  // tuyển dụng hay có một form tìm kiếm hoặc đăng ký nhận tin đứng trước, và
  // nếu ô đầu rơi vào form đó thì máy đi bấm nút của form đó. Chốt `inform`
  // cũ so nút với chính cái form vừa lấy ra nên luôn đúng — một chốt rỗng.
  const tally = new Map();
  for (const el of document.querySelectorAll('[data-jb]')) {
    const f = el.closest('form');
    if (f) tally.set(f, (tally.get(f) || 0) + 1);
  }
  if (!tally.size) return JSON.stringify({err: 'không thấy form đã điền'});
  let form = null, best = -1;
  for (const [f, n] of tally) { if (n > best) { best = n; form = f; } }

  const all = Array.from(form.querySelectorAll(
      'button[type="submit"], input[type="submit"], button:not([type])'))
    .filter(b => !b.disabled && b.offsetParent);
  // CHỈ nút mang chữ gửi. Không có thì DỪNG, không lùi về "nút duy nhất còn
  // lại" — nút đó có thể là "Save draft", "Add another", "Upload".
  const named = all.filter(b => %TEXT%.test(((b.innerText || b.value || '') + '').trim()));
  if (named.length !== 1)
    return JSON.stringify({err: `${named.length} nút mang chữ gửi trong ${all.length} nút`});
  const pick = named;

  const b = pick[0];
  b.scrollIntoView({block: 'center', behavior: 'instant'});
  const r = b.getBoundingClientRect();
  const x = r.x + r.width / 2, y = r.y + r.height / 2;
  const on = document.elementFromPoint(x, y);
  return JSON.stringify({
    x: x, y: y, tag: b.tagName,
    inform: form.contains(b),
    fields: best,
    hits: !!on && (on === b || b.contains(on)),
    text: ((b.innerText || b.value || '') + '').trim(),
  });
})()
"""

MARK_JS = "document.documentElement.setAttribute('data-jbjob', '%JOB%')"
AFTER_JS = r"""
(() => ({url: location.href,
         text: (document.body ? document.body.innerText : '').slice(0, 600)}))()
"""


@dataclass
class Sent:
    ok: bool = False
    why: str = ""
    missing: list[str] = _field(default_factory=list)
    button: str = ""
    landed: str = ""


def _js(tab, template: str, **kw):
    text = template
    for key, value in kw.items():
        text = text.replace(f"%{key}%", str(value))
    return tab.eval(text)


def mark(tab, job: int) -> None:
    """Đóng dấu số hiệu tin lên trang, để lát nữa tìm lại đúng tab này."""
    try:
        _js(tab, MARK_JS, JOB=int(job))
    except cdp.CDPError:
        pass


def find(job: int, port: int = PORT):
    """Tab đang mở form của tin này. Không có thì trả None."""
    for page in cdp.pages(port):
        try:
            tab = cdp.attach(page["id"], port)
        except Exception:                            # noqa: BLE001
            continue
        try:
            if str(tab.eval("document.documentElement.getAttribute('data-jbjob')")
                   or "") == str(job):
                return tab
        except cdp.CDPError:
            pass
        tab.ws.close()                               # không phải tab cần tìm
    return None


def missing(tab) -> list[str]:
    """Ô bắt buộc còn trống. Rỗng nghĩa là form đã đủ để gửi."""
    out = []
    for item in F.read(tab):
        if item.get("required") and not (item.get("value") or "").strip():
            out.append(item["label"] or item["name"] or "?")
    return out


def submit(tab, job: int | None = None) -> Sent:
    """Kiểm rồi mới bấm. Không đủ điều kiện thì KHÔNG bấm, và nói vì sao."""
    # Trang KHÔNG CÒN Ô NÀO nghĩa là form đã đi rồi — thường là vừa gửi xong
    # và trang đã nhảy sang lời cảm ơn. Lúc đó missing() trả rỗng (không ô nào
    # thì không ô nào trống), nên nếu không chặn ở đây thì bấm lần hai sẽ đi
    # tìm "một nút bất kỳ trong form bất kỳ" trên trang cảm ơn.
    if not F.read(tab):
        return Sent(False, "trang không còn form — có thể đã gửi rồi")
    gaps = missing(tab)
    if gaps:
        return Sent(False, "còn ô bắt buộc chưa trả lời", gaps)

    # Cuộn trước, đo sau: trang đặt cuộn mượt thì đo ngay là lấy TOẠ ĐỘ CŨ và
    # cú bấm rơi ra ngoài màn hình (đo được y=1252 trên màn hình cao 900).
    _js(tab, AIM_JS, TEXT=f"/{SUBMIT_TEXT.pattern}/i")
    time.sleep(0.45)
    aim = json.loads(_js(tab, AIM_JS, TEXT=f"/{SUBMIT_TEXT.pattern}/i"))
    if aim.get("err"):
        return Sent(False, aim["err"])
    if not aim.get("inform"):
        return Sent(False, "nút không thuộc form đã điền")
    if not aim.get("hits"):
        return Sent(False, "điểm bấm không nằm trên nút")

    before = json.loads(json.dumps(tab.eval(AFTER_JS) or {}))
    for kind in ("mousePressed", "mouseReleased"):
        tab.call("Input.dispatchMouseEvent",
                 {"type": kind, "x": aim["x"], "y": aim["y"],
                  "button": "left", "clickCount": 1})
    time.sleep(3.5)
    after = json.loads(json.dumps(tab.eval(AFTER_JS) or {}))

    # BẰNG CHỨNG, không phải "đã bắn được sự kiện chuột". Bản cũ tính `good`
    # rồi vứt đi và luôn trả ok=True — nên một form bị ATS từ chối (thiếu ô nó
    # tự kiểm, hết hạn tin, chống bot) vẫn được ghi vào bảng là "đã nộp", và
    # Vin đinh ninh đã nộp trong khi chưa.
    body = (after.get("text") or "").lower()
    said = any(w in body for w in ("thank", "received", "submitted", "success",
                                   "application sent", "we have your", "đã nhận"))
    moved = (after.get("url") or "") != (before.get("url") or "")
    gone = not F.read(tab)                       # form biến mất = đã đi
    if not (said or moved or gone):
        return Sent(False, "bấm rồi mà trang không đổi gì — có thể chưa gửi được",
                    button=aim.get("text", ""),
                    landed=(after.get("url") or "")[:120])
    why = "đã gửi" + ("" if said else
                      " (trang đổi nhưng không nói lời xác nhận)")
    return Sent(True, why, button=aim.get("text", ""),
                landed=(after.get("url") or "")[:120])
