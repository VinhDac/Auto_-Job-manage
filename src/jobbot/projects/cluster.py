"""Gom tin tuyển dụng thành nhóm theo kỹ năng chúng đòi.

Dùng greedy set cover, KHÔNG dùng k-means: nó giải thích được.
Mỗi nhóm trả lời được câu "nhóm này tồn tại vì 12 tin cùng đòi time series",
chứ không phải "thuật toán xếp chúng cạnh nhau".
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from ..cv.build import skills_in

MIN_JOBS = 2           # dưới ngần này không đáng gọi là nhóm
MAX_CLUSTERS = 8

# Kỹ năng xuất hiện ở quá nhiều tin thì KHÔNG dùng làm tên nhóm: "python" có mặt
# ở 19/24 tin nên lấy nó làm khoá sẽ nuốt gọn mọi thứ vào một nhóm.
# Nó vẫn được liệt kê trong nhóm, chỉ không được làm khoá.
TOO_COMMON = 0.6


@dataclass
class Cluster:
    key: str                                  # kỹ năng định danh nhóm
    skills: list[str] = field(default_factory=list)
    jobs: list[dict] = field(default_factory=list)
    covered_by: list[str] = field(default_factory=list)   # project đã có trả lời được
    gap: bool = True

    @property
    def title(self) -> str:
        return " + ".join(self.skills[:3]) if self.skills else self.key


def job_skills(row: sqlite3.Row) -> set[str]:
    """Kỹ năng một tin đòi — gộp từ yêu cầu đã tách và toàn văn tin."""
    out = skills_in(row["title"] + " " + (row["description"] or "")[:6000])
    if row["score_json"]:
        for req in json.loads(row["score_json"]).get("requirements", []):
            out |= skills_in(req["text"])
    return out


def build(conn: sqlite3.Connection, project_blocks: list) -> list[Cluster]:
    rows = conn.execute(
        "SELECT id, title, company, score, description, score_json FROM posting"
        " WHERE kept = 1 ORDER BY score DESC NULLS LAST").fetchall()

    pool = [{"id": r["id"], "title": r["title"], "company": r["company"],
             "score": r["score"], "skills": job_skills(r)} for r in rows]

    everywhere = {s for s, c in Counter(s for j in pool for s in j["skills"]).items()
                  if c > len(pool) * TOO_COMMON}

    clusters: list[Cluster] = []
    left = list(pool)
    while left and len(clusters) < MAX_CLUSTERS:
        counts = Counter(s for job in left for s in job["skills"])
        usable = [(s, c) for s, c in counts.most_common() if s not in everywhere]
        if not usable:
            break
        key, n = usable[0]
        if n < MIN_JOBS:
            break
        members = [j for j in left if key in j["skills"]]
        # kỹ năng đặc trưng của nhóm: xuất hiện ở quá nửa thành viên
        shared = [s for s, c in Counter(s for j in members for s in j["skills"]).items()
                  if c >= max(2, len(members) * 0.5)]
        shared.sort(key=lambda s: -sum(1 for j in members if s in j["skills"]))
        clusters.append(Cluster(key, shared[:5], members))
        left = [j for j in left if key not in j["skills"]]

    # project đã có trả lời được nhóm nào — so với TOÀN BỘ kỹ năng của nhóm,
    # không chỉ 5 cái tiêu biểu, và đọc cả chữ trong project chứ không chỉ nhãn
    for cluster in clusters:
        wanted = {s for job in cluster.jobs for s in job["skills"]}
        for block in project_blocks:
            tags = set(block.tags) | skills_in(block.text())
            if len(tags & wanted) >= 2:
                cluster.covered_by.append(block.title or "untitled project")
        cluster.gap = not cluster.covered_by

    if left:                                   # phần lẻ, gom lại một chỗ
        clusters.append(Cluster("other", [], left, [], False))
    return clusters
