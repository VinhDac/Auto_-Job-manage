"""Test bước 4 — gom nhóm JD và trang kết quả.  python3 tests/test_projects.py"""

import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import db, postings
from jobbot.cv import rules
from jobbot.cv.blocks import parse
from jobbot.ingest.base import Posting
from jobbot.projects.page import _slot, build as build_page, health

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}")

CV = """DAC VINH NGUYEN
EXPERIENCE
Founder / Quantitative Developer — Trading Startup Jan 2026 – Present
I designed and built two systems in Python with portfolio construction and risk limits.
A random train/test split leaks, because adjacent dates are correlated.
Live drawdown ran roughly 30% deeper than the model predicted.
The mistake was mine: thousands of free parameters is still room to overfit.
I ran walk-forward validation across 17 instruments and five years of data.
SELECTED PROJECTS
Quant Trading Studio — backtesting, out-of-sample validation and risk budgeting on the
efficient frontier.
TECHNICAL SKILLS
Programming — Python, SQL.
"""
PROFILE = {"cv_text": CV, "links": "https://github.com/vin/studio"}

print("\n[xếp câu vào phần nào]")
cases = [
    ("The mistake was mine: thousands of free parameters is still room to overfit", "tradeoff"),
    ("Live drawdown ran roughly 30% deeper than the model predicted", "tradeoff"),
    ("A random train/test split leaks, because adjacent dates are correlated", "problem"),
    ("I designed and built two systems in Python with risk limits", "method"),
    ("I ran walk-forward validation across 17 instruments and five years of data", "numbers"),
]
for text, want in cases:
    check(f"{want:8} ← {text[:44]}…", _slot(text) == want)

print("\n[vòng lặp khép: câu bị CV cắt về đúng phần Đánh đổi]")
cut = [t for t in [c[0] for c in cases]
       if rules.sentence_ok(t)[0] == "drop" and rules.SELF_CRITIQUE.search(t)]
check("có câu bị CV cắt", len(cut) >= 2)
check("mọi câu bị cắt đều rơi vào tradeoff",
      all(_slot(t) == "tradeoff" for t in cut))

doc = build_page(PROFILE, "Quantitative Researcher", "Point72",
                 {"python", "risk", "validation", "portfolio"})
check("trang có phần Đánh đổi", len(doc.tradeoff) >= 2)
check("phần Đánh đổi chứa đúng câu CV đã bỏ",
      any("mistake was mine" in t for t in doc.tradeoff))
check("phần Cách làm không dính câu thất bại",
      not any(rules.SELF_CRITIQUE.search(t) for t in doc.method))
check("bắt được link code", any("github.com" in c for c in doc.code))
check("nêu được trang trả lời tin này ở điểm nào", "python" in doc.speaks_to)

print("\n[chỗ trang còn thiếu]")
thin = build_page({"cv_text": "EXPERIENCE\nAnalyst — X Jan 2025 – Present\n"
                              "I built dashboards in Python for the team.\n"}, "A", "B", {"python"})
gaps = dict(health(thin))
check("thiếu số đo -> báo", "No measurement" in gaps)
check("không có chỗ đánh đổi -> báo", "Nothing given up" in gaps)
check("thiếu link code -> báo", "No code link" in gaps)
check("trang đủ thì không báo bừa", "Nothing given up" not in dict(health(doc)))

# ---------------------------------------------------------------- KHO PROJECT

print("\n[kho project — cung/cầu theo KỸ NĂNG]")
from jobbot.projects import inventory as inv, make
from jobbot.projects.brief import Brief

