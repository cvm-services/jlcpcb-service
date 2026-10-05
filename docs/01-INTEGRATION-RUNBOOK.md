# 01 — Integration Runbook: everything required, reproducible

This is the complete record of what was required to take a PCB design and get a JLCPCB
quote, done by hand on an Ubuntu box on 2026-10-05. It is written so a competent
engineer can reproduce it on a clean machine.

Everything below was **observed working**. Anything not observed is marked `UNVERIFIED`.

## 0. Host setup

JLCPCB is a browser-only integration — there is no public ordering API. We need a
**headed** Chrome (headless is detected and behaves differently) on a virtual display,
driven by Playwright over CDP so the session survives between script runs.

```bash
sudo apt-get install -y google-chrome-stable xvfb x11vnc
python3 -m venv ~/venvs/pw
~/venvs/pw/bin/pip install playwright
```

**Do not put the venv in `/tmp`.** `/tmp` is tmpfs; a reboot wiped `~/tmp/pwvenv`
mid-session and every script failed with `No such file or directory`. Use `~/venvs/pw`.

Start the virtual display:

```bash
Xvfb :99 -screen 0 1600x1200x24 -nolisten tcp &
export DISPLAY=:99
```

Launch Chrome as a durable, reconnectable session:

```bash
google-chrome --no-sandbox --disable-dev-shm-usage \
  --user-data-dir="$HOME/.hermes/profiles/manager/state/jlc-browser9" \
  --remote-debugging-port=9222 --remote-allow-origins='*' \
  --window-size=1500,1150 --lang=en-US --disable-gpu &
```

The `--user-data-dir` is the **whole game**: it holds the session cookies. Keep it on
disk, back it up, and reuse it. A fresh profile is unauthenticated and will send you
down a login rabbit hole for nothing.

If a human ever needs to click something, expose the display:

```bash
x11vnc -display :99 -rfbport 5901 -shared -forever -rfbauth ~/.vnc_jlc.pass
```

## 1. Create the account (once per fleet)

Register at `https://passport.jlcpcb.com/#/register`. Form fields: Company, Country,
Username, Email, Password, plus two checkboxes.

### Trap A — the country field is the submit gate, not the captcha

Country is a bespoke `div.country-select`, **not** a native `<select>`. While it is
unset, clicking **Sign Up is a silent no-op** — no network call, no modal. This reads
exactly like "the captcha cannot be clicked" and cost hours of misdiagnosis.

The working interaction: click `div.country-select`, then click the row whose text is the
target country (e.g. `GERMANY`), then verify the widget displays it before submitting.

### Trap B — the verification code is not 6 digits

The code is **6 alphanumeric characters wrapped in asterisks** — e.g. `*Yepflc*`. A
`\b\d{6}\b` poll matches nothing while the code sits in the inbox, and the flow stalls
forever. TTL is 10 minutes; delivery took 60–90 seconds.

### Trap C — mail to a disposable address does work here

A nomail.name address received JLCPCB's mail, including the welcome message that proves
the account exists. Poll the inbox with:

```bash
curl -s "https://nomail.name/api/messages?limit=20" -b ~/.nomail_cookies
```

### Trap D — fill inputs the way the SPA expects

Playwright's `fill()` and `type()` time out on this SPA. Set the value through the native
setter and dispatch the events the framework listens for:

```javascript
// inside page.evaluate
const set = (el, v) => {
  const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
  d.set.call(el, v);
  el.dispatchEvent(new Event('input',  { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  el.dispatchEvent(new Event('blur',   { bubbles: true }));
};
```

## 2. Use the session — there is no login step

**This is the single most important finding.** The register-flow profile is already
authenticated. Confirm it:

```bash
# navigate to https://jlcpcb.com/ and look at the header
```

- authenticated → header renders **`My Account`**
- unauthenticated → header renders `Sign In`

Cookies present when authenticated include `ONEKEYID`, `jlc_session_customer_code`,
`JLCPCB_SESSION_ID`, `XSRF-TOKEN`, and `RT` on both `.jlcpcb.com` and
`.passport.jlcpcb.com`.

### Trap E — `POST /checkLogin` is not a verdict

It returns **HTTP 200 even when logged out**, with body
`{"message":"login.unlogin","code":200}`. Status codes and this endpoint alone cannot
establish auth. Use the header.

