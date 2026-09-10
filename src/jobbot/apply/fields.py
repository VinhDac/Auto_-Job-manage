"""Đọc form nộp, rồi xếp mỗi ô vào ĐÚNG MỘT trong ba giỏ.

    ĐIỀN   máy chứng minh được câu trả lời  -> máy điền
    HỎI    câu cần Vin quyết                -> để trống, ghi lý do
    CẤM    nhân khẩu học                    -> KHÔNG chạm, dù form bắt buộc

Một ô rơi vào một giỏ, không hai. Ô nào không luật nào nhận thì mặc định là
HỎI — không biết thì hỏi, đó là hướng an toàn duy nhất.

Ghép theo CÂU HỎI chứ không theo tên ô: Greenhouse gọi `first_name`, Ashby gọi
`_systemfield_name`, Lever gọi `name`. Cả ba đều hỏi "tên bạn là gì". Bám vào
tên ô là ba bộ luật; bám vào câu hỏi là một.
"""

from __future__ import annotations

import json
import re

FILL, ASK, SKIP = "điền", "hỏi", "bỏ"

# --- CẤM ------------------------------------------------------------------
# Đặc điểm được pháp luật bảo vệ. Máy không trả lời thay người về những thứ
# này, kể cả khi form đánh dấu bắt buộc. Vin tự chọn, kể cả chọn "không nói".
NEVER = re.compile(
    r"gender|\bsex\b|\brace\b|ethnic|hispanic|latin[ox]|veteran|militar|"
    r"armed forces|disabilit|"
    r"disabled|sexual orientation|lgbt|transgender|pronoun|self identif|"
    r"equal opportunit|eeoc|protected (class|characteristic)")

# --- HỎI ------------------------------------------------------------------
# Mỗi dòng kèm LÝ DO, vì lý do là thứ Vin đọc để biết phải làm gì.
ASK_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sponsor|visa|right to work|work (authoris|authoriz)|immigration|"
                r"eligib\w* to work"),
     "sai một chữ là hỏng đơn — Graduate visa: HIỆN không cần bảo lãnh, TƯƠNG LAI có"),
    (re.compile(r"\bgpa\b|grade point|classification|predicted grade"),
     "MSc chưa có điểm tổng; BA là 3.59/4.0"),
    (re.compile(r"graduat\w*|expected completion|when .* finish"),
     "Vin tốt nghiệp 2026 — đoán sai là bị loại thẳng"),
    (re.compile(r"salary|compensation|expected pay|day rate|remuneration"),
     "con số này Vin tự quyết"),
    (re.compile(r"cover letter|why (do|are) you|motivat|tell us|describe|"
                r"what interests|in your own words"),
     "câu này viết tay, không lắp ghép"),
    (re.compile(r"notice period|start date|earliest|available from|when can you"),
     "phụ thuộc lịch của Vin"),
    (re.compile(r"relocat"), "Vin tự quyết"),
    (re.compile(r"criminal|conviction|background check|dbs"), "khai báo pháp lý"),
    (re.compile(r"agree|consent|acknowledg|privacy|terms|gdpr|data protection"),
     "đồng ý điều khoản là chữ ký — chỉ Vin bấm được"),
    (re.compile(r"how did you hear|referr|source|who referred"), "Vin tự chọn"),
    (re.compile(r"cover_letter|coverletter"), "chưa có tệp thư ngỏ"),
]

