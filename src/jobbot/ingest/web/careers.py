"""Đi THẲNG trang tuyển dụng của công ty, bỏ mọi trung gian.

Vì sao: 19/28 tin lấy từ board là của môi giới. Đi thẳng thì
    - tên công ty không mơ hồ
    - JD nguyên bản, không bị viết lại
    - có sẵn đúng form để nộp (bước 5)
    - thấy được cả tin không bao giờ lên board

Cách dò, rẻ trước đắt sau:
    1. Đoán slug trên các ATS phổ biến — chỉ là HTTP, không cần Chrome
    2. Không ra thì mở trang chủ bằng Chrome, tìm link careers
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from ..base import UA

ATS_PROBE = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever":      "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby":      "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}

# Dấu vết ATS trên trang careers, khi phải mở bằng Chrome
ATS_MARKS = [
    ("greenhouse", re.compile(r"boards\.greenhouse\.io/([a-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/([a-z0-9_-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", re.I)),
    ("workday", re.compile(r"([a-z0-9_-]+)\.wd\d+\.myworkdayjobs\.com", re.I)),
    ("smartrecruiters", re.compile(r"careers\.smartrecruiters\.com/([A-Za-z0-9_-]+)", re.I)),
    ("teamtailor", re.compile(r"([a-z0-9-]+)\.teamtailor\.com", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/([a-z0-9-]+)", re.I)),
]

CAREERS_PATHS = ["/careers", "/jobs", "/careers/", "/about/careers",
                 "/company/careers", "/join-us", "/work-with-us", "/en/careers"]


# Đuôi pháp lý thì bỏ, nhưng "Group"/"Capital"/"Partners" thì GIỮ — chúng nằm
# trong slug thật. `norm_company` cắt cả những từ này (đúng cho việc so khớp
# tên công ty, sai cho việc đoán slug): "Man Group" -> "man", mất "mangroup".
LEGAL_TAIL = re.compile(r"\b(ltd|limited|llp|llc|plc|inc|incorporated|"
                        r"gmbh|bv|nv|sa|ag|co)\b", re.I)


def slug_guesses(name: str) -> list[str]:
    """'Man Group Ltd' -> mangroup, man-group, man."""
    base = LEGAL_TAIL.sub(" ", name or "").lower()
    base = re.sub(r"[^a-z0-9 ]+", " ", base)
    words = base.split()
    if not words:
        return []
    out = ["".join(words), "-".join(words)]
    if len(words) > 1:
        out.append(words[0])                       # "Man Group" -> "man"
        out.append("".join(words[:-1]))            # bỏ từ cuối
        out.append("".join(w[0] for w in words))   # viết tắt
    return [s for s in dict.fromkeys(out) if 2 < len(s) < 40]


def _probe(url: str) -> tuple[int, str]:
    """(số tin, tên công ty board tự khai). (0, '') = không phải board này."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, OSError, ValueError):
        return 0, ""

    rows = data if isinstance(data, list) else next(
        (data[k] for k in ("jobs", "data", "results")
         if isinstance(data.get(k), list)), [])
    if not rows:
        return 0, ""
    first = rows[0] if isinstance(rows[0], dict) else {}
    return len(rows), str(first.get("company_name") or first.get("companyName") or "")


def _same_company(wanted: str, claimed: str) -> bool:
    """Board có đúng là của công ty mình đang tìm không.

    Cần bước này vì đoán slug bắt nhầm: "London Stock Exchange Group" đoán ra
    slug `london`, và đó là board của một công ty hoàn toàn khác.
    """
    if not claimed:
        return True                      # board không khai tên -> đành tin
    a, b = set(norm_key(wanted).split()), set(norm_key(claimed).split())
    return bool(a & b)


def norm_key(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower()).strip()


def resolve_ats(name: str) -> tuple[str, str, int]:
    """Đoán ATS + slug. Trả về (ats, slug, số tin). Không ra thì ('','',0)."""
    for slug in slug_guesses(name):
        for ats, template in ATS_PROBE.items():
            count, claimed = _probe(template.format(slug=slug))
            if not count:                   # board rỗng không tính
                continue
            if not _same_company(name, claimed):
                continue                    # slug bắt nhầm board công ty khác
            return ats, slug, count
    return "", "", 0


def sniff_page(html: str) -> tuple[str, str]:
    """Trang careers này chạy trên ATS nào."""
    for ats, pattern in ATS_MARKS:
        found = pattern.search(html or "")
        if found:
            return ats, found.group(1)
    return "", ""


def resolve_via_chrome(tab, domain: str) -> tuple[str, str, str]:
    """Mở trang chủ, lần theo link careers, xem nó chạy ATS nào.

    Trả về (ats, slug, careers_url).
    """
    from .base import Blocked, open_page

    for path in CAREERS_PATHS:
        url = f"https://{domain}{path}"
        try:
            open_page(tab, url, timeout=25)
        except Blocked:
            return "", "", ""
        except Exception:                    # noqa: BLE001
            continue
        html = tab.html()
        if len(html) < 2000:
            continue
        ats, slug = sniff_page(html)
        if ats:
            return ats, slug, url
        if re.search(r"\b(open roles?|current vacanc|job openings?|"
                     r"view (all )?jobs)\b", html, re.I):
            return "custom", "", url        # có trang tuyển dụng nhưng ATS lạ
    return "", "", ""
