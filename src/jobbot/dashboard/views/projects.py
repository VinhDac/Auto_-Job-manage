"""Projects — bước 4. Ba ô, ba câu hỏi. Giống hệt Search.

    KHOẢNG TRỐNG   còn thiếu bằng chứng cho kỹ năng nào  (ô trái, có nút Dựng)
    KHO            đã tích được những gì                  (ô phải, cao nhất)
    NHẬT KÝ        máy đang làm gì                        (góc dưới trái, dẹt)

Vì sao trục là KỸ NĂNG chứ không phải nhóm JD: xem projects/inventory.py.

Vì sao có kho: một project mất 2-3 ngày. Trước đây pipeline sinh đề bài, vẽ ra
màn hình rồi VỨT — mỗi lần mở trang chạy lại cả bảy chặng từ đầu. Đo được
09/09: 9 lần hỏi LLM, 4 câu trả lời, cả 4 thuộc một nhóm ma đã biến mất. Không
có gì tích lại. Giờ đề bài nào qua được kiểm thì thành một dòng, nằm đó.

CHỈ VẼ.
"""

from __future__ import annotations

from html import escape as esc

from ..layout import h1, page
from . import runtime
from ...projects.inventory import (DANG_LAM, DE_BAI, MIN_DEMAND,
                                   STATE_LABEL, XONG)

# Bậc tiếp theo của mỗi trạng thái — một nút, không phải ba nút chọn.
NEXT = {DE_BAI: (DANG_LAM, "Bắt đầu"), DANG_LAM: (XONG, "Xong"), XONG: ("", "")}


# ------------------------------------------------------------ khoảng trống

def _gap_row(cell: dict, most: int, scored: int) -> str:
    """Một kỹ năng: bao nhiêu tin đòi · ngành nào đòi · đang đứng ở đâu.

    BA trạng thái, không phải hai. Gộp "đã làm xong" với "mới có đề bài" thì
    bấm Dựng mười lăm lần là lưới sạch bong mà chưa viết dòng code nào.
    """
    width = round(100 * cell["demand"] / most) if most else 0
    tags = "".join(f"<span class=ind>{esc(i)}</span>"
                   for i in cell["industries"][:3])

    if cell["covered"]:
        where = "hồ sơ" if cell["by"] is None else f"#{cell['by']}"
        state = "done"
        act = (f"<span class=gothave title='đã có bằng chứng thật'>"
               f"✓ {esc(where)}</span>")
    elif cell["planned"]:
        pid, pstate = cell["planned"]
        state = "doing"
        act = (f"<span class=gotplan title='đã nhận làm, chưa có bằng chứng'>"
               f"◐ {esc(STATE_LABEL.get(pstate, pstate))} #{pid}</span>")
    else:
        state = "open"
        act = (f"<button class='mbtn tiny' data-post='/api/project/build'"
               f" data-arg='{esc(cell['skill'])}'>Dựng</button>")

    return (f"<div class='gaprow {state}'>"
            f"<div class=gapmain><div class=gaphead>"
            f"<b>{esc(cell['skill'])}</b>"
            f"<span class=gapn>{cell['demand']}<i>/{scored}</i> tin</span></div>"
            f"<div class=gaptrack><i style='width:{width}%'></i></div>"
            f"<div class=gapind>{tags or '<span class=muted>—</span>'}</div>"
            f"</div><div class=gapact>{act}</div></div>")


def _gaps(grid: list[dict], scored: int) -> str:
    if not grid:
        # Hai lý do khác nhau, nói cả hai: chưa quét lần nào, hoặc quét rồi mà
        # chưa kỹ năng nào đủ đông tin để đáng bỏ 2-3 ngày.
        return (f"<div class=empty-box>chưa đo được gì — hoặc chưa có tin nào "
                f"được chấm điểm, hoặc chưa kỹ năng nào đủ {MIN_DEMAND} tin "
                f"đòi. Chạy Search trước.</div>")
    most = max(c["demand"] for c in grid)
    done = sum(1 for c in grid if c["covered"])
    doing = sum(1 for c in grid if c["planned"] and not c["covered"])
    return (f"<div class=gapnote><b>{len(grid) - done - doing}</b> chưa ai đụng"
            f" · <b>{doing}</b> đang làm · <b>{done}</b> đã có bằng chứng."
            f" Số tin đòi trên <b>{scored}</b> tin đã chấm điểm.</div>"
            + "<div class=gaplist>"
            + "".join(_gap_row(c, most, scored) for c in grid) + "</div>")


def _queue(waiting: list[dict]) -> str:
    """Hàng đợi LLM — chỗ RA, thứ trước giờ chưa có.

    llm.ask() xếp yêu cầu vào bảng và llm.answer_request() lấy ra, nhưng KHÔNG
    chỗ nào trong giao diện gọi cái thứ hai: 5 yêu cầu treo từ 07/09 không ai
    trả lời được. Hàng đợi chỉ có đường vào thì nó là cái hố, không phải hàng đợi.
    """
    if not waiting:
        return ""
    dead = sum(1 for r in waiting if r.get("stale"))
    items = ""
    for req in waiting:
        # Khoá theo nhóm cũ thì trả lời cũng vô ích — nói thẳng ra chỗ đó,
        # đừng để người dùng ngồi chép prompt rồi công cốc.
        if req.get("stale"):
            items += (
                f"<div class='lqitem old'><span>{esc(req['purpose'])}</span>"
                f"<span class=lqwhen>nhóm cũ · không còn dùng</span></div>")
            continue
        items += (
            f"<details class=lqitem><summary>{esc(req['purpose'])}"
            f"<span class=lqwhen>{esc(req.get('age') or '')}</span></summary>"
            f"<div class=lqbody>"
            f"<label class=lqlab>1 · bấm vào ô dưới để chọn hết, chép sang Claude</label>"
            f"<textarea class=lqprompt readonly rows=6"
            f" onclick='this.select()'>{esc(req['prompt'])}</textarea>"
            f"<form method=post action='/api/llm/answer'>"
            f"<input type=hidden name=id value='{req['id']}'>"
            f"<label class=lqlab>2 · dán câu trả lời vào đây</label>"
            f"<textarea class=lqanswer name=text rows=4"
            f" placeholder='dán nguyên câu trả lời, kể cả phần JSON'></textarea>"
            f"<button class='mbtn apply' type=submit>Nhận câu trả lời</button>"
            f"</form></div></details>")

    clean = (f"<form method=post action='/api/llm/drop' class=lqclean>"
             f"<button class='mbtn tiny' type=submit>Dọn {dead} cái cũ</button>"
             f"</form>" if dead else "")
    live = len(waiting) - dead
    head = (f"{live} đề bài đang chờ Claude trả lời" if live
            else f"{dead} yêu cầu cũ còn sót")
    return (f"<div class=lq><div class=lqhead>{head}{clean}</div>"
            f"{items}</div>")


