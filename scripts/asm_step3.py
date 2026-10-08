#!/usr/bin/env python3
"""Step 3: idempotently enter PCBA mode, upload BOM+CPL, read the assembly price.

Fixes from step 2:
  * the PCBA toggle is persisted in the profile's SPA state, so a blind click
    can turn it OFF. ensure_pcba() checks for the marker and only clicks when
    it is absent.
  * the full page text is dumped (not truncated) so one run answers everything.
"""
import re
import sys

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")

from jlcpcb_client.session import browser  # noqa: E402
from jlcpcb_client.selectors import GERBER_FILE_INPUT, QUOTE_URL  # noqa: E402

OUT = "/home/c03rad0r/worktrees/balloon-u2-integrate/tracker/hardware/output"
ZIP = f"{OUT}/gerbers_v8h_jlcpcb.zip"
BOM = f"{OUT}/jlc_bom_v8h_smt.csv"
CPL = f"{OUT}/cpl_v8h_jlc_smt.csv"

MARKER = "Upload BOM & CPL"

TEXT = "() => (document.body.innerText||'')"

CLICK_ASM = """() => {
    const els = [...document.querySelectorAll('div,a,li,span')];
    const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                             && /PCB Assembly/i.test(e.innerText||''));
    if (sw) { sw.click(); return 'clicked'; }
    return 'no-switch';
}"""

CLICK = """(label) => {
    const els = [...document.querySelectorAll('div,a,li,span,button')];
    const el = els.find(e => (e.innerText||'').trim() === label);
    if (el) { el.click(); return 'clicked ' + el.tagName; }
    return 'NOT FOUND: ' + label;
}"""

FILES = """() => [...document.querySelectorAll('input[type=file]')].map(e => ({
    id:e.id, name:e.name, cls:(e.className||'').slice(0,30), accept:e.accept}))"""


def ensure_pcba(page, log):
    """Make PCBA mode ON, without toggling it off if already on."""
    for attempt in range(6):
        txt = page.evaluate(TEXT)
        if MARKER in txt:
            log(f"PCBA mode ON (attempt {attempt})")
            return True
        r = page.evaluate(CLICK_ASM)
        log(f"attempt {attempt}: marker absent, clicked switch -> {r}")
        page.wait_for_timeout(9000)
    log("PCBA mode could not be entered")
    return False


def main():
    lines = []

    def log(m):
        lines.append(str(m))
        print(m)

    with browser() as page:
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)
        for i in range(20):
            page.wait_for_timeout(8000)
            if "Calculated Price" in page.evaluate(TEXT):
                log(f"gerber loaded after ~{(i+1)*8}s")
                break

        if not ensure_pcba(page, log):
            return 1

        log(page.evaluate("label => label", ""))  # noop keeps signature simple
        log("click upload: " + page.evaluate(CLICK, MARKER))
        page.wait_for_timeout(9000)

        d = page.evaluate(FILES)
        log(f"file inputs: {len(d)}")
        for f in d:
            log("   " + str(f))

        if len(d) >= 2:
            page.set_input_files(f"#{d[0]['id']}", BOM)
            log(f"uploaded BOM -> #{d[0]['id']}")
            page.wait_for_timeout(7000)
            page.set_input_files(f"#{d[1]['id']}", CPL)
            log(f"uploaded CPL -> #{d[1]['id']}")
            for i in range(25):
                page.wait_for_timeout(8000)
                t = page.evaluate(TEXT)
                if "SMT Assembly" in t and "$" in t:
                    break
            txt = page.evaluate(TEXT)
            log(f"\n=== ASSEMBLY-RELATED LINES (len {len(txt)}) ===")
            for ln in txt.split("\n"):
                s = ln.strip()
                if re.search(r"SMT Assembly|Manual Assembly|Assembly cost|Setup|Extended|Parts|\\$[0-9]", s):
                    log("  " + s[:150])
            log("\n=== ALL MONEY AMOUNTS ===")
            seen = set()
            for m in re.finditer(r"\\$\\s?[0-9][0-9,]*(?:\\.\\d+)?", txt):
                v = m.group(0)
                if v not in seen:
                    seen.add(v)
                    log("  " + v)
            with open("/tmp/asm_full_text.txt", "w") as f:
                f.write(txt)
            log("full text -> /tmp/asm_full_text.txt")
        else:
            log("no file inputs; full text follows")
            with open("/tmp/asm_full_text.txt", "w") as f:
                f.write(page.evaluate(TEXT))

    with open("/tmp/asm3b.log", "w") as f:
        f.write("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
