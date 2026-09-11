"""CV — mọi bản hệ thống SẼ GỬI, xem trước khi gửi.

Tab này KHÔNG phải chỗ soạn CV. Bản gốc vẫn là `cv_text` trong Hồ sơ — chữ của
Vin, và luật gốc không đổi: máy CHỌN và SẮP XẾP, không viết mới (xem cv/build).

Đây là chỗ NHÌN TRƯỚC. Trước khi bước 5 gửi bất cứ thứ gì đi, Vin phải đọc
được mọi bản sẽ đi ra ngoài, trên một trang.

Vì sao gộp bản trùng: 101 tin đáng nộp, nhưng chỉ 29 bản khác nhau. Cấu trúc
CV cố định — 2 việc · 3 project · 2 học vấn · 1 chứng chỉ · 4 kỹ năng = 16 câu
— nên phần đổi chỉ là CÂU NÀO trong mỗi khối được chọn. Liệt kê đủ 101 dòng là
bắt đọc lại cùng một bản ba bốn lần.

CHỈ VẼ.
"""

from __future__ import annotations

from html import escape as esc
from urllib.parse import quote

from . import runtime

KIND_LABEL = {"experience": "việc", "project": "project", "education": "học vấn",
              "cert": "chứng chỉ", "skill": "kỹ năng", "summary": "tóm tắt"}


def _row(index: int, ver: dict) -> str:
    jobs = ver["jobs"]
    where = ", ".join(dict.fromkeys(j["company"] for j in jobs[:3]))
    more = f" +{len(jobs) - 3}" if len(jobs) > 3 else ""

    # CHỈ hiện câu RIÊNG của bản này. Hiện cấu trúc (2 việc · 3 project…) thì
    # cả 29 dòng in ra y hệt nhau, vì ngân sách mỗi phần là cố định.
    only = "".join(f"<div class=cvonly>{esc(line)}</div>" for line in ver["only"])

    miss = "".join(f"<span class=cvmiss>{esc(m)}</span>" for m in ver["missing"][:6])
    if len(ver["missing"]) > 6:
        miss += f"<span class=cvmiss>+{len(ver['missing']) - 6}</span>"

    best = max(jobs, key=lambda j: j["score"] or 0)
    return (
        f"<a class=cvrow href='/jobs/{best['id']}/cv'>"
        f"<div class=cvn>#{index}<span>{len(jobs)} tin</span></div>"
        f"<div class=cvmain>"
        f"<div class=cvwho><b>{esc(where)}</b>{more}</div>"
        f"{only or '<div class=cvonly muted>— không câu nào riêng —</div>'}"
        f"{f'<div class=cvgap>JD đòi mà CV không nói được: {miss}</div>' if miss else ''}"
        f"</div>"
        f"<div class=cvact><span class=cvscore>{best['score']}</span>"
        f"<button class='mbtn tiny' data-post='/cv/pdf'"
        f" data-arg='{best['id']}' onclick='event.preventDefault()'>PDF</button>"
        f"<span class=muted>xem →</span></div></a>")


def _list(data: dict) -> str:
    versions = data["versions"]
    if not versions:
        return ("<div class=empty-box>chưa có tin nào đáng nộp — chạy Search "
                "trước, hoặc nới lưới lọc</div>")

    lines = versions[0]["lines"]
    core = data["core"]
    gaps = "".join(f"<span class=cvmiss>{esc(g)}</span>" for g in data["gaps"][:14])

    # Nói thẳng mức may đo thật. "29 bản khác nhau" nghe như nhiều, nhưng
    # 14/16 câu giống hệt nhau ở mọi bản — chỉ 2 câu đổi theo JD.
    head = (f"<div class=gapnote><b>{len(versions)}</b> bản cho "
            f"<b>{data['jobs']}</b> tin đáng nộp. Nhưng <b>{core}/{lines}</b> câu "
            f"giống hệt nhau ở mọi bản — chỉ <b>{lines - core}</b> câu đổi theo JD. "
            f"Dưới đây mỗi dòng chỉ in phần RIÊNG của bản đó.</div>")
    if gaps:
        head += (f"<div class=cvgaps>Hồ sơ KHÔNG nói được câu nào về: {gaps}"
                 f"<span class=muted>— đây là chỗ project mới nên nhắm</span></div>")

    head += (f"<div class=allpdf>"
             f"<button class='mbtn apply' data-post='/cv/pdf/all'>"
             f"In tất cả {len(versions)} bản ra PDF</button>"
             f"<span class=muted>~{round(3 + 1.8 * len(versions))} giây · "
             f"một tệp mỗi bản, đặt tên theo công ty · tiến độ ở nhật ký</span>"
             f"</div>")
    return head + "<div class=vlist>" + "".join(
        _row(i, v) for i, v in enumerate(versions, 1)) + "</div>"


