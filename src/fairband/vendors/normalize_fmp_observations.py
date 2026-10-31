"""FMP estimates, earnings, quotes, profiles, closes and screener rows to store rows.

Observations carry ``unit`` ``currency``, ``per-share``, ``shares``, ``count``, or ``None`` for a
label or a date:

- ``estimate-annual`` and ``estimate-quarter``: every row returned, ``period`` its ``date``,
  ``as_of`` the observed date; picking the NTM quarters by period is the engine's job.
  ``eps_avg``, ``revenue_avg``, ``net_income_avg``, ``analysts_eps`` and ``analysts_revenue`` read
  ``epsAvg``, ``revenueAvg``, ``netIncomeAvg``, ``numAnalystsEps`` and ``numAnalystsRevenue``.
  FMP has no net-income analyst count (the documented response has only the two above), so
  ``analysts_net_income`` reads ``numAnalystsEps`` (controller ruling, Task 9). The documented
  rows carry no fiscal year or period either: ``fiscal_year`` (``fiscalYear``) and
  ``fiscal_period`` (the quarter number of a ``fiscalPeriod`` such as ``Q2``) have no value unless
  a row supplies them, and the fiscal year of an estimate comes from the statements' calendar.
- ``street-actual``: ``eps_actual`` for each ``earnings`` row with a non-null ``epsActual``;
  ``period`` the fiscal quarter end ``periodEnding`` (else the report ``date``), ``as_of`` the
  report date.
- ``earnings-date``: one ``next_date``, the earliest ``date`` on or after ``today`` whose
  ``epsActual`` is null, if any; ``period`` its ``periodEnding`` (else ``None``), ``as_of`` the
  observed date. The date is stored as the decimal ``YYYYMMDD``; ``value_as_date`` reads it back.
- ``quote``: ``price``, ``market_cap``, ``shares_outstanding``, ``year_high`` and ``year_low``
  from the row for the symbol; ``period`` ``None``, ``as_of`` the UTC date of the row's
  ``timestamp`` (else the observed date). The documented stable quote has no
  ``sharesOutstanding``, so ``shares_outstanding`` has no value unless a row supplies it.
- ``profile``: ``is_adr`` (1 or 0 from the boolean ``isAdr``; no value when the flag is absent or
  not a boolean; unit ``None``) and ``market_cap`` (``marketCap``) from the profile object, which
  arrives as a one-item list or a bare object; ``period`` ``None``, ``as_of`` the observed date.
  The screener carries no ``isAdr``, so the ADR flag is read from here.

A row without a parseable ``date`` is skipped and records nothing; nothing here raises on vendor
data.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from fairband.store.observations import ObservationRow
from fairband.vendors._fmp_parse import (
    COUNT,
    MONEY,
    PER_SHARE,
    SHARES,
    Source,
    dated,
    number,
    objects,
    parse_date,
    text,
)
from fairband.vendors.fmp import to_fmp_symbol

_ESTIMATES = (  # (field, FMP field, unit)
    ("eps_avg", "epsAvg", PER_SHARE),
    ("revenue_avg", "revenueAvg", MONEY),
    ("net_income_avg", "netIncomeAvg", MONEY),
    ("analysts_eps", "numAnalystsEps", COUNT),
    ("analysts_revenue", "numAnalystsRevenue", COUNT),
    ("analysts_net_income", "numAnalystsEps", COUNT),
    ("fiscal_year", "fiscalYear", None),
)
_QUOTE = (
    ("price", "price", MONEY),
    ("market_cap", "marketCap", MONEY),
    ("shares_outstanding", "sharesOutstanding", SHARES),
    ("year_high", "yearHigh", MONEY),
    ("year_low", "yearLow", MONEY),
)
_QUARTER_LABEL = re.compile(r"Q([1-4])")
_SHARE_CLASS = re.compile(r"[A-Z]+-[A-Z]")


@dataclass(frozen=True)
class ScreenerRow:
    """One ``company-screener`` row; the universe build maps it to a ``CompanyRow``."""

    symbol: str
    name: str | None
    exchange: str | None
    sector: str | None
    industry: str | None
    country: str | None
    currency: str | None
    market_cap: Decimal | None
    is_etf: bool
    is_fund: bool
    is_actively_trading: bool
    is_adr: bool


def estimate_observations(
    payload: Any,
    symbol: str,
    period: Literal["annual", "quarter"],
    response_id: int,
    observed_at: datetime,
    entered_at: datetime,
) -> list[ObservationRow]:
    """The consensus per row returned, keyed by the row's ``date``; no row is selected here."""
    source = Source(symbol, response_id, observed_at, entered_at)
    dataset = f"estimate-{period}"
    as_of = observed_at.date()
    out: list[ObservationRow] = []
    for row, when in dated(payload):
        for name, key, unit in _ESTIMATES:
            out.append(source.observation(dataset, when, name, number(row.get(key)), unit, as_of))
        quarter = _quarter_number(row.get("fiscalPeriod"))
        out.append(source.observation(dataset, when, "fiscal_period", quarter, None, as_of))
    return out


