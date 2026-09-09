"""Khuôn chung cho mọi tab CÓ THỜI GIAN CHẠY.

Search, Score, Project là ba việc khác nhau, nhưng câu hỏi người dùng đặt ra
cho cả ba là một:

    đang làm gì · vừa làm gì · ra được cái gì · chỉnh ở đâu · hỏng thì soi đâu

Nên chúng dùng CHUNG một khuôn. Mỗi tab tự nộp phần ruột, còn vị trí các ô,
cách lọc nhật ký theo luồng, chỗ đặt thanh tiến độ thì giống hệt nhau — học
một tab là biết cả ba, và thêm tab thứ tư không phải nghĩ lại từ đầu.

CHỈ VẼ.
"""

from __future__ import annotations

from html import escape as esc

from ..layout import grid, journal_box, page, progress_box, stat, widget


def tiles(rows: list[tuple[str, str, str]]) -> str:
    """rows = [(số, nhãn, ghi chú)]."""
    return "<div class=stats>" + "".join(stat(v, k, note) for v, k, note in rows) + "</div>"


def rows(items: list[tuple[str, str]], empty_note: str = "—") -> str:
    """Bảng hai cột nhãn/giá trị — dùng cho ô thống kê và ô cài đặt."""
    if not items:
        return f"<div class=empty-box>{esc(empty_note)}</div>"
    return "<div class=krows>" + "".join(
        f"<div class=krow><span>{esc(k)}</span><b>{v}</b></div>"
        for k, v in items) + "</div>"


def actions(items: list[tuple[str, str, str]]) -> str:
    """Nút debug. items = [(nhãn, đường dẫn POST, mô tả)].

    Nút nào CHƯA nối backend thì để path rỗng — nó hiện mờ và không bấm được,
    thay vì bấm vào rồi không có gì xảy ra và người dùng tưởng app hỏng.
    """
    out = ""
    for label, path, note in items:
        dead = "" if path else " disabled"
        act = f" data-act='{esc(path)}'" if path else ""
        out += (f"<div class=drow><button class=mbtn{dead}{act}>{esc(label)}</button>"
                f"<span class=muted>{esc(note)}</span></div>")
    return f"<div class=debug>{out}</div>"


def render(*, title: str, active: str, stream: str,
           stats: str, chart_title: str, chart: str,
           settings: str, debug: str, note: str = "") -> str:
    """Sáu ô, thứ tự cố định cho mọi tab runtime.

    Nhật ký chiếm nguyên cột phải, cao bằng cả trang — nó là thứ được nhìn
    nhiều nhất, và cắt nó xuống ba dòng thì coi như không có.
    """
    head = (f"<div class=tnote>{esc(note)}</div>" if note else "")
    return page(title, head + grid(
        widget("Đang chạy", progress_box(stream), span=2),
        widget(f"Nhật ký · {title.lower()}", journal_box(stream),
               span=1, rows=4, cls="tall"),
        widget("Thống kê", stats, span=2),
        widget(chart_title, chart, span=2),
        widget("Cài đặt", settings, span=1),
        widget("Debug", debug, span=1),
        cols=3,
    ), active=active, flow=False)
