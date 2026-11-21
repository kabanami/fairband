"""``peer_figures`` over a temporary database that ``fetch_company`` fills.

ACME's stored peers (``stock-peers.ACME.json``) name BOLT; ACME itself; ZZZZ, which no universe
lists; NEWT, admitted but Young Growth (the synthetic company at a -10% margin); and FIRB, the
synthetic company and Mature Growth, but listed and not admitted. BOLT is the fixtures' company,
two June fiscal years at a positive margin, so Mature Growth on the test deciles: the one peer kept.

The industry fallback's tests add AXLE, COGS and GEAR, the synthetic company again, Mature Growth
with ten years of margin each, and list universes of their own (``universe``), every listing in
``add_company``'s industry unless a test names another.
"""

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from fixture_universe import company
from synthetic import YEARS, M, add_company, balance_annual, balance_as_reported, income_annual
from vendor_double import FIXTURES, Clients, Clock, Router

from fairband.engine.classifier import Deciles
from fairband.engine.revenue_growth import Peers, PeerSource
from fairband.engine.roic import aggregate_roic
from fairband.policy import Policy
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh.fetch import fetch_company
from fairband.refresh.inputs_statements import statements_for, stored_payload
from fairband.refresh.peers import peer_figures
from fairband.store.companies import insert_companies, latest_company

TODAY = date(2026, 11, 1)
DECILES = Deciles((-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3), (0.0,) * 9, 1, 1, 1)
INDUSTRY = "Specialty Industrial Machinery"  # every listing's in ``add_company``

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
        fetch_company(conn, clients.fmp, symbol, policy, clock(), clients.secrets)
    add_company(conn, symbols=("ACME", "BOLT", "NEWT"))
    listed = latest_company(conn, "NEWT")
    assert listed is not None
    excluded = "industry: Banks - Regional"
    firb = replace(listed, symbol="FIRB", eligible=False, exclusion_reason=excluded)
    insert_companies(conn, [firb])
    return conn


@pytest.fixture
def conn_with_industry(
    conn_with_peers: sqlite3.Connection,
    clients: Clients,
    router: Router,
    clock: Clock,
    policy: Policy,
) -> sqlite3.Connection:
    """``conn_with_peers`` with AXLE, COGS and GEAR fetched, each the synthetic company: Mature
    Growth on the test deciles with ten years of margin. No universe lists them yet."""
    for symbol in ("AXLE", "COGS", "GEAR"):
        for endpoint, body in company(symbol).items():
            router.symbol_bodies[(endpoint, symbol)] = body
        fetch_company(conn_with_peers, clients.fmp, symbol, policy, clock(), clients.secrets)
    return conn_with_peers


def universe(
    conn: sqlite3.Connection, caps: Mapping[str, int | None], **changes: dict[str, Any]
) -> None:
    """A new universe admitting each symbol of ``caps`` at its market cap in $ m (``None``
    unknown), in ``INDUSTRY``, its row ``add_company``'s with the ``changes`` named for it (another
    industry, not admitted)."""
    refresh_id = add_company(conn, symbols=())
    template = latest_company(conn, "ACME")
    assert template is not None
    admitted = {"industry": INDUSTRY, "eligible": True, "exclusion_reason": None}
    rows = [
        replace(
            template,
            symbol=symbol,
            refresh_id=refresh_id,
            name=f"{symbol.capitalize()} Corp",
            market_cap=None if cap is None else Decimal(cap * M),
            **(admitted | changes.get(symbol, {})),
        )
        for symbol, cap in caps.items()
    ]
    insert_companies(conn, rows)


