"""Assembly: a company's mature peers and the three figures the revenue-growth route reads of each.

The peers are the symbols of the latest usable ``stock-peers`` payload stored for the company, in
its order, the company itself and repeats dropped (``peer_symbols``). As growth routes spec 5.5
words it, the peers kept are those in the latest universe that the classifier puts in Mature Growth
or Mature Stable: a peer counts when the latest universe lists it, the admitted companies of the
newest refresh that admitted any (``latest_companies``, read once per call), and its stored fiscal
years classify as one of the two on the given deciles (on the spot, so the order of companies
within a refresh does not matter). A peer the latest universe does not list (never listed, not
admitted, or admitted only by an older universe, its newest row eligible but stale), without
statements, unclassified or in another phase is dropped. Without deciles, a stored payload or a
peer, the company has none.

Each kept peer's figures come from its stored statements:

- its margin: the ten-year aggregate operating margin, Σ operating income ÷ Σ revenue over its last
  ten fiscal years with both and a positive revenue, and the count of those years; ``None`` with
  no such year (the route sets the fewest years a margin needs);
- its sales-to-capital: the revenue of its newest kept ROIC year (method.md 4.5) ÷ that year's
  average invested capital, both of one fiscal year; ``None`` without a kept year, without a
  revenue for that year, or with a capital at or below zero;
- its ROIC: the ten-year aggregate (method.md 4.5), ``None`` when unavailable;

and its market cap is its latest universe row's. Invested capital and NOPAT are the company's own rules
(``statements_for``), taxed at the peer's country, found as the company's is (``country_for``).
"""

import sqlite3
from collections.abc import Sequence
from datetime import date

from fairband.engine.classifier import Deciles, Series, classify
from fairband.engine.revenue_growth import PeerFigures
from fairband.engine.roic import RoicYear, aggregate_roic
from fairband.engine.types import Phase
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs_statements import (
    country_for,
    series_for,
    statements_for,
    stored_payload,
)
from fairband.store.companies import CompanyRow, latest_companies
from fairband.vendors.normalize_fmp import peer_symbols

_MATURE: frozenset[Phase | None] = frozenset({"Mature Growth", "Mature Stable"})
_MARGIN_YEARS = 10  # the ten-year aggregate margin (growth routes spec 5.5)


def peer_figures(
    conn: sqlite3.Connection,
    symbol: str,
    deciles: Deciles | None,
    policy: Policy,
    tax: TaxTable,
    today: date,
) -> tuple[PeerFigures, ...]:
    """``symbol``'s mature peers with their figures, in the stored payload's order. No rule here
    reads the policy yet."""
    if deciles is None:
        return ()
    peers = peer_symbols(stored_payload(conn, "peers", symbol), symbol)
    universe = {company.symbol: company for company in latest_companies(conn)} if peers else {}
    kept = []
    for peer in peers:
        company = universe.get(peer)
        if company is None:
            continue
        series = series_for(conn, peer)
        if classify(series, deciles).phase in _MATURE:
            kept.append(_figures(conn, company, series, tax, today))
    return tuple(kept)


def _figures(
    conn: sqlite3.Connection, company: CompanyRow, series: Series, tax: TaxTable, today: date
) -> PeerFigures:
    country, _ = country_for(conn, company.symbol, company)
    roic = aggregate_roic(statements_for(conn, company.symbol, country, tax, today).capital_years)
    margin, years = _margin(series)
    return PeerFigures(
        symbol=company.symbol,
        market_cap=None if company.market_cap is None else float(company.market_cap),
        margin=margin,
        margin_years=years,
        sales_to_capital=_sales_to_capital(series, roic.by_year),
        roic=roic.aggregate,
    )


def _margin(series: Series) -> tuple[float | None, int]:
    """Σ operating income ÷ Σ revenue over the last ten years with both and a positive revenue,
    and the count of those years."""
    held = [
        (income, revenue)
        for fy in series
        if (income := fy.operating_income) is not None
        and (revenue := fy.revenue) is not None
        and revenue > 0
    ][-_MARGIN_YEARS:]
    if not held:
        return None, 0
    return sum(i for i, _ in held) / sum(r for _, r in held), len(held)


def _sales_to_capital(series: Series, kept: Sequence[RoicYear]) -> float | None:
    """The newest kept ROIC year's revenue over its average capital, both of that fiscal year."""
    if not kept:
        return None
    newest = kept[-1]
    revenue = next((fy.revenue for fy in series if fy.year == newest.year), None)
    if revenue is None or newest.average_capital <= 0:
        return None
    return revenue / newest.average_capital
