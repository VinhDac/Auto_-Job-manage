"""Score — bước 2, chấm điểm khớp và "có cửa không". Tab có thời gian chạy.

Hai câu hỏi KHÁC NHAU, cố ý tách:
    điểm   hồ sơ có khớp yêu cầu không
    cơ hội có đường vào không (đòi PhD, đòi 5 năm, chức danh senior)

Tin điểm cao mà cơ hội 'unlikely' thì không đáng nộp — nên ô thống kê phải
hiện cả hai, không chỉ điểm.
"""

from __future__ import annotations

from .. import plot
from . import runtime


def render(*, stats: dict, hist: list, chances: list, settings: list) -> str:
    blind = stats["blind"]
    tiles = runtime.tiles([
        (f"{stats['kept']:,}", "Tin đang giữ", "qua bộ lọc"),
        (f"{stats['scored']:,}", "Chấm được", f"{blind} không đọc được yêu cầu"),
        (f"{stats['strong']}", "Điểm ≥ 70", "khớp mạnh"),
        (f"{stats['worth']}", "Đáng nộp", "điểm cao VÀ có cửa"),
    ])

    # Không chấm được là trạng thái đáng báo, không phải con số bình thường:
    # nghĩa là bộ tách không đọc ra yêu cầu nào trong tin đó.
    alert = ""
    if blind:
        alert = ("<div class=alerts><div class=alert>"
                 f"<b>{blind} tin không chấm được</b>"
                 "<span>không tách được yêu cầu nào từ mô tả — "
                 "tin quá ngắn, hoặc viết bằng văn xuôi</span></div></div>")

    return runtime.render(
        title="Score", active="/score", stream="score",
        note="Bước 2 — chấm độ khớp, rồi hỏi riêng: có đường vào không.",
        panels=[
            runtime.panel("Thống kê", alert + tiles
                          + "<div class=subhead>Cơ hội thật</div>"
                          + plot.spread(chances), span=2),
            runtime.panel("Phân bố điểm", plot.bars(hist, unit=" tin"), span=2),
            runtime.panel("Cài đặt", runtime.rows(settings)),
            runtime.panel("Debug", runtime.actions([
                ("Chấm lại tất cả", "rescore", "bỏ điểm cũ, chấm lại từ đầu"),
                ("Dựng lại từ raw", "", "chưa nối — bóc lại mô tả từ HTML gốc"),
            ])),
        ],
    )
