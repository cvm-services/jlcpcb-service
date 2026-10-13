# JLCPCB quote — measured results and the automation traps

**Date:** 2026-10-13
**Boards:** hub v9, wing v9 (balloon-fresh)
**Tool:** `jlcpcb_client` (this repo) — read-only, never orders

## Verified quotes (read off the live page, qty 5)

| Board | Layers | Dimensions | PCB price | Shipping | Weight |
|---|---|---|---|---|---|
| **hub v9** | 4 | **115×103 mm** | **$32.30** | $23.36 DHL | 0.33 kg |
| **wing v9** | 2 | **25×184 mm** | **$6.40** | $23.36 DHL | 0.20 kg |

Reproduce:

```bash
cd ~/repos/jlcpcb-service
DISPLAY=:99 JLC_PROFILE=~/.hermes/profiles/manager/state/jlc-browser9 \
  ~/venvs/pw/bin/python -m jlcpcb_client.cli quote ~/jlc-quote-inputs/hub_v9.zip \
  --snapshot ./snapshots --json
```

### The `$4.00` figure is NOT the board price

The quote page renders **"Special Offer"** as well as **"Calculated Price"**, plus
build-time adders, coupons and assembly rows — all carrying dollar figures. An
earlier read that took a `$` value without anchoring on the **"Calculated Price"**
label reported **$4.00** for a board that is actually **$32.30**. `selectors.py`
already warns about this (`LABEL_PRICE_FALLBACKS = ("Special Offer",)`); the
regression is in *how the value is extracted*, not in the label choice. When
reading this page, anchor on the label — never on "the first $" or "the last $".

### Dimensions corroborate the gerber

JLCPCB independently detects **115×103 mm** for the hub. That agrees with
`pcbnew` (all Edge.Cuts geometry) and with the exported `.gm1` gerber, all three
reporting **115 mm** on the Y axis. The 103×103 body alone is *not* the board:
the wing-interface tabs (`J_W1`…`J_W4`) carry their outline as `PCB_SHAPE`
graphics inside the footprints and protrude ±6 mm, so a board-level-only
Edge.Cuts scan under-reports.

## Environment requirements (each cost real time)

- **X server required** — the quote drives headed Chrome. Start one:
  `setsid Xvfb :99 -screen 0 1400x1100x24 >/tmp/xvfb99.log 2>&1 </dev/null &`
- **Playwright's bundled Chromium is MISSING** on this box. Launch with
  `executable_path="/usr/bin/google-chrome"`, or it fails with
  *"Executable doesn't exist at .../ms-playwright/chromium-1243/..."*.
- Use **`~/venvs/pw/bin/python`** — it has Playwright. An older README references
  `/tmp/pwvenv`, which no longer exists (`/tmp` is tmpfs and is cleared).
- The session profile is
  `~/.hermes/profiles/manager/state/jlc-browser9`. When it expires the client
  refuses with *"profile is not authenticated (header does not render 'My
  Account')"*; re-run the login harness in
  `~/.hermes/profiles/manager/state/jlc-signup/`.
- Keep input zips **outside /tmp** (`~/jlc-quote-inputs/`), or a reboot loses them.

## Automating the QUANTITY control — blocked, and here is exactly where

The shipped client has no quantity parameter: it reads whatever quantity the page
defaults to (5). Reading the price at other quantities is the useful thing (see
the cost note below), but automating the control did not succeed in this session.
Recording the diagnosis so the next attempt starts from the right place.

**The control is Element-UI, not a `<select>`:**

```html
<div id="QtyDom" class="main-btn-group clearfix">
  <label>PCB Qty ...</label>
  <span class="btn qtySelect btnlg cursor"><span>5</span><img ...></span>
  <ul class="qty-select-list list-unstyled w-[524px]"> <li>5</li> ... </ul>
  <button class="el-button ... is-disabled"><span>Confirm</span></button>
</div>
```

Offered ladder: `5,10,15,20,25,30,50,75,100,125,150,200,...` (65 entries).

**Three traps, each measured:**

1. **Do not click text outside `#QtyDom`.** A bare `get_by_text("10")` matched the
   *Layers* dropdown option ("10" is a valid layer count: 6/8/10/12/14/16) and
   produced **$268.60** for the hub — an impossible jump, since doubling the
   quantity cannot multiply the price 8×.
2. **The popover list is TELEPORTED out of `#QtyDom` when it opens.** After
   clicking `span.qtySelect`, `document.querySelector('#QtyDom ul.qty-select-list')`
   returns **null** — observe that `item_count` goes from 65 to null. Any scoped
   selector breaks; search document-wide and prefer the *visible* list.
3. **`Confirm` starts disabled** (`class="... is-disabled"`) and enables only
   after a selection. Clicking it immediately does nothing; poll for an enabled
   one. Whether it is required at all, or the value applies on `li` click, was not
   settled.

**Status:** `scope/quote_qty.py` implements all of the above and reports
`confirmed=False` for every quantity, so it publishes **SUSPECT** rather than a
number. The read path is therefore *not* trusted for non-default quantities yet.

**Next step:** since the operator places the order manually, the practical path is
to read the ladder in the browser. To finish the automation, instrument what
`li.click()` actually triggers (a framework handler may need a real mouse event:
try `page.mouse` at the element's bounding box, or `dispatchEvent` with bubbling
`MouseEvent`s), and confirm the widget's own value changes before reading price.

## Cost structure — the reason quantity matters

At qty 5, shipping ($23.36) is **42%** of the hub's delivered cost and **78%** of
the wing's. Setup is per-design and shipping is per-parcel, so marginal boards are
cheap while a *second* order pays the full shipping again.

Practical consequence: **buy up in one order.** The hub is the expensive,
high-attrition board (4-layer, 137 vias, via-in-pad special process); the wing is
cheap with high mechanical attrition (cracked solar cells, castellated tab
fracture). Ratio is 4 wings per hub, so 10 hubs + 40–50 wings keeps the build
ratio intact with genuine spares.
