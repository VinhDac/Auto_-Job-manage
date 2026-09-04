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

    print(f"  jobbot  →  {url}")
    print(f"  DB      →  {db_path()}")
    if ran:
        print(f"  đã chạy {ran} migration")
    print("  Ctrl+C để dừng\n")

    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  đã dừng.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
