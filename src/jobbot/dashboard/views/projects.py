"""Projects — nhóm JD, project nào trả lời được nhóm nào, và chỗ nào còn trống."""

from __future__ import annotations

from html import escape as esc
from urllib.parse import quote

from .. import plot
from ..layout import badge, card, empty, h1, page
from . import runtime


def _groups(clusters: list) -> str:
    cards = []
    for cluster in clusters:
        if cluster.key == "other":
            continue
        gap = (badge("chưa project nào trả lời", "warn") if cluster.gap
               else badge(f"đã có: {cluster.covered_by[0]}", "ok"))
        jobs = "".join(
            f"<li><a href='/jobs/{j['id']}'>{esc(j['title'])}</a>"
            f"<span class=muted>{esc(j['company'])}</span>"
            f"<b>{j['score'] if j['score'] is not None else '—'}</b></li>"
            for j in sorted(cluster.jobs, key=lambda x: -(x["score"] or 0))[:5])
        more = (f"<li class=muted>+{len(cluster.jobs) - 5} tin nữa</li>"
                if len(cluster.jobs) > 5 else "")
        cards.append(card(
            f"<div class=grow><b>{esc(cluster.title)}</b>{gap}"
            f"<span class=spacer></span>"
            f"<span class=muted>{len(cluster.jobs)} tin</span></div>"
            f"<ul class=cjobs>{jobs}{more}</ul>"
            f"<a class=ghost href='/projects/{esc(quote(cluster.key))}'>"
            "Dựng một project nhỏ cho nhóm này →</a>", "proj"))
    return "".join(cards) or empty("Chưa có nhóm nào — cần thêm tin đã chấm điểm.")


def _mine(have: list) -> str:
    if not have:
        return empty("CV chưa có project nào.")
    return "".join(
        f"<div class=srow><span>{esc(b.title or 'chưa đặt tên')}</span>"
        f"<span class=muted>"
        + (", ".join(esc(t) for t in sorted(set(b.tags)))
           or "không nhận ra kỹ năng nào — phần mô tả có thể quá chung")
        + "</span></div>" for b in have)


def render(clusters: list, have: list, *, stats: dict, settings: list,
           sizes: list) -> str:
    gaps = stats["gaps"]
    tiles = runtime.tiles([
        (str(stats["clusters"]), "Nhóm JD", f"{stats['jobs']} tin"),
        (str(gaps), "Nhóm còn trống", "CV chưa trả lời được"),
        (str(stats["mine"]), "Project trên CV", "đọc từ CV"),
        (str(stats["waiting"]), "Đang chờ LLM", "yêu cầu chưa trả lời"),
    ])

    # Nhóm trống là VIỆC PHẢI LÀM, không phải con số trung tính — đó chính là
    # lý do bước 4 tồn tại.
    alert = ""
    if gaps:
        alert = ("<div class=alerts><div class=alert>"
                 f"<b>{gaps} nhóm chưa có project nào trả lời</b>"
                 "<span>mỗi nhóm là một dạng yêu cầu lặp lại nhiều tin — "
                 "một project đúng trọng tâm phủ được cả nhóm</span></div></div>")

    return runtime.render(
        title="Projects", active="/projects", stream="project",
        note="Bước 4 — gom tin theo thứ chúng thật sự đòi, rồi dựng một "
             "project nhỏ cho mỗi nhóm.",
        stats=alert + tiles
              + "<div class=subhead>Project đang có trên CV</div>" + _mine(have),
        chart_title="Nhóm JD — mỗi nhóm bao nhiêu tin",
        chart=plot.bars(sizes, unit=" tin", note="chưa có nhóm nào")
              + "<div class=subhead>Chi tiết từng nhóm</div>" + _groups(clusters),
        settings=runtime.rows(settings),
        debug=runtime.actions([
            ("Nghiên cứu công ty", "", "chưa nối — xem scripts/research.py"),
            ("Dựng lại nhóm", "", "chưa nối"),
        ]),
    )


STATE_NOTE = {
    "ok": ("brief ready", "ok"),
    "pending": ("waiting on Claude", "warn"),
    "no_llm": ("no LLM configured", "warn"),
    "not_enough": ("not enough postings to design from", "muted"),
    "all_rejected": ("every candidate failed the checks", "warn"),
    "unreadable": ("answer was not readable", "warn"),
}


