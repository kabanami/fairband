"""Assembly: one company's stored facts and observations to the engine's ``CompanyInputs``.

The statement side (``series_for``, the capital years, the tax rate, the trailing figures and the
share count) is ``inputs_statements``; its docstring states those rules. ``build_inputs`` adds:

- the consensus: one ``QuarterEstimate`` per ``estimate-quarter`` period and one ``AnnualEstimate``
  per ``estimate-annual`` period, every row returned; the fiscal year is FMP's when stored, else
  derived from the company's fiscal-year end (``FiscalCalendar``), and so is the quarter label;
- the street's trailing EPS: the sum of the four ``street-actual`` values whose periods are exactly
  the four trailing quarter ends; ``None`` when one is missing or the trailing figures are a fiscal
  year, which leaves the SBC basis unknown (``mech/1.2``);
- the price and its date from the ``quote``; the market cap from the quote, else the profile, else
  the universe row; ``is_adr`` from the profile, else the universe row; the country is the
  universe row's;
- the currency: the newest annual income statement's, else the universe row's, else ``"unknown"``
  flagged ``currency-unknown``. The route reads every currency but USD as a foreign filer, so an
  unknown one gets the foreign-filer refusal, which is the honest outcome;
- the GuruFocus moat score and EPS, the next earnings date (``None`` when before ``today``) and the
  closes of the latest price-history payload (none when it is absent or does not parse).

``provenance`` holds an entry under each key the route cites (``route`` module docstring) whose
input the store supplied; an input it did not supply has none and cites "unknown". The source names
the vendor and its route (``"FMP quote"``, ``"GuruFocus summary"``) or the tax table; ``as_of`` is
the row's date and ``observed_at`` and ``entered_at`` the row's, the newest of several rows.
Nothing here raises on missing data: a missing piece is ``None``, a flag or a refusal. An unknown
dataset name is a programming error and raises ``ValueError``.
"""

import json
import sqlite3
from collections.abc import Sequence
from datetime import date

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate
from fairband.engine.route import CompanyInputs
from fairband.engine.types import Flag, Provenance
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs_statements import (
    FiscalCalendar,
    Statements,
    series_for,
    statements_for,
)
from fairband.store.companies import CompanyRow, latest_company
from fairband.store.observations import ObservationRow, observations_for
from fairband.store.vendor import latest_response, response_payload
from fairband.vendors.normalize_fmp import price_closes, value_as_date

__all__ = ["build_inputs", "series_for"]

_OBSERVATIONS = frozenset(
    {
        "estimate-annual",
        "estimate-quarter",
        "street-actual",
        "earnings-date",
        "quote",
        "profile",
        "gf-score",
        "gf-ratio",
    }
)
_QUOTE, _PROFILE, _SCREENER = "FMP quote", "FMP profile", "FMP company-screener"
_ESTIMATES, _EARNINGS = "FMP analyst-estimates", "FMP earnings"
_CLOSES = "FMP historical-price-eod/full"
_SUMMARY, _KEYRATIOS = "GuruFocus summary", "GuruFocus keyratios"
_UNKNOWN_CURRENCY = Flag(
    "currency-unknown",
    "Currency unknown",
    "Neither the statements nor the universe row give the reporting currency, so the company is "
    "treated as a foreign filer.",
)

type _Cited[T] = tuple[T, Provenance | None]
type _Closes = tuple[tuple[date, float], ...]


def build_inputs(
    conn: sqlite3.Connection, symbol: str, policy: Policy, tax: TaxTable, today: date
) -> CompanyInputs:
    """Everything the engine reads for ``symbol``, from the store. No assembly rule reads the
    policy yet."""
    company = latest_company(conn, symbol)
    country = company.country if company is not None and company.country else "unknown"
    stated = statements_for(conn, symbol, country, tax, today)
    provenance = dict(stated.provenance)

    def cite[T](name: str, found: _Cited[T]) -> T:
        value, source = found
        if source is not None:
            provenance[name] = source
        return value

    def read(dataset: str) -> list[ObservationRow]:
        if dataset not in _OBSERVATIONS:
            raise ValueError(f"not an observation dataset: {dataset}")
        return observations_for(conn, symbol, dataset)

    quote, profile, ratios = read("quote"), read("profile"), read("gf-ratio")
    price = _field(quote, "price")
    calendar = stated.calendar
    currency = stated.currency or (None if company is None else company.currency)
    flags = stated.flags if currency is not None else (*stated.flags, _UNKNOWN_CURRENCY)
    quarters = cite("estimates_quarter", _quarter_estimates(read("estimate-quarter"), calendar))
    annual = cite("estimates_annual", _annual_estimates(read("estimate-annual"), calendar))
    street = cite("street_ttm_eps", _street_ttm_eps(read("street-actual"), stated))
    moat = cite("moat_score", _value(_field(read("gf-score"), "moat_score"), _SUMMARY))
    eps_ttm = cite("gf_eps_ttm", _value(_field(ratios, "eps_ttm"), _KEYRATIOS))
    eps_clean = cite("gf_eps_without_nri", _value(_field(ratios, "eps_without_nri"), _KEYRATIOS))
    return CompanyInputs(
        symbol=symbol,
        name=company.name if company is not None and company.name else symbol,
        country=country,
        currency=currency or "unknown",
        is_adr=_is_adr(profile, company),
        market_cap=cite("market_cap", _market_cap(quote, profile, company)),
        price=cite("price", _value(price, _QUOTE)),
        price_date=None if price is None else price.as_of,
        shares_diluted=stated.shares_diluted,
        series=stated.series,
        capital_years=stated.capital_years,
        tax_rate_latest=stated.tax_rate_latest,
        trailing=stated.trailing,
        quarter_estimates=quarters,
        annual_estimates=annual,
        street_ttm_eps=street,
        moat_score=moat,
        gf_eps_ttm=eps_ttm,
        gf_eps_without_nri=eps_clean,
        next_earnings=cite("next_earnings", _next_earnings(read("earnings-date"), today)),
        closes=cite("closes", _closes(conn, symbol)),
        data_date=stated.data_date,
        provenance=provenance,
        input_flags=flags,
        refusal=stated.refusal,
        estimate_methods=stated.estimate_methods,
    )