def render(*, versions: list[dict], jobs: int, gaps: list[str],
           core: int = 0, blocks: list[dict] | None = None) -> str:
    data = {"versions": versions, "jobs": jobs, "gaps": gaps, "core": core}
    blocks = blocks or []
    words = sum(len(b["lines"]) for b in blocks)
    return runtime.render(
        title="CV", active="/cv", stream="score", journal="corner",
        note=f"{words} câu nguyên liệu → {len(versions)} bản cho {jobs} tin. "
             f"Kho câu là TRẦN của cả hệ thống: muốn CV trúng hơn thì viết "
             f"thêm khối, không phải chọn khéo hơn.",
        cols=2, columns="minmax(360px, 1fr) 1.6fr",
        rows_tpl="1fr 150px", journal_at=(1, 2),
        panels=[
            runtime.panel("Khối", _blocks(blocks, gaps), at=(1, 1)),
            runtime.panel("Bản sẽ gửi", _list(data), rows=2, at=(2, 1)),
        ],
    )


# ------------------------------------------------------------ soạn khối

KIND_TAG = {"experience": "việc", "project": "project"}


def _blocks(blocks: list[dict], gaps: list[str]) -> str:
    """Kho nguyên liệu, xếp theo VỚI TỚI BAO NHIÊU TIN.

    Cột đó là cả câu chuyện: khối 0 tin lên CV vì có ô trống phải lấp, không
    vì nó chứng minh được gì.
    """
    rows = ""
    for b in blocks:
        skills = "".join(f"<span class=sk>{esc(s)}</span>" for s in b["skills"][:5])
        dead = " dead" if b["reach"] == 0 else ""
        rows += (
            f"<a class='blk{dead}' href='#' data-settings="
            # quote(), KHÔNG phải esc(): esc() là để CHỮ hiện an toàn trong
            # HTML, còn đây là THAM SỐ URL. Tiêu đề "Research & Development"
            # thoát HTML thành "Research &amp; Development" — dấu & vẫn cắt
            # tham số, và trang mở ra một khối khác hoặc khối rỗng.
            f"'/cv/block?title={quote(b['title'], safe='')}'>"
            f"<div class=blkmain>"
            f"<div class=blkhead><b>{esc(b['title'][:44])}</b>"
            f"<span class=blkkind>{esc(KIND_TAG.get(b['kind'], b['kind']))}</span></div>"
            f"<div class=blktags>{skills or '<span class=muted>không kỹ năng nào</span>'}</div>"
            f"</div>"
            f"<div class=blkreach><b>{b['reach']}</b><span>tin</span>"
            f"<i>{len(b['lines'])} câu</i></div></a>")

    aim = "".join(f"<span class=cvmiss>{esc(g)}</span>" for g in gaps[:8])
    return (
        f"<div class=gapnote>Xếp theo <b>số tin khối đó với tới</b>. "
        f"Khối <b>0 tin</b> đang chiếm chỗ chứ không chứng minh gì.</div>"
        f"<div class=blklist>{rows}</div>"
        f"<div class=blkfoot>"
        f"<button class='mbtn apply' data-settings='/cv/block?title='>+ Khối mới</button>"
        f"<div class=blkaim>nhắm vào chỗ hồ sơ đang câm: {aim}</div></div>")