def symbols(peers: Peers) -> list[str]:
    return [p.symbol for p in peers.figures]


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
    the universe did not admit. A policy that counts BOLT's two years and needs one peer keeps
    FMP's list."""
    enough = replace(policy, peer_margin_min_years=2, peer_min=1)
    peers = peer_figures(conn_with_peers, "ACME", DECILES, enough, tax, TODAY)
    assert peers.source == PeerSource("fmp", None, 1)
    assert symbols(peers) == ["BOLT"]
    [peer] = peers.figures
    income = bolt("income-statement.annual")
    sheets = bolt("balance-sheet-statement.annual")
    filed = [row["data"] for row in bolt("balance-sheet-statement-as-reported.annual")]
    opening, closing = (invested_capital(s, f) for s, f in zip(sheets, filed, strict=True))
    margin = sum(r["operatingIncome"] for r in income) / sum(r["revenue"] for r in income)
    assert peer.margin == pytest.approx(margin) and peer.margin_years == len(income) == 2
    assert peer.sales_to_capital == pytest.approx(income[-1]["revenue"] / ((opening + closing) / 2))
    assert peer.roic is None  # one ROIC year, fewer than the five an aggregate needs
    assert peer.market_cap == 4_000 * M  # the universe row's, not the quote's $10 bn


