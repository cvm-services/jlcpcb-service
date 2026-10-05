#!/usr/bin/env python3
"""Dump the FULL quote page text after detection, plus every money amount with context."""
import os
import re
import sys
import time

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, _goto  # noqa: E402
from jlcpcb_client.selectors import QUOTE_URL  # noqa: E402

ZIP = "/home/c03rad0r/worktrees/t_3c28ba1f/tracker/hardware/output/gerbers_v8i_jlcpcb.zip"

with browser() as page:
    _goto(page, QUOTE_URL, settle=18.0)
    page.locator("input#uploadFile").first.set_input_files(ZIP, timeout=20000)

    for _ in range(20):
        time.sleep(6)
        t = page.evaluate("document.body.innerText || ''")
        if "Detected" in t:
            break
    time.sleep(20)  # let pricing settle
    t = page.evaluate("document.body.innerText || ''")

    print("=== FULL TEXT (%d chars) ===" % len(t), flush=True)
    print(t, flush=True)
    print("=== MONEY AMOUNTS with context ===", flush=True)
    for m in re.finditer(r"\$\s?[0-9][0-9,]*(?:\.[0-9]+)?", t):
        a, b = max(0, m.start() - 70), min(len(t), m.end() + 20)
        print(repr(t[a:b].replace("\n", " | ")), flush=True)
    print("=== LABEL CANDIDATES ===", flush=True)
    for pat in ["PCB Price", "PCB Size", "Total", "Price", "Subtotal", "Board"]:
        print(pat, "->", pat in t, flush=True)
    page.screenshot(path="/home/c03rad0r/repos/jlcpcb-service/snapshots/debug-full.png", full_page=True)
    print("DONE", flush=True)
