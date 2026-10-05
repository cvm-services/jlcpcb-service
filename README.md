# jlcpcb-service — JLCPCB fabrication/assembly integration as a ContextVM service

**Status: PLAN + DOCS. No service code yet** — feature work awaits operator approval
(PLAN GATE). This repo currently contains the reproducible documentation of the
integration that was done by hand on 2026-10-05, plus the design for wrapping it as a
ContextVM (CVM) service others can call.

## Problem

Given a customer's PCB design (KiCad project or gerber set), produce a **fabrication +
assembly quote** from JLCPCB and, on approval, place the order — without the customer
needing a JLCPCB account, and without a human driving a browser.

## What was proven by hand (2026-10-05)

| Leg | Result | Evidence |
|---|---|---|
| Account creation | works | welcome mail in a nomail inbox |
| Login | works — **session persists in the Chrome profile** | jlcpcb.com header renders "My Account" |
| Gerber upload + instant PCB quote | works | 4-layer 45×55 mm, qty 5 → $4.00 + $23.21 DHL |
| SMT / assembly quote | **blocked on missing part data** | no LCSC/MPN fields in the source design |

Full detail: [`docs/01-INTEGRATION-RUNBOOK.md`](docs/01-INTEGRATION-RUNBOOK.md).

## Client (Phase 1 — DONE)

The quoting library works and reproduces the manual run exactly.

```bash
python3 -m venv ~/venvs/pw && ~/venvs/pw/bin/pip install -e '.[test]'

# is the Chrome profile still authenticated?
JLC_PROFILE=~/.hermes/profiles/manager/state/jlc-browser9 \
  ~/venvs/pw/bin/python -m jlcpcb_client.cli session
# -> session OK

# quote a gerber zip (read-only — never places an order)
DISPLAY=:99 JLC_PROFILE=~/.hermes/profiles/manager/state/jlc-browser9 \
  ~/venvs/pw/bin/python -m jlcpcb_client.cli quote BOARD.zip \
  --snapshot ./snapshots --json
```

Gate evidence — the v8i board, quoted through the library, matching the manual run:

```text
PCB price : $4.00      (manual: $4.00)
Shipping  : $23.21     (manual: $23.21)
Qty       : 5          (manual: 5)
Layers    : 4          (manual: 4)
Size      : 45x55mm    (manual: 45x55mm)
Weight    : 0.29 kg    (manual: 0.29 kg)
```

22 tests pass, no network required for the pure parsers. The parsing tests run
against a **verbatim capture** of a real quote page
(`tests/fixtures/quote_v8i_real.txt`), not a hand-written fixture.

### Three traps the build exposed

1. **The price labels are `Calculated Price` / `Shipping Estimate`.** An earlier
   version looked for `PCB Price` / `PCB Size`, which JLCPCB never renders. The
   tests passed anyway, because the fixture had been hand-written to match the
   parser — a suite agreeing with its own fiction. Fixed by capturing the page.
2. **Price and shipping render *during* upload.** At `Uploading your files....
   74%` the page already shows `Calculated Price` and `Shipping Estimate` but
   not the parsed board. Waiting on price alone yields a quote with
   `layers=None`. The render criterion therefore requires the
   `Detected N layer board of WxHmm` sentence.
3. **`Weight` is ambiguous.** The page contains `Outer Copper Weight` and
   `Inner Copper Weight` *before* the board weight, so a label search returns
   the wrong value. Weight is anchored on the `kg` unit instead.

### Quotes depend on live board options

The same board quoted at `$8.00` / `0.17 kg` in one run and `$4.00` /
`0.29 kg` in another, because the page carries whatever options are currently
selected (surface finish, via covering, build time). A quote is only meaningful
together with the options it was taken under — pinning those as explicit inputs
is part of Phase 3, not something to assume.

## The three honest blockers to productising this

1. **LCSC part numbers do not exist in typical designs.** The v8i KiCad source has
   `LCSC`/`MPN` grep count **0**. An SMT quote needs a part per BOM line. This is not a
   tooling gap — it is missing input data, and guessing is a scrap board.
2. **It is browser automation, not an API.** JLCPCB publishes no public ordering API.
   Everything rides on a stateful headed Chrome with a session cookie. That is fragile
   by construction and needs a real anti-breakage strategy
   ([`docs/03-TOOLCHAIN.md`](docs/03-TOOLCHAIN.md)).
3. **The account boundary is undefined.** Whose JLCPCB account places the order? Ours
   (we are the merchant of record) or the customer's (we are an integration helper)?
   This is a business decision, not a technical one, and it changes the architecture.

## Proposed service shape

MCP tools exposed over Nostr (ContextVM), so a customer's agent can call:

- `jlc_validate_design` — DFM preflight from gerbers; returns layer count, dimensions,
  min trace/space, min drill; no JLCPCB contact, no account needed.
- `jlc_quote_pcb` — upload gerbers, return the instant PCB quote (price, shipping,
  lead time). **Read-only, no commitment.**
- `jlc_quote_assembly` — requires BOM + CPL; returns a per-line part match with
  confidence and an assembly quote. Lines it cannot match are returned as
  `unmatched`, never silently guessed.
- `jlc_place_order` — **payment-gated (CEP-8) and explicitly gated.** Never automatic.

Design detail: [`docs/02-ARCHITECTURE.md`](docs/02-ARCHITECTURE.md).

## The one thing a customer must supply

For the SMT leg only: **an LCSC part per BOM line**. Everything else (gerbers, CPL) we
generate or accept. A design with no part numbers can still get a **bare-PCB quote** —
that leg is fully productisable today.

## Documentation set

| File | Purpose |
|---|---|
| [`docs/01-INTEGRATION-RUNBOOK.md`](docs/01-INTEGRATION-RUNBOOK.md) | Every step, cookie, selector, endpoint and trap required to reproduce the integration by hand |
| [`docs/02-ARCHITECTURE.md`](docs/02-ARCHITECTURE.md) | Pipeline stages, MCP tool contracts, CVM announcement and payment design |
| [`docs/03-TOOLCHAIN.md`](docs/03-TOOLCHAIN.md) | Best tool per stage, with the alternative that was rejected and why |
| [`docs/04-AUTOMATION-PLAN.md`](docs/04-AUTOMATION-PLAN.md) | Phased build plan with observable gates, estimates and risks |
| [`MANIFEST.txt`](MANIFEST.txt) | Path + one-line purpose per file |

## Verified facts this rests on

- `/tmp` is tmpfs: the pip venv was wiped by a reboot. The durable venv is `~/venvs/pw`.
- JLCPCB's register page country field is a bespoke `div.country-select`; unset, "Sign Up"
  is a silent no-op with no network call.
- The verification code format is `*Yepflc*` (6 alphanumerics in asterisks), **not** 6 digits.
- `POST /checkLogin` returns HTTP 200 while logged out (`login.unlogin`). Never judge auth
  from a status code.

## UNVERIFIED

- **Whether JLCPCB permits automated ordering under its ToS.** Not checked. Must be
  settled before any paid service is offered.
- **Whether a quote remains valid across sessions.** Quotes were read in one session only.
- **Whether the Chrome-profile session survives a machine reboot** — the profile is on
  disk so it should, but this was not observed.
- **Assembly pricing for v8i** was never obtained (blocked on part numbers), so the
  assembly cost model is unmeasured.
