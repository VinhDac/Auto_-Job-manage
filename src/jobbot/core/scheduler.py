"""Vòng chạy nền — cái làm cho nó thành APP thay vì trang web phải tự bấm.

Nhịp (design.md §3):
  - Nguồn có API công khai: chạy 24/7, không có lý do gì phải nhịn.
  - Nguồn qua Chrome: chỉ trong cửa sổ giờ người. Không ai lướt web 3 giờ sáng
    mỗi đêm — chính nhịp đó tố cáo, chứ không phải tốc độ click.

Mọi vòng chạy đều ghi audit. Hỏng một nguồn không được làm chết cả vòng.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

from . import notify, postings
from .db import connect

SCAN_EVERY_MIN = 60
HUMAN_WINDOW = (8, 22)          # giờ địa phương, cho nguồn qua Chrome


def in_human_window(now: datetime | None = None) -> bool:
    hour = (now or datetime.now()).hour
    return HUMAN_WINDOW[0] <= hour < HUMAN_WINDOW[1]


class Scheduler:
    """Chạy trong luồng nền. Không bao giờ ném lỗi ra ngoài — app phải sống tiếp."""

    def __init__(self, scan_every_min: int = SCAN_EVERY_MIN):
        self.scan_every = scan_every_min * 60
        self.stop_flag = threading.Event()
        self.last_scan: float = 0.0
        self.last_result: str = "chưa chạy lần nào"
        self.running = False
        self._thread: threading.Thread | None = None

    # --- điều khiển -------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler")
        self._thread.start()

    def stop(self) -> None:
        self.stop_flag.set()

    def next_in(self) -> int:
        """Còn bao nhiêu giây tới lần quét sau."""
        if not self.last_scan:
            return 0
        return max(0, int(self.scan_every - (time.time() - self.last_scan)))

    # --- vòng lặp ---------------------------------------------------------
    def _loop(self) -> None:
        time.sleep(5)                       # để server lên trước
        while not self.stop_flag.is_set():
            if time.time() - self.last_scan >= self.scan_every:
                self.scan_once()
            self.stop_flag.wait(30)

    def scan_once(self) -> str:
        """Một lần quét. Nuốt mọi lỗi — một nguồn chết không được giết app."""
        self.running = True
        self.last_scan = time.time()
        try:
            from ..scan_runner import run_scan          # nạp muộn, tránh vòng import
            result = run_scan()
            self.last_result = result["summary"]
            self._maybe_notify(result)
        except Exception as exc:                        # noqa: BLE001
            self.last_result = f"lỗi: {type(exc).__name__}: {exc}"
            try:
                conn = connect()
                postings.log(conn, "scan_error", str(exc)[:300])
                conn.close()
            except Exception:                           # noqa: BLE001
                pass
        finally:
            self.running = False
        return self.last_result

    @staticmethod
    def _maybe_notify(result: dict) -> None:
        """Chỉ báo khi có việc MỚI đáng xem. Không báo mỗi lần quét."""
        fresh = result.get("new_matches", 0)
        if fresh > 0:
            notify.send("jobbot",
                        f"{fresh} việc mới khớp hồ sơ của bạn",
                        subtitle="Mở dashboard để xem")
