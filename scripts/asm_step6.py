#!/usr/bin/env python3
"""Step 6: locate the container holding the BOM/CPL upload, print its ancestor
chain and structure, then attempt to reveal it.

The node exists but is not visible, so we need to know WHAT is collapsed around
it: a tab, an el-collapse-item, or a dialog that is not yet open.
"""
import sys

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")

from jlcpcb_client.session import browser  # noqa: E402
from jlcpcb_client.selectors import GERBER_FILE_INPUT, QUOTE_URL  # noqa: E402

OUT = "/home/c03rad0r/worktrees/balloon-u2-integrate/tracker/hardware/output"
ZIP = f"{OUT}/gerbers_v8h_jlcpcb.zip"
TEXT = "() => (document.body.innerText||'')"

CLICK_ASM = """() => {
    const els = [...document.querySelectorAll('div,li,span')];
    const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                             && /PCB Assembly/i.test(e.innerText||''));
    if (sw) { sw.click(); return 'clicked'; }
    return 'no-switch';
}"""

# ancestor chain + what collapses it
ANCESTRY = """() => {
    const all = [...document.querySelectorAll('*')];
    const node = all.find(e => (e.textContent||'').trim() === 'Upload BOM & CPL'
                               && e.children.length === 0);
    if (!node) return {found:false};
    const chain = [];
    let n = node;
    for (let i=0; i<10 && n; i++) {
        chain.push({tag:n.tagName, cls:(n.className||'').toString().slice(0,90),
                    display:getComputedStyle(n).display,
                    visibility:getComputedStyle(n).visibility,
                    h:n.offsetHeight});
        n = n.parentElement;
    }
    // nearest el-collapse-item and its header
    const item = node.closest('.el-collapse-item');
    const header = item ? item.querySelector('.el-collapse-item__header') : null;
    return {
        found:true,
        chain,
        collapseHeader: header ? (header.innerText||'').slice(0,80) : null,
        collapseItemCls: item ? (item.className||'').toString().slice(0,80) : null,
        itemActive: item ? item.className.toString().includes('is-active') : null,
    };
}"""

# try to expand every collapsed el-collapse-item header
EXPAND_ALL = """() => {
    const hs = [...document.querySelectorAll('.el-collapse-item__header')];
    hs.forEach(h => { if (!h.closest('.el-collapse-item').className.toString().includes('is-active')) h.click(); });
    return 'toggled ' + hs.length + ' headers';
}"""

# click any tab whose label mentions assembly / BOM
CLICK_TAB = """() => {
    const tabs = [...document.querySelectorAll('.el-tabs__item,[role=tab],.el-radio-button')];
    const hit = tabs.find(t => /assembl|bom|part/i.test(t.innerText||''));
    if (hit) { hit.click(); return 'tab: ' + hit.innerText.slice(0,40); }
    return 'no tab; tabs=' + tabs.map(t=>(t.innerText||'').slice(0,18)).join('|').slice(0,120);
}"""

FILES = """() => [...document.querySelectorAll('input[type=file]')].map(e => ({
    id:e.id, name:e.name, cls:(e.className||'').toString().slice(0,30), vis:!!e.offsetParent}))"""


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
        page.wait_for_timeout(9000)
        h = page.evaluate("() => document.body.scrollHeight")
        for y in range(0, min(h, 6000), 600):
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(500)

        a = page.evaluate(ANCESTRY)
        w("\n=== ancestry of 'Upload BOM & CPL' ===")
        w(f"found={a.get('found')}")
        for c in (a.get("chain") or []):
            w("   " + str(c))
        w(f"collapseHeader={a.get('collapseHeader')!r} active={a.get('itemActive')}")

        w("\nexpand all: " + page.evaluate(EXPAND_ALL))
        page.wait_for_timeout(4000)
        w("click tab: " + page.evaluate(CLICK_TAB))
        page.wait_for_timeout(6000)

        d = page.evaluate(FILES)
        w(f"\nfile inputs after expand: {len(d)}")
        for f in d:
            w("   " + str(f))
        w("marker in text: " + str("Upload BOM & CPL" in page.evaluate(TEXT)))

        with open("/tmp/asm6_full.txt", "w") as f:
            f.write(page.evaluate(TEXT))

    with open("/tmp/asm6.log", "w") as f:
        f.write("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
