#!/usr/bin/env python3
"""Switch the quote page into PCBA mode and report what the assembly flow exposes.

Discovery only: clicks the 'PCB Assembly' mode switch, uploads nothing.
"""
import sys

sys.path.insert(0, "/home/c03rad0r/repos/jlcpcb-service")

from jlcpcb_client.session import browser  # noqa: E402
from jlcpcb_client.selectors import QUOTE_URL  # noqa: E402

CLICK_ASSEMBLY = """() => {
    const els = [...document.querySelectorAll('div,a,li,span')];
    // the mode switch on the quote page
    const sw = els.find(e => (e.className||'').toString().includes('switch-box')
                             && /PCB Assembly/i.test(e.innerText||''));
    if (sw) { sw.click(); return 'clicked switch-box: ' + sw.innerText.slice(0,50).replace(/\\n/g,' '); }
    // fallback: nav menu item
    const li = els.find(e => e.tagName==='LI' && /^PCB Assembly$/i.test((e.innerText||'').trim()));
    if (li) { li.click(); return 'clicked nav LI'; }
    return 'NOT FOUND';
}"""

DUMP = """() => {
    const files = [...document.querySelectorAll('input[type=file]')].map(e => ({
        id: e.id, name: e.name, cls: (e.className||'').slice(0,40), accept: e.accept}));
    const btns = [];
    document.querySelectorAll('button,a,div,span,li').forEach(e => {
        const t = (e.innerText||'').trim();
        if (!t || t.length > 70) return;
        if (/BOM|CPL|pick.?and.?place|assembly|add gerber|next|confirm|upload/i.test(t)) {
            btns.push(t.replace(/\\n/g,' | '));
        }
    });
    return {files, btns: [...new Set(btns)].slice(0,50),
            text: (document.body.innerText||'').slice(0,1800)};
}"""


def main():
    with browser() as page:
        page.goto(QUOTE_URL, wait_until="commit", timeout=90000)
        page.wait_for_timeout(14000)
        print("URL:", page.url)
        print("authed:", "My Account" in page.evaluate("document.body.innerText||''"))
        print("\n--- clicking assembly mode ---")
        print(page.evaluate(CLICK_ASSEMBLY))
        page.wait_for_timeout(9000)
        print("URL after:", page.url)
        d = page.evaluate(DUMP)
        print(f"\n--- file inputs ({len(d['files'])}) ---")
        for f in d["files"]:
            print("   ", f)
        print(f"\n--- candidate controls ({len(d['btns'])}) ---")
        for b in d["btns"]:
            print("   ", b)
        print("\n--- page text ---")
        print(d["text"].replace("\n", " | "))


if __name__ == "__main__":
    sys.exit(main())
