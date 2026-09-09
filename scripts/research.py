#!/usr/bin/env python3
"""Đọc trang công ty cho từng nhóm JD. Chạy nền, lưu lại 3 ngày.

    python3 scripts/research.py

Vài chục giây một công ty, 3 công ty một nhóm. Chậm — nhưng chạy một lần rồi
dùng cho cả nhóm hàng chục tin, và KHÔNG chạy trong lúc vẽ trang.
"""

import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobbot.browser import cdp, chrome
from jobbot.core import db
from jobbot.cv.blocks import parse
from jobbot.profile import store
from jobbot.projects.cluster import build
from jobbot.projects.pipeline import research_cached
from jobbot.projects.research import study

if __name__ == "__main__":
    conn = db.connect()
    answers = store.load(conn)
    mine = [b for b in parse(answers.get("cv_text") or "") if b.kind == "project"]
    if not chrome.alive():
        chrome.launch(headless=False)
        time.sleep(3)

    print("\nĐọc trang công ty theo nhóm\n")
    for cluster in build(conn, mine):
        if cluster.key == "other":
            continue
        found = study(conn, cluster)
        t0 = time.time()
        found, source = research_cached(conn, cluster, found,
                                        tab_factory=cdp.open_tab)
        got = [n for n in found.web_notes if n.url]
        print(f"  {cluster.title[:34]:36} {len(got)}/3 trang · {source} · "
              f"{time.time() - t0:.0f}s")
        for note in got:
            print(f"      {note.company[:20]:22} {note.url}")
    print()
