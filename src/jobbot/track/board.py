"""Bảng theo dõi — một dòng cho một lần nộp.

Một dòng sinh ra khi Vin nộp, và đổi trạng thái khi có thư về. Thư là CẢM
BIẾN, bảng là TRẠNG THÁI — không phải hai tính năng, là một vòng.

`im lặng` KHÔNG lưu thành cột. Nó là phép trừ, tính lúc đọc: đã nộp quá lâu
mà chưa thư nào. Lưu thì phải ngồi cập nhật mỗi ngày, và sẽ có ngày quên —
đúng cách `khoảng trống` ở lưới project.
"""

from __future__ import annotations

import sqlite3

from ..ingest.base import norm

# Năm chặng. Mỗi chặng ứng với một việc Vin làm khác nhau — chặng nào không
# ứng với việc nào thì không được tồn tại.
#
# `draft` sinh ra khi máy mở form và điền hộ. Nó KHÔNG phải "đã nộp": form còn
# vài câu chỉ Vin trả lời được, và cú bấm Gửi là của Vin. Ghi thẳng "đã nộp"
# lúc đó thì bảng nói dối ngay dòng đầu tiên — mà bảng này Vin đọc mỗi ngày.
# Thư xác nhận về sẽ tự đẩy nó sang "đã nộp"; đó đúng là vai trò cảm biến của
# thư, không phải một cơ chế mới.
DRAFT = "draft"
SENT, INTERVIEW, REJECTED, OFFER = "applied", "interview", "rejected", "offer"
STAGES = (DRAFT, SENT, INTERVIEW, REJECTED, OFFER)
STAGE_LABEL = {DRAFT: "đang điền", SENT: "đã nộp", INTERVIEW: "phỏng vấn",
               REJECTED: "từ chối", OFFER: "nhận"}
# Đang chờ KẾT CỤC. Bản nháp không chờ ai cả — nó chờ chính Vin, nên không
# tính vào đây và không bao giờ bị gọi là "im lặng".
OPEN = (SENT, INTERVIEW)

SILENT_AFTER = 14        # ngày, chưa thư nào thì coi như im lặng


def _now() -> str:
    from ..core.postings import now
    return now()


def add(conn: sqlite3.Connection, company: str, role: str,
        posting_id: int | None = None, cv_file: str = "",
        origin: str = "manual", applied_at: str = "",
        stage: str = SENT) -> int:
    """Ghi một lần nộp. Nộp lại đúng vai trò đó ở đúng công ty đó thì KHÔNG
    đẻ dòng mới — đó là một lần nộp, không phải hai."""
    key = norm(company)
    found = conn.execute(
        "SELECT id, stage, posting_id FROM application"
        " WHERE company_key = ? AND role = ?", (key, role)).fetchone()
    if found:
        app_id = int(found["id"])
        if cv_file:
            conn.execute("UPDATE application SET cv_file = ? WHERE id = ?",
                         (cv_file, app_id))
        # Dòng dựng từ thư không có số hiệu tin. Không gắn vào thì nút Gửi đơn
        # đi tìm cửa sổ theo posting_id và trả "không có tin gốc".
        if posting_id and not found["posting_id"]:
            conn.execute("UPDATE application SET posting_id = ? WHERE id = ?",
                         (posting_id, app_id))
        # NỘP LẠI nơi từng bị từ chối (công ty mở lại tin) là một lần nộp MỚI.
        # Giữ nguyên chặng cũ thì bảng vẫn ghi "từ chối", nút Gửi đơn không
        # hiện, và đơn Vin vừa điền không bao giờ đi. Kéo về nháp, nhưng NÓI RA
        # kết cục cũ — mất lịch sử cũng là nói dối.
        if stage == DRAFT and found["stage"] in (REJECTED, OFFER):
            conn.execute(
                "UPDATE application SET stage = ?, last_event = ?,"
                " last_event_at = ? WHERE id = ?",
                (DRAFT, f"nộp lại — lần trước: {STAGE_LABEL[found['stage']]}",
                 _now(), app_id))
        conn.commit()
        return app_id
    cur = conn.execute(
        "INSERT INTO application (company, company_key, role, posting_id,"
        " origin, applied_at, stage, cv_file) VALUES (?,?,?,?,?,?,?,?)",
        (company, key, role, posting_id, origin, applied_at or _now(),
         stage if stage in STAGES else SENT, cv_file))
    conn.commit()
    return int(cur.lastrowid)


