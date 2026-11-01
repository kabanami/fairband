"""The full refresh over the six listings of ``fixture_universe`` and a migrated temporary database
that holds no universe yet: the universe, the fetch, the deciles, the values and the calibration;
the stops and the rerun that continues.
"""

import threading
from collections import Counter
from contextlib import closing
from datetime import timedelta

import pytest
from fixture_universe import ADMITTED, serve_universe
from refresh_env import Env
from vendor_double import FMP_KEY

from fairband.engine.classifier import Deciles
from fairband.refresh.deciles import deciles_for_universe
from fairband.refresh.run import Progress
from fairband.store.companies import latest_companies
from fairband.store.refreshes import current_refresh, latest_deciles
from fairband.vendors.http import VendorError

RATE_LIMITED = "data fetch incomplete: rate limited"
NOT_BUILT = "Young Growth route not built yet"
# The fixture universe's calibration: ACME, AXLE and MILD valued, NEWT refused; every company
# carries a flag (the synthetic company has no leases on its balance sheet, among others).
CALIBRATION = {
    "total": 4,
    "valued": 3,
    "refused": {NOT_BUILT: 1},
    "phases": {
        "Start-up": 0,
        "Young Growth": 1,
        "High Growth": 0,
        "Mature Growth": 2,
        "Mature Stable": 1,
        "Decline": 0,
        "unclassified": 0,
    },
    "flagged": 4,
    "flags": {
        "fcf-sign": 1,
        "growth-word-disagrees": 1,
        "large-nri": 3,
        "leases-not-on-balance-sheet": 4,
        "line-not-presented:current_lease_liability": 3,
        "line-not-presented:goodwill": 3,
        "line-not-presented:lease_rou_asset": 3,
        "margin-direction-disagrees": 2,
        "path-on-eps": 2,
        "sbc-basis-unknown": 2,
        "value-spread": 2,
    },
    "universe": {
        "admitted": 4,
        "excluded": {"industry": 1, "symbol pattern": 0, "manual exclusion": 0, "skipped": 1},
    },
}


@pytest.fixture
def env_fixture_universe(env_without_universe: Env) -> Env:
    serve_universe(env_without_universe.router)
    return env_without_universe


def deciles(env: Env) -> Deciles | None:
    with closing(env.connect()) as conn:
        return latest_deciles(conn)


def universe(env: Env) -> dict[str, tuple[int, bool]]:
    """The latest universe: each listing recorded, with its refresh and whether it is admitted."""
    with closing(env.connect()) as conn:
        rows = latest_companies(conn, eligible_only=False)
    return {c.symbol: (c.refresh_id, c.eligible) for c in rows}


def test_full_refresh_builds_universe_deciles_and_values(env_fixture_universe: Env) -> None:
    env = env_fixture_universe
    refresh_id = env.refresh().run("full")
    row = env.last()
    assert (row.id, row.kind, row.symbols, row.status, row.stage, row.message) == (
        refresh_id,
        "full",
        None,
        "done",
        "done",
        None,
    )
    assert universe(env) == {
        "ACME": (refresh_id, True),
        "AXLE": (refresh_id, True),
        "FIRB": (refresh_id, False),
        "MILD": (refresh_id, True),
        "NEWT": (refresh_id, True),
    }
    saved = deciles(env)
    assert saved is not None
    # Every admitted company ranks on growth; NEWT's negative margin keeps it off the margin slope.
    assert (saved.refresh_id, saved.n_growth, saved.n_margin) == (refresh_id, 4, 3)

    assert env.items(refresh_id) == [(symbol, "valued", None) for symbol in ADMITTED]
    snapshots = {symbol: env.snapshot(symbol) for symbol in ADMITTED}
    assert {
        s: (row.refresh_id, row.deciles_refresh_id) for s, row in snapshots.items()
    } == dict.fromkeys(ADMITTED, (refresh_id, refresh_id))
    assert {s: row.phase for s, row in snapshots.items()} == {
        "ACME": "Mature Growth",
        "AXLE": "Mature Growth",
        "MILD": "Mature Stable",
        "NEWT": "Young Growth",
    }
    for symbol, route in (
        ("ACME", "mature-growth"),
        ("AXLE", "mature-growth"),
        ("MILD", "mature-stable"),
    ):
        valued = snapshots[symbol]
        assert valued.route == route and valued.refusal is None
        assert valued.value is not None and valued.value > 0
    assert snapshots["NEWT"].refusal == NOT_BUILT and snapshots["NEWT"].value is None

    calibration = row.calibration
    assert calibration == CALIBRATION
    assert sum(calibration["phases"].values()) == calibration["total"]
    assert calibration["valued"] + sum(calibration["refused"].values()) == calibration["total"]

    assert list(dict.fromkeys(p.stage for p in env.progress)) == [
        "universe",
        "fetch",
        "deciles",
        "value",
        "done",
    ]
    assert [p for p in env.progress if p.stage in ("universe", "deciles", "done")] == [
        Progress(refresh_id, "universe", 0, 0, 0, None),
        Progress(refresh_id, "universe", 4, 0, 0, None),
        Progress(refresh_id, "deciles", 0, 0, 4, None),
        Progress(refresh_id, "deciles", 4, 0, 0, None),
        Progress(refresh_id, "done", 4, 0, 0, None),
    ]
    assert env.router.calls["screener"] == 1
    assert set(env.router.symbol_calls) == {"", *ADMITTED}  # FIRB and TINY are never fetched


