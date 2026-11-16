"""Command line: ``python -m fairband serve | refresh | migrate | mcp``, or ``fairband`` (the console
script)."""

import argparse
import logging
import signal
import sqlite3
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
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
from fairband.mcp.server import main as run_mcp
from fairband.policy import load_policy
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh.clients import build_clients, build_fmp, build_gurufocus
from fairband.refresh.passthrough import Passthrough
from fairband.refresh.run import KINDS, UNCLASSIFIED, Progress, Refresh
from fairband.refresh.worker import RefreshWorker
from fairband.store.db import connect, migrate
from fairband.store.refreshes import RefreshRunning, latest_refresh, mark_interrupted
from fairband.store.settings import effective_policy
from fairband.store.snapshots import SnapshotRow, latest_snapshot
from fairband.vendors.http import VendorError
from fairband.vendors.limiter import RateLimiter
from fairband.vendors.logos import fetch_logo
from fairband.web.app import create_app

logger = logging.getLogger("fairband")

_HOST = "127.0.0.1"  # the screen is for this machine only (D11)
_PRIVATE_BITS = 0o077  # group and other
_NO_GF_KEY = (
    "no GuruFocus key: the moat score and the GuruFocus EPS are not fetched, and the pe-history"
    " pass-through is off"
)
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
        help="default: scoped when symbols are given, full otherwise; revalue: value every"
        " company again from the stored facts, with no vendor call",
    )

    commands.add_parser(
        "migrate", help="apply the database migrations and mark interrupted refreshes"
    )

    mcp = commands.add_parser(
        "mcp", help="serve the agent's tools over stdio, calling the server on 127.0.0.1"
    )
    mcp.add_argument("--port", type=int, default=DEFAULT_PORT, help="the server's port")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    args = _build_parser().parse_args(argv)
    if args.command == "refresh" and args.kind is None:
        args.kind = "scoped" if args.symbols else "full"
    return args


def make_refresh(
    conn_factory: Callable[[], sqlite3.Connection],
    keys: Keys | None,
    tax: TaxTable,
    cancel: threading.Event,
    on_progress: Callable[[Progress], None],
    limiter: RateLimiter | None = None,
) -> Refresh:
    """The server worker's next run: under the effective policy read now (the file and the stored
    overlay, spec 2026-11-04 8.8), so a setting saved since the last run is this one's, with
    vendor clients of its own built from that policy (the pace is a setting). Given the server's
    ``limiter``, which the pass-through shares, the run paces it to that policy and its FMP client
    takes its slots from it. Without an FMP key it builds no client and the run refuses every kind
    but a revalue. ``Refresh.close`` closes the clients. Raises ``ValueError`` when the stored
    settings no longer apply to the file."""
    with closing(conn_factory()) as conn:
        policy = effective_policy(conn)
    if keys is not None and keys.fmp is not None:
        if limiter is not None:
            limiter.set_pace(policy.refresh.fmp_calls_per_minute)
        fmp, gf, secrets = build_clients(keys, policy, limiter=limiter)
    else:
        fmp, gf, secrets = None, None, ()

    def close() -> None:
        if fmp is not None:
            fmp.close()
        if gf is not None:
            gf.close()

    return Refresh(conn_factory, fmp, gf, policy, tax, utcnow, cancel, on_progress, secrets, close)


