"""Test thông báo macOS — thứ đã HỎNG SUỐT mà không ai biết.

Bản cũ dựng câu AppleScript bằng shlex.quote, tức là rào chuỗi cho SHELL:

    display notification '5 new matches' with title Jobbot
    -> 21:22: syntax error ... found unknown token. (-2741)

Không một thông báo nào từng hiện lên. send() trả False, người gọi vứt đi.

    python3 tests/test_notify.py
"""

import subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.core import notify

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"  ok   {name}")
    else:    fail += 1; print(f"  FAIL {name}{' — ' + extra if extra else ''}")


def compiles(script: str) -> tuple[bool, str]:
    """AppleScript có DỊCH được không. Không hiện thông báo, chỉ dịch thử —
    đây mới là bài kiểm tra thật: mắt thường nhìn chuỗi rào không ra lỗi."""
    done = subprocess.run(["osascript", "-e", f"return 1"], capture_output=True)
    if done.returncode != 0:                 # máy không có osascript -> bỏ qua
        return True, "không có osascript"
    done = subprocess.run(["osacompile", "-o", "/dev/null", "-e", script],
                          capture_output=True)
    return done.returncode == 0, done.stderr.decode()[:120]


print("[câu lệnh sinh ra phải là AppleScript hợp lệ]")
built = notify.script("jobbot", "5 việc mới khớp hồ sơ", "Mở dashboard để xem")
check("rào bằng nháy KÉP, không phải nháy đơn",
      '"jobbot"' in built and "'jobbot'" not in built)
good, err = compiles(built)
check("dịch được", good, err)

print("\n[chuỗi hiểm phải được thoát, không được làm hỏng câu lệnh]")
for title, message in [
        ('Job"bot', 'a "quoted" title'),
        ("back\\slash", "path C:\\temp"),
        ("hai dòng", "dòng một\ndòng hai"),
        ("chèn lệnh", '" & (do shell script "echo x") & "'),
        ("tiếng Việt", "5 việc mới khớp hồ sơ của bạn"),
]:
    good, err = compiles(notify.script(title, message))
    check(f"{title:12} -> vẫn dịch được", good, err)

check("dấu nháy trong nội dung bị thoát",
      '\\"' in notify.script("t", 'say "hi"'))
check("xuống dòng không cắt đôi câu lệnh",
      "\n" not in notify.script("t", "một\nhai"))

print("\n[send trả về THẬT, không phải luôn True]")
check("gửi được thì trả True", notify.send("jobbot", "test suite") is True)
real = notify.subprocess
class Dead:
    SubprocessError = subprocess.SubprocessError
    @staticmethod
    def run(*a, **k):
        raise FileNotFoundError("không có osascript")
notify.subprocess = Dead
check("gửi hỏng thì trả False", notify.send("jobbot", "x") is False)
notify.subprocess = real

print(f"\n{ok} ok, {fail} fail")
sys.exit(1 if fail else 0)