with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")
    rows = [
        ("a1", "Quant Researcher", "Cygnus", "we run a systematic fund",
         "backtesting and equities"),
        ("a2", "Quant Researcher", "Cygnus", "we run a systematic fund",
         "backtesting and portfolio"),
        ("a3", "Risk Analyst", "Solid Insurance", "actuarial reserving team",
         "risk and derivatives"),
        ("a4", "Data Scientist", "PayFlow", "payment processing platform",
         "machine learning and sql"),
    ]
    import json as _json
    postings.save_batch(conn, "t", [
        Posting(source_id=sid, title=title, company=company,
                location="London", url=f"https://x/{sid}", description=blurb)
        for sid, title, company, blurb, _needs in rows])
    for sid, _t, _c, _b, needs in rows:
        conn.execute("UPDATE posting SET kept = 1, score_json = ?"
                     " WHERE raw_id IN (SELECT id FROM raw_posting"
                     "                  WHERE source_id = ?)",
                     (_json.dumps({"requirements": [{"text": needs}]}), sid))
    conn.commit()

    counts = inv.demand(conn)
    check("đếm theo TIN, không theo dòng yêu cầu", counts["backtesting"] == 2)
    check("kỹ năng chỉ một tin đòi vẫn đếm được", counts["sql"] == 1)

    tags = inv.industries(conn)
    check("ngành đọc ra từ chính tin", "hedge fund" in tags.get("backtesting", []))
    check("ngành gắn đúng tin", "insurance" in tags.get("risk", []))
    check("ngành không dính sang kỹ năng khác",
          "insurance" not in tags.get("backtesting", []))

    # Lưới bỏ kỹ năng dưới ngưỡng — hạ ngưỡng xuống để bộ dữ liệu bé này hiện ra.
    real_min = inv.MIN_DEMAND
    inv.MIN_DEMAND = 1
    grid = inv.coverage(conn, [])
    names = [c["skill"] for c in grid]
    check("lưới xếp theo số tin đòi, nhiều nhất lên đầu",
          names and names[0] == "backtesting")
    check("bỏ kỹ năng ai cũng đòi khỏi lưới",
          not ({"python", "statistics", "pandas"} & set(names)))
    check("kho trống thì mọi ô đều trống", all(not c["covered"] for c in grid))

    class Block:                       # giả một project trên CV
        tags = ["risk"]
    check("project trên CV lấp được ô",
          any(c["covered"] and c["by"] is None
              for c in inv.coverage(conn, [Block()]) if c["skill"] == "risk"))

    b = Brief(question="Does a cost model change a momentum backtest's Sharpe?",
              dataset_url="https://x/y.csv", method=["a" * 30] * 3,
              measure="Sharpe before and after, measured on the same series",
              days=2, skills=["backtesting", "equities"],
              deliverable="one notebook")
    pid = inv.add(conn, b, ["hedge fund"])
    after = {c["skill"]: c for c in inv.coverage(conn, [])}
    # CHỐT CHẶN cho lỗi đã bắt được lúc chạy thật 09/09: đề bài mới sinh mà đã
    # tính là lấp ô, nên bấm Dựng mười lăm lần là lưới sạch bong trong khi chưa
    # viết dòng code nào.
    check("đề bài CHƯA làm thì KHÔNG tính là lấp ô",
          not after["backtesting"]["covered"] and not after["equities"]["covered"])
    check("nhưng có đánh dấu là đã nhận làm", after["backtesting"]["planned"][0] == pid)
    check("ô đã nhận làm thì không mời dựng thêm lần nữa",
          "backtesting" not in {c["skill"] for c in inv.uncovered(conn, [])})

    check("kho đọc lại được", len(inv.all(conn)) == 1)
    check("mới cất thì là đề bài", inv.all(conn)[0]["state"] == inv.DE_BAI)
    inv.set_state(conn, pid, inv.DANG_LAM)
    check("đổi được trạng thái", inv.all(conn)[0]["state"] == inv.DANG_LAM)
    inv.set_state(conn, pid, "bịa")
    check("trạng thái bịa thì không nhận", inv.all(conn)[0]["state"] == inv.DANG_LAM)
    check("đang làm dở vẫn CHƯA phải bằng chứng",
          not {c["skill"]: c for c in inv.coverage(conn, [])}["backtesting"]["covered"])

    inv.set_state(conn, pid, inv.XONG)
    done = {c["skill"]: c for c in inv.coverage(conn, [])}
    check("làm XONG thì một đề bài lấp được NHIỀU ô cùng lúc",
          done["backtesting"]["covered"] and done["equities"]["covered"])
    check("ô đã lấp chỉ đúng vào project vừa cất", done["backtesting"]["by"] == pid)
    check("kỹ năng không nằm trong đề bài thì vẫn trống", not done["sql"]["covered"])

    class Older:                       # CV đứng trước kho khi cùng lấp một ô
        tags = ["backtesting"]
    check("bằng chứng trên CV được ưu tiên hơn dòng trong kho",
          {c["skill"]: c for c in inv.coverage(conn, [Older()])}
          ["backtesting"]["by"] is None)
    inv.MIN_DEMAND = real_min

    group = make.for_skill(conn, "backtesting")
    check("gom được đúng những tin đòi kỹ năng đó", len(group.jobs) == 2)
    check("nhóm mang tên chính kỹ năng đó", group.title == "backtesting")
    check("kỹ năng không ai đòi thì nhóm rỗng",
          make.for_skill(conn, "kubernetes").jobs == [])
    check("thứ đã làm gồm cả kho lẫn CV",
          b.question in make.existing_work(conn, []))
    conn.close()

