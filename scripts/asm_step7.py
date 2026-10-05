#!/usr/bin/env python3
"""Step 7: crack the PCBA BOM/CPL upload panel AND capture the wire.

Step 6 was written but never run. This is 6 + three things it lacked:

  1. A CDP `DOM.setFileInputFiles` fallback, because the panel's inputs are
     hidden (`offsetParent == false`) and Playwright's `set_input_files`
     refuses invisible elements.
  2. A network listener that logs every POST to cart.jlcpcb.com with its
     payload key-shape. This is what makes the API replay possible at all:
     the config/whitelist calls were captured before, but the load-bearing
     BOM/CPL upload call never was, because the upload never happened.
  3. Reads the money strings off the assembled page.

READ-ONLY: uploads BOM+CPL to obtain a quote. Never clicks Add to Cart or
Place Order. The panel toggle persists in the profile, so we only ever click
it if the panel is not already open.
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

# --- panel state, read BEFORE clicking anything (the toggle persists) -------
PANEL_STATE = """() => {
    const items = [...document.querySelectorAll('.el-collapse-item')];
    return items.map(it => ({
        header: (it.querySelector('.el-collapse-item__header')||{}).innerText || '',
        active: (it.className||'').includes('is-active'),
        bodyH: (it.querySelector('.el-collapse-item__wrap')||{}).offsetHeight || 0,
    }));
}"""

EXPAND_ALL = """() => {
    const hs = [...document.querySelectorAll('.el-collapse-item__header')];
    let n = 0;
    hs.forEach(h => {
        const it = h.closest('.el-collapse-item');
        if (it && !(it.className||'').includes('is-active')) { h.click(); n++; }
    });
    return 'expanded ' + n + ' of ' + hs.length;
}"""

FILES = """() => [...document.querySelectorAll('input[type=file]')].map(e => ({
    id:e.id, name:e.name, accept:(e.accept||'').slice(0,40),
    vis: !!e.offsetParent, h: e.offsetHeight}))"""

MONEY = """() => {
    const t = document.body.innerText || '';
    const out = {};
    for (const line of t.split('\\n')) {
        const m = line.match(/^\\s*([A-Za-z][A-Za-z /&()-]{2,40}?)\\s*\\$([0-9,]+\\.[0-9]{2})/);
        if (m) out[m[1].trim()] = '$' + m[2];
    }
    return out;
}"""


def main():
    log = []
    net = []

    def w(m):
        log.append(str(m))
        print(m, flush=True)

    with browser() as page:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Network.enable")

        def on_request(p):
            try:
                u = p.get("request", {}).get("url", "")
                if "cart.jlcpcb.com/api" not in u:
                    return
                m = p.get("request", {}).get("method", "")
                if m != "POST":
                    return
                pd = p.get("request", {}).get("postData", "") or ""
                net.append({
                    "url": u.split("?")[0],
                    "method": m,
                    "len": len(pd),
                    "body": pd[:2000],
                    "ct": p.get("request", {}).get("headers", {}).get("Content-Type", ""),
                })
            except Exception:
                pass

        cdp.on("Network.requestWillBeSent", on_request)

        # ---------- 1. produce the bare-PCB quote ----------
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)
        for i in range(20):
            page.wait_for_timeout(8000)
            t = page.evaluate(TEXT)
            if "Detected" in t and "Calculated Price" in t:
                w(f"bare-PCB quote ok ~{(i+1)*8}s")
                break
        else:
            w("WARN: bare-PCB quote never rendered")

        w("\n=== panel state BEFORE any click ===")
        for st in page.evaluate(PANEL_STATE):
            w("   " + json.dumps(st))
        w("file inputs before: " + json.dumps(page.evaluate(FILES)))

        # ---------- 2. switch to assembly ----------
        w("\n=== switch to assembly mode ===")
        w(page.evaluate("""() => {
            const els = [...document.querySelectorAll('div,li,span,button,a')];
            const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                                     && /PCB Assembly/i.test(e.innerText||''));
            if (sw) { sw.click(); return 'clicked switch-box'; }
            const li = els.find(e => e.tagName==='LI' && /^PCB Assembly$/i.test((e.innerText||'').trim()));
            if (li) { li.click(); return 'clicked nav LI'; }
            return 'NOT FOUND';
        }"""))
        page.wait_for_timeout(12000)

        # scroll to force lazy mount
        h = page.evaluate("() => document.body.scrollHeight")
        for y in range(0, min(h, 7000), 600):
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(400)

        w("\n=== panel state after asm switch ===")
        for st in page.evaluate(PANEL_STATE):
            w("   " + json.dumps(st))

        # ---------- 3. reveal the upload panel ----------
        w("\nexpand: " + page.evaluate(EXPAND_ALL))
        page.wait_for_timeout(5000)
        w("tabs: " + page.evaluate("""() => {
            const tabs = [...document.querySelectorAll('.el-tabs__item,[role=tab],.el-radio-button')];
            const hit = tabs.find(t => /assembl|bom|part/i.test(t.innerText||''));
            if (hit) { hit.click(); return 'clicked: ' + hit.innerText.slice(0,40); }
            return 'no tab; ' + tabs.map(t=>(t.innerText||'').slice(0,16)).join('|').slice(0,140);
        }"""))
        page.wait_for_timeout(7000)

        inputs = page.evaluate(FILES)
        w(f"\n=== file inputs after reveal: {len(inputs)} ===")
        for f in inputs:
            w("   " + json.dumps(f))

        # ---------- 4. upload BOM + CPL via CDP (hidden inputs OK) ----------
        if inputs:
            w("\n=== uploading via CDP DOM.setFileInputFiles ===")
            doc = cdp.send("DOM.getDocument", {"depth": -1})
            for f in inputs:
                if not f.get("id"):
                    continue
                try:
                    node = cdp.send("DOM.querySelector", {
                        "nodeId": doc["root"]["nodeId"],
                        "selector": f"#{f['id']}"})
                    nid = node.get("nodeId")
                    if not nid:
                        w(f"   {f['id']}: no node"); continue
                    # pick BOM vs CPL by id/name hint, else two-step
                    hint = (f["id"] + f.get("name", "")).lower()
                    path = CPL if "cpl" in hint or "place" in hint else BOM
                    cdp.send("DOM.setFileInputFiles", {"files": [path], "nodeId": nid})
                    w(f"   {f['id']} <- {path.split('/')[-1]}")
                    page.wait_for_timeout(6000)
                    net.append({"MARK": f"uploaded {f['id']}"})
                except Exception as e:
                    w(f"   {f['id']}: FAILED {type(e).__name__}: {str(e)[:120]}")
            # if only one input existed, try the second file too
            if len(inputs) == 1 and inputs[0].get("id"):
                try:
                    node = cdp.send("DOM.querySelector", {
                        "nodeId": doc["root"]["nodeId"],
                        "selector": f"#{inputs[0]['id']}"})
                    cdp.send("DOM.setFileInputFiles",
                             {"files": [CPL], "nodeId": node["nodeId"]})
                    w(f"   (2nd) {inputs[0]['id']} <- {CPL.split('/')[-1]}")
                except Exception as e:
                    w("   2nd upload failed: " + str(e)[:100])

            page.wait_for_timeout(25000)
        else:
            w("STILL no file inputs — panel not revealed by expand/tab")

        # ---------- 5. read the numbers ----------
        w("\n=== page money lines ===")
        w(json.dumps(page.evaluate(MONEY), indent=2))
        txt = page.evaluate(TEXT)
        open("/tmp/asm7_full.txt", "w").write(txt)
        w(f"({len(txt)} chars -> /tmp/asm7_full.txt)")

    json.dump(net, open("/tmp/asm7_net.json", "w"), indent=1)
    open("/tmp/asm7.log", "w").write("\n".join(log))
    w(f"\ncaptured {len([x for x in net if 'url' in x])} POSTs -> /tmp/asm7_net.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
