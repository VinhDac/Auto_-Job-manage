"""Quy trình đầy đủ để ra một đề bài project — bảy chặng.

    0 NHẮM      nhóm JD  ->  cần chứng minh cái gì
    1 NGHIÊN CỨU đọc kỹ toàn bộ JD trong nhóm; Chrome đọc thêm trang công ty
    2 SINH      LLM đề xuất NHIỀU phương án, không phải một
    3 KIỂM CỨNG  8 luật trong brief.validate — trượt là loại, không thương lượng
    4 KIỂM DỮ LIỆU tải thật, nhìn vào bên trong: có cột ngày? có cột giá? đủ dòng?
    5 XẾP HẠNG   6 chiều: phủ · bác bỏ được · cụ thể · dữ liệu sẵn · gọn · mới
    6 CHỌN       lấy cái đầu bảng, GIỮ LẠI cả những cái bị loại kèm lý do

Vì sao sinh nhiều rồi mới chọn: ý đầu tiên hiếm khi là ý tốt nhất, và đã có bộ
chấm thì so sánh rẻ hơn nhiều so với làm nhầm 2 ngày.

Vì sao giữ cái bị loại: lý do loại nói cho Vin biết nhóm JD này thiếu dữ liệu gì,
hoặc bộ luật đang quá chặt ở đâu.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..core.journal import PROJECT, log as jlog
from . import brief as brief_mod
from . import feasible, rank as rank_mod
from .research import Findings

N_CANDIDATES = 4

# CẨN THẬN: PROMPT dùng {{ }} để thoát dấu ngoặc cho .format(). Gọi .format()
# lên chuỗi thay thế sẽ biến {{ thành { và làm hỏng escaping — lỗi này đã xảy ra.
MULTI_PROMPT = (
    brief_mod.PROMPT
    .replace("Design ONE project that answers",
             f"Design {N_CANDIDATES} DIFFERENT projects, each answering")
    .replace("Reply with ONLY a JSON object, no prose around it:\n{{",
             f"Reply with ONLY a JSON array of {N_CANDIDATES} objects, "
             "no prose around it:\n[{{")
    .replace('"deliverable": "one notebook + a one-page write-up"}}',
             '"deliverable": "one notebook + a one-page write-up"}}, ...]')
)


CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS cluster_research (
    cluster_key TEXT PRIMARY KEY,
    made_at     TEXT NOT NULL,
    payload     TEXT NOT NULL
)"""


def research_cached(conn: sqlite3.Connection, cluster, findings,
                    max_age_hours: float = 72.0, tab_factory=None):
    """Đọc trang công ty — nhưng CHỈ MỘT LẦN mỗi 3 ngày, không phải mỗi lần mở trang.

    Trước đây trang /projects/<nhóm> chạy cả pipeline khi render: mở Chrome, tải
    dataset, kiểm URL. Mất 2 giây và gọi mạng ngay trong lúc vẽ trang — sai hoàn
    toàn. Việc nặng phải chạy nền và lưu lại.
    """
    import json as _json
    from datetime import datetime, timedelta, timezone

    conn.execute(CACHE_TABLE)
    row = conn.execute("SELECT made_at, payload FROM cluster_research"
                       " WHERE cluster_key = ?", (cluster.key,)).fetchone()
    if row:
        try:
            when = datetime.fromisoformat(row["made_at"])
            if datetime.now(timezone.utc) - when < timedelta(hours=max_age_hours):
                from .research import WebNote, merge_web
                notes = [WebNote(**n) for n in _json.loads(row["payload"])]
                return merge_web(findings, notes), "cache"
        except (ValueError, TypeError):
            pass

    if tab_factory is None:
        return findings, "not_run"

    from .research import merge_web, web_study
    tab = tab_factory()
    try:
        notes = web_study(tab, findings, limit=3)
    finally:
        tab.close()
    from dataclasses import asdict
    conn.execute("INSERT OR REPLACE INTO cluster_research VALUES (?,?,?)",
                 (cluster.key, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  _json.dumps([asdict(n) for n in notes], ensure_ascii=False)))
    conn.commit()
    return merge_web(findings, notes), "fresh"


@dataclass
class Outcome:
    state: str = ""
    chosen: object = None
    chosen_score: object = None
    rejected: list = field(default_factory=list)
    why: str = ""
    prompt: str = ""