def test_rerun_after_cancel_continues(env_fixture_universe: Env) -> None:
    """The cancel lands after two companies are fetched: no deciles and no values, since the
    deciles need the whole universe. The rerun is a new refresh: it rebuilds the universe from the
    screener response of the hour before, reuses the two fetched companies and fetches the rest."""
    env = env_fixture_universe
    cancel = threading.Event()

    def stop_after_two(progress: Progress) -> None:
        if progress.stage == "fetch" and progress.done + progress.failed == 2:
            cancel.set()

    first = env.refresh(workers=1, cancel=cancel, then=stop_after_two).run("full")
    row = env.last()
    assert (row.id, row.status, row.stage, row.calibration) == (first, "cancelled", "fetch", None)
    assert env.items(first) == [
        ("ACME", "fetched", None),
        ("AXLE", "fetched", None),
        ("MILD", "pending", None),
        ("NEWT", "pending", None),
    ]
    assert deciles(env) is None and env.snapshots() == []
    assert env.router.symbol_calls == Counter({"": 1, "ACME": 14, "AXLE": 14})

    env.router.symbol_calls.clear()
    env.progress.clear()
    env.clock.now += timedelta(hours=1)
    second = env.refresh().run("full")
    row = env.last()
    assert (row.id, row.status) == (second, "done") and second == first + 1
    assert env.router.symbol_calls == Counter({"MILD": 14, "NEWT": 14})  # no screener call
    assert Progress(second, "fetch", 4, 0, 0, None) in env.progress
    assert env.items(second) == [(symbol, "valued", None) for symbol in ADMITTED]
    assert {refresh for refresh, _ in universe(env).values()} == {second}
    saved = deciles(env)
    assert saved is not None and saved.refresh_id == second
    assert sorted(env.snapshots()) == sorted(
        (symbol, second, env.snapshot(symbol).refusal) for symbol in ADMITTED
    )
    assert row.calibration is not None and row.calibration["total"] == 4


@pytest.mark.parametrize(
    ("status", "body", "error", "message"),
    [
        (403, None, VendorError, "VendorError: "),
        (200, b"[]", ValueError, "ValueError: screener returned no rows"),
    ],
)
def test_full_refresh_screener_failure_finishes_failed(
    env_fixture_universe: Env,
    status: int,
    body: bytes | None,
    error: type[Exception],
    message: str,
) -> None:
    env = env_fixture_universe
    if body is None:
        env.router.fail.add("screener")
        env.router.fail_status = status
    else:
        env.router.bodies["screener"] = body
    with pytest.raises(error):
        env.refresh().run("full")
    row = env.last()
    assert (row.status, row.stage, row.finished_at, row.calibration) == (
        "failed",
        "universe",
        env.clock.now,
        None,
    )
    assert row.message is not None and row.message.startswith(message)
    assert FMP_KEY not in row.message
    assert universe(env) == {} and deciles(env) is None and env.snapshots() == []
    assert set(env.router.symbol_calls) == {""}  # no company is fetched
    with closing(env.connect()) as conn:
        assert current_refresh(conn) is None


def test_full_refresh_rate_limited_saves_no_deciles(env_fixture_universe: Env) -> None:
    """As in a scoped refresh, a 429 stops the fetch and what was fetched is valued, here with no
    deciles stored: the run saves none from part of the universe."""
    env = env_fixture_universe
    env.router.fail_status = 429
    env.router.fail_symbols.add("MILD")
    refresh_id = env.refresh(workers=1).run("full")
    row = env.last()
    assert (row.status, row.message, row.calibration) == (
        "failed",
        "rate limited by FMP: stopped after 3 companies",
        None,
    )
    assert deciles(env) is None
    assert env.items(refresh_id) == [
        ("ACME", "valued", None),
        ("AXLE", "valued", None),
        ("MILD", "failed", RATE_LIMITED),
        ("NEWT", "pending", None),
    ]
    assert sorted(env.snapshots()) == [
        ("ACME", refresh_id, "no universe deciles yet"),
        ("AXLE", refresh_id, "no universe deciles yet"),
        ("MILD", refresh_id, RATE_LIMITED),
    ]


def test_deciles_leave_out_symbols_without_statements(env_fixture_universe: Env) -> None:
    env = env_fixture_universe
    refresh_id = env.refresh().run("full")
    saved = deciles(env)
    assert saved is not None and saved.refresh_id == refresh_id
    with closing(env.connect()) as conn:
        assert deciles_for_universe(conn, [*ADMITTED, "NONE"], refresh_id) == saved
        assert deciles_for_universe(conn, ["NONE"], 99) == Deciles((), (), 0, 0, 99)
