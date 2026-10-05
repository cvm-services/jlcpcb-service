"""Command-line interface.

    jlcpcb-client quote BOARD.zip [--snapshot DIR] [--json]
    jlcpcb-client session          # health check the Chrome profile

The `quote` command is read-only: it uploads gerbers and prints the quote. It
never places an order — ordering is a separate, explicitly gated concern
(docs/04-AUTOMATION-PLAN.md §Phase 6).
"""
import argparse
import json
import sys

from .errors import JlcError
from .quote import quote_gerber
from .session import assert_session, browser


def _cmd_quote(args) -> int:
    q = quote_gerber(args.zip, profile=args.profile, snapshot_dir=args.snapshot)
    if args.json:
        print(json.dumps(q.as_dict(), indent=2))
    else:
        print(f"PCB price : ${q.pcb_price_usd:,.2f}")
        if q.shipping_usd is not None:
            print(f"Shipping  : ${q.shipping_usd:,.2f}")
        print(f"Qty       : {q.qty}")
        print(f"Layers    : {q.layers}")
        print(f"Size      : {q.dimensions_mm}")
        print(f"Weight    : {q.weight_kg} kg")
    return 0


def _cmd_session(args) -> int:
    with browser(profile=args.profile) as page:
        try:
            assert_session(page)
        except JlcError as e:
            print(f"UNAUTHENTICATED: {e}", file=sys.stderr)
            return 1
    print("session OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jlcpcb-client")
    ap.add_argument("--profile", default=None, help="Chrome profile dir override")
    sub = ap.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quote", help="quote a gerber zip (read-only)")
    q.add_argument("zip")
    q.add_argument("--snapshot", default=None, help="dir to save raw quote text + screenshot")
    q.add_argument("--json", action="store_true")
    q.set_defaults(fn=_cmd_quote)

    s = sub.add_parser("session", help="check the Chrome profile is authenticated")
    s.set_defaults(fn=_cmd_session)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except JlcError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
