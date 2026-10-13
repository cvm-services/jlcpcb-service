# JLCPCB PCBA (assembled board) — findings, and exactly where the automation stands

**Date:** 2026-10-14
**Scope:** hub v9 and wing v9 (balloon-fresh)
**Related:** `JLCPCB-QUOTE-FINDINGS.md` (fabrication-only quotes), `README.md`

PCBA ≠ fab. A fabrication quote needs **gerbers only**. A PCBA (assembled)
quote needs three artifacts per board:

| Artifact | Hub | Wing |
|---|---|---|
| Gerbers | ✅ `docs/fab/hub-v9/` | ✅ `docs/fab/wing-v9/` |
| Centroid / CPL | ✅ `hub_v9_pos.csv` (39 rows) | ✅ `pos_wing_v9.csv` |
| BOM with **LCSC C-numbers** | ✅ `hub_v9_bom_pcba.csv` | n/a — see below |

## Headline: the wing has no meaningful PCBA

The wing is 6 solar cells + a connector. The cells are **not in LCSC's catalog**
(they are 52×19 mm monocrystalline cells, a commodity part outside PCBA
sourcing), and the remaining parts are through-hole. After excluding
non-assemblable parts there is nothing to place — **the wing is a hand-tabbed
board by design**. Do not ask JLC to assemble it.

The hub is the real PCBA candidate (QFN-24, 0402 passives, castellated module).

## Hub BOM — every part mapped to a live-verified LCSC part

`docs/fab/hub-v9/hub_v9_bom_pcba.csv`, 16 lines covering all SMT parts. Full
provenance per line (search term, rank, stock, unit price) is in
`hub_v9_bom_mapping_report.md`.

| Ref(s) | Comment | LCSC | Unit $ | Notes |
|---|---|---|---|---|
| U1 | ESP32-S3-WROOM-1U-N8R8 | C2980300 | 5.76 | exact N8R8 variant confirmed |
| U4 | SX1280IMLTRT | C125969 | 3.28 | |
| U5 | MAX-M10S-00B | C4153167 | 10.84 | `-00B-01` (C24834155) rejected: stock 157 vs 1157 |
| U6 | MS561101BA03-50 | C15639 | 6.73 | |
| U7 | TPS7A0233DBVR | C5142805 | 0.59 | |
| ANT1–4 | U.FL | C434808 | 0.36 | **substitution** — see below |
| D_BP*, D_HUB* | SS24 | C50645 | 0.026 | mapping-report choice; page proposed C78573 |
| D1 | BAT54W | C699107 | 0.032 | **substitution** — see below |
| C4/C_BULK/C_HF/C_MON | 10uF/100uF/100nF/10nF | C15525/C15008/C1525/C15195 | 0.005–0.13 | |
| R_BAL*/R_DIV*/R_F1/R_MON* | 10k/1M/100R/4.7M | C25744/C26083/C25076/C11906 | 0.001–0.003 | 1% used for divider duty (5% rejected) |

### Two substitutions, both checked

- **D1 BAT54 → BAT54W (C699107).** The plain `BAT54` is **SOT-23 only** at LCSC;
  the board footprint is `D_SOD-123`. `BAT54W` is the SOD-123 package part.
  Electrically equivalent for this use.
- **U.FL: Molex 73412-0110 → Hirose U.FL-R-SMT(10) (C434808).** Searches for
  `73412-0110`, `MCRF` and `Molex U.FL` return **0 hits** — the Molex part is
  **not in JLC's catalog**. The Hirose part is the standard U.FL SMD mate.
- **Correction to a bad hint:** the number `C2906862` was suggested for U.FL. It
  is **not** a connector — it is a 10 Ω 0402 resistor (verified by code-search)
  and was rejected. Do not reuse it.

### Explicitly NOT assembled (DNP)

Supercaps (2× AVX 3.3 F, through-hole), the LoRa2021 / LoRa2021F33 modules (not
in the LCSC catalog), fiducials, mounting holes, the solder jumper, and the
wing-interface tabs — none carry a part.

## Cost facts learned from the live flow

- **The ESP32-S3-WROOM-1U forces the STANDARD PCBA tier**, not the cheaper
  "Economic" service. JLC surfaces this as *"Standard PCBA Only"* on the U1 row.
  Any assembled-hub number is therefore a Standard-PCBA number.
- Parts cost is dominated by the four ICs: ESP32-S3 5.76 + MAX-M10S 10.84 +
  MS5611 6.73 + SX1280 3.28 ≈ **$26.61 per board in parts alone** at unit-1
  pricing, before any assembly fee. Expect meaningful quantity breaks above that.

## Where the automation stands — resume EXACTLY here

The browser flow was scripted and driven successfully through these steps:

1. `https://jlcpcb.com/quote` → upload gerber zip (fab price renders: hub $32.30)
2. Switch the service to **PCB Assembly**
3. Upload **BOM + CPL** — page reported **16 parts detected, 16 confirmed**
4. A **"Do not place this part"** dialog appears for U1 (the Standard-PCBA
   requirement) — it was dismissed
5. Each BOM row needs its **checkbox ticked**; SS24 (`D_BP1,D_BP2,…`) was the
   last row reached and it produced the warning *"multiple types of parts, one
   tick"*

**It stopped one step short of the price.** The remaining steps are:
reconcile the SS24 choice (mapping report says **C50645**, the page proposed
**C78573** at $1.42 — pick the cheaper/stocked one deliberately, do not let the
default win), finish ticking, dismiss any remaining "do not place" dialogs, then
read the **Component Placements** total.

All intermediate page states and screenshots were preserved on cobrador in
`~/jlc-pcba-work/` (`after_next_body.txt`, `hub_bom_added_body.txt`,
`hub_cpl_added_body.txt`, `hub_after_process_body.txt`, `hub_after_dnp_body.txt`,
`after_tick_body.txt`, plus matching `.png`). Resume from those rather than
re-driving the upload.

### The elemental trap, repeated

Everything in `JLCPCB-QUOTE-FINDINGS.md` still applies: the page renders
"Special Offer" **and** "Calculated Price" plus adders/coupons/assembly rows, all
carrying `$` figures. Reading a bare `$` reported **$4.00** for a board actually
priced **$32.30**. **Always anchor on the label.** This is the single most
expensive mistake available on this page.

## Making this cheap next time

- `services/jlc-quote` (in `cvm-services/cvm-service-kit`) already exposes the
  **fabrication** quote as a CVM tool with the honesty invariants tested
  (expired session → visible refusal, never a fabricated price, qty limited to
  the page default with an explicit `qty_unsupported` refusal).
- The **PCBA** tool (`quote_pcba`: BOM + CPL + gerbers → price) is **not
  implemented**. Its contract is the same as the fab tool's; the honesty
  requirements are identical, plus one: **DNP and unavailable parts must be
  reported explicitly per line**, never silently dropped from the total.
- The BOM + CPL artifacts committed here are exactly the inputs that tool needs,
  so implementing it is now a wiring job, not a research job.
