"""Biểu đồ bằng SVG dựng thẳng ở server. Không thư viện vẽ.

Vì sao không dùng thư viện: cả app không có một gói cài thêm nào, và biểu đồ
ở đây chỉ có hai loại — cột theo thời gian, và dải phân bố. Kéo về một thư
viện 300KB để vẽ 14 cái hình chữ nhật là đổi một thứ đang sạch lấy một thứ
phải bảo trì.

SVG dựng ở server còn được thêm: trang hiện ra là đã có hình, không chờ JS.

CHỈ VẼ. Số liệu là việc của live.py.
"""

from __future__ import annotations

from html import escape as esc

W, H = 100, 100          # toạ độ trong viewBox; CSS lo kích thước thật


def _empty(note: str) -> str:
    return f"<div class=empty-box>{esc(note)}</div>"


def bars(rows: list[tuple[str, int]], unit: str = "",
         note: str = "chưa có số liệu") -> str:
    """Cột theo thời gian. rows = [(nhãn, giá trị)] theo thứ tự thời gian.

    Chỉ ghi nhãn ở cột đầu và cột cuối — 14 nhãn ngày chen nhau thì không đọc
    được cái nào, mà mắt chỉ cần biết dải thời gian là từ đâu tới đâu.
    """
    if not rows or not any(v for _, v in rows):
        return _empty(note)

    top = max(v for _, v in rows) or 1
    step = W / len(rows)
    width = max(step * 0.62, 0.8)

    body = ""
    for index, (label, value) in enumerate(rows):
        height = value / top * H
        x = index * step + (step - width) / 2
        body += (f"<rect class=bar x='{x:.2f}' y='{H - max(height, 0.6):.2f}'"
                 f" width='{width:.2f}' height='{max(height, 0.6):.2f}'>"
                 f"<title>{esc(label)}: {value}{esc(unit)}</title></rect>")

    # Nhãn để NGOÀI svg. preserveAspectRatio=none kéo giãn cột cho vừa ô —
    # kéo cả chữ thì chữ méo. Cột thì giãn được, chữ thì không.
    return (f"<div class=plot><div class=pmax>{top}{esc(unit)}</div>"
            f"<svg class=chart viewBox='0 0 {W} {H}' preserveAspectRatio=none"
            f" role=img aria-label='biểu đồ cột'>{body}</svg>"
            f"<div class=pfoot><span>{esc(rows[0][0])}</span>"
            f"<span>{esc(rows[-1][0])}</span></div></div>")


def spread(rows: list[tuple[str, int, str]], note: str = "chưa có số liệu") -> str:
    """Dải phân bố ngang. rows = [(nhãn, số lượng, lớp màu)].

    Dùng cho "6 likely · 111 possible · 87 unlikely": một dải liền cho thấy
    TỈ LỆ ngay, ba con số rời thì phải tự nhẩm.
    """
    total = sum(n for _, n, _ in rows)
    if not total:
        return _empty(note)

    seg = legend = ""
    for label, count, kind in rows:
        if not count:
            continue
        seg += (f"<span class='sg {esc(kind)}' style='flex:{count}'"
                f" title='{esc(label)}: {count}'></span>")
        legend += (f"<span class=lg><b class='dotc {esc(kind)}'></b>"
                   f"{esc(label)} <u>{count}</u></span>")
    return f"<div class=spread>{seg}</div><div class=legend>{legend}</div>"
