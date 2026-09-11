"""Chi tiết MỘT tin — điểm, từng yêu cầu, bằng chứng, lý do.

Trang DANH SÁCH đã bỏ cùng tab Jobs. Danh sách sẽ nằm trong tab Search, vì
"tìm" và "xem kết quả tìm" là một việc chứ không phải hai.

Trang này VẪN SỐNG, vào được bằng /jobs/<id> — nó là chỗ danh sách mới sẽ
trỏ tới, và là chỗ đọc được vì sao một tin được chấm ngần ấy điểm.

CHỈ VẼ.
"""

from __future__ import annotations

from html import escape as esc

from ..layout import card, empty, h1, page, score_bar

CHANCE_BADGE = {"likely": ("worth applying", "ok"),
                "possible": ("maybe", ""),
                "unlikely": ("long shot", "warn")}



CONF_NOTE = {"high": "", "medium": "few requirements found",
             "low": "requirements guessed from prose", "none": ""}


def _score(job: dict) -> str:
    """Không chấm được thì NÓI THẲNG. Điểm bịa còn tệ hơn không có điểm."""
    if job.get("score") is None:
        return "<span class=noscore>can&#39;t read requirements — judge it yourself</span>"
    note = CONF_NOTE.get(job.get("confidence", ""), "")
    tail = f"<span class=conf>{esc(note)}</span>" if note else ""
    return score_bar(job["score"]) + tail


def _breakdown(job: dict) -> str:
    """Điểm đến từ đâu. Không giải thích được thì không dùng để quyết định nộp."""
    data = job.get("explain")
    if not data or data.get("score") is None:
        return ""
    b = data["breakdown"]
    rows = "".join(
        f"<div class=bdrow><span class=bdl>{esc(label)}</span>"
        f"<span class=bdtrack><span class=bdfill style='width:{pts / cap * 100:.0f}%'></span></span>"
        f"<b>{pts:g}<i>/{cap}</i></b><span class=muted>{esc(why)}</span></div>"
        for label, pts, cap, why in [
            ("Must-have requirements", b["must"]["points"], 55,
             f"{b['must']['met']}/{b['must']['total']} met"),
            ("Nice-to-haves", b["nice"]["points"], 15,
             f"{b['nice']['met']}/{b['nice']['total']} met"),
            ("Level fit", b["level"]["points"], 20, b["level"]["why"]),
            ("Title match", b["title"]["points"], 10, b["title"]["why"]),
        ])
    notes = []
    if data.get("capped"):
        notes.append("Score capped at 55 — this posting asks for experience or a "
                     "qualification you do not have, so it is unlikely to pass screening "
                     "however well the rest matches.")
    if data.get("unknown"):
        notes.append(f"{data['unknown']} lines could not be judged automatically "
                     "(soft skills, culture fit) — left out of the maths entirely "
                     "rather than guessed at.")
    if data.get("weak_evidence"):
        notes.append(f"{data['weak_evidence']} matches rest on keywords you set rather than "
                     "evidence in your CV. Filling in your skills and CV would firm these up.")
    tail = "".join(f"<div class=note>{esc(n)}</div>" for n in notes)
    return card(f"<div class=bd>{rows}</div>{tail}", "bdcard")


def render_detail(job: dict) -> str:
    reqs = "".join(
        f"<li class='{'met' if r['met'] else ('unk' if r['met'] is None else 'miss')}'>"
        f"<b>{esc(r['text'])}</b>"
        f"<span>{esc(r['evidence'])}</span></li>"
        for r in job["requirements"]
    )
    proj = job.get("project")
    return page(
        job["title"],
        f"<a class=back href='/search'>← Jobs</a>"
        + h1(job["title"], f"{job['company']} · {job['location']} · {job['salary']}")
        + f"<div class=jmeta>{_score(job)}"
          f"<span class=spacer></span><span class=muted>{esc(job['posted'])}</span></div>"
        + "<h2>Why this score</h2>"
        + _breakdown(job)
        + (card(f"<ul class=reqs>{reqs}</ul>") if reqs
           else empty("Could not read any requirements from this posting. "
                      "Read it yourself — the system will not guess."))
        + "<h2>Tailored CV</h2>"
        + card(f"<a class=ghost href='/jobs/{esc(job['id'])}/cv'>"
               "Build a CV for this posting →</a>"
               "<div class=muted style='margin-top:6px'>Selects and orders lines from your "
               "own profile against what this posting asks for. Writes nothing new.</div>")
        + "<h2>Project write-up</h2>"
        + card(f"<a class=ghost href='/jobs/{esc(job['id'])}/project'>"
               "Build a one-page write-up for this posting →</a>"
               "<div class=muted style='margin-top:6px'>Five parts, 90 seconds to read. "
               "Uses the lines the CV builder cut out — that is where they belong.</div>")
        + "<h2>The posting</h2>"
        + card(f"<pre class=jd>{esc(job['jd'])}</pre>")
        + "<div class=actbar><button class=primary>Queue for approval</button>"
          "<button class=ghostbtn>Reject…</button>"
          "<span class=muted>Nothing is sent until you approve it in the queue.</span></div>",
        active="/jobs",
    )