def _parse_many(text: str) -> list:
    """LLM có thể trả mảng, hoặc nhiều object rời. Nhận cả hai."""
    import json
    import re
    out = []
    array = re.search(r"\[\s*\{.*\}\s*\]", text or "", re.S)
    if array:
        try:
            for item in json.loads(array.group()):
                got = brief_mod.parse_brief(json.dumps(item))
                if got:
                    out.append(got)
            if out:
                return out
        except ValueError:
            pass
    for block in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text or "", re.S):
        got = brief_mod.parse_brief(block.group())
        if got and got.question:
            out.append(got)
    return out


def run(conn: sqlite3.Connection, findings: Findings, existing: list[str],
        check_url=brief_mod.url_ok, inspect=feasible.inspect) -> Outcome:
    from ..core import llm

    if findings.thin:
        jlog.warn(PROJECT, f"{findings.cluster}: chỉ {findings.jobs} tin có mô tả"
                           " — chưa đủ để dựng đề bài")
        return Outcome("not_enough",
                       why=f"chỉ {findings.jobs} tin có mô tả — không đủ để biết họ cần gì")

    jlog.progress(PROJECT, f"dựng đề bài — {findings.cluster}")

    prompt = MULTI_PROMPT.format(
        jobs=findings.jobs,
        companies=", ".join(findings.companies[:6]) or "several firms",
        needs="\n".join(f"  - ({n} postings) {t}" for t, n in findings.core_needs[:6])
              or "  - (nothing repeated clearly)",
        concepts=", ".join(k for k, _ in findings.concepts[:8]) or "—",
        data=", ".join(k for k, _ in findings.data_named[:5]) or "none named",
        skills=", ".join(findings.skills[:10]),
        existing="\n".join(f"  - {e}" for e in existing[:5]) or "  - nothing yet",
        max_days=brief_mod.MAX_DAYS)

    answer = llm.ask(conn, f"project_briefs:{findings.cluster}", prompt)
    if answer.pending:
        jlog.emit(PROJECT, f"{findings.cluster}: đã xếp hàng, chờ Claude trả lời")
        jlog.done(PROJECT)
        return Outcome("pending", why="đã xếp hàng chờ Claude trả lời", prompt=prompt)
    if not answer.text:
        jlog.warn(PROJECT, f"{findings.cluster}: chưa bật LLM, không dựng được đề bài")
        jlog.done(PROJECT)
        return Outcome("no_llm", why="chưa bật LLM — xem Settings", prompt=prompt)

    candidates = _parse_many(answer.text)
    if not candidates:
        jlog.error(PROJECT, f"{findings.cluster}: không bóc được đề bài nào từ câu trả lời")
        jlog.done(PROJECT)
        return Outcome("unreadable", why="không bóc được đề bài nào từ câu trả lời")

    scored = []
    for index, item in enumerate(candidates, 1):
        # Kiểm dữ liệu có TẢI THẬT bộ dữ liệu về đọc — chậm, nên phải báo tiến độ.
        jlog.progress(PROJECT, f"kiểm {len(candidates)} đề bài", index, len(candidates))
        problems = brief_mod.validate(item, findings.skills, existing, check_url)
        data_problems: list[str] = []
        if not any(p.field == "dataset_url" for p in problems):
            check = inspect(item.dataset_url)
            data_problems = feasible.judge(item, check)
        marks = rank_mod.score(item, findings.skills, data_problems, existing)
        scored.append((item, problems, data_problems, marks))

    ordered = rank_mod.rank(scored)
    best, problems, data_problems, marks = ordered[0]
    jlog.done(PROJECT)
    if problems or data_problems:
        jlog.warn(PROJECT, f"{findings.cluster}: cả {len(candidates)} đề bài đều trượt"
                           f" — {(problems + data_problems)[0]}")
        return Outcome("all_rejected", rejected=ordered,
                       why="không đề bài nào qua được cả kiểm cứng lẫn kiểm dữ liệu")
    jlog.ok(PROJECT, f"{findings.cluster}: chọn được đề bài ({marks.total:.0f} điểm)"
                     f" — {best.question[:60]}")
    return Outcome("ok", chosen=best, chosen_score=marks, rejected=ordered[1:])
