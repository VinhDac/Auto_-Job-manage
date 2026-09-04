"""Khung trang dùng chung: nav, thẻ, huy hiệu, thanh điểm.

CHỈ VẼ. Không có luật nghiệp vụ, không đọc DB.
Mọi trang đều đi qua page() để nav và banner nhất quán.
"""

from __future__ import annotations

from html import escape as esc

NAV = [
    ("/", "Dashboard"),
    ("/jobs", "Jobs"),
    ("/queue", "Queue"),
    ("/pipeline", "Pipeline"),
    ("/projects", "Projects"),
    ("/profile", "Profile"),
    ("/stats", "Stats"),
    ("/settings", "Settings"),
]

# Bật/tắt banner nhắc đây là dữ liệu giả. Xoá khi backend nối xong.
MOCK_BANNER = True


def page(title: str, body: str, active: str = "", wide: bool = False,
         pending: int = 0) -> str:
    nav = "".join(
        f"<a href='{esc(href)}' class='{'on' if href == active else ''}'>{esc(label)}"
        + (f"<span class=pill>{pending}</span>" if label == "Queue" and pending else "")
        + "</a>"
        for href, label in NAV
    )
    banner = (
        "<div class=mockbar>Mock data — backend not connected yet. "
        "Everything below is a placeholder to agree the shape of the app.</div>"
        if MOCK_BANNER else ""
    )
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)} · jobbot</title>"
        "<link rel=stylesheet href='/static/app.css'></head><body>"
        f"{banner}<nav class=top><span class=brand>jobbot</span>{nav}</nav>"
        f"<main class='{'wide' if wide else ''}'>{body}</main></body></html>"
    )


# ---------------------------------------------------------------- mảnh nhỏ

def h1(text: str, sub: str = "") -> str:
    return f"<h1>{esc(text)}</h1>" + (f"<p class=lead>{esc(sub)}</p>" if sub else "")


def badge(text: str, kind: str = "") -> str:
    return f"<span class='badge {kind}'>{esc(text)}</span>"


def score_bar(score: int) -> str:
    """Thanh điểm khớp. Màu theo ngưỡng, không phải gradient — đọc nhanh hơn."""
    kind = "hi" if score >= 75 else ("mid" if score >= 55 else "lo")
    return (
        f"<span class='score {kind}'><span class=track>"
        f"<span class=fill style='width:{score}%'></span></span>"
        f"<b>{score}</b></span>"
    )


def stat(value: str, label: str, note: str = "") -> str:
    return (
        f"<div class=stat><b>{esc(value)}</b><span>{esc(label)}</span>"
        + (f"<i>{esc(note)}</i>" if note else "") + "</div>"
    )


def card(inner: str, cls: str = "") -> str:
    return f"<div class='card {cls}'>{inner}</div>"


def empty(text: str) -> str:
    return f"<div class=empty-box>{esc(text)}</div>"


def section(title: str, inner: str, action: str = "") -> str:
    return f"<h2>{esc(title)}{action}</h2>{inner}"
