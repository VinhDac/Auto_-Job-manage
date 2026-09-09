"""Chạy TOÀN BỘ bài test bằng một lệnh, và không tin bài test nào cả.

    python3 tests/run_all.py

Vì sao cần: mỗi file test là một script tự chạy, không có runner nào. Hậu quả
thật là test_browser.py quên mất dòng sys.exit — nó in "48 ok, 0 fail" rồi
thoát 0 dù có hỏng bao nhiêu đi nữa, và vòng lặp chạy-rồi-xem-mã-thoát không
đời nào phát hiện ra.

Nên ở đây kiểm CẢ HAI phía, và bên nào cũng phải khớp:
    · mã thoát phải là 0
    · dòng tổng kết cuối phải nói 0 fail
    · phải CÓ dòng tổng kết — im lặng không phải là đạt
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUMMARY = re.compile(r"^(\d+) ok, (\d+) fail\s*$", re.M)


def main() -> int:
    files = sorted(f for f in HERE.glob("test_*.py"))
    if not files:
        print("không tìm thấy file test nào")
        return 1

    width = max(len(f.name) for f in files)
    total_ok = total_fail = broken = 0

    for path in files:
        done = subprocess.run([sys.executable, str(path)],
                              capture_output=True, text=True, cwd=HERE.parent)
        out = done.stdout + done.stderr
        found = SUMMARY.search(out)

        if not found:
            print(f"  {path.name:<{width}}  KHÔNG CÓ DÒNG TỔNG KẾT (thoát {done.returncode})")
            print("\n".join("      " + line for line in out.strip().splitlines()[-8:]))
            broken += 1
            continue

        n_ok, n_fail = int(found.group(1)), int(found.group(2))
        total_ok += n_ok
        total_fail += n_fail

        note = ""
        if n_fail and done.returncode == 0:
            # đây chính là lỗi test_browser.py: hỏng mà vẫn báo thành công
            note = "  <-- CÓ HỎNG MÀ VẪN THOÁT 0 (thiếu sys.exit?)"
            broken += 1
        elif not n_fail and done.returncode != 0:
            note = f"  <-- 0 hỏng mà thoát {done.returncode}"
            broken += 1

        mark = "ok  " if not n_fail and done.returncode == 0 else "HỎNG"
        print(f"  {mark} {path.name:<{width}}  {n_ok:>3} ok, {n_fail} fail{note}")
        if n_fail:
            for line in out.splitlines():
                if line.lstrip().startswith("FAIL"):
                    print("       " + line.strip())

    print(f"\n{len(files)} file · {total_ok} ok · {total_fail} fail"
          + (f" · {broken} file có vấn đề về chính nó" if broken else ""))
    return 1 if (total_fail or broken) else 0


if __name__ == "__main__":
    sys.exit(main())
