"""Dựng đề bài cho MỘT kỹ năng — chỗ nối giữa ô trống trên lưới và bảy chặng.

pipeline.run() cần một Findings, mà Findings dựng từ một NHÓM tin. Trước đây
nhóm là cụm tự chia theo dữ liệu. Cụm sinh ra từ dữ liệu, nên dữ liệu đổi là
cụm đổi — và đề bài đã sinh thành mồ côi. Đã xảy ra: bốn câu trả lời thuộc cụm
"excel + python + statistics", sửa lỗi khớp chuỗi con xong thì cụm đó biến
mất, bốn câu trả lời thành rác.

Ở đây nhóm là "mọi tin đang giữ CÓ ĐÒI kỹ năng này". Kỹ năng lấy từ từ vựng cố
định trong scoring/vocab.py — nó không tự biến mất, nên đề bài không mồ côi.

KHÔNG dùng LLM. Đề bài do khuôn trong frame.py dựng — xem lời chú ở đó. Cái
chết theo: hàng đợi chờ Claude trả lời, tám giây mỗi lần, chép prompt dán câu
trả lời, và cảnh kẹt cứng sau bốn phương án.

Vẫn chạy NỀN: chặng kiểm dữ liệu tải bộ dữ liệu thật về đọc, và chặng đẻ repo
ghi cả chục tệp ra đĩa.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from ..core.journal import PROJECT, log as jlog
from . import brief as brief_mod
from . import feasible, frame, inventory, research


@dataclass
class Group:
    """Một nhóm tin cùng đòi MỘT kỹ năng.

    Trước đây là `cluster.Cluster`, do cluster.build() tự chia theo dữ liệu —
    dữ liệu đổi là cụm đổi là đề bài mồ côi, đã xảy ra thật với cụm ma
    'excel'. Trục giờ là kỹ năng lấy từ từ vựng cố định, nên nhóm không tự
    biến mất, và cả module chia cụm không còn việc gì để làm.
    """
    key: str
    skills: list[str] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.key


def for_skill(conn: sqlite3.Connection, skill: str) -> Group:
    """Mọi tin đang giữ có đòi kỹ năng này, tin điểm cao lên trước."""
    jobs = []
    for row, skills in inventory._scan(conn):
        if skill in skills:
            jobs.append({"id": row["id"], "title": row["title"],
                         "company": row["company"]})
    return Group(key=skill, skills=[skill], jobs=jobs)


def existing_work(conn: sqlite3.Connection, cv_projects: list,
                  dataset_url: str = "") -> list[str]:
    """Thứ Vin ĐÃ làm — để bộ chấm không chọn lại cái trùng.

    `dataset_url` thu hẹp lại còn project dùng CHUNG một nguồn. Một khuôn thì
    ra mấy câu hỏi na ná nhau về mặt chữ, nên so theo hành văn là loại oan:
    'phân tán lợi suất 49 ngành' và 'độ dốc đường cong lãi suất' trùng 16/20
    từ, mà đó là hai project hoàn toàn khác nhau. Cái đáng gọi là trùng là
    cùng một phép làm trên CÙNG một bộ dữ liệu.
    """
    out = [getattr(b, "title", "") for b in cv_projects]
    import json as _json
    for row in conn.execute("SELECT question, brief_json FROM project"):
        if dataset_url:
            try:
                if _json.loads(row["brief_json"]).get("dataset_url") != dataset_url:
                    continue
            except (TypeError, ValueError):
                continue
        out.append(row["question"])
    return [x for x in out if x]


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in text.lower())
    return "-".join(x for x in keep.split("-") if x)[:40]


def build(conn: sqlite3.Connection, skill: str, cv_projects: list,
          root=None) -> str:
    """Một ô trên lưới -> một đề bài trong kho + một repo chạy được trên đĩa.

    Chỉ cất khi qua được cổng. Trượt thì ghi nhật ký nói rõ trượt ở đâu, không
    cất bừa — kho có rác thì nhìn vào không biết cái nào làm được.
    """
    from pathlib import Path

    # MỘT kỹ năng chỉ một đề bài đang mở. Không có luật này thì bấm Dựng ba
    # lần là kho có bốn đề bài cùng một ô mà không cái nào làm — đo được thật
    # ngày 09/09. Vin làm được ~1 project/tuần; bốn đề bài mở là bốn thứ nhiễu.
    doing = inventory.planned(conn)
    if skill in doing:
        pid, state = doing[skill]
        jlog.warn(PROJECT, f"{skill}: đã có đề bài #{pid} ({state}) đang mở "
                           f"— xong cái đó rồi hẵng dựng tiếp")
        return "already_open"

    # Kiểm cái RẺ trước: khuôn có dựng được ô này không. Để sau thì đọc xong
    # cả trăm tin rồi mới phát hiện ra là không dựng được — công đổ đi.
    if frame.build(skill) is None:
        jlog.warn(PROJECT, f"{skill}: khuôn hiện tại chưa chứng minh được ô này "
                           f"— cần một hình dạng khác, xem frame.PROVES")
        return "no_frame"

    group = for_skill(conn, skill)
    if not group.jobs:
        jlog.warn(PROJECT, f"{skill}: không tin nào đang giữ đòi kỹ năng này")
        return "no_jobs"

    jlog.emit(PROJECT, f"{skill}: đọc {len(group.jobs)} tin")
    findings = research.study(conn, group)
    brief, src = frame.build(skill, findings)

    # Cổng hỏi "đề bài này có chạm thứ THỊ TRƯỜNG đòi không", nên phạm vi phải
    # là cả thị trường chứ không riêng một cụm. findings.skills chỉ là top-12
    # của cụm này: `validation` có 10/178 tin đòi mà vẫn rớt khỏi top-12, và
    # khuôn thì luôn chứng minh `validation` — hỏi sai phạm vi là loại oan.
    wanted = sorted(set(findings.skills) | set(inventory.demand(conn)))
    problems = brief_mod.validate(
        brief, wanted, existing_work(conn, cv_projects, brief.dataset_url))
    if problems:
        jlog.error(PROJECT, f"{skill}: khuôn ra đề bài không qua cổng — "
                            f"{problems[0].field}: {problems[0].why}")
        return "rejected"

    # KHÔNG gọi jlog.done() ở đây. `done` là tín hiệu bảo trang vẽ lại; gọi
    # giữa chừng thì trang nạp lại TRƯỚC khi đề bài kịp vào kho, và người dùng
    # thấy kho có đề bài mới mà lưới bên trái vẫn mời Dựng lại ô đó. Chỉ khối
    # `finally` ở server được đóng luồng, vì chỉ nó biết việc đã xong thật.
    jlog.progress(PROJECT, f"{skill}: kiểm dữ liệu")
    bad = feasible.judge(brief, feasible.inspect(brief.dataset_url))
    if bad:
        jlog.error(PROJECT, f"{skill}: nguồn dữ liệu hỏng — {bad[0][:80]}")
        return "data_bad"

    pid = inventory.add(conn, brief, inventory.industries(conn).get(skill, []))

    root = Path(root) if root else _default_root()
    out = root / f"{pid:02d}-{_slug(skill)}-{src.key}"
    frame.scaffold(brief, src, out)
    inventory.set_state(conn, pid, inventory.DE_BAI, link=str(out))
    jlog.ok(PROJECT, f"{skill}: đề bài #{pid} + repo ở {out}")
    return "ok"


def _default_root():
    from pathlib import Path
    from ..core.db import db_path
    return Path(db_path()).parent / "projects"
