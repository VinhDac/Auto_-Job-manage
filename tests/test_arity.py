"""Chỗ gọi hàm có khớp định nghĩa không — đối chiếu bằng AST.

Vì sao cần: bỏ tham số `conn` khỏi `mail.account()` mà sót một chỗ gọi ở
`server.py` làm SẬP TRẮNG cả trang /track. Lúc đó 906 bài test vẫn xanh — vì
Python chỉ phát hiện lệch tham số khi dòng đó thật sự chạy, mà không bài test
nào chạy tới dòng đó.

Bài này đọc CẢ REPO bằng AST và đối chiếu từng lời gọi với định nghĩa. Nó chỉ
xét lời gọi TRUY ĐƯỢC về đúng một module trong dự án — bản đầu tiên khớp theo
tên trần nên `dict.get`, `str.split`, `datetime.now` đụng tên với hàm trong
dự án: 216 báo động, 0 cái thật.

    python3 tests/test_arity.py
"""

import ast, sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
mods = {}                      # 'jobbot.track.mail' -> {tên hàm: (min,max,dòng)}
for f in sorted(SRC.rglob("*.py")):
    dotted = ".".join(f.relative_to(SRC).with_suffix("").parts)
    if dotted.endswith(".__init__"):
        dotted = dotted[: -len(".__init__")]
    table = {}
    tree = ast.parse(f.read_text(), str(f))
    for node in tree.body:                     # CHỈ hàm mức module, không method
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            pos = len(a.posonlyargs) + len(a.args)
            table[node.name] = (pos - len(a.defaults),
                                None if a.vararg else pos,
                                {k.arg for k in a.kwonlyargs} | {x.arg for x in a.args},
                                node.lineno, str(f))
    mods[dotted] = table

def resolve(node, package):
    """`from ..track import mail` -> {'mail': 'jobbot.track.mail'}"""
    out = {}
    for n in ast.walk(node):
        if isinstance(n, ast.ImportFrom):
            # level 1 = chính package này, level 2 = package cha. Nên bỏ đi
            # (level - 1) bậc, không phải `level` bậc — sai một bậc là phân
            # giải ra 'track.mail' thay vì 'jobbot.track.mail', và mọi lời gọi
            # qua import tương đối lọt lưới hết.
            base = package.split(".")
            if n.level:
                cut = len(base) - (n.level - 1)
                base = base[: max(cut, 0)]
            root = ".".join([*base, n.module] if n.module else base)
            for alias in n.names:
                out[alias.asname or alias.name] = f"{root}.{alias.name}"
        elif isinstance(n, ast.Import):
            for alias in n.names:
                out[alias.asname or alias.name] = alias.name
    return out

bad = []
for f in sorted(SRC.rglob("*.py")):
    dotted = ".".join(f.relative_to(SRC).with_suffix("").parts)
    package = dotted.rsplit(".", 1)[0]
    tree = ast.parse(f.read_text(), str(f))
    names = resolve(tree, package)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn, target = node.func, None
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
            base = names.get(fn.value.id)
            if base in mods and fn.attr in mods[base]:
                target = (base, fn.attr)
        elif isinstance(fn, ast.Name):
            full = names.get(fn.id)
            if full:
                mod, _, name = full.rpartition(".")
                if mod in mods and name in mods[mod]:
                    target = (mod, name)
        if not target:
            continue
        req, mx, allowed, ln, where = mods[target[0]][target[1]]
        got = len(node.args)
        keys = {k.arg for k in node.keywords if k.arg}
        if any(isinstance(x, ast.Starred) for x in node.args) or any(k.arg is None for k in node.keywords):
            continue
        if mx is not None and got > mx:
            bad.append(f"{f}:{node.lineno}  {target[0]}.{target[1]}({got}) — nhận tối đa {mx}  [{where}:{ln}]")
        elif got + len(keys) < req:
            bad.append(f"{f}:{node.lineno}  {target[0]}.{target[1]}({got}+{len(keys)}) — cần {req}  [{where}:{ln}]")
        else:
            for k in keys:
                if k not in allowed:
                    bad.append(f"{f}:{node.lineno}  {target[0]}.{target[1]}(…, {k}=) — không có tham số đó  [{where}:{ln}]")


ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ok   {name}")
    else:
        fail += 1
        print(f"  FAIL {name}{' — ' + extra if extra else ''}")


print(f"\n[đối chiếu {sum(len(t) for t in mods.values())} hàm trong {len(mods)} module]")
check("mọi chỗ gọi khớp định nghĩa", not bad, " · ".join(bad[:4]))
for line in bad:
    print("     ", line)

# Bộ kiểm phải TỰ CHỨNG MINH nó bắt được — một bộ kiểm luôn trả 0 thì vô dụng
# mà nhìn vẫn như đang chạy.
import ast as _ast
_probe = _ast.parse("from ..track import mail\nmail.account(conn)\n")
_names = resolve(_probe, "jobbot.dashboard")
check("phân giải được import tương đối",
      _names.get("mail") == "jobbot.track.mail", str(_names))
check("và module đó có trong bảng", "jobbot.track.mail" in mods)
check("account() thật sự nhận 0 tham số",
      mods.get("jobbot.track.mail", {}).get("account", (None,))[1] == 0)

# --------------------------------------------------------------------------
# GỌI MỘT HÀM KHÔNG TỒN TẠI. Lớp lỗi khác hẳn ở trên: trên kia là gọi SAI số
# tham số, đây là gọi vào HƯ KHÔNG.
#
# LỖI THẬT: commit f669e66 xoá `def _await(...)` trong apply/run.py mà để lại
# HAI chỗ gọi. Mọi lần nộp đơn đi tới nhánh "chưa thấy ô nào" đều chết bằng
# NameError. 1.451 bài test vẫn xanh, vì nhánh đó chỉ chạy khi có Chrome thật
# và một trang tuyển dụng thật — chỉ nhật ký lúc chạy mới lộ ra.
#
# Chỉ soi tên bắt đầu bằng "_": đó là hàm riêng của module, KHÔNG thể đến từ
# `import *` hay từ builtins, nên không định nghĩa trong chính file đó thì
# chắc chắn là gọi vào hư không — không có báo động giả.
print("\n[gọi hàm riêng của module thì hàm đó phải TỒN TẠI]")
treo = []
for f in sorted(SRC.rglob("*.py")):
    tree = ast.parse(f.read_text(), str(f))
    co = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            co.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            co.add(node.id)
        elif isinstance(node, ast.arg):
            co.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                co.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.Global):
            co.update(node.names)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id.startswith("_") and node.func.id not in co):
            treo.append(f"{f.name}:{node.lineno} {node.func.id}()")

check("không chỗ nào gọi vào hư không", not treo, " · ".join(treo[:4]))
for line in treo:
    print("     ", line)

# Bộ kiểm phải TỰ CHỨNG MINH nó bắt được cái nó nói là bắt được.
_gia = ast.parse("def _co(): pass\n_co()\n_khong_he_co()\n")
_dinh = set()
for _n in ast.walk(_gia):
    if isinstance(_n, ast.FunctionDef):
        _dinh.add(_n.name)
_bat = [n.func.id for n in ast.walk(_gia)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id.startswith("_") and n.func.id not in _dinh]
check("và bộ kiểm tự chứng minh nó bắt được", _bat == ["_khong_he_co"], str(_bat))

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
