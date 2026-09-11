"""Kho chức danh — rút từ TIN THẬT, không gõ tay.

Câu hỏi trong hồ sơ nói rõ: "viết ĐÚNG như chức danh xuất hiện trên tin". Vậy
nguồn đúng duy nhất là chính các tin đó. Một danh sách gõ tay trong mã nguồn
sai ngay từ ngày viết và mục dần từ đó: thị trường đẻ chức danh mới liên tục
("Forward Deployed Engineer" không tồn tại vài năm trước), mà không ai nhớ vào
sửa lại file.

Hai đường lấy, cùng một hàm rút:

    từ DB     `posting` đã có tin thì dùng luôn — miễn phí, và tự mới lại sau
              mỗi lần quét, không cần cơ chế cập nhật riêng nào.
    từ board  ngày đầu tiên chưa có tin nào thì gọi thẳng board công ty. Đo
              được: 9 board -> 1.471 tin -> 1.107 tiêu đề trong ~4 giây, thuần
              HTTP, không cần Chrome và KHÔNG cần hồ sơ (cổng chỉ chặn quét có
              lọc, không chặn đọc board).

Rút CỤM NGHỀ chứ không lấy nguyên tiêu đề: tiêu đề thật là
"2027 Point72 Academy Investment Analyst Summer Internship Program - Japan
(BCF)" — dùng làm gợi ý thì vô dụng. Thứ tìm được việc là cụm "Investment
Analyst".
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter

# Từ cuối của một cụm nghề. Cụm phải KẾT THÚC bằng một trong số này — "Senior
# Quantitative" không phải chức danh, "Quantitative Researcher" mới là.
ROLE_TAIL = re.compile(
    r"^(analyst|engineer|scientist|developer|researcher|manager|trader|"
    r"strategist|consultant|associate|specialist|architect|lead|intern|"
    r"quant|technologist|administrator)$", re.I)
WORD = re.compile(r"[A-Za-z+#][A-Za-z+#'&.]*")
CACHE_KEY = "title_vocab"


def extract(titles: list[str], least: int = 3, top: int = 60) -> list[tuple[str, int]]:
    """Tiêu đề thật -> cụm nghề dùng được, kèm số tin chứa nó.

    `least` là sàn: cụm chỉ xuất hiện một hai lần thường là tên chương trình
    riêng của một công ty, không phải thứ gõ vào ô tìm.
    """
    dem: Counter = Counter()
    for raw in titles:
        t = re.sub(r"\s*[\(\[].*?[\)\]]", "", raw or "")      # bỏ ngoặc
        t = re.split(r"\s+[-–—,|/]\s+", t)[0]                 # bỏ đuôi địa điểm
        w = WORD.findall(t)
        for n in (2, 3):
            for i in range(len(w) - n + 1):
                cum = w[i:i + n]
                if not ROLE_TAIL.match(cum[-1]):
                    continue
                dem[" ".join(cum)] += 1

    thuong = [(k, v) for k, v in dem.most_common() if v >= least]

    # Bỏ cụm DÀI HƠN mà không phổ biến hơn: "Academy Investment Analyst" (15)
    # nằm trong "Investment Analyst" (15) — cùng số tin nghĩa là cụm dài chỉ
    # là một cách gọi riêng của một công ty. Cụm ngắn tìm được rộng hơn.
    #
    # Ngược lại, "Machine Learning Researcher" (13) nằm trong "Learning
    # Researcher" (13) — ở đây cụm NGẮN mới là mảnh vụn. Nên luật là: bỏ cụm
    # nào là khúc GIỮA/ĐUÔI của một cụm khác cùng số tin, giữ cụm đứng đầu.
    giu: list[tuple[str, int]] = []
    for cum, n in thuong:
        thua = False
        for khac, m in thuong:
            if khac == cum or n != m:
                continue
            if cum in khac and not khac.startswith(cum):
                thua = True       # cum là đuôi của khac -> mảnh vụn
                break
            if khac in cum and cum.endswith(khac):
                thua = True       # cum dài hơn nhưng không phổ biến hơn
                break
        if not thua:
            giu.append((cum, n))
    return giu[:top]


def from_postings(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    rows = conn.execute("SELECT title FROM posting WHERE title <> ''").fetchall()
    return extract([r[0] for r in rows]) if rows else []


def fetch_boards(boards: dict[str, list[str]], log=None) -> list[str]:
    """Gọi board công ty lấy tiêu đề. KHÔNG lưu tin — chỉ mượn chữ.

    Board nào hỏng thì bỏ qua: kho chức danh thiếu vài dòng vẫn dùng được,
    còn ném lỗi ra thì cả nút bấm chết vì một board đang bảo trì.
    """
    from ..ingest import ashby, greenhouse, lever
    mods = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}
    out: list[str] = []
    for ten, danh_sach in boards.items():
        mod = mods.get(ten)
        if mod is None:
            continue
        for board in danh_sach:
            try:
                out += [p.title for p in mod.fetch_board(board)]
            except Exception as exc:                       # noqa: BLE001
                if log:
                    log(f"{ten}:{board} — {type(exc).__name__}")
    return out


def cached(conn: sqlite3.Connection) -> list[str]:
    """Kho để màn hình dùng. Ưu tiên tin đã quét, sau đó mới tới bản đã lưu."""
    from ..core import prefs
    tu_tin = from_postings(conn)
    if tu_tin:
        return [c for c, _ in tu_tin]
    try:
        return json.loads(prefs.get(conn, CACHE_KEY) or "[]")
    except (ValueError, TypeError):
        return []


def save(conn: sqlite3.Connection, cum: list[tuple[str, int]]) -> int:
    from ..core import prefs
    prefs.put(conn, CACHE_KEY, json.dumps([c for c, _ in cum]))
    return len(cum)
