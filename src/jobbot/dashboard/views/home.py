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
    # Câu hay bị hỏi nhất: "không có phần kinh nghiệm làm việc à?". Có — nó
    # đọc thẳng từ CV bạn nhập (mục EXPERIENCE), thành các khối ở tab CV. Gõ
    # lại ở đây là đẻ hai nguồn cho cùng một sự thật.
    "nang_luc": "Nguyên liệu để chấm điểm và dựng CV. Thiếu thì chấm là đoán mò.",
    "kinh_nghiem": "Chỗ nhà tuyển dụng đọc đầu tiên. Mỗi câu bạn viết ở đây là "
                   "một câu có thể lên CV.",
    "project": "Khớp thì qua được bộ lọc, bằng chứng mới đưa bạn vào nhóm được gọi.",
    "danh_tinh": "Cần lúc dựng CV và điền đơn. Chưa tới đó thì để trống cũng được.",
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


def sheet(state: dict) -> str:
    """Chu trình dựng hồ sơ — MẢNH HTML cho tấm phủ, không phải cả trang.

    Nó không chiếm tab Home nữa: việc của nó chỉ có lúc đầu, mà tab Home là
    chỗ của bảng điều khiển pipeline. Cổng chưa mở thì tấm này tự bật lên khi
    vào app — đó là chỗ "bắt điền". Mở xong thì nó biến mất, bấm lại được từ
    tab Profile.
    """
    mo = state["gate_open"]
    ke = state["next"]

    if mo:
        gate = ("<div class='gate ok'><b>Hồ sơ đủ để chạy.</b> "
                "Sang tab Search bấm Chạy.</div>")
    else:
        thieu = " · ".join(esc(q["text"]) for q in state["gate_missing"])
        gate = (f"<div class='gate block'><b>Chưa chạy được gì.</b> "
                f"App cần đúng {len(state['gate_missing'])} câu này trước: "
                f"{thieu}</div>")

    if state["answered"] == 0:
        nut = ("<div class=octa>"
               "<a class='mbtn apply big' href='/profile/import'>"
               "Nhập CV — app điền hộ →</a>"
               + (f"<a class=oalt href='{esc(ke['href'])}'>hoặc tự gõ</a>"
                  if ke else "")
               + "</div>"
               "<p class=omeo>Máy đọc CV rồi ĐỀ XUẤT từng ô — không ô nào được "
               "ghi vào cho tới khi bạn tick duyệt. Riêng <b>quyền làm việc</b> "
               "máy cố tình không đoán: CV không nói, mà đoán sai thì hỏng cả "
               "lá đơn.</p>")
    elif ke:
        nut = (f"<a class='mbtn apply big' href='{esc(ke['href'])}'>"
               f"Tiếp tục — {esc(ke['title'])} →</a>")
    else:
        nut = ""

    return ("<div class=sheethead>Hồ sơ của bạn</div>"
            "<div class=setupbody>"
            + _thanh(state["answered"], state["total"])
            + gate + nut
            + "<div class=blklist>"
            + "".join(_the(s, mo) for s in state["sections"])
            + "</div></div>")


def render(state: dict) -> str:
    """Tab Home — để trống, chờ bảng điều khiển pipeline (phương án B).

    Chu trình dựng hồ sơ ĐÃ RỜI khỏi đây: nó là tấm phủ, tự bật lên khi cổng
    chưa mở. Để nó nằm lì trên Home thì mỗi lần mở app đều phải nhìn một danh
    sách đã xong, mà tab Home thì không còn chỗ cho việc của chính nó.
    """
    cho = ("Trang này sẽ là bảng điều khiển pipeline — khúc nào tự chạy, "
           "khúc nào chờ bạn duyệt.")
    body = f"<div class=empty-box>{esc(cho)}</div>"
    # Cổng chưa mở -> bật tấm phủ ngay khi vào app. Chỉ đặt cờ ở ĐÂY, không
    # đặt trong layout: bật ở mọi trang thì nó thành cái pop-up đuổi theo.
    return page("Home", body, active="/",
                setup="" if state["gate_open"] else "/onboarding")