def _serve(args: argparse.Namespace) -> int:
    """Apply the pending migrations, then serve the screen on 127.0.0.1 until interrupted. The
    server runs refreshes on its worker; each run reads the effective policy and builds its
    clients as it starts (``make_refresh``). With an FMP key it also builds the agent's vendor
    pass-through, whose calls run on the request threads, with a GuruFocus client of its own when
    a GuruFocus key is present, not paced as the refresh's is not, its token among the secrets
    scrubbed; without one the pe-history pass-through answers 503. One limiter paces every FMP
    call of both: made at the pace of the effective policy as the server starts (the file's, when
    a stored setting no longer applies, which the worker then refuses), paced again by each run to
    the policy it runs under, and read by the pass-through, whose reuse window is the start's.
    Without an FMP key the worker runs a revalue only and refuses the other kinds, and the
    pass-through route answers 503. With or without one the app fetches a company's logo
    (``vendors.logos.fetch_logo``): FMP's image host takes no key, and the fetch goes through
    no limiter, since it counts against no quota. The app reads the policy file as its base. When it
    starts, the app marks every ``running`` refresh interrupted; with no process lock in this cut,
    that includes one a command in another process is running at that moment."""
    settings = load_settings()
    policy, tax = load_policy(), load_tax_table()
    with closing(connect(settings.db_path)) as conn:
        migrate(conn)
        try:
            started = effective_policy(conn, policy)
        except ValueError:
            started = policy

    def conn_factory() -> sqlite3.Connection:
        return connect(settings.db_path)

    keys = _keys(settings)
    limiter = RateLimiter(started.refresh.fmp_calls_per_minute, utcnow, time.sleep)
    passthrough = None
    if keys.fmp is None:
        logger.warning("%s; the server runs a revalue only", MissingKey("fmp"))
    else:
        secrets = tuple(key for key in (keys.fmp, keys.gurufocus) if key)
        fmp = build_fmp(keys, started, limiter=limiter)
        gurufocus = build_gurufocus(keys, started)
        passthrough = Passthrough(fmp, conn_factory, started, utcnow, secrets, gurufocus)
    worker = RefreshWorker(
        lambda cancel, on_progress: make_refresh(
            conn_factory, keys, tax, cancel, on_progress, limiter
        )
    )
    app = create_app(
        settings,
        policy,
        conn_factory,
        worker,
        tax=tax,
        passthrough=passthrough,
        fetch_logo=fetch_logo,
    )
    try:
        uvicorn.run(app, host=_HOST, port=args.port, log_level="info")
    finally:
        # A run still alive holds the clients, so they close with the process, which ends now:
        # closed here, they would fail the companies in flight. The cancel keeps the run from
        # starting another meanwhile; the next start marks its record interrupted. The server has
        # answered its last request, so the pass-through's clients close.
        worker.cancel()
        if passthrough is not None:
            passthrough.close()
    return 0


def _refresh(args: argparse.Namespace) -> int:
    """A refresh in the foreground with its progress lines, then, for a scoped refresh, one line
    per symbol from its latest snapshot, for a full one or a revalue its calibration, and for a
    price one its counts on the status line: ``refresh 7: done · 1,800 repriced, 3 failed, 9
    skipped``. A revalue reads no key and builds no vendor client. A ``VendorError`` or
    ``ValueError`` from the run (the screener failed or gave no rows) is one line, never a
    traceback: ``refresh <id>: failed: <message>``, or ``refresh failed: <message>`` when the run
    refused before its record existed. The run reads the effective policy (the file and the
    stored overlay) as it starts; stored settings that no longer apply to the file are one line
    naming the setting. Exits 0 when the refresh is done, 1 when not, 2 when it cannot start."""
    if args.symbols == []:
        return _usage("no symbols given: name them as AAPL,MSFT")
    if args.kind == "price" and args.symbols:
        return _usage("a price refresh takes no symbols: name none, or leave out --kind price")
    if args.kind == "scoped" and not args.symbols:
        return _usage("a scoped refresh needs symbols, e.g. AAPL,MSFT")
    if args.kind == "full" and args.symbols:
        return _usage("a full refresh takes no symbols: name none, or add --kind scoped")
    if args.kind == "revalue" and args.symbols:
        return _usage("a revalue takes no symbols: name none, or leave out --kind revalue")
    settings = load_settings()
    keys = None if args.kind == "revalue" else _keys(settings)
    if keys is not None:
        try:
            require(keys, "fmp")
        except MissingKey as exc:
            return _usage(str(exc))
    base, tax = load_policy(), load_tax_table()
    with closing(connect(settings.db_path)) as conn:
        migrate(conn)
        try:
            policy = effective_policy(conn, base)
        except ValueError as exc:
            return _usage(str(exc))
    cancel = threading.Event()
    fmp, gf, secrets = (None, None, ()) if keys is None else build_clients(keys, policy)
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
        if fmp is not None:
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
    calibration = None if ours is None else ours.calibration
    line = f"refresh {refresh_id}: {status}" + (f": {message}" if message else "")
    if args.kind == "price" and calibration is not None:
        line += (
            f" · {calibration['repriced']:,} repriced, {calibration['failed']:,} failed,"
            f" {calibration['skipped']:,} skipped"
        )
    print(line)
    if args.kind in ("full", "revalue") and calibration is not None:
        for line in _calibration_lines(calibration):
            print(line)
    for symbol, snapshot in rows:
        print(_snapshot_line(symbol, snapshot, policy.designation_edges))
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