# --- ĐIỀN -----------------------------------------------------------------
# Sự thật kiểm chứng được, lấy từ answer.book(). Thứ tự có ý nghĩa: luật hẹp
# đứng trước luật rộng ("first name" trước "name").
FILL_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"first name|given name|forename|\bfname\b"), "first_name"),
    (re.compile(r"last name|family name|surname|\blname\b"), "last_name"),
    (re.compile(r"preferred name|nickname|preferred first"), "first_name"),
    (re.compile(r"linkedin"), "linkedin"),
    (re.compile(r"github"), "github"),
    (re.compile(r"website|portfolio|personal site|blog|web page"), "website"),
    (re.compile(r"e ?mail"), "email"),
    (re.compile(r"phone|mobile|telephone|contact number"), "phone"),
    (re.compile(r"country"), "country"),
    (re.compile(r"\bcity\b|town"), "city"),
    (re.compile(r"location|where are you based|current residence|address"), "location"),
    (re.compile(r"school|universit|college|institution|alma mater"), "school"),
    (re.compile(r"discipline|major|field of study|course|subject"), "discipline"),
    (re.compile(r"degree|qualification|level of study|education level"), "degree"),
    (re.compile(r"(start|from)[^a-z]*month"), "edu_start_month"),
    (re.compile(r"(start|from)[^a-z]*year"), "edu_start_year"),
    (re.compile(r"(end|to|finish)[^a-z]*month"), "edu_end_month"),
    (re.compile(r"(end|to|finish)[^a-z]*year"), "edu_end_year"),
    (re.compile(r"full name|your name|\bname\b"), "full_name"),
]

RESUME = re.compile(r"resume|\bcv\b|curriculum")

# Đọc mọi ô đang hiện, gắn cho mỗi ô một số hiệu để lát nữa điền không bị lạc.
#
# BA THỨ HỌC ĐƯỢC TỪ FORM THẬT (Point72, Greenhouse bản Remix 2025):
#
# 1. Không còn <select> nào. Mọi thứ trông như danh sách thả xuống đều là
#    input[role=combobox] — react-select. Đặt .value cho nó chỉ là gõ vào ô
#    LỌC, chưa chọn gì; mà `el.value` sau đó đúng bằng chữ vừa gõ, nên kiểm
#    tra kiểu đó BÁO THÀNH CÔNG GIẢ. Đo được 4 ô như vậy.
# 2. Cạnh mỗi combobox có một input BÓNG: không name, không id, chỉ để react
#    hiện chữ "bắt buộc". Nó không nhãn nên tự mượn nhãn hàng xóm -> mọi câu
#    hỏi hiện ra hai lần. Ô không name lẫn id thì form không đọc; bỏ.
# 3. Câu nhiều lựa chọn là N ô đánh dấu CÙNG name. Đọc rời ra thì "London",
#    "Paris", "Hong Kong" thành ba câu hỏi bắt buộc riêng — vô nghĩa. Gộp
#    theo name, một câu một dòng.
READ_JS = r"""
(() => {
  const seen = [], out = [];
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const own = el => {
    let t = '';
    if (el.id) { const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
                 if (l) t = l.innerText; }
    if (!t && el.closest('label')) t = el.closest('label').innerText;
    if (!t) t = el.getAttribute('aria-label') || '';
    if (!t) { const by = el.getAttribute('aria-labelledby');
              if (by) { const n = document.getElementById(by); if (n) t = n.innerText; } }
    return clean(t).slice(0, 200);
  };
  // Câu hỏi CHUNG của một nhóm ô đánh dấu: đi ngược lên tìm nhãn khác nhãn
  // của chính ô này.
  const groupLabel = (el, mine) => {
    const fs = el.closest('fieldset');
    if (fs) { const lg = fs.querySelector('legend'); if (lg) return clean(lg.innerText).slice(0, 200); }
    let p = el.parentElement, hop = 0;
    while (p && hop++ < 5) {
      for (const c of p.querySelectorAll('label,legend,[class*="label"]')) {
        const t = clean(c.innerText);
        if (t && t !== mine && t.length > 2) return t.slice(0, 200);
      }
      p = p.parentElement;
    }
    return '';
  };
  document.querySelectorAll('input,select,textarea').forEach(el => {
    const type = (el.type || '').toLowerCase();
    if (['hidden','submit','button','image','reset'].includes(type)) return;
    if (el.disabled || el.readOnly) return;
    if (!el.name && !el.id) return;                       // ô bóng, form không đọc
    if (type !== 'file' && !el.offsetParent) return;
    const n = seen.length; seen.push(el); el.setAttribute('data-jb', n);

    const combo = el.getAttribute('role') === 'combobox'
               || /select__input/.test(el.className || '');
    const kind = el.tagName === 'SELECT' ? 'select'
               : el.tagName === 'TEXTAREA' ? 'textarea'
               : combo ? 'combo'
               : type;
    const mine = own(el);
    const grouped = (type === 'checkbox' || type === 'radio');
    // Giá trị ĐANG CÓ. Với danh sách thả xuống, giá trị thật không nằm ở
    // el.value (đó chỉ là ô lọc) mà ở cái "chip" vẽ trong thẻ bọc.
    let now = '';
    if (grouped) now = el.checked ? (mine || 'x') : '';
    else if (combo) {
      const ctl = el.closest('[class*="control"]');
      const chip = ctl && ctl.querySelector('[class*="ingleValue"], [class*="ingle-value"],'
                                          + '[class*="ultiValue"], [class*="ulti-value"]');
      now = chip ? clean(chip.innerText) : '';
    } else if (type === 'file') now = (el.files && el.files.length) ? el.files[0].name : '';
    else now = el.value || '';
    out.push({
      k: n, name: el.name || '', dom_id: el.id || '', kind: kind,
      label: grouped ? (groupLabel(el, mine) || mine) : (mine || el.placeholder || ''),
      option: grouped ? mine : '',
      group: grouped ? (el.name || el.id) : '',
      required: !!(el.required || el.getAttribute('aria-required') === 'true'
                   || /\*/.test(mine)),
      value: now,
      options: el.tagName === 'SELECT'
             ? Array.from(el.options).map(o => clean(o.text)).filter(Boolean).slice(0, 60) : [],
    });
  });
  return JSON.stringify(out);
})()
"""


