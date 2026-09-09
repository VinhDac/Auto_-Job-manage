"""Bộ lọc do NGƯỜI DÙNG điều khiển, trạng thái nằm trong URL.

Khác với `ingest/filter.py`: cái kia chạy lúc quét, quyết định tin nào GIỮ trong DB.
Cái này chạy lúc xem, quyết định tin nào HIỆN ra — không xoá gì, đổi ý là bấm lại.

Trạng thái nằm hết trên URL (`/search?q=quant&show=dropped`) nên:
  - nút Back của trình duyệt chạy đúng
  - lưu được link về đúng bộ lọc đang xem
  - không cần JavaScript, không cần lưu session

Truy vấn LUÔN dùng tham số ràng buộc — không bao giờ nối chuỗi vào SQL.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

SHOW = [("matched", "Matched"), ("dropped", "Filtered out"), ("all", "Everything")]
LOC = [("", "Anywhere"), ("london", "London"), ("uk", "UK"),
       ("remote", "Remote"), ("other", "Outside UK")]
DAYS = [("", "Any time"), ("7", "Last 7 days"), ("30", "Last 30 days"), ("90", "Last 90 days")]
SORT = [("score", "Best match"), ("new", "Newest first"), ("old", "Oldest first"),
        ("company", "Company"), ("title", "Title")]
BAND = [("", "Any score"), ("75", "75+"), ("60", "60+"), ("none", "Not scorable")]
# Dùng "all", KHÔNG dùng chuỗi rỗng: chuỗi rỗng bị coi là "chưa chọn" nên rơi
# về mặc định, và người dùng không có cách nào bảo "cho tôi xem cả hai".
VIA = [("direct", "Direct employers"), ("all", "Include agencies"),
       ("agency", "Agencies only")]
# "Khớp" và "có cửa" là hai câu hỏi khác nhau — lọc riêng
CHANCE = [("", "Any"), ("likely", "Worth applying"), ("possible", "Maybe"),
          ("unlikely", "Long shot"), ("unknown", "Can't tell")]

UK_LIKE = ("london", "united kingdom", "england", "scotland", "wales", "manchester",
           "edinburgh", "cambridge", "oxford", "bristol", "leeds", "birmingham")


PER_PAGE = 50


@dataclass
class JobFilter:
    """company/source chọn được NHIỀU (ô tích). Còn lại là dải chồng nhau
    hoặc loại trừ nhau nên chọn một (chip)."""
    q: str = ""
    show: str = "matched"
    source: list[str] = field(default_factory=list)
    company: list[str] = field(default_factory=list)
    loc: str = ""
    days: str = ""
    band: str = ""
    via: str = "direct"
    chance: str = ""
    sort: str = "score"
    page: int = 1

    # --- đọc từ URL -------------------------------------------------------
    @staticmethod
    def from_query(query: dict[str, list[str]]) -> "JobFilter":
        def one(key: str, default: str = "") -> str:
            return (query.get(key, [default])[0] or default).strip()

        def many(key: str, cap: int) -> list[str]:
            seen, out = set(), []
            for value in query.get(key, []):
                value = value.strip()[:cap]
                if value and value.lower() not in seen:
                    seen.add(value.lower())
                    out.append(value)
            return out[:30]                       # chặn URL bị nhồi vô hạn

        found = JobFilter(
            q=one("q")[:120],
            show=one("show", "matched"),
            source=many("source", 60),
            company=many("company", 80),
            loc=one("loc"),
            days=one("days"),
            band=one("band"),
            via=one("via", "direct"),
            chance=one("chance"),
            sort=one("sort", "score"),
        )
        try:
            found.page = max(1, int(one("page", "1")))
        except ValueError:
            found.page = 1
        # chỉ nhận giá trị có trong danh sách — phần còn lại vứt
        valid = lambda value, options: value if value in {v for v, _ in options} else ""
        found.show = valid(found.show, SHOW) or "matched"
        found.loc = valid(found.loc, LOC)
        found.days = valid(found.days, DAYS)
        found.band = valid(found.band, BAND)
        found.via = found.via if found.via in {v for v, _ in VIA} else "direct"
        found.chance = valid(found.chance, CHANCE)
        found.sort = valid(found.sort, SORT) or "score"
        return found

    # --- dựng SQL ---------------------------------------------------------
    def where(self) -> tuple[str, list]:
        clauses: list[str] = []
        args: list = []

        if self.show == "matched":
            clauses.append("kept = 1")
        elif self.show == "dropped":
            clauses.append("kept = 0")

        if self.q:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(company) LIKE ?)")
            needle = f"%{self.q.lower()}%"
            args += [needle, needle]

        if self.source:
            clauses.append("(" + " OR ".join("source LIKE ?" for _ in self.source) + ")")
            args += [f"{s}%" for s in self.source]

        if self.company:
            marks = ",".join("?" for _ in self.company)
            clauses.append(f"LOWER(company) IN ({marks})")
            args += [c.lower() for c in self.company]

        if self.loc == "london":
            clauses.append("LOWER(location) LIKE '%london%'")
        elif self.loc == "uk":
            clauses.append("(" + " OR ".join("LOWER(location) LIKE ?" for _ in UK_LIKE) + ")")
            args += [f"%{w}%" for w in UK_LIKE]
        elif self.loc == "remote":
            clauses.append("remote = 1")
        elif self.loc == "other":
            clauses.append("NOT (" + " OR ".join("LOWER(location) LIKE ?" for _ in UK_LIKE) + ")")
            args += [f"%{w}%" for w in UK_LIKE]

        if self.via == "direct":
            clauses.append("via_agency = 0")
        elif self.via == "agency":
            clauses.append("via_agency = 1")
        # "all" -> không thêm điều kiện nào

        if self.chance:
            clauses.append("realism = ?")
            args.append(self.chance)

        if self.band == "none":
            clauses.append("score IS NULL")
        elif self.band:
            clauses.append("score >= ?")
            args.append(int(self.band))

        if self.days:
            clauses.append("posted_ts >= ?")
            args.append(int(time.time()) - int(self.days) * 86400)

        return (" WHERE " + " AND ".join(clauses)) if clauses else "", args

    def limit(self) -> tuple[int, int]:
        return PER_PAGE, (self.page - 1) * PER_PAGE

    def order(self) -> str:
        return {"score": "CASE realism WHEN 'likely' THEN 0 WHEN 'possible' THEN 1"
                         " WHEN 'unknown' THEN 2 ELSE 3 END, score DESC NULLS LAST",
                "new": "posted_ts DESC, id DESC", "old": "posted_ts ASC, id ASC",
                "company": "LOWER(company) ASC, LOWER(title) ASC",
                "title": "LOWER(title) ASC"}[self.sort]

    # --- dựng URL ---------------------------------------------------------
    def url(self, **changes) -> str:
        from urllib.parse import urlencode
        state: dict = {"q": self.q, "show": self.show, "source": list(self.source),
                       "company": list(self.company), "loc": self.loc,
                       "days": self.days, "band": self.band, "via": self.via,
                       "chance": self.chance, "sort": self.sort, "page": self.page}
        # đổi bộ lọc thì về trang 1 — trừ khi chính nó đang đổi trang
        if "page" not in changes:
            state["page"] = ""
        state.update(changes)
        if str(state.get("page", "")) in ("", "1"):
            state["page"] = ""
        default = {"show": "matched", "sort": "score", "via": "direct"}

        pairs: list[tuple[str, str]] = []
        for key, value in state.items():
            if isinstance(value, list):
                pairs += [(key, v) for v in value]
            elif value and default.get(key) != value:
                pairs.append((key, str(value)))
        # Danh sách việc nằm trong tab Search — tab Jobs đã bỏ.
        return "/search" + (f"?{urlencode(pairs)}" if pairs else "")

    def toggle(self, key: str, value: str) -> str:
        """URL sau khi bật/tắt một ô tích."""
        current = list(getattr(self, key))
        low = [c.lower() for c in current]
        if value.lower() in low:
            current.pop(low.index(value.lower()))
        else:
            current.append(value)
        return self.url(**{key: current})

    def has(self, key: str, value: str) -> bool:
        return value.lower() in [c.lower() for c in getattr(self, key)]

    def active(self) -> list[tuple[str, str]]:
        """Các bộ lọc đang bật, kèm URL để tắt từng cái."""
        out: list[tuple[str, str]] = []
        label = dict
        if self.q:
            out.append((f'"{self.q}"', self.url(q="")))
        if self.show != "matched":
            out.append((dict(SHOW)[self.show], self.url(show="matched")))
        for value in self.source:
            out.append((value, self.toggle("source", value)))
        for value in self.company:
            out.append((value, self.toggle("company", value)))
        if self.loc:
            out.append((dict(LOC)[self.loc], self.url(loc="")))
        if self.days:
            out.append((dict(DAYS)[self.days], self.url(days="")))
        if self.band:
            out.append((dict(BAND)[self.band], self.url(band="")))
        if self.chance:
            out.append((dict(CHANCE)[self.chance], self.url(chance="")))
        if self.via != "direct":
            out.append((dict(VIA)[self.via], self.url(via="direct")))
        return out
