class JlcError(Exception):
    """Base class for all errors raised by this client."""


class QuoteParseError(JlcError):
    """The quote page did not contain the fields a quote requires.

    Raised rather than returning a partial quote: a quote without a price is
    worse than no quote, because a caller cannot tell the difference between
    "free" and "we failed to read it".
    """


class SessionError(JlcError):
    """The Chrome profile is not authenticated, or the session has expired."""
