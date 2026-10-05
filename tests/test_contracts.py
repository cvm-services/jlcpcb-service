"""Contract tests for the browser layer.

These do NOT drive a browser. They pin the rules that were expensive to learn,
so the same mistakes are not reintroduced: selectors live in one module, the
session check never trusts a status code, and the BOM never invents a part.
"""
import pathlib

import pytest

from jlcpcb_client import selectors


def test_selectors_module_holds_only_strings():
    """Every public name in selectors is a str or tuple-of-str.

    This is the constraint that makes 'selectors live in one file' true: if
    logic creeps in here, it stops being a single edit point for a redesign.
    """
    for name in dir(selectors):
        if name.startswith("_"):
            continue
        val = getattr(selectors, name)
        assert isinstance(val, (str, tuple)), f"{name} is {type(val)}"


def test_quote_url_points_at_the_cart_quote_page():
    assert selectors.QUOTE_URL == "https://cart.jlcpcb.com/quote"


def test_auth_marker_is_header_text_not_a_status_code():
    # /checkLogin returns HTTP 200 with login.unlogin while logged out, so the
    # verdict must be a rendered string. If someone replaces this with a code
    # check, this test is the tripwire.
    assert selectors.AUTH_MARKER == "My Account"


def test_price_label_is_the_one_jlcpcb_actually_renders():
    # Verified against a real capture. An earlier version of this constant said
    # "PCB Price", which JLCPCB never renders.
    assert selectors.LABEL_PRICE == "Calculated Price"
    assert selectors.LABEL_SHIPPING == "Shipping Estimate"


def test_render_markers_require_the_parsed_board_sentence():
    """Price/shipping render mid-upload; only 'Detected' means parsing finished.

    Without this the client returns a quote with layers/dimensions == None while
    the archive is still uploading (observed: "Uploading your files.... 74%").
    """
    assert "Detected" in selectors.RENDER_MARKERS


def test_gerber_input_is_the_known_hidden_input():
    assert selectors.GERBER_FILE_INPUT == "input#uploadFile"


def test_no_placeholder_tokens_in_selectors():
    """No '<...>' placeholders: they break copy-paste and the docs checker."""
    src = pathlib.Path(selectors.__file__).read_text()
    assert "<" not in src.replace("<=", "").replace("<-", "")


def test_excluded_bom_values_include_dnp_and_jumpers():
    from jlcpcb_client.bom import EXCLUDED_VALUES

    assert "DNP" in EXCLUDED_VALUES
    assert "0R" in EXCLUDED_VALUES
