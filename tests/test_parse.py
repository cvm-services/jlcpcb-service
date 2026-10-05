"""Parsing tests against a VERBATIM capture of a real quote page.

The fixture is not hand-written. It is the exact text JLCPCB rendered for the
v8i board (see `fixtures/quote_v8i_real.txt`). If a test here fails after a
JLCPCB change, re-capture the fixture — do not edit it to agree with the parser.

An earlier version of this file used a hand-written fixture and passed while the
parser was reading labels that do not exist. That is the failure mode this file
exists to prevent.
"""
import pathlib

import pytest

from jlcpcb_client import selectors
from jlcpcb_client.errors import QuoteParseError
from jlcpcb_client.parse import parse_quote_text

REAL = pathlib.Path(__file__).parent / "fixtures" / "quote_v8i_real.txt"


@pytest.fixture(scope="module")
def real_text():
    return REAL.read_text()


def test_fixture_is_a_real_capture_not_a_fabrication(real_text):
    """Sanity: the captured page carries the strings JLCPCB actually renders."""
    for marker in ("Calculated Price", "Shipping Estimate", "Detected 4 layer board"):
        assert marker in real_text, f"fixture lost its real marker: {marker}"
    # And it must NOT contain a label that does not exist on the page.
    assert "PCB Price" not in real_text


def test_parses_real_v8i_quote(real_text):
    q = parse_quote_text(real_text)
    assert q.pcb_price_usd == 8.00
    assert q.shipping_usd == 23.21
    assert q.weight_kg == 0.17
    assert q.qty == 5
    assert q.layers == 4
    assert q.dimensions_mm == "45x55mm"


def test_layers_and_dims_come_from_the_detected_sentence(real_text):
    assert selectors.DETECTED_RE
    q = parse_quote_text(real_text)
    assert (q.layers, q.dimensions_mm) == (4, "45x55mm")


def test_weight_is_the_board_weight_not_the_copper_weight(real_text):
    """The page contains 'Outer Copper Weight' BEFORE the real weight.

    A label search for 'Weight' returns the copper option; the real figure is
    the one suffixed with kg.
    """
    assert real_text.find("Outer Copper Weight") < real_text.find("0.17kg")
    q = parse_quote_text(real_text)
    assert q.weight_kg == 0.17


def test_missing_price_raises_rather_than_returning_partial():
    text = "PCB Qty\n5\nDetected 4 layer board of 45x55mm(1.772x2.165 inches).\n"
    with pytest.raises(QuoteParseError):
        parse_quote_text(text)


def test_empty_text_raises():
    with pytest.raises(QuoteParseError):
        parse_quote_text("")
    with pytest.raises(QuoteParseError):
        parse_quote_text("   ")


def test_price_falls_back_to_special_offer_when_calculated_price_absent():
    text = "Special Offer\n$8.00\nShipping Estimate\n$23.21\n"
    q = parse_quote_text(text)
    assert q.pcb_price_usd == 8.00


def test_handles_thousands_separator():
    text = "Calculated Price\n$1,234.56\n"
    assert parse_quote_text(text).pcb_price_usd == 1234.56


def test_detected_sentence_without_quote_still_yields_no_dims():
    text = "Calculated Price\n$8.00\n"
    q = parse_quote_text(text)
    assert q.layers is None and q.dimensions_mm is None
