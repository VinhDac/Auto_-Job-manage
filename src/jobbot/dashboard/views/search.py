"""Search — bước 1. MỘT tab, HAI cách tìm.

API board và Chrome không phải hai vai trò. Chúng là hai CÁCH TÌM khác nhau,
mù ở hai chỗ khác nhau, nên bù cho nhau:

    Chrome  bị chặn bởi CÂU HỎI      5/12 chức danh · 1 địa điểm · trần 200 tin
    API     bị chặn bởi DANH SÁCH    58 board · 30 board im lặng

Đo bằng gì: KHÔNG phải tỉ lệ. "greenhouse 1.9%" đọc ra là "nguồn kém", trong
khi chính nó mang về Jane Street, Point72, Jump Trading, Qube — 14 việc đáng
nộp mà LinkedIn không thấy cái nào. Hai bên chỉ trùng nhau 14/156 việc.

Thước đúng cho một cách tìm: ĐÓNG GÓP RIÊNG, và CÒN MÙ Ở ĐÂU.
"""

from __future__ import annotations

from html import escape as esc

from . import runtime


def _method(name: str, note: str, d: dict, blind: list[str],
            alerts: list[str] = ()) -> str:
    """Một cách tìm: nó mang về gì, nó đang hỏng gì, và nó còn mù ở đâu.

    Cảnh báo nằm TRONG thẻ của chính cách tìm đó. Để chung một khối phía trên
    thì đọc không ra nó thuộc bên nào — mà "78/192 tin đọc hỏng" là chuyện
    riêng của Chrome, API không liên quan.
    """
    agency = (f"<b class=warn-t>{d['agency']}</b>qua môi giới"
              if d["agency"] else "<b>0</b>qua môi giới")
    bad = "".join(f"<div class=malert>{a}</div>" for a in alerts)
    holes = "".join(f"<li>{b}</li>" for b in blind)
    return (
        f"<div class=method><div class=mhead><b>{esc(name)}</b>"
        f"<span class=muted>{esc(note)}</span></div>{bad}"
        f"<div class=mnums>"
        f"<span><b>{d['kept']}</b>việc giữ lại</span>"
        f"<span><b>{d['only']}</b>chỉ nó tìm ra</span>"
        f"<span><b class=hi-t>{d['worth']}</b>đáng nộp, riêng nó</span>"
        f"<span>{agency}</span></div>"
        f"<div class=mblind><u>còn mù</u><ul>{holes}</ul></div></div>")


def _watch(rows: list[dict]) -> str:
    """Từng công ty một. KHÔNG gộp thành một thanh 'greenhouse 1.9%' — gộp thì
    Point72 (9 việc) nằm lẫn với Betsson (0 việc, 131 lần kéo về)."""
    if not rows:
        return "<div class=empty-box>chưa theo dõi công ty nào</div>"
    out = ""
    for c in rows:
        who = ("<i class=own title='bạn tự chọn trong boards.toml'>◆</i>"
               if c["mine"] else "<i class=learn title='máy nhặt từ tin'>·</i>")
        # Công ty im lặng KHÔNG tô đỏ: im không phải hỏng, chỉ là chưa mở tuyển.
        # Tô đỏ thì 30 dòng đỏ rực và người đọc bỏ qua luôn cả dòng thật.
        out += (f"<div class='crow{'' if c['kept'] else ' quiet'}'>{who}"
                f"<span class=cname>{esc(c['slug'])}</span>"
                f"<span class=cats>{esc(c['ats'])}</span>"
                f"<b class=ckept>{c['kept'] or '—'}</b>"
                f"<span class=cpull>/{c['pulled']}</span>"
                f"<span class=cwhen>{esc(c['last_hit'])}</span></div>")
    return f"<div class=watch>{out}</div>"


def render(*, sources: list[dict], reach: dict, watch: list[dict],
           chrome_set: list, api_set: list, chrome: dict) -> str:
    ch, api = reach["chrome"], reach["api"]
    failed = [s for s in sources if s["note"]]

    blind_ch = [
        f"<b>{ch['titles_all'] - ch['titles_used']}</b> chức danh chưa bao giờ "
        f"tìm — {esc(', '.join(ch['titles_missed'][:3]))}…",
        f"chỉ một địa điểm: <b>{esc(ch['location'])}</b>",
        f"trần <b>{ch['cap']}</b> tin mỗi vòng",
    ]
    blind_api = [
        f"<b>{api['silent']}</b>/{api['boards']} board chưa từng ra việc nào",
        f"chỉ <b>{api['mine']}</b> board do bạn tự chọn, còn lại máy nhặt được",
        "nhà nào không dùng Greenhouse/Lever/Ashby thì không thấy",
    ]

    hurt = lambda li: [f"<b>{esc(s['name'])}</b> {esc(s['note'])}"
                       for s in failed
                       if (s["name"] == "linkedin") is li][:3]

    # Cạnh nhau, không xếp chồng: cả ô này tồn tại để SO SÁNH hai cách tìm,
    # mà so sánh thì phải nhìn được cả hai cùng lúc.
    body = (
        "<div class=methods>"
        + _method("Chrome — tìm theo từ khoá",
                  "cả thị trường · 8–16 phút · bị chặn được",
                  ch, blind_ch, hurt(True))
        + _method("API — theo dõi công ty",
                  "board của chính họ · ~30 giây · chưa hỏng",
                  api, blind_api, hurt(False))
        + "</div>"
        + f"<div class=overlap>Hai bên chỉ trùng nhau <b>{reach['both']}</b> việc"
          " — chúng gần như không tìm ra cùng một thứ.</div>")

    # Lịch quét là chuyện CHUNG của cả hai cách tìm, không của riêng bên nào —
    # nên nó nằm ở ô "Đang chạy", không nhét vào một trong hai bảng cài đặt.
    schedule = (f"<div class=runsched>Quét mỗi <b>{reach['every']}</b> phút · "
                f"tự quét <b>{'BẬT' if reach['autorun'] else 'TẮT'}</b></div>")

    return runtime.render(
        title="Search", active="/search", stream="search",
        note="Bước 1 — hai cách tìm, bù chỗ mù cho nhau.",
        run_span=1, run_extra=schedule,
        panels=[
            runtime.panel("Debug", runtime.actions([
                ("Quét ngay", "run", "chạy cả hai cách, kể cả Chrome"),
                ("Chỉ nguồn API", "", "chưa nối — cần route riêng"),
            ])),
            # Hai thẻ cách tìm cần hai hàng: nhét vào một hàng thì thẻ thứ hai
            # bị cắt cụt, mà đó mới là thẻ nói API đóng góp gì.
            runtime.panel("Hai cách tìm", body, span=2, rows=2),
            runtime.panel("Cài đặt · Chrome search", runtime.rows(chrome_set)),
            runtime.panel("Cài đặt · API search", runtime.rows(api_set)),
            runtime.panel(f"Công ty đang theo dõi — {api['boards']} board",
                          _watch(watch), span=2),
        ],
    )
