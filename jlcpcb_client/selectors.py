"""Every DOM selector and page string the client depends on.

Keeping these here — and nowhere else — is deliberate. JLCPCB ships redesigns
without notice; when the SPA changes, this is the only file that should need
editing, and the canary (docs/04-AUTOMATION-PLAN.md §Phase 4) tells us when.

**Every constant below was read off a real captured page** (see
`tests/fixtures/quote_v8i_real.txt`). None of them are guesses: an earlier
version of this file invented `PCB Price` / `PCB Size` labels that JLCPCB does
not render, and the tests passed anyway because the fixture contained the same
invention. Do not add a constant here without a capture behind it.

Nothing in this module imports Playwright.
"""

# --- URLs -----------------------------------------------------------------
QUOTE_URL = "https://cart.jlcpcb.com/quote"
HOME_URL = "https://jlcpcb.com/"
REGISTER_URL = "https://passport.jlcpcb.com/#/register"

# --- auth detection -------------------------------------------------------
# POST /checkLogin returns HTTP 200 with body login.unlogin while logged out,
# so a status code is never a verdict. The rendered header is the verdict.
AUTH_MARKER = "My Account"
LOGOUT_MARKER = "Sign In"

# --- gerber upload --------------------------------------------------------
GERBER_FILE_INPUT = "input#uploadFile"
GERBER_FILE_INPUT_FALLBACKS = (
    "input[type=file]",
    "input[accept*='zip']",
    "input[accept*='rar']",
)
ADD_GERBER_TEXT = "Add gerber file"

# --- register page (only needed to bootstrap a session) -------------------
COUNTRY_WIDGET = "div.country-select"
USERNAME_INPUT = 'input[placeholder="Username"]'
EMAIL_INPUT = 'input[placeholder="Email"]'

# --- quote page -----------------------------------------------------------
# The price line is labelled "Calculated Price" (verified). "Special Offer"
# carries the same figure and is kept as a fallback for a different order mode.
LABEL_PRICE = "Calculated Price"
LABEL_PRICE_FALLBACKS = ("Special Offer",)
LABEL_SHIPPING = "Shipping Estimate"
LABEL_QTY = "PCB Qty"

# The board summary is a sentence, not a field: "Detected 4 layer board of
# 45x55mm(1.772x2.165 inches)." Layers and dimensions are parsed from it.
DETECTED_RE = r"Detected\s+(\d+)\s+layer\s+board\s+of\s+([0-9.]+)\s*x\s*([0-9.]+)\s*mm"

# Weight is anchored on the kg unit because the page also contains the strings
# "Outer Copper Weight" and "Inner Copper Weight" *earlier in the document* —
# a label search for "Weight" returns the copper weight, not the board's.
WEIGHT_RE = r"([0-9]+(?:\.[0-9]+)?)\s*kg"

# A quote is considered rendered when all of these are present. The "Detected"
# sentence is the load-bearing one: price and shipping lines render *while the
# archive is still uploading* ("Uploading your files.... 74%"), so a criterion
# built on them alone fires early and yields a quote with no layers/dimensions.
RENDER_MARKERS = ("Detected", "Calculated Price", "Shipping Estimate")
