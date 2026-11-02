"""``peer_figures`` over a temporary database that ``fetch_company`` fills.

ACME's stored peers (``stock-peers.ACME.json``) name BOLT; ACME itself; ZZZZ, which no universe
lists; NEWT, admitted but Young Growth (the synthetic company at a -10% margin); and FIRB, the
synthetic company and Mature Growth, but listed and not admitted. BOLT is the fixtures' company,
two June fiscal years at a positive margin, so Mature Growth on the test deciles: the one peer kept.
"""

import json
import sqlite3
from dataclasses import replace
from datetime import date
from typing import Any

import pytest
from fixture_universe import company
from synthetic import YEARS, M, add_company, income_annual
from vendor_double import FIXTURES, Clients, Clock, Router

from fairband.engine.classifier import Deciles
from fairband.engine.roic import aggregate_roic
from fairband.policy import Policy
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh.fetch import fetch_company
from fairband.refresh.inputs_statements import statements_for
from fairband.refresh.peers import peer_figures
from fairband.store.companies import insert_companies, latest_company

TODAY = date(2026, 11, 1)
DECILES = Deciles((-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3), (0.0,) * 9, 1, 1, 1)

type Row = dict[str, Any]


@pytest.fixture
def tax() -> TaxTable:
    return load_tax_table()


@pytest.fixture
def conn_with_peers(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> sqlite3.Connection:
    """ACME and BOLT from their fixtures, NEWT and FIRB from the synthetic company; ACME, BOLT and
    NEWT admitted, FIRB listed but not admitted."""
    for symbol in ("NEWT", "FIRB"):
        for endpoint, body in company(symbol).items():
            router.symbol_bodies[(endpoint, symbol)] = body
    for symbol in ("ACME", "BOLT", "NEWT", "FIRB"):
        fetch_company(conn, clients.fmp, clients.gf, symbol, policy, clock(), clients.secrets)
    add_company(conn, symbols=("ACME", "BOLT", "NEWT"))
    listed = latest_company(conn, "NEWT")
    assert listed is not None
    excluded = "industry: Banks - Regional"
    firb = replace(listed, symbol="FIRB", eligible=False, exclusion_reason=excluded)
    insert_companies(conn, [firb])
    return conn


def bolt(name: str) -> list[Row]:
    """The rows of BOLT's fixture for ``name``, oldest first."""
    rows = json.loads((FIXTURES / "fmp" / f"{name}.BOLT.json").read_text(encoding="utf-8"))
    return sorted(rows, key=lambda row: row["date"])


def invested_capital(sheet: Row, filed: Row) -> float:
    """method.md 4.4 on a BOLT balance sheet and its as-reported tags: BOLT's goodwill and
    intangibles are vendor zeros, so nil, and the lease lines are the tags'."""
    operating_assets = (
        sheet["totalCurrentAssets"]
        - sheet["cashAndCashEquivalents"]
        - sheet["shortTermInvestments"]
    )
    operating_liabilities = (
        sheet["totalCurrentLiabilities"]
        - sheet["shortTermDebt"]
        - filed.get("operatingleaseliabilitycurrent", 0)
    )
    long_term = sheet["propertyPlantEquipmentNet"] + filed.get("operatingleaserightofuseasset", 0)
    return operating_assets - operating_liabilities + long_term


def test_peers_keep_only_mature_universe_companies(
    conn_with_peers: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """Not ACME itself, not ZZZZ outside the universe, not NEWT in Young Growth, not FIRB, which
    the universe did not admit."""
    figures = peer_figures(conn_with_peers, "ACME", DECILES, policy, tax, TODAY)
    assert [p.symbol for p in figures] == ["BOLT"]
    [peer] = figures
    income = bolt("income-statement.annual")
    sheets = bolt("balance-sheet-statement.annual")
    filed = [row["data"] for row in bolt("balance-sheet-statement-as-reported.annual")]
    opening, closing = (invested_capital(s, f) for s, f in zip(sheets, filed, strict=True))
    margin = sum(r["operatingIncome"] for r in income) / sum(r["revenue"] for r in income)
    assert peer.margin == pytest.approx(margin) and peer.margin_years == len(income) == 2
    assert peer.sales_to_capital == pytest.approx(income[-1]["revenue"] / ((opening + closing) / 2))
    assert peer.roic is None  # one ROIC year, fewer than the five an aggregate needs
    assert peer.market_cap == 4_000 * M  # the universe row's, not the quote's $10 bn


def test_no_peers_without_deciles_or_payload(
    conn_with_peers: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    assert peer_figures(conn_with_peers, "ACME", None, policy, tax, TODAY) == ()
    assert peer_figures(conn_with_peers, "NOPE", DECILES, policy, tax, TODAY) == ()


@pytest.mark.parametrize(
    ("gap", "years"),
    [(None, list(range(2016, 2026))), (2020, [y for y in range(2015, 2026) if y != 2020])],
    ids=["the-ten-newest", "past-a-year-without-revenue"],
)
def test_a_peers_margin_takes_its_last_ten_years_with_both(
    conn: sqlite3.Connection,
    clients: Clients,
    router: Router,
    clock: Clock,
    policy: Policy,
    tax: TaxTable,
    gap: int | None,
    years: list[int],
) -> None:
    """ACME's peer BOLT on the synthetic company's statements, eleven fiscal years kept (2015 to
    2025), 2015 at a margin of its own: the margin's years are the ten newest with a revenue and
    an operating income; the ROIC is the ten-year aggregate."""
    annual = income_annual(YEARS)
    for row in annual:
        if row["fiscalYear"] == "2015":
            row["operatingIncome"] = 0
        if row["fiscalYear"] == str(gap):
            row["revenue"] = None
    answers = {
        **company("BOLT"),
        "income-annual": json.dumps(annual).replace("ACME", "BOLT").encode(),
    }
    for endpoint, body in answers.items():
        router.symbol_bodies[(endpoint, "BOLT")] = body
    for symbol in ("ACME", "BOLT"):
        fetch_company(conn, clients.fmp, clients.gf, symbol, policy, clock(), clients.secrets)
    add_company(conn, symbols=("ACME", "BOLT"))

    [peer] = peer_figures(conn, "ACME", DECILES, policy, tax, TODAY)
    kept = [row for row in annual if int(row["fiscalYear"]) in years]
    margin = sum(r["operatingIncome"] for r in kept) / sum(r["revenue"] for r in kept)
    assert peer.margin == pytest.approx(margin) and peer.margin_years == 10
    roic = aggregate_roic(statements_for(conn, "BOLT", "US", tax, TODAY).capital_years)
    assert roic.years_used == 10 and roic.aggregate is not None
    assert peer.roic == pytest.approx(roic.aggregate)
    newest = roic.by_year[-1]
    assert newest.year == 2025
    assert peer.sales_to_capital == pytest.approx(annual[-1]["revenue"] / newest.average_capital)
