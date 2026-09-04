"""Sinh HTML từ schema. CHỈ VẼ — không có luật nghiệp vụ ở đây.

Thêm câu hỏi mới thì sửa profile/schema.py, file này không phải đụng tới.
Thấy mình sắp viết một cái `if question.id == "..."` ở đây -> viết nhầm chỗ.
"""

from __future__ import annotations

from html import escape as esc
from typing import Any

from ..profile.schema import LONGTEXT, MULTI, SINGLE, TEXT, ROUNDS, Question, Round

Answers = dict[str, Any]


def page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang=vi><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title>"
        "<link rel=stylesheet href='/static/app.css'></head>"
        f"<body><main>{body}</main></body></html>"
    )


def _selected(answers: Answers, qid: str) -> set[str]:
    value = answers.get(qid)
    if value is None:
        return set()
    return set(value) if isinstance(value, list) else {str(value)}


def _field(question: Question, answers: Answers) -> str:
    chosen = _selected(answers, question.id)
    parts: list[str] = []

    if question.kind in (SINGLE, MULTI):
        input_type = "radio" if question.kind == SINGLE else "checkbox"
        parts.append("<div class=opts>")
        for option in question.options:
            checked = " checked" if option.value in chosen else ""
            note = f"<span class=note>{esc(option.note)}</span>" if option.note else ""
            parts.append(
                f"<label class=opt><input type={input_type} name={esc(question.id)} "
                f"value='{esc(option.value)}'{checked}>"
                f"<span><span class=lbl>{esc(option.label)}</span>{note}</span></label>"
            )
        parts.append("</div>")

    elif question.kind == TEXT:
        current = esc(str(answers.get(question.id, "")))
        parts.append(
            f"<input class=txt type=text name={esc(question.id)} value='{current}' "
            f"placeholder='{esc(question.placeholder)}'>"
        )

    elif question.kind == LONGTEXT:
        current = esc(str(answers.get(question.id, "")))
        parts.append(
            f"<textarea class=txt rows=8 name={esc(question.id)} "
            f"placeholder='{esc(question.placeholder)}'>{current}</textarea>"
        )

    return "".join(parts)


def _question(question: Question, answers: Answers) -> str:
    optional = "" if question.required else "<span class=opt-tag>không bắt buộc</span>"
    why = f"<p class=why>{esc(question.why)}</p>" if question.why else ""
    return (
        f"<section class=q><h3>{esc(question.text)}{optional}</h3>"
        f"{why}{_field(question, answers)}</section>"
    )


def render_round(round_: Round, answers: Answers, done_ids: set[str]) -> str:
    steps = "".join(
        f"<li class='{'done' if r.id in done_ids else ('now' if r.id == round_.id else '')}'>"
        f"{esc(r.title.split(' — ')[0])}</li>"
        for r in ROUNDS
    )
    questions = "".join(_question(q, answers) for q in round_.questions)
    return page(
        round_.title,
        f"<ol class=steps>{steps}</ol>"
        f"<h1>{esc(round_.title)}</h1><p class=lead>{esc(round_.why)}</p>"
        f"<form method=post>{questions}"
        "<div class=actions><button type=submit>Lưu và tiếp tục</button>"
        "<a class=skip href='/profile'>Xem lại hồ sơ</a></div></form>",
    )


def _shown(question: Question, answers: Answers) -> str:
    value = answers.get(question.id)
    if value is None or value == "" or value == []:
        return "<em class=empty>— chưa trả lời —</em>"
    if question.options:
        labels = {o.value: o.label for o in question.options}
        values = value if isinstance(value, list) else [value]
        return " · ".join(esc(labels.get(v, v)) for v in values)
    text = str(value)
    if len(text) > 300:
        text = text[:300] + "…"
    return f"<span class=val>{esc(text)}</span>"


def render_summary(answers: Answers, versions: int, ingest_ready: bool) -> str:
    blocks: list[str] = []
    for round_ in ROUNDS:
        rows = "".join(
            f"<tr><th>{esc(q.text)}</th><td>{_shown(q, answers)}</td></tr>"
            for q in round_.questions
        )
        blocks.append(
            f"<h2>{esc(round_.title)} "
            f"<a class=edit href='/profile/{esc(round_.id)}'>sửa</a></h2>"
            f"<table class=sum>{rows}</table>"
        )

    if ingest_ready:
        gate = ("<div class='gate ok'>Vòng 1 đã xong — hệ thống được phép kéo tin về (M2).</div>")
    else:
        gate = (
            "<div class='gate block'>Vòng 1 chưa xong — chưa kéo tin nào về. "
            "<a href='/profile/dinh_vi'>Làm vòng 1</a></div>"
        )

    return page(
        "Hồ sơ",
        f"<h1>Hồ sơ của bạn</h1>"
        f"<p class=lead>Đã lưu {versions} phiên bản. Mỗi lần sửa tạo một phiên bản mới, "
        f"không ghi đè — hồ sơ là dữ liệu sống.</p>"
        f"{gate}{''.join(blocks)}",
    )
