"""Cài đặt — MENU, không phải một tab.

Trả về một MẢNH HTML, không phải cả trang: live.js nạp nó vào tấm phủ khi bấm
nút bánh răng. Làm thành tab thì nó chiếm một chỗ trong thanh bên ngang hàng
với Search và Projects — trong khi nó không phải một việc, nó là mấy cái công
tắc mở ra chỉnh rồi đóng lại.

Chỉ hai núm. Thước để một thứ được vào đây:

    1. có nhiều hơn một câu trả lời đúng
    2. NGƯỜI DÙNG là người nên chọn
    3. đổi nó thì máy chạy khác đi

Thiếu một trong ba thì nó là thứ khác: một câu trả lời đúng -> đó là LỖI, sửa
code; máy tự báo về mình -> đó là SỐ ĐỌC VỀ; không đổi được cố ý -> đó là
RANH GIỚI AN TOÀN. Trang cũ có 18 dòng mà chỉ 2 dòng qua được thước này.

Hai núm này đều KHÔNG đụng tới phán quyết — đổi chúng chỉ đổi cách chạy, có
tác dụng từ lần quét sau. Thứ đổi phán quyết nằm ở ô Lưới lọc bên tab Search,
và ở đó nút Áp dụng nói rõ sẽ phán lại bao nhiêu tin.

Ba TAB. Trước đây một cột dài 782px trong hộp cao 660px — phần "Làm lại từ
đầu" nằm dưới nếp gấp, phải cuộn mới thấy, mà không ai biết là có thể cuộn.
Chia tab thì mỗi tab vừa một màn, và hộp co lại đúng một hộp thoại nổi thay vì
một cột chạy gần hết chiều cao cửa sổ.

Chia theo VIỆC, không theo độ dài: thứ đổi được / thứ chỉ đọc / thứ phá huỷ.
Để việc phá huỷ chung màn với nhịp quét là sớm muộn cũng có người bấm nhầm.

CHỈ VẼ.
"""

from __future__ import annotations

from html import escape as esc

def _num(name: str, value: int, low: int, high: int, unit: str) -> str:
    return (f"<input type=number name={name} value='{value}'"
            f" min={low} max={high} step=1><span class=unit>{esc(unit)}</span>")


PACE_TEXT = [
    ("nhe", "Nhẹ nhàng", "4-7 giây mỗi tin · ít bị bóp nhất"),
    ("thuong", "Thường", "2,5-5 giây · mặc định"),
    ("nhanh", "Nhanh", "1,2-2,5 giây · gọi dày gấp đôi, dễ bị bóp hơn"),
]


def _nhip(pace: str) -> str:
    """Núm hiệu năng THẬT của vòng quét — và nó là núm ĐÁNH ĐỔI.

    Vì sao không phải "chạy mấy tab song song": N tab với nhịp P giống hệt 1
    tab với nhịp P/N — cùng số lượt gọi mỗi giây, cùng rủi ro bị bóp. Song
    song chỉ là cách viết phức tạp hơn của một con số nhỏ hơn, cộng thêm N cửa
    sổ Chrome ăn RAM và N chỗ có thể chết nửa chừng. Nên bày ra đúng cái thật
    sự đổi: nhịp.

    Nói thẳng cái ĐÁNH ĐỔI ngay trên màn hình. Một núm ghi "Nhanh" mà không
    nói nhanh bằng giá gì là núm mời người ta bấm rồi lãnh hậu quả.
    """
    nut = "".join(
        f"<label class=prow><input type=radio name=pace value='{esc(v)}'"
        f"{' checked' if v == pace else ''}>"
        f"<b>{esc(ten)}</b><span class=muted>{esc(ghi)}</span></label>"
        for v, ten, ghi in PACE_TEXT)
    return (f"<div class=sthead>Nhịp gọi LinkedIn</div>{nut}"
            "<div class=safe>Board công ty không đụng tới nhịp này — chúng là "
            "API công khai, mỗi board một lượt gọi. Nhịp chỉ áp cho LinkedIn, "
            "bên duy nhất app đang ở nhờ.</div>")


