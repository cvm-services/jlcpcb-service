"""quote_qty.py -- read the REAL JLCPCB price at several quantities.

The shipped client has no quantity control (it reads the page default, 5). This
drives the same authenticated profile and changes the real control.

CONTROL SHAPE (measured on jlcpcb.com/quote, 2026-10-13) -- an Element-UI
component, NOT a <select>:

    <div id="QtyDom">
      <label>PCB Qty ...</label>
      <span class="btn qtySelect btnlg cursor">
        <span>5</span>                       <-- current value
      </span>
      <ul class="qty-select-list list-unstyled w-[524px]">
        <li>5</li><li>10</li>...             <-- the offered quantities
      </ul>
      <button class="el-button">Confirm</button>
    </div>

THREE TRAPS THIS AVOIDS, EACH MEASURED:

1. Clicking a bare `get_by_text("10")` matched the LAYERS option ("10" is a
   layer count: 6/8/10/12/14/16) and sent the price to $268.60 — an impossible
   jump, since doubling quantity cannot multiply the price 8x. The click MUST be
   scoped inside #QtyDom.

2. Playwright's normal `.click()` on the list item fails silently: the
   Element-UI popover puts an overlay above the list, so the click is either
   intercepted or lands on the overlay, and the value never changes while the
   code believes it clicked. Fix: dispatch the click in-page via JS, which
   bypasses actionability/overlay checks.

3. A left-over price read is indistinguishable from a real one. So after each
   change we (a) confirm the widget's own value actually became the requested
   quantity, and (b) require the observed price set to contain more than one
   distinct value. A constant price across different quantities is reported
   SUSPECT, not published.

Sanity gate: total price non-decreasing in quantity, unit price non-increasing,
AND at least two distinct totals observed. Anything else -> SUSPECT, because a
wrong price is worse than no price.

READ-ONLY: uploads and reads prices. Never adds to a cart, never orders.
"""
import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.expanduser("~/repos/jlcpcb-service"))

from jlcpcb_client.quote import _goto, _upload, _wait_for_quote  # noqa: E402
from jlcpcb_client.selectors import QUOTE_URL  # noqa: E402
from jlcpcb_client.session import assert_session, browser  # noqa: E402

PRICE_RE = re.compile(r"Calculated Price\s*\$?([0-9][0-9,]*\.[0-9]{2})", re.S)
SHIP_RE = re.compile(r"Shipping Estimate\s*\$?([0-9][0-9,]*\.[0-9]{2})", re.S)
DETECT_RE = re.compile(
    r"Detected\s+(\d+)\s+layer\s+board\s+of\s+([0-9.]+)\s*x\s*([0-9.]+)\s*mm"
)

CURRENT_QTY_JS = (
    "document.querySelector('#QtyDom span.qtySelect')?.innerText.trim()"
)


def body(page):
    return page.evaluate("document.body.innerText || ''")


def board_price(text):
    """Value immediately after the 'Calculated Price' label, else None."""
    m = None
    for m in PRICE_RE.finditer(text):
        pass
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def qty_options(page):
    return page.evaluate(
        """(() => {
             const l = document.querySelector('#QtyDom ul.qty-select-list');
             if (!l) return [];
             return Array.from(l.querySelectorAll('li'))
               .map(li => li.innerText.trim()).filter(Boolean);
           })()"""
    )


