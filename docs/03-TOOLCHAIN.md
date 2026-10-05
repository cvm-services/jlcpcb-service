# 03 — Toolchain: what to automate this with, and what not to

One recommendation per stage, with the alternative that was considered and why it lost.
Everything recommended here was either used in the manual run or is standard for the job.

## Summary

| Stage | Recommended | Why this one |
|---|---|---|
| Browser session | headed Chrome + Playwright over **CDP**, persistent `--user-data-dir` | the session cookie is the product; it must outlive the script |
| Virtual display | **Xvfb** (+ `x11vnc` for human handoff) | headless triggers different behaviour; a display keeps it ordinary |
| Gerber generation | **KiCad CLI** (`kicad-cli pcb export gerbers` / `… drill`) | official, scriptable, already in use in-repo |
| Gerber/design validation | **`gerbv`** (render) + **`pcbnew`/KiCad DRC JSON** | catches a broken export before a session is spent |
| BOM/CPL shaping | **Python `csv`** | the transforms are trivial; no framework earns its weight |
| Part resolution | **JLCPCB's own upload matching** + a local cache, never a guess | it is authoritative; a local MPN→LCSC map is the fallback |
| Quote extraction | **DOM text parse with regex guards**, snapshotted | the page has no API; the numbers are in the DOM |
| Session state | **Playwright `storage_state`** + the profile dir | two independent restore paths |
| Service transport | **direct `nostr-tools`, or Python `nostr_sdk`** | the TS `NostrServerTransport` silently hangs |
| Announcements | **`cvm-service-kit`** (spec-stage) once implemented | keeps the tagging contract in one place |
| Canary | **a scheduled `jlc_quote_pcb` on a fixed gerber** | the only way to learn the SPA changed |

## Stage detail

### Browser session: why Playwright-over-CDP, not headless

Playwright's usual happy path (`chromium.launch(headless=True)`) loses the session on
every run and is more likely to be fingerprinted. Launching Chrome once with
`--remote-debugging-port` and attaching Playwright to it means:

- the session cookie lives in `--user-data-dir` and survives between scripts;
- a human can attach over VNC when a captcha genuinely requires it;
- one Chrome, many scripts — no repeated logins.

**Rejected:** Selenium. Playwright's file-input handling
(`set_input_files` on a hidden input) and CDP attach are both cleaner, and the manual run
already proved Playwright works against this SPA.

**Rejected:** `undetected-chromedriver` / stealth plugins. The manual run passed
JLCPCB's checks without them; adding anti-detection machinery for a vendor we are
integrating with legitimately is the wrong posture and invites worse failure modes.

### Two things that will bite whoever implements this

1. **`fill()` / `type()` time out on this SPA.** Set the value via the native
   `HTMLInputElement` value setter and dispatch `input`, `change`, `blur`.
2. **A JS `element.click()` is not a click.** It fires no POST and arms no captcha;
   only a real CDP click establishes trusted user activation. This single difference
   made several login attempts look "inert" during the manual run.

### Gerber generation and validation

`kicad-cli` is the only sane choice — it is the official headless exporter and the repo
already has working scripts (`export_v8i_gerbers.sh`). For validation, render the layers
with `gerbv` to catch an empty or inverted layer, and read KiCad's own DRC JSON
(`v8i_krt_gnss_drc.json` in the repo) for clearance/width violations. **The DFM preflight
tool should do this locally** — it is fast, free, and needs no account.

**Rejected:** sending every design to JLCPCB just to learn it is invalid. It burns a
session and pollutes the account with junk uploads.

### Part resolution: the hard one

There is no public JLCPCB parts API worth relying on. Options, best first:

1. **Let JLCPCB match.** Upload the BOM and read back its per-line match report. This is
   authoritative by definition — it is the library that will actually assemble the board.
2. **Cache it.** Persist every successful `value+footprint → LCSC` mapping. Over time this
   becomes a local map covering the common passives, which is most of any BOM.
3. **Ask the customer.** If a line is unmatched, return it. Do not guess.

A useful heuristic for the *default* case: for standard passives (`100nF`, `10uF`, `100k`,
`10k`, `330R` in 0402/0603) any JLCPCB **basic-library** part of the right value and size
is interchangeable, so auto-matching those is safe *if* the chosen part is in the basic
library. For anything else — modules, ICs, connectors — never auto-match.

**Rejected:** scraping an LCSC search per line. Slow, brittle, and it still is not the
library JLCPCB will assemble from.

### Quote extraction

The quote page has no API. Parse the DOM text and guard every extraction with a regex
that must match, then **snapshot the raw text next to the parsed numbers**. When JLCPCB
changes wording, the snapshot is what tells you what changed.

**Rejected:** an LLM reading the page. Non-deterministic, costs tokens per quote, and
returns plausible wrong numbers — the exact failure this service must not have.

### Transport: the one well-known trap

The TypeScript `NostrServerTransport` / `ApplesauceRelayPool` **silently hangs** — it
connects and never completes. Both verified working alternatives are:

- direct `nostr-tools` (subscribe to kind 1059, NIP-44 decrypt, parse JSON-RPC, respond
  gift-wrapped);
- Python `nostr_sdk` bindings (`ClientBuilder().signer(signer).build()`).

Since the rest of this service is Python (Playwright, CSV, KiCad CLI), **Python
`nostr_sdk` is the consistent choice** — it avoids maintaining a second runtime for the
transport alone.

**Rejected:** `@contextvm/sdk` transport, for the hang. **Rejected:** `bun:sqlite`-based
examples — they cannot run under Node and add a runtime for no benefit here.

### Relay selection

Use only verified-working relays and wrap every connection in a timeout:

```text
wss://nostr.mom
wss://relay.primal.net
wss://nos.lol
wss://relay2.contextvm.org
wss://relay.nostr.band
```

`wss://relay.contextvm.org` is unreachable (DNS/TLS timeout) — do not include it. A
server needs only one working relay to function.

## Tooling that is explicitly NOT needed

- **An OCR/vision model.** Every value this service needs is in the DOM as text.
- **A headless-browser farm.** One long-lived headed profile is simpler and matches how
  the account expects to be used.
- **A database server.** BOM, quotes and the part cache are small; SQLite or JSON files
  are sufficient at any plausible volume.
