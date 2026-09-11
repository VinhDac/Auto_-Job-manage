"""Home — ĐANG TRỐNG, chờ thiết kế lại.

Bản cũ là một lưới sáu widget: phễu, con số, biểu đồ tin mỗi ngày, cơ hội
thật, cần bạn, nhật ký. Đã gỡ hết cùng với 135 dòng ở `live.py` chỉ tồn tại
để nuôi nó, và cả `dashboard/plot.py` — không ai khác dùng.

Giữ lại đúng cái vỏ: thanh bên, thanh master, tấm phủ Cài đặt. Xoá luôn cả
route thì mục Home ở thanh bên thành 404.

Muốn xem bản cũ: `git show HEAD -- src/jobbot/dashboard/views/home.py`.
"""

from __future__ import annotations

from ..layout import page


def render() -> str:
    return page(
        "Home",
        "<div class=empty-box>Trang này đang trống — sẽ thiết kế lại.</div>",
        active="/",
    )
