#!/usr/bin/env python3
"""Quét một lần bằng tay.

    python3 scripts/scan.py               API + Chrome, đọc kỹ từng tin
    python3 scripts/scan.py --shallow     Chrome chỉ lấy danh sách, không mở từng tin
    python3 scripts/scan.py --no-chrome   chỉ nguồn API

App chạy nền cũng gọi đúng hàm này theo lịch — xem src/jobbot/core/scheduler.py.
Chỉ ĐỌC, không gửi gì ra ngoài. Chạy lại bao nhiêu lần cũng được (có cache).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.scan_runner import run_scan


def main() -> int:
    pages = 3
    if "--pages" in sys.argv:
        pages = int(sys.argv[sys.argv.index("--pages") + 1])
    chrome = "--no-chrome" not in sys.argv
    deep = "--shallow" not in sys.argv

    print("\nQuét nguồn\n")
    # manual=True: người dùng tự bấm, nên không áp cửa sổ giờ người
    result = run_scan(pages=pages, log=print, chrome_sources=chrome,
                      deep=deep, manual=True)
    if not result["ok"]:
        print(f"\n{result['summary']}: {result.get('missing')}")
        return 1
    print(f"\nTổng: {result['summary']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
