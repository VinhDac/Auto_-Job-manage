"""Web server chạy local — thư viện chuẩn, không cài gì thêm.

Chỉ định tuyến và vẽ. Mọi luật nghiệp vụ nằm ở profile/ và core/.
"""

from __future__ import annotations

import json
import socket
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ..core import db
from ..core.paths import web_dir
from ..profile import store
from ..profile.schema import LONGTEXT, MULTI, ROUNDS, TEXT, round_by_id
from . import render

HOST = "127.0.0.1"          # chỉ máy này truy cập được. Không mở ra mạng.
DEFAULT_PORT = 8765


def _form_to_answers(form: dict[str, list[str]], round_id: str) -> dict:
    """Đọc form theo ĐỊNH NGHĨA trong schema, không tin những gì trình duyệt gửi lên."""
    round_ = round_by_id(round_id)
    answers: dict = {}
    if round_ is None:
        return answers
    for question in round_.questions:
        values = form.get(question.id, [])
        if question.kind == MULTI:
            allowed = {o.value for o in question.options}
            answers[question.id] = [v for v in values if v in allowed]
        elif question.kind in (TEXT, LONGTEXT):
            answers[question.id] = values[0].strip() if values else ""
        else:                                    # SINGLE
            allowed = {o.value for o in question.options}
            answers[question.id] = values[0] if values and values[0] in allowed else ""
    return answers


class Handler(BaseHTTPRequestHandler):
    server_version = "jobbot"

    # --- tiện ích ---------------------------------------------------------
    def _send(self, body: bytes, status: int = 200, ctype: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, markup: str, status: int = 200):
        self._send(markup.encode("utf-8"), status)

    def _redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _conn(self) -> sqlite3.Connection:
        return db.connect()

    def log_message(self, fmt, *args):            # bớt ồn
        return

    # --- định tuyến -------------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/static/app.css":
            css = (web_dir() / "app.css").read_bytes()
            return self._send(css, ctype="text/css; charset=utf-8")

        conn = self._conn()
        try:
            answers = store.load(conn)

            if path == "/":
                nxt = store.next_unfinished_round(answers)
                return self._redirect(f"/profile/{nxt.id}" if nxt else "/profile")

            if path == "/profile":
                return self._html(
                    render.render_summary(answers, len(store.history(conn)), store.can_ingest(answers))
                )

            if path == "/api/profile":
                payload = {
                    "answers": answers,
                    "versions": len(store.history(conn)),
                    "can_ingest": store.can_ingest(answers),
                }
                return self._send(
                    json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                    ctype="application/json; charset=utf-8",
                )

            if path.startswith("/profile/"):
                round_ = round_by_id(path.rsplit("/", 1)[-1])
                if round_ is None:
                    return self._html(render.page("Không tìm thấy", "<h1>404</h1>"), 404)
                done = {r.id for r in ROUNDS if store.is_round_done(answers, r)}
                return self._html(render.render_round(round_, answers, done))

            self._html(render.page("Không tìm thấy", "<h1>404</h1>"), 404)
        finally:
            conn.close()

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/profile/"):
            return self._html(render.page("Không tìm thấy", "<h1>404</h1>"), 404)

        round_id = path.rsplit("/", 1)[-1]
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)

        conn = self._conn()
        try:
            store.save(conn, _form_to_answers(form, round_id), note=f"vòng: {round_id}")
            nxt = store.next_unfinished_round(store.load(conn))
            self._redirect(f"/profile/{nxt.id}" if nxt else "/profile")
        finally:
            conn.close()


def find_port(start: int = DEFAULT_PORT, tries: int = 20) -> int:
    for port in range(start, start + tries):
        with socket.socket() as sock:
            if sock.connect_ex((HOST, port)) != 0:
                return port
    raise RuntimeError(f"Không tìm được cổng trống từ {start}")


def serve(port: int | None = None) -> tuple[ThreadingHTTPServer, str]:
    port = port or find_port()
    httpd = ThreadingHTTPServer((HOST, port), Handler)
    return httpd, f"http://{HOST}:{port}/"
