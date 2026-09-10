"""Quét hộp thư một lượt: đọc → xếp loại → khớp → ĐỀ XUẤT.

KHÔNG tự đổi trạng thái. Một thư mở đầu "unfortunately" có thể là từ chối, mà
cũng có thể là câu mở đầu của thư đổi lịch phỏng vấn. Đoán sai mà tự ghi thì
bảng thành sai, và Vin không có cách nào biết là nó đã sai.

Thư dựng lại được QUÁ KHỨ: mỗi thư "thank you for applying" trong 30 ngày là
bằng chứng một lần đã nộp. Nên thư không khớp dòng nào mà là thư xác nhận thì
được phép ĐẺ RA một dòng mới — đó là lần nộp có thật, chỉ là app chưa biết.
"""

from __future__ import annotations

import sqlite3

from ..core.journal import SEARCH, log as jlog
from . import board, mail, sort


def store(conn: sqlite3.Connection, msg: dict, kind: str,
          company: str, app_id: int | None) -> bool:
    """Ghi một thư. Trả True nếu là thư MỚI."""
    found = conn.execute("SELECT id FROM message WHERE msg_id = ?",
                         (msg["msg_id"],)).fetchone()
    if found:
        return False
    conn.execute(
        "INSERT INTO message (msg_id, from_addr, from_name, subject,"
        " received_at, snippet, kind, company_guess, application_id, needs_you)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (msg["msg_id"], msg["from_addr"], msg["from_name"], msg["subject"],
         msg["received_at"], msg["snippet"], kind, company,
         app_id, int(kind != "other")))
    conn.commit()
    return True


def run(conn: sqlite3.Connection, days: int = mail.SINCE_DAYS) -> dict:
    """Một lượt quét. Trả về số đo, không trả về chữ."""
    address, password = mail.account(conn)
    if not address or not password:
        jlog.warn(SEARCH, "chưa cấu hình hộp thư — xem config/config.toml")
        return {"ok": False, "why": "chưa cấu hình"}

    jlog.progress(SEARCH, f"đọc thư {days} ngày")
    try:
        messages = mail.fetch(address, password, since_days=days)
    except Exception as exc:                 # noqa: BLE001
        jlog.error(SEARCH, f"đọc thư hỏng — {type(exc).__name__}: {exc}")
        return {"ok": False, "why": str(exc)}
    finally:
        jlog.done(SEARCH)

    seen = fresh = made = 0
    for msg in messages:
        seen += 1
        kind = sort.kind(msg)
        company = sort.company_of(msg)
        app_id = sort.match(conn, msg)

        # Thư xác nhận không khớp dòng nào = lần nộp app chưa biết. Dựng lại.
        if app_id is None and kind == board.SENT and company:
            app_id = board.add(conn, company, "", origin="mail",
                               applied_at=msg["received_at"])
            made += 1

        fresh += store(conn, msg, kind, company, app_id)

    jlog.ok(SEARCH, f"thư: đọc {seen} · mới {fresh} · dựng lại {made} lần nộp")
    return {"ok": True, "seen": seen, "fresh": fresh, "made": made}


def proposals(conn: sqlite3.Connection) -> list[dict]:
    """Thư đang ĐỀ XUẤT đổi trạng thái — Vin bấm mới đổi.

    Chỉ đề xuất khi trạng thái mới KHÁC trạng thái đang có; một thư xác nhận
    cho một dòng đã ở 'đã nộp' thì không có gì để hỏi.
    """
    out = []
    for r in conn.execute(
            "SELECT m.id, m.subject, m.snippet, m.kind, m.received_at,"
            " m.company_guess, a.id AS app_id, a.company, a.role, a.stage"
            " FROM message m LEFT JOIN application a ON a.id = m.application_id"
            " WHERE m.needs_you = 1 ORDER BY m.received_at DESC"):
        row = dict(r)
        if row["app_id"] and row["kind"] == row["stage"]:
            continue                       # đã đúng trạng thái, không hỏi lại
        out.append(row)
    return out


def settle(conn: sqlite3.Connection, message_id: int, accept: bool) -> None:
    """Vin trả lời một đề xuất. Nhận thì đổi trạng thái, bỏ thì im luôn."""
    row = conn.execute(
        "SELECT kind, subject, application_id FROM message WHERE id = ?",
        (message_id,)).fetchone()
    if row is None:
        return
    if accept and row["application_id"] and row["kind"] in board.STAGES:
        board.set_stage(conn, row["application_id"], row["kind"],
                        row["subject"][:90])
    conn.execute("UPDATE message SET needs_you = 0 WHERE id = ?", (message_id,))
    conn.commit()
