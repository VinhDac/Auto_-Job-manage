"""Tầng suy diễn — tính lại được, chỉ tính cái đã cũ, và là MỘT giao dịch.

Kiến trúc:

    raw_posting   nguyên văn đã lấy về. KHÔNG BAO GIỜ sửa.
    posting       chuẩn hoá + phán quyết. Tính lại được hoàn toàn từ raw.

Ba tính chất phải giữ:

1. **Tính lại được.** `rebuild()` dựng lại toàn bộ phán quyết từ raw. Không có
   nó thì một lỗi trong luật là hỏng vĩnh viễn.

2. **Gắn phiên bản.** Mỗi phán quyết ghi rõ nó sinh ra từ hồ sơ phiên bản nào,
   luật phiên bản nào. Đổi hồ sơ hay đổi luật -> tin cũ tự động thành cần tính
   lại, không im lặng.

3. **Một giao dịch.** Web đọc giữa chừng phải thấy trạng thái CŨ trọn vẹn, chứ
   không thấy trạng thái dở dang.
"""

from __future__ import annotations

import json
import sqlite3

from ..dedup import group
from ..ingest import filter as jobfilter
from ..ingest.base import Posting
from ..ingest.web.agency import judge as judge_agency
from ..profile import store
from ..scoring.score import score_job
from . import versions


def _row_to_posting(row: sqlite3.Row) -> Posting:
    return Posting(source_id="", title=row["title"], company=row["company"],
                   location=row["location"], remote=bool(row["remote"]),
                   description=row["description"] or "")


def stale_count(conn: sqlite3.Connection) -> int:
    pv = store.latest_version_id(conn) or 0
    return int(conn.execute(
        "SELECT COUNT(*) FROM posting WHERE judged_profile != ? OR judged_rules != ?",
        (pv, versions.FILTER_RULES)).fetchone()[0])


def derive(conn: sqlite3.Connection, force: bool = False,
           log=lambda _m: None) -> dict:
    """Tính lại phán quyết cho tin đã cũ. Trả về thống kê."""
    answers = store.load(conn)
    profile_version = store.latest_version_id(conn) or 0

    if force:
        rows = conn.execute("SELECT * FROM posting").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM posting WHERE judged_profile != ? OR judged_rules != ?",
            (profile_version, versions.FILTER_RULES)).fetchall()

    # sqlite3 của Python tự mở giao dịch ở lệnh ghi đầu tiên và giữ tới commit().
    # Nên chỉ cần KHÔNG commit ở giữa là cả khối này là một giao dịch.
    try:
        judged = kept = agencies = 0
        for row in rows:
            item = _row_to_posting(row)
            keep, reason = jobfilter.judge(item, answers)
            is_agency, _ = judge_agency(row["company"], row["description"] or "")
            conn.execute(
                "UPDATE posting SET kept=?, drop_reason=?, via_agency=?,"
                " judged_profile=?, judged_rules=? WHERE id=?",
                (int(keep), "" if keep else reason, int(is_agency),
                 profile_version, versions.FILTER_RULES, row["id"]))
            judged += 1
            kept += int(keep)
            agencies += int(is_agency)

        n_rows, n_groups = group.regroup(conn, commit=False)

        # chấm điểm: tin đang giữ mà luật chấm đã đổi, hoặc chưa từng chấm
        to_score = conn.execute(
            "SELECT id, title, description FROM posting WHERE kept = 1"
            " AND (scored_rules != ? OR scored_rules = '')",
            (versions.SCORE_RULES,)).fetchall()
        scored = 0
        for row in to_score:
            result = score_job(row["title"], row["description"] or "", answers)
            conn.execute(
                "UPDATE posting SET score=?, score_conf=?, score_json=?, scored_rules=?"
                " WHERE id=?",
                (result["score"], result["confidence"],
                 json.dumps(result, ensure_ascii=False),
                 versions.SCORE_RULES, row["id"]))
            scored += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    # Số đếm phải là TỔNG hiện tại, không phải phần vừa phán lượt này.
    # Không có gì cũ -> judged=0, mà báo "giữ 0" thì đọc ra là mất hết dữ liệu.
    totals = conn.execute(
        "SELECT COUNT(*) AS n, SUM(via_agency) AS ag FROM posting WHERE kept = 1"
    ).fetchone()
    kept_total = totals["n"] or 0
    agency_total = totals["ag"] or 0

    log(f"  suy diễn: phán lại {judged} · đang giữ {kept_total} "
        f"({agency_total} môi giới) · {n_groups} việc duy nhất · chấm {scored}")
    return {"judged": judged, "kept": kept_total, "agencies": agency_total,
            "kept_new": kept, "groups": n_groups, "scored": scored}


def rebuild(conn: sqlite3.Connection, log=lambda _m: None) -> dict:
    """Dựng lại TOÀN BỘ tầng suy diễn từ tầng raw.

    Dùng khi sửa luật, sửa hàm bóc HTML, hay nghi ngờ dữ liệu suy diễn hỏng.
    Không mất gì: raw vẫn nguyên.
    """
    from ..ingest.base import strip_html
    rows = conn.execute(
        "SELECT p.id, r.body FROM posting p JOIN raw_posting r ON p.raw_id = r.id"
        " WHERE length(COALESCE(r.body,'')) > 0").fetchall()
    conn.executemany("UPDATE posting SET description = ? WHERE id = ?",
                     [(strip_html(r["body"])[:20000], r["id"]) for r in rows])
    conn.execute("UPDATE posting SET judged_rules = '', scored_rules = ''")
    conn.commit()
    log(f"  bóc lại mô tả từ raw: {len(rows)} tin")
    return derive(conn, force=True, log=log)
