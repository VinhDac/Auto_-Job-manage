"""Cài đặt — MENU, không phải một tab.

Trả về một MẢNH HTML, không phải cả trang: live.js nạp nó vào tấm phủ khi bấm
nút bánh răng. Làm thành tab thì nó chiếm một chỗ trong thanh bên ngang hàng
với Search và Projects — trong khi nó không phải một việc, nó là mấy cái công
tắc mở ra chỉnh rồi đóng lại.

Chỉ ba núm. Thước để một thứ được vào đây:

    1. có nhiều hơn một câu trả lời đúng
    2. NGƯỜI DÙNG là người nên chọn
    3. đổi nó thì máy chạy khác đi

Thiếu một trong ba thì nó là thứ khác: một câu trả lời đúng -> đó là LỖI, sửa
code; máy tự báo về mình -> đó là SỐ ĐỌC VỀ; không đổi được cố ý -> đó là
RANH GIỚI AN TOÀN. Trang cũ có 18 dòng mà chỉ 2 dòng qua được thước này.

Ba núm này đều KHÔNG đụng tới phán quyết — đổi chúng chỉ đổi cách chạy, có
tác dụng từ lần quét sau. Thứ đổi phán quyết nằm ở ô Lưới lọc bên tab Search,
và ở đó nút Áp dụng nói rõ sẽ phán lại bao nhiêu tin.

CHỈ VẼ.
"""

from __future__ import annotations

from html import escape as esc

ENGINE_LABEL = {"none": "Không dùng",
                "claude_code": "Claude Code (phiên đang mở)",
                "api": "API (cần khoá)"}


def _num(name: str, value: int, low: int, high: int, unit: str) -> str:
    return (f"<input type=number name={name} value='{value}'"
            f" min={low} max={high} step=1><span class=unit>{esc(unit)}</span>")


def render(*, every: int, hours: tuple[int, int], engine: str,
           engines: list[str], status: list[tuple[str, str]],
           engine_forced: str = "") -> str:
    picks = "".join(
        f"<option value='{esc(e)}'{' selected' if e == engine else ''}>"
        f"{esc(ENGINE_LABEL.get(e, e))}</option>" for e in engines)

    rows = "".join(f"<div class=strow><span>{esc(k)}</span><b>{esc(v)}</b></div>"
                   for k, v in status)

    return (
        "<form class=setform method=post action='/settings'>"
        "<h3>Cài đặt</h3>"

        "<label class=srow><span>Quét lại mỗi</span>"
        + _num("every", every, 5, 1440, "phút") + "</label>"

        "<label class=srow><span>Chrome chạy từ</span>"
        + _num("from", hours[0], 0, 23, "giờ") + "</label>"
        "<label class=srow><span>… đến</span>"
        + _num("to", hours[1], 1, 24, "giờ") + "</label>"

        "<label class=srow><span>Máy LLM</span>"
        f"<select name=engine{' disabled' if engine_forced else ''}>{picks}"
        "</select></label>"
        + (f"<div class=forced>đang bị biến môi trường "
           f"<code>JOBBOT_LLM={esc(engine_forced)}</code> ép — bỏ biến đó đi "
           f"thì ô này mới có tác dụng</div>" if engine_forced else "")

        + "<div class=setfoot>"
        "<button class='mbtn apply' type=submit>Lưu</button>"
        "<span class=applynote>có tác dụng từ lần quét sau · "
        "không đụng tới điểm hay bộ lọc</span></div>"

        # Số máy tự báo về mình — KHÔNG phải cài đặt, nên tách hẳn xuống dưới
        # và nói rõ là chỉ để xem.
        f"<div class=sthead>Tình trạng · chỉ để xem</div><div class=stlist>{rows}</div>"

        # Ranh giới an toàn: không đổi được, cố ý. Chỉ giữ những câu CÓ TEST
        # đỡ lưng (xem tests/test_browser.py) — lời hứa không ai kiểm thì mục
        # dần mà không biết, đúng như REJECT_JS và shutdown() vừa rồi.
        "<div class=sthead>Ranh giới — không đổi được</div>"
        "<div class=safe>Chrome chạy bằng profile riêng, không đăng nhập tài "
        "khoản nào, chỉ đọc trang tuyển dụng công khai. Cookie chỉ bấm Từ chối. "
        "Bị chặn thì dừng và ghi nhật ký, không cãi lại.</div>"
        "</form>")