def test_no_peers_without_deciles(
    conn_with_peers: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    assert peer_figures(conn_with_peers, "ACME", None, policy, tax, TODAY) == Peers((), None)


def test_no_peers_without_a_payload_or_a_universe_row(
    conn_with_peers: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """NOPE has no stored peers and no universe row: FMP's list is empty, and no industry is
    there to fall back on."""
    peers = peer_figures(conn_with_peers, "NOPE", DECILES, policy, tax, TODAY)
    assert peers == Peers((), PeerSource("fmp", None, 0))


def test_a_peer_outside_the_latest_universe_is_dropped(
    conn_with_peers: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """A newer universe leaves BOLT out (its cap fell below the floor, say): its newest row is
    still the older universe's eligible one, but it is no peer until a universe lists it again."""
    conn = conn_with_peers
    enough = replace(policy, peer_margin_min_years=2, peer_min=1)  # BOLT alone would do
    add_company(conn, symbols=("ACME", "NEWT"))
    stale = latest_company(conn, "BOLT")
    assert stale is not None and stale.eligible
    assert peer_figures(conn, "ACME", DECILES, enough, tax, TODAY).figures == ()
    add_company(conn, symbols=("ACME", "BOLT", "NEWT"))
    peers = peer_figures(conn, "ACME", DECILES, enough, tax, TODAY)
    assert symbols(peers) == ["BOLT"] and peers.source == PeerSource("fmp", None, 1)


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
        fetch_company(conn, clients.fmp, symbol, policy, clock(), clients.secrets)
    add_company(conn, symbols=("ACME", "BOLT"))

    [peer] = peer_figures(conn, "ACME", DECILES, policy, tax, TODAY).figures
    kept = [row for row in annual if int(row["fiscalYear"]) in years]
    margin = sum(r["operatingIncome"] for r in kept) / sum(r["revenue"] for r in kept)
    assert peer.margin == pytest.approx(margin) and peer.margin_years == 10
    roic = aggregate_roic(statements_for(conn, "BOLT", "US", tax, TODAY).capital_years)
    assert roic.years_used == 10 and roic.aggregate is not None
    assert peer.roic == pytest.approx(roic.aggregate)
    newest = roic.by_year[-1]
    assert newest.year == 2025
    assert peer.sales_to_capital == pytest.approx(annual[-1]["revenue"] / newest.average_capital)


def test_a_peers_sales_to_capital_reads_one_fiscal_year(
    conn: sqlite3.Connection,
    clients: Clients,
    router: Router,
    clock: Clock,
    policy: Policy,
    tax: TaxTable,
) -> None:
    """BOLT on the synthetic company without its 2025 balance sheets: its newest fiscal year is
    2025 but its newest kept ROIC year 2024, so the ratio reads 2024's revenue, not 2025's."""
    held = YEARS[:-1]
    answers = {
        **company("BOLT"),
        "balance-annual": json.dumps(balance_annual(held)).replace("ACME", "BOLT").encode(),
        "balance-asreported-annual": json.dumps(balance_as_reported(held))
        .replace("ACME", "BOLT")
        .encode(),
    }
    for endpoint, body in answers.items():
        router.symbol_bodies[(endpoint, "BOLT")] = body
    for symbol in ("ACME", "BOLT"):
        fetch_company(conn, clients.fmp, symbol, policy, clock(), clients.secrets)
    add_company(conn, symbols=("ACME", "BOLT"))

    [peer] = peer_figures(conn, "ACME", DECILES, policy, tax, TODAY).figures
    newest = aggregate_roic(statements_for(conn, "BOLT", "US", tax, TODAY).capital_years).by_year[
        -1
    ]
    revenue = {int(row["fiscalYear"]): row["revenue"] for row in income_annual(YEARS)}
    assert newest.year == 2024 and max(revenue) == 2025
    assert peer.sales_to_capital == pytest.approx(revenue[2024] / newest.average_capital)
    assert peer.sales_to_capital != pytest.approx(revenue[2025] / newest.average_capital)


def test_the_industry_supplies_the_peers_when_fmp_leaves_too_few(
    conn_with_industry: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """FMP's list keeps BOLT, one peer that counts on a policy that counts its two years, fewer
    than three: the peers are the mature companies of ACME's industry by market cap, BOLT among
    them, read as any peer's; not ACME itself, not NEWT in Young Growth."""
    conn = conn_with_industry
    caps = {"ACME": 50_000, "BOLT": 1_000, "NEWT": 9_000, "AXLE": 3_000, "COGS": 6_000}
    universe(conn, caps | {"GEAR": 8_000})
    counting_bolt = replace(policy, peer_margin_min_years=2)
    peers = peer_figures(conn, "ACME", DECILES, counting_bolt, tax, TODAY)
    assert peers.source == PeerSource("industry", INDUSTRY, 1)
    assert symbols(peers) == ["GEAR", "COGS", "AXLE", "BOLT"]
    assert [p.market_cap for p in peers.figures] == [8_000 * M, 6_000 * M, 3_000 * M, 1_000 * M]
    gear = peers.figures[0]
    assert gear.margin == pytest.approx(0.20) and gear.margin_years == 10
    fmp = peer_figures(conn, "ACME", DECILES, replace(counting_bolt, peer_min=1), tax, TODAY)
    assert fmp.figures == (peers.figures[-1],)  # BOLT's figures, whichever list took it


def test_the_industry_takes_only_mature_companies_the_latest_universe_admits(
    conn_with_industry: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """Of ACME's industry, AXLE only: not NEWT in Young Growth, not FIRB, listed but not admitted,
    not GEAR, admitted by an older universe only; nor COGS of another industry. FMP's list leaves
    none (BOLT is not listed)."""
    conn = conn_with_industry
    universe(conn, {"ACME": 5_000, "GEAR": 8_000})
    universe(
        conn,
        {"ACME": 5_000, "NEWT": 9_000, "FIRB": 20_000, "COGS": 6_000, "AXLE": 3_000},
        FIRB={"eligible": False, "exclusion_reason": "industry: Banks - Regional"},
        COGS={"industry": "Tools & Accessories"},
    )
    peers = peer_figures(conn, "ACME", DECILES, policy, tax, TODAY)
    assert peers.source == PeerSource("industry", INDUSTRY, 0)
    assert symbols(peers) == ["AXLE"]


def test_the_industry_takes_the_largest_by_market_cap(
    conn_with_industry: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """At most ``industry_peer_max``, the largest first; a tie in symbol order; a company without
    a market cap last."""
    conn = conn_with_industry
    universe(conn, {"ACME": 5_000, "GEAR": None, "BOLT": 3_000, "AXLE": 3_000, "COGS": 6_000})
    two = replace(policy, industry_peer_max=2)
    assert symbols(peer_figures(conn, "ACME", DECILES, two, tax, TODAY)) == ["COGS", "AXLE"]
    every = peer_figures(conn, "ACME", DECILES, policy, tax, TODAY)
    assert symbols(every) == ["COGS", "AXLE", "BOLT", "GEAR"]
    assert every.figures[-1].market_cap is None


def test_no_fallback_when_fmp_leaves_enough(
    conn_with_industry: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """BOLT counts on two years: with one peer the minimum, FMP's list stands and no industry
    company joins it; with two the minimum, the industry's companies replace it."""
    conn = conn_with_industry
    universe(conn, {"ACME": 5_000, "BOLT": 1_000, "AXLE": 3_000, "COGS": 6_000, "GEAR": 8_000})
    at = replace(policy, peer_margin_min_years=2, peer_min=1)
    peers = peer_figures(conn, "ACME", DECILES, at, tax, TODAY)
    assert peers.source == PeerSource("fmp", None, 1) and symbols(peers) == ["BOLT"]
    below = peer_figures(conn, "ACME", DECILES, replace(at, peer_min=2), tax, TODAY)
    assert below.source == PeerSource("industry", INDUSTRY, 1)
    assert symbols(below) == ["GEAR", "COGS", "AXLE", "BOLT"]


def test_no_fallback_without_an_industry_or_a_universe_row(
    conn_with_industry: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """ACME's row carries no industry, and GEAR, whose stored peers name BOLT, has no universe
    row: each keeps FMP's list, though the industry has mature companies."""
    conn = conn_with_industry
    universe(conn, {"ACME": 5_000, "BOLT": 1_000, "AXLE": 3_000}, ACME={"industry": None})
    assert latest_company(conn, "GEAR") is None
    for symbol in ("ACME", "GEAR"):
        peers = peer_figures(conn, symbol, DECILES, policy, tax, TODAY)
        assert peers.source == PeerSource("fmp", None, 0), symbol
        assert symbols(peers) == ["BOLT"], symbol


def test_without_a_stored_payload_the_industry_applies(
    conn_with_industry: sqlite3.Connection, policy: Policy, tax: TaxTable
) -> None:
    """NOPE is admitted but has no stored peers: FMP's list is empty and the industry supplies
    the peers."""
    conn = conn_with_industry
    universe(conn, {"NOPE": 2_500, "AXLE": 3_000, "COGS": 6_000, "GEAR": 8_000})
    assert stored_payload(conn, "peers", "NOPE") is None
    peers = peer_figures(conn, "NOPE", DECILES, policy, tax, TODAY)
    assert peers.source == PeerSource("industry", INDUSTRY, 0)
    assert symbols(peers) == ["GEAR", "COGS", "AXLE"]


def test_a_peers_answer_that_is_the_empty_list_falls_back_to_the_industry(
    conn_with_industry: sqlite3.Connection,
    clients: Clients,
    router: Router,
    clock: Clock,
    policy: Policy,
    tax: TaxTable,
) -> None:
    """LONE's stored peers answer is exactly the empty list, a usable answer naming no peer: FMP's
    list leaves none and the industry supplies the peers."""
    conn = conn_with_industry
    for endpoint, body in company("LONE").items():
        router.symbol_bodies[(endpoint, "LONE")] = body
    router.symbol_bodies[("peers", "LONE")] = b"[]"
    fetch_company(conn, clients.fmp, "LONE", policy, clock(), clients.secrets)
    universe(conn, {"LONE": 2_500, "AXLE": 3_000, "COGS": 6_000, "GEAR": 8_000})
    assert stored_payload(conn, "peers", "LONE") == []
    peers = peer_figures(conn, "LONE", DECILES, policy, tax, TODAY)
    assert peers.source == PeerSource("industry", INDUSTRY, 0)
    assert symbols(peers) == ["GEAR", "COGS", "AXLE"]
