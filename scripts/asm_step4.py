#!/usr/bin/env python3
"""Step 4: capture the XHR/API traffic the PCBA assembly flow uses.

Discovery by interception rather than clicking: every request whose URL looks
like quote/assembly/price is logged, so the real API is known even if a UI
toggle fails. Also dumps visible BOM/CPL controls.
"""
import json
import sys

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")

from jlcpcb_client.session import browser  # noqa: E402
from jlcpcb_client.selectors import GERBER_FILE_INPUT, QUOTE_URL  # noqa: E402

OUT = "/home/c03rad0r/worktrees/balloon-u2-integrate/tracker/hardware/output"
ZIP = f"{OUT}/gerbers_v8h_jlcpcb.zip"

TEXT = "() => (document.body.innerText||'')"

CLICK_TEXT = """(label) => {
    const els = [...document.querySelectorAll('div,a,li,span,button')];
    const vis = els.filter(e => (e.innerText||'').trim() === label);
    if (vis.length) { vis[0].click(); return 'clicked ' + vis.length; }
    const any = els.filter(e => (e.innerText||'').trim().includes(label));
    if (any.length) { any[0].click(); return 'partial->clicked'; }
    return 'NOT FOUND';
}"""

CLICK_ASM = """() => {
    const els = [...document.querySelectorAll('div,a,li,span')];
    const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                             && /PCB Assembly/i.test(e.innerText||''));
    if (sw) { sw.click(); return 'clicked'; }
    return 'no-switch';
}"""


def main():
    log = []
    reqs = []

    def w(m):
        log.append(str(m))
        print(m)

    with browser() as page:
        def on_req(r):
            u = r.url
            if any(k in u.lower() for k in
                   ("quote", "assembly", "smt", "price", "cost", "bom", "part", "cart")):
                if not any(u.endswith(e) for e in (".js", ".css", ".png", ".svg", ".woff2")):
                    reqs.append((r.method, u))

        page.on("request", on_req)
        page.on("response", lambda r: None)

        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        w("authed: " + str("My Account" in page.evaluate(TEXT)))
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)

        for i in range(20):
            page.wait_for_timeout(8000)
            t = page.evaluate(TEXT)
            if "Detected" in t and "Calculated Price" in t:
                w(f"quote ok after ~{(i+1)*8}s")
                break

        before = page.evaluate(TEXT)
        w("marker before click: " + str("Upload BOM & CPL" in before))
        w("asm click: " + page.evaluate(CLICK_ASM))
        page.wait_for_timeout(12000)
        after = page.evaluate(TEXT)
        w("marker after click: " + str("Upload BOM & CPL" in after))
        w("text grew by: " + str(len(after) - len(before)))

        w("\n--- BOM/CPL + assembly visible text after click ---")
        for ln in after.split("\n"):
            s = ln.strip()
            if any(k in s for k in ("BOM", "CPL", "Assembly Side", "Parts Selection",
                                    "NEXT", "SMT Assembly", "Manual Assembly", "$")):
                w("   " + s[:140])

        # try NEXT as the alternate route into the assembly step
        w("\nclicking NEXT: " + page.evaluate(CLICK_TEXT, "NEXT"))
        page.wait_for_timeout(12000)
        after2 = page.evaluate(TEXT)
        w("url now: " + page.url)
        w("marker after NEXT: " + str("Upload BOM & CPL" in after2))
        for ln in after2.split("\n"):
            s = ln.strip()
            if any(k in s for k in ("BOM", "CPL", "Assembly Side", "Parts Selection",
                                    "SMT Assembly", "Manual Assembly", "$")):
                w("   " + s[:140])

        w("\n--- API endpoints seen ---")
        seen = set()
        for m, u in reqs:
            key = (m, u.split("?")[0])
            if key in seen:
                continue
            seen.add(key)
            w(f"   {m} {u[:160]}")

        with open("/tmp/asm4_full.txt", "w") as f:
            f.write(after2)
        with open("/tmp/asm4_reqs.json", "w") as f:
            json.dump(reqs, f, indent=2)

    with open("/tmp/asm4.log", "w") as f:
        f.write("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
