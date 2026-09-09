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
from ..layout import score_bar
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
        f"<span class=jwhen>{esc(job['posted'])}</span></div></a>")


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


# ---------------------------------------------------------------- trang

def render(*, jobs: list[dict], flt, counts: dict, sieve: dict) -> str:
    return runtime.render(
        title="Search", active="/search", stream="search", journal="corner",
        note=f"Bước 1 — {counts.get('matched', 0):,} việc đang giữ · "
             f"hiện {len(jobs)} · hai cách tìm bù chỗ mù cho nhau.",
        # Cột trái RỘNG hơn chia đều: ô lưới có ô thẻ, hai nhóm ô tích và một
        # nút — chật quá thì thẻ xuống dòng lung tung và ô tích vỡ hàng.
        # Cột phải là kết quả, nên nó lấy phần lớn.
        # 1fr : 1.75fr — cột lưới rộng hơn hẳn kiểu chia đều ba cột (366px),
        # vì ô thẻ và hai nhóm ô tích cần chỗ để không vỡ hàng.
        cols=2, columns="minmax(360px, 1fr) 1.75fr",
        rows_tpl="1fr 150px",
        journal_at=(1, 2),          # góc dưới trái, dưới ô lưới lọc
        panels=[
            runtime.panel("Lưới lọc", _sieve(sieve), at=(1, 1)),
            # Danh sách kéo suốt hai hàng — chạm đáy màn hình.
            runtime.panel("Việc tìm được", _list(jobs, flt, counts),
                          rows=2, at=(2, 1)),
        ],
    )
