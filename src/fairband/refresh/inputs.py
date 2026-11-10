"""Assembly: one company's stored facts and observations to the engine's ``CompanyInputs``.

The statement side (``series_for``, the capital years, the balance years, the tax rate, the
trailing figures and the share count) is ``inputs_statements``; its docstring states those rules.
``build_inputs`` adds:

- the consensus: one ``QuarterEstimate`` per period of the ``estimate-quarter`` rows and one
  ``AnnualEstimate`` per period of the ``estimate-annual`` rows, in period-end order, an annual one
  with its EPS, net-income and revenue analyst counts; the fiscal year is FMP's when stored, else
  derived from the company's fiscal-year end (``FiscalCalendar``), and so is the quarter label.
  FMP reports some companies under two fiscal calendars, two rows for one period with period ends
  days apart (AAPL: 2027-12-26 and 2027-12-27 for fiscal 2028 Q1), so a row whose period end lies
  within ``SAME_PERIOD_DAYS`` of the period's first row is that period, whatever its label; the row
  kept has the larger EPS analyst count, a tie or no count keeping the later period end, so the NTM
  quarters chain (``ntm_quarters``). The labels are information on the kept row and decide
  nothing here;
- the street's trailing EPS: the sum of the four ``street-actual`` values whose periods are exactly
  the four trailing quarter ends; ``None`` when one is missing or the trailing figures are a fiscal
  year, which leaves the SBC basis unknown (``mech/1.2``);
- the price and its date from the ``quote``; the market cap from the quote, else the profile, else
  the universe row; ``is_adr`` from the profile, else the universe row;
- the country, which picks the statutory tax rate: the ``country`` of the latest stored profile
  payload (the headquarters, spec 6.6), else the universe row's, else ``"unknown"``
  (``country_for``). The tax rate's note (``notes``) names the country, where it came from, and the
  rate's year and source;
- the currency: the newest annual income statement's, else the universe row's, else ``"unknown"``
  flagged ``currency-unknown``. The route reads every currency but USD as a foreign filer, so an
  unknown one gets the foreign-filer refusal, which is the honest outcome;
- the refusal: "no financial statements", else the statements' missing tax rate, except for a
  foreign filer (an ADR, or a currency other than USD), whose missing rates stay ``None`` so the
  route gives it the foreign-filer refusal of spec 11 with its phase;
- the GuruFocus moat score and EPS, the next earnings date (``None`` when before ``today``) and the
  closes of the latest price-history payload (none when it is absent or does not parse);
- the debt, short-term plus long-term debt, and the cash, cash and equivalents plus short-term
  investments, from the newest annual balance sheet: a line it does not present counts as nil and
  is named in the input's note (``"longTermDebt not presented"``), and with both lines missing the
  figure is ``None``;
- the peers and their source: ``peers.peer_figures`` on the given deciles; none without them.

``provenance`` holds an entry under each key the route cites (``route`` module docstring) whose
input the store supplied; an input it did not supply has none and cites "unknown". The source names
the vendor and its route (``"FMP quote"``, ``"GuruFocus summary"``) or the tax table; ``as_of`` is
the row's date and ``observed_at`` and ``entered_at`` the row's, the newest of several rows.
Nothing here raises on missing data: a missing piece is ``None``, a flag or a refusal. An unknown
dataset name is a programming error and raises ``ValueError``.
"""

import json
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from datetime import date

from fairband.engine.anchor import SAME_PERIOD_DAYS, AnnualEstimate, QuarterEstimate
from fairband.engine.classifier import Deciles
from fairband.engine.route import CompanyInputs
from fairband.engine.types import Flag, Provenance
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs_statements import (
    PROFILE_SOURCE,
    SCREENER_SOURCE,
    FiscalCalendar,
    Statements,
    balance_lines,
    balance_sums,
    country_for,
    series_for,
    statements_for,
)
from fairband.refresh.peers import peer_figures
from fairband.store.companies import CompanyRow, latest_company
from fairband.store.observations import ObservationRow, observations_for
from fairband.store.vendor import latest_response, response_payload
from fairband.vendors.normalize_fmp import price_closes, value_as_date

