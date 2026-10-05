# 02 — Architecture: the service, the tools, the CVM surface

Design only. Nothing here is implemented; see
[`04-AUTOMATION-PLAN.md`](04-AUTOMATION-PLAN.md) for the build order and
[`03-TOOLCHAIN.md`](03-TOOLCHAIN.md) for the concrete library choices.

## 1. Pipeline

```text
customer design                our service                          JLCPCB
──────────────                 ───────────                          ──────
KiCad project  ──┐
                 ├─► [1] ingest + normalise
gerber zip     ──┘        │
                          ├─► [2] DFM preflight  (no account)
                          │
                          ├─► [3] PCB quote ─────────────────────►  upload gerbers
                          │        ◄─────────────────────────────  price/dims/lead time
                          │
                          ├─► [4] BOM/CPL build
                          │      └─► part resolution ──► unmatched? ──► return to customer
                          │
                          └─► [5] assembly quote ────────────────►  upload BOM + CPL
                                   ◄─────────────────────────────  per-line match + price
                                         │
                                    [6] order  ──────────────────►  place, pay
                                         (payment-gated, explicit)
```

Stages [2]–[4] need **no account and no money**. They are the product. Stage [6] is a
commitment and must never be reachable by a single unlucky tool call.

## 2. Why the design is split this way

Each boundary is a place where something can go wrong in a way the customer must see:

- **[2] preflight** catches a broken export before we spend a session on it. Cheap, local.
- **[3] quote** is read-only. It is safe to expose to anyone and it is the demo.
- **[4] part resolution** is where correctness is won or lost. It must be *explicitly
  allowed to fail* — an unmatched line returned to the customer is a correct result, a
  guessed part number is a defect.
- **[6] order** is irreversible and costs money. Separate process, separate credentials,
  separate gate.

## 3. MCP tool contracts

Names are prefixed `jlc_` so they are unambiguous when a foreign agent sees them in a
tool list.

### `jlc_validate_design`

```json
{
  "gerber_zip_url": "https://…  OR  gerber_zip_b64": "…",
  "layer_hint": 4
}
```

Returns: `{ layers, dimensions_mm, min_trace_mm, min_space_mm, min_drill_mm, warnings[] }`.
No JLCPCB contact. No account. Safe to run at high volume.

### `jlc_quote_pcb`

```json
{
  "gerber_zip_url": "https://…",
  "qty": 5,
  "layers": 4,
  "thickness_mm": 1.6,
  "surface_finish": "HASL",
  "color": "Green",
  "build_hours": 24
}
```

Returns: `{ pcb_price_usd, build_price_usd, shipping_usd, weight_kg, lead_time_days, currency, quote_ref }`.

### `jlc_quote_assembly`

```json
{
  "gerber_zip_url": "https://…",
  "bom_url": "https://…",
  "cpl_url": "https://…",
  "qty": 5
}
```

Returns:

```json
{
  "lines": [
    { "designators": ["C1","C2"], "value": "10uF", "footprint": "C_0603",
      "lcsc": "C19702", "match": "exact", "unit_price_usd": 0.0121, "qty": 10 },
    { "designators": ["U2"], "value": "LoRa2021_Gen4", "footprint": "LoRa2021_Castellated",
      "lcsc": null, "match": "unmatched", "reason": "module not in JLC library" }
  ],
  "assembly_price_usd": 1.94,
  "unmatched_count": 3,
  "quotable": false
}
```

`quotable` is `false` whenever any line is unmatched. The service does not pretend.

### `jlc_place_order`

Requires an explicit `confirm: true`, a previously returned `quote_ref`, and a satisfied
payment. Refuses otherwise. Returns the order number and a status handle.

## 4. ContextVM surface

The service is a normal MCP server fronted by a CVM transport, so **the tool contracts
above are the entire customer interface** — a customer's agent calls them by npub, with
no HTTP endpoint, no signup, and no shared network.

Per the `cvm-service-kit` contract (which is the in-fleet build-side library, currently
spec-stage):

- Publish **CEP-6 announcements**: kind `11316` (server) and `11317` (tools list).
- Tagging: `d` slug (e.g. `jlcpcb-fab`), namespaced `t=cvm:service:pcb-fab`, and `g`
  geohash at **at least two precisions** — multi-letter tags are not relay-filterable and
  `#g` is exact-match, so precision fan-out is required, not optional.
- Message traffic on kind `25910`, gift-wrapped per NIP-59 (CEP-4). Gift wrap is
  mandatory: unwrapped 25910 is public to anyone on the relay.
- **Transport gotcha:** the TypeScript `NostrServerTransport` /
  `ApplesauceRelayPool` silently hangs. Use direct `nostr-tools`, or the Python
  `nostr_sdk` bindings, both verified working.

### Discovery path for a customer

```bash
SERVER_NPUB=npub1qexamplejlcpcbservice
npx cvmi discover                       # browse CEP-6 announcements
npx cvmi call "$SERVER_NPUB" tool:jlc_quote_pcb gerber_zip_url=https://example.com/board.zip
```

## 5. Payment design (CEP-8)

Two distinct money flows; do not conflate them.

1. **JLCPCB's money** — the fab and assembly cost, paid on *our* JLCPCB account (if we
   are merchant of record). This is a cost to the operator.
2. **Our fee** — what the customer pays us for the integration.

Payment surface: `cap` tag advertising per-tool prices, `pmi` advertising
`bitcoin-lightning-bolt11` and `bitcoin-cashu`, and `explicit_gating` on
`jlc_place_order` only. Quote tools stay `transparent` so nobody pays to look.

`UNVERIFIED`: the fee model. Whether we charge a flat fee, a percentage, or pass through
JLCPCB's price with a margin is an operator decision and is not settled here.

## 6. The account-boundary decision (blocking)

This determines the whole architecture and cannot be made by an engineer:

| Model | We hold the JLCPCB account | Consequences |
|---|---|---|
| **A. Merchant of record** | yes | one account to maintain and audit; we carry fraud and payment risk; shipping address is ours; customer never touches JLCPCB |
| **B. Integration helper** | no — customer's account | we handle DFM/BOM/quote; the customer places and pays; no money flows through us; but we need per-customer sessions (fragile, unbounded) |

Recommendation: **A for the first release**, because it is one Chrome profile instead of
N customers' sessions, and it keeps the CVM surface credential-free for the customer.
Model B is the natural upgrade once volume justifies per-tenant session management.

## 7. Fragility and the anti-breakage strategy

Browser automation against an undocumented SPA breaks whenever JLCPCB ships a redesign.
The design mitigations:

- **Selectors live in one file.** No selector literals anywhere else.
- **A canary runs on a schedule** — `jlc_quote_pcb` on a fixed, known gerber, asserting a
  non-zero price. If the canary fails, the service marks itself degraded and the CEP-6
  announcement stops advertising the affected tool. Silence is worse than absence.
- **Every quote is snapshotted** (inputs + HTML + extracted numbers) so a regression can
  be diffed rather than guessed.
- **The session is health-checked, not assumed.** The `My Account` header check runs
  before any tool call that needs auth.