def render(*, every: int, hours: tuple[int, int],
           status: list[tuple[str, str]], pace: str = "thuong",
           reset_rows: int = 0, reset_files: int = 0, reset_mb: float = 0.0,
           reset_backup_dir: str = "") -> str:
    rows = "".join(f"<div class=strow><span>{esc(k)}</span><b>{esc(v)}</b></div>"
                   for k, v in status)

    chay = (
        "<form class=setform method=post action='/settings'>"
        "<label class=srow><span>Quét lại mỗi</span>"
        + _num("every", every, 5, 1440, "phút") + "</label>"
        "<label class=srow><span>Chrome chạy từ</span>"
        + _num("from", hours[0], 0, 23, "giờ") + "</label>"
        "<label class=srow><span>… đến</span>"
        + _num("to", hours[1], 1, 24, "giờ") + "</label>"
        + _nhip(pace) +
        "<div class=setfoot>"
        "<button class='mbtn apply' type=submit>Lưu</button>"
        "<span class=applynote>có tác dụng từ lần quét sau · "
        "không đụng tới điểm hay bộ lọc</span></div>"
        "</form>")

    # Số máy tự báo về mình — KHÔNG phải cài đặt, nên tách sang tab riêng và
    # nói rõ là chỉ để xem. Ranh giới an toàn ở cùng đây vì nó cũng không đổi
    # được; chỉ giữ những câu CÓ TEST đỡ lưng (xem tests/test_browser.py) —
    # lời hứa không ai kiểm thì mục dần mà không biết.
    tinh_trang = (
        f"<div class=stlist>{rows}</div>"
        "<div class=sthead>Ranh giới — không đổi được</div>"
        "<div class=safe>Chrome chạy bằng profile riêng, không đăng nhập tài "
        "khoản nào, chỉ đọc trang tuyển dụng công khai. Cookie chỉ bấm Từ chối. "
        "Bị chặn thì dừng và ghi nhật ký, không cãi lại.</div>")

    tab = [("chay", "Chạy", chay),
           ("xem", "Tình trạng", tinh_trang),
           ("lam-lai", "Làm lại",
            _lam_lai(reset_rows, reset_files, reset_mb, reset_backup_dir))]

    chips = "".join(
        f"<button class='stab{" on" if n == 0 else ""}' data-stab='{tid}'>"
        f"{esc(ten)}</button>" for n, (tid, ten, _) in enumerate(tab))
    panes = "".join(
        f"<div class='stpane{" on" if n == 0 else ""}' data-pane='{tid}'>{noi}</div>"
        for n, (tid, _, noi) in enumerate(tab))

    return (f"<div class=sheethead>Cài đặt</div>"
            f"<div class=stabs>{chips}</div>{panes}")


def _lam_lai(rows: int, files: int, mb: float, backup_dir: str) -> str:
    """Nút đưa app về trạng thái ban đầu.

    Hai chốt, cả hai đều do từng làm hỏng thật mà có:
      - phải gõ đúng chữ XOA rồi mới bấm được (server cũng kiểm lại, không
        tin mỗi phía trình duyệt);
      - nói TRƯỚC sẽ mất bao nhiêu, và nói trước sao lưu sẽ nằm ở đâu.
    """
    co = (f"{rows:,} dòng dữ liệu · {files} tệp · ~{mb} MB"
          if rows or files else "hiện đang trống")
    return (
        f"<div class=safe>Xoá sạch hồ sơ, tin đã quét, CV đã dựng, đơn đã "
        f"theo dõi, hộp thư đã nối và cả profile Chrome — đưa app về đúng lúc "
        f"mới cài. <b>Sẽ mất: {esc(co)}.</b><br>"
        f"Trước khi xoá, app tự gói tất cả vào một tệp .tar.gz ở "
        f"<code>{esc(backup_dir)}</code>. Gói hỏng thì KHÔNG xoá gì.</div>"
        "<div class=dangerrow>"
        "<input class=search id=resetword placeholder='gõ XOA để mở khoá' "
        "autocomplete=off spellcheck=false>"
        "<button class='mbtn kill' data-post='/api/reset' data-arg=''"
        " data-needword=resetword disabled>Xoá hết, làm lại</button>"
        "</div>")