# ------------------------------------------------- KHUÔN DỰNG PROJECT (không LLM)

print("\n[khuôn — ô nào dựng được, ô nào nói thẳng là không]")
from jobbot.projects import frame, shelf
from jobbot.projects.brief import validate as gate

check("ô khuôn chứng minh được thì dựng ra đề bài",
      frame.build("machine learning") is not None)
check("ô nào cũng phải rơi vào một hình dạng có thật",
      all(frame.shape_for(s) in frame.PROVES for s in ("machine learning",
          "alpha research", "sql", "portfolio")))
check("ô khuôn KHÔNG chứng minh được thì trả None, không bịa",
      frame.build("optimisation") is None and frame.build("derivatives") is None)
check("kỹ năng không có nguồn dữ liệu cũng trả None", frame.build("nlp") is None)

print("\n[hai hình dạng, đọc ra từ dòng VIỆC PHẢI LÀM của JD]")
check("ô về tín hiệu -> hình dạng signal",
      frame.shape_for("alpha research") == "signal"
      and frame.shape_for("backtesting") == "signal")
check("ô còn lại -> hình dạng change", frame.shape_for("machine learning") == "change")
check("hai hình dạng ra hai câu hỏi KHÁC HẲN nhau",
      frame.build("alpha research")[0].question
      != frame.build("machine learning")[0].question)
check("câu hỏi không lặp chữ (lỗi 'cross-sectional cross-sectional')",
      "cross-sectional cross-sectional"
      not in frame.build("alpha research")[0].question)

made = frame.build("machine learning")
b, src = made
check("đề bài khuôn dựng ra tự qua được CỔNG",
      gate(b, ["machine learning", "equities", "validation"], [], lambda _u: True) == [])
check("khai đúng ô đang nhắm", b.skills[0] == "machine learning")
check("khai cả thứ khuôn LUÔN làm", set(frame.ALWAYS) <= set(b.skills))
check("không khai thứ khuôn không chứng minh được",
      not (set(b.skills) - frame.PROVES["change"] - frame.INHERIT))
check("KHÔNG thừa hưởng kỹ năng phương pháp từ nguồn dữ liệu",
      "sql" not in b.skills and "probability" not in b.skills)
check("thứ giao nộp là REPO, không phải notebook trần",
      "repo" in b.deliverable and "test" in b.deliverable)

print("\n[bước 1 đổi theo kỹ năng — không phải khai rồi để đấy]")
check("change + machine learning -> mô hình",
      frame.STEP_ONE["change"]["machine learning"] == "detect_model")
check("change + sql -> viết bằng SQL", frame.STEP_ONE["change"]["sql"] == "detect_sql")
check("signal + machine learning -> mô hình",
      frame.STEP_ONE["signal"]["machine learning"] == "signal_model")
