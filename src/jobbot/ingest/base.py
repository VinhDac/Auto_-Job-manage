"""Nền chung cho mọi nguồn: kiểu Posting, gọi HTTP, chuẩn hoá chuỗi.

Mỗi nguồn chỉ phải làm đúng một việc: fetch -> trả về list[Posting]. Hết.
Ghi DB, gộp trùng, chấm điểm đều là việc của chỗ khác.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

UA = "jobbot/0.1 (personal job search; contact via local app)"
TIMEOUT = 25


# ---------------------------------------------------------------- HTTP

def get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


# ------------------------------------------------------------ chuẩn hoá

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^a-z0-9 ]+")

# Đuôi công ty — bỏ đi để "Monzo Bank Ltd" và "Monzo Bank" gộp được vào nhau.
_SUFFIX = re.compile(
    r"\b(ltd|limited|llp|plc|inc|incorporated|llc|gmbh|bv|nv|sa|ag|corp|corporation|"
    r"co|company|group|holdings|international|uk|global)\b")


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = _TAG.sub("", text)
    for entity, char in (("&amp;", "&"), ("&nbsp;", " "), ("&#39;", "'"),
                         ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(entity, char)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def norm(text: str) -> str:
    """Chuẩn hoá để so khớp: thường hoá, bỏ dấu câu, gộp khoảng trắng."""
    return _WS.sub(" ", _PUNCT.sub(" ", (text or "").lower())).strip()


def norm_company(name: str) -> str:
    """Bỏ đuôi pháp lý. 'Monzo Bank Ltd' -> 'monzo bank'."""
    return _WS.sub(" ", _SUFFIX.sub(" ", norm(name))).strip()


def norm_title(title: str) -> str:
    """Bỏ phần trong ngoặc và đuôi mã tin. 'Analyst (London) - REQ123' -> 'analyst'."""
    title = re.sub(r"\([^)]*\)", " ", title or "")
    title = re.sub(r"\b(req|job|id|ref)[-_ ]?\d+\b", " ", title, flags=re.I)
    return norm(title)


# ---------------------------------------------------------------- Posting

@dataclass
class Posting:
    """Một tin, đã chuẩn hoá về cùng hình dạng dù đến từ nguồn nào."""
    source_id: str
    title: str
    company: str
    location: str = ""
    remote: bool = False
    salary: str = ""
    url: str = ""
    posted_at: str = ""
    description: str = ""
    payload: dict = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Cùng công ty + cùng chức danh = nhiều khả năng cùng một việc."""
        return f"{norm_company(self.company)}|{norm_title(self.title)}"

    def text(self) -> str:
        """Toàn bộ chữ để tìm từ khoá."""
        return f"{self.title}\n{self.company}\n{self.location}\n{self.description}"
