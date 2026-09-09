"""Web server chạy local — thư viện chuẩn, không cài gì thêm.

Chỉ định tuyến. Vẽ là việc của views/, dữ liệu là việc của core/ và live.py.
"""

from __future__ import annotations

import json
import queue
import socket
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from ..core import db
from ..core import journal, scheduler as sched
from ..core.paths import web_dir
from ..profile import store
from ..profile.schema import LONGTEXT, MULTI, SECTIONS, TEXT, section_by_id
from . import layout, live
from . import upload
from .views import cv as cvview
from .views import cvhealth, importcv
from .filters import JobFilter
from .views import home, jobs, profile, projects, search, settings

HOST = "127.0.0.1"          # chỉ máy này truy cập được. Không mở ra mạng.
DEFAULT_PORT = 8765


def _segments(path: str) -> list[str]:
    """Tách path thành từng mảnh rồi giải mã TỪNG mảnh.

    Trình duyệt mã hoá khoảng trắng thành %20, nên khoá cụm 'machine learning'
    tới đây là 'machine%20learning' — không khớp với gì cả. Phải giải mã.

    Giải mã cả chuỗi RỒI mới tách là sai: '%2F' sẽ hoá thành '/' và tự đẻ ra
    một mảnh mới. Tách trước, giải mã sau thì không đẻ được.
    """
    return [unquote(part) for part in path.strip("/").split("/") if part]


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
    # --- dòng sự kiện đẩy xuống trình duyệt --------------------------------
    def _events(self):
        """SSE: một kết nối sống lâu, server đẩy xuống, trình duyệt không hỏi.

        Chọn SSE chứ không polling: nhật ký chỉ đi MỘT chiều từ máy xuống màn
        hình. Polling mỗi giây thì 24/7 là 86.400 lượt/ngày cho phần lớn là
        "chưa có gì mới". WebSocket thì thừa nguyên chiều ngược lại.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        chan = journal.log.subscribe()
        try:
            # Gửi ngay trạng thái hiện tại — mở tab giữa chừng vẫn thấy đúng,
            # không phải chờ sự kiện kế tiếp mới biết máy đang làm gì.
            self._send_event({"type": "hello", **_state_payload(),
                              "events": [e.as_dict()
                                         for e in journal.log.tail(limit=40)][::-1]})
            while True:
                try:
                    self._send_event(chan.get(timeout=20))
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")     # giữ kết nối, proxy không cắt
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ValueError):
            pass                     # đóng tab là chuyện thường, không phải lỗi
        finally:
            journal.log.unsubscribe(chan)

    def _send_event(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        self.wfile.write(f"data: {body}\n\n".encode())
        self.wfile.flush()

    def _json(self, payload: dict, status: int = 200):
        return self._send(json.dumps(payload, ensure_ascii=False).encode(),
                          status=status, ctype="application/json; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)

        if path == "/static/app.css":
            return self._send((web_dir() / "app.css").read_bytes(),
                              ctype="text/css; charset=utf-8")
        if path == "/static/live.js":
            return self._send((web_dir() / "live.js").read_bytes(),
                              ctype="text/javascript; charset=utf-8")
        if path == "/events":
            return self._events()
        if path == "/api/state":
            return self._json(_state_payload())

        # --- ĐÃ NỐI DỮ LIỆU THẬT (bước 1) ---
        if path == "/" or path.startswith("/jobs/"):
            conn = db.connect()
            try:
                if path == "/":
                    return self._html(home.render(
                        live.run_status(conn), live.counters(conn),
                        live.needs_you(conn), live.activity(conn),
                        days=live.per_day(conn), chances=live.chances(conn),
                        funnel=live.funnel(conn)))
                parts = _segments(path)
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
                    return self._html(projects.render_page(found, doc, health(doc)))
                if len(parts) == 3 and parts[2] == "cv":
                    import json as _json
                    from ..cv.build import build as build_cv
                    from ..profile import store as pstore
                    answers = pstore.load(conn)
                    explain = _json.loads(found["score_json"]) if found.get("score_json") else None
                    tailored = build_cv(answers, explain, found["jd"])
                    return self._html(cvview.render(found, tailored))
                return self._html(jobs.render_detail(found))
            finally:
                conn.close()

        if path.startswith("/projects/"):
            conn = db.connect()
            try:
                from ..cv.blocks import parse as parse_cv
                from ..projects.cluster import build as cluster_jobs
                from ..projects.pipeline import run as run_pipeline
                from ..projects.research import study
                answers = store.load(conn)
                mine = [b for b in parse_cv(answers.get("cv_text") or "")
                        if b.kind == "project"]
                key = _segments(path)[-1]
                found = next((c for c in cluster_jobs(conn, mine) if c.key == key), None)
                if found is None:
                    return self._404()
                from ..projects.pipeline import research_cached
                findings = study(conn, found)
                # Chỉ ĐỌC cache. Mở Chrome trong lúc vẽ trang là sai — việc nặng
                # thuộc về vòng quét nền, xem scripts/research.py.
                findings, source = research_cached(conn, found, findings)
                outcome = run_pipeline(conn, findings, [b.title for b in mine])
                return self._html(projects.render_brief(found, findings, outcome))
            finally:
                conn.close()

        if path == "/projects":
            conn = db.connect()
            try:
                from ..cv.blocks import parse as parse_cv
                from ..projects.cluster import build as cluster_jobs
                answers = store.load(conn)
                mine = [b for b in parse_cv(answers.get("cv_text") or "")
                        if b.kind == "project"]
                found = cluster_jobs(conn, mine)
                return self._html(projects.render(
                    found, mine,
                    stats=live.project_stats(conn, found, mine),
                    settings=live.project_settings(conn),
                    sizes=live.cluster_sizes(conn, found)))
            finally:
                conn.close()
        if path == "/search":
            conn = db.connect()
            try:
                flt = JobFilter.from_query(query)
                return self._html(search.render(
                    jobs=live.jobs(conn, flt), flt=flt,
                    counts=live.job_counts(conn, flt),
                    sieve=live.sieve(conn)))
            finally:
                conn.close()

        if path == "/settings":
            # Trả MẢNH HTML, không phải cả trang: live.js nạp nó vào tấm phủ.
            # Cài đặt là menu bấm ra rồi đóng lại, không phải một tab.
            conn = db.connect()
            try:
                return self._html(settings.render(**live.settings(conn)))
            finally:
                conn.close()

        # --- profile: đã nối backend thật ---
        conn = db.connect()
        try:
            answers = store.load(conn)
            if path == "/profile":
                return self._html(profile.render_summary(
                    answers, len(store.history(conn)),
                    store.missing_for_ingest(answers)))

            if path == "/profile/import":
                return self._html(importcv.render_form())
            if path == "/profile/health":
                return self._html(cvhealth.render(answers.get("cv_text", "")))

            if path == "/api/profile":
                payload = {"answers": answers, "versions": len(store.history(conn)),
                           "can_ingest": store.can_ingest(answers),
                           "missing_for_ingest": store.missing_for_ingest(answers)}
                return self._send(json.dumps(payload, ensure_ascii=False, indent=2).encode(),
                                  ctype="application/json; charset=utf-8")

            if path.startswith("/profile/"):
                section = section_by_id(_segments(path)[-1])
                if section is None:
                    return self._404()
                done = {s.id for s in SECTIONS if store.is_section_done(answers, s)}
                nxt = store.next_section(section.id)
                label = f"Save and continue → {nxt.title}" if nxt else "Save and review profile"
                return self._html(profile.render_section(section, answers, done, label))

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

        if path == "/api/run":
            runner = sched.current()
            threading.Thread(target=runner.scan_once, daemon=True,
                             name="scan-manual").start()
            return self._json({"ok": True, "state": "running"})

        if path == "/settings":
            conn = db.connect()
            try:
                from ..core import llm, prefs
                prefs.put(conn, prefs.SCAN_EVERY, form.get("every", ["60"])[0])
                prefs.put(conn, prefs.HOURS_FROM, form.get("from", ["8"])[0])
                prefs.put(conn, prefs.HOURS_TO, form.get("to", ["22"])[0])
                engine = form.get("engine", [""])[0]
                prefs.put(conn, prefs.LLM_ENGINE,
                          engine if engine in llm.ENGINES else "")
                journal.log.emit(journal.SYSTEM, "cài đặt đã đổi")
                return self._html(settings.render(**live.settings(conn)))
            finally:
                conn.close()

        if path == "/api/sieve":
            # Lưới GIỮ/BỎ nằm trong HỒ SƠ. Lưu xong thì mọi tin tự thành cần
            # phán lại (judged_profile lệch phiên bản) — derive lo phần đó.
            conn = db.connect()
            try:
                store.save(conn, {
                    # Ô thẻ gửi lên MỘT DANH SÁCH giá trị, mỗi thẻ một cái.
                    # Bỏ trùng, giữ thứ tự người dùng xếp.
                    "job_titles": "\n".join(dict.fromkeys(
                        t.strip() for t in form.get("job_titles", []) if t.strip())),
                    "seniority": form.get("seniority", []),
                    "markets": form.get("markets", []),
                }, note="lưới lọc sửa ở tab Search")
            finally:
                conn.close()

            def _rejudge():
                from ..core.derive import derive
                conn = db.connect()
                try:
                    journal.log.emit(journal.SEARCH, "lưới lọc đổi — phán lại tất cả")
                    derive(conn)
                except Exception as exc:            # noqa: BLE001
                    journal.log.error(journal.SEARCH,
                                      f"phán lại hỏng: {type(exc).__name__} — {exc}")
                finally:
                    journal.log.done(journal.SEARCH)
                    journal.log.done(journal.SCORE)
                    conn.close()

            # Chạy nền rồi quay lại ngay: 1,1 giây vẫn là 1,1 giây trình duyệt
            # đứng hình, mà nhật ký hiện tiến độ rồi nên không cần chờ.
            threading.Thread(target=_rejudge, daemon=True, name="rejudge").start()
            return self._redirect("/search")

        if path == "/api/pause":
            runner = sched.current()
            runner.resume() if runner.paused else runner.pause()
            return self._json({"ok": True, **_state_payload()})

        if path.startswith("/profile/"):
            section_id = _segments(path)[-1]
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
        try:
            fields = upload.parse(ctype, raw) if "multipart" in ctype else {}
            filename, blob = fields.get("file", ("", b""))
            pasted = fields.get("pasted", ("", b""))[1].decode("utf-8", "replace").strip()
            text = read(filename, blob) if blob else pasted
            if not text.strip():
                raise ReadError("No file chosen and nothing pasted.")
        except (upload.TooBig, ReadError) as exc:
            return self._html(importcv.render_form(str(exc)))
        except Exception as exc:                        # noqa: BLE001
            return self._html(importcv.render_form(f"Could not read it: {exc}"))

        conn = db.connect()
        try:
            found = propose(text, store.load(conn))
        finally:
            conn.close()
        self._html(importcv.render_review(found, text))

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


def _state_payload() -> dict:
    """Trạng thái THẬT của vòng chạy, không phải chuỗi cứng.

    live.run_status() cũ trả 'idle' kể cả lúc đang quét, vì nó chỉ nhìn bảng
    source_run chứ không hỏi scheduler. Đây là chỗ duy nhất biết sự thật.
    """
    runner = sched.current()
    return {"state": runner.state(),
            "next_in": runner.next_in() // 60,      # phút
            "running": journal.log.running()}
