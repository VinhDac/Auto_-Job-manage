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
    # Lối viết phổ biến nhất của Greenhouse/Lever là ĐẢO: "authorized to work
    # in this country". Bản cũ chỉ bắt "work authoriz…" theo đúng thứ tự đó,
    # nên câu đảo lọt xuống luật ĐIỀN `country` và máy trả lời một câu Có/Không
    # về quyền làm việc bằng chữ "United Kingdom".
    (re.compile(r"sponsor|visa|right to work|immigration|"
                r"work (authoris|authoriz)|(authoris|authoriz)\w*\s+to work|"
                r"legally (authoris|authoriz)|eligib\w*\s+to work|"
                r"work permit|permitted to work"),
     "sai một chữ là hỏng đơn — Graduate visa: HIỆN không cần bảo lãnh, TƯƠNG LAI có"),
    # Quốc tịch / nơi sinh KHÔNG phải nơi đang ở. Bản cũ để mọi ô có chữ
    # "country" rơi vào luật ĐIỀN và trả lời bằng nước cư trú.
    (re.compile(r"citizen|nationalit|country of birth|born in|place of birth|"
                r"passport|domicile|country of origin"),
     "tư cách pháp lý — Vin quốc tịch Việt Nam, đang ở UK bằng Graduate visa"),
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
    # \b: chuỗi "referr" nằm NGAY TRONG chữ "preferred", nên mọi ô
    # "Preferred name" bị xếp vào giỏ HỎI và Vin phải gõ tay tên mình mỗi lần.
    (re.compile(r"how did you hear|\breferr|\bsource\b|who referred"),
     "Vin tự chọn"),
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

# Dấu hiệu đây là một CÂU HỎI, không phải nhãn của một ô dữ kiện.
#
# Luật ĐIỀN so khớp chuỗi con, nên "Do you have a valid driving licence for
# work in your city?" trúng luật `city` và máy điền "London" vào đó. Nhãn ô dữ
# kiện thật thì ngắn và không hỏi han: "City", "Country", "Phone". Câu hỏi thì
# có chủ ngữ và dấu hỏi. Thấy dấu hiệu hỏi -> để Vin trả lời.
ASKING = re.compile(
    r"\b(do|did|does|are|is|have|has|will|would|can|could|should|were|was)\s+you"
    r"|\byou\b.{0,24}\?|^\s*(why|how|what|which|when|where|who)\b"
    r"|\bplease (tell|describe|explain|list|confirm)\b")

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
    if (el.disabled) return;
    // Ô KHOÁ (readOnly) vẫn phải VÀO danh sách. Widget chọn ngày hay khoá ô
    // chữ để bắt bấm vào lịch, và ô đó thường BẮT BUỘC. Bỏ nó ra khỏi danh
    // sách thì missing() không thấy, và máy bấm Gửi cho một lá đơn thiếu ngày
    // tốt nghiệp. Giữ lại, đánh dấu là khoá, rồi để Vin tự chọn.
    const locked = !!el.readOnly;
    // Ô bóng (không name lẫn id) thì form không đọc — BỎ, TRỪ ô tệp: rất
    // nhiều ATS để <input type=file> ẩn, không name không id, điều khiển
    // hoàn toàn bằng JS. Bỏ nó là gửi đơn KHÔNG có CV mà không ai báo.
    if (!el.name && !el.id && type !== 'file') return;
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
    // Nhãn DÙNG ĐỂ DÒ. Với ô nhóm, nhãn của từng lựa chọn là "London",
    // "Yes" — không có dấu * nào, nên cờ `required` tính từ nó luôn ra false
    // và missing() không thấy câu sponsorship bắt buộc còn trống.
    const lab = grouped ? (groupLabel(el, mine) || mine) : (mine || el.placeholder || '');
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
      label: lab,
      option: grouped ? mine : '',
      group: grouped ? (el.name || el.id) : '',
      required: !!(el.required || el.getAttribute('aria-required') === 'true'
                   || /[*✱]/.test(lab)),
      locked: locked,
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
    asking = bool(ASKING.search(asked)) or asked.count(" ") >= 8
    for rule, key in FILL_RULES:
        if rule.search(hay):
            # Câu hỏi dài, có chủ ngữ "you", hay có dấu hỏi thì không phải một
            # ô dữ kiện — dù nó có tình cờ nhắc tới "city" hay "country".
            if asking:
                return ASK, "câu hỏi, không phải ô dữ kiện — máy không đoán"
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
        # Ô khoá thì không gõ vào được — chỉ chọn bằng widget. Giữ trong danh
        # sách để missing() thấy, nhưng đừng để fill() đi gõ.
        if f.get("locked") and f["bucket"] == FILL:
            f["bucket"], f["key"] = ASK, "ô khoá — chọn bằng lịch/widget trên trang"
    return out
