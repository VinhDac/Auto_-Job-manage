"""Nhận diện tin do MÔI GIỚI đăng, không phải chủ việc.

Vì sao quan trọng: 17/28 tin lấy về từ eFinancialCareers là của công ty tuyển
dụng trung gian. Chúng viết lại JD, giấu tên công ty thật, và nộp qua đó thì
hồ sơ đi qua thêm một tầng lọc nữa.

Hai tín hiệu, dùng CẢ HAI vì mỗi cái riêng đều hụt:
    tên công ty  — danh sách hãng môi giới đã biết
    chữ trong JD — "our client", "on behalf of"

Một mình chữ thì hụt: tin ghi "Invesco" vẫn chứa "our client" (môi giới đăng hộ).
Một mình tên thì hụt: hãng mới không có trong danh sách.
"""

from __future__ import annotations

import re

from ...ingest.base import norm

# Hãng môi giới tài chính/công nghệ ở London, gặp trong dữ liệu thật
KNOWN = {
    "oxford knight", "eka finance", "anson mccade", "mccabe barton",
    "emagine consulting", "quanteam", "selby jennings", "harrington starr",
    "robert walters", "michael page", "hays", "robert half", "morgan mckinley",
    "goodman masson", "eames consulting", "gqr", "durlston partners",
    "arrows group", "lorien", "sthree", "huxley", "phaidon", "glocomms",
    "understanding recruitment", "salt", "la fosse", "trust in soda",
    "vertus partners", "paragon alpha", "alexander ash", "gerrard white",
}

# Từ trong TÊN công ty
NAME_HINTS = re.compile(
    r"\b(recruit\w*|resourcing|staffing|talent|search|consultanc\w+|"
    r"partners?|associates|solutions group|manpower|headhunt\w*)\b", re.I)

# Câu chỉ có môi giới mới viết
TEXT_HINTS = re.compile(
    r"\b(our client|my client|our customer|on behalf of (?:our|a)|"
    r"we are (?:working with|partnered with|recruiting for)|"
    r"a (?:leading|top[- ]tier|prestigious|world[- ]class) (?:hedge fund|"
    r"investment bank|asset manager|firm|client)|"
    r"confidential client|client is seeking)\b", re.I)


def judge(company: str, description: str) -> tuple[bool, str]:
    """(là môi giới, vì sao). Luôn nói được lý do."""
    key = norm(company).replace("ltd", "").replace("limited", "").strip()
    if key in KNOWN:
        return True, f"'{company}' is a known recruitment agency"

    text = description or ""
    phrase = TEXT_HINTS.search(text)
    if phrase:
        return True, f"description says \"{phrase.group().strip()}\""

    if NAME_HINTS.search(company or "") and "bank" not in key:
        return True, f"company name reads like an agency"
    return False, ""
