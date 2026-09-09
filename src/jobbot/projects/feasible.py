"""Kiểm đề bài có LÀM ĐƯỢC THẬT không — trước khi bỏ ra 2 ngày.

Đây là chỗ mọi người bỏ qua, và là chỗ phân biệt đề bài THẬT với đề bài NGHE HỢP LÝ.

"URL trả về 200" là hàng rào yếu: một trang HTML 404-đẹp cũng trả 200, một
trang đăng nhập cũng trả 200. Hàng rào mạnh là **tải thật vài KB đầu và nhìn
vào bên trong**:

    có phải bảng dữ liệu không, hay là HTML
    có bao nhiêu cột, tên cột là gì
    có cột thời gian không (gần như mọi đề bài quant đều cần)
    ước lượng bao nhiêu dòng

Đề bài nói "phân tích chuỗi thời gian" mà dữ liệu không có cột ngày thì hỏng —
và biết điều đó mất 3 giây, thay vì mất nửa ngày.
"""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field

from ..ingest.base import UA

PEEK_BYTES = 96_000
# .zip phải tải TRỌN bộ: mục lục của zip nằm ở CUỐI tệp, lấy 96KB đầu là không
# mở được. Chặn ở 12MB để một đường dẫn trỏ nhầm vào bộ dữ liệu khổng lồ không
# treo nguyên vòng dựng đề bài.
MAX_ZIP = 12_000_000
ZIP_MAGIC = b"PK\x03\x04"
# Tách gạch dưới ra trước khi khớp: FRED đặt tên cột là `observation_date`, mà
# `\bdate\b` không khớp được vì gạch dưới cũng là ký tự chữ.
DATE_COL = re.compile(r"\b(date|time|timestamp|day|month|year|period|dt)\b", re.I)
# "Date added", "Founded", "Year established" là siêu dữ liệu, KHÔNG phải trục
# thời gian. Nhầm hai thứ này là lý do một bảng tra cứu 399 dòng lọt qua như
# thể nó là chuỗi giá 20 năm.
META_DATE = re.compile(r"\b(date\s*(added|founded|created|joined|listed)|"
                       r"founded|established|incorporated|inception)\b", re.I)
PRICE_COL = re.compile(r"\b(open|high|low|close|adj|price|px|return|ret|nav|"
                       r"volume|vwap|bid|ask|yield|rate|value|amount)\b", re.I)
NUM_VALUE = re.compile(r"^-?\d[\d,]*\.?\d*([eE][-+]?\d+)?$")
# Cột ngày nhận ra bằng GIÁ TRỊ, không chỉ bằng tên. Cả thư viện Fama-French
# để cột ngày KHÔNG TÊN, giá trị dạng 19260701 — soi theo tên thì kết luận
# "không có trục thời gian" và loại oan đúng nguồn dữ liệu chuẩn nhất.
DATE_VALUE = re.compile(r"^(?:(19|20)\d{2}(?:\d{2}|\d{4})|"
                        r"\d{4}-\d{2}(?:-\d{2})?|\d{2}/\d{2}/\d{4})$")


@dataclass
class DataCheck:
    ok: bool = False
    kind: str = ""                 # csv | json | html | unknown
    columns: list[str] = field(default_factory=list)
    rows_seen: int = 0
    est_rows: int | None = None
    has_date: bool = False
    numeric_cols: int = 0
    date_cols: list[str] = field(default_factory=list)
    price_cols: list[str] = field(default_factory=list)
    lookup_table: bool = False     # mỗi dòng một thực thể, không phải chuỗi
    date_by_value: list[str] = field(default_factory=list)   # nhận ra nhờ giá trị
    problems: list[str] = field(default_factory=list)
    note: str = ""


