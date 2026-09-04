"""Khởi động app.   python3 -m jobbot   (hoặc: python3 run.py)"""

from __future__ import annotations

import sys
import threading
import webbrowser

from .core import db
from .core.paths import db_path
from .dashboard.server import serve


def main() -> int:
    ran = db.migrate(db.connect())          # tạo/nâng cấp DB trước khi mở cổng
    httpd, url = serve()

    print(f"  jobbot  →  {url}", flush=True)
    print(f"  DB      →  {db_path()}", flush=True)
    if ran:
        print(f"  ran {ran} migration(s)", flush=True)
    print("  Ctrl+C to stop\n", flush=True)

    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