def edit(block: dict | None, gaps: list[str]) -> str:
    """Mảnh HTML cho tấm phủ: soạn một khối.

    Ghi thẳng vào `cv_text` — MỘT nguồn sự thật. Không dựng bảng khối riêng:
    hai kho thì phải ngồi giữ chúng khớp nhau, đúng cái bệnh vừa chữa xong ở
    tầng chấm điểm và tầng dựng CV.
    """
    b = block or {"kind": "project", "title": "", "meta": "", "lines": [],
                  "skills": [], "reach": 0}
    boxes = "".join(
        f"<textarea class=cvdraft name=line rows=2>{esc(l)}</textarea>"
        for l in b["lines"] + ["", ""])
    kinds = "".join(
        f"<option value='{k}'{' selected' if k == b['kind'] else ''}>{esc(v)}</option>"
        for k, v in KIND_TAG.items())
    aim = "".join(f"<span class=cvmiss>{esc(g)}</span>" for g in gaps[:10])

    return (
        "<form class=setform method=post action='/cv/block'>"
        f"<h3>{'Sửa khối' if block else 'Khối mới'}</h3>"
        "<div class=safe>Mỗi câu ở đây là một câu có thể lên CV. Câu nào không "
        "chứng minh được gì thì không tin nào với tới — nhưng câu nói về QUY MÔ "
        "hay VẾT XƯỚC vẫn đáng viết, chúng thuyết phục theo cách khác.<br>"
        f"Đang câm ở: {aim}</div>"
        f"<input type=hidden name=was value='{esc(b['title'])}'>"
        f"<label class=slab>Loại</label><select name=kind>{kinds}</select>"
        "<label class=slab>Tên khối</label>"
        f"<input class=dfthead type=text name=title value='{esc(b['title'])}'>"
        "<label class=slab>Ngày tháng / tổ chức<span>để trống nếu là project</span></label>"
        f"<input class=dfthead type=text name=meta value='{esc(b['meta'])}'>"
        f"<label class=slab>Câu<span>mỗi ô một câu · ô trống thì bỏ qua</span></label>"
        f"{boxes}"
        "<div class=setfoot>"
        "<button class='mbtn apply' type=submit>Lưu vào CV gốc</button>"
        + (f"<button class='mbtn kill' type=submit name=kill value=1>Xoá khối"
           f"</button>" if block else "")
        + "<span class=applynote>ghi thẳng vào hồ sơ · mọi bản CV dựng lại từ đó"
        "</span></div>"
        + (f"<div class=forced>Khối này hợp với <b>{b['reach']}</b> tin. "
           f"Không hợp tin nào thì xoá đi cho sạch — giữ lại chỉ làm CV gốc "
           f"bẩn thêm.</div>" if block and b["reach"] == 0 else "")
        + "</form>")


# --------------------------------------------------- project xong -> dòng CV

def draft(row: dict, data: dict, lines: list[str], head: str) -> str:
    """Mảnh HTML: mấy dòng đề xuất, để Vin SỬA rồi mới đồng ý.

    Không tự dán vào CV. Thứ lên CV là thứ Vin phải bảo vệ được trong phòng
    phỏng vấn — nên nó phải đi qua mắt Vin, và phải sửa được ngay tại chỗ.
    """
    if not data:
        return ("<div class=setform><h3>Chưa có số để nói</h3>"
                "<div class=safe>Repo này chưa có <code>result.json</code>. "
                "Chạy <code>make run</code> trong "
                f"<code>{esc(row.get('link') or '?')}</code> rồi quay lại — "
                "mỗi dòng đề xuất đều phải dựng từ một con số mã của bạn vừa "
                "in ra, không phải từ chữ máy tự nghĩ.</div></div>")

    boxes = "".join(
        f"<textarea class=cvdraft name=line rows=3>{esc(line)}</textarea>"
        for line in lines)
    return (
        "<form class=setform method=post action='/cv/draft'>"
        f"<h3>Đưa project #{row['id']} vào CV</h3>"
        "<div class=safe>Mọi con số dưới đây đọc từ <code>result.json</code> — "
        "chính mã của bạn vừa in ra. Máy CHÉP LẠI, không nghĩ hộ. "
        "<b>Sửa cho ra giọng của bạn trước khi đồng ý</b>: thứ lên CV là thứ "
        "bạn phải bảo vệ được khi bị hỏi.</div>"
        f"<input type=hidden name=id value='{row['id']}'>"
        "<label class=slab>Tên khối<span>kèm link repo công khai nếu đã có</span></label>"
        f"<input class=dfthead type=text name=head value='{esc(head)}'>"
        "<label class=slab>Ba dòng<span>làm gì · kỷ luật giữ số cho thật · "
        "chỗ yếu. Bỏ trống một ô là bỏ dòng đó.</span></label>"
        f"{boxes}"
        "<div class=setfoot>"
        "<button class='mbtn apply' type=submit>Thêm vào CV gốc</button>"
        "<span class=applynote>ghi thẳng vào mục SELECTED PROJECTS của hồ sơ · "
        "mọi bản CV sẽ dựng lại từ đó</span></div></form>")
