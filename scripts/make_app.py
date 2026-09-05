#!/usr/bin/env python3
"""Đóng gói thành jobbot.app — app macOS đúng nghĩa.

    python3 scripts/make_app.py

Sau đó: kéo jobbot.app vào thư mục Applications. Bấm đúp như mọi app khác,
hiện ở Dock, ở Launchpad, cmd-tab được, có icon riêng.

Bundle chỉ là vỏ mỏng gọi run.py — code vẫn nằm trong dự án, sửa là chạy ngay,
không phải đóng gói lại.
"""

from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "jobbot.app"
BUNDLE_ID = "com.jobbot.app"


def draw_icon(out_dir: Path) -> Path | None:
    """Vẽ icon bằng AppKit (có sẵn), xuất .icns bằng iconutil (có sẵn)."""
    try:
        from AppKit import (NSAttributedString, NSBezierPath, NSBitmapImageRep,
                            NSColor, NSFont, NSFontAttributeName,
                            NSForegroundColorAttributeName, NSImage, NSMakePoint,
                            NSMakeRect, NSPNGFileType)
        from Foundation import NSMakeSize
    except ImportError:
        return None

    iconset = out_dir / "jobbot.iconset"
    iconset.mkdir(parents=True, exist_ok=True)

    def render(size: int) -> bytes:
        image = NSImage.alloc().initWithSize_(NSMakeSize(size, size))
        image.lockFocus()
        pad = size * 0.08
        radius = size * 0.225
        NSColor.colorWithSRGBRed_green_blue_alpha_(0.106, 0.239, 0.204, 1.0).set()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(pad, pad, size - 2 * pad, size - 2 * pad), radius, radius).fill()

        # NSAttributedString, KHÔNG phải str của Python — str không có
        # sizeWithAttributes_, đó là method của NSString.
        attrs = {
            NSFontAttributeName: NSFont.systemFontOfSize_(size * 0.46),
            NSForegroundColorAttributeName:
                NSColor.colorWithSRGBRed_green_blue_alpha_(0.42, 0.647, 0.561, 1.0),
        }
        text = NSAttributedString.alloc().initWithString_attributes_("◆", attrs)
        bounds = text.size()
        text.drawAtPoint_(NSMakePoint((size - bounds.width) / 2,
                                      (size - bounds.height) / 2))
        image.unlockFocus()

        rep = NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
        return bytes(rep.representationUsingType_properties_(NSPNGFileType, None))

    for size in (16, 32, 128, 256, 512):
        (iconset / f"icon_{size}x{size}.png").write_bytes(render(size))
        (iconset / f"icon_{size}x{size}@2x.png").write_bytes(render(size * 2))

    icns = out_dir / "jobbot.icns"
    done = subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)],
                          capture_output=True, text=True)
    shutil.rmtree(iconset, ignore_errors=True)
    return icns if done.returncode == 0 else None


def build() -> int:
    contents = APP / "Contents"
    macos, resources = contents / "MacOS", contents / "Resources"
    if APP.exists():
        shutil.rmtree(APP)
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    icns = draw_icon(resources)

    info = {
        "CFBundleName": "jobbot",
        "CFBundleDisplayName": "jobbot",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": "0.1",
        "CFBundleShortVersionString": "0.1",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "jobbot",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    }
    if icns:
        info["CFBundleIconFile"] = icns.name
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))

    launcher = macos / "jobbot"
    launcher.write_text(
        "#!/bin/bash\n"
        "# Vỏ mỏng — code thật nằm trong dự án, sửa là chạy ngay.\n"
        f'cd "{ROOT}" || exit 1\n'
        f'exec "{sys.executable}" run.py "$@"\n')
    launcher.chmod(0o755)

    subprocess.run(["touch", str(APP)], check=False)     # để Finder nhận icon mới
    print(f"\n  Đã dựng: {APP}")
    print(f"  Icon:    {'có' if icns else 'dùng icon mặc định'}")
    print("\n  Kéo jobbot.app vào /Applications rồi bấm đúp.\n")
    return 0


if __name__ == "__main__":
    sys.exit(build())