def _project_row(row: dict) -> str:
    skills = "".join(f"<span class=sk>{esc(s)}</span>" for s in row["skills"])
    inds = "".join(f"<span class=ind>{esc(i)}</span>" for i in row["industries"])
    nxt, label = NEXT.get(row["state"], ("", ""))
    act = (f"<button class='mbtn tiny' data-post='/api/project/state'"
           f" data-arg='{row['id']}:{nxt}'>{esc(label)}</button>"
           if nxt else f"<a class=plink href='{esc(row['link'])}'>xem</a>"
           if row["link"] else "")

    return (f"<div class='prow {esc(row['state'])}'>"
            f"<div class=pstate>{esc(STATE_LABEL.get(row['state'], '?'))}</div>"
            f"<div class=pmain><div class=pq>{esc(row['question'])}</div>"
            f"<div class=ptags>{skills}{inds}</div></div>"
            f"<div class=pact>{act}</div></div>")


def _store(rows: list[dict], waiting: list[dict]) -> str:
    if not rows:
        body = ("<div class=empty-box>kho còn trống. Bấm <b>Dựng</b> ở một ô "
                "bên trái — đề bài nào qua được kiểm cứng và kiểm dữ liệu thì "
                "thành một dòng ở đây.</div>")
    else:
        done = sum(1 for r in rows if r["state"] == XONG)
        body = (f"<div class=gapnote>{len(rows)} đề bài · {done} đã xong</div>"
                + "<div class=plist>"
                + "".join(_project_row(r) for r in rows) + "</div>")
    return _queue(waiting) + body


# ------------------------------------------------------------------ trang

def render(*, grid: list[dict], store: list[dict],
           waiting: list[dict], scored: int = 0) -> str:
    open_cells = sum(1 for c in grid if not c["covered"] and not c["planned"])
    done = sum(1 for c in grid if c["covered"])
    return runtime.render(
        title="Projects", active="/projects", stream="project",
        journal="corner",
        note=f"Bước 4 — kho {len(store)} · {done} kỹ năng đã có bằng chứng · "
             f"{open_cells} chưa ai đụng. Chỉ project LÀM XONG mới tính là lấp ô.",
        cols=2, columns="minmax(360px, 1fr) 1.75fr",
        rows_tpl="1fr 150px",
        journal_at=(1, 2),
        panels=[
            runtime.panel("Khoảng trống", _gaps(grid, scored), at=(1, 1)),
            runtime.panel("Kho", _store(store, waiting), rows=2, at=(2, 1)),
        ],
    )


def render_page(job: dict, doc, gaps: list) -> str:
    def part(label: str, items: list[str], note: str = "") -> str:
        if not items:
            return (f"<h4 class=cvsec>{esc(label)}</h4>"
                    f"<div class=empty-box>{esc(note or 'nothing in your profile fits here yet')}</div>")
        body = "".join(f"<li>{esc(x)}</li>" for x in items)
        return f"<h4 class=cvsec>{esc(label)}</h4><ul class=cvlist>{body}</ul>"

    links = "".join(f"<li>{esc(l)}</li>" for l in doc.code) or "<li>—</li>"
    warn = "".join(
        f"<div class=note><b>{esc(t)}</b> {esc(why)}</div>" for t, why in gaps)

    covered = set(doc.speaks_to)
    chips = "".join(
        f"<span class='badge {'ok' if w in covered else 'warn'}'>{esc(w)}</span>"
        for w in doc.wanted) or "<span class=muted>—</span>"

    return page(
        f"Write-up — {job['title']}",
        f"<a class=back href='/jobs/{esc(job['id'])}'>← {esc(job['title'])}</a>"
        + h1("One-page write-up",
             f"For {doc.for_job}. Built from lines already in your profile — including "
             f"the ones the CV builder cut out. Nothing here is written by the system.")
        + f"<div class=cvpaper><div class=cvhead><div class=cvline>{esc(doc.project)}</div>"
          f"<div class=cvline>written for {esc(doc.for_job)}</div></div>"
        + part("The problem", doc.problem)
        + part("What I did", doc.method)
        + part("The number", doc.numbers,
               "No measurement yet — this is the part that decides whether an "
               "experienced reader believes any of it.")
        + part("What I gave up, and got wrong", doc.tradeoff,
               "Nothing here yet. A project with no scars reads as one that never ran.")
        + f"<h4 class=cvsec>Code</h4><ul class=cvlist>{links}</ul></div>"
        + "<h4 class=cvsec>What this posting asks for</h4>"
        + f"<div class=chiprow>{chips}</div>" + warn,
        active="/projects", status="Running")
