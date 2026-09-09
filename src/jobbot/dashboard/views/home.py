"""Home — bảng tổng hợp của một cái máy đang chạy, không phải trang giới thiệu.

Người mở app lên không hỏi "có bao nhiêu tin". Họ hỏi:
    nó đang làm gì · nó vừa làm gì · có gì cần tôi không

Nên nhật ký chiếm hẳn một cột dọc, đứng cạnh mọi thứ khác. Còn nút RUN/PAUSE
thì nằm trên thanh master (layout.page), không nằm trong ô nào cả — bấm được
từ bất kỳ trang nào.

Trang KHÔNG cuộn: mỗi ô tự cuộn bên trong.
"""

from __future__ import annotations

from html import escape as esc

from .. import plot
from ..layout import (empty, grid, journal_box, page, progress_box, stat, widget)

TAG = {"approve": "Quyết định", "mail": "Cài đặt", "follow": "Theo dõi",
       "scan": "Quét", "warn": "Chú ý"}

KEY_LABELS = {"Unique jobs", "Awaiting you", "Match your titles"}


def _funnel(rows: list[dict]) -> str:
    top = max((r["n"] for r in rows), default=0) or 1
    out = ""
    for row in rows:
        # Bậc chưa làm hiện chữ 'chưa làm', KHÔNG hiện số 0 — số 0 đọc ra là
        # "đã chạy mà không ra gì", trong khi sự thật là chưa hề chạy.
        width = 0 if row["todo"] else max(row["n"] / top * 100, 0.8)
        value = "chưa làm" if row["todo"] else f"{row['n']:,}"
        out += (f"<div class='frow{' todo' if row['todo'] else ''}'>"
                f"<span class=fname>{esc(row['name'])}</span>"
                f"<span class=ftrack><i style='width:{width:.1f}%'></i></span>"
                f"<b class=fnum>{esc(value)}</b></div>")
    return f"<div class=funnel>{out}</div>"


def render(status: dict, counters: list[dict], needs: list[dict],
           activity: list[dict], *,
           days: list, chances: list, funnel: list) -> str:
    needs_html = "".join(
        # href="#settings" -> mở MENU cài đặt tại chỗ, không rời trang. Cài
        # đặt không còn là một trang để mà đi tới.
        f"<a class='need {esc(n['kind'])}' href='{esc(n['href'])}'"
        f"{' data-settings' if n['href'] == '#settings' else ''}>"
        f"<span class=tag>{esc(TAG.get(n['kind'], 'Ghi chú'))}</span>"
        f"<b>{esc(n['text'])}</b><span class=muted>{esc(n['note'])}</span></a>"
        for n in needs) or empty("Không có gì đang chờ bạn.")

    tiles = "".join(
        stat(c["value"], c["label"], c["note"], key=c["label"] in KEY_LABELS)
        for c in counters)

    # MỘT lưới duy nhất. Hai lưới chồng nhau thì tổng chiều cao vượt màn hình
    # và trang cuộn trở lại — đúng thứ đang muốn bỏ.
    body = grid(
        widget("Đang chạy", progress_box(), span=1),
        widget("Tin lấy về mỗi ngày", plot.bars(days, unit=" tin"), span=1),
        # Nhật ký cao bằng cả cột: đây là thứ được nhìn nhiều nhất.
        widget("Nhật ký", journal_box(), span=1, rows=4, cls="tall"),

        widget("Phễu", _funnel(funnel), span=2),
        widget("Con số", f"<div class=stats>{tiles}</div>", span=2),

        widget("Cần bạn", f"<div class=needs>{needs_html}</div>", span=1),
        widget("Cơ hội thật", plot.spread(chances), span=1),
        cols=3,
    )

    return page("Home", body, active="/", flow=False,
                status=f"{status['sources_ok']}/{status['sources_total']} nguồn")
