#!/usr/bin/env python3
"""Step 8: walk NEXT off the quote page to find the real BOM/CPL upload.

Established by step 7:
  * The PCBA panel renders INLINE (not an el-collapse-item): Parts Selection,
    Assembly Side, PCBA Qty, Tooling holes, T&C checkbox.
  * There is NO upload control on the quote page. "Upload BOM & CPL" only
    appears on a LATER stage — which is why every earlier attempt found zero
    file inputs while looking at the quote page.
  * The $66.20 line is the "2-3 days" build-time option, NOT an assembly price.

So: set the PCBA options, tick the T&C, press NEXT, and see where we land.
READ-ONLY with respect to ordering: never clicks Place Order / Submit / Pay.
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
        const m = line.match(/^\\s*([A-Za-z][A-Za-z /&()-]{2,40}?)\\s*\\$([0-9,]+\\.[0-9]{2})/);
        if (m) out[m[1].trim()] = '$' + m[2];
    }
    return out;
}"""

# click any clickable whose trimmed text matches exactly
CLICK_TEXT = """(want) => {
    const els = [...document.querySelectorAll('button,a,span,div,li,label,p')];
    const hit = els.find(e => (e.innerText||'').trim() === want && e.children.length <= 2);
    if (hit) { hit.click(); return 'clicked: ' + want; }
    const loose = els.find(e => (e.innerText||'').trim().toLowerCase().includes(want.toLowerCase()));
    if (loose) { loose.click(); return 'loose-clicked: ' + (loose.innerText||'').trim().slice(0,40); }
    return 'NOT FOUND: ' + want;
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
                r = p.get("request", {})
                u = r.get("url", "")
                if "cart.jlcpcb.com/api" not in u or r.get("method") != "POST":
                    return
                net.append({"url": u.split("?")[0], "len": len(r.get("postData") or ""),
                            "body": (r.get("postData") or "")[:3000],
                            "ct": r.get("headers", {}).get("Content-Type", "")})
            except Exception:
                pass

        cdp.on("Network.requestWillBeSent", on_request)

        # ---------- 1. bare-PCB quote ----------
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)
        for i in range(20):
            page.wait_for_timeout(8000)
            if "Detected" in page.evaluate(TEXT):
                w(f"quote ok ~{(i+1)*8}s")
                break

        # ---------- 2. PCBA options ----------
        w("\n=== set PCBA options ===")
        w("  " + page.evaluate(CLICK_TEXT, "By Customer (Self-Service)"))
        page.wait_for_timeout(4000)
        w("  " + page.evaluate(CLICK_TEXT, "Top Side"))
        page.wait_for_timeout(4000)
        w("  " + page.evaluate(CLICK_TEXT, "Economic"))
        page.wait_for_timeout(4000)

        # T&C checkbox — find it by its label text, then click the input
        w("  " + page.evaluate("""() => {
            const el = [...document.querySelectorAll('*')].find(e =>
                /I agree to the Terms and Conditions/i.test(e.textContent||'')
                && e.children.length === 0);
            if (!el) return 'no T&C label';
            const box = el.closest('label')?.querySelector('input')
                     || document.querySelector('.el-checkbox__original');
            if (box) { box.click(); return 'ticked T&C'; }
            el.click(); return 'clicked T&C text';
        }"""))
        page.wait_for_timeout(3000)
        w("  money now: " + json.dumps(page.evaluate(MONEY)))

        # ---------- 3. NEXT ----------
        w("\n=== press NEXT ===")
        w("  " + page.evaluate(CLICK_TEXT, "NEXT"))
        page.wait_for_timeout(15000)
        w("  url: " + page.url)
        h = page.evaluate("() => document.body.scrollHeight")
        for y in range(0, min(h, 8000), 700):
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(400)

        inputs = page.evaluate(FILES)
        w(f"  file inputs: {len(inputs)}")
        for f in inputs:
            w("     " + json.dumps(f))

        txt = page.evaluate(TEXT)
        open("/tmp/asm8_full.txt", "w").write(txt)
        w(f"  text {len(txt)} chars -> /tmp/asm8_full.txt")
        for s in ["Upload BOM & CPL", "BOM", "CPL", "Parts Selection",
                  "Add to Cart", "Shopping Cart", "Assembly Side"]:
            w(f"     {s!r} in page: {s in txt}")

        # ---------- 4. upload if we found inputs ----------
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
                    page.wait_for_timeout(8000)
                except Exception as e:
                    w(f"   {f['id']}: {type(e).__name__} {str(e)[:100]}")
            page.wait_for_timeout(25000)
            w("\n=== money after upload ===")
            w(json.dumps(page.evaluate(MONEY), indent=2))
            open("/tmp/asm8_after.txt", "w").write(page.evaluate(TEXT))

    json.dump(net, open("/tmp/asm8_net.json", "w"), indent=1)
    open("/tmp/asm8.log", "w").write("\n".join(log))
    w(f"\ncaptured {len(net)} POSTs -> /tmp/asm8_net.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
