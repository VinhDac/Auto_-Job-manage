"""Khởi động jobbot.

    python3 run.py            app thật: cửa sổ riêng + icon Dock + icon thanh menu
    python3 run.py --window   chạy trong Terminal, mở trình duyệt, Ctrl+C dừng
    python3 run.py --scan     quét một lần rồi thoát
"""

from __future__ import annotations

import sys
import threading
import webbrowser

from .core import db
from .core.paths import db_path
from .core.scheduler import Scheduler
from .dashboard.server import serve


def run_window() -> int:
    """Chế độ cửa sổ: server + scheduler, log hiện ra Terminal."""
    ran = db.migrate(db.connect())
    httpd, url = serve()
    scheduler = Scheduler()
    scheduler.start()

    print(f"  jobbot  ->  {url}", flush=True)
    print(f"  DB      ->  {db_path()}", flush=True)
    if ran:
        print(f"  ran {ran} migration(s)", flush=True)
    print("  scanning every 60 min · Ctrl+C to stop\n", flush=True)

    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")
    finally:
        scheduler.stop()
        httpd.server_close()
    return 0


def main() -> int:
    db.migrate(db.connect())

    if "--scan" in sys.argv:
        from .scan_runner import run_scan
        result = run_scan(log=print)
        print(f"\n  {result['summary']}\n")
        return 0 if result["ok"] else 1

    if "--window" in sys.argv:
        return run_window()

    try:
        from .app import run                   # cửa sổ app thật (PyObjC + WKWebView)
        return run()
    except (ImportError, AttributeError) as exc:
        print(f"  (không dựng được cửa sổ app: {exc})")
        print("  chuyển sang chế độ trình duyệt\n")
        return run_window()


if __name__ == "__main__":
    sys.exit(main())
