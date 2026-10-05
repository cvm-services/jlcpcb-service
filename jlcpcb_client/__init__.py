"""JLCPCB quote client — drive the cart quote page over CDP.

Requires a persistent Chrome profile that already holds a JLCPCB session
(see docs/01-INTEGRATION-RUNBOOK.md §2). Playwright is imported lazily so the
pure parsers (parse, bom) are importable without a browser installed.
"""
from .errors import QuoteParseError, SessionError
from .parse import Quote, parse_quote_text

__all__ = ["Quote", "parse_quote_text", "QuoteParseError", "SessionError"]
__version__ = "0.1.0"