### Trap F — the login page's captcha, if you ever must log in

Only relevant when a profile is genuinely unauthenticated:

- A fresh load has only the register key's invisible widget and **no modal**. The login
  key (`6LeinFUp…`) and the "Security Verification" modal are injected **only after the
  first click**, and whether it challenges is nondeterministic.
- **Wait** until `typeof grecaptcha === 'object'` and at least one iframe exists before
  clicking. On a loaded box an early click lands on a half-built page: zero textareas, no
  modal, nothing to solve.
- Use a **real CDP click** (`page.locator(...).click()`). A JS `element.click()` fires no
  POST and no modal — trusted user activation is required to arm the widget.
- The click may **navigate**, killing `Page.evaluate` with "Execution context was
  destroyed". That is a positive signal, not a crash; wrap DOM reads in a retry.
- Once armed there are **two** `g-recaptcha-response` textareas: index 0 holds the
  register key's leftover token (~2400 chars); **index 1 is the login key**. Matching
  "any token longer than 20" yields a false `SOLVED`.
- Google/Apple sign-in buttons do **not** reach an account created with a username and a
  mailbox we control.

## 3. Get the gerbers

From a KiCad project, export a single zip. Required layers: `F_Cu`, `B_Cu`, `In1_Cu`,
`In2_Cu` (for 4-layer), `F_Mask`, `B_Mask`, `F_Silkscreen`, `B_Silkscreen`, `F_Paste`,
`B_Paste`, `Edge_Cuts`, plus `PTH.drl` and `NPTH.drl`.

A working reference exists in the balloon tracker repo:
`tracker/hardware/export_v8i_gerbers.sh`, producing
`gerbers_v8i_jlcpcb.zip` (176,706 bytes for a 4-layer, 45×55 mm board).

## 4. Upload and read the instant PCB quote

Navigate to `https://cart.jlcpcb.com/quote` and set the gerber file input directly —
the input is `input#uploadFile` (class `hide`), so `set_input_files` works without
clicking:

```javascript
// inside the Playwright script
page.locator("input[type=file]").first.set_input_files(ZIP_PATH)
```

JLCPCB parses the archive and renders the quote. Read back:

- detected layer count and dimensions
- PCB price (the "Special Offer" line)
- build-time options
- shipping estimate and weight

Observed for v8i: **4-layer 45×55 mm**, qty 5 → **$4.00**, 24-hour build +$7.60,
**$23.21** DHL Express, 0.29 kg.

## 5. Assembly / SMT — what it requires, and why it stopped

The SMT leg needs **BOM + CPL (placement)** files.

- **CPL** we can generate: KiCad exports `pos_*.csv`. JLCPCB wants
  `Designator, Mid X, Mid Y, Layer, Rotation`.
- **BOM** we can shape: grouped `Comment, Designator, Footprint, Layer, LCSC Part #`.

The blocker is the last column. JLCPCB assembly needs an **LCSC part number per line**,
and a value like `100nF` does not identify one. In the v8i source,
`grep -c -i "lcsc" v8i_krt_gnss.kicad_pcb` returns **0**, and the only populated
properties are `Datasheet`, `Description`, `Reference`.

Three consequences that must be handled in code, not discovered at order time:

1. Exclude `DNP` designators and `0R` jumpers from the assembly BOM.
2. Modules are generally not JLC-assemblable: `ESP32-C3-WROOM-02` and `MAX-M10S` (ublox)
   were expected to be unmatched; `LoRa2021_Gen4` (NiceRF) likewise.
3. Never guess an LCSC number. Return the line as `unmatched` and let the customer
   resolve it — a wrong reel is a scrap board.

**Bare-PCB quoting is fully productisable today. SMT quoting is not, until part data
arrives.**

## 6. Artifacts produced by the manual run

| Path | What it is |
|---|---|
| `state/jlc-signup/jlc_upload_v8i.py` | the working gerber-upload + quote script |
| `state/jlc-signup/jlc_country.py` | `pick_country()` for the register page widget |
| `state/jlc-signup/jlc_login_hold.py` | robust human-handoff login (only if unauthenticated) |
| `state/jlc-signup/jlc_probe_header.py` | decisive auth probe (`My Account` vs `Sign In`) |
| `state/handovers/jlcpcb-account-signup.md` | full session handover |
