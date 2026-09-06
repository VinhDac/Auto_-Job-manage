"""Đọc CV từ file — PDF, DOCX, TXT — và ĐỀ XUẤT điền hồ sơ.

Không cài gì thêm:
    PDF   PDFKit của macOS qua PyObjC (có sẵn)
    DOCX  zipfile + xml trong thư viện chuẩn
    TXT   đọc thẳng

Luật: **đề xuất, không tự ghi.** Người dùng bấm duyệt từng mục.
Tự ghi đè là cách nhanh nhất để xoá mất thứ họ đã điền tay.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from io import BytesIO

from ..ingest.base import norm
from ..scoring.vocab import ALIASES

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?){2,4}\d{2,4}")
URL = re.compile(r"(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/[\w./%-]*)?", re.I)
CITY = re.compile(r"\b(London|Manchester|Edinburgh|Birmingham|Leeds|Bristol|Glasgow|"
                  r"Cambridge|Oxford|Hanoi|Ho Chi Minh|New York|Singapore|Dublin)\b", re.I)


class ReadError(RuntimeError):
    pass


# ---------------------------------------------------------------- đọc file

def from_pdf(data: bytes) -> str:
    """Dùng PDFKit của macOS. Nó xử lý được font nhúng và mã hoá riêng —
    bóc tay bằng zlib chỉ ra ký tự rác."""
    try:
        import objc
        from Foundation import NSData, NSBundle
        objc.loadBundle("PDFKit", globals(),
                        bundle_path="/System/Library/Frameworks/Quartz.framework"
                                    "/Frameworks/PDFKit.framework")
        doc = PDFDocument.alloc().initWithData_(          # noqa: F821
            NSData.dataWithBytes_length_(data, len(data)))
        if doc is None:
            raise ReadError("Không mở được PDF — file hỏng hoặc có mật khẩu.")
        return str(doc.string() or "")
    except ImportError as exc:
        raise ReadError(f"Đọc PDF cần PyObjC (macOS có sẵn): {exc}") from exc


def from_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", "replace")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ReadError("Không đọc được .docx — file hỏng?") from exc
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", " ", xml)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", "", xml)).strip()


def read(filename: str, data: bytes) -> str:
    low = (filename or "").lower()
    if low.endswith(".pdf") or data[:5] == b"%PDF-":
        return from_pdf(data)
    if low.endswith(".docx") or data[:2] == b"PK":
        return from_docx(data)
    text = data.decode("utf-8", "replace")
    if "\x00" in text:
        raise ReadError("Định dạng không đọc được. Dùng PDF, DOCX hoặc TXT.")
    return text


# ------------------------------------------------------------- đề xuất

@dataclass
class Proposal:
    field: str
    label: str
    value: str
    note: str = ""


def _section(text: str, name: str) -> str:
    found = re.search(rf"^{name}\s*$(.*?)(?=^[A-Z][A-Z &]{{3,}}\s*$|\Z)",
                      text, re.M | re.S)
    return found.group(1).strip() if found else ""


def propose(text: str, existing: dict) -> list[Proposal]:
    """Rút thông tin ra khỏi CV. CHỈ đề xuất cho ô đang TRỐNG —
    không bao giờ đè lên thứ người dùng đã tự điền."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: list[Proposal] = []

    def add(field: str, label: str, value: str, note: str = ""):
        if value and not (existing.get(field) or "").strip():
            out.append(Proposal(field, label, value.strip(), note))

    add("cv_text", "Full CV text", text, f"{len(text)} characters")

    if lines:
        head = lines[0]
        if len(head) < 60 and head.replace(" ", "").isalpha():
            add("full_name", "Name", head.title() if head.isupper() else head)

    blob = "\n".join(lines[:6])
    email = EMAIL.search(blob)
    if email:
        add("email", "Email", email.group())
    phone = PHONE.search(blob.replace(email.group(), "") if email else blob)
    if phone and len(re.sub(r"\D", "", phone.group())) >= 9:
        add("phone", "Phone", phone.group().strip())
    city = CITY.search(blob)
    if city:
        add("location", "Location", city.group())

    links = [u for u in URL.findall(blob)
             if any(k in u.lower() for k in ("github", "linkedin", ".io", "gitlab", "portfolio"))]
    if links:
        add("links", "Profile links", "\n".join(dict.fromkeys(links)))

    edu = _section(text, "EDUCATION")
    if edu:
        add("education", "Education", edu.split("Certification")[0].strip())
    cert = re.search(r"^Certifications?\s*[—–-]\s*(.+)$", text, re.M)
    if cert:
        add("certifications", "Certifications", cert.group(1).strip())

    skills = _section(text, "TECHNICAL SKILLS") or _section(text, "SKILLS")
    found = sorted({c for a, c in ALIASES.items()
                    if (f" {a.strip()} " if len(a.strip()) <= 3 else a.strip())
                    in f" {norm(skills or text)} "})
    if found:
        add("skills_strong", "Skills recognised in your CV", ", ".join(found),
            f"{len(found)} terms — edit before saving, the system cannot tell "
            f"strong from merely mentioned")
    return out