def _snapshot_line(symbol: str, snapshot: SnapshotRow | None, edges: Sequence[float]) -> str:
    """``AAPL  Mature Growth  value 189.40  near (1.05 × value)``, or the phase (``—`` without
    one) and the refusal reason. A snapshot valued before the designation ends at its value. The
    ratio is ``_ratio_figure``'s, on the policy's designation ``edges``."""
    if snapshot is None:
        return f"{symbol}  —  no snapshot yet"
    phase = snapshot.phase or "—"
    if snapshot.value is None:
        return f"{symbol}  {phase}  {snapshot.refusal}"
    line = f"{symbol}  {phase}  value {snapshot.value:.2f}"
    if snapshot.designation is None or snapshot.price_to_value is None:
        return line
    ratio = _ratio_figure(snapshot.price_to_value, edges)
    return f"{line}  {snapshot.designation} ({ratio} × value)"


def _ratio_figure(ratio: float, edges: Sequence[float]) -> str:
    """Price ÷ value to two decimals, unless they would land on one of the designation ``edges``
    the ratio is not on (0.8499 would read 0.85, where ``near`` starts, beside ``below``); then
    three decimals, kept a thousandth off the edge (0.849, and 1.151 for 1.1501), so the figure
    stays inside the word's band. The drawer's caption does the same (``app.js``)."""
    two = f"{ratio:.2f}"
    edge = float(two)
    if ratio == edge or edge not in edges:
        return two
    three = float(f"{ratio:.3f}")
    three = min(three, edge - 0.001) if ratio < edge else max(three, edge + 0.001)
    return f"{three:.3f}"


def _calibration_lines(calibration: dict[str, Any]) -> list[str]:
    """``1,812 companies · 1,540 valued · 204 flagged by a classifier check``, a line per phase in
    life-cycle order, then each refusal reason with its count, the most frequent first."""
    phases, refused = calibration["phases"], calibration["refused"]
    total, valued, flagged = calibration["total"], calibration["valued"], calibration["flagged"]
    lines = [f"{total:,} companies · {valued:,} valued · {flagged:,} flagged by a classifier check"]
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


def _mcp(args: argparse.Namespace) -> int:
    """Serve the agent's tools over stdio (``fairband.mcp.server``) until the host closes the
    pipe, each tool a call to the web server on ``--port``, which must be running: when it does
    not answer, each tool answers so in one sentence. Opens no database and reads no key; stdout
    carries the protocol alone, the log lines go to stderr."""
    run_mcp(args.port)
    return 0


_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "serve": _serve,
    "refresh": _refresh,
    "migrate": _migrate,
    "mcp": _mcp,
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # Once per process; a no-op when logging is configured already. The scrubbing filters of
    # fairband.vendors.http keep the keys out of httpx's and httpcore's records.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
