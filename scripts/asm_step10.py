#!/usr/bin/env python3
"""Step 10: go straight to the SMT order page and upload BOM+CPL.

Step 9 broke the flow open:
    NEXT  ->  https://cart.jlcpcb.com/smt-order/?pcbFileNo=<id>

That URL is the assembly (BOM/CPL) stage, and it is addressable by a handle we
can read off the page — no blind clicking. The 1693-char text was just the SPA
still hydrating, hence the generous polling here.

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
SMT_BASE = "https://cart.jlcpcb.com/smt-order/"

TEXT = "() => (document.body.innerText||'')"
FILES = """() => [...document.querySelectorAll('input[type=file]')].map(e => ({
    id:e.id, name:e.name, accept:(e.accept||'').slice(0,40), vis:!!e.offsetParent}))"""


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
                                "body": (r.get("postData") or "")[:4000]})
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

        # ---- reach the SMT page ----
        w("asm: " + page.evaluate("""() => {
            const sw = [...document.querySelectorAll('div,li,span,button,a,label')]
                .find(e => (e.className||'').toString().includes('switch-box')
                           && /PCB Assembly/i.test(e.innerText||''));
            if (sw) { sw.click(); return 'toggled on'; }
            return 'already on';
        }"""))
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
            const c = [...document.querySelectorAll('button,span,div,a')]
                .filter(e => (e.innerText||'').trim() === 'NEXT' && e.offsetParent);
            if (c.length) c[c.length-1].click();
        }""")
        page.wait_for_timeout(12000)
        w("after NEXT url: " + page.url)

        # ---- if the SPA put us elsewhere, navigate explicitly ----
        if "smt-order" not in page.url:
            import re
            w("not on smt-order; looking for pcbFileNo")
            m = re.search(r"pcbFileNo=([0-9a-f]+)", json.dumps(net))
            if m:
                page.goto(f"{SMT_BASE}?pcbFileNo={m.group(1)}",
                          wait_until="commit", timeout=90000)
                w("nav'd explicitly to smt-order")
        page.wait_for_timeout(15000)

        # ---- poll for the upload UI ----
        inputs = []
        for i in range(12):
            page.wait_for_timeout(8000)
            t = page.evaluate(TEXT)
            inputs = page.evaluate(FILES)
            w(f"  t+{(i+1)*8}s text={len(t)} inputs={len(inputs)} "
              f"BOM={'BOM' in t} CPL={'CPL' in t}")
            if inputs or ("BOM" in t and "CPL" in t):
                break

        txt = page.evaluate(TEXT)
        open("/tmp/asm10_full.txt", "w").write(txt)
        w(f"\ntext {len(txt)} chars -> /tmp/asm10_full.txt")
        w("file inputs:")
        for f in inputs:
            w("   " + json.dumps(f))
        w("\n=== upload-ish controls ===")
        for c in page.evaluate("""() => [...document.querySelectorAll('button,a,div,span,label')]
            .filter(e => /upload|BOM|CPL/i.test(e.innerText||'')
                         && (e.innerText||'').trim().length < 60)
            .map(e => e.tagName + '|' + (e.className||'').toString().slice(0,50) + '|'
                      + (e.innerText||'').trim().replace(/\\n/g,' / ')).slice(0,40)"""):
            w("   " + c)

        # ---- upload ----
        if inputs:
            w("\n=== uploading ===")
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
                    page.wait_for_timeout(12000)
                except Exception as e:
                    w(f"   {f['id']}: {type(e).__name__} {str(e)[:90]}")
            for i in range(10):
                page.wait_for_timeout(8000)
                t = page.evaluate(TEXT)
                if "$" in t and ("Assembly" in t or "SMT" in t):
                    break
            open("/tmp/asm10_after.txt", "w").write(page.evaluate(TEXT))
            w("wrote /tmp/asm10_after.txt")

    json.dump(net, open("/tmp/asm10_net.json", "w"), indent=1)
    open("/tmp/asm10.log", "w").write("\n".join(log))
    w(f"\ncaptured {len(net)} POSTs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
