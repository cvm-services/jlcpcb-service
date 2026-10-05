#!/usr/bin/env python3
"""Step 11: walk the smt-order 4-step wizard and produce a real assembly quote.

Step 10 revealed the missing structure. The smt-order page is a wizard:

    PCB | Bill of Materials | Component Placements | Quote & Order
    PCBA Type: Economic | Assembly Side: Top Side | PCBA Qty: 5

Previous scripts scanned `.el-tabs__item` for /bom/ and found nothing, because
these steps are custom elements — yet "Bill of Materials" is plainly in the page
text. So the upload lives one click further in, not on the quote page.

This run: upload gerber -> PCBA on -> NEXT -> click each step by TEXT ->
upload BOM -> upload CPL -> read Quote & Order.

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

MONEY = """() => {
    const out = {};
    for (const line of (document.body.innerText||'').split('\\n')) {
        const m = line.match(/^\\s*([A-Za-z][A-Za-z /&()#-]{2,44}?)\\s*\\$\\s*([0-9,]+\\.[0-9]{2})/);
        if (m) out[m[1].trim()] = '$' + m[2];
    }
    return out;
}"""

STEP = """(want) => {
    const els = [...document.querySelectorAll('*')];
    const cands = els.filter(e => (e.textContent||'').trim() === want && e.children.length === 0);
    if (!cands.length) return 'NOT FOUND: ' + want;
    const e = cands[0];
    // click the nearest clickable ancestor, else the node itself
    let t = e;
    for (let i = 0; i < 4 && t.parentElement; i++) {
        t = t.parentElement;
        if (['LI','BUTTON','A'].includes(t.tagName)
            || /tab|step|nav|item/i.test((t.className||'').toString())) break;
    }
    t.click();
    return 'clicked ' + t.tagName + '/' + (t.className||'').toString().slice(0,40);
}"""


def wait_for(page, needle, tries=12, step=5000):
    for i in range(tries):
        page.wait_for_timeout(step)
        if needle in page.evaluate(TEXT):
            return i * step // 1000
    return None


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
                                "body": (r.get("postData") or "")[:5000]})
            except Exception:
                pass

        cdp.on("Network.requestWillBeSent", on_request)

        # ---------- quote page ----------
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)
        w("quote render: " + str(wait_for(page, "Detected", 20, 8000)) + "s")

        page.evaluate("""() => {
            const sw = [...document.querySelectorAll('div,li,span,button,a,label')]
                .find(e => (e.className||'').toString().includes('switch-box')
                           && /PCB Assembly/i.test(e.innerText||''));
            if (sw) sw.click();
        }""")
        page.wait_for_timeout(12000)
        h = page.evaluate("() => document.body.scrollHeight")
        for y in range(0, min(h, 9000), 700):
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(300)
        page.evaluate("""() => {
            const c = [...document.querySelectorAll('button,span,div,li,label,p,a')]
                .filter(e => (e.innerText||'').trim() === 'By Customer (Self-Service)'
                             && e.children.length === 0);
            if (c.length) c[c.length-1].click();
        }""")
        page.wait_for_timeout(5000)
        page.evaluate("""() => {
            const c = [...document.querySelectorAll('button,div,span,a')]
                .filter(e => (e.innerText||'').trim() === 'NEXT' && e.offsetParent);
            if (c.length) c[c.length-1].click();
        }""")
        page.wait_for_timeout(14000)
        w("wizard url: " + page.url)
        w("wizard ready: " + str(wait_for(page, "Bill of Materials", 8, 5000)) + "s")

        # ---------- STEP 2: Bill of Materials ----------
        w("\n=== [2] Bill of Materials ===")
        w("  " + page.evaluate(STEP, "Bill of Materials"))
        page.wait_for_timeout(10000)
        inputs = page.evaluate(FILES)
        w(f"  file inputs: {len(inputs)}")
        for f in inputs:
            w("     " + json.dumps(f))
        t = page.evaluate(TEXT)
        open("/tmp/asm11_bom.txt", "w").write(t)

        doc = cdp.send("DOM.getDocument", {"depth": -1})

        def upload(fid, path):
            nid = cdp.send("DOM.querySelector", {
                "nodeId": doc["root"]["nodeId"], "selector": f"#{fid}"}).get("nodeId")
            if not nid:
                return "no node"
            cdp.send("DOM.setFileInputFiles", {"files": [path], "nodeId": nid})
            return "ok"

        up_bom = [f for f in inputs if f.get("id") and
                  ("bom" in (f["id"] + f.get("name", "")).lower() or len(inputs) == 1)]
        for f in up_bom:
            w(f"  upload BOM -> {f['id']}: {upload(f['id'], BOM)}")
            page.wait_for_timeout(15000)

        w("  matching wait: " + str(wait_for(page, "Component", 10, 6000)) + "s")
        open("/tmp/asm11_bom_after.txt", "w").write(page.evaluate(TEXT))

        # ---------- STEP 3: Component Placements ----------
        w("\n=== [3] Component Placements ===")
        w("  " + page.evaluate(STEP, "Component Placements"))
        page.wait_for_timeout(10000)
        inputs = page.evaluate(FILES)
        w(f"  file inputs: {len(inputs)}")
        for f in inputs:
            w("     " + json.dumps(f))
        for f in [x for x in inputs if x.get("id")]:
            w(f"  upload CPL -> {f['id']}: {upload(f['id'], CPL)}")
            page.wait_for_timeout(15000)
        page.wait_for_timeout(10000)
        open("/tmp/asm11_cpl_after.txt", "w").write(page.evaluate(TEXT))

        # ---------- STEP 4: Quote & Order ----------
        w("\n=== [4] Quote & Order ===")
        w("  " + page.evaluate(STEP, "Quote & Order"))
        page.wait_for_timeout(15000)
        w("  money: " + json.dumps(page.evaluate(MONEY), indent=2))
        open("/tmp/asm11_quote.txt", "w").write(page.evaluate(TEXT))
        w("  wrote /tmp/asm11_quote.txt")

    json.dump(net, open("/tmp/asm11_net.json", "w"), indent=1)
    open("/tmp/asm11.log", "w").write("\n".join(log))
    w(f"\ncaptured {len(net)} POSTs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
