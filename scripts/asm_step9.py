#!/usr/bin/env python3
"""Step 9: step 8 plus the switch-box click it forgot.

Step 8's lesson: the PCBA panel does NOT exist until the "PCB Assembly"
switch-box is clicked. Without it, every option lookup fails and a loose
"NEXT" match lands on a tooltip. Step 7 proved the panel then renders inline
(Parts Selection / Assembly Side / PCBA Qty / T&C) with NO upload control, so
NEXT is the only way to reach the BOM/CPL stage.

READ-ONLY w.r.t. ordering: never clicks Place Order / Submit / Pay.
"""
import json
import sys

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")

from jlcpcb_client.session import browser  # noqa: E402
from jlcpcb_client.selectors import GERBER_FILE_INPUT, QUOTE_URL  # noqa: E402

OUT = "/home/c03rad0r/worktrees/balloon-u2-integrate/tracker/hardware/output"
ZIP = f"{OUT}/gerbers_v8h_jlcpcb.zip"
BOM = f"{OUT}/jlc_bom_v8h_smt.csv"
CPL = f"{OUT}/cpl_v8h_jlc_smt.csv"

TEXT = "() => (document.body.innerText||'')"
FILES = """() => [...document.querySelectorAll('input[type=file]')].map(e => ({
    id:e.id, name:e.name, accept:(e.accept||'').slice(0,40), vis:!!e.offsetParent}))"""

TURN_ON_ASM = """() => {
    const els = [...document.querySelectorAll('div,li,span,button,a,label')];
    const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                             && /PCB Assembly/i.test(e.innerText||''));
    if (sw) { sw.click(); return 'clicked switch-box'; }
    return 'NO switch-box';
}"""

CLICK_EXACT = """(want) => {
    const els = [...document.querySelectorAll('button,span,div,li,label,p,a')];
    const exact = els.filter(e => (e.innerText||'').trim() === want && e.children.length === 0);
    if (exact.length) { exact[exact.length-1].click(); return 'clicked exact x'+exact.length; }
    return 'NOT FOUND: ' + want;
}"""

FIND_NEXT = """() => {
    const els = [...document.querySelectorAll('button,div,span,a')];
    const cands = els.filter(e => (e.innerText||'').trim() === 'NEXT');
    return cands.map(e => ({tag: e.tagName, cls: (e.className||'').toString().slice(0,70),
                            vis: !!e.offsetParent, w: e.offsetWidth}));
}"""

CLICK_NEXT = """() => {
    const els = [...document.querySelectorAll('button,div,span,a')];
    const c = els.filter(e => (e.innerText||'').trim() === 'NEXT' && e.offsetParent);
    if (!c.length) return 'no visible NEXT';
    c[c.length-1].click();
    return 'clicked NEXT (' + c.length + ' candidates)';
}"""

CANDS = """() => [...document.querySelectorAll('button,a,div,span,label')]
    .filter(e => /upload|BOM|CPL|add to cart|assembly/i.test((e.innerText||''))
                 && (e.innerText||'').trim().length < 60)
    .map(e => e.tagName + '|' + (e.className||'').toString().slice(0,45) + '|'
              + (e.innerText||'').trim().replace(/\\n/g,' / '))
    .slice(0,30)"""


def main():
    log, net = [], []

    def w(m):
        log.append(str(m))
        print(m, flush=True)

    with browser() as page:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Network.enable")

        def on_request(p):
            try:
                r = p.get("request", {})
                u = r.get("url", "")
                if "cart.jlcpcb.com/api" in u and r.get("method") == "POST":
                    net.append({"url": u.split("?")[0], "len": len(r.get("postData") or ""),
                                "body": (r.get("postData") or "")[:3000]})
            except Exception:
                pass

        cdp.on("Network.requestWillBeSent", on_request)

        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)
        for i in range(20):
            page.wait_for_timeout(8000)
            if "Detected" in page.evaluate(TEXT):
                w(f"quote ok ~{(i+1)*8}s")
                break

        # --- toggle PCBA on, only if not already showing ---
        if "Parts Selection" not in page.evaluate(TEXT):
            w("asm: " + page.evaluate(TURN_ON_ASM))
            page.wait_for_timeout(12000)
        else:
            w("asm: already on")
        h = page.evaluate("() => document.body.scrollHeight")
        for y in range(0, min(h, 9000), 700):
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(300)

        t = page.evaluate(TEXT)
        w(f"panel present: Parts Selection={'Parts Selection' in t} "
          f"Assembly Side={'Assembly Side' in t}")

        w("\n=== set PCBA options ===")
        w("  " + page.evaluate(CLICK_EXACT, "By Customer (Self-Service)"))
        page.wait_for_timeout(4000)
        w("  " + page.evaluate(CLICK_EXACT, "Top Side"))
        page.wait_for_timeout(4000)
        w("  " + page.evaluate("""() => {
            const el = [...document.querySelectorAll('*')].find(e =>
                /I agree to the Terms and Conditions/i.test(e.textContent||'')
                && e.children.length === 0);
            if (!el) return 'no T&C';
            const box = el.closest('label')?.querySelector('input')
                     || document.querySelector('.el-checkbox__original');
            if (box) { box.click(); return 'ticked T&C'; }
            el.click(); return 'clicked T&C text';
        }"""))
        page.wait_for_timeout(6000)

        w("\n=== NEXT candidates ===")
        for c in page.evaluate(FIND_NEXT):
            w("   " + json.dumps(c))
        w("press: " + page.evaluate(CLICK_NEXT))
        page.wait_for_timeout(18000)
        w("url: " + page.url)

        h = page.evaluate("() => document.body.scrollHeight")
        for y in range(0, min(h, 9000), 700):
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(300)

        txt = page.evaluate(TEXT)
        open("/tmp/asm9_full.txt", "w").write(txt)
        w(f"text {len(txt)} chars -> /tmp/asm9_full.txt")
        inputs = page.evaluate(FILES)
        w(f"file inputs: {len(inputs)}")
        for f in inputs:
            w("   " + json.dumps(f))
        w("\n=== upload-ish candidates ===")
        for c in page.evaluate(CANDS):
            w("   " + c)

        if inputs:
            w("\n=== upload BOM + CPL ===")
            doc = cdp.send("DOM.getDocument", {"depth": -1})
            for f in inputs:
                if not f.get("id"):
                    continue
                try:
                    nid = cdp.send("DOM.querySelector", {
                        "nodeId": doc["root"]["nodeId"],
                        "selector": f"#{f['id']}"}).get("nodeId")
                    hint = (f["id"] + f.get("name", "")).lower()
                    path = CPL if ("cpl" in hint or "place" in hint) else BOM
                    cdp.send("DOM.setFileInputFiles", {"files": [path], "nodeId": nid})
                    w(f"   {f['id']} <- {path.split('/')[-1]}")
                    page.wait_for_timeout(10000)
                except Exception as e:
                    w(f"   {f['id']}: {type(e).__name__} {str(e)[:90]}")
            page.wait_for_timeout(30000)
            open("/tmp/asm9_after.txt", "w").write(page.evaluate(TEXT))
            w("wrote /tmp/asm9_after.txt")

    json.dump(net, open("/tmp/asm9_net.json", "w"), indent=1)
    open("/tmp/asm9.log", "w").write("\n".join(log))
    w(f"\ncaptured {len(net)} POSTs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
