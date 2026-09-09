"""Chỗ cắm LLM — ba engine, cùng một giao diện.

    none         không LLM. Trả None, bên gọi dùng bản dựng bằng luật.
    claude_code   ghi yêu cầu vào hàng đợi, Claude trả lời trong phiên. Không cần key.
    api           Anthropic API. Cần ANTHROPIC_API_KEY.

Luật cứng, khác nhau theo việc:

    CV, trang kết quả  ->  LLM chỉ được CHỌN và SẮP XẾP. Bịa = hỏng.
    Đề bài project     ->  LLM ĐƯỢC nghĩ ra cái mới. Đó chính là việc của nó.

Và mọi thứ LLM sinh ra đều phải qua bộ kiểm tra bằng luật trước khi dùng —
xem projects/brief.py. Không tin LLM, chỉ tin thứ kiểm được.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass

ENGINES = ("none", "claude_code", "api")


@dataclass
class Answer:
    text: str
    engine: str
    pending: bool = False       # claude_code: đã xếp hàng, chờ trả lời


DEFAULT_ENGINE = "claude_code"


def env_override() -> str:
    """Máy đặt bằng biến môi trường, nếu có. Rỗng = không ai ép."""
    name = os.environ.get("JOBBOT_LLM", "").strip()
    return name if name in ENGINES else ""


def engine_name() -> str:
    """Máy LLM đang dùng.

    Thứ tự: biến môi trường -> menu Cài đặt -> mặc định.

    Biến môi trường ĐỨNG TRƯỚC vì nó là lệnh ép cho riêng lần chạy này —
    quy ước chung, và cũng là thứ bài test dùng để dựng tình huống. Đọc pref
    trước thì test đặt JOBBOT_LLM=none xong vẫn lấy phải lựa chọn trong DB
    thật của người dùng.

    Menu Cài đặt phải NÓI RA khi bị biến môi trường đè, nếu không người dùng
    chọn xong mà không có gì đổi.
    """
    forced = env_override()
    if forced:
        return forced
    try:
        from . import prefs
        from .db import connect
        conn = connect()
        try:
            chosen = prefs.get(conn, prefs.LLM_ENGINE).strip()
        finally:
            conn.close()
    except Exception:                       # noqa: BLE001
        chosen = ""
    return chosen if chosen in ENGINES else DEFAULT_ENGINE


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_request (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            purpose    TEXT NOT NULL,
            prompt     TEXT NOT NULL,
            answer     TEXT NOT NULL DEFAULT '',
            answered_at TEXT NOT NULL DEFAULT ''
        )""")
    conn.commit()


def ask(conn: sqlite3.Connection, purpose: str, prompt: str) -> Answer:
    """Hỏi LLM. `claude_code` trả về pending — câu trả lời tới sau."""
    engine = engine_name()
    if engine == "none":
        return Answer("", "none")

    if engine == "api":
        return Answer(_ask_api(prompt), "api")

    ensure_table(conn)
    # Tra theo PURPOSE, không theo toàn bộ prompt.
    #
    # Khoá bằng prompt thì chỉ cần một chữ đổi — thứ tự công ty, một tin mới
    # trong nhóm — là câu trả lời cũ không bao giờ khớp, và hệ thống xếp hàng
    # lại vô hạn. Purpose đã đủ định danh (nó chứa tên nhóm).
    row = conn.execute(
        "SELECT answer FROM llm_request WHERE purpose = ? AND answer != ''"
        " ORDER BY id DESC LIMIT 1", (purpose,)).fetchone()
    if row:
        return Answer(row["answer"], "claude_code")

    from .postings import now
    waiting = conn.execute(
        "SELECT id FROM llm_request WHERE purpose = ? AND answer = ''"
        " ORDER BY id DESC LIMIT 1", (purpose,)).fetchone()
    if waiting:                       # đã xếp hàng rồi, đừng xếp thêm bản trùng
        conn.execute("UPDATE llm_request SET prompt = ? WHERE id = ?",
                     (prompt, waiting["id"]))
        conn.commit()
        return Answer("", "claude_code", pending=True)

    conn.execute("INSERT INTO llm_request (created_at, purpose, prompt)"
                 " VALUES (?,?,?)", (now(), purpose, prompt))
    conn.commit()
    return Answer("", "claude_code", pending=True)


def answer_request(conn: sqlite3.Connection, request_id: int, text: str) -> None:
    """Claude trong phiên trả lời một yêu cầu đang chờ."""
    from .postings import now
    conn.execute("UPDATE llm_request SET answer = ?, answered_at = ? WHERE id = ?",
                 (text, now(), request_id))
    conn.commit()


def pending(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    ensure_table(conn)
    return conn.execute(
        "SELECT id, purpose, prompt, created_at FROM llm_request"
        " WHERE answer = '' ORDER BY id LIMIT ?", (limit,)).fetchall()


def _ask_api(prompt: str) -> str:
    """Gọi thẳng Anthropic API. Không cài SDK — dùng urllib."""
    import urllib.request

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return ""
    body = json.dumps({
        "model": os.environ.get("JOBBOT_LLM_MODEL", "claude-sonnet-5"),
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception:                       # noqa: BLE001
        return ""


def drop(conn: sqlite3.Connection, ids: list[int]) -> int:
    """Bỏ hẳn mấy yêu cầu đang chờ. Chỉ bỏ cái CHƯA trả lời — câu trả lời đã
    có là dữ liệu thật, xoá đi là mất công người ngồi chép."""
    if not ids:
        return 0
    marks = ",".join("?" for _ in ids)
    cur = conn.execute(
        f"DELETE FROM llm_request WHERE answer = '' AND id IN ({marks})", ids)
    conn.commit()
    return cur.rowcount