def earnings_observations(
    payload: Any,
    symbol: str,
    response_id: int,
    observed_at: datetime,
    entered_at: datetime,
    today: date,
) -> list[ObservationRow]:
    """The street actual per reported quarter, and the next earnings date if one is scheduled."""
    source = Source(symbol, response_id, observed_at, entered_at)
    out: list[ObservationRow] = []
    upcoming: list[tuple[date, date | None]] = []
    for row, reported in dated(payload):
        quarter_end = parse_date(row.get("periodEnding"))
        if row.get("epsActual") is not None:
            eps = number(row["epsActual"])
            period = quarter_end or reported
            out.append(
                source.observation("street-actual", period, "eps_actual", eps, PER_SHARE, reported)
            )
        elif reported >= today:
            upcoming.append((reported, quarter_end))
    if upcoming:
        when, quarter_end = min(upcoming, key=lambda pair: pair[0])
        out.append(
            source.observation(
                "earnings-date",
                quarter_end,
                "next_date",
                _date_value(when),
                None,
                observed_at.date(),
            )
        )
    return out


def quote_observations(
    payload: Any, symbol: str, response_id: int, observed_at: datetime, entered_at: datetime
) -> list[ObservationRow]:
    """The quote fields from the payload row for ``symbol`` (a batch holds several); none when no
    row matches."""
    forms = (symbol, to_fmp_symbol(symbol))
    row = next((r for r in objects(payload) if r.get("symbol") in forms), None)
    if row is None:
        return []
    source = Source(symbol, response_id, observed_at, entered_at)
    as_of = _timestamp_date(row.get("timestamp")) or observed_at.date()
    return [
        source.observation("quote", None, name, number(row.get(key)), unit, as_of)
        for name, key, unit in _QUOTE
    ]


def profile_observations(
    payload: Any, symbol: str, response_id: int, observed_at: datetime, entered_at: datetime
) -> list[ObservationRow]:
    """``is_adr`` and ``market_cap`` from the profile object (the first one of a list); none when
    the payload holds no object."""
    row = payload if isinstance(payload, dict) else next(objects(payload), None)
    if row is None:
        return []
    flag = row.get("isAdr")
    is_adr = Decimal(int(flag)) if isinstance(flag, bool) else None
    source = Source(symbol, response_id, observed_at, entered_at)
    as_of = observed_at.date()
    market_cap = number(row.get("marketCap"))
    return [
        source.observation("profile", None, "is_adr", is_adr, None, as_of),
        source.observation("profile", None, "market_cap", market_cap, MONEY, as_of),
    ]


def price_closes(payload: Any) -> list[tuple[date, float]]:
    """``(date, close)`` per row with a date and a numeric close, oldest first. Reads the stable
    route's flat list of rows, or the legacy ``{"historical": [...]}`` object."""
    if isinstance(payload, dict):
        payload = payload.get("historical")
    closes = []
    for row, when in dated(payload):
        close = number(row.get("close"))
        if close is not None:
            closes.append((when, float(close)))
    return sorted(closes)


def screener_rows(payload: Any) -> list[ScreenerRow]:
    """One row per screener entry with a symbol, in payload order. A share-class symbol comes back
    to the exchange form (``BRK-B`` → ``BRK.B``); any other dash stays (``ACME-PA``)."""
    out: list[ScreenerRow] = []
    for row in objects(payload):
        symbol = text(row.get("symbol"))
        if symbol is None:
            continue
        if _SHARE_CLASS.fullmatch(symbol):
            symbol = symbol.replace("-", ".")
        out.append(
            ScreenerRow(
                symbol=symbol,
                name=text(row.get("companyName")),
                # ``exchange`` is the full name ("NASDAQ Global Select"); the policy lists the
                # short name.
                exchange=text(row.get("exchangeShortName")) or text(row.get("exchange")),
                sector=text(row.get("sector")),
                industry=text(row.get("industry")),
                country=text(row.get("country")),
                currency=text(row.get("currency")),
                market_cap=number(row.get("marketCap")),
                is_etf=row.get("isEtf") is True,
                is_fund=row.get("isFund") is True,
                is_actively_trading=row.get("isActivelyTrading") is True,
                is_adr=row.get("isAdr") is True,
            )
        )
    return out


def value_as_date(value: Decimal) -> date:
    """The date a ``next_date`` observation stores as the decimal ``YYYYMMDD``."""
    n = int(value)
    return date(n // 10000, n // 100 % 100, n % 100)


def _date_value(when: date) -> Decimal:
    return Decimal(when.year * 10000 + when.month * 100 + when.day)


def _quarter_number(raw: Any) -> Decimal | None:
    match = _QUARTER_LABEL.fullmatch(raw) if isinstance(raw, str) else None
    return Decimal(match.group(1)) if match else None


def _timestamp_date(raw: Any) -> date | None:
    seconds = number(raw)
    if seconds is None:
        return None
    try:
        return datetime.fromtimestamp(float(seconds), UTC).date()
    except (OverflowError, OSError, ValueError):
        return None
