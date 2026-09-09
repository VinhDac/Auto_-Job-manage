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
from dataclasses import dataclass, field

from ..ingest.base import UA

PEEK_BYTES = 96_000
DATE_COL = re.compile(r"\b(date|time|timestamp|day|month|year|period|dt)\b", re.I)
# "Date added", "Founded", "Year established" là siêu dữ liệu, KHÔNG phải trục
# thời gian. Nhầm hai thứ này là lý do một bảng tra cứu 399 dòng lọt qua như
# thể nó là chuỗi giá 20 năm.
META_DATE = re.compile(r"\b(date\s*(added|founded|created|joined|listed)|"
                       r"founded|established|incorporated|inception)\b", re.I)
PRICE_COL = re.compile(r"\b(open|high|low|close|adj|price|px|return|ret|nav|"
                       r"volume|vwap|bid|ask|yield|rate|value|amount)\b", re.I)
NUM_VALUE = re.compile(r"^-?\d[\d,]*\.?\d*([eE][-+]?\d+)?$")


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
    problems: list[str] = field(default_factory=list)
    note: str = ""


def _fetch(url: str, timeout: float = 20.0) -> tuple[bytes, str, int | None]:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Range": f"bytes=0-{PEEK_BYTES}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(PEEK_BYTES)
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
        try:
            dialect = csv.Sniffer().sniff(text[:4000])
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(io.StringIO(text), dialect)
        rows = [r for _, r in zip(range(400), reader)]
        if not rows:
            check.problems.append("tệp rỗng")
            return check
        check.columns = [c.strip() for c in rows[0]][:40]
        body = rows[1:]
        check.rows_seen = len(body)
        if body:
            width = len(check.columns)
            for index in range(width):
                values = [r[index] for r in body[:60] if len(r) > index]
                if values and sum(bool(NUM_VALUE.match(v.strip())) for v in values) > len(values) * 0.7:
                    check.numeric_cols += 1
        if size and len(raw) and check.rows_seen:
            check.est_rows = int(size / (len(raw) / max(check.rows_seen, 1)))

    real_dates = [c for c in check.columns
                  if DATE_COL.search(c) and not META_DATE.search(c)]
    check.has_date = bool(real_dates)
    check.date_cols = real_dates
    check.price_cols = [c for c in check.columns if PRICE_COL.search(c)]

    # Bảng tra cứu: mỗi dòng một thực thể, không phải chuỗi quan sát theo thời gian
    if check.kind == "csv" and check.rows_seen:
        check.lookup_table = (not real_dates) or check.numeric_cols <= 1

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

    if needs_price and not check.price_cols:
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