def _fetch(url: str, timeout: float = 20.0, limit: int = PEEK_BYTES,
           ranged: bool = True) -> tuple[bytes, str, int | None]:
    head = {"User-Agent": UA}
    if ranged:
        head["Range"] = f"bytes=0-{limit}"
    req = urllib.request.Request(url, headers=head)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(limit)
        ctype = (resp.headers.get("Content-Type") or "").lower()
        total = resp.headers.get("Content-Range") or resp.headers.get("Content-Length")
    size = None
    if total:
        found = re.search(r"/(\d+)$", total) or re.match(r"^(\d+)$", total)
        if found:
            size = int(found.group(1))
    return raw, ctype, size


def inspect(url: str, fetch=_fetch) -> DataCheck:
    """Nhìn vào BÊN TRONG dữ liệu, không chỉ hỏi máy chủ có sống không."""
    check = DataCheck()
    if not re.match(r"^https?://", url or ""):
        check.problems.append("không phải địa chỉ http(s)")
        return check
    try:
        raw, ctype, size = fetch(url)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        check.problems.append(f"tải không được: {type(exc).__name__}")
        return check

    # Cả thư viện Fama-French — nguồn dữ liệu chuẩn của đúng loại project này —
    # chỉ phát hành dưới dạng .zip. Không mở được zip thì chặng kiểm dữ liệu
    # loại sạch nguồn tốt nhất đang có.
    if raw.startswith(ZIP_MAGIC):
        raw, ctype, size, note = _unzip(url, fetch)
        if note and not raw:
            check.kind = "zip"
            check.problems.append(note)
            return check
        check.note = note

    text = raw.decode("utf-8", "replace")
    head = text.lstrip()[:400].lower()

    if head.startswith(("<!doctype", "<html")) or "text/html" in ctype:
        check.kind = "html"
        check.problems.append("là trang web, không phải tệp dữ liệu — "
                              "người đọc không tải thẳng được")
        return check

    if head.startswith(("{", "[")) or "json" in ctype:
        check.kind = "json"
        try:
            data = json.loads(text if text.rstrip().endswith(("]", "}")) else text + "]")
            rows = data if isinstance(data, list) else next(
                (v for v in data.values() if isinstance(v, list)), [])
            if rows and isinstance(rows[0], dict):
                check.columns = list(rows[0].keys())[:40]
                check.rows_seen = len(rows)
        except ValueError:
            check.note = "JSON cắt dở khi xem trước — bình thường"
    else:
        check.kind = "csv"
        delim = _delimiter(text)
        lines = text.splitlines()
        skip = _table_start(lines, delim)
        if skip:
            check.note = ((check.note + " · ") if check.note else "") + \
                         f"bỏ {skip} dòng lời tựa"
        reader = csv.reader(io.StringIO("\n".join(lines[skip:])), delimiter=delim)
        try:
            rows = [r for _, r in zip(range(400), reader)]
        except csv.Error as exc:
            # Đã xảy ra thật: một .zip đọc thẳng như CSV ném "new-line character
            # seen in unquoted field" và làm hỏng cả lượt dựng đề bài. Một tệp
            # đọc không nổi chỉ được phép loại ĐỀ BÀI ĐÓ.
            check.problems.append(f"đọc không ra bảng: {exc}"[:90])
            return check
        if not rows:
            check.problems.append("tệp rỗng")
            return check
        check.columns = [c.strip() for c in rows[0]][:40]
        body = rows[1:]
        check.rows_seen = len(body)
        if body:
            width = len(check.columns)
            for index in range(width):
                values = [r[index].strip() for r in body[:60] if len(r) > index]
                if not values:
                    continue
                name = check.columns[index] if index < len(check.columns) else ""
                if sum(bool(DATE_VALUE.match(v)) for v in values) > len(values) * 0.7:
                    # Trục thời gian thì mỗi dòng một mốc KHÁC NHAU. Cột "Date
                    # added" của bảng tra cứu cũng toàn ngày, nhưng lặp lại —
                    # nó nói tin đó vào bảng lúc nào, không phải quan sát lúc
                    # nào. Ngày lặp lại thì không phải trục, cũng không phải số
                    # đo, nên nó rơi ra khỏi cả hai ô đếm.
                    if (len(set(values)) > len(values) * 0.7
                            and not META_DATE.search(name)):
                        check.date_by_value.append(name or f"cột {index + 1}")
                elif sum(bool(NUM_VALUE.match(v)) for v in values) > len(values) * 0.7:
                    check.numeric_cols += 1
        if size and len(raw) and check.rows_seen:
            check.est_rows = int(size / (len(raw) / max(check.rows_seen, 1)))

    named = [c for c in check.columns
             if DATE_COL.search(c.replace("_", " ").replace("-", " "))
             and not META_DATE.search(c)]
    real_dates = named or check.date_by_value
    check.has_date = bool(real_dates)
    check.date_cols = real_dates
    check.price_cols = [c for c in check.columns if PRICE_COL.search(c)]

    # Bảng tra cứu: mỗi dòng một thực thể, không phải chuỗi quan sát theo thời gian.
    #
    # Dấu hiệu DUY NHẤT là thiếu trục thời gian. Điều kiện cũ còn đòi trên một
    # cột số, từ hồi cột ngày dạng 19260701 bị đếm nhầm là cột số; giờ ngày đã
    # tách riêng nên nó loại oan đúng dạng chuỗi phổ biến nhất: một cột ngày,
    # một cột giá trị (VIX ngày của FRED chính là thế).
    if check.kind == "csv" and check.rows_seen:
        check.lookup_table = not real_dates

    if len(check.columns) < 2:
        check.problems.append("dưới 2 cột — không đủ để phân tích gì")
    if check.rows_seen < 20 and (check.est_rows or 0) < 100:
        check.problems.append(f"chỉ thấy {check.rows_seen} dòng — quá ít")
    check.ok = not check.problems
    return check


