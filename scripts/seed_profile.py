#!/usr/bin/env python3
"""Nạp hồ sơ mẫu vào DB.  Chạy:  python3 scripts/seed_profile.py

Chạy lại được nhiều lần — mỗi lần tạo một phiên bản mới, không ghi đè lịch sử.

Ba loại dữ liệu ở đây, phân biệt rõ:
    [thật]     Vin đưa trực tiếp
    [đề xuất]  Claude suy ra từ hồ sơ — Vin phải xem lại và sửa
    [để trống] KHÔNG được đoán. Đoán sai tốn hàng tháng.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db
from jobbot.profile import store

# ---------------------------------------------------------------- [thật]
REAL = {
    "full_name": "Dac Vinh Nguyen",
    "location": "London, UK",
    "phone": "+44 7454 070297",
    "education": (
        "MSc Computational Finance — Royal Holloway, University of London, 2025–2026\n"
        "  Investment & Portfolio Management 86 · Data Analysis 83\n"
        "  Deep Learning 83 · Principles of Computation and Programming 75\n"
        "\n"
        "BA (Hons) Advanced Finance — National Economics University, Vietnam\n"
        "  GPA 3.59/4.0 · Sep 2025"
    ),
    "certifications": (
        "CFA Level I — October 2024, top 10% of global candidates\n"
        "IBM Data Science Professional Certificate\n"
        "IBM Machine Learning"
    ),
    "cv_text": (
        "EXPERIENCE\n"
        "Research Consultant — WorldQuant (BRAIN platform), Jan 2025 – Sep 2025\n"
        "\n"
        "[Chưa đầy đủ — Vin dán nốt phần mô tả công việc, dự án, kỹ năng vào đây]"
    ),
    "seniority": ["intern", "grad", "grad_scheme", "junior"],
    "languages": "English, Vietnamese (native)",
    "doc_language": "en",
    "work_auth": "visa_no_sponsor",          # Graduate visa — Vin xác nhận 04/09/2026
}

# ------------------------------------------------------------ [đề xuất]
# Suy ra từ: MSc Computational Finance + CFA L1 + WorldQuant alpha research.
# Vin XEM LẠI VÀ SỬA — đây là chuỗi thật đem đi tìm, sai là tìm ra rác.
PROPOSED = {
    "job_titles": "\n".join([
        "Quantitative Analyst",
        "Quantitative Researcher",
        "Quantitative Developer",
        "Data Scientist",
        "Data Analyst",
        "Risk Analyst",
        "Investment Analyst",
        "Research Analyst",
        "Portfolio Analyst",
        "Financial Analyst",
        "Trading Analyst",
        "Graduate Analyst",
    ]),
    "search_keywords": (
        "Python, pandas, SQL, machine learning, quantitative, alpha research, "
        "backtesting, portfolio optimisation, time series, CFA"
    ),
    "markets": ["uk_onsite", "uk_remote"],
    "industries": "asset management, hedge fund, investment bank, fintech, quantitative trading",
}

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
    conn = db.connect()
    version = store.save(conn, {**REAL, **PROPOSED}, note="seed: hồ sơ Vin")
    answers = store.load(conn)

    print(f"\n  Đã nạp — phiên bản {version}\n")
    print(f"  [thật]    {len(REAL)} câu")
    print(f"  [đề xuất] {len(PROPOSED)} câu — XEM LẠI, nhất là job_titles")
    print(f"  [để trống]{len(MUST_ASK)} câu — Vin phải tự điền\n")

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
