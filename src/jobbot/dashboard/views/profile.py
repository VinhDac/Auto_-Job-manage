"""Profile — sinh HTML từ schema. CHỈ VẼ, không có luật nghiệp vụ ở đây.

Thêm câu hỏi thì sửa profile/schema.py, file này không phải đụng tới.
Thấy mình sắp viết `if question.id == "..."` ở đây -> viết nhầm chỗ.
"""

from __future__ import annotations

from html import escape as esc
from typing import Any

from ...profile.schema import (
    LONGTEXT, MULTI, SINGLE, TEXT, SECTIONS, Question, Section, all_questions,
)
from ..layout import page

Answers = dict[str, Any]
OTHER_SUFFIX = "__other"


def _values(answers: Answers, qid: str) -> list[str]:
    value = answers.get(qid)
    if value is None or value == "":
        return []
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def _field(question: Question, answers: Answers) -> str:
    chosen = set(_values(answers, question.id))
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

        if question.allow_other:
            known = {o.value for o in question.options}
            extra = ", ".join(v for v in _values(answers, question.id) if v not in known)
            parts.append(
                f"<input class='txt other' type=text name='{esc(question.id)}{OTHER_SUFFIX}' "
                f"value='{esc(extra)}' placeholder='Add your own — separate with commas'>"
            )

    elif question.kind == TEXT:
        parts.append(
            f"<input class=txt type=text name={esc(question.id)} "
            f"value='{esc(str(answers.get(question.id, '')))}' "
            f"placeholder='{esc(question.placeholder)}'>"
        )

    elif question.kind == LONGTEXT:
        rows = 6 if question.placeholder.count("\n") < 3 else 8
        parts.append(
            f"<textarea class=txt rows={rows} name={esc(question.id)} "
            f"placeholder='{esc(question.placeholder)}'>"
            f"{esc(str(answers.get(question.id, '')))}</textarea>"
        )

    return "".join(parts)


def _question(question: Question, answers: Answers) -> str:
    tag = "<span class=req>required</span>" if question.required else ""
    why = f"<p class=why>{esc(question.why)}</p>" if question.why else ""
    return (
        f"<section class=q><h3>{esc(question.text)}{tag}</h3>"
        f"{why}{_field(question, answers)}</section>"
    )


def _steps(current_id: str, done_ids: set[str]) -> str:
    items = "".join(
        f"<li class='{'done' if s.id in done_ids else ''}"
        f"{' now' if s.id == current_id else ''}'>"
        f"<a href='/profile/{esc(s.id)}'>{esc(s.title)}</a></li>"
        for s in SECTIONS
    )
    return f"<ol class=steps>{items}</ol>"


def render_section(section: Section, answers: Answers, done_ids: set[str],
                   next_label: str) -> str:
    optional = "<span class=opt-tag>optional</span>" if section.optional else ""
    questions = "".join(_question(q, answers) for q in section.questions)
    return page(
        section.title,
        _steps(section.id, done_ids)
        + f"<h1>{esc(section.title)}{optional}</h1>"
        + f"<p class=lead>{esc(section.why)}</p>"
        + f"<form method=post>{questions}"
        + f"<div class=actions><button class=primary type=submit>{esc(next_label)}</button>"
        + "<a class=skip href='/profile'>Review profile</a></div></form>",
        active="/profile", status="Running",
    )


def _shown(question: Question, answers: Answers) -> str:
    values = _values(answers, question.id)
    if not values:
        return "<em class=empty>— not answered —</em>"
    if question.options:
        labels = {o.value: o.label for o in question.options}
        return " · ".join(esc(labels.get(v, v)) for v in values)
    text = values[0]
    return f"<span class=val>{esc(text if len(text) <= 300 else text[:300] + '…')}</span>"


def render_summary(answers: Answers, versions: int, missing_gate: list[str]) -> str:
    questions = all_questions()

    if missing_gate:
        names = " · ".join(esc(questions[q].text) for q in missing_gate)
        gate = (
            f"<div class='gate block'><b>Can't search yet.</b> Still missing: {names}. "
            "<a href='/profile/muc_tieu'>Fill these in</a></div>"
        )
    else:
        gate = "<div class='gate ok'><b>Ready to search.</b> The system may now pull postings (M2).</div>"

    blocks: list[str] = []
    for section in SECTIONS:
        filled = sum(1 for q in section.questions if _values(answers, q.id))
        optional = "<span class=opt-tag>optional</span>" if section.optional else ""
        rows = "".join(
            f"<tr><th>{esc(q.text)}</th><td>{_shown(q, answers)}</td></tr>"
            for q in section.questions
        )
        blocks.append(
            f"<h2>{esc(section.title)}{optional}"
            f"<span class=count>{filled}/{len(section.questions)}</span>"
            f"<a class=edit href='/profile/{esc(section.id)}'>edit</a></h2>"
            f"<table class=sum>{rows}</table>"
        )

    return page(
        "Profile",
        "<h1>Your profile</h1>"
        + "<div class=frow style='margin:0 0 14px'>"
          "<a class='chip on' href='/profile/import'>Import a CV</a>"
          "<a class=chip href='/profile/health'>CV health</a></div>"
        f"<p class=lead>{versions} version(s) saved. Every edit writes a new version rather than "
        "overwriting — this profile is living data, not a form you fill in once.</p>"
        f"{gate}{''.join(blocks)}",
        active="/profile", status="Running",
    )
