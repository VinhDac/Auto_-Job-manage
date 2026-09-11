#!/usr/bin/env python3
"""Nạp hồ sơ vào DB.  Chạy:  python3 scripts/seed_profile.py

Chạy lại được nhiều lần — mỗi lần tạo một phiên bản mới, không ghi đè lịch sử.

DỮ LIỆU NẰM NGOÀI MÃ, ở `config/profile.seed.json` (đã gitignore).

Vì sao: repo này công khai trên GitHub, và bản trước để thẳng trong mã họ tên,
SỐ ĐIỆN THOẠI THẬT, học vấn kèm điểm, chứng chỉ và TOÀN VĂN CV. Số điện thoại
trên repo công khai là thứ bot quét về để spam và lừa đảo. Dữ liệu cá nhân
không thuộc về mã nguồn.

Chép `config/profile.seed.example.json` sang `config/profile.seed.json` rồi
điền.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db
from jobbot.profile import store

SEED = Path(__file__).resolve().parent.parent / "config" / "profile.seed.json"


def load_seed() -> dict:
    """Đọc hồ sơ từ tệp ngoài. Không có tệp thì nói rõ cách tạo."""
    if not SEED.exists():
        raise SystemExit(
            f"Chưa có {SEED}.\n"
            f"Chép từ {SEED.with_name('profile.seed.example.json')} rồi điền.")
    return json.loads(SEED.read_text(encoding="utf-8"))


# ------------------------------------------------------------ [để trống]
# visa_expiry    — ngày hết hạn Graduate visa. Vin chưa đưa. ĐÂY LÀ HẠN CHÓT THẬT.
# sponsor_future — có cần công ty bảo lãnh được về sau không. Chỉ Vin quyết.
# email          — Vin chưa đưa.
# available_from — phụ thuộc ngày MSc kết thúc chính thức.
# urgency        — chỉ Vin biết.
# salary_floor   — chỉ Vin biết.
# skills_strong / skills_weak — phải tách từ CV đầy đủ, chưa có.
MUST_ASK = ["visa_expiry", "sponsor_future", "email", "available_from",
            "urgency", "salary_floor", "skills_strong"]


def main() -> int:
    seed = load_seed()
    conn = db.connect()
    version = store.save(conn, seed, note="seed: hồ sơ từ config/profile.seed.json")
    answers = store.load(conn)

    print(f"\n  Đã nạp — phiên bản {version}\n")
    print(f"  {len(seed)} câu từ {SEED.name}")
    print(f"  {len(MUST_ASK)} câu KHÔNG đoán — Vin phải tự điền\n")

    missing = store.missing_for_ingest(answers)
    if missing:
        print(f"  CHƯA TÌM ĐƯỢC. Còn thiếu: {', '.join(missing)}")
    else:
        print("  Đủ điều kiện để bắt đầu tìm.")
    print()
    print("  Cần Vin điền tiếp:")
    for qid in MUST_ASK:
        print(f"     - {qid}")
    print()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
