"""Search — bước 1. Ba ô, ba câu hỏi.

    VIỆC TÌM ĐƯỢC   máy kiếm được gì cho tôi     (ô đứng, to nhất)
    LƯỚI LỌC        tôi đang hỏi cái gì           (ô trái, có nút Áp dụng)
    NHẬT KÝ         nó đang làm gì                (góc dưới trái, dẹt)

Hai loại lọc KHÁC HẲN nhau, cố ý để hai chỗ:

    lưới GIỮ/BỎ   ingest/filter.judge  →  đổi là phán lại 4.660 tin (1,1 giây)
                  nằm trong ô Lưới lọc, có nút Áp dụng vì nó tốn thật

    nút XEM       filters.JobFilter    →  chỉ đổi màn hình
                  nằm ngay trên đầu danh sách, bấm là đổi luôn

Nhét chung một nút Áp dụng thì hoặc "sắp theo điểm" cũng phải chờ Áp dụng
(vô lý), hoặc đổi chức danh — thứ phán lại cả bảng — dễ như đổi cách sắp xếp.

CHỈ VẼ.
"""

from __future__ import annotations

from html import escape as esc

from ..filters import BAND, CHANCE, SHOW, SORT, VIA
from ..layout import deck, score_bar
from . import runtime

# Badge nguồn: hai cách tìm mù ở hai chỗ khác nhau, nên nhìn dòng nào cũng
# biết ngay cách nào mang nó về. Tin cả hai cùng thấy thì hai badge.
FOUND_BY = {"chrome": ("⌕", "chrome", "tìm bằng từ khoá trên LinkedIn"),
            "api": ("◆", "api", "board tuyển dụng của chính công ty")}

CHANCE_TEXT = {"likely": ("đáng nộp", "ok"),
               "possible": ("có thể", ""),
               "unlikely": ("khó", "warn")}


# ---------------------------------------------------------------- danh sách

def _chips(name: str, options, current: str, flt) -> str:
    """Một hàng nút XEM. Bấm là đổi ngay — không đi qua nút Áp dụng."""
    return "".join(
        f"<a class='vchip{' on' if value == current else ''}'"
        f" href='{esc(flt.url(**{name: value}))}'>{esc(label)}</a>"
        for value, label in options)


def _row(job: dict) -> str:
    marks = "".join(
        f"<i class='src {k}' title='{esc(FOUND_BY[k][2])}'>"
        f"{FOUND_BY[k][0]}<b>{FOUND_BY[k][1]}</b></i>"
        for k in job["found_by"] if k in FOUND_BY)
    if job["via_agency"]:
        marks += ("<i class='src agency' title='tin do hãng môi giới đăng'>"
                  "⚠<b>môi giới</b></i>")

    chance = ""
    if job["realism"] in CHANCE_TEXT:
        text, kind = CHANCE_TEXT[job["realism"]]
        chance = (f"<span class='chance {kind}'"
                  f" title='{esc(job['realism_why'])}'>{text}</span>")

    # Tin bị bỏ thì LÝ DO là thứ đáng đọc nhất — đó là cách duy nhất soi được
    # lưới lọc có đang quá tay không.
    why = (f"<div class=dropwhy>bỏ vì {esc(job['drop_reason'])}</div>"
           if job["state"] == "dropped" and job["drop_reason"] else "")

    merged = (f"<span class=merged>+{job['merged'] - 1} nơi</span>"
              if job["merged"] > 1 else "")
    money = f" · {esc(job['salary'])}" if job["salary"] != "not stated" else ""
    score = (score_bar(job["score"]) if job["score"] is not None
             else "<span class=noscore>—</span>")

    return (
        f"<a class='jrow{' dropped' if job['state'] == 'dropped' else ''}'"
        f" href='/jobs/{esc(job['id'])}'>"
        f"<div class=jscore>{score}</div>"
        f"<div class=jmain><div class=jtitle>{esc(job['title'])}</div>"
        f"<div class=jsub><b>{esc(job['company'])}</b> · {esc(job['location'])}"
        f"{money}</div>{why}</div>"
        f"<div class=jtags>{chance}{marks}{merged}"
        f"<span class=jwhen>{esc(job['posted'])}</span>"
        # Nút Nộp: mở trang nộp bằng trình duyệt mặc định và ghi một dòng vào
        # bảng Quản lí.
        #
        # KHÔNG gắn onclick stopPropagation ở đây. Trình nghe [data-post] nằm ở
        # `document`, nên chặn lan truyền là giết luôn sự kiện trước khi nó tới
        # nơi — nút bấm không làm gì cả, mà cũng không báo lỗi. Bản thân trình
        # nghe đã gọi preventDefault(), đủ để thẻ <a> bao ngoài không nhảy trang.
        f"<button class='mbtn tiny' data-post='/api/apply'"
        f" data-arg='{esc(job['id'])}'>Nộp</button>"
        f"</div></a>")


