# 04 — Automation Plan

**Status: awaits operator approval (PLAN GATE).** No phase below starts until the operator
picks a scope. Phase 0 is documentation and is already done. Phases with a `[DECISION]`
marker cannot start before that decision is made.

## Shape of the recommendation

Ship the **bare-PCB quote leg as the product** and treat SMT as a follow-on. Reasons:

1. The PCB leg is fully working today, end to end, with no missing inputs.
2. SMT is blocked on customer-supplied part data — a data problem we cannot engineer away.
3. A narrow service that always works beats a broad one that fails on the common case.

## Phases

### Phase 0 — Documentation (DONE)

Deliverable: this doc set.
Gate: every command in `01-INTEGRATION-RUNBOOK.md` was taken from the working manual run;
all traps are recorded. **Passed.**

### Phase 1 — Extract a reusable, tested client library (DONE)

Deliverable: `jlcpcb_client/` — session health check, gerber upload, quote
extraction, BOM/CPL transforms. Selectors confined to `selectors.py`.

Gate (**passed**, evidence in `README.md`): `jlcpcb-client quote` on the v8i zip
returns **$4.00 PCB / $23.21 DHL / 4 layers / 45x55mm / 0.29 kg**, matching the
manual run field for field. 22 unit tests pass with no network.

The gate did its job — it failed twice first, and both failures were real:

- The parser read labels (`PCB Price`/`PCB Size`) that do not exist, and passed
  because the fixture had been hand-written to match. Replaced with a verbatim
  capture; the parser now reads `Calculated Price`/`Shipping Estimate`.
- Price renders mid-upload, so waiting on it alone produced `layers=None`. The
  render criterion now requires the `Detected … board` sentence.

Estimate: 1–2 days. Actual: ~1 session. Cost: 3 JLCPCB uploads.

### Phase 2 — DFM preflight (no account, no session)

Deliverable: `jlc_validate_design` — layers, dimensions, min trace/space/drill, warnings,
from a gerber zip. Fully local.

Gate: on the v8i zip it reports 4 layers and 45×55 mm, matching JLCPCB's own parse, with
no JLCPCB contact. Runs on a machine with no Chrome and no session.

Estimate: 1 day.

### Phase 3 — MCP server + CVM transport

Deliverable: the four tools from `02-ARCHITECTURE.md` exposed over CVM (direct
`nostr_sdk` transport, CEP-6 announcements, gift-wrapped kind 25910).

Gate: from a *different machine*, `cvmi discover` finds the service and
`cvmi call npub1… tool:jlc_quote_pcb gerber_zip_url=…` returns a real quote. Pasted
command output or it did not happen.

Estimate: 2–3 days (the transport is the risky part; the hang is known and avoided).

### Phase 4 — Reliability: canary + session health

Deliverable: scheduled canary calling `jlc_quote_pcb` on a fixed gerber; session health
check before any authenticated call; degraded state suppresses the affected tool's
announcement; quote snapshots retained.

Gate: deliberately break a selector in a scratch copy → canary fails and the tool stops
being advertised. Inject an expired session → the service reports degraded instead of
returning a wrong price.

Estimate: 1–2 days.

### Phase 5 — Assembly quote `[DECISION: account model]`

Cannot start before the merchant-of-record decision in `02-ARCHITECTURE.md §6`.

Deliverable: `jlc_quote_assembly` with explicit unmatched handling and
`quotable: false`.

Gate: on a v8i BOM, returns ≥1 correctly matched passive with a real LCSC number, and
returns `unmatched` (not a guess) for `ESP32-C3-WROOM-02`, `MAX-M10S` and
`LoRa2021_Gen4`. `quotable: false` when any line is unmatched.

Estimate: 3–5 days, dominated by part resolution.

### Phase 6 — Ordering `[DECISION: payments + ToS]`

Gate, all of which must hold:
- **JLCPCB ToS explicitly permits automated ordering** — currently `UNVERIFIED`.
  This is a hard stop, not a checkbox.
- `explicit_gating` payment via CEP-8 works end to end on a real order.
- A test order is placed, received, and reconciled without human browser work.

Estimate: unbounded until the ToS question is settled. **Do not schedule.**

## Phase summary

| Phase | Deliverable | Estimate | Gate | Money |
|---|---|---|---|---|
| 0 | doc set | done | commands from the real run | none |
| 1 | client library | 1–2 d | reproduces v8i quote exactly | 1 upload |
| 2 | DFM preflight | 1 d | 4 layers / 45×55 mm locally | none |
| 3 | MCP + CVM | 2–3 d | remote `cvmi call` returns a quote | 1 upload |
| 4 | canary + health | 1–2 d | broken selector → degraded | none |
| 5 | assembly quote | 3–5 d | real LCSC match + honest unmatched | uploads |
| 6 | ordering | unbounded | ToS cleared + paid test order | real order |

Productisable after **Phase 4**: a bare-PCB quoting service, remotely callable, that
degrades honestly instead of lying.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| JLCPCB redesigns the SPA | quotes stop | selectors in one file; canary catches it in one tick; snapshots show the diff |
| Session cookie expires | all authenticated tools fail | health check before use; human handoff path already built (VNC + `jlc_login_hold.py`) |
| Account flagged or banned | service dies | **UNVERIFIED** — check ToS before scaling; keep a human fallback |
| Customer designs carry no part numbers | SMT unquotable | return `unmatched`; sell the PCB leg; cache mappings over time |
| Wrong auto-matched part | scrap board | auto-match **only** JLCPCB basic-library passives; never for modules/ICs |
| Relay silently drops events | service looks dead | verified relay list, connection timeouts, broad filter + client-side p-tag match |

## What the operator must decide

1. **Scope to approve**: Phase 1–4 (recommended) or wider.
2. **Account model**: merchant of record (recommended) vs customer's account.
3. **Fee model**: flat, percentage, or pass-through + margin.
4. **ToS**: who verifies that automated ordering is permitted, and it must be verified
   before Phase 6.

## Open questions worth settling cheaply

- Does a quote survive across sessions, or is `quote_ref` only valid live? (One test.)
- Does the Chrome session survive a machine reboot? (One reboot, or read the profile.)
- What does JLCPCB return for a BOM with no LCSC column at all — an error, or a list of
  near-matches? (One upload, and it decides how much auto-matching is possible.)
