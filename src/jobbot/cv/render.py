"""Vẽ CV đã tuỳ biến ra HTML — và LUÔN hiện phần đã bỏ.

Bỏ im lặng là cách chắc chắn nhất để mất một câu đáng giá mà không bao giờ biết.
Vin phải nhìn được: giữ gì, bỏ gì, vì sao, và JD đòi gì mà hồ sơ không có.
"""

from __future__ import annotations

from html import escape as esc

from .build import TailoredCV

LABEL = {"experience": "Experience", "project": "Selected projects",
         "education": "Education", "cert": "Certifications", "skill": "Technical skills"}


def paper(cv: TailoredCV) -> str:
    """Phần trông giống tờ CV thật."""
    head = "".join(f"<div class=cvline>{esc(h)}</div>" for h in cv.header if h)
    out = [f"<div class=cvhead>{head}</div>"]
    if cv.summary:
        out.append(f"<p class=cvsum>{esc(cv.summary)}</p>")

    last = ""
    for section in cv.sections:
        if section.kind != last:
            out.append(f"<h4 class=cvsec>{esc(LABEL.get(section.kind, section.kind))}</h4>")
            last = section.kind

        if section.kind in ("experience", "project", "education"):
            meta = f"<span class=cvmeta>{esc(section.meta)}</span>" if section.meta else ""
            if section.title:
                out.append(f"<div class=cvrole><b>{esc(section.title)}</b>{meta}</div>")
            items = "".join(
                f"<li{' class=review' if l.review else ''}>{esc(l.text)}"
                + (f"<span class=rv>{esc(l.review)}</span>" if l.review else "")
                + "</li>" for l in section.lines)
            out.append(f"<ul class=cvlist>{items}</ul>")
        else:
            body = " ".join(l.text for l in section.lines)
            label = f"<b>{esc(section.title)}</b> — " if section.title else ""
            out.append(f"<div class=cvskill>{label}{esc(body)}</div>")
    return f"<div class=cvpaper>{''.join(out)}</div>"


def audit(cv: TailoredCV) -> str:
    """Phần kiểm chứng: cái gì bị bỏ, JD đòi gì mà mình không có."""
    covered = set(cv.covered)
    chips = "".join(
        f"<span class='badge {'ok' if w in covered else 'warn'}'>{esc(w)}</span>"
        for w in cv.wanted) or "<span class=muted>no recognisable skills in this posting</span>"

    gap = ""
    if cv.missing:
        gap = ("<div class=note><b>Nothing on your profile answers: </b>"
               + ", ".join(esc(m) for m in cv.missing)
               + ". Either it is genuinely missing, or it is in your head but not written down.</div>")

    drops = "".join(
        f"<li><span class=dtext>{esc(text)}</span>"
        f"<span class=dwhy>{esc(why)}</span></li>" for text, why in cv.dropped)
    dropbox = (f"<h4 class=cvsec>Left out ({len(cv.dropped)})</h4>"
               f"<ul class=droplist>{drops}</ul>"
               "<div class=note>Nothing here is deleted — the self-critique moves to the "
               "project write-up, where an experienced reader values it. It does not "
               "belong in front of a screener reading 200 CVs.</div>") if drops else ""

    return (f"<h4 class=cvsec>What this posting asks for</h4>"
            f"<div class=chiprow>{chips}</div>{gap}{dropbox}")