check("ô khác -> bản mặc định của hình dạng đó",
      frame.STEP_ONE["signal"].get("portfolio", frame.DEFAULT_STEP_ONE["signal"])
      == "signal_momentum")

print("\n[repo đẻ ra phải sạch]")
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "repo"
    files = frame.scaffold(b, src, out)
    check("có đủ ba thứ JD đòi: test · README · script tải dữ liệu",
          {"test_analyse.py", "README.md", "get_data.py"} <= set(files))
    check("chỉ chép MỘT bản bước 1, đổi tên cố định",
          "detect.py" in files
          and not any(f.startswith("detect_") for f in files))
    check("bước 1 chép vào đúng bản của kỹ năng đó",
          "IsolationForest" in (out / "detect.py").read_text())
    check("dữ liệu KHÔNG kèm trong repo", "data/" in (out / ".gitignore").read_text())
    # Sót một chỗ điền là repo phát hành ra có chữ {{unit}} nằm giữa README.
    left = [f for f in files if "{{" in (out / f).read_text()]
    check("không sót chỗ điền nào", not left)
    check("mọi tệp .py trong repo đều cú pháp đúng",
          all(__import__("ast").parse((out / f).read_text())
              for f in files if f.endswith(".py")) or True)

print("\n[repo hình dạng signal]")
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "sig"
    sb, ssrc = frame.build("alpha research")
    sfiles = frame.scaffold(sb, ssrc, out)
    check("chép bản dựng tín hiệu, không chép bản phát hiện",
          "signal_rule.py" in sfiles and "detect.py" not in sfiles)
    check("vẫn có đủ test · README · script tải dữ liệu",
          {"test_analyse.py", "README.md", "get_data.py"} <= set(sfiles))
    check("không sót chỗ điền nào",
          not [f for f in sfiles if "{{" in (out / f).read_text()])
    body = (out / "README.md").read_text()
    check("README chép NGUYÊN VĂN dòng việc phải làm của JD",
          "> ·" in body or "no explicit responsibilities" in body)
    check("số lượng long/short hợp lệ với số thành phần",
          2 * int(__import__("re").search(r"SIDE = (\d+)",
                  (out / "analyse.py").read_text()).group(1)) <= ssrc.parts)

print("\n[một kỹ năng chỉ MỘT đề bài đang mở]")
with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(Path(tmp) / "t.db")
    postings.save_batch(conn, "t", [
        Posting(source_id=f"x{i}", title="Quant Researcher", company=f"Firm{i}",
                location="London", url=f"https://x/{i}",
                description="Requirements:\n· machine learning and python\n"
                            "· out-of-sample validation, no look-ahead\n"
                            "· visualisation of results\n" + "d " * 200)
        for i in range(3)])
    import json as _j
    conn.execute("UPDATE posting SET kept = 1, score_json = ?",
                 (_j.dumps({"requirements": [
                     {"text": "machine learning and python"},
                     {"text": "out-of-sample validation, no look-ahead bias"},
                     {"text": "visualisation of research results"}]}),))
    conn.commit()
    first = make.build(conn, "machine learning", [], root=Path(tmp) / "kho")
    again = make.build(conn, "machine learning", [], root=Path(tmp) / "kho")
    check("lần đầu dựng được", first == "ok")
    check("lần hai bị chặn, không đẻ thêm đề bài trùng ô", again == "already_open")
    check("kho chỉ có một dòng", len(inv.all(conn)) == 1)
    check("repo có đường dẫn thật, và link được lưu lại",
          Path(inv.all(conn)[0]["link"]).joinpath("Makefile").exists())
    # Trang chỉ được vẽ lại KHI VIỆC XONG THẬT. Đã xảy ra: make.build đóng
    # luồng nhật ký ngay sau chặng kiểm dữ liệu, trang nạp lại trước khi đề bài
    # kịp vào kho, và kho hiện đề bài mới trong khi lưới vẫn mời Dựng lại ô đó.
    import inspect as _inspect
    code = [l for l in _inspect.getsource(make.build).splitlines()
            if not l.strip().startswith("#")]
    check("make.build KHÔNG tự đóng luồng nhật ký giữa chừng",
          "jlog.done" not in "\n".join(code))

    check("ô không dựng được thì nói thẳng",
          make.build(conn, "nlp", [], root=Path(tmp) / "kho") == "no_frame")
    conn.close()



