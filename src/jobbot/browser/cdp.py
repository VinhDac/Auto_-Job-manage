"""Nói chuyện với một tab Chrome qua DevTools Protocol.

Chỉ đủ những gì job board cần: mở trang, chờ, chạy JS, lấy HTML, cuộn, bấm.
Không phải thư viện automation đầy đủ — và cố ý không phải.
"""

from __future__ import annotations

import json
import random
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .chrome import PORT
from .ws import WebSocket

# Nhịp giống người: mỗi thao tác nghỉ một chút, và nghỉ không đều nhau.
# Không phải để né phát hiện — mà vì trang cần thời gian dựng, và bắn liên
# tiếp thì lấy về DOM chưa xong.
PAUSE = (0.6, 1.8)


class CDPError(RuntimeError):
    pass


def _targets(port: int) -> list[dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
        return json.load(r)


@dataclass
class Tab:
    ws: WebSocket
    target_id: str
    port: int = PORT
    _next: int = 1

    # --- nền ---------------------------------------------------------------
    def call(self, method: str, params: dict | None = None, timeout: float = 30.0) -> dict:
        self._next += 1
        message_id = self._next
        self.ws.send(json.dumps({"id": message_id, "method": method,
                                 "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = json.loads(self.ws.recv())
            if data.get("id") != message_id:
                continue                            # sự kiện, không phải phản hồi
            if "error" in data:
                raise CDPError(f"{method}: {data['error'].get('message')}")
            return data.get("result", {})
        raise CDPError(f"{method}: quá hạn {timeout:g}s")

    def eval(self, expression: str, timeout: float = 30.0):
        result = self.call("Runtime.evaluate",
                           {"expression": expression, "returnByValue": True,
                            "awaitPromise": True}, timeout)
        if result.get("exceptionDetails"):
            raise CDPError(result["exceptionDetails"].get("text", "lỗi JS"))
        return result.get("result", {}).get("value")

    # --- thao tác ----------------------------------------------------------
    def go(self, url: str, wait_for: str = "", timeout: float = 30.0) -> None:
        self.call("Page.navigate", {"url": url}, timeout)
        self.settle(wait_for, timeout)

    def settle(self, wait_for: str = "", timeout: float = 30.0) -> None:
        """Chờ trang dựng xong. Có selector thì chờ đúng nó xuất hiện."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.35)
            try:
                ready = self.eval("document.readyState", timeout=8)
                if ready not in ("interactive", "complete"):
                    continue
                if not wait_for:
                    break
                found = self.eval(
                    f"!!document.querySelector({json.dumps(wait_for)})", timeout=8)
                if found:
                    break
            except CDPError:
                continue
        self.pause()

    def html(self) -> str:
        return self.eval("document.documentElement.outerHTML") or ""

    def text(self) -> str:
        return self.eval("document.body ? document.body.innerText : ''") or ""

    def click(self, selector: str) -> bool:
        done = self.eval(
            f"(()=>{{const e=document.querySelector({json.dumps(selector)});"
            "if(!e)return false;e.click();return true;})()")
        self.pause()
        return bool(done)

    def scroll_to_end(self, rounds: int = 6) -> None:
        """Trang cuộn vô hạn: cuộn tới khi chiều cao không tăng nữa."""
        last = 0
        for _ in range(rounds):
            self.eval("window.scrollTo(0, document.body.scrollHeight)")
            self.pause()
            height = self.eval("document.body.scrollHeight") or 0
            if height == last:
                break
            last = height

    @staticmethod
    def pause() -> None:
        time.sleep(random.uniform(*PAUSE))

    def close(self) -> None:
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/json/close/{self.target_id}", timeout=5)
        except Exception:                           # noqa: BLE001
            pass
        finally:
            self.ws.close()


def pages(port: int = PORT) -> list[dict]:
    """Các tab đang mở. Dùng để tìm lại một trang đã mở từ trước, thay vì giữ
    tay cầm trong bộ nhớ máy chủ — tay cầm thì mất khi khởi động lại, còn tab
    thì vẫn nằm đó."""
    try:
        return [t for t in _targets(port) if t.get("type") == "page"]
    except (OSError, ValueError):
        return []


def attach(target_id: str, port: int = PORT) -> Tab:
    """Nối vào một tab CÓ SẴN. Không mở tab mới, không điều hướng."""
    tab = Tab(WebSocket(f"ws://127.0.0.1:{port}/devtools/page/{target_id}"),
              target_id, port)
    tab.call("Runtime.enable")
    return tab


def open_tab(url: str = "about:blank", port: int = PORT) -> Tab:
    """Mở tab mới qua Target.createTarget.

    KHÔNG dùng endpoint HTTP /json/new: Chrome mới đòi PUT thay vì GET và trả
    405, nên cách đó gãy theo phiên bản. Lệnh CDP thì ổn định.
    """
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=5) as r:
        browser_ws = json.load(r)["webSocketDebuggerUrl"]

    control = WebSocket(browser_ws)
    try:
        control.send(json.dumps({"id": 1, "method": "Target.createTarget",
                                 "params": {"url": url}}))
        while True:
            reply = json.loads(control.recv())
            if reply.get("id") == 1:
                break
        if "error" in reply:
            raise CDPError(f"Target.createTarget: {reply['error'].get('message')}")
        target_id = reply["result"]["targetId"]
    finally:
        control.close()

    tab = Tab(WebSocket(f"ws://127.0.0.1:{port}/devtools/page/{target_id}"),
              target_id, port)
    tab.call("Page.enable")
    tab.call("Runtime.enable")
    return tab
