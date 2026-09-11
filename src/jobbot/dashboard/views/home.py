"""Home — chu trình dựng hồ sơ. Đây là CỬA VÀO của app.

Trước đây trang này trống trơn: người dùng mới mở app ra, đáp xuống đây đầu
tiên, và không ai nói cho họ biết phải làm gì. Bốn tab kia đều đã biết chỉ
đường ("chạy Search trước", "còn thiếu ba câu") — chỉ mỗi cửa vào là im.

Trang này KHÔNG tự nghĩ ra luật nào. Nó đọc `live.onboarding()` — cùng cái
cổng mà Search và Profile đang đọc — rồi vẽ ra đường đi: phần nào xong, phần
nào chưa, bước tiếp theo là gì, bấm vào là tới thẳng chỗ điền.

Ba câu mở cổng, 35 câu là đủ. Nên trang chia làm hai giai đoạn:

    cổng CHƯA mở  -> chỉ có một việc: điền cho xong ba câu đó. Mọi thứ khác
                     trong app đều chưa chạy được, bày thêm chỉ làm nhiễu.
    cổng ĐÃ mở    -> danh sách này thành MENU "thêm cho mạnh": mỗi phần nói
                     rõ thêm nó thì app làm tốt thêm được gì.
"""

from __future__ import annotations

from html import escape as esc

from ..layout import page

# Thêm phần này thì app làm tốt thêm được gì — nói bằng hệ quả, không bằng
# tên trường. "Thêm kỹ năng" không thuyết phục ai; "chấm điểm hết đoán mò" thì có.
LOI = {
    "muc_tieu": "Không có phần này thì app không biết tìm gì — chưa quét được.",
    "rang_buoc": "Lọc ở đây rẻ hơn nhiều so với đọc rồi mới loại.",
    "nang_luc": "Nguyên liệu để chấm điểm và dựng CV. Thiếu thì chấm là đoán mò.",
    "danh_tinh": "Cần lúc dựng CV và điền đơn. Chưa tới đó thì để trống cũng được.",
    "project": "Chỗ hổng nào hồ sơ chưa nói được, project sẽ lấp.",
}


def _thanh(xong: int, tong: int) -> str:
    pc = round(xong * 100 / tong) if tong else 0
    return (f"<div class=obar><span style='width:{pc}%'></span></div>"
            f"<div class=obarnum><b>{xong}</b>/{tong} câu đã trả lời</div>")


def _the(s: dict, mo: bool) -> str:
    """Một phần hồ sơ. `mo` = cổng đã mở chưa — đổi câu chữ chứ không đổi luật."""
    if s["done"]:
        dau, lop, nut = "✓", " done", "Sửa"
    else:
        dau, lop, nut = "", "", ("Điền ngay" if s["required"] else "Thêm")

    nhan = ""
    if s["required"] and not s["done"]:
        nhan = "<span class='blkkind req'>BẮT BUỘC</span>"
    elif s["optional"]:
        nhan = "<span class=blkkind>tuỳ chọn</span>"

    # Cổng chưa mở thì chỉ phần bắt buộc được nói to; phần khác lùi lại.
    mo_nhat = " dim" if (not mo and not s["required"] and not s["done"]) else ""
    return (
        f"<a class='blk ostep{lop}{mo_nhat}' href='{esc(s['href'])}'>"
        f"<span class=blkmain>"
        f"<span class=blkhead><b>{dau} {esc(s['title'])}</b>{nhan}"
        f"<span class=ocount>{s['answered']}/{s['total']}</span></span>"
        f"<span class=osub>{esc(LOI.get(s['id'], s['why']))}</span></span>"
        f"<span class='mbtn tiny'>{nut}</span></a>")


def render(state: dict) -> str:
    mo = state["gate_open"]
    ke = state["next"]

    if mo:
        gate = ("<div class='gate ok'><b>Hồ sơ đủ để chạy.</b> "
                "Sang tab Search bấm Chạy — hoặc thêm bên dưới để app "
                "chấm điểm và viết CV sát hơn.</div>")
        loi_mo = ("Hồ sơ càng đầy, app càng ít phải đoán. Mỗi phần dưới đây "
                  "nói rõ thêm nó thì được gì.")
    else:
        thieu = " · ".join(esc(q["text"]) for q in state["gate_missing"])
        gate = (f"<div class='gate block'><b>Chưa chạy được gì.</b> "
                f"App cần đúng {len(state['gate_missing'])} câu này trước: "
                f"{thieu}</div>")
        loi_mo = ("Trước khi tìm được việc nào, app cần biết bạn muốn gì. "
                  "Ba câu là đủ để bắt đầu — phần còn lại thêm dần.")

    nut = ""
    if ke:
        nhan = "Bắt đầu" if state["answered"] == 0 else "Tiếp tục"
        nut = (f"<a class='mbtn apply big' href='{esc(ke['href'])}'>"
               f"{nhan} — {esc(ke['title'])} →</a>")

    body = (
        "<h1>Hồ sơ của bạn</h1>"
        f"<p class=lead>{loi_mo}</p>"
        + _thanh(state["answered"], state["total"])
        + gate + nut
        + "<h2 class=ohead>"
        + ("Thêm cho mạnh" if mo else "Các phần")
        + "</h2><div class=blklist>"
        + "".join(_the(s, mo) for s in state["sections"])
        + "</div>")
    return page("Home", body, active="/")
