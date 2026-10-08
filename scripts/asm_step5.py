#!/usr/bin/env python3
"""Step 5: scroll to force lazy render, then find+use the BOM/CPL upload control.

innerText skips off-screen nodes; textContent does not. The assembly panel is
lazy-rendered, so we scroll the page in steps before searching.
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

TEXT = "() => (document.body.innerText||'')"

CLICK_ASM = """() => {
    const els = [...document.querySelectorAll('div,li,span')];
    const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                             && /PCB Assembly/i.test(e.innerText||''));
    if (sw) { sw.click(); return 'clicked'; }
    return 'no-switch';
}"""

# search the WHOLE dom (textContent), including hidden/off-screen nodes
FIND_BOM_CTRL = """() => {
    const out = [];
    document.querySelectorAll('*').forEach(e => {
        const tc = (e.textContent||'').trim();
        if (tc.length < 40 && /upload.*bom|bom.*cpl/i.test(tc)) {
            out.push({tag:e.tagName, cls:(e.className||'').toString().slice(0,60),
                      txt:tc, visible: !!(e.offsetParent)});
        }
    });
    return out.slice(0,12);
}"""

CLICK_TEXT_ANY = """(needle) => {
    const all = [...document.querySelectorAll('*')];
    const hit = all.find(e => {
        const tc = (e.textContent||'').trim();
        return tc.length < 40 && new RegExp(needle, 'i').test(tc);
    });
    if (hit) { hit.click(); return 'clicked ' + hit.tagName; }
    return 'NOT FOUND';
}"""

FILES = """() => [...document.querySelectorAll('input[type=file]')].map(e => ({
    id:e.id, name:e.name, cls:(e.className||'').toString().slice(0,30)}))"""


def main():
    log = []

    def w(m):
        log.append(str(m))
        print(m)

    with browser() as page:
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)
        for i in range(20):
            page.wait_for_timeout(8000)
            t = page.evaluate(TEXT)
            if "Detected" in t and "Calculated Price" in t:
                w(f"quote ok ~{(i+1)*8}s")
                break

        w("asm: " + page.evaluate(CLICK_ASM))
        page.wait_for_timeout(8000)

        # force lazy render
        h = page.evaluate("() => document.body.scrollHeight")
        w(f"scrollHeight={h}")
        for y in range(0, min(h, 6000), 700):
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(700)
        page.evaluate("window.scrollTo(0,0)")
        page.wait_for_timeout(2500)

        w("\n--- dom nodes matching upload/bom ---")
        for e in page.evaluate(FIND_BOM_CTRL):
            w("   " + str(e))

        w("\nclick upload control: " + page.evaluate(CLICK_TEXT_ANY, "upload.{0,4}bom"))
        page.wait_for_timeout(9000)
        d = page.evaluate(FILES)
        w(f"file inputs after: {len(d)}  {d}")

        if len(d) >= 2:
            page.set_input_files(f"#{d[0]['id']}", BOM)
            w(f"BOM -> #{d[0]['id']}")
            page.wait_for_timeout(7000)
            page.set_input_files(f"#{d[1]['id']}", CPL)
            w(f"CPL -> #{d[1]['id']}")
            for i in range(30):
                page.wait_for_timeout(8000)
                t = page.evaluate(TEXT)
                if re.search(r"(SMT|Assembly)\s+Assembly[\s\S]{0,400}?\$\s?[1-9]", t):
                    break
            t = page.evaluate(TEXT)
            w("\n--- assembly / money lines ---")
            for ln in t.split("\n"):
                s = ln.strip()
                if re.search(r"Assembly|Setup|Extended|Parts|\\$[0-9]", s):
                    w("   " + s[:150])
            with open("/tmp/asm5_full.txt", "w") as f:
                f.write(t)
        else:
            with open("/tmp/asm5_full.txt", "w") as f:
                f.write(page.evaluate(TEXT))
            w("no inputs; full text dumped")

    with open("/tmp/asm5.log", "w") as f:
        f.write("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
