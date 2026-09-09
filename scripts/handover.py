#!/usr/bin/env python3
"""Đóng gói để chuyển sang máy khác.

    python3 scripts/handover.py            đóng gói ra jobbot-handover.zip
    python3 scripts/handover.py --check    chỉ xem sẽ mang gì, không đóng gói

Mang theo: mã nguồn + data/jobbot.db (toàn bộ tin, điểm, hồ sơ, nhật ký).
KHÔNG mang: chrome-profile (311 MB, tự sinh lại, chép sang còn dễ hỏng).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Chép: mã, cấu hình, tài liệu, test — và ĐÚNG một file dữ liệu.
TAKE_DIRS = ["src", "scripts", "config", "docs", "tests"]
TAKE_FILES = ["run.py", "run.bat", "run-console.bat", "start.command",
              "pyproject.toml", "README.md", ".gitignore"]
TAKE_DATA = ["data/jobbot.db"]

SKIP = {"__pycache__", ".pyc", ".DS_Store", "chrome-profile", "chrome-ui"}


def wanted(path: Path) -> bool:
    return not any(s in str(path) for s in SKIP)


def collect() -> list[Path]:
    out: list[Path] = []
    for name in TAKE_DIRS:
        out += [p for p in (ROOT / name).rglob("*") if p.is_file() and wanted(p)]
    for name in TAKE_FILES + TAKE_DATA:
        path = ROOT / name
        if path.is_file():
            out.append(path)
    return sorted(out)


def human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def main() -> int:
    files = collect()
    total = sum(f.stat().st_size for f in files)

    db = ROOT / "data" / "jobbot.db"
    print(f"\n  {len(files)} file · {human(total)}\n")
    print(f"  DB          {'CÓ — ' + human(db.stat().st_size) if db.is_file() else 'KHÔNG THẤY'}")
    for name in ("chrome-profile", "chrome-ui"):
        path = ROOT / "data" / name
        if path.is_dir():
            size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            print(f"  bỏ lại      {name} ({human(size)}) — tự sinh lại")

    if "--check" in sys.argv:
        print("\n  (--check: chưa đóng gói gì)\n")
        return 0

    out = ROOT / "jobbot-handover.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(ROOT))

    print(f"\n  -> {out.name}  ({human(out.stat().st_size)})")
    print("\n  Sang máy mới: giải nén, cài Python 3.11+ và Chrome,")
    print("  rồi bấm đúp run.bat (Windows) hoặc chạy python3 run.py.")
    print("  Chi tiết: docs/windows.md\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
