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

FIND_JS = r"""
(() => {
  const el = document.querySelector('[data-jb]');
  const form = el ? el.closest('form') : document.querySelector('form');
  if (!form) return JSON.stringify({err: 'không thấy form'});
  const spots = Array.from(form.querySelectorAll(
      'button[type="submit"], input[type="submit"], button:not([type])'))
    .filter(b => !b.disabled && b.offsetParent);
  const named = spots.filter(b => %TEXT%.test(
      ((b.innerText || b.value || '') + '').trim()));
  const pick = named.length ? named : spots;
  if (pick.length !== 1) return JSON.stringify({err: `tìm thấy ${pick.length} nút gửi`});
  const b = pick[0];
  b.scrollIntoView({block: 'center', behavior: 'instant'});
  return JSON.stringify({ready: true, text: ((b.innerText || b.value || '') + '').trim()});
})()
"""

AIM_JS = r"""
(() => {
  const el = document.querySelector('[data-jb]');
  const form = el ? el.closest('form') : document.querySelector('form');
  const spots = Array.from(form.querySelectorAll(
      'button[type="submit"], input[type="submit"], button:not([type])'))
    .filter(b => !b.disabled && b.offsetParent);
  const named = spots.filter(b => %TEXT%.test(((b.innerText || b.value || '') + '').trim()));
  const b = (named.length ? named : spots)[0];
  if (!b) return JSON.stringify({err: 'mất nút'});
  const r = b.getBoundingClientRect();
  const x = r.x + r.width / 2, y = r.y + r.height / 2;
  const on = document.elementFromPoint(x, y);
  return JSON.stringify({x: x, y: y, tag: b.tagName,
                         inform: !!b.closest('form'),
                         hits: !!on && (on === b || b.contains(on)),
                         text: ((b.innerText || b.value || '') + '').trim()});
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
    gaps = missing(tab)
    if gaps:
        return Sent(False, "còn ô bắt buộc chưa trả lời", gaps)

    where = json.loads(_js(tab, FIND_JS, TEXT=f"/{SUBMIT_TEXT.pattern}/i"))
    if where.get("err"):
        return Sent(False, where["err"])
    time.sleep(0.45)                                 # cuộn xong rồi mới đo
    aim = json.loads(_js(tab, AIM_JS, TEXT=f"/{SUBMIT_TEXT.pattern}/i"))
    if aim.get("err"):
        return Sent(False, aim["err"])
    if not aim.get("inform"):
        return Sent(False, "nút không thuộc form đã điền")
    if not aim.get("hits"):
        return Sent(False, "điểm bấm không nằm trên nút")

    for kind in ("mousePressed", "mouseReleased"):
        tab.call("Input.dispatchMouseEvent",
                 {"type": kind, "x": aim["x"], "y": aim["y"],
                  "button": "left", "clickCount": 1})
    time.sleep(3.5)
    after = json.loads(json.dumps(tab.eval(AFTER_JS) or {}))
    body = (after.get("text") or "").lower()
    good = any(w in body for w in ("thank", "received", "submitted", "application sent",
                                  "we have your", "success"))
    return Sent(True, "đã bấm gửi" + ("" if good else " — trang chưa xác nhận rõ"),
                button=aim.get("text", ""),
                landed=(after.get("url") or "")[:120])
