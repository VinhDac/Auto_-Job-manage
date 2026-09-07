#!/usr/bin/env python3
"""Dựng lại TOÀN BỘ tầng suy diễn từ tầng raw.

    python3 scripts/rebuild.py

Dùng khi: sửa luật lọc/chấm, sửa hàm bóc HTML, hoặc nghi ngờ dữ liệu suy diễn
đã hỏng. Không mất gì — tầng raw không bị đụng tới.

Đây là thứ mà kiến trúc cũ KHÔNG có: mô tả chỉ tồn tại ở dạng đã bóc, nên một
lỗi trong strip_html là hỏng vĩnh viễn.
"""

import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db
from jobbot.core.derive import rebuild

if __name__ == "__main__":
    conn = db.connect()
    t0 = time.time()
    print("\nDựng lại từ tầng raw\n")
    result = rebuild(conn, log=print)
    print(f"\n  xong trong {time.time() - t0:.1f}s\n")