def set_qty(page, q):
    """Select quantity q inside #QtyDom. True only if the widget confirms it."""
    try:
        page.locator("#QtyDom span.qtySelect").first.click(timeout=8000)
    except Exception:
        pass
    time.sleep(1.2)

    # Element-UI TELEPORTS the popover list OUT of #QtyDom when it opens
    # (measured: after the click, `#QtyDom ul.qty-select-list` no longer exists).
    # So search document-wide and prefer a VISIBLE list.
    clicked = page.evaluate(
        """(q) => {
             let lists = Array.from(document.querySelectorAll('ul.qty-select-list'));
             if (!lists.length) return false;
             const vis = lists.filter(l => l.offsetParent !== null);
             const l = vis.length ? vis[0] : lists[lists.length - 1];
             for (const li of l.querySelectorAll('li')) {
               if (li.innerText.trim() === String(q)) { li.click(); return true; }
             }
             return false;
           }""",
        q,
    )
    if not clicked:
        page.keyboard.press("Escape")
        return False

    time.sleep(1.2)
    # The Confirm button starts DISABLED and enables only after a selection,
    # so poll for an enabled one rather than clicking immediately.
    for _ in range(8):
        done = page.evaluate(
            """(() => {
                 const c = Array.from(document.querySelectorAll('button.el-button'))
                   .find(b => b.innerText.trim() === 'Confirm' && !b.disabled);
                 if (c) { c.click(); return true; }
                 return false;
               })()"""
        )
        if done:
            break
        time.sleep(0.7)

    # wait for the widget to show the new value
    for _ in range(12):
        time.sleep(1.0)
        cur = page.evaluate(CURRENT_QTY_JS)
        if str(cur) == str(q):
            time.sleep(3.0)          # let the price settle
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("--qtys", default="5,10,20,50")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    qtys = [int(x) for x in args.qtys.split(",")]
    rows, ship, dims = [], None, ""

    with browser(profile=None, headless=False) as page:
        assert_session(page)
        _goto(page, QUOTE_URL, settle=18.0)
        _upload(page, os.path.abspath(args.zip))
        text = _wait_for_quote(page)

        m = DETECT_RE.search(text)
        if m:
            dims = f"{m.group(2)}x{m.group(3)}mm"
            print(f"board: {m.group(1)}-layer {dims}")
        ms = SHIP_RE.search(text)
        if ms:
            ship = float(ms.group(1).replace(",", ""))
            print(f"shipping (once per order): ${ship:.2f}")
        print(f"quantities offered: {qty_options(page)[:12]} ...")
        print()

        for q in qtys:
            ok = set_qty(page, q)
            p = board_price(body(page))
            rows.append((q, p, ok))
            unit = f"  unit ${p / q:.2f}" if p else ""
            flag = "" if ok else "   <-- WIDGET DID NOT CONFIRM"
            print(f"  qty {q:>5}: pcb ${p if p is not None else 'READ-FAILED'}"
                  f"{unit}{flag}")

    # ---- sanity gate ----
    confirmed = [(q, p) for q, p, ok in rows if ok and p is not None]
    suspect = []
    if len({p for _, p in confirmed}) < 2:
        suspect.append("every confirmed quantity returned the SAME price — "
                       "the control almost certainly did not take effect")
    for (q1, p1), (q2, p2) in zip(confirmed, confirmed[1:]):
        if q2 > q1 and p2 < p1:
            suspect.append(f"total DECREASED {q1}->{q2} (${p1}->${p2})")
        if q2 > q1 and (p2 / q2) > (p1 / q1):
            suspect.append(f"unit price ROSE {q1}->{q2} "
                           f"(${p1/q1:.2f}->${p2/q2:.2f}/board)")

    print()
    if suspect:
        print("!! SUSPECT — do NOT use these numbers:")
        for s in suspect:
            print(f"   - {s}")
    else:
        print("sanity: OK (>=2 distinct totals, total non-decreasing, "
              "unit non-increasing)")

    lines = ["| qty | PCB price | unit price | shipping (once) |",
             "|---|---|---|---|"]
    for q, p, ok in rows:
        if p is None:
            lines.append(f"| {q} | read failed | - | - |")
        elif not ok:
            lines.append(f"| {q} | ${p:.2f} (unconfirmed) | - | - |")
        else:
            lines.append(f"| {q} | ${p:.2f} | ${p/q:.2f} | ${ship:.2f} |")
    table = "\n".join(lines)
    print()
    print(table)
    if args.out:
        with open(args.out, "w") as f:
            f.write(f"# JLCPCB quote — {os.path.basename(args.zip)} ({dims})\n\n")
            if suspect:
                f.write("> **SUSPECT** — sanity gate failed:\n")
                for s in suspect:
                    f.write(f"> - {s}\n")
                f.write("\n")
            f.write(table + "\n")
        print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
