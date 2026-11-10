"""The splits on file (spec 2026-11-09 section 10) over a temporary database that
``fetch_company`` fills.

The router answers each endpoint a test sets with its payload, and every other endpoint with its
ACME fixture.
"""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from synthetic import add_company, bodies
from vendor_double import Clients, Clock, Router

from fairband.policy import Policy
from fairband.refresh.fetch import fetch_company
from fairband.refresh.inputs_splits import SplitRow, splits_for
from fairband.store.observations import insert_observations, observations_for

type Store = Callable[..., sqlite3.Connection]


@pytest.fixture
def store(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> Store:
    """Fetches ACME with the given payloads in place of its fixtures, then lists the company."""

    def fill(company: bool = True, **payloads: Any) -> sqlite3.Connection:
        router.bodies.update(
            {endpoint: json.dumps(body).encode() for endpoint, body in payloads.items()}
        )
        fetch_company(conn, clients.fmp, clients.gf, "ACME", policy, clock(), clients.secrets)
        if company:
            add_company(conn)
        return conn

    return fill


def test_splits_for_reads_the_rows_oldest_first(store: Store) -> None:
    conn = store(
        **bodies(),
        splits=[
            {"symbol": "ACME", "date": "2026-10-15", "numerator": 2, "denominator": 1},
            {"symbol": "ACME", "date": "2019-05-20", "numerator": 3, "denominator": 2},
            {"symbol": "ACME", "date": "2010-01-04", "numerator": 1, "denominator": 10},
        ],
    )
    rows = splits_for(conn, "ACME")
    assert [(r.date, r.numerator, r.denominator) for r in rows] == [
        (date(2010, 1, 4), 1.0, 10.0),
        (date(2019, 5, 20), 3.0, 2.0),
        (date(2026, 10, 15), 2.0, 1.0),
    ]
    assert [r.ratio for r in rows] == [0.1, 1.5, 2.0]
    assert [r.word for r in rows] == ["1-for-10 reverse split", "3-for-2 split", "2-for-1 split"]


def test_a_split_word_prints_at_most_two_decimals() -> None:
    """A whole number prints as an integer, any other to two decimals with trailing zeros
    dropped."""
    day = date(2025, 1, 2)
    assert SplitRow(day, 1.0526, 1).word == "1.05-for-1 split"
    assert SplitRow(day, 1.1, 1).word == "1.1-for-1 split"
    assert SplitRow(day, 4, 3.0).word == "4-for-3 split"
    assert SplitRow(day, 1, 1.3333).word == "1-for-1.33 reverse split"


def test_splits_for_without_rows(store: Store) -> None:
    assert splits_for(store(**bodies(), splits=[]), "ACME") == ()


def test_splits_for_skips_a_half_split_and_a_zero_denominator(store: Store) -> None:
    """The normalizer stores neither; a store that holds one still reads no split from it."""
    conn = store(**bodies(), splits=[{"date": "2019-05-20", "numerator": 2, "denominator": 1}])
    denominator, numerator = observations_for(conn, "ACME", "split")
    insert_observations(
        conn,
        [
            replace(numerator, period=date(2021, 1, 4)),
            replace(numerator, period=date(2022, 1, 3)),
            replace(denominator, period=date(2022, 1, 3), value=Decimal(0)),
        ],
    )
    assert splits_for(conn, "ACME") == (SplitRow(date(2019, 5, 20), 2.0, 1.0),)


def test_splits_for_reads_the_latest_response_alone(store: Store, clock: Clock) -> None:
    """FMP's list at the newest fetch is the whole truth: a split it no longer lists, withdrawn
    or re-dated, is not read, though its observations stay on file."""
    kept = {"symbol": "ACME", "date": "2019-05-20", "numerator": 3, "denominator": 2}
    withdrawn = {"symbol": "ACME", "date": "2026-10-15", "numerator": 2, "denominator": 1}
    conn = store(**bodies(), splits=[withdrawn, kept])
    assert [r.date for r in splits_for(conn, "ACME")] == [date(2019, 5, 20), date(2026, 10, 15)]
    clock.now += timedelta(days=2)  # past the reuse window: the splits are fetched again
    store(company=False, splits=[kept])
    assert splits_for(conn, "ACME") == (SplitRow(date(2019, 5, 20), 3.0, 2.0),)


def test_splits_for_without_a_usable_response(store: Store, router: Router) -> None:
    router.fail.add("splits")
    assert splits_for(store(**bodies()), "ACME") == ()
