"""Sổ trả lời — hồ sơ của Vin, viết lại thành CÁI FORM HỎI.

MỘT NGUỒN. Mọi ô được điền đều lấy giá trị từ đây, không nơi nào khác dựng
chuỗi riêng. Thiếu thì thiếu công khai — trả về rỗng, và ô đó thành việc của
Vin. KHÔNG bịa, không suy diễn "chắc là".

Vì sao có `aliases`: một sự thật, hai kiểu ô. Ô chữ nhận "MSc"; ô chọn có sẵn
danh sách và phải trúng đúng chữ trong danh sách ("Master's Degree"). Cùng một
sự thật, nên cùng một mục — không tách hai khoá rồi có ngày lệch nhau.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Học vị: chữ viết tắt trên CV -> nhóm mà ô chọn của ATS dùng.
DEGREE_LEVEL = {
    "phd": "doctor", "dphil": "doctor",
    "msc": "master", "ma": "master", "meng": "master", "mphil": "master",
    "mba": "mba", "mres": "master", "mfin": "master", "mst": "master",
    "bsc": "bachelor", "ba": "bachelor", "beng": "bachelor", "ba (hons)": "bachelor",
}
# Chữ hay gặp trong ô chọn học vị. Xếp từ CHÍNH XÁC NHẤT xuống, vì đó cũng là
# thứ tự thử. Đo được: để mỗi chữ "master" thì máy chọn trúng "Master of
# Business Administration (M.B.A.)" — Vin học MSc, đó là khai sai bằng cấp.
LEVEL_WORDS = {
    "doctor": ("Doctorate", "Doctor of Philosophy (Ph.D.)", "PhD", "doctor"),
    "master": ("Master's Degree", "Masters Degree", "Master of Science", "master"),
    "mba": ("Master of Business Administration (M.B.A.)", "MBA"),
    "bachelor": ("Bachelor's Degree", "Bachelors Degree", "bachelor"),
}

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
MONTH_NAME = ["", "January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]

COUNTRY = {"uk": ("United Kingdom", "GB", "UK", "United Kingdom of Great Britain"),
           "gb": ("United Kingdom", "GB", "UK"),
           "england": ("United Kingdom", "GB", "UK"),
           "vietnam": ("Vietnam", "VN", "Viet Nam")}


@dataclass(frozen=True)
class Ans:
    """Một sự thật.

    `value`   điền vào ô chữ
    `aliases` các cách gọi khác, để dò trong danh sách thả xuống
    `prefer`  phần CÒN LẠI của hồ sơ dùng để phân xử khi nhiều dòng cùng trúng

    Vì sao có `prefer`: gõ "London" vào ô thành phố của Greenhouse thì ra cả
    "London, England, United Kingdom" lẫn "London, Ontario, Canada". Một câu
    trả lời thiếu vế không tự phân xử được — phải lấy vế còn lại của hồ sơ
    (Vin ở UK) mà chọn. Đo được: không có nó, máy khai Vin sống ở Canada.
    """
    value: str
    aliases: tuple[str, ...] = ()
    prefer: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.value)

    def candidates(self) -> tuple[str, ...]:
        return (self.value,) + tuple(a for a in self.aliases if a)


@dataclass
class Education:
    degree: str = ""          # "MSc"
    level: str = ""           # "master"
    discipline: str = ""      # "Computational Finance"
    school: str = ""          # "Royal Holloway, University of London"
    start_month: int = 0
    start_year: int = 0
    end_month: int = 0
    end_year: int = 0
    note: str = ""            # dòng phụ: điểm môn, hạng
    missing: list[str] = field(default_factory=list)


_YEARS = re.compile(r"(?:(?P<m1>[A-Za-z]{3,9})\s+)?(?P<y1>(?:19|20)\d{2})"
                    r"\s*[–—-]\s*"
                    r"(?:(?P<m2>[A-Za-z]{3,9})\s+)?(?P<y2>(?:19|20)\d{2})")
_DEGREE_HEAD = re.compile(r"^\s*([A-Za-z.]+(?:\s*\(Hons\))?)\s+(.*)$")


def _month(word: str | None) -> int:
    return MONTHS.get((word or "")[:3].lower(), 0)


def educations(text: str) -> list[Education]:
    """MỌI bằng trong ô Education, không chỉ bằng mới nhất.

    MỘT ngữ pháp cho cả đọc lẫn ghi: form hồ sơ dựng dòng bằng `line()` ngay
    dưới, rồi chính hàm này đọc lại. Hai bên lệch nhau là form ghi ra thứ máy
    không hiểu — mà thứ máy không hiểu ở đây là NGÀY TỐT NGHIỆP, câu mà lá đơn
    nào cũng hỏi.

    Dòng thụt đầu là dòng PHỤ (điểm môn, hạng) — thuộc về bằng ngay trên nó,
    không phải một bằng mới.
    """
    out: list[Education] = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        if line.startswith((" ", "\t")):
            if out:
                out[-1].note = (out[-1].note + " " + line.strip()).strip()
            continue
        sach = line.strip()
        # Dòng KHÔNG mang tên bằng và KHÔNG có khoảng năm thì không phải một
        # bằng — nó là dòng phụ viết sát lề. CV thật hay viết điểm môn kiểu đó
        # ("Investment & Portfolio Management 86 · Data Analysis 83"), và nhận
        # nhầm thì nó hiện ra thành một cái bằng tên "Investment".
        if out and not _la_bang(sach):
            out[-1].note = (out[-1].note + " " + sach).strip()
            continue
        out.append(_one(sach))
    return out


def _la_bang(dong: str) -> bool:
    """Dòng này có phải một cái BẰNG không — có tên bằng, hoặc có khoảng năm."""
    dau = _DEGREE_HEAD.match(dong)
    if dau:
        key = dau.group(1).lower().replace(".", "").replace(" (hons)", "")
        if key in DEGREE_LEVEL:
            return True
    return bool(_YEARS.search(dong))


def line(degree: str, discipline: str, school: str,
         start: str, end: str, note: str = "") -> str:
    """Các ô rời -> ĐÚNG dòng mà `educations()` đọc lại được.

    Dạng: "MSc Computational Finance — Royal Holloway, Sep 2025 – Sep 2026"
    Ghi chú (điểm môn) xuống dòng và THỤT VÀO — đó là cách nói "đây là dòng
    phụ của bằng trên", và cũng là thứ giữ cho nó không bị đọc nhầm thành một
    bằng thứ hai.
    """
    trai = " ".join(x for x in (degree.strip(), discipline.strip()) if x)
    phai = school.strip()
    khi = " – ".join(x for x in (start.strip(), end.strip()) if x)
    if khi:
        phai = f"{phai}, {khi}" if phai else khi
    dong = " — ".join(x for x in (trai, phai) if x)
    if note.strip():
        dong += "\n  " + note.strip()
    return dong


def education(text: str) -> Education:
    """Bằng MỚI NHẤT — dòng đầu. Các ô mà form xin việc hỏi.

    Ngữ pháp đọc được (đúng cách Vin đã viết):

        MSc Computational Finance — Royal Holloway, University of London, 2025–2026
        BA (Hons) Advanced Finance — National Economics University, Vietnam

    Có tháng thì lấy tháng ("Sep 2025 – Sep 2026"). Không có thì KHÔNG đoán —
    ghi vào `missing` để báo Vin sửa hồ sơ một lần, khỏi phải chọn tay 49 lần.
    """
    hang = educations(text)
    if not hang:
        trong = Education()
        trong.missing = ["học vấn"]
        return trong
    return hang[0]


def _one(head: str) -> Education:
    out = Education()
    # Nhiều kiểu dấu ngăn. Chỉ nhận "—" và " - " thì Vin gõ "MSc X-Royal
    # Holloway" hay "MSc X | Royal Holloway" là CẢ DÒNG chui vào ô ngành học
    # và ô trường bỏ trống — nhà tuyển dụng nhận một chuỗi vô nghĩa.
    left, right = head, ""
    for dash in ("—", "–", " - ", " | ", " · ", ", "):
        a, sep, b = head.partition(dash)
        if sep and b.strip():
            left, right = a, b
            break
    left, right = left.strip(), right.strip()

    match = _DEGREE_HEAD.match(left)
    if match:
        out.degree, out.discipline = match.group(1).strip(), match.group(2).strip()
        key = out.degree.lower().replace(".", "").replace(" (hons)", "")
        out.level = DEGREE_LEVEL.get(key, "")
    else:
        out.discipline = left

    span = _YEARS.search(right)
    if span:
        out.start_year, out.end_year = int(span.group("y1")), int(span.group("y2"))
        out.start_month, out.end_month = _month(span.group("m1")), _month(span.group("m2"))
        right = right[: span.start()].rstrip(" ,")
    out.school = right.rstrip(" ,")

    if not out.start_year:
        out.missing.append("năm học")
    elif not out.start_month:
        # Ghi rõ cách sửa: đây là dữ liệu thiếu, không phải luật thiếu.
        out.missing.append("tháng học — sửa ô Education thành 'Sep 2025 – Sep 2026'")
    return out


def _links(raw: str) -> dict[str, str]:
    """Tách các đường dẫn. Chỉ nhận thứ THẬT SỰ là URL.

    Hồ sơ đang ghi trần chữ "LinkedIn"/"GitHub" — đó là nhãn, không phải địa
    chỉ. Điền chữ "LinkedIn" vào ô LinkedIn URL là rác. Bỏ, và báo thiếu.
    """
    out = {"website": "", "linkedin": "", "github": ""}
    for piece in re.split(r"[\s,]+", raw or ""):
        low = piece.lower()
        if not low.startswith(("http://", "https://", "www.")):
            continue
        url = piece if piece.lower().startswith("http") else "https://" + piece
        if "linkedin." in low:
            out["linkedin"] = url
        elif "github.com" in low:
            out["github"] = url
        elif not out["website"]:
            out["website"] = url
    return out


def book(profile: dict[str, Any]) -> dict[str, Ans]:
    """Hồ sơ -> sổ trả lời. Khoá là CÂU HỎI, không phải tên ô của ATS nào."""
    get = lambda k: str(profile.get(k) or "").strip()      # noqa: E731

    # "Dac Vinh Nguyen" viết theo lối Tây: TIẾNG CUỐI là họ, phần còn lại là
    # tên gọi. Cắt ngược lại (first = "Dac", last = "Vinh Nguyen") là sai họ —
    # và họ là thứ nhà tuyển dụng gọi trong thư.
    full = get("full_name")
    parts = full.split()
    first = " ".join(parts[:-1]) if len(parts) > 1 else (parts[0] if parts else "")
    last = parts[-1] if len(parts) > 1 else ""

    place = get("location")                                # "London, UK"
    city, _, tail = place.partition(",")
    country_key = tail.strip().lower().rstrip(".")
    country = COUNTRY.get(country_key, (tail.strip(),) if tail.strip() else ())

    edu = education(get("education"))
    link = _links(get("links"))

    def month(n: int) -> Ans:
        return Ans(f"{n:02d}", (MONTH_NAME[n], MONTH_NAME[n][:3], str(n))) if n else Ans("")

    # Vế dùng để phân xử tên thành phố trùng nhau khắp thế giới.
    where = tuple(x for x in (country[0] if country else "", "England",
                              *(country[1:] if country else ())) if x)

    return {
        "first_name": Ans(first),
        "last_name": Ans(last),
        "full_name": Ans(full),
        "email": Ans(get("email")),
        "phone": Ans(get("phone")),
        "location": Ans(place, (city.strip(),), where),
        "city": Ans(city.strip(), (place,), where),
        "country": Ans(country[0] if country else "", tuple(country[1:])),
        "website": Ans(link["website"]),
        "linkedin": Ans(link["linkedin"]),
        "github": Ans(link["github"]),
        "school": Ans(edu.school),
        "degree": Ans(edu.degree, tuple(LEVEL_WORDS.get(edu.level, ()))),
        "discipline": Ans(edu.discipline),
        "edu_start_year": Ans(str(edu.start_year) if edu.start_year else ""),
        "edu_end_year": Ans(str(edu.end_year) if edu.end_year else ""),
        "edu_start_month": month(edu.start_month),
        "edu_end_month": month(edu.end_month),
    }
