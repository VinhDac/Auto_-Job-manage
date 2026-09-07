"""Web server chạy local — thư viện chuẩn, không cài gì thêm.

Chỉ định tuyến. Vẽ là việc của views/, dữ liệu là việc của core/ và mock.py.
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
from ..profile.schema import LONGTEXT, MULTI, SECTIONS, TEXT, section_by_id
from . import layout, live, mock
from .filters import JobFilter
from . import upload
from .views import cv as cvview
from .views import cvhealth, importcv
from .views import (home, jobs, pipeline, profile,
                    projects, settings, stats, queue)

HOST = "127.0.0.1"          # chỉ máy này truy cập được. Không mở ra mạng.
DEFAULT_PORT = 8765


def _split_other(raw: str) -> list[str]:
    """Ô 'add your own' của câu CHỌN-NHIỀU -> danh sách, ngăn bằng phẩy hoặc xuống dòng."""
    return [part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()]


def _form_to_answers(form: dict[str, list[str]], section_id: str) -> dict:
    """Đọc form theo ĐỊNH NGHĨA trong schema, không tin những gì trình duyệt gửi lên."""
    section = section_by_id(section_id)
    answers: dict = {}
    if section is None:
        return answers

    for question in section.questions:
        values = form.get(question.id, [])
        allowed = {o.value for o in question.options}
        other_raw = form.get(question.id + "__other", [""])[0] if question.allow_other else ""

        if question.kind == MULTI:
            picked = [v for v in values if v in allowed]
            extra = _split_other(other_raw)
            answers[question.id] = picked + [e for e in extra if e not in picked]
        elif question.kind in (TEXT, LONGTEXT):
            answers[question.id] = values[0].strip() if values else ""
        else:                                       # SINGLE
            # Câu chọn-một lấy NGUYÊN VĂN ô tự do — không cắt theo dấu phẩy.
            chosen = values[0] if values and values[0] in allowed else ""
            answers[question.id] = chosen or other_raw.strip()
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

    def _404(self):
        self._html(layout.page("Not found", "<h1>404</h1>"
                               "<p class=lead>No such page.</p>"), 404)

    def log_message(self, fmt, *args):            # bớt ồn
        return

    # --- định tuyến -------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)

        if path == "/static/app.css":
            return self._send((web_dir() / "app.css").read_bytes(),
                              ctype="text/css; charset=utf-8")

        pending = len(mock.proposals())          # TODO bước 5: đếm từ hàng đợi thật

        # --- ĐÃ NỐI DỮ LIỆU THẬT (bước 1) ---
        if path in ("/", "/jobs") or path.startswith("/jobs/"):
            conn = db.connect()
            try:
                if path == "/":
                    return self._html(home.render(
                        live.run_status(conn), live.counters(conn),
                        live.needs_you(conn), live.activity(conn), pending))
                if path == "/jobs":
                    flt = JobFilter.from_query(query)
                    return self._html(jobs.render(
                        live.jobs(conn, flt), flt, live.job_counts(conn, flt),
                        live.facets(conn), pending))
                parts = path.strip("/").split("/")
                found = live.job_detail(conn, parts[1])
                if not found:
                    return self._404()
                if len(parts) == 3 and parts[2] == "project":
                    import json as _json
                    from ..cv.build import wanted_skills
                    from ..profile import store as pstore
                    from ..projects.page import build as build_page, health
                    answers = pstore.load(conn)
                    explain = (_json.loads(found["score_json"])
                               if found.get("score_json") else None)
                    doc = build_page(answers, found["title"], found["company"],
                                     wanted_skills(explain, found["jd"]))
                    return self._html(projects.render_page(found, doc, health(doc), pending))
                if len(parts) == 3 and parts[2] == "cv":
                    import json as _json
                    from ..cv.build import build as build_cv
                    from ..profile import store as pstore
                    answers = pstore.load(conn)
                    explain = _json.loads(found["score_json"]) if found.get("score_json") else None
                    tailored = build_cv(answers, explain, found["jd"])
                    return self._html(cvview.render(found, tailored, pending))
                return self._html(jobs.render_detail(found, pending))
            finally:
                conn.close()

        # --- vẫn dùng dữ liệu giả (bước 4-6) ---
        if path == "/queue":
            return self._html(queue.render(mock.proposals(), pending))
        if path == "/pipeline":
            return self._html(pipeline.render(mock.pipeline(), mock.STAGES, pending))
        if path == "/projects":
            conn = db.connect()
            try:
                from ..cv.blocks import parse as parse_cv
                from ..projects.cluster import build as cluster_jobs
                answers = store.load(conn)
                mine = [b for b in parse_cv(answers.get("cv_text") or "")
                        if b.kind == "project"]
                return self._html(projects.render(cluster_jobs(conn, mine), mine, pending))
            finally:
                conn.close()
        if path == "/stats":
            return self._html(stats.render(mock.stats(), pending))
        if path == "/settings":
            conn = db.connect()
            try:
                return self._html(settings.render(
                    live.sources(conn), live.chrome_status(),
                    live.company_stats(conn), live.last_runs(conn), pending))
            finally:
                conn.close()

        # --- profile: đã nối backend thật ---
        conn = db.connect()
        try:
            answers = store.load(conn)
            if path == "/profile":
                return self._html(profile.render_summary(
                    answers, len(store.history(conn)),
                    store.missing_for_ingest(answers), pending))

            if path == "/profile/import":
                return self._html(importcv.render_form(pending))
            if path == "/profile/health":
                return self._html(cvhealth.render(answers.get("cv_text", ""), pending))

            if path == "/api/profile":
                payload = {"answers": answers, "versions": len(store.history(conn)),
                           "can_ingest": store.can_ingest(answers),
                           "missing_for_ingest": store.missing_for_ingest(answers)}
                return self._send(json.dumps(payload, ensure_ascii=False, indent=2).encode(),
                                  ctype="application/json; charset=utf-8")

            if path.startswith("/profile/"):
                section = section_by_id(path.rsplit("/", 1)[-1])
                if section is None:
                    return self._404()
                done = {s.id for s in SECTIONS if store.is_section_done(answers, s)}
                nxt = store.next_section(section.id)
                label = f"Save and continue → {nxt.title}" if nxt else "Save and review profile"
                return self._html(profile.render_section(section, answers, done, label, pending))

            self._404()
        finally:
            conn.close()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        ctype = self.headers.get("Content-Type", "")
        raw = self.rfile.read(length)

        if path == "/profile/import":
            return self._import_cv(ctype, raw)

        form = parse_qs(raw.decode("utf-8"), keep_blank_values=True)

        if path == "/profile/import/save":
            return self._save_import(form)

        if path == "/queue":
            # TODO backend: thực thi đề xuất đã duyệt. Hiện chỉ quay lại trang.
            return self._redirect("/queue")

        if path.startswith("/profile/"):
            section_id = path.rsplit("/", 1)[-1]
            conn = db.connect()
            try:
                store.save(conn, _form_to_answers(form, section_id), note=f"section: {section_id}")
                nxt = store.next_section(section_id)
                return self._redirect(f"/profile/{nxt.id}" if nxt else "/profile")
            finally:
                conn.close()

        self._404()


    # --- nhập CV ----------------------------------------------------------
    def _import_cv(self, ctype: str, raw: bytes):
        """Đọc file hoặc chữ dán vào rồi hiện ĐỀ XUẤT — chưa ghi gì cả."""
        from ..profile.import_cv import ReadError, propose, read
        pending = len(mock.proposals())
        try:
            fields = upload.parse(ctype, raw) if "multipart" in ctype else {}
            filename, blob = fields.get("file", ("", b""))
            pasted = fields.get("pasted", ("", b""))[1].decode("utf-8", "replace").strip()
            text = read(filename, blob) if blob else pasted
            if not text.strip():
                raise ReadError("No file chosen and nothing pasted.")
        except (upload.TooBig, ReadError) as exc:
            return self._html(importcv.render_form(pending, str(exc)))
        except Exception as exc:                        # noqa: BLE001
            return self._html(importcv.render_form(pending, f"Could not read it: {exc}"))

        conn = db.connect()
        try:
            found = propose(text, store.load(conn))
        finally:
            conn.close()
        self._html(importcv.render_review(found, text, pending))

    def _save_import(self, form: dict):
        """Chỉ ghi những ô người dùng để tick. Không đè ô đã có sẵn."""
        from ..profile.import_cv import propose
        text = form.get("text", [""])[0]
        wanted = set(form.get("accept", []))
        conn = db.connect()
        try:
            found = {p.field: p.value for p in propose(text, store.load(conn))}
            picked = {k: v for k, v in found.items() if k in wanted}
            if picked:
                store.save(conn, picked, note=f"imported CV ({len(picked)} fields)")
        finally:
            conn.close()
        self._redirect("/profile")


def find_port(start: int = DEFAULT_PORT, tries: int = 20) -> int:
    for port in range(start, start + tries):
        with socket.socket() as sock:
            if sock.connect_ex((HOST, port)) != 0:
                return port
    raise RuntimeError(f"No free port from {start}")


def serve(port: int | None = None) -> tuple[ThreadingHTTPServer, str]:
    port = port or find_port()
    return ThreadingHTTPServer((HOST, port), Handler), f"http://{HOST}:{port}/"
