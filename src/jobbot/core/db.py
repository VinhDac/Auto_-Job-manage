"""SQLite — một file, không cần server, restart không mất dữ liệu.

Migration chạy tiến, không lùi. Mỗi thay đổi schema thêm một phần tử vào
MIGRATIONS, không bao giờ sửa phần tử cũ — DB đang chạy thật ngoài kia.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .paths import db_path

# Chỉ THÊM vào cuối. Không sửa, không xoá phần tử đã có.
MIGRATIONS: list[str] = [
    # 1 — hồ sơ người dùng, lưu theo phiên bản (M0)
    """
    CREATE TABLE profile_version (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT    NOT NULL,
        note       TEXT
    );
    CREATE TABLE profile_answer (
        version_id  INTEGER NOT NULL REFERENCES profile_version(id) ON DELETE CASCADE,
        question_id TEXT    NOT NULL,
        value_json  TEXT    NOT NULL,
        PRIMARY KEY (version_id, question_id)
    );
    """,
    # 2 — tin tuyển dụng: raw (nguyên văn) / posting (đã chuẩn hoá) / nhật ký
    """
    CREATE TABLE raw_posting (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source      TEXT    NOT NULL,     -- 'linkedin' | 'greenhouse:monzo'
        source_id   TEXT    NOT NULL,     -- id bên nguồn
        url         TEXT,
        fetched_at  TEXT    NOT NULL,
        payload     TEXT    NOT NULL,     -- JSON nguyên văn, không đụng vào
        UNIQUE (source, source_id)
    );

    CREATE TABLE posting (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_id       INTEGER NOT NULL REFERENCES raw_posting(id) ON DELETE CASCADE,
        source       TEXT    NOT NULL,
        title        TEXT    NOT NULL,
        company      TEXT    NOT NULL,
        location     TEXT    NOT NULL DEFAULT '',
        remote       INTEGER NOT NULL DEFAULT 0,
        salary       TEXT    NOT NULL DEFAULT '',
        url          TEXT    NOT NULL DEFAULT '',
        posted_at    TEXT    NOT NULL DEFAULT '',
        description  TEXT    NOT NULL DEFAULT '',
        fingerprint  TEXT    NOT NULL,    -- công ty + chức danh đã chuẩn hoá
        group_id     TEXT,                -- cùng group_id = cùng một việc
        kept         INTEGER NOT NULL DEFAULT 1,   -- 0 = bị lọc bỏ
        drop_reason  TEXT    NOT NULL DEFAULT '',
        UNIQUE (raw_id)
    );
    CREATE INDEX posting_fp    ON posting(fingerprint);
    CREATE INDEX posting_group ON posting(group_id);
    CREATE INDEX posting_kept  ON posting(kept);

    CREATE TABLE source_run (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        source     TEXT    NOT NULL,
        started_at TEXT    NOT NULL,
        ok         INTEGER NOT NULL,
        fetched    INTEGER NOT NULL DEFAULT 0,
        new_rows   INTEGER NOT NULL DEFAULT 0,
        error      TEXT    NOT NULL DEFAULT ''
    );

    -- Ghi từ BƯỚC 1. Thiếu thì đến bước 6 không có gì để đếm và không lấy lại được.
    CREATE TABLE audit (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        at     TEXT NOT NULL,
        kind   TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX audit_at ON audit(at);
    """,
    # 3 — vòng đời ứng tuyển + thư đọc từ hộp thư
    """
    CREATE TABLE application (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        company       TEXT    NOT NULL,
        company_key   TEXT    NOT NULL,          -- tên đã chuẩn hoá, để khớp
        role          TEXT    NOT NULL DEFAULT '',
        posting_id    INTEGER REFERENCES posting(id),
        origin        TEXT    NOT NULL DEFAULT 'mail',   -- mail | manual | auto
        applied_at    TEXT    NOT NULL,
        stage         TEXT    NOT NULL DEFAULT 'applied',
        last_event_at TEXT    NOT NULL DEFAULT '',
        last_event    TEXT    NOT NULL DEFAULT '',
        UNIQUE (company_key, role)
    );
    CREATE INDEX application_stage ON application(stage);

    CREATE TABLE message (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        msg_id         TEXT    NOT NULL UNIQUE,  -- Message-ID của thư
        from_addr      TEXT    NOT NULL DEFAULT '',
        from_name      TEXT    NOT NULL DEFAULT '',
        subject        TEXT    NOT NULL DEFAULT '',
        received_at    TEXT    NOT NULL DEFAULT '',
        snippet        TEXT    NOT NULL DEFAULT '',
        kind           TEXT    NOT NULL DEFAULT 'other',
        company_guess  TEXT    NOT NULL DEFAULT '',
        application_id INTEGER REFERENCES application(id),
        needs_you      INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX message_kind ON message(kind);
    CREATE INDEX message_app  ON message(application_id);
    """,
    # 4 — mốc thời gian dạng số. posted_at là chuỗi và mỗi nguồn một kiểu
    # (ISO của Greenhouse/Lever, unix của Arbeitnow) nên SQL không so được.
    """
    ALTER TABLE posting ADD COLUMN posted_ts INTEGER NOT NULL DEFAULT 0;
    CREATE INDEX posting_ts ON posting(posted_ts);
    """,
    # 5 — điểm khớp. score NULL = chưa chấm HOẶC không đọc được yêu cầu;
    # score_conf phân biệt hai trường hợp đó.
    """
    ALTER TABLE posting ADD COLUMN score INTEGER;
    ALTER TABLE posting ADD COLUMN score_conf TEXT NOT NULL DEFAULT '';
    ALTER TABLE posting ADD COLUMN score_json TEXT NOT NULL DEFAULT '';
    CREATE INDEX posting_score ON posting(score);
    """,
    # 6 — công ty mục tiêu. Đi thẳng trang tuyển dụng của họ thay vì qua
    # board trung gian: tên công ty không mơ hồ, JD nguyên bản, và có sẵn
    # đúng form để nộp ở bước 5.
    """
    CREATE TABLE company (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        name         TEXT    NOT NULL,
        key          TEXT    NOT NULL UNIQUE,     -- tên đã chuẩn hoá
        domain       TEXT    NOT NULL DEFAULT '',
        careers_url  TEXT    NOT NULL DEFAULT '',
        ats          TEXT    NOT NULL DEFAULT '', -- greenhouse|lever|ashby|workday|...
        ats_slug     TEXT    NOT NULL DEFAULT '',
        is_agency    INTEGER NOT NULL DEFAULT 0,  -- 1 = môi giới, không phải chủ việc
        checked_at   TEXT    NOT NULL DEFAULT '',
        roles_found  INTEGER NOT NULL DEFAULT 0,
        note         TEXT    NOT NULL DEFAULT ''
    );
    CREATE INDEX company_ats ON company(ats);
    ALTER TABLE posting ADD COLUMN via_agency INTEGER NOT NULL DEFAULT 0;
    """,
    # 7 — `kept` mặc định 1 nghĩa là tin vừa nạp đã được coi là "giữ" trước khi
    # vòng lọc chạy. Bất cứ ai đọc DB giữa hai bước đó đều thấy tin chưa lọc.
    # Mặc định đúng là 0: chưa phán thì chưa hiện.
    """
    CREATE TABLE posting_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_id INTEGER NOT NULL REFERENCES raw_posting(id) ON DELETE CASCADE,
        source TEXT NOT NULL, title TEXT NOT NULL, company TEXT NOT NULL,
        location TEXT NOT NULL DEFAULT '', remote INTEGER NOT NULL DEFAULT 0,
        salary TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
        posted_at TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
        fingerprint TEXT NOT NULL, group_id TEXT,
        kept INTEGER NOT NULL DEFAULT 0,           -- 0 = chưa phán HOẶC đã bị lọc
        drop_reason TEXT NOT NULL DEFAULT 'not judged yet',
        posted_ts INTEGER NOT NULL DEFAULT 0,
        score INTEGER, score_conf TEXT NOT NULL DEFAULT '',
        score_json TEXT NOT NULL DEFAULT '',
        via_agency INTEGER NOT NULL DEFAULT 0,
        UNIQUE (raw_id)
    );
    INSERT INTO posting_new SELECT id, raw_id, source, title, company, location,
        remote, salary, url, posted_at, description, fingerprint, group_id, kept,
        drop_reason, posted_ts, score, score_conf, score_json, via_agency FROM posting;
    DROP TABLE posting;
    ALTER TABLE posting_new RENAME TO posting;
    CREATE INDEX posting_fp    ON posting(fingerprint);
    CREATE INDEX posting_group ON posting(group_id);
    CREATE INDEX posting_kept  ON posting(kept);
    CREATE INDEX posting_ts    ON posting(posted_ts);
    CREATE INDEX posting_score ON posting(score);
    """,
    # 8 — sửa ba lỗi LÕI, không phải vá:
    #
    # (a) Tầng raw không thật sự raw. `posting.description` là bản DUY NHẤT của
    #     mô tả; strip_html sai là mất gốc, mà tin LinkedIn hết hạn thì không
    #     fetch lại được. Giờ giữ nguyên văn trong raw_posting.body.
    #
    # (b) Phán quyết (kept/score) không gắn với PHIÊN BẢN hồ sơ và PHIÊN BẢN
    #     luật đã sinh ra nó. Đổi hồ sơ hay đổi luật thì mọi phán quyết cũ
    #     thành sai — im lặng, không ai biết cái nào còn dùng được.
    #
    # (c) Không có cách tính lại toàn bộ tầng suy diễn từ tầng raw.
    """
    ALTER TABLE raw_posting ADD COLUMN body TEXT NOT NULL DEFAULT '';
    ALTER TABLE posting ADD COLUMN judged_profile INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE posting ADD COLUMN judged_rules TEXT NOT NULL DEFAULT '';
    ALTER TABLE posting ADD COLUMN scored_rules TEXT NOT NULL DEFAULT '';
    CREATE INDEX posting_judged ON posting(judged_profile, judged_rules);
    """,
    # 9 — nguồn hỏng phải TRÔNG khác nguồn chạy tốt.
    # Trước đây vòng đọc kỹ nuốt mọi ngoại lệ (`except Exception: continue`),
    # nên một nguồn đổi giao diện và hỏng 100% trông y hệt nguồn bình thường:
    # ok=1, không có mô tả nào, không ai biết.
    """
    ALTER TABLE source_run ADD COLUMN attempted INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE source_run ADD COLUMN failed INTEGER NOT NULL DEFAULT 0;
    """,
    # 10 — "khớp" khác "có cửa". Điểm khớp cao ở một tin đòi PhD và 5 năm kinh
    # nghiệm không nói lên gì về xác suất được gọi. Tách hai thứ ra.
    """
    ALTER TABLE posting ADD COLUMN realism TEXT NOT NULL DEFAULT '';
    ALTER TABLE posting ADD COLUMN realism_why TEXT NOT NULL DEFAULT '';
    ALTER TABLE posting ADD COLUMN deadline TEXT NOT NULL DEFAULT '';
    ALTER TABLE posting ADD COLUMN deadline_ts INTEGER NOT NULL DEFAULT 0;
    CREATE INDEX posting_realism ON posting(realism);
    """,
    # 11 — điểm cũng phải gắn phiên bản HỒ SƠ, không chỉ phiên bản luật.
    # Thiếu cột này thì đổi hồ sơ chỉ lọc lại chứ không chấm lại: 72/204 tin
    # đang giữ bị đóng băng ở score=NULL vì chúng được chấm lúc còn rỗng mô tả.
    # DEFAULT 0 = "chưa chấm với hồ sơ nào" -> mọi tin cũ tự thành cần chấm lại.
    """
    ALTER TABLE posting ADD COLUMN scored_profile INTEGER NOT NULL DEFAULT 0;
    """,
    # 12 — nhật ký chạy: mỗi dòng thuộc một LUỒNG và có MỨC.
    # Nhờ luồng mà tab Search chỉ hiện việc của Search; nhờ mức mà lỗi không
    # nằm lẫn với dòng thường. Dòng cũ không có -> mặc định 'system'/'info'.
    """
    ALTER TABLE audit ADD COLUMN stream TEXT NOT NULL DEFAULT 'system';
    ALTER TABLE audit ADD COLUMN level  TEXT NOT NULL DEFAULT 'info';
    CREATE INDEX audit_stream ON audit(stream, id);
    """,
    # 13 — tuỳ chọn của APP (khác profile_answer: đó là hồ sơ NGƯỜI DÙNG).
    # Chỗ để nhớ "có tự quét khi mở app không" qua các lần khởi động.
    """
    CREATE TABLE pref (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # 14 — KHO PROJECT. Trước đây pipeline sinh đề bài rồi vẽ ra màn hình và
    # VỨT: mỗi lần mở trang chạy lại cả bảy chặng, không có gì tích lại.
    # Một project làm mất 2-3 ngày thì nó phải sống lâu hơn một lần vẽ trang.
    #
    # skills = TRỤC (kỹ năng nào project này chứng minh được)
    # industries = NHÃN (ngành nào kể được câu chuyện này)
    # Trục là kỹ năng chứ không phải nhóm JD: nhóm sinh ra từ dữ liệu nên đổi
    # là đề bài mồ côi — đã xảy ra thật với nhóm ma 'excel'.
    """
    CREATE TABLE project (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        question    TEXT NOT NULL,
        skills      TEXT NOT NULL DEFAULT '',
        industries  TEXT NOT NULL DEFAULT '',
        state       TEXT NOT NULL DEFAULT 'de_bai',
        brief_json  TEXT NOT NULL DEFAULT '',
        link        TEXT NOT NULL DEFAULT '',
        made_at     TEXT NOT NULL
    );
    CREATE INDEX project_state ON project(state);
    """,
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")   # đọc được trong lúc đang ghi (chạy 24/7)
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Chạy các migration còn thiếu. Trả về số migration vừa chạy."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    ran = 0
    for index in range(current, len(MIGRATIONS)):
        conn.executescript(MIGRATIONS[index])
        conn.execute(f"PRAGMA user_version = {index + 1}")
        conn.commit()
        ran += 1
    return ran