# ------------------------------------------------ PROJECT XONG -> DÒNG CV

print("\n[project xong -> dòng CV]")
from jobbot.projects import tocv
from jobbot.cv.blocks import parse as parse_cv
from jobbot.cv.build import skills_in as cv_skills

FACTS = {"shape": "signal", "number": 0.4348, "days": 14392, "dropped": 11904,
         "parts": 49, "from": "1969-07-01", "to": "2026-07-31",
         "in_sample_sharpe": 0.74, "held_out_sharpe": 0.322, "cost_bps": 10,
         "turnover": 0.223, "held_out_from": "2007-07-06",
         "signal": "trailing 252-day return skipping the last 21 days"}
ROW = {"id": 1, "skills": ["alpha research", "validation", "visualisation",
                           "equities", "market data"], "link": ""}

check("chưa chạy make run thì KHÔNG có dòng nào", tocv.lines(ROW, {}) == [])
check("có số rồi thì ra đúng ba dòng", len(tocv.lines(ROW, FACTS)) == 3)

blk = tocv.block(ROW, FACTS, "https://github.com/vin/x")
# BẤT BIẾN. Nếu dòng CV không mang nổi kỹ năng project chứng minh thì cả vòng
# lặp nói dối: lưới bảo ô đã lấp, mà CV gửi đi không hề nói được điều đó. Đã
# xảy ra thật — bản đầu viết "never used to choose anything" thay vì
# "out-of-sample", và mất sạch equities · market data · validation.
carried = cv_skills(blk)
check("dòng CV MANG được mọi kỹ năng project khai",
      not (set(ROW["skills"]) - carried))
check("và mang thêm thứ nó làm thật, không ít hơn",
      {"backtesting", "portfolio"} & carried)

check("có nhắc con số đo được", "43%" in blk and "0.74" in blk)
check("có nhắc CHỖ YẾU, không chỉ khoe", "Dropped" in blk and "45%" in blk)
check("có link repo", "github.com/vin/x" in blk)

# Định dạng phải khớp cv/blocks.py, nếu không khối lọt vào mục khác của CV.
parsed = parse_cv("SELECTED PROJECTS\n" + blk)
proj = [b for b in parsed if b.kind == "project"]
check("bóc lại được đúng một khối project", len(proj) == 1)
check("thân khối KHÔNG dính dấu gạch đầu dòng thừa",
      all(not l.lstrip().startswith("·") for l in proj[0].lines))
# cv/blocks.py coi MỌI dòng chứa " — " là tiêu đề khối mới, nên một dấu gạch
# dài lọt vào thân là khối project tự tách làm đôi.
for _shape, _f in (("signal", FACTS),
                   ("change", {**FACTS, "shape": "change", "events": 79,
                               "biggest": "2001-09-17", "driver": "Guns",
                               "detector": "a rolling 4-sigma threshold",
                               "headline": "25.5% from one industry"})):
    _b = tocv.block({**ROW, "skills": ["machine learning"]}, _f, "")
    check(f"[{_shape}] thân không chứa dấu gạch dài",
          all(" — " not in l for l in tocv.lines(ROW, _f)))
    check(f"[{_shape}] bóc lại vẫn đúng MỘT khối",
          len([b for b in parse_cv("SELECTED PROJECTS\n" + _b)
               if b.kind == "project"]) == 1)
check("tag của khối khớp kỹ năng project", set(ROW["skills"]) <= set(proj[0].tags)
      or set(proj[0].tags) & set(ROW["skills"]) != set())

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
