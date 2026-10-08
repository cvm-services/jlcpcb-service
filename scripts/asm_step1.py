#!/usr/bin/env python3
"""Step 1: upload v8h gerbers, then enter PCBA mode and find the BOM/CPL inputs."""
import sys

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")

from jlcpcb_client.session import browser  # noqa: E402
from jlcpcb_client.selectors import GERBER_FILE_INPUT, QUOTE_URL  # noqa: E402

ZIP = ("/home/c03rad0r/worktrees/balloon-u2-integrate/tracker/hardware/output/"
       "gerbers_v8h_jlcpcb.zip")

CLICK_ASM = """() => {
    const els = [...document.querySelectorAll('div,a,li,span')];
    const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                             && /PCB Assembly/i.test(e.innerText||''));
    if (sw) { sw.click(); return 'clicked switch-box'; }
    return 'NOT FOUND';
}"""

DUMP = """() => {
    const files = [...document.querySelectorAll('input[type=file]')].map(e => ({
        id: e.id, name: e.name, cls: (e.className||'').slice(0,40), accept: e.accept}));
    const btns = [];
    document.querySelectorAll('button,a,div,span,li').forEach(e => {
        const t = (e.innerText||'').trim();
        if (!t || t.length > 70) return;
        if (/BOM|CPL|pick.?and.?place|assembly|parts|next|Matching/i.test(t)) btns.push(t.replace(/\\n/g,' | '));
    });
    return {files, btns: [...new Set(btns)].slice(0,40),
            body: (document.body.innerText||'').slice(0,900)};
}"""


def main():
    with browser() as page:
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        print("authed:", "My Account" in page.evaluate("document.body.innerText||''"))

        inp = page.query_selector(GERBER_FILE_INPUT)
        print("gerber input found:", bool(inp))
        inp.set_input_files(ZIP)
        print("uploaded gerber zip, waiting for detection...")

        for i in range(20):
            page.wait_for_timeout(8000)
            t = page.evaluate("document.body.innerText||''")
            if "Detected" in t and "Calculated Price" in t:
                print(f"quote rendered at t+{(i+1)*8}s")
                break
        else:
            print("quote did not render")

        print("\n--- entering PCBA mode ---")
        print(page.evaluate(CLICK_ASM))
        page.wait_for_timeout(10000)

        d = page.evaluate(DUMP)
        print(f"\nfile inputs ({len(d['files'])}):")
        for f in d["files"]:
            print("   ", f)
        print(f"\ncontrols ({len(d['btns'])}):")
        for b in d["btns"]:
            print("   ", b)
        print("\n--- body ---")
        print(d["body"].replace("\n", " | "))


if __name__ == "__main__":
    sys.exit(main())
