"""Pure parsing of the JLCPCB quote page text.

No network, no browser. The quote page exposes no API, so the numbers are read
out of the rendered DOM text; these functions are the only place that happens,
which is what makes them testable against a saved snapshot.

The fixture these are tested against is a **verbatim capture** of a real quote
page (`tests/fixtures/quote_v8i_real.txt`). Do not edit it to make a test pass —
re-capture instead. An earlier fixture was hand-written to match the parser and
the whole suite passed while the parser was wrong.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from . import selectors
from .errors import QuoteParseError

_NUM = r"([0-9][0-9,]*(?:\.[0-9]+)?)"


@dataclass
class Quote:
    """A read-only PCB quote. Only the price is required."""

    pcb_price_usd: float
    raw_text: str = ""
    qty: Optional[int] = None
    layers: Optional[int] = None
    dimensions_mm: Optional[str] = None
    shipping_usd: Optional[float] = None
    weight_kg: Optional[float] = None
    extras: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = {
            "pcb_price_usd": self.pcb_price_usd,
            "qty": self.qty,
            "layers": self.layers,
            "dimensions_mm": self.dimensions_mm,
            "shipping_usd": self.shipping_usd,
            "weight_kg": self.weight_kg,
        }
        d.update(self.extras)
        return d


def _money(s: str) -> float:
    return float(s.replace(",", ""))


def _label_int(text: str, label: str) -> Optional[int]:
    m = re.search(re.escape(label) + r"[\s:]*\n?\s*" + _NUM, text)
    if not m:
        return None
    try:
        return int(float(m.group(1).replace(",", "")))
    except ValueError:
        return None


def _money_after_label(text: str, label: str) -> Optional[float]:
    """Find a label, then the first money amount after it.

    Anchoring on the label matters: the page carries several '$' figures
    (build-time adders, coupons, the special offer) and a naive global match
    returns whichever comes first, not the one the caller asked for.
    """
    idx = text.find(label)
    if idx < 0:
        return None
    m = re.search(r"\$\s?" + _NUM, text[idx:])
    if not m:
        return None
    return _money(m.group(1))


def _parse_detected(text: str):
    """Return (layers, "WxHmm") from JLCPCB's board summary sentence."""
    m = re.search(selectors.DETECTED_RE, text)
    if not m:
        return None, None
    layers = int(m.group(1))
    dims = f"{m.group(2)}x{m.group(3)}mm"
    return layers, dims


def parse_quote_text(text: str) -> Quote:
    """Parse the quote page's visible text into a Quote.

    Raises QuoteParseError when no price can be found — a quote without a price
    must never be handed back as if it were valid, because a caller cannot tell
    "free" from "we failed to read it".
    """
    if not text or not text.strip():
        raise QuoteParseError("empty quote text")

    price = _money_after_label(text, selectors.LABEL_PRICE)
    if price is None:
        for alt in selectors.LABEL_PRICE_FALLBACKS:
            price = _money_after_label(text, alt)
            if price is not None:
                break
    if price is None:
        raise QuoteParseError(
            f"no '{selectors.LABEL_PRICE}' amount found in quote text"
        )

    layers, dims = _parse_detected(text)

    weight = None
    m = re.search(selectors.WEIGHT_RE, text, re.I)
    if m:
        weight = float(m.group(1))

    return Quote(
        pcb_price_usd=price,
        raw_text=text,
        qty=_label_int(text, selectors.LABEL_QTY),
        layers=layers,
        dimensions_mm=dims,
        shipping_usd=_money_after_label(text, selectors.LABEL_SHIPPING),
        weight_kg=weight,
    )