__all__ = ["build_inputs", "latest_price", "series_for"]

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
        "split",
    }
)
_QUOTE, _PROFILE, _SCREENER = "FMP quote", PROFILE_SOURCE, SCREENER_SOURCE
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
    conn: sqlite3.Connection,
    symbol: str,
    policy: Policy,
    tax: TaxTable,
    today: date,
    deciles: Deciles | None = None,
) -> CompanyInputs:
    """Everything the engine reads for ``symbol``, from the store; ``deciles`` classify its peers,
    and without them it has none. Only the peers read the policy, for the industry fallback."""
    company = latest_company(conn, symbol)
    country, origin = country_for(conn, symbol, company)
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
    is_adr = _is_adr(profile, company)
    foreign = is_adr or currency != "USD"
    quarters = cite("estimates_quarter", _quarter_estimates(read("estimate-quarter"), calendar))
    annual = cite("estimates_annual", _annual_estimates(read("estimate-annual"), calendar))
    street = cite("street_ttm_eps", _street_ttm_eps(read("street-actual"), stated))
    moat = cite("moat_score", _value(_field(read("gf-score"), "moat_score"), _SUMMARY))
    eps_ttm = cite("gf_eps_ttm", _value(_field(ratios, "eps_ttm"), _KEYRATIOS))
    eps_clean = cite("gf_eps_without_nri", _value(_field(ratios, "eps_without_nri"), _KEYRATIOS))
    sums = balance_sums(balance_lines(conn, symbol))
    notes = _tax_note(country, origin, stated)
    notes.update({name: note for name, (_, note) in sums.items() if note is not None})
    peers = peer_figures(conn, symbol, deciles, policy, tax, today)
    return CompanyInputs(
        symbol=symbol,
        name=company.name if company is not None and company.name else symbol,
        country=country,
        currency=currency or "unknown",
        is_adr=is_adr,
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
        refusal=stated.refusal or (None if foreign else stated.tax_refusal),
        estimate_methods=stated.estimate_methods,
        notes=notes,
        peers=peers.figures,
        peer_source=peers.source,
        debt=sums["debt"][0],
        cash=sums["cash"][0],
        balance_years=stated.balance_years,
    )


def latest_price(conn: sqlite3.Connection, symbol: str) -> tuple[float | None, date | None]:
    """The price of the newest stored quote and its date, as ``build_inputs`` reads them;
    ``(None, None)`` when the store holds no quote price for ``symbol``."""
    row = _field(observations_for(conn, symbol, "quote"), "price")
    return (None, None) if row is None else (_float(row), row.as_of)


def _quarter_estimates(
    rows: Sequence[ObservationRow], calendar: FiscalCalendar | None
) -> _Cited[tuple[QuarterEstimate, ...]]:
    if calendar is None:
        return (), None
    estimates = _one_per_period(
        (
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
        ),
        lambda q: q.analysts,
    )
    return estimates, _cite(_ESTIMATES, rows) if estimates else None


def _annual_estimates(
    rows: Sequence[ObservationRow], calendar: FiscalCalendar | None
) -> _Cited[tuple[AnnualEstimate, ...]]:
    if calendar is None:
        return (), None
    estimates = _one_per_period(
        (
            AnnualEstimate(
                fiscal_year=_fiscal_year(fields, period, calendar),
                period_end=period,
                eps=_float(fields.get("eps_avg")),
                revenue=_float(fields.get("revenue_avg")),
                net_income=_float(fields.get("net_income_avg")),
                analysts_eps=_whole(fields.get("analysts_eps")),
                analysts_net_income=_whole(fields.get("analysts_net_income")),
                analysts_revenue=_whole(fields.get("analysts_revenue")),
            )
            for period, fields in _by_period(rows).items()
        ),
        lambda a: a.analysts_eps,
    )
    return estimates, _cite(_ESTIMATES, rows) if estimates else None


def _one_per_period[E: (QuarterEstimate, AnnualEstimate)](
    estimates: Iterable[E], analysts: Callable[[E], int | None]
) -> tuple[E, ...]:
    """One estimate per period, in period-end order. Walking the rows by period end, a row ending
    within ``SAME_PERIOD_DAYS`` of the current period's first row joins that period, as the rows
    FMP gives for one period under two fiscal calendars do; of a period's rows, the one kept has
    the most EPS ``analysts``, a tie or no count taking the later period end; a count beats none."""
    periods: list[list[E]] = []
    for estimate in sorted(estimates, key=lambda e: e.period_end):
        if periods and (estimate.period_end - periods[-1][0].period_end).days <= SAME_PERIOD_DAYS:
            periods[-1].append(estimate)
        else:
            periods.append([estimate])

    def rank(estimate: E) -> tuple[int, date]:
        count = analysts(estimate)
        return (-1 if count is None else count), estimate.period_end

    return tuple(max(same, key=rank) for same in periods)


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


def _tax_note(country: str, origin: str | None, stated: Statements) -> dict[str, str]:
    """The tax rate's note, by input name: the country, where it came from, and the rate's year
    and source; none without a rate."""
    cited = stated.provenance.get("tax_rate_latest")
    if origin is None or stated.tax_year is None or cited is None:
        return {}
    note = (
        f"{country}, the headquarters country in the {origin}: its {stated.tax_year} statutory "
        f"rate, from {cited.source}"
    )
    return {"tax_rate_latest": note}


def stored_closes(conn: sqlite3.Connection, symbol: str) -> _Closes:
    """The closes ``build_inputs`` reads, oldest first, without building the rest: the report
    export's price table reads them (``reports.charts``)."""
    return _closes(conn, symbol)[0]


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
