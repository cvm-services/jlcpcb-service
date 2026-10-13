# Running PCB quotes without burning tokens

**Purpose.** Answering "what does this board cost at JLCPCB?" used to require an
agent to drive a browser through several rounds of trial and error, which costs
real inference tokens each time. `services/jlc-quote` turns that into a **direct
tool call**: no LLM in the loop, no rediscovery, deterministic output.

## What is shipped

| Tool | Input | Output |
|---|---|---|
| `quote` | a gerber zip (path or base64) | `pcb_price_usd`, `shipping_usd`, `layers`, `dimensions_mm`, `weight_kg`, `qty` |

**Read-only.** It prices; it never adds to a cart and never orders.
**Free.** No payment rail, tier-less. It must not carry a tier tag.

Not implemented: **`quote_pcba`** (assembled boards). The contract is written up
in `jlcpcb-service/docs/PCBA-QUOTE-FINDINGS.md` — building it is a wiring job
now, because the required BOM + CPL artifacts already exist there.

## Run it locally

```bash
git worktree add -B pr/<slug> ~/worktrees/<slug> github/main   # never work in /tmp
cd ~/worktrees/<slug> && bun install --frozen-lockfile         # else tsc is absent
bun test services/jlc-quote
bun run typecheck
```

A fresh worktree has **no `node_modules`** — run `bun install` first or
typecheck simply fails to find `tsc`. That is not a repo defect.

CI runs two jobs, `bun` and `deno`; `bun test` from the repo root discovers
`services/**`, so a new service needs no CI edit.

There is also a live end-to-end check that exercises the real browser path
(`services/jlc-quote/src/verify-live.ts`) — use it when you suspect the upstream
page changed, not on every run.

## Environment the adapter needs (on the host that holds the session)

Each of these was measured the hard way; encode them, do not rediscover them:

- **An X server.** The upstream is a headed browser:
  `setsid Xvfb :99 -screen 0 1400x1100x24 >/tmp/xvfb99.log 2>&1 </dev/null &`
- **`executable_path="/usr/bin/google-chrome"`.** Playwright's bundled Chromium
  is missing on this fleet; without the explicit path it dies with
  *"Executable doesn't exist at .../ms-playwright/chromium-1243/..."*.
- **The authenticated profile** `~/.hermes/profiles/manager/state/jlc-browser9`.
  When it expires the client refuses with *"profile is not authenticated (header
  does not render 'My Account')"*; re-run the login harness in
  `~/.hermes/profiles/manager/state/jlc-signup/`.
- **Input zips outside `/tmp`** (`/tmp` is tmpfs and is cleared on reboot).

## The honesty invariants — the reason this is trustworthy

Each is enforced by a test **and** a counter-test proving the assertion can
actually fail:

1. **An expired/absent session is a VISIBLE refusal**
   (`{refused: true, reason: "session_expired", …}`) — never a fabricated price,
   never `0`, never a silent empty result.
2. **A price the page did not render is never reported.**
3. **Absent data is never emitted as a value** — a missing shipping row is not a
   shipping cost of zero.
4. **The announcement tag set is asserted**, with a counter-test so the
   assertion cannot pass on a typo.
5. **Quantity is bounded honestly.** The service quotes the **page-default
   quantity (5) only** and refuses anything else with `reason:
   "qty_unsupported"`. Automating JLC's quantity widget was attempted and
   **failed** (three measured traps), so the service refuses rather than
   silently presenting a default-qty price as if it were the requested qty. A
   wrong price is worse than a refusal.

### The `$4.00` trap — read this before touching the parser

The quote page renders **"Special Offer"** *and* **"Calculated Price"**, plus
build-time adders, coupons and assembly rows, **all carrying `$` figures**. A
read that took a bare `$` value reported **$4.00** for a board actually priced
**$32.30**. The parser must **anchor on the "Calculated Price" label** — never
"the first `$`" and never "the last `$`". There is a committed fixture
(`fixtures/hub_special_offer_trap.txt`) captured from the real page, so a
regression here fails a test instead of mispricing an order.

## Why this saves tokens

Before: an agent session had to start an X server, find the profile, discover the
missing Chromium, learn the label trap, and iterate — each attempt costing
inference. After: one tool call. The knowledge that used to live in a session
transcript now lives in committed fixtures and tests, which is also why it can be
reused without an agent at all (cron, CI, another service).