def judge(brief, check: DataCheck) -> list[str]:
    """Dữ liệu này có đỡ được đề bài đó không. Trả về danh sách chỗ vênh."""
    out: list[str] = list(check.problems)
    text = " ".join([brief.question, brief.measure, *brief.method]).lower()

    needs_time = any(w in text for w in
                     ("time series", "daily", "monthly", "yearly", "over 10 years",
                      "walk-forward", "rolling", "backtest", "momentum", "trend",
                      "point-in-time", "history", "over 20 years"))
    needs_price = any(w in text for w in
                      ("return", "price", "sharpe", "momentum", "volatility",
                       "drawdown", "portfolio", "pnl", "yield", "alpha"))

    if needs_time and not check.has_date:
        meta = [c for c in check.columns if META_DATE.search(c)]
        extra = (f" (cột '{meta[0]}' là siêu dữ liệu, không phải trục thời gian)"
                 if meta else "")
        out.append("đề bài cần chuỗi thời gian nhưng dữ liệu không có cột ngày"
                   + extra + ": " + ", ".join(check.columns[:6]))

    # Bảng CÓ trục thời gian thì mọi cột số đều là quan sát theo thời gian —
    # tên cột lúc đó là tên chuỗi (ngành, mã, danh mục), không phải "close" hay
    # "price". Bộ 49 ngành của Fama-French đặt tên cột là Agric, Food, Beer…
    # mà toàn bộ giá trị bên trong là lợi suất ngày.
    series = check.has_date and check.numeric_cols >= 1
    if needs_price and not check.price_cols and not series:
        out.append("đề bài cần giá/lợi suất nhưng không có cột nào như thế: "
                   + ", ".join(check.columns[:6]))

    if check.lookup_table and (needs_time or needs_price):
        out.append(f"đây là bảng tra cứu ({check.est_rows or check.rows_seen} dòng, "
                   f"{check.numeric_cols} cột số), không phải chuỗi quan sát")

    if check.numeric_cols == 0 and check.kind == "csv":
        out.append("không có cột số nào — không đo được gì")

    if (check.est_rows or check.rows_seen) < 500 and needs_time:
        out.append(f"chỉ ~{check.est_rows or check.rows_seen} dòng — quá ít cho "
                   "phân tích chuỗi thời gian")
    return out


