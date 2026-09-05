"""Khung trang: sidebar trái + vùng nội dung cuộn được.

CHỈ VẼ. Không luật nghiệp vụ, không đọc DB.

Bố cục kiểu app desktop, không phải trang web:
    sidebar cố định bên trái, chạy lên tận đỉnh cửa sổ (thanh tiêu đề trong suốt)
    vùng nội dung tự cuộn, sidebar đứng yên
"""

from __future__ import annotations

from html import escape as esc

# (đường dẫn, nhãn, ký hiệu)
NAV = [
    ("/",          "Home",     "◈"),
    ("/jobs",      "Jobs",     "◆"),
    ("/queue",     "Queue",    "▣"),
    ("/pipeline",  "Pipeline", "▤"),
    ("/projects",  "Projects", "▦"),
    ("/profile",   "Profile",  "◇"),
    ("/stats",     "Stats",    "▥"),
    ("/settings",  "Settings", "⚙"),
]


def page(title: str, body: str, active: str = "", wide: bool = False,
         pending: int = 0, mock: bool = False, status: str = "") -> str:
    """mock=True -> dải cảnh báo dữ liệu giả. Trang đã nối thật thì KHÔNG hiện."""
    links = ""
    for href, label, mark in NAV:
        badge = (f"<b class=navcount>{pending}</b>"
                 if label == "Queue" and pending else "")
        on = " on" if href == active else ""
        links += (f"<a class='navlink{on}' href='{esc(href)}'>"
                  f"<i>{mark}</i><span>{esc(label)}</span>{badge}</a>")

    foot = (f"<div class=navfoot><span class=dot></span>{esc(status)}</div>"
            if status else "")
    banner = ("<div class=mockbar>Placeholder data — this page is not wired up yet</div>"
              if mock else "")

    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)} · jobbot</title>"
        "<link rel=stylesheet href='/static/app.css'></head><body>"
        f"<aside class=side><div class=brand>jobbot</div>"
        f"<nav>{links}</nav>{foot}</aside>"
        f"<main class='{'wide' if wide else ''}'>{banner}"
        f"<div class=inner>{body}</div></main></body></html>"
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
