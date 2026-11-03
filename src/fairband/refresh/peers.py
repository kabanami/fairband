"""Assembly: a company's mature peers and the three figures the revenue-growth route reads of each.

The peers are the symbols of the latest usable ``stock-peers`` payload stored for the company, in
its order, the company itself and repeats dropped (``peer_symbols``). As growth routes spec 5.5
words it, the peers kept are those in the latest universe that the classifier puts in Mature Growth
or Mature Stable: a peer counts when the latest universe lists it, the admitted companies of the
newest refresh that admitted any (``latest_companies``, read once per call), and its stored fiscal
years classify as one of the two on the given deciles (on the spot, so the order of companies
within a refresh does not matter). A peer the latest universe does not list (never listed, not
admitted, or admitted only by an older universe, its newest row eligible but stale), without
statements, unclassified or in another phase is dropped. Without deciles the company has none.

The industry fallback (growth routes spec 5.5): when FMP's kept peers leave fewer than
``peer_min`` that count for the target margin (``margin_peers``), the peers are instead the
largest ``industry_peer_max`` companies of the latest universe whose row carries the company's own
industry, the company itself excluded, that classify on the spot as Mature Growth or Mature Stable;
the largest by market cap first, a company without one last, ties in symbol order. FMP's kept
peers are dropped, not merged. The industry is the company's latest universe row's
(``latest_company``); without that row or an industry on it there is no fallback. Without a stored
payload FMP's list is empty and the fallback applies. ``Peers.source`` names the list taken and
FMP's count.

Each peer's figures, FMP's or the industry's, come from its stored statements:

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
from fairband.engine.revenue_growth import PeerFigures, Peers, PeerSource, margin_peers
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
from fairband.store.companies import CompanyRow, latest_companies, latest_company
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
) -> Peers:
    """``symbol``'s mature peers with their figures and their source: FMP's, in the stored
    payload's order, unless they leave fewer than ``peer_min`` that count for the target margin;
    then the industry's."""
    if deciles is None:
        return Peers((), None)
    universe = latest_companies(conn)
    by_symbol = {company.symbol: company for company in universe}
    kept = []
    for peer in peer_symbols(stored_payload(conn, "peers", symbol), symbol):
        company = by_symbol.get(peer)
        if company is None:
            continue
        series = series_for(conn, peer)
        if classify(series, deciles).phase in _MATURE:
            kept.append(_figures(conn, company, series, tax, today))
    counted = len(margin_peers(kept, policy))
    fmp = Peers(tuple(kept), PeerSource("fmp", None, counted))
    if counted >= policy.peer_min:
        return fmp
    own = latest_company(conn, symbol)
    if own is None or own.industry is None:
        return fmp
    candidates = sorted(
        (c for c in universe if c.industry == own.industry and c.symbol != symbol), key=_by_size
    )
    taken: list[PeerFigures] = []
    for company in candidates:  # classified in size order, until enough are taken
        if len(taken) == policy.industry_peer_max:
            break
        series = series_for(conn, company.symbol)
        if classify(series, deciles).phase in _MATURE:
            taken.append(_figures(conn, company, series, tax, today))
    return Peers(tuple(taken), PeerSource("industry", own.industry, counted))


def _by_size(company: CompanyRow) -> tuple[bool, float, str]:
    """The largest market cap first, a company without one last, ties in symbol order."""
    cap = company.market_cap
    return (cap is None, 0.0 if cap is None else -float(cap), company.symbol)


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
