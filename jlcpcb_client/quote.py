"""Upload a gerber zip and read back JLCPCB's instant PCB quote."""
import json
import os
import time
from typing import Optional

from .errors import QuoteParseError
from .parse import Quote, parse_quote_text
from .selectors import (
    ADD_GERBER_TEXT,
    GERBER_FILE_INPUT,
    GERBER_FILE_INPUT_FALLBACKS,
    QUOTE_URL,
    RENDER_MARKERS,
)
from .session import _goto, assert_session, browser

# Poll cadence for the quote to render after upload. JLCPCB parses the archive
# server-side; on a loaded box this took tens of seconds in the manual run.
POLL_ATTEMPTS = 30
POLL_INTERVAL_S = 6.0


def quote_gerber(
    zip_path: str,
    profile: Optional[str] = None,
    snapshot_dir: Optional[str] = None,
    headless: Optional[bool] = None,
) -> Quote:
    """Return JLCPCB's instant PCB quote for a gerber zip.

    Read-only: this uploads and reads the quote. It never places an order.
    """
    zip_path = os.path.abspath(zip_path)
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(zip_path)

    with browser(profile=profile, headless=headless) as page:
        assert_session(page)

        _goto(page, QUOTE_URL, settle=18.0)
        if "cart.jlcpcb.com" not in page.url:
            raise QuoteParseError(f"did not reach the quote page (at {page.url})")

        _upload(page, zip_path)

        text = _wait_for_quote(page)
        if snapshot_dir:
            _snapshot(snapshot_dir, zip_path, text, page)

        return parse_quote_text(text)


def _upload(page, zip_path: str) -> None:
    """Set the hidden gerber file input, falling back to clicking first."""
    selectors = (GERBER_FILE_INPUT,) + tuple(GERBER_FILE_INPUT_FALLBACKS)
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count():
                el.set_input_files(zip_path, timeout=20000)
                return
        except Exception:
            continue

    # Nothing accepted the file directly — open the picker UI and retry.
    try:
        page.locator(f"text={ADD_GERBER_TEXT}").first.click(timeout=10000)
        time.sleep(3)
        page.locator(GERBER_FILE_INPUT_FALLBACKS[0]).first.set_input_files(
            zip_path, timeout=20000
        )
        return
    except Exception as e:
        raise QuoteParseError(f"could not attach gerber file: {str(e)[:120]}") from e


def _wait_for_quote(page) -> str:
    """Poll until the quote renders, then return the page text.

    Rendered means the price and shipping lines are present — not that any '$'
    appears, because the page shows build-time adders, coupons and a special
    offer before the board itself has been priced.
    """
    last = ""
    for _ in range(POLL_ATTEMPTS):
        time.sleep(POLL_INTERVAL_S)
        last = _body_text(page)
        if all(m in last for m in RENDER_MARKERS):
            return last
    raise QuoteParseError(
        "quote never rendered (missing "
        f"{' and '.join(RENDER_MARKERS)} after "
        f"{POLL_ATTEMPTS * POLL_INTERVAL_S:.0f}s)"
    )


def _body_text(page) -> str:
    try:
        return page.evaluate("document.body.innerText || ''")
    except Exception:
        return ""


def _snapshot(snapshot_dir: str, zip_path: str, text: str, page) -> None:
    """Persist raw text + a screenshot next to the parsed numbers.

    When JLCPCB changes wording, the snapshot is what shows what changed — and
    it is the only artifact that makes a regression diffable.
    """
    os.makedirs(snapshot_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.join(snapshot_dir, f"quote-{stamp}")
    with open(base + ".txt", "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(base + ".json", "w", encoding="utf-8") as fh:
        json.dump({"zip": zip_path, "at": stamp}, fh, indent=2)
    try:
        page.screenshot(path=base + ".png", full_page=False)
    except Exception:
        pass
