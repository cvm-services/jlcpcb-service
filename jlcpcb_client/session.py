"""Session handling: launch the persistent profile and prove it is authenticated.

The whole client rests on one Chrome profile that already holds a JLCPCB
session (docs/01-INTEGRATION-RUNBOOK.md §2). There is no login step in the
happy path, and there must never be a silent fallback that pretends otherwise.
"""
import os
from contextlib import contextmanager
from typing import Optional

from .errors import SessionError
from .selectors import AUTH_MARKER, HOME_URL, QUOTE_URL

DEFAULT_PROFILE = os.path.expanduser(
    "~/.hermes/profiles/manager/state/jlc-browser9"
)
CHROME = os.environ.get("JLC_CHROME", "/usr/bin/google-chrome")

LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--window-size=1400,1100",
    "--disable-gpu",
]


def profile_dir(override: Optional[str] = None) -> str:
    return os.path.expanduser(override or os.environ.get("JLC_PROFILE") or DEFAULT_PROFILE)


@contextmanager
def browser(profile: Optional[str] = None, headless: Optional[bool] = None):
    """Yield a Playwright page on the persistent JLCPCB profile.

    Playwright is imported here, not at module scope, so the pure parsers can be
    imported and tested on a machine with no browser.
    """
    from playwright.sync_api import sync_playwright

    if headless is None:
        headless = os.environ.get("JLC_HEADLESS", "0") == "1"

    prof = profile_dir(profile)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            prof,
            executable_path=CHROME,
            headless=headless,
            args=LAUNCH_ARGS,
            locale="en-US",
            viewport={"width": 1400, "height": 1100},
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            yield page
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def is_authed(page) -> bool:
    """True when the page renders the signed-in account area.

    Reads the header, never a status code: ``POST /checkLogin`` answers HTTP 200
    with ``login.unlogin`` while logged out, so it cannot be used as a verdict.
    """
    try:
        text = page.evaluate("document.body.innerText || ''")
    except Exception:
        return False
    return AUTH_MARKER in text


def assert_session(page, url: str = HOME_URL) -> None:
    """Navigate and raise SessionError if the profile is not authenticated."""
    _goto(page, url)
    if not is_authed(page):
        raise SessionError(
            "profile is not authenticated (header does not render "
            f"'{AUTH_MARKER}'); re-bootstrap the session per "
            "docs/01-INTEGRATION-RUNBOOK.md"
        )


def _goto(page, url: str, settle: float = 12.0) -> None:
    """Navigate tolerantly, then let the SPA settle.

    The SPA sometimes never fires 'load'; waiting for 'commit' and settling is
    what the working manual scripts did, and it is more reliable than
    wait_until='load'.
    """
    import time

    try:
        page.goto(url, wait_until="commit", timeout=90000)
    except Exception:
        pass
    time.sleep(settle)
