#!/usr/bin/env python3
"""Cài jobbot thành dịch vụ chạy nền của macOS (launchd).

    python3 scripts/install_agent.py             cài + bật ngay
    python3 scripts/install_agent.py --status    xem đang chạy không
    python3 scripts/install_agent.py --uninstall gỡ

Sau khi cài: bật máy là tự chạy, tắt đi tự bật lại nếu crash.
Bấm "Quit jobbot" trên thanh menu thì nó DỪNG HẲN, không tự bật lại —
đó là lý do dùng KeepAlive={SuccessfulExit:false} chứ không phải KeepAlive=true.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABEL = "com.jobbot.agent"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG = ROOT / "data" / "agent.log"


def plist_body() -> dict:
    return {
        "Label": LABEL,
        # Trỏ vào bundle chứ không phải run.py: app mới có đúng icon,
        # đúng tên ở Dock và cmd-tab.
        "ProgramArguments": [str(ROOT / "jobbot.app" / "Contents" / "MacOS" / "jobbot")],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        # dict, KHÔNG phải True: crash thì bật lại, tự thoát thì thôi.
        "KeepAlive": {"SuccessfulExit": False},
        "StandardOutPath": str(LOG),
        "StandardErrorPath": str(LOG),
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "PYTHONUNBUFFERED": "1",
        },
    }


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def domain() -> str:
    return f"gui/{os.getuid()}"


def install() -> int:
    bundle = ROOT / "jobbot.app"
    if not bundle.exists():
        print("\n  Chưa có jobbot.app. Chạy trước:  python3 scripts/make_app.py\n")
        return 1
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)

    _launchctl("bootout", f"{domain()}/{LABEL}")        # gỡ bản cũ nếu có
    PLIST.write_bytes(plistlib.dumps(plist_body()))

    done = _launchctl("bootstrap", domain(), str(PLIST))
    if done.returncode != 0:                             # macOS cũ
        done = _launchctl("load", "-w", str(PLIST))
    if done.returncode != 0:
        print(f"Không nạp được: {done.stderr.strip()}")
        return 1

    print(f"\n  Đã cài: {PLIST}")
    print(f"  Log:    {LOG}")
    print("\n  Bật máy là tự chạy. Icon ◆ nằm trên thanh menu.")
    print("  Dashboard: http://127.0.0.1:8765/\n")
    return 0


def uninstall() -> int:
    _launchctl("bootout", f"{domain()}/{LABEL}")
    _launchctl("unload", "-w", str(PLIST))
    if PLIST.exists():
        PLIST.unlink()
    print(f"\n  Đã gỡ {LABEL}\n")
    return 0


def status() -> int:
    found = _launchctl("print", f"{domain()}/{LABEL}")
    if found.returncode != 0:
        print("\n  Chưa cài.\n")
        return 1
    state = next((l.strip() for l in found.stdout.splitlines() if "state =" in l), "?")
    pid = next((l.strip() for l in found.stdout.splitlines() if l.strip().startswith("pid =")), "pid = —")
    print(f"\n  {LABEL}\n  {state}\n  {pid}\n  plist: {PLIST}\n")
    return 0


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        sys.exit(uninstall())
    if "--status" in sys.argv:
        sys.exit(status())
    sys.exit(install())