def set_stage(conn: sqlite3.Connection, app_id: int, stage: str,
              event: str = "") -> None:
    if stage not in STAGES:
        return
    conn.execute(
        "UPDATE application SET stage = ?, last_event_at = ?, last_event = ?"
        " WHERE id = ?",
        (stage, _now(), event or STAGE_LABEL[stage], app_id))
    conn.commit()


SENDING = "sending"          # đang bấm Gửi — chặng TẠM, không hiện thành nhãn


def claim(conn: sqlite3.Connection, app_id: int) -> bool:
    """Giành quyền gửi lá đơn này. Trả True nếu giành được.

    Một câu UPDATE ... WHERE stage = 'draft' là NGUYÊN TỬ: hai cú bấm cách
    nhau hai giây thì chỉ một câu đổi được dòng, câu kia đếm 0. Đọc-rồi-ghi ở
    tầng route thì cả hai cùng thấy 'draft' và cùng đi bấm Submit — hai lá đơn
    giống nhau tới cùng một nhà tuyển dụng.
    """
    cur = conn.execute(
        "UPDATE application SET stage = ? WHERE id = ? AND stage = ?",
        (SENDING, app_id, DRAFT))
    conn.commit()
    return cur.rowcount == 1


def unclaim(conn: sqlite3.Connection, app_id: int) -> None:
    """Trả lại về nháp khi gửi không thành."""
    conn.execute("UPDATE application SET stage = ? WHERE id = ? AND stage = ?",
                 (DRAFT, app_id, SENDING))
    conn.commit()


def drop(conn: sqlite3.Connection, app_id: int) -> bool:
    """Xoá một dòng — CHỈ khi nó còn là bản nháp.

    Mở form rồi đổi ý là chuyện thường, và một dòng nháp bỏ quên làm bẩn bảng.
    Nhưng lần nộp THẬT thì không xoá bằng một cú bấm: đó là lịch sử, và lịch
    sử mất đi thì 30 ngày nhìn lại chẳng còn gì để nhìn.

    Xoá thư trước rồi mới xoá dòng: `message.application_id` không có
    ON DELETE CASCADE nên làm ngược lại là vướng khoá ngoại.
    """
    row = conn.execute("SELECT stage FROM application WHERE id = ?",
                       (app_id,)).fetchone()
    if row is None or row["stage"] != DRAFT:
        return False
    conn.execute("DELETE FROM message WHERE application_id = ?", (app_id,))
    conn.execute("DELETE FROM application WHERE id = ?", (app_id,))
    conn.commit()
    return True


def note(conn: sqlite3.Connection, app_id: int, text: str) -> None:
    conn.execute("UPDATE application SET note = ? WHERE id = ?", (text, app_id))
    conn.commit()


def _days(stamp: str) -> int | None:
    from datetime import datetime, timezone
    if not stamp:
        return None
    try:
        then = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - then).total_seconds() // 86400)


def all(conn: sqlite3.Connection) -> list[dict]:
    """Cả bảng. Đang chờ lên trước, im lặng lâu nhất lên đầu."""
    rows = []
    for r in conn.execute(
            "SELECT a.*, p.url AS url, p.score AS score FROM application a"
            " LEFT JOIN posting p ON p.id = a.posting_id ORDER BY a.id DESC"):
        row = dict(r)
        row["days"] = _days(row["applied_at"])
        row["event_days"] = _days(row["last_event_at"])
        # im lặng = đã nộp lâu, chưa thư nào. Chỉ tính khi còn đang chờ.
        row["silent"] = (row["stage"] in OPEN
                         and not row["last_event_at"]
                         and (row["days"] or 0) >= SILENT_AFTER)
        rows.append(row)
    # Nháp lên đầu: đó là việc đang dở, và việc đang dở phải đập vào mắt.
    rows.sort(key=lambda r: (r["stage"] != DRAFT, r["stage"] not in OPEN,
                             -(r["days"] or 0)))
    return rows


def counts(conn: sqlite3.Connection) -> dict:
    out = {s: 0 for s in STAGES}
    silent = 0
    for row in all(conn):
        out[row["stage"]] = out.get(row["stage"], 0) + 1
        silent += bool(row["silent"])
    out["silent"] = silent
    # "Tổng" là số lần NỘP THẬT. Bản nháp chưa gửi đi đâu cả, đếm vào là tự
    # khen mình.
    out["total"] = sum(out[s] for s in STAGES if s != DRAFT)
    return out
