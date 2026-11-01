"""Command line: ``python -m fairband serve | refresh | migrate``."""

import argparse
import logging
import signal
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from types import FrameType

from fairband import __version__
from fairband.config import (
    MissingKey,
    Settings,
    keys_path,
    load_keys,
    load_settings,
    require,
    utcnow,
)
from fairband.policy import load_policy
from fairband.policy.tax import load_tax_table
from fairband.refresh.clients import build_clients
from fairband.refresh.run import Progress, Refresh
from fairband.store.db import connect, migrate
from fairband.store.refreshes import RefreshRunning, latest_refresh
from fairband.store.snapshots import SnapshotRow, latest_snapshot

logger = logging.getLogger("fairband")

DEFAULT_PORT = 8470
REFRESH_KINDS = ("full", "price", "scoped")
_PRIVATE_BITS = 0o077  # group and other


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
    """A scoped refresh of the named symbols in the foreground, then one line per symbol from
    its latest snapshot. Exits 0 when the refresh is done, 1 when not, 2 when it cannot start."""
    if args.symbols == []:
        return _usage("no symbols given: name them as AAPL,MSFT")
    if args.kind != "scoped":
        return _usage(f"a {args.kind} refresh is not built yet")
    if not args.symbols:
        return _usage("a scoped refresh needs symbols, e.g. AAPL,MSFT")
    settings = load_settings()
    _warn_if_others_can_read_keys(settings)
    keys = load_keys(settings)
    try:
        require(keys, "fmp")
    except MissingKey as exc:
        return _usage(str(exc))
    if keys.gurufocus is None:
        logger.warning("no GuruFocus key: the moat score and the GuruFocus EPS are not fetched")
    policy, tax = load_policy(), load_tax_table()
    with closing(connect(settings.db_path)) as conn:
        migrate(conn)
    cancel = threading.Event()
    fmp, gf, secrets = build_clients(keys, policy)
    try:
        refresh = Refresh(
            lambda: connect(settings.db_path),
            fmp,
            gf,
            policy,
            tax,
            utcnow,
            cancel,
            _print_progress,
            secrets,
        )
        with _ctrl_c_cancels(cancel):
            refresh_id = refresh.run("scoped", args.symbols)
    except RefreshRunning as exc:
        print(f"{exc}; try again when it has finished", file=sys.stderr)
        return 1
    finally:
        fmp.close()
        if gf is not None:
            gf.close()
    with closing(connect(settings.db_path)) as conn:
        last = latest_refresh(conn)  # ours, unless another refresh has started since
        rows = [(symbol, latest_snapshot(conn, symbol)) for symbol in dict.fromkeys(args.symbols)]
    ours = last if last is not None and last.id == refresh_id else None
    status = "unknown" if ours is None else ours.status
    message = None if ours is None else ours.message
    print(f"refresh {refresh_id}: {status}" + (f": {message}" if message else ""))
    for symbol, snapshot in rows:
        print(_snapshot_line(symbol, snapshot))
    return 0 if status == "done" else 1


@contextmanager
def _ctrl_c_cancels(cancel: threading.Event) -> Iterator[None]:
    """While the block runs, the first Ctrl-C sets ``cancel`` (the refresh ends ``cancelled``
    after the current company) and puts back Python's default handler, so a second Ctrl-C
    interrupts at once. Python runs signal handlers on the main thread only, so on any other
    thread this changes nothing. The handler in place before is restored at the end."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def first_ctrl_c(signum: int, frame: FrameType | None) -> None:
        cancel.set()
        signal.signal(signal.SIGINT, signal.default_int_handler)

    previous = signal.signal(signal.SIGINT, first_ctrl_c)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, signal.default_int_handler if previous is None else previous)


def _usage(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def _warn_if_others_can_read_keys(settings: Settings) -> None:
    path = keys_path(settings)
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return
    if mode & _PRIVATE_BITS:
        logger.warning(
            "%s has mode %04o: other users can read it; chmod 600 it", path, mode & 0o777
        )


def _print_progress(progress: Progress) -> None:
    print(
        f"{progress.stage}: {progress.done} done, {progress.failed} failed,"
        f" {progress.remaining} to go",
        flush=True,
    )


def _snapshot_line(symbol: str, snapshot: SnapshotRow | None) -> str:
    """``AAPL  Mature Growth  value 189.40  stance HOLD``, or the phase (``—`` without one) and
    the refusal reason."""
    if snapshot is None:
        return f"{symbol}  —  no snapshot yet"
    phase = snapshot.phase or "—"
    if snapshot.value is None:
        return f"{symbol}  {phase}  {snapshot.refusal}"
    return f"{symbol}  {phase}  value {snapshot.value:.2f}  stance {snapshot.stance5}"


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
    # Once per process; a no-op when logging is configured already. The scrubbing filters of
    # fairband.vendors.http keep the keys out of httpx's and httpcore's records.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