def _unzip(url: str, fetch) -> tuple[bytes, str, int | None, str]:
    """Tải trọn .zip rồi lấy bảng đầu tiên bên trong.

    Trả về (bytes, content-type, cỡ, ghi chú). bytes rỗng + ghi chú = hỏng.
    """
    try:
        whole, _ctype, size = fetch(url, limit=MAX_ZIP, ranged=False)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return b"", "", None, f"tải zip không được: {type(exc).__name__}"
    try:
        book = zipfile.ZipFile(io.BytesIO(whole))
        names = [n for n in book.namelist()
                 if n.lower().endswith((".csv", ".txt"))
                 and not n.startswith("__")
                 and not re.search(r"readme|licen[cs]e|notes?\.", n, re.I)]
        # .csv trước .txt, rồi tệp TO nhất: FRED gói nhiều chuỗi thành zip có
        # README.txt nằm trước tệp dữ liệu, lấy tệp đầu tiên là đọc lời tựa.
        names.sort(key=lambda n: (not n.lower().endswith(".csv"),
                                  -book.getinfo(n).file_size))
        if not names:
            return b"", "", None, "zip không có tệp dữ liệu nào bên trong"
        with book.open(names[0]) as member:
            return (member.read(PEEK_BYTES), "text/csv", size,
                    f"đọc {names[0]} trong zip")
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        return b"", "", None, f"zip hỏng: {type(exc).__name__}"


def _delimiter(text: str) -> str:
    """Dấu phân cách cột. Sniffer đoán BỪA khi tệp mở đầu bằng văn xuôi — trên
    tệp Fama-French nó trả về '\r', và csv.reader ném thẳng ValueError. Chỉ
    nhận bốn dấu thật, còn lại quay về dấu phẩy."""
    try:
        found = csv.Sniffer().sniff(text[:4000]).delimiter
    except csv.Error:
        found = ""
    # Phải là TUPLE. `found in ",;\t|"` là kiểm chuỗi con: Sniffer thất bại trả
    # về "", mà "" nằm trong mọi chuỗi -> lọt qua -> csv.reader ném TypeError.
    # Cùng một hạng lỗi với 'excel' nằm trong 'excellent'.
    return found if found in (",", ";", "\t", "|") else ","


def _table_start(lines: list[str], delim: str) -> int:
    """Bảng bắt đầu ở dòng nào — bỏ phần lời tựa phía trên.

    Rất nhiều bộ dữ liệu công khai mở đầu bằng vài dòng văn xuôi (bản quyền,
    nguồn, cách mã hoá ô trống). Đọc từ dòng đầu là lấy nhầm một câu văn làm
    tên cột, rồi kết luận "dưới 2 cột" và loại oan bộ dữ liệu.

    Dấu hiệu của bảng: SỐ Ô giữ nguyên qua ba dòng liền nhau. Chỉ xét hai dòng
    thì chưa đủ — đo được trên tệp Fama-French: hai câu văn liền nhau tình cờ
    cùng có một dấu phẩy, và nó nhận nhầm câu văn làm tiêu đề.

    Lấy dòng có NHIỀU ô nhất, không phải dòng đầu tiên hợp lệ, vì bảng thật
    bao giờ cũng nhiều cột hơn một câu văn lọt lưới.
    """
    best_index, best_count = 0, 0
    for index in range(max(0, min(len(lines) - 2, 80))):
        count = lines[index].count(delim)
        if count <= best_count:
            continue
        if (lines[index + 1].count(delim) == count
                and lines[index + 2].count(delim) == count):
            best_index, best_count = index, count
    return best_index
