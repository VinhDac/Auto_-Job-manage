"""Khung trang: sidebar trái + thanh master + vùng widget.

CHỈ VẼ. Không luật nghiệp vụ, không đọc DB.

Bố cục kiểu app desktop, không phải trang web:
    sidebar cố định trái, chạy lên tận đỉnh cửa sổ
    thanh master trên cùng: RUN / PAUSE / trạng thái đang chạy
    nội dung là các Ô (widget) — mỗi ô tự cuộn bên trong, TRANG thì không cuộn

Vì sao ô tự cuộn chứ không phải trang cuộn: đây là app chạy 24/7, mở ra là
phải thấy ngay toàn cảnh. Trang cuộn thì nửa thông tin nằm dưới màn hình,
và cái đang chạy có thể đang nằm ở chỗ không nhìn thấy.
"""

from __future__ import annotations

from html import escape as esc

# (đường dẫn, nhãn, ký hiệu)
# Thứ tự = thứ tự công việc chạy thật, không phải thứ tự chữ cái.
# Tab có (rt) là tab CÓ THỜI GIAN CHẠY -> dùng khuôn views/runtime.py.
NAV = [
    ("/",          "Home",     "◈"),
    ("/search",    "Search",   "⌕"),      # rt — bước 1
    ("/jobs",      "Jobs",     "◆"),      #      kết quả bước 1+2
    ("/score",     "Score",    "▤"),      # rt — bước 2
    ("/projects",  "Projects", "▦"),      # rt — bước 4
    ("/profile",   "Profile",  "◇"),
    ("/settings",  "Settings", "⚙"),
]


def page(title: str, body: str, active: str = "", wide: bool = False,
         status: str = "", flow: bool = True) -> str:
    """flow=True  trang cuộn như cũ — dành cho trang CHƯA chuyển sang widget
    flow=False trang không cuộn, nội dung là lưới widget tự cuộn bên trong
    """
    links = ""
    for href, label, mark in NAV:
        on = " on" if href == active else ""
        links += (f"<a class='navlink{on}' href='{esc(href)}'>"
                  f"<i>{mark}</i><span>{esc(label)}</span></a>")

    foot = (f"<div class=navfoot><span class=dot></span>{esc(status)}</div>"
            if status else "")
    # Thanh master. Trạng thái và nhãn nút do live.js ghi đè ngay khi SSE nối
    # được — chữ ở đây chỉ là thứ hiện trong tích tắc trước lúc đó.
    top = ("<header class=topbar>"
           "<div class=runstate><span class=rdot></span>"
           "<b data-state>đang nối…</b></div>"
           "<div class=masters>"
           "<button class=mbtn data-act=run>Chạy ngay</button>"
           "<button class=mbtn data-act=pause>Tạm dừng</button>"
           "</div></header>")

    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)} · jobbot</title>"
        "<link rel=stylesheet href='/static/app.css'></head><body>"
        f"<aside class=side><div class=brand>jobbot</div>"
        f"<nav>{links}</nav>{foot}</aside>"
        f"<main class='{'wide' if wide else ''}{' flow' if flow else ''}'>{top}"
        f"<div class=inner>{body}</div></main>"
        "<script src='/static/live.js'></script></body></html>"
    )


# ---------------------------------------------------------------- mảnh nhỏ

def h1(text: str, sub: str = "") -> str:
    return f"<h1>{esc(text)}</h1>" + (f"<p class=lead>{esc(sub)}</p>" if sub else "")


def badge(text: str, kind: str = "") -> str:
    return f"<span class='badge {kind}'>{esc(text)}</span>"


def score_bar(score: int) -> str:
    """Màu theo ngưỡng, không phải dải chuyển màu — đọc nhanh hơn."""
    kind = "hi" if score >= 75 else ("mid" if score >= 55 else "lo")
    return (f"<span class='score {kind}'><span class=track>"
            f"<span class=fill style='width:{score}%'></span></span><b>{score}</b></span>")


def stat(value: str, label: str, note: str = "", key: bool = False) -> str:
    return (f"<div class='stat{' key' if key else ''}'><b>{esc(value)}</b>"
            f"<span>{esc(label)}</span>"
            + (f"<i>{esc(note)}</i>" if note else "") + "</div>")


def card(inner: str, cls: str = "") -> str:
    return f"<div class='card {cls}'>{inner}</div>"


def empty(text: str) -> str:
    return f"<div class=empty-box>{esc(text)}</div>"


def section(title: str, inner: str, action: str = "") -> str:
    return f"<h2>{esc(title)}{action}</h2>{inner}"


# ---------------------------------------------------------------- ô (widget)

def widget(title: str, body: str, tools: str = "", span: int = 1,
           rows: int = 1, expand: bool = True, cls: str = "") -> str:
    """Một ô trong lưới. Tự cuộn bên trong, không đẩy trang dài ra.

    span = chiếm mấy cột. expand=True thì có nút mở to ra toàn màn hình để
    xem kỹ hoặc chỉnh, bấm lại (hoặc Esc) thì thu về.
    """
    grow = ("<button class=wexp data-expand title='Mở to (Esc để thu)'>⤢</button>"
            if expand else "")
    return (f"<section class='wid {cls}' data-widget"
            f" style='grid-column:span {span};grid-row:span {rows}'>"
            f"<header class=whead><h3>{esc(title)}</h3>"
            f"<div class=wtools>{tools}{grow}</div></header>"
            f"<div class=wbody>{body}</div></section>")


def grid(*widgets: str, cols: int = 3) -> str:
    return (f"<div class=wgrid style='grid-template-columns:repeat({cols},1fr)'>"
            + "".join(widgets) + "</div>")


def journal_box(stream: str = "") -> str:
    """Khung nhật ký. live.js tự đổ dữ liệu vào — ở đây không vẽ sẵn gì cả."""
    return f"<div class=journal data-journal='{esc(stream)}'></div>"


def progress_box(stream: str = "") -> str:
    return (f"<div class=progress data-progress='{esc(stream)}'>"
            "<div class=pidle>đang nối…</div></div>")
