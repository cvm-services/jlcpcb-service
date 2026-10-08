#!/usr/bin/env python3
"""Step 2: click 'Upload BOM & CPL' in PCBA mode and upload the v8h BOM + CPL.

Logs every discovery so one run yields the full picture:
  - what the dialog exposes (file inputs, expected formats)
  - whether the parts match (parts-selection result)
  - the resulting assembly price, if it renders
"""
import sys

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")

from jlcpcb_client.session import browser  # noqa: E402
from jlcpcb_client.selectors import GERBER_FILE_INPUT, QUOTE_URL  # noqa: E402

OUT = "/home/c03rad0r/worktrees/balloon-u2-integrate/tracker/hardware/output"
ZIP = f"{OUT}/gerbers_v8h_jlcpcb.zip"
BOM = f"{OUT}/jlc_bom_v8h_smt.csv"
CPL = f"{OUT}/cpl_v8h_jlc_smt.csv"

CLICK_ASM = """() => {
    const els = [...document.querySelectorAll('div,a,li,span')];
    const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                             && /PCB Assembly/i.test(e.innerText||''));
    if (sw) { sw.click(); return 'ok'; }
    return 'NOT FOUND';
}"""

CLICK_UPLOAD_BOM = """() => {
    const els = [...document.querySelectorAll('div,a,li,span,button')];
    const el = els.find(e => /^Upload BOM & CPL$/i.test((e.innerText||'').trim()));
    if (el) { el.click(); return 'clicked: ' + el.tagName + '.' + (el.className||'').slice(0,50); }
    return 'NOT FOUND';
}"""

FILES = """() => [...document.querySelectorAll('input[type=file]')].map(e => ({
    id:e.id, name:e.name, cls:(e.className||'').slice(0,40), accept:e.accept,
    visible: !!(e.offsetParent)}))"""

TEXT = "() => (document.body.innerText||'')"


def wait_for(page, needle, tries=20, step=8000):
    for i in range(tries):
        page.wait_for_timeout(step)
        t = page.evaluate(TEXT)
        if needle in t:
            return (i + 1) * step, t
    return None, page.evaluate(TEXT)


def main():
    with browser() as page:
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)
        t, _ = wait_for(page, "Calculated Price")
        print(f"gerber loaded at ~{t}s")

        print("pcba switch:", page.evaluate(CLICK_ASM))
        page.wait_for_timeout(9000)
        before = len(page.evaluate(FILES))
        print(f"file inputs before clicking upload-bom: {before}")

        print("upload-bom click:", page.evaluate(CLICK_UPLOAD_BOM))
        page.wait_for_timeout(8000)

        d = page.evaluate(FILES)
        print(f"file inputs after ({len(d)}):")
        for f in d:
            print("   ", f)

        if len(d) >= 2:
            ids = [f["id"] for f in d]
            # BOM and CPL are distinct inputs; order in DOM is BOM then CPL
            page.set_input_files(f"#{ids[0]}", BOM)
            print(f"uploaded BOM -> #{ids[0]}")
            page.wait_for_timeout(6000)
            page.set_input_files(f"#{ids[1]}", CPL)
            print(f"uploaded CPL -> #{ids[1]}")
            t2, txt = wait_for(page, "SMT Assembly", tries=25, step=6000)
            print(f"assembly section settled at ~{t2}s")
            # look for a price near SMT Assembly
            import re
            for m in re.finditer(r"[^\n]{0,60}\$[0-9][0-9.,]*[^\n]{0,40}", txt):
                print("PRICE-CTX:", m.group(0).strip()[:110])
        else:
            print("no file inputs appeared; dumping text")
            print(page.evaluate(TEXT)[:2000].replace("\n", " | "))


if __name__ == "__main__":
    sys.exit(main())
