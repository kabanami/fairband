"""Command line: ``python -m fairband serve | refresh | migrate``."""

import argparse
import logging
import signal
import sqlite3
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from types import FrameType
from typing import Any

import uvicorn

from fairband import __version__
from fairband.config import (
    DEFAULT_PORT,
    Keys,
    MissingKey,
    Settings,
    keys_path,
    load_keys,
    load_settings,
    require,
    utcnow,
)
from fairband.engine.types import PHASE_NUMBER
from fairband.policy import load_policy
from fairband.policy.tax import load_tax_table
from fairband.refresh.clients import build_clients
from fairband.refresh.run import KINDS, UNCLASSIFIED, Progress, Refresh
from fairband.refresh.worker import RefreshWorker
from fairband.store.db import connect, migrate
from fairband.store.refreshes import RefreshRunning, latest_refresh, mark_interrupted
from fairband.store.snapshots import SnapshotRow, latest_snapshot
from fairband.vendors.http import VendorError
from fairband.web.app import create_app

logger = logging.getLogger("fairband")

_HOST = "127.0.0.1"  # the screen is for this machine only (D11)
_PRIVATE_BITS = 0o077  # group and other
_NO_GF_KEY = "no GuruFocus key: the moat score and the GuruFocus EPS are not fetched"
_WAY_OUT = "Start the server, or run migrate, to mark an interrupted refresh."


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
        choices=KINDS,
        help="default: scoped when symbols are given, full otherwise",
    )

    commands.add_parser(
        "migrate", help="apply the database migrations and mark interrupted refreshes"
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    args = _build_parser().parse_args(argv)
    if args.command == "refresh" and args.kind is None:
        args.kind = "scoped" if args.symbols else "full"
    return args


def _serve(args: argparse.Namespace) -> int:
    """Apply the pending migrations, then serve the screen on 127.0.0.1 until interrupted. With
    an FMP key the server runs refreshes on its worker, whose thread alone calls the vendors;
    without one it serves the screen and refuses refreshes. When it starts, the app marks every
    ``running`` refresh interrupted; with no process lock in this cut, that includes one a command
    in another process is running at that moment."""
    settings = load_settings()
    policy, tax = load_policy(), load_tax_table()
    with closing(connect(settings.db_path)) as conn:
        migrate(conn)

    def conn_factory() -> sqlite3.Connection:
        return connect(settings.db_path)

    keys = _keys(settings)
    worker = None
    if keys.fmp is None:
        logger.warning("%s; the screen is served without refreshes", MissingKey("fmp"))
    else:
        fmp, gf, secrets = build_clients(keys, policy)
        worker = RefreshWorker(
            lambda cancel, on_progress: Refresh(
                conn_factory, fmp, gf, policy, tax, utcnow, cancel, on_progress, secrets
            )
        )
    app = create_app(settings, policy, conn_factory, worker)
    try:
        uvicorn.run(app, host=_HOST, port=args.port, log_level="info")
    finally:
        # A run still alive holds the clients, so they close with the process, which ends now:
        # closed here, they would fail the companies in flight. The cancel keeps the run from
        # starting another meanwhile; the next start marks its record interrupted.
        if worker is not None:
            worker.cancel()
    return 0


def _refresh(args: argparse.Namespace) -> int:
    """A refresh in the foreground with its progress lines, then, for a scoped refresh, one line
    per symbol from its latest snapshot, and for a full one its calibration. A ``VendorError`` or
    ``ValueError`` from the run (the screener failed or gave no rows) is one line, never a
    traceback: ``refresh <id>: failed: <message>``, or ``refresh failed: <message>`` when the run
    refused before its record existed. Exits 0 when the refresh is done, 1 when not, 2 when it
    cannot start."""
    if args.symbols == []:
        return _usage("no symbols given: name them as AAPL,MSFT")
    if args.kind == "price":
        return _usage("a price refresh is not built yet")
    if args.kind == "scoped" and not args.symbols:
        return _usage("a scoped refresh needs symbols, e.g. AAPL,MSFT")
    if args.kind == "full" and args.symbols:
        return _usage("a full refresh takes no symbols: name none, or add --kind scoped")
    settings = load_settings()
    keys = _keys(settings)
    try:
        require(keys, "fmp")
    except MissingKey as exc:
        return _usage(str(exc))
    policy, tax = load_policy(), load_tax_table()
    with closing(connect(settings.db_path)) as conn:
        migrate(conn)
    cancel = threading.Event()
    fmp, gf, secrets = build_clients(keys, policy)
    started: list[int] = []
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
    try:
        with _ctrl_c_cancels(cancel):
            refresh_id = refresh.run(args.kind, args.symbols, started.append)
    except RefreshRunning as exc:
        print(f"{exc}; try again when it has finished. {_WAY_OUT}", file=sys.stderr)
        return 1
    except (VendorError, ValueError) as exc:
        reason = refresh.describe(exc)  # the record's message, when the record exists
        print(f"refresh {started[0]}: failed: {reason}" if started else f"refresh failed: {reason}")
        return 1
    finally:
        fmp.close()
        if gf is not None:
            gf.close()
    with closing(connect(settings.db_path)) as conn:
        last = latest_refresh(conn)  # ours, unless another refresh has started since
        symbols = dict.fromkeys(args.symbols or ())
        rows = [(symbol, latest_snapshot(conn, symbol)) for symbol in symbols]
    ours = last if last is not None and last.id == refresh_id else None
    status = "unknown" if ours is None else ours.status
    message = None if ours is None else ours.message
    print(f"refresh {refresh_id}: {status}" + (f": {message}" if message else ""))
    if ours is not None and ours.calibration is not None:
        for line in _calibration_lines(ours.calibration):
            print(line)
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


def _keys(settings: Settings) -> Keys:
    """The vendor keys, read after a warning when others can read the keys file; a warning too
    when an FMP key comes without a GuruFocus one."""
    _warn_if_others_can_read_keys(settings)
    keys = load_keys(settings)
    if keys.fmp is not None and keys.gurufocus is None:
        logger.warning(_NO_GF_KEY)
    return keys


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


def _calibration_lines(calibration: dict[str, Any]) -> list[str]:
    """``1,812 companies · 1,540 valued``, a line per phase in life-cycle order, then each refusal
    reason with its count, the most frequent first."""
    phases, refused = calibration["phases"], calibration["refused"]
    lines = [f"{calibration['total']:,} companies · {calibration['valued']:,} valued"]
    lines += [f"{phase}: {phases.get(phase, 0):,}" for phase in (*PHASE_NUMBER, UNCLASSIFIED)]
    by_count = sorted(refused.items(), key=lambda item: (-item[1], item[0]))
    lines += [f"{count:,} refused: {reason}" for reason, count in by_count]
    return lines


def _migrate(args: argparse.Namespace) -> int:
    """Apply the pending migrations, then mark ``interrupted`` the refreshes a server or a
    command that stopped left ``running``, as the server does when it starts. With no process
    lock in this cut, it also marks one another process is running at that moment."""
    with closing(connect(load_settings().db_path)) as conn:
        applied = migrate(conn)
        interrupted = mark_interrupted(conn, utcnow())
    for filename in applied:
        print(f"Applied {filename}")
    if not applied:
        print("No migrations to apply.")
    if interrupted:
        print(
            f"Marked {interrupted} running refresh{'' if interrupted == 1 else 'es'} interrupted."
        )
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
