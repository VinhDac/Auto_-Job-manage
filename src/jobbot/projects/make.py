"""Dựng đề bài cho MỘT kỹ năng — chỗ nối giữa ô trống trên lưới và bảy chặng.

pipeline.run() cần một Findings, mà Findings dựng từ một NHÓM tin. Trước đây
nhóm là cụm do cluster.build() tự chia. Cụm sinh ra từ dữ liệu, nên dữ liệu đổi
là cụm đổi — và đề bài đã sinh thành mồ côi. Đã xảy ra: bốn câu trả lời của
Claude thuộc cụm "excel + python + statistics", sửa lỗi khớp chuỗi con xong thì
cụm đó biến mất, bốn câu trả lời thành rác.

Ở đây nhóm là "mọi tin đang giữ CÓ ĐÒI kỹ năng này". Kỹ năng lấy từ từ vựng cố
định trong scoring/vocab.py — nó không tự biến mất, nên đề bài không mồ côi.

Chạy NỀN, không chạy lúc vẽ trang: chặng nghiên cứu mở Chrome đọc trang công
ty, chặng kiểm dữ liệu tải bộ dữ liệu thật về. Đó là việc tính bằng phút.
"""

from __future__ import annotations

import sqlite3

from ..core.journal import PROJECT, log as jlog
from . import inventory, pipeline, research
from .cluster import Cluster


def for_skill(conn: sqlite3.Connection, skill: str) -> Cluster:
    """Mọi tin đang giữ có đòi kỹ năng này, tin điểm cao lên trước."""
    jobs = []
    for row, skills in inventory._scan(conn):
        if skill in skills:
            jobs.append({"id": row["id"], "title": row["title"],
                         "company": row["company"]})
    return Cluster(key=skill, skills=[skill], jobs=jobs)


def existing_work(conn: sqlite3.Connection, cv_projects: list) -> list[str]:
    """Thứ Vin ĐÃ làm — để bộ chấm không chọn lại cái trùng.

    Gộp cả hai nguồn: project trên CV, và đề bài đã có trong kho. Thiếu nguồn
    thứ hai thì lần dựng sau lại đẻ ra đúng đề bài lần trước.
    """
    out = [getattr(b, "title", "") for b in cv_projects]
    out += [r["question"] for r in inventory.all(conn)]
    return [x for x in out if x]


def build(conn: sqlite3.Connection, skill: str, cv_projects: list,
          tab_factory=None) -> str:
    """Chạy bảy chặng cho một kỹ năng. Trả về trạng thái pipeline.

    Chỉ khi ra được đề bài QUA ĐƯỢC cả kiểm cứng lẫn kiểm dữ liệu thì mới cất
    vào kho. Trượt thì ghi nhật ký nói rõ trượt ở đâu, không cất bừa — kho có
    rác thì lần sau nhìn vào không biết cái nào làm được.
    """
    group = for_skill(conn, skill)
    if not group.jobs:
        jlog.warn(PROJECT, f"{skill}: không tin nào đang giữ đòi kỹ năng này")
        return "no_jobs"

    jlog.emit(PROJECT, f"{skill}: đọc {len(group.jobs)} tin")
    findings = research.study(conn, group)
    findings, web = pipeline.research_cached(conn, group, findings,
                                             tab_factory=tab_factory)
    if web == "fresh":
        jlog.ok(PROJECT, f"{skill}: đọc thêm {len(findings.web_notes)} trang công ty")

    out = pipeline.run(conn, findings, existing_work(conn, cv_projects))
    if out.state != "ok":
        return out.state

    tags = inventory.industries(conn).get(skill, [])
    inventory.add(conn, out.chosen, tags)
    jlog.ok(PROJECT, f"{skill}: đã cất vào kho — {out.chosen.question[:60]}")
    return "ok"


def is_stale(purpose: str) -> bool:
    """Yêu cầu LLM khoá theo NHÓM JD — trục cũ, giờ không ai hỏi lại nữa.

    Khoá cũ trông như `project_briefs:risk + python + statistics`: tên một cụm
    do cluster.build() tự chia. Trục giờ là MỘT kỹ năng, nên khoá mới luôn là
    một tên đơn. Không lần chạy nào còn hỏi đúng khoá cũ, nên câu trả lời cho
    nó sẽ nằm đó không ai đọc — trả lời nó là mất công vô ích.

    Đo được 09/09: cả 5 yêu cầu đang treo đều thuộc loại này.
    """
    return (purpose.startswith("project_brief:")
            or (purpose.startswith("project_briefs:") and " + " in purpose))
