"""Command line: ``python -m fairband serve | refresh | migrate``."""

import argparse
from collections.abc import Callable
from contextlib import closing

from fairband import __version__
from fairband.config import load_settings
from fairband.store.db import connect, migrate

DEFAULT_PORT = 8470
REFRESH_KINDS = ("full", "price", "scoped")


def _symbol_list(text: str) -> list[str]:
    return [symbol.strip() for symbol in text.split(",") if symbol.strip()]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fairband", description="A local valuation screen for a value investor."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="serve the screen on 127.0.0.1")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)

    refresh = commands.add_parser("refresh", help="fetch, classify and value companies")
    refresh.add_argument(
        "symbols",
        nargs="?",
        type=_symbol_list,
        help="comma-separated symbols, e.g. AAPL,MSFT; omit for the whole universe",
    )
    refresh.add_argument(
        "--kind",
        choices=REFRESH_KINDS,
        help="default: scoped when symbols are given, full otherwise",
    )

    commands.add_parser("migrate", help="apply the database migrations")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    args = _build_parser().parse_args(argv)
    if args.command == "refresh" and args.kind is None:
        args.kind = "scoped" if args.symbols else "full"
    return args


def _serve(args: argparse.Namespace) -> int:
    raise NotImplementedError("serve is not built yet")


def _refresh(args: argparse.Namespace) -> int:
    raise NotImplementedError("refresh is not built yet")


def _migrate(args: argparse.Namespace) -> int:
    with closing(connect(load_settings().db_path)) as conn:
        applied = migrate(conn)
    for filename in applied:
        print(f"Applied {filename}")
    if not applied:
        print("No migrations to apply.")
    return 0


_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "serve": _serve,
    "refresh": _refresh,
    "migrate": _migrate,
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
