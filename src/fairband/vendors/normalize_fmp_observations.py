"""FMP estimates, earnings, quotes, profiles, splits, closes, exchange rates, screener rows and
peers to store rows.

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
  The screener carries no ``isAdr``, so the ADR flag is read from here. The country, the
  company brief and the logo's address are not observations: ``profile_country``,
  ``profile_brief`` and ``profile_logo`` read them from the stored payload.
- ``split``: ``numerator`` and ``denominator`` (unit ``shares``) for each ``splits`` row with a
  parseable ``date`` and two numbers above zero; ``period`` and ``as_of`` the split date. The two
  stay apart so a sentence can say 2-for-1 or 1-for-10; ``inputs_splits.splits_for`` reads them
  back as one split each and divides them for the ratio.
- ``fx-quote``: a forex pair's quote (``USDSEK``), stored under the pair as the symbol: one
  ``price`` (unit ``None``: units of the currency per USD) from the row for the pair, when that
  price is a number above zero; ``period`` and ``as_of`` the UTC date of the row's ``timestamp``
  (else the observed date), so each quote is a dated close ``rates.rates_for`` merges with the
  pair's history.

The peers are not observations either: ``peer_symbols`` reads the ``stock-peers`` symbols from the
stored payload, in the exchange form. Nor are a stock's closes or a pair's: ``price_closes`` and
``fx_closes`` read them from the stored payload, ``price_closes`` from the rows ``close_rows``
finds, which the company page's prices read too.

A row without a parseable ``date`` is skipped and records nothing; nothing here raises on vendor
data.
"""

import re
from collections.abc import Iterator
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

LOGO_HOST = "images.financialmodelingprep.com"  # FMP's image host, which answers without a key
_LOGO = re.compile(rf"https://{re.escape(LOGO_HOST)}/[A-Za-z0-9._/-]+")

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


def fx_quote_observations(
    payload: Any, pair: str, response_id: int, observed_at: datetime, entered_at: datetime
) -> list[ObservationRow]:
    """The pair's ``price`` from the payload row for ``pair`` (a batch holds several), keyed by
    the quote's date; none when no row matches or its price is not a number above zero."""
    row = next((r for r in objects(payload) if r.get("symbol") == pair), None)
    price = None if row is None else number(row.get("price"))
    if row is None or price is None or price <= 0:
        return []
    day = _timestamp_date(row.get("timestamp")) or observed_at.date()
    source = Source(pair, response_id, observed_at, entered_at)
    return [source.observation("fx-quote", day, "price", price, None, day)]


def profile_observations(
    payload: Any, symbol: str, response_id: int, observed_at: datetime, entered_at: datetime
) -> list[ObservationRow]:
    """``is_adr`` and ``market_cap`` from the profile object (the first one of a list); none when
    the payload holds no object."""
    row = _profile(payload)
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


def profile_country(payload: Any) -> str | None:
    """The profile object's ``country``, the headquarters as FMP gives it (an ISO 3166-1 alpha-2
    code), stripped; ``None`` without a non-empty string. Assembly reads it from the stored
    payload, as it reads the closes."""
    row = _profile(payload)
    return None if row is None else text(row.get("country"))


def profile_brief(payload: Any) -> str | None:
    """The company brief (B-149): the profile object's ``description``, FMP's paragraph on what
    the company does, stripped; ``None`` without a non-empty string. The detail read hands it to
    the drawer and the MCP ``company`` tool from the stored payload."""
    row = _profile(payload)
    return None if row is None else text(row.get("description"))


def profile_logo(payload: Any) -> str | None:
    """The company logo's address (B-203): the profile object's ``image`` where it is an https
    address on FMP's image host, a path of letters, digits, dots, dashes, underscores and slashes
    and nothing else, so no user, port or query; ``None`` otherwise, and where ``defaultImage`` is
    true: FMP holds no logo there and sends a placeholder. The logo read fetches the file from it,
    with no key (``vendors.logos``)."""
    row = _profile(payload)
    if row is None or row.get("defaultImage") is True:
        return None
    image = row.get("image")
    return image if isinstance(image, str) and _LOGO.fullmatch(image) else None


def _profile(payload: Any) -> dict[str, Any] | None:
    """The profile object: a bare object, or the first object of a list."""
    return payload if isinstance(payload, dict) else next(objects(payload), None)


def split_observations(
    payload: Any, symbol: str, response_id: int, observed_at: datetime, entered_at: datetime
) -> list[ObservationRow]:
    """The numerator and the denominator of each split, keyed by the split date; a row needs a
    date and two numbers above zero, and a payload that is not a list gives none."""
    source = Source(symbol, response_id, observed_at, entered_at)
    out: list[ObservationRow] = []
    for row, when in dated(payload):
        numerator, denominator = number(row.get("numerator")), number(row.get("denominator"))
        if numerator is None or denominator is None or numerator <= 0 or denominator <= 0:
            continue
        out.append(source.observation("split", when, "numerator", numerator, SHARES, when))
        out.append(source.observation("split", when, "denominator", denominator, SHARES, when))
    return out


def close_rows(payload: Any) -> Iterator[tuple[dict[str, Any], date, float]]:
    """Each row of a price history with a date and a numeric close (a JSON number or a numeric
    text), with that date and close, in the payload's order. Reads the stable route's flat list
    of rows, or the legacy ``{"historical": [...]}`` object. ``price_closes`` reads the engine's
    closes from it, and the company page's prices their rows (``page_fmp.prices``)."""
    if isinstance(payload, dict):
        payload = payload.get("historical")
    for row, when in dated(payload):
        close = number(row.get("close"))
        if close is not None:
            yield row, when, float(close)


def price_closes(payload: Any) -> list[tuple[date, float]]:
    """``(date, close)`` per row with a date and a numeric close (``close_rows``), oldest
    first."""
    return sorted((when, close) for _, when, close in close_rows(payload))


def fx_closes(payload: Any) -> list[tuple[date, float]]:
    """``(date, rate)`` per row of a forex pair's ``historical-price-eod/light`` history with a
    date and a ``price`` above zero, oldest first; the rate is in units of the currency per
    USD."""
    closes = []
    for row, when in dated(payload):
        rate = number(row.get("price"))
        if rate is not None and rate > 0:
            closes.append((when, float(rate)))
    return sorted(closes)


def screener_rows(payload: Any) -> list[ScreenerRow]:
    """One row per screener entry with a symbol, in payload order. A share-class symbol comes back
    to the exchange form (``BRK-B`` → ``BRK.B``); any other dash stays (``ACME-PA``)."""
    out: list[ScreenerRow] = []
    for row in objects(payload):
        symbol = text(row.get("symbol"))
        if symbol is None:
            continue
        out.append(
            ScreenerRow(
                symbol=_exchange_form(symbol),
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


def peer_symbols(payload: Any, own: str) -> list[str]:
    """The ``symbol`` of each object of a ``stock-peers`` payload, in payload order and the
    exchange form (as ``screener_rows`` gives it), ``own`` and repeats dropped; empty when the
    payload is not a list of objects."""
    out: list[str] = []
    for row in objects(payload):
        symbol = text(row.get("symbol"))
        if symbol is None:
            continue
        symbol = _exchange_form(symbol)
        if symbol != own and symbol not in out:
            out.append(symbol)
    return out


def _exchange_form(symbol: str) -> str:
    """An FMP share-class symbol in the exchange form (``BRK-B`` → ``BRK.B``); any other dash
    stays (``ACME-PA``)."""
    return symbol.replace("-", ".") if _SHARE_CLASS.fullmatch(symbol) else symbol


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
