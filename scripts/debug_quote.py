#!/usr/bin/env python3
"""Debug: what does the quote page look like after an upload attempt?"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")
from jlcpcb_client.session import browser, is_authed, _goto  # noqa: E402
from jlcpcb_client.selectors import QUOTE_URL  # noqa: E402

ZIP = "/home/c03rad0r/worktrees/t_3c28ba1f/tracker/hardware/output/gerbers_v8i_jlcpcb.zip"

with browser() as page:
    _goto(page, QUOTE_URL, settle=18.0)
    print("URL:", page.url, flush=True)
    print("AUTHED:", is_authed(page), flush=True)

    inputs = page.evaluate("""() => [...document.querySelectorAll('input')]
        .map((i,n)=>({n, type:i.type, acc:i.accept||'', id:i.id||'', cls:(i.className||'').slice(0,40)}))
        .filter(x=>x.type==='file')""")
    print("FILE INPUTS:", json.dumps(inputs)[:600], flush=True)

    print("--- text before upload ---", flush=True)
    print(page.evaluate("document.body.innerText.slice(0,900)"), flush=True)

    try:
        page.locator("input#uploadFile").first.set_input_files(ZIP, timeout=20000)
        print("UPLOADED via input#uploadFile", flush=True)
    except Exception as e:
        print("upload fail:", str(e)[:200], flush=True)

    for i in range(8):
        time.sleep(8)
        t = page.evaluate("document.body.innerText || ''")
        print(f"--- t+{(i+1)*8}s len={len(t)} ---", flush=True)
        print(t[:700], flush=True)
        if "PCB Price" in t and "PCB Size" in t:
            print("RENDERED", flush=True)
            break
    page.screenshot(path="/home/c03rad0r/repos/jlcpcb-service/snapshots/debug-quote.png", full_page=False)
    print("DONE", flush=True)
