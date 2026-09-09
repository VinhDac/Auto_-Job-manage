"""Search — bước 1, đi lấy tin về. Tab có thời gian chạy.

Ô "Hiệu suất nguồn" là ô quan trọng nhất ở đây: nó trả lời câu "nguồn nào
đáng giữ". Tỉ lệ thấp KHÔNG tự động nghĩa là nguồn kém — greenhouse phải tải
cả board rồi mới lọc nên tỉ lệ 2% là bình thường, còn arbeitnow tỉ lệ 0.1% vì
sai hẳn thị trường. Nên cột "tải về" và cột "dùng được" phải đứng cạnh nhau.
"""

from __future__ import annotations

from html import escape as esc

from . import runtime


def _yield_table(rows: list[dict]) -> str:
    if not rows:
        return "<div class=empty-box>chưa quét lần nào</div>"
    top = max(r["pulled"] for r in rows) or 1
    out = ""
    for row in rows:
        # Hai thanh chồng nhau: nền = tải về, thanh đậm = dùng được. Nhìn một
        # cái là thấy nguồn nào đang kéo về hàng nghìn tin để lấy vài tin.
        pulled = row["pulled"] / top * 100
        kept = row["kept"] / top * 100
        out += (f"<div class=yrow><span class=yname>{esc(row['name'])}</span>"
                f"<span class=ytrack><i class=yp style='width:{pulled:.1f}%'></i>"
                f"<i class=yk style='width:{kept:.1f}%'></i></span>"
                f"<b class=ynum>{row['kept']:,}<u>/{row['pulled']:,}</u></b>"
                f"<span class=yrate>{row['rate']}%</span></div>")
    return f"<div class=yields>{out}</div>"


def render(*, sources: list[dict], yields: list[dict], settings: list,
           chrome: dict) -> str:
    live_sources = [s for s in sources if s["found"]]
    failed = [s for s in sources if s["note"]]

    stats = runtime.tiles([
        (f"{sum(s['pulled'] for s in yields):,}", "Tin đã tải về", "mọi nguồn"),
        (f"{sum(s['kept'] for s in yields):,}", "Qua bộ lọc", "khớp chức danh"),
        (f"{len(live_sources)}", "Nguồn có tin", f"{len(failed)} đang lỗi"),
        ("mở" if chrome["alive"] else "tắt", "Chrome", "profile riêng"),
    ])

    alerts = ""
    if failed:
        # Alert nằm NGAY trong tab của việc hỏng, không dồn về một trang lỗi
        # chung — hỏng ở đâu thì báo ở đó.
        alerts = "<div class=alerts>" + "".join(
            f"<div class=alert><b>{esc(s['name'])}</b>"
            f"<span>{esc(s['note'])}</span></div>" for s in failed[:6]) + "</div>"

    return runtime.render(
        title="Search", active="/search", stream="search",
        note="Bước 1 — đi lấy tin về từ nguồn API và từ LinkedIn qua Chrome.",
        stats=alerts + stats,
        # Biểu đồ theo ngày đã có ở Home — lặp lại ở đây không thêm gì. Chỗ này
        # để dành cho câu hỏi riêng của tab Search: nguồn nào đáng giữ.
        chart_title="Hiệu suất nguồn — dùng được / tải về",
        chart=_yield_table(yields),
        settings=runtime.rows(settings),
        debug=runtime.actions([
            ("Quét ngay", "run", "chạy đủ một vòng, cả Chrome"),
            ("Chỉ nguồn API", "", "chưa nối — cần route riêng"),
            ("Thử một tin LinkedIn", "", "chưa nối"),
        ]),
    )
