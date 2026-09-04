#!/usr/bin/env python3
"""Chạy app:  python3 run.py

Không cần cài gì. Không cần venv. Chỉ cần Python 3.11+.
"""

import sys
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(f"Cần Python 3.11 trở lên. Máy đang dùng {sys.version.split()[0]}.")

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jobbot.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