# Tên ô kiểu lập trình: firstName, opportunityLocationId.
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
# Ô định danh nội bộ của trang, không phải câu hỏi cho người.
INTERNAL = re.compile(r"\bid\b$|\buuid\b|\btoken\b|\bcsrf\b")


def _ask(text: str) -> str:
    """Câu hỏi rút về dạng so khớp được: tách camelCase, chữ thường, chỉ chữ số."""
    return re.sub(r"[^a-z0-9]+", " ", _CAMEL.sub(" ", text or "").lower()).strip()


def classify(field: dict) -> tuple[str, str]:
    """Ô này -> (giỏ, khoá-hoặc-lý-do). Luật đầu tiên trúng thì thắng."""
    asked = _ask(f"{field.get('label','')} {field.get('name','')} {field.get('dom_id','')}")
    if not asked:
        return ASK, "ô không nhãn"
    # Không nhãn cho người đọc, mà tên là định danh nội bộ (Lever:
    # `opportunityLocationId`) — đó không phải câu hỏi. Đoán vào là điền bừa.
    # Dùng bản ĐÃ TÁCH, vì luật này cần ranh giới từ.
    if not field.get("label") and INTERNAL.search(asked):
        return ASK, "ô nội bộ của trang"

    # Dò trên CẢ HAI dạng. Tách camelCase giúp `opportunityLocationId`, nhưng
    # nó cũng bẻ "LinkedIn" thành "linked in" và "GitHub" thành "git hub" —
    # luật `linkedin` trượt, ô LinkedIn im lặng thành "cần bạn" không lý do.
    hay = f"{asked} {asked.replace(' ', '')}"
    if NEVER.search(hay):
        return SKIP, ""
    if field.get("kind") == "file":
        return (FILL, "resume") if RESUME.search(hay) else (ASK, "tệp đính kèm khác")
    for rule, reason in ASK_RULES:
        if rule.search(hay):
            return ASK, reason
    for rule, key in FILL_RULES:
        if rule.search(hay):
            return FILL, key
    return ASK, ""


def read(tab) -> list[dict]:
    """Mọi ô của form đang mở, đã gộp nhóm và phân giỏ sẵn."""
    raw = tab.eval(READ_JS) or "[]"
    out: list[dict] = []
    groups: dict[str, dict] = {}
    for f in json.loads(raw):
        if f["group"]:
            head = groups.get(f["group"])
            if head is None:
                f["options"] = [f["option"]] if f["option"] else []
                groups[f["group"]] = f
                out.append(f)
            else:
                if f["option"]:
                    head["options"].append(f["option"])
                head["required"] = head["required"] or f["required"]
                head["value"] = head.get("value") or f.get("value", "")
            continue
        out.append(f)
    for f in out:
        f["bucket"], f["key"] = classify(f)
    return out