def render_brief(cluster, findings, outcome) -> str:
    """Một đề bài project cho một nhóm JD — kèm TOÀN BỘ đường đi tới nó."""
    label, kind = STATE_NOTE.get(outcome.state, (outcome.state, ""))

    web = "".join(
        f"<div class=srow><span>{esc(n.company)}</span>"
        f"<span class=muted>{esc(n.what_they_do[:150])}</span></div>"
        for n in findings.web_notes) or (
        "<div class=muted>No company sites read yet — run the research pass.</div>")

    needs = "".join(f"<li>{esc(text)} <b>{n} postings</b></li>"
                    for text, n in findings.core_needs[:6])
    research = card(
        f"<b>What these {findings.jobs} postings actually ask for</b>"
        f"<ul class=changes>{needs or '<li>nothing repeated clearly</li>'}</ul>"
        f"<div class=note>Concepts they name: "
        f"{esc(', '.join(k for k, _ in findings.concepts[:8]) or '—')}</div>"
        f"<div class=note>Data sources they name: "
        f"{esc(', '.join(k for k, _ in findings.data_named[:5]) or 'none')}</div>")

    sites = card("<b>Read from the companies&#39; own sites</b>"
                 "<div class=muted style='margin-bottom:6px'>Job ads are written by "
                 "recruiters and copy each other. This is what the firms say themselves."
                 "</div>" + web)

    body = ""
    if outcome.chosen:
        b, s = outcome.chosen, outcome.chosen_score
        steps = "".join(f"<li>{esc(x)}</li>" for x in b.method)
        bars = "".join(
            f"<div class=bdrow><span class=bdl>{esc(k)}</span>"
            f"<span class=bdtrack><span class=bdfill style='width:{v*100:.0f}%'></span></span>"
            f"<b>{v:.2f}</b></div>" for k, v in s.parts.items())
        body = card(
            f"<h4 class=cvsec>The question</h4><p>{esc(b.question)}</p>"
            f"<h4 class=cvsec>Why it answers this cluster</h4>"
            f"<p class=muted>{esc(b.answers_jd)}</p>"
            f"<h4 class=cvsec>Data</h4>"
            f"<p><a href='{esc(b.dataset_url)}'>{esc(b.dataset)}</a>"
            f"<span class=muted> — fetched and inspected, not just pinged</span></p>"
            f"<h4 class=cvsec>Method</h4><ul class=cvlist>{steps}</ul>"
            f"<h4 class=cvsec>The number</h4><p>{esc(b.measure)}</p>"
            f"<h4 class=cvsec>Size</h4><p>{b.days:g} days · {esc(b.deliverable)}</p>"
            f"<h4 class=cvsec>Score {s.total:.0f}/100</h4><div class=bd>{bars}</div>",
            "cvpaper")

    rejected = "".join(
        f"<div class=qrow><span class=qbody><span class=qhead>"
        f"{badge(f'{sc.total:.0f}', 'muted')}<b>{esc(br.question[:90] or '(no question)')}</b>"
        f"</span>" + "".join(
            f"<span class='risk risky'>{esc(p.field)}: {esc(p.why)}</span>"
            for p in probs[:3])
        + "".join(f"<span class='risk risky'>data: {esc(d)}</span>" for d in dprobs[:2])
        + "</span></div>"
        for br, probs, dprobs, sc in outcome.rejected[:4])

    return page(
        f"Brief — {cluster.title}",
        "<a class=back href='/projects'>← Projects</a>"
        + h1(f"Project brief · {cluster.title}",
             "Seven stages: target, research, generate four, hard checks, "
             "inspect the data, rank, choose.")
        + f"<div class=chiprow>{badge(label, kind)}"
          f"<span class=muted>{esc(outcome.why)}</span></div>"
        + "<h2>1 · Research</h2>" + research + sites
        + "<h2>2 · Chosen brief</h2>"
        + (body or empty("Nothing passed the checks yet."))
        + ("<h2>3 · Rejected, and why</h2>"
           "<p class=lead>Kept on purpose — the reasons say what this cluster is "
           "missing, or where the rules are too tight.</p>"
           f"<div class=qlist>{rejected}</div>" if rejected else ""),
        active="/projects", status="Running")


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
