"""The report tests' fixtures: the packaged policy and a migrated database holding the refresh
tests' synthetic company, ACME (``refresh/synthetic.py``): twelve fiscal years of statements, 2014
to 2025, of which assembly keeps the last eleven, and five quarters, stored as a fetch stores
them, and its universe row. The refresh's ``env_valued`` fixture belongs to the refresh tests'
directory; storing the same payloads through the same normalizers gives the same statements
without a refresh.

``snapshots`` adds the web tests' AAPL (the Mature Growth golden renamed: a price of $150, 1 bn
diluted shares, a Wide moat) and AAL (Young Growth, refused for its target margin), valued as the
web tests value them, each with a snapshot under a newer full refresh whose universe lists ACME,
AAPL and AAL; AAPL also gets ACME's synthetic statements (revenue $2,100 m in fiscal 2025, $2,000 m
in 2024), two years of annual consensus, three closes and a peers list naming ACME, and the store
the universe deciles, under which ACME is a mature peer."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest
from refresh.synthetic import NOW, add_company, bodies
from support.engine_companies import mature_growth_inputs, universe_deciles, young_growth_inputs
from support.payloads import store_payloads
from support.web import TODAY

from fairband.engine.route import value_company
from fairband.policy import Policy, load_policy
from fairband.store.db import connect, migrate
from fairband.store.refreshes import save_deciles
from fairband.store.snapshots import insert_snapshot

ANNUAL = [  # FMP's order: the furthest year first
    {
        "symbol": "AAPL",
        "date": "2027-12-31",
        "revenueAvg": 2_420_000_000,
        "netIncomeAvg": 363_000_000,
        "epsAvg": 3.63,
        "numAnalystsEps": 8,
        "numAnalystsRevenue": 10,
    },
    {
        "symbol": "AAPL",
        "date": "2026-12-31",
        "revenueAvg": 2_200_000_000,
        "netIncomeAvg": 330_000_000,
        "epsAvg": 3.3,
        "numAnalystsEps": 9,
        "numAnalystsRevenue": 12,
    },
]
CLOSES = [  # newest first, as FMP sends them
    {"symbol": "AAPL", "date": "2026-10-30", "close": 150.0},
    {"symbol": "AAPL", "date": "2025-11-03", "close": 190.0},
    {"symbol": "AAPL", "date": "2024-06-28", "close": 180.0},
]


@pytest.fixture
def policy() -> Policy:
    return load_policy()


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(connect(tmp_path / "f.db")) as conn:
        migrate(conn)
        statements = {e: p for e, p in bodies().items() if e != "earnings"}
        store_payloads(conn, "ACME", statements, NOW)
        add_company(conn)
        yield conn


@pytest.fixture
def snapshots(conn: sqlite3.Connection, policy: Policy) -> dict[str, int]:
    """AAPL's and AAL's snapshot ids (module docstring)."""
    deciles = universe_deciles()
    refresh_id = add_company(conn, symbols=("ACME", "AAPL", "AAL"))
    valued = value_company(replace(mature_growth_inputs(), symbol="AAPL"), deciles, policy, TODAY)
    no_peers = replace(young_growth_inputs(), symbol="AAL", peers=())
    refused = value_company(no_peers, deciles, policy, TODAY)
    assert valued.value is not None and refused.value is None
    ids = {
        r.symbol: insert_snapshot(conn, r, refresh_id, clock=lambda: NOW) for r in (valued, refused)
    }
    statements = {e: p for e, p in bodies().items() if e != "earnings"}
    reads = {"estimates-annual": ANNUAL, "price-history": CLOSES, "peers": [{"symbol": "ACME"}]}
    store_payloads(conn, "AAPL", statements | reads, NOW)
    save_deciles(conn, refresh_id, deciles, NOW)
    return ids
