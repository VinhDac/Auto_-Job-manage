"""Download the data. Run: python3 get_data.py

The data is NOT committed — only the script that fetches it. A reader can
rebuild everything from zero, and the repo does not carry megabytes of CSV.
"""
from __future__ import annotations

import io
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "{{url}}"
OUT = Path(__file__).parent / "data" / "raw.csv"
UA = "Mozilla/5.0 (compatible; project-data/1.0)"

DATE_LIKE = r"\d{8}|\d{4}-\d{2}-\d{2}|\d{6}"


def fetch(url: str = URL) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def unwrap(raw: bytes) -> str:
    """Many public sources ship a .zip even when the URL ends in .csv."""
    if not raw.startswith(b"PK\x03\x04"):
        return raw.decode("utf-8", "replace")
    book = zipfile.ZipFile(io.BytesIO(raw))
    names = [n for n in book.namelist()
             if n.lower().endswith((".csv", ".txt"))
             and not re.search(r"readme|licen[cs]e", n, re.I)]
    names.sort(key=lambda n: (not n.lower().endswith(".csv"),
                              -book.getinfo(n).file_size))
    return book.read(names[0]).decode("utf-8", "replace")


def table_start(lines: list[str]) -> int:
    """Skip the prose above the table.

    A table holds its field count steady; prose does not. Requiring three
    consecutive rows with the same count matters: two adjacent sentences that
    happen to share one comma would otherwise be read as a header.
    """
    best_i, best_n = 0, 0
    for i in range(max(0, min(len(lines) - 2, 80))):
        n = lines[i].count(",")
        if n > best_n and lines[i + 1].count(",") == n == lines[i + 2].count(","):
            best_i, best_n = i, n
    return best_i


def parse(text: str) -> pd.DataFrame:
    # dtype=str is required. Left to infer, pandas reads the date column as
    # int64 near the top of the file and as str further down (the "mixed
    # types" warning) — and then 19260701 is taken as nanoseconds since 1970,
    # so every date is wrong.
    lines = text.splitlines()
    frame = pd.read_csv(io.StringIO("\n".join(lines[table_start(lines):])),
                        dtype=str, skip_blank_lines=False)
    frame = frame.rename(columns={frame.columns[0]: "date"})

    # Some files concatenate several tables (Ken French: value-weighted, then
    # equal-weighted) separated by a blank line and a caption. Keep the first
    # table: cut at the first row that is not a date.
    key = frame["date"].fillna("").str.strip()
    bad = (~key.str.fullmatch(DATE_LIKE, na=False)).to_numpy().nonzero()[0]
    if len(bad):
        frame, key = frame.iloc[: bad[0]], key.iloc[: bad[0]]

    stamp = pd.to_datetime(key, format="%Y%m%d", errors="coerce")
    stamp = stamp.fillna(pd.to_datetime(key, errors="coerce", format="mixed"))
    frame = frame.assign(date=stamp).dropna(subset=["date"]).set_index("date")
    return frame.apply(pd.to_numeric, errors="coerce")


def main() -> None:
    frame = parse(unwrap(fetch()))
    OUT.parent.mkdir(exist_ok=True)
    frame.to_csv(OUT)
    print(f"{OUT}  ·  {len(frame):,} rows  ·  {frame.shape[1]} {{units}}"
          f"  ·  {frame.index.min():%Y-%m-%d} → {frame.index.max():%Y-%m-%d}")


if __name__ == "__main__":
    main()
