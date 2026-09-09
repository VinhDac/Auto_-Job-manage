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
    out = ""
    for k, v in items:
        # Dòng "— CHROME —" là TIÊU ĐỀ nhóm, không phải một cài đặt. Nhận ra
        # bằng chỗ giá trị rỗng, để cài đặt của ba cách tìm không lẫn vào nhau.
        if not v:
            out += f"<div class=kgroup>{esc(k.strip(' —'))}</div>"
        else:
            out += f"<div class=krow><span>{esc(k)}</span><b>{v}</b></div>"
    return f"<div class=krows>{out}</div>"


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


def _rows_needed(panels: list[tuple], width: int, run_span: int = 0) -> int:
    """Bên trái xếp hết mấy hàng — để nhật ký bên phải cao đúng bằng.

    Không dùng CSS 'grid-row: 1 / -1' được: số âm chỉ đếm các hàng KHAI BÁO
    tường minh, mà lưới ở đây dùng grid-auto-rows nên hàng là hàng ngầm —
    '1 / -1' rút về đúng một hàng. Còn đếm tay thì thêm bớt một ô là lệch.
    """
    # Ô "Đang chạy" nằm ở hàng 1; nếu nó không chiếm trọn hàng thì ô nội dung
    # đầu tiên xếp ngay cạnh nó, không xuống hàng mới.
    run_span = run_span or width
    row, col, tall = 1, run_span, 1
    for _title, _body, span, rows in panels:
        if col + span > width:        # hết chỗ -> xuống hàng mới
            row += tall
            col, tall = 0, 1
        col += span
        tall = max(tall, rows)
    return row + tall - 1


def panel(title: str, body: str, span: int = 1, rows: int = 1) -> tuple:
    """Một ô nội dung riêng của tab. Khuôn lo phần chung, tab lo phần ruột."""
    return (title, body, span, rows)


def render(*, title: str, active: str, stream: str, panels: list[tuple],
           note: str = "", cols: int = 3, run_span: int | None = None,
           run_extra: str = "") -> str:
    """Khuôn chung cho mọi tab CÓ THỜI GIAN CHẠY.

    Cố định hai ô, vì tab runtime nào cũng cần đúng hai thứ đó:
        "Đang chạy"  — tiến độ của luồng này
        "Nhật ký"    — sự kiện của luồng này, cao nguyên cột phải

    Phần còn lại do tab tự xếp. Trước đây khuôn ép cứng sáu ô cùng kích thước,
    nên tab Search phải nhét hai thẻ "cách tìm" vào một ô cao 180px và cụt mất
    thẻ thứ hai. Hình dạng nên dùng chung; kích thước thì tuỳ nội dung.
    """
    head = f"<div class=tnote>{esc(note)}</div>" if note else ""
    boxes = [widget("Đang chạy", progress_box(stream) + run_extra,
                    span=run_span if run_span else cols - 1),
             widget(f"Nhật ký · {title.lower()}", journal_box(stream), span=1,
                    rows=_rows_needed(panels, cols - 1, run_span or 0),
                    cls="tall", at=(cols, 1))]
    boxes += [widget(t, body, span=sp, rows=rw) for t, body, sp, rw in panels]
    return page(title, head + grid(*boxes, cols=cols), active=active, flow=False)