def _quarter_estimates(
    rows: Sequence[ObservationRow], calendar: FiscalCalendar | None
) -> _Cited[tuple[QuarterEstimate, ...]]:
    if calendar is None:
        return (), None
    estimates = tuple(
        QuarterEstimate(
            period_end=period,
            fiscal_year=_fiscal_year(fields, period, calendar),
            fiscal_period=f"Q{_whole(fields.get('fiscal_period')) or calendar.quarter(period)}",
            eps=_float(fields.get("eps_avg")),
            revenue=_float(fields.get("revenue_avg")),
            net_income=_float(fields.get("net_income_avg")),
            analysts=_whole(fields.get("analysts_eps")),
        )
        for period, fields in _by_period(rows).items()
    )
    return estimates, _cite(_ESTIMATES, rows) if estimates else None


def _annual_estimates(
    rows: Sequence[ObservationRow], calendar: FiscalCalendar | None
) -> _Cited[tuple[AnnualEstimate, ...]]:
    if calendar is None:
        return (), None
    estimates = tuple(
        AnnualEstimate(
            fiscal_year=_fiscal_year(fields, period, calendar),
            period_end=period,
            eps=_float(fields.get("eps_avg")),
            revenue=_float(fields.get("revenue_avg")),
            net_income=_float(fields.get("net_income_avg")),
            analysts_eps=_whole(fields.get("analysts_eps")),
            analysts_net_income=_whole(fields.get("analysts_net_income")),
        )
        for period, fields in _by_period(rows).items()
    )
    return estimates, _cite(_ESTIMATES, rows) if estimates else None


def _street_ttm_eps(rows: Sequence[ObservationRow], stated: Statements) -> _Cited[float | None]:
    ends = stated.trailing_quarter_ends
    actual = {r.period: r for r in rows if r.field == "eps_actual" and r.value is not None}
    matched = [actual[end] for end in ends if end in actual]
    if not ends or len(matched) != len(ends):
        return None, None
    return sum(_float(r) or 0.0 for r in matched), _cite(_EARNINGS, matched)


def _market_cap(
    quote: Sequence[ObservationRow], profile: Sequence[ObservationRow], company: CompanyRow | None
) -> _Cited[float | None]:
    for rows, source in ((quote, _QUOTE), (profile, _PROFILE)):
        row = _field(rows, "market_cap")
        if row is not None:
            return _value(row, source)
    if company is None or company.market_cap is None:
        return None, None
    stamp = company.observed_at
    return float(company.market_cap), Provenance(_SCREENER, stamp.date(), stamp, None)


def _is_adr(profile: Sequence[ObservationRow], company: CompanyRow | None) -> bool:
    row = _field(profile, "is_adr")
    if row is not None and row.value is not None:
        return row.value == 1
    return company is not None and company.is_adr


def _next_earnings(rows: Sequence[ObservationRow], today: date) -> _Cited[date | None]:
    row = _field(rows, "next_date")
    if row is None or row.value is None or value_as_date(row.value) < today:
        return None, None
    return value_as_date(row.value), _cite(_EARNINGS, [row])


def _closes(conn: sqlite3.Connection, symbol: str) -> _Cited[_Closes]:
    """The closes of the latest usable price-history response; none without one that parses."""
    response = latest_response(conn, "fmp", "price-history", symbol, {"symbol": symbol})
    text = None if response is None else response_payload(conn, response.id)
    if response is None or text is None:
        return (), None
    try:
        closes = tuple(price_closes(json.loads(text)))
    except ValueError:
        return (), None
    if not closes:
        return (), None
    return closes, Provenance(_CLOSES, closes[-1][0], response.observed_at, None)


def _field(rows: Sequence[ObservationRow], name: str) -> ObservationRow | None:
    """The field's row with a value from the newest response, if any."""
    held = [r for r in rows if r.field == name and r.value is not None]
    return max(held, key=lambda r: r.response_id, default=None)


def _value(row: ObservationRow | None, source: str) -> _Cited[float | None]:
    return (None, None) if row is None else (_float(row), _cite(source, [row]))


def _cite(source: str, rows: Sequence[ObservationRow]) -> Provenance:
    """The rows' newest as-of date, observation and entry."""
    dates = [r.as_of for r in rows if r.as_of is not None]
    return Provenance(
        source,
        max(dates, default=None),
        max(r.observed_at for r in rows),
        max(r.entered_at for r in rows),
    )


def _by_period(rows: Sequence[ObservationRow]) -> dict[date, dict[str, ObservationRow]]:
    """Each dated period's rows by field, in the store's order: oldest period first."""
    out: dict[date, dict[str, ObservationRow]] = {}
    for row in rows:
        if row.period is not None:
            out.setdefault(row.period, {})[row.field] = row
    return out


def _fiscal_year(fields: dict[str, ObservationRow], period: date, calendar: FiscalCalendar) -> int:
    stored = _whole(fields.get("fiscal_year"))
    return calendar.fiscal_year(period) if stored is None else stored


def _float(row: ObservationRow | None) -> float | None:
    return None if row is None or row.value is None else float(row.value)


def _whole(row: ObservationRow | None) -> int | None:
    return None if row is None or row.value is None else int(row.value)