def _list(jobs: list[dict], flt, counts: dict) -> str:
    head = ("<div class=vbar>"
            + _chips("show", [(v, f"{l} {counts.get(v, 0):,}") for v, l in SHOW],
                     flt.show, flt)
            + "</div><div class=vbar>"
            + _chips("chance", CHANCE, flt.chance, flt)
            + _chips("via", VIA, flt.via, flt)
            + "</div><div class=vbar>"
            + _chips("band", BAND, flt.band, flt)
            + _chips("sort", SORT, flt.sort, flt)
            + "</div>")
    if not jobs:
        return head + "<div class=empty-box>không có tin nào khớp</div>"
    return (head + "<div class=jlist>" + "".join(_row(j) for j in jobs)
            + "</div>" + _pager(flt, counts.get(flt.show, 0)))


def _pager(flt, total: int) -> str:
    """Không có nút sang trang thì 132 việc chỉ xem được 50 — 82 việc còn lại
    có tồn tại cũng như không."""
    # Lấy từ flt.limit() chứ KHÔNG import PER_PAGE: import theo giá trị thì
    # con số bị đóng băng lúc nạp module, test không đổi được để dựng ra
    # tình huống nhiều trang.
    per, _offset = flt.limit()
    pages = max(1, -(-total // per))
    if pages < 2:
        return ""
    prev = (f"<a class=vchip href='{esc(flt.url(page=flt.page - 1))}'>← trước</a>"
            if flt.page > 1 else "<span class='vchip off'>← trước</span>")
    nxt = (f"<a class=vchip href='{esc(flt.url(page=flt.page + 1))}'>sau →</a>"
           if flt.page < pages else "<span class='vchip off'>sau →</span>")
    return (f"<div class=pager>{prev}"
            f"<span class=muted>trang {flt.page}/{pages:,} · {total:,} việc</span>"
            f"{nxt}</div>")


# ---------------------------------------------------------------- lưới lọc

def _tags(titles: list[str]) -> str:
    """Ô thẻ: gõ chức danh rồi Enter là thêm, bấm × là bỏ.

    Mỗi thẻ mang theo một <input hidden name=job_titles>, nên form gửi lên một
    DANH SÁCH giá trị — không phải một khối chữ rồi server ngồi tách dòng.
    Khối chữ thì người dùng phải tự nhớ luật "mỗi dòng một cái", và một dòng
    trống hay một dấu phẩy thừa là ra chức danh rác.
    """
    chips = "".join(
        f"<span class=tag>{esc(t)}"
        f"<input type=hidden name=job_titles value='{esc(t)}'>"
        # type=button, nếu không bấm × là gửi luôn cả form
        f"<button type=button class=untag data-untag title='bỏ'>×</button>"
        f"</span>" for t in titles)
    return (f"<div class=tagbox data-tags>{chips}"
            "<input class=taginput type=text autocomplete=off"
            " placeholder='thêm chức danh…'></div>")


def _missed(missed: list[dict]) -> str:
    """Chức danh lưới đang bỏ sót mà trông như việc của Vin.

    Lưới là mấy chuỗi gõ tay: thiếu một chuỗi là mất cả loạt tin, và mất TRONG
    IM LẶNG. Đo ngày 10/09: `Quantitative Trader` bị bỏ chín lần, toàn ở Jane
    Street; 47 tin `machine learning` bị bỏ, mà ML là ô cầu cao nhất (56/178).

    Máy KHÔNG tự nới lưới — nới là đổi hồ sơ, và hồ sơ đổi thì cả bảng phải
    phán lại. Nó chỉ chỗ; bấm vào là thẻ rơi vào ô trên, rồi vẫn phải bấm
    Áp dụng như mọi thay đổi khác.
    """
    if not missed:
        return ""
    chips = "".join(
        f"<button type=button class=addtag data-addtag='{esc(m['title'])}'"
        f" title='{esc(', '.join(m['firms'][:3]))}'>"
        f"+ {esc(m['title'][:34])}<b>{m['n']}</b></button>" for m in missed)
    return (f"<div class=missed><div class=missedhead>"
            f"lưới đang bỏ sót — bấm để thêm</div>{chips}</div>")


def _sieve(sieve: dict) -> str:
    """Ô sửa lưới GIỮ/BỎ. FORM thật, không phải bảng đọc.

    Giá trị nằm trong HỒ SƠ — sửa ở đây là sửa hồ sơ, và nó đổi cả điểm (chức
    danh nằm trong công thức chấm). Phải ghi câu đó ra, không được im.
    """
    levels = "".join(
        f"<label class=tick><input type=checkbox name=seniority value='{esc(v)}'"
        f"{' checked' if v in sieve['seniority'] else ''}>{esc(l)}</label>"
        for v, l in sieve["seniority_options"])
    markets = "".join(
        f"<label class=tick><input type=checkbox name=markets value='{esc(v)}'"
        f"{' checked' if v in sieve['markets'] else ''}>{esc(l)}</label>"
        for v, l in sieve["market_options"])

    return (
        "<form class=sieve method=post action='/api/sieve'>"
        "<label class=slab>Chức danh nhắm tới<span>gõ rồi Enter để thêm · "
        "vừa là từ khoá gửi cho LinkedIn, vừa là điều kiện giữ tin</span></label>"
        + _tags(sieve["titles"])
        + _missed(sieve.get("missed") or [])
        + "<label class=slab>Cấp bậc nhận</label>"
        f"<div class=ticks>{levels}</div>"
        "<label class=slab>Thị trường<span>quyết định LinkedIn tìm ở đâu, "
        "và tin ở đâu thì được giữ</span></label>"
        f"<div class=ticks>{markets}</div>"
        # Nút phải nói TRƯỚC hậu quả. "Lưu" trống không thì người bấm không
        # biết mình vừa làm cả bảng phán lại từ đầu.
        "<div class=stick>"
        "<button class='mbtn apply' type=submit>Áp dụng</button>"
        f"<div class=applynote>phán lại <b>{sieve['total']:,}</b> tin đã lấy về"
        f" (~{sieve['seconds']} giây) · đây là <b>hồ sơ</b> của bạn, "
        "sửa ở đây đổi cả điểm</div></div>"
        "</form>")


def adjust(sieve: dict) -> str:
    """Mảnh cho tấm phủ ⚟ — LƯỚI SÀNG.

    Vì sao lưới sàng vào đây mà BỘ LỌC thì không: lọc (hiện/cơ hội/dải/sắp
    xếp) bấm vài giây một lần khi lướt danh sách, giấu vào menu là lướt chậm
    hẳn. Lưới sàng đổi vài tháng một lần, và mỗi lần đổi là phán lại toàn bộ
    tin trong kho. Khác nhau: LỌC thứ đang nhìn ≠ ĐỔI thứ máy đi thu về.
    """
    return f"<div class=sheethead>Điều chỉnh · Search</div>{_sieve(sieve)}"


# ---------------------------------------------------------------- trang

def render(*, jobs: list[dict], flt, counts: dict, sieve: dict,
           stage: dict | None = None) -> str:
    info = stage or {}
    return runtime.render(
        title="Search", active="/search", stream="search",
        # Thanh của KHÚC này: số liệu + nút chạy/dừng của chính nó. Hai nút
        # "Chạy ngay"/"Bật tự quét" trước đây nằm trên thanh toàn app nhưng
        # chỉ điều khiển đúng khúc này.
        bar=deck(
            "search", "Search",
            info.get("state", "chưa quét lần nào"),
            # vai -> màu: xem luật ở layout.deck()
            [(f"{counts.get('matched', 0):,}", "giữ", "stock"),
             (f"{info.get('worth', 0):,}", "đáng nộp", "act"),
             (f"{info.get('fresh', 0):,}", "mới", "new"),
             (len(jobs), "đang hiện", "view")],
            adjust="/adjust/search"),
        # Lưới sàng đã chuyển vào ⚟ nên cột trái hết việc. Danh sách — thứ
        # Vin thật sự đọc — lấy cả bề ngang. Nhật ký về dải dẹt dưới đáy.
        cols=1, journal="bottom",
        panels=[
            runtime.panel("Việc tìm được", _list(jobs, flt, counts), span=1),
        ],
    )
