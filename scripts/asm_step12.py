#!/usr/bin/env python3
"""Step 12: full assembly quote. Fixes step 11's two real bugs.

Bug 1: the tab is literally "Bill of Materials" — which contains NO "bom"
substring, so every `/bom/i` tab scan in steps 1-9 silently missed it.
Bug 2: the BOM/CPL inputs have id="" (name="file"), so the `#id` selector
in step 11 skipped them. Use DOM.querySelectorAll and address by index.

Wizard: PCB | Bill of Materials | Component Placements | Quote & Order
("Component Placements" is is-disabled until the BOM is accepted.)

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
MONEY = """() => {
    const out = {};
    for (const line of (document.body.innerText||'').split('\\n')) {
        const m = line.match(/^\\s*([A-Za-z][A-Za-z /&()#-]{2,44}?)\\s*\\$\\s*([0-9,]+\\.[0-9]{2})/);
        if (m) out[m[1].trim()] = '$' + m[2];
    }
    return out;
}"""


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
                                "body": (r.get("postData") or "")[:6000]})
            except Exception:
                pass

        cdp.on("Network.requestWillBeSent", on_request)

        def click_tab(label):
            return page.evaluate("""(want) => {
                const tabs = [...document.querySelectorAll('.el-tabs__item, [role=tab]')];
                const hit = tabs.find(t => (t.innerText||'').trim() === want);
                if (!hit) return 'NO TAB: ' + want + ' | have: '
                    + tabs.map(t=>(t.innerText||'').trim()).join(',');
                const dis = (hit.className||'').includes('is-disabled');
                hit.click();
                return 'clicked ' + want + (dis ? ' (was DISABLED)' : '');
            }""", label)

        def file_nodes():
            doc = cdp.send("DOM.getDocument", {"depth": -1})
            r = cdp.send("DOM.querySelectorAll", {
                "nodeId": doc["root"]["nodeId"], "selector": "input[type=file]"})
            return r.get("nodeIds", [])

        def put(path, node_ids, which=0):
            if len(node_ids) <= which:
                return f"no node index {which} (have {len(node_ids)})"
            try:
                cdp.send("DOM.setFileInputFiles", {"files": [path], "nodeId": node_ids[which]})
                return "ok"
            except Exception as e:
                return f"{type(e).__name__}: {str(e)[:110]}"

        def wait_text(needle, tries=15, step=6000):
            for i in range(tries):
                page.wait_for_timeout(step)
                if needle in page.evaluate(TEXT):
                    return f"{(i+1)*step//1000}s"
            return "TIMEOUT"

        # ---------- reach the wizard ----------
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        page.query_selector(GERBER_FILE_INPUT).set_input_files(ZIP)
        w("quote render: " + wait_text("Detected", 20, 8000))

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
        w("wizard ready: " + wait_text("Bill of Materials", 8, 5000))

        # ---------- [2] BOM ----------
        w("\n=== [2] Bill of Materials ===")
        w("  " + click_tab("Bill of Materials"))
        page.wait_for_timeout(9000)
        ids = file_nodes()
        w(f"  file nodes: {len(ids)}")
        w("  BOM upload -> " + put(BOM, ids, 0))
        w("  match: " + wait_text("Component", 15, 6000))
        page.wait_for_timeout(6000)
        t = page.evaluate(TEXT)
        open("/tmp/asm12_bom.txt", "w").write(t)
        w("  bom text chars: " + str(len(t)))
        for ln in [x for x in t.split("\n") if any(k in x for k in
                   ("Components", "Matched", "Unmatched", "Part", "Price", "Total"))][:14]:
            w("     | " + ln.strip()[:110])

        # ---------- [3] CPL ----------
        w("\n=== [3] Component Placements ===")
        w("  " + click_tab("Component Placements"))
        page.wait_for_timeout(9000)
        ids = file_nodes()
        w(f"  file nodes: {len(ids)}")
        w("  CPL upload -> " + put(CPL, ids, 0))
        w("  placement: " + wait_text("Placement", 12, 6000))
        page.wait_for_timeout(6000)
        open("/tmp/asm12_cpl.txt", "w").write(page.evaluate(TEXT))

        # ---------- [4] Quote ----------
        w("\n=== [4] Quote & Order ===")
        w("  " + click_tab("Quote & Order"))
        page.wait_for_timeout(18000)
        w("  money: " + json.dumps(page.evaluate(MONEY), indent=2))
        t = page.evaluate(TEXT)
        open("/tmp/asm12_quote.txt", "w").write(t)
        w(f"  quote text chars: {len(t)}")
        w("  wrote /tmp/asm12_quote.txt")

    json.dump(net, open("/tmp/asm12_net.json", "w"), indent=1)
    open("/tmp/asm12.log", "w").write("\n".join(log))
    w(f"\ncaptured {len(net)} POSTs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
