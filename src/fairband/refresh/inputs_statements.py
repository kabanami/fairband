"""The statement side of assembly: fiscal years, capital years, balance years, the tax rate and
trailing figures.

Fiscal years run from the newest annual income period back, at most eleven (spec 6.5), one per
fiscal year with none skipped: a year the vendor data lacks keeps its place with no values, so the
classifier's and the ROIC's positions stay on the year. A period's fiscal year is FMP's label,
else the one ``FiscalCalendar`` derives from its period end. The cash flow joins the income
statement by period end; the balance sheet and the as-reported balance sheet join by fiscal year.
A year's currency is its income statement's, else the year before's (``"unknown"`` with none).

Capital years (spec 6.6, ROIC): cash and investments are cash plus short-term investments, one
missing counting as nil and both missing ``None``. Goodwill and intangibles are the normalized
lines, ``None`` where the vendor gave a zero (D17's vendor-zero rule) or nothing; intangibles take
the issuer's as-reported total (D17 method ``bs10-intangibles-total-v1``) where it has one. The
lease lines come from the as-reported balance sheet only. A balance sheet ending before 15 December
2019, when lease accounting (ASC 842) put operating leases on it, without lease assets flags
``leases-not-on-balance-sheet``; nothing is reconstructed (D3a's limitation, stated).

Balance years (spec 2026-11-03 10.6 and 10.8): one per fiscal year of the series with an annual
balance sheet, oldest first, its lines by FMP name beside that fiscal year's income statement and
cash flow; a year without a balance sheet has none.

The tax rate is the OECD statutory rate for the company's country and fiscal year (D3, D9). A rate
carried past the table's newest year flags ``tax-carried-forward`` and makes ``tax_rate_latest``
an estimate. The first year with an operating income and no rate gives ``tax_refusal``; a year
without a rate keeps a ``None`` rate. The country (``country_for``) is the ``country`` of the
latest stored profile payload that parses (the headquarters, spec 6.6), else the universe row's,
else ``"unknown"``.

Trailing figures (spec 6.6, spec 2026-11-10 8): the reporting cadence is read from the quarterly
statement rows (``cadence_of``): quarterly when the two newest end 80 to 100 days apart,
half-yearly when 170 to 195 (FMP's quarterly rows of a half-year reporter are its half-years). The
trailing figures are the sums of the last four quarters when the cadence is quarterly and each
ends 80 to 100 days after the one before (the anchor's rule), or of the last two half-years when
it is half-yearly and they end 170 to 195 days apart, joined to the quarterly cash flow by period
end, a sum ``None`` when any period lacks its part; else the last fiscal year, flagged
``trailing-on-fiscal-year``, on the quarterly cadence. The last fiscal year stands in too when any
of those periods' income statements names another currency than the newest annual one, the
reporting currency (spec 2026-11-10 7): the note's sentence then names those periods and their
currency. The interest expense and the depreciation and amortization (spec 2026-11-03 section 11)
are summed the same way; the interest expense counts each period by its size, as FMP signs it
either way.
The diluted share count is the newest quarterly row's weighted average, else the newest fiscal
year's. The trailing periods are the periods the trailing figures read, oldest first, each with its
own diluted EPS and weighted-average diluted count: the four quarters or the two half-years, or
the one fiscal year on the fallback; the split rule judges each on its own count
(``inputs_splits``).

``balance_lines`` reads the newest annual balance sheet's lines by FMP name, and
``stored_payload`` a payload the store keeps whole (the profile's, the peers'). ``balance_sums``
is the debt and the cash from those lines, short-term plus long-term debt and cash and equivalents
plus short-term investments, a line not presented counting as nil and a figure with every line
missing ``None``: assembly's reading, which ``newest_debt_and_cash`` gives the secondary
valuation.

``annual_lines`` reads each fiscal year's annual statements whole, by FMP name, joined as the
series and the balance years join them: the lines the report's financial tables read beside the
engine's records (``fairband.reports.tables``).
"""

import json
import sqlite3
from calendar import monthrange
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from fairband.engine.anchor import (
    HALF_DAYS_MAX,
    HALF_DAYS_MIN,
    PERIODS_PER_YEAR,
    QUARTER_DAYS_MAX,
    QUARTER_DAYS_MIN,
    Cadence,
    TrailingFigures,
    consecutive_periods,
)
from fairband.engine.balance import BalanceYear
from fairband.engine.classifier import FiscalYear, Series
from fairband.engine.roic import CapitalYear
from fairband.engine.types import Flag, Provenance
from fairband.policy.tax import TaxRate, TaxTable
from fairband.refresh.fetch import STATEMENT_YEARS
from fairband.store.companies import CompanyRow
from fairband.store.facts import FactRow, facts_for
from fairband.store.vendor import latest_response, response_payload
from fairband.vendors.normalize_fmp import profile_brief, profile_country

INCOME_SOURCE = "FMP income-statement"
STATEMENTS_SOURCE = "FMP income-statement, balance-sheet-statement, cash-flow-statement"
PROFILE_SOURCE = "FMP profile"
SCREENER_SOURCE = "FMP company-screener"

_DATASETS = (
    "income-annual",
    "balance-annual",
    "cashflow-annual",
    "balance-asreported-annual",
    "income-quarter",
    "cashflow-quarter",
)
_CFO = "netCashProvidedByOperatingActivities"
_SHARES = "weightedAverageShsOutDil"
_AS_REPORTED_INTANGIBLES = "intangibles_ex_goodwill"
# Lease accounting (ASC 842) applies to fiscal years beginning after 15 December 2018.
_LEASES_ON_BALANCE_SHEET = date(2019, 12, 15)
# A 52/53-week fiscal year ends up to six days either side of a fixed month and day.
_YEAR_END_DRIFT = timedelta(days=7)
_DAYS_A_YEAR = 365.25
# A trailing period's name, one and several, under each cadence.
_PERIOD_NOUNS: dict[Cadence, tuple[str, str]] = {
    "quarterly": ("quarter", "quarters"),
    "half-yearly": ("half-year", "half-years"),
}
# The newest annual balance sheet's lines each figure sums, by input name.
_BALANCE_SUMS = {
    "debt": ("shortTermDebt", "longTermDebt"),
    "cash": ("cashAndCashEquivalents", "shortTermInvestments"),
}


@dataclass(frozen=True)
class FiscalCalendar:
    """The company's fiscal-year end: the month and day of its newest annual period end.

    FMP labels a fiscal year by the calendar year its period ends in, so a period belongs to the
    year whose end it does not pass. A period ending up to a week past a year's month and day
    still belongs to that year, since a 52/53-week year's end moves by up to six days; that week
    can cross into the next calendar year (a year ending on the Saturday nearest 31 December ends
    on 2 January 2027 for fiscal 2026).
    """

    month: int
    day: int

    def year_end(self, year: int) -> date:
        return date(year, self.month, min(self.day, monthrange(year, self.month)[1]))

    def fiscal_year(self, end: date) -> int:
        for year in (end.year - 1, end.year):
            if end <= self.year_end(year) + _YEAR_END_DRIFT:
                return year
        return end.year + 1

    def quarter(self, end: date) -> int:
        """1 to 4, counted from the start of the period's fiscal year."""
        days_left = (self.year_end(self.fiscal_year(end)) - end).days
        return min(4, max(1, 4 - round(days_left * 4 / _DAYS_A_YEAR)))


@dataclass(frozen=True)
class TrailingPeriod:
    """One period the trailing figures read: its end, its diluted EPS and its own diluted
    weighted-average share count, each ``None`` where the statement lacks it."""

    end: date
    eps_diluted: float | None
    shares_diluted: float | None


@dataclass(frozen=True)
class Statements:
    """The statement-side fields of ``CompanyInputs``; ``calendar`` is ``None`` and ``refusal`` is
    "no financial statements" when the store holds no annual income statement. ``tax_refusal``
    names the first year with an operating income and no statutory tax rate; ``tax_year`` is the
    table year ``tax_rate_latest`` comes from, before the newest fiscal year when carried forward."""

    calendar: FiscalCalendar | None
    series: Series
    capital_years: tuple[CapitalYear, ...]
    balance_years: tuple[BalanceYear, ...]
    tax_rate_latest: float | None
    trailing: TrailingFigures | None
    trailing_quarter_ends: tuple[date, ...]  # the periods' ends; empty on the fiscal-year fallback
    trailing_periods: tuple[TrailingPeriod, ...]  # oldest first; the one year on the fallback
    shares_diluted: float | None
    currency: str | None  # the newest annual income statement's
    data_date: date
    provenance: dict[str, Provenance]
    flags: tuple[Flag, ...]
    refusal: str | None
    tax_refusal: str | None = None
    estimate_methods: dict[str, str] = field(default_factory=dict)
    tax_year: int | None = None


@dataclass(frozen=True)
class _Period:
    """One statement period's facts by field."""

    end: date
    facts: dict[str, FactRow]

    def value(self, name: str) -> float | None:
        row = self.facts.get(name)
        return None if row is None or row.value is None else float(row.value)

    @property
    def fiscal_year(self) -> int | None:
        return next((r.fiscal_year for r in self.facts.values() if r.fiscal_year is not None), None)

    @property
    def currency(self) -> str | None:
        return next((r.currency for r in self.facts.values() if r.currency is not None), None)


_NONE = _Period(date.min, {})


@dataclass(frozen=True)
class _Years:
    """The kept fiscal years, oldest first, and each one's income statement."""

    calendar: FiscalCalendar
    span: range
    income: dict[int, _Period]

    @classmethod
    def of(cls, income: Sequence[_Period]) -> "_Years | None":
        if not income:
            return None
        newest = income[-1].end
        calendar = FiscalCalendar(newest.month, newest.day)
        by_year = _by_year(income, calendar)
        last = max(by_year)
        first = max(min(by_year), last - STATEMENT_YEARS + 1)
        return cls(calendar, range(first, last + 1), by_year)

    def end(self, year: int) -> date:
        income = self.income.get(year)
        return self.calendar.year_end(year) if income is None else income.end


def series_for(conn: sqlite3.Connection, symbol: str) -> Series:
    """The fiscal-year series of ``symbol``: oldest first, at most eleven years, none skipped;
    empty without an annual income statement."""
    years = _Years.of(_periods(conn, symbol, "income-annual"))
    if years is None:
        return ()
    return _series(years, _by_end(_periods(conn, symbol, "cashflow-annual")))


def statements_for(
    conn: sqlite3.Connection, symbol: str, country: str, tax: TaxTable, today: date
) -> Statements:
    """The statement-side inputs of ``symbol``, taxed at ``country``'s statutory rates."""
    periods = {dataset: _periods(conn, symbol, dataset) for dataset in _DATASETS}
    years = _Years.of(periods["income-annual"])
    if years is None:
        return Statements(
            calendar=None,
            series=(),
            capital_years=(),
            balance_years=(),
            tax_rate_latest=None,
            trailing=None,
            trailing_quarter_ends=(),
            trailing_periods=(),
            shares_diluted=None,
            currency=None,
            data_date=today,
            provenance={},
            flags=(),
            refusal="no financial statements",
        )
    cash = _by_end(periods["cashflow-annual"])
    balance = _by_year(periods["balance-annual"], years.calendar)
    reported = _by_year(periods["balance-asreported-annual"], years.calendar)
    rates = {year: tax.rate_for(country, year) for year in years.span}
    capital, methods = _capital_years(years, balance, reported, rates)
    newest_rate = rates[years.span[-1]]
    quarters = periods["income-quarter"]
    trailing, trailing_periods, fallback = _trailing(
        years, cash, quarters, _by_end(periods["cashflow-quarter"])
    )
    quarter_ends = () if trailing.on_fiscal_year else tuple(p.end for p in trailing_periods)
    shares, shares_source = _shares(quarters, periods["income-annual"])

    facts = [row for found in periods.values() for p in found for row in p.facts.values()]
    provenance = {
        "statements": Provenance(
            STATEMENTS_SOURCE,
            years.income[years.span[-1]].end,
            max(r.observed_at for r in facts),
            max(r.entered_at for r in facts),
        )
    }
    if newest_rate is not None:
        provenance["tax_rate_latest"] = Provenance(newest_rate.source, None, None, None)
        if newest_rate.method is not None:
            methods["tax_rate_latest"] = newest_rate.method
    if shares_source is not None:
        provenance["shares_diluted"] = shares_source

    flags = (
        _tax_flag(country, rates)
        + _leases_flag(years, balance, reported)
        + (() if quarter_ends else (fallback,))
    )
    return Statements(
        calendar=years.calendar,
        series=_series(years, cash),
        capital_years=capital,
        balance_years=_balance_years(years, balance, cash),
        tax_rate_latest=None if newest_rate is None else newest_rate.rate,
        trailing=trailing,
        trailing_quarter_ends=quarter_ends,
        trailing_periods=trailing_periods,
        shares_diluted=shares,
        currency=periods["income-annual"][-1].currency,
        data_date=max(r.observed_at for r in facts).date(),
        provenance=provenance,
        flags=flags,
        refusal=None,
        tax_refusal=_tax_refusal(country, capital),
        estimate_methods=methods,
        tax_year=None if newest_rate is None else newest_rate.year_used,
    )


def cadence_of(ends: Sequence[date]) -> Cadence | None:
    """The reporting cadence of statement periods ending ``ends``, oldest first (spec 2026-11-10
    8): ``quarterly`` when the two newest end 80 to 100 days apart, ``half-yearly`` when 170 to
    195, else ``None``, as with fewer than two."""
    if len(ends) < 2:
        return None
    days = (ends[-1] - ends[-2]).days
    if QUARTER_DAYS_MIN <= days <= QUARTER_DAYS_MAX:
        return "quarterly"
    if HALF_DAYS_MIN <= days <= HALF_DAYS_MAX:
        return "half-yearly"
    return None


def country_for(
    conn: sqlite3.Connection, symbol: str, company: CompanyRow | None
) -> tuple[str, str | None]:
    """The company's country and where it came from: the latest usable profile's (the
    headquarters, spec 6.6), else the universe row's (``company``); ``"unknown"`` from neither."""
    country = profile_country(stored_payload(conn, "profile", symbol))
    if country is not None:
        return country, PROFILE_SOURCE
    if company is not None and company.country:
        return company.country, SCREENER_SOURCE
    return "unknown", None


def brief_for(conn: sqlite3.Connection, symbol: str) -> str | None:
    """The company brief (B-149): the latest usable profile's description; ``None`` without
    one."""
    return profile_brief(stored_payload(conn, "profile", symbol))


def balance_lines(conn: sqlite3.Connection, symbol: str) -> dict[str, float | None]:
    """The newest annual balance sheet's lines by FMP name, ``None`` where it presents no value;
    empty without a balance sheet."""
    sheets = _periods(conn, symbol, "balance-annual")
    return {} if not sheets else {name: sheets[-1].value(name) for name in sheets[-1].facts}


def balance_sums(
    lines: Mapping[str, float | None],
) -> dict[str, tuple[float | None, str | None]]:
    """The debt and the cash of a balance sheet's ``lines``, by input name (module docstring),
    each with the note naming its missing lines, ``None`` with none missing."""
    return {name: _sum_lines(lines, names) for name, names in _BALANCE_SUMS.items()}


def newest_debt_and_cash(
    conn: sqlite3.Connection, symbol: str
) -> tuple[float | None, float | None]:
    """The newest annual balance sheet's debt and cash as assembly reads them; ``None`` for a
    figure with every line missing, and both without a balance sheet."""
    sums = balance_sums(balance_lines(conn, symbol))
    return sums["debt"][0], sums["cash"][0]


def annual_lines(
    conn: sqlite3.Connection, symbol: str
) -> dict[int, dict[str, dict[str, float | None]]]:
    """Each fiscal year of the series, oldest first, with its annual statements' lines by
    dataset (``income-annual``, ``cashflow-annual``, ``balance-annual``) and FMP name: the year's
    income statement, the cash flow ending on its period end and the balance sheet of its fiscal
    year, as ``series_for`` and the balance years join them. A statement the year lacks is
    absent and a line it does not present ``None``; empty without an annual income statement."""
    years = _Years.of(_periods(conn, symbol, "income-annual"))
    if years is None:
        return {}
    cash = _by_end(_periods(conn, symbol, "cashflow-annual"))
    balance = _by_year(_periods(conn, symbol, "balance-annual"), years.calendar)
    out = {}
    for year in years.span:
        income = years.income.get(year)
        found = {
            "income-annual": income,
            "cashflow-annual": None if income is None else cash.get(income.end),
            "balance-annual": balance.get(year),
        }
        out[year] = {
            dataset: {name: period.value(name) for name in period.facts}
            for dataset, period in found.items()
            if period is not None
        }
    return out


def _sum_lines(
    lines: Mapping[str, float | None], names: Sequence[str]
) -> tuple[float | None, str | None]:
    """The lines' sum, a missing line counting as nil, ``None`` with every line missing; and the
    note naming the missing lines, ``None`` with none missing."""
    missing = [name for name in names if lines.get(name) is None]
    held = [value for name in names if (value := lines.get(name)) is not None]
    note = f"{' and '.join(missing)} not presented" if missing else None
    return (sum(held) if held else None), note


def stored_payload(conn: sqlite3.Connection, endpoint: str, symbol: str) -> Any:
    """The parsed payload of the latest usable FMP response to ``endpoint`` for ``symbol``, a call
    whose only parameter is the symbol; ``None`` without one or when it does not parse."""
    response = latest_response(conn, "fmp", endpoint, symbol, {"symbol": symbol})
    text = None if response is None else response_payload(conn, response.id)
    try:
        return None if text is None else json.loads(text)
    except ValueError:  # a payload that does not parse is none
        return None


def _series(years: _Years, cash: dict[date, _Period]) -> Series:
    currencies = _carried([years.income.get(y, _NONE).currency for y in years.span])
    rows = []
    for year, currency in zip(years.span, currencies, strict=True):
        income = years.income.get(year, _NONE)
        flows = cash.get(income.end, _NONE)
        rows.append(
            FiscalYear(
                year=year,
                period_end=years.end(year),
                currency=currency,
                revenue=income.value("revenue"),
                operating_income=income.value("operatingIncome"),
                cfo=flows.value(_CFO),
                cfi=flows.value("netCashProvidedByInvestingActivities"),
                cff=flows.value("netCashProvidedByFinancingActivities"),
                capex=flows.value("capitalExpenditure"),
            )
        )
    return tuple(rows)


def _capital_years(
    years: _Years,
    balance: dict[int, _Period],
    reported: dict[int, _Period],
    rates: dict[int, TaxRate | None],
) -> tuple[tuple[CapitalYear, ...], dict[str, str]]:
    """The capital years and, when an as-reported intangibles estimate was used, its method."""
    rows, methods = [], {}
    for year in years.span:
        sheet, filed, rate = balance.get(year, _NONE), reported.get(year, _NONE), rates[year]
        intangibles = filed.value(_AS_REPORTED_INTANGIBLES)
        if intangibles is None:
            intangibles = sheet.value("intangibleAssets")
        elif (method := filed.facts[_AS_REPORTED_INTANGIBLES].estimate_method) is not None:
            methods["intangibles"] = method
        cash = sheet.value("cashAndCashEquivalents")
        investments = sheet.value("shortTermInvestments")
        rows.append(
            CapitalYear(
                year=year,
                operating_income=years.income.get(year, _NONE).value("operatingIncome"),
                tax_rate=None if rate is None else rate.rate,
                total_current_assets=sheet.value("totalCurrentAssets"),
                cash_and_investments=(
                    None
                    if cash is None and investments is None
                    else (cash or 0.0) + (investments or 0.0)
                ),
                total_current_liabilities=sheet.value("totalCurrentLiabilities"),
                short_term_debt=sheet.value("shortTermDebt"),
                current_lease_liability=filed.value("current_lease_liability"),
                net_ppe=sheet.value("propertyPlantEquipmentNet"),
                lease_rou_asset=filed.value("lease_rou_asset"),
                goodwill=sheet.value("goodwill"),
                intangibles=intangibles,
            )
        )
    return tuple(rows), methods


def _balance_years(
    years: _Years, balance: dict[int, _Period], cash: dict[date, _Period]
) -> tuple[BalanceYear, ...]:
    rows = []
    for year in years.span:
        sheet = balance.get(year)
        if sheet is None:
            continue
        income = years.income.get(year, _NONE)
        flows = cash.get(income.end, _NONE)
        rows.append(
            BalanceYear(
                year=year,
                period_end=sheet.end,
                total_current_assets=sheet.value("totalCurrentAssets"),
                total_current_liabilities=sheet.value("totalCurrentLiabilities"),
                total_assets=sheet.value("totalAssets"),
                total_liabilities=sheet.value("totalLiabilities"),
                retained_earnings=sheet.value("retainedEarnings"),
                equity=sheet.value("totalStockholdersEquity"),
                long_term_debt=sheet.value("longTermDebt"),
                revenue=income.value("revenue"),
                gross_profit=income.value("grossProfit"),
                operating_income=income.value("operatingIncome"),
                net_income=income.value("netIncome"),
                cfo=flows.value(_CFO),
                stock_issued=flows.value("commonStockIssuance"),
            )
        )
    return tuple(rows)


def _trailing(
    years: _Years,
    cash: dict[date, _Period],
    quarters: Sequence[_Period],
    quarter_cash: dict[date, _Period],
) -> tuple[TrailingFigures, tuple[TrailingPeriod, ...], Flag]:
    """The trailing figures and the periods they read, oldest first: the four quarters or the two
    half-years of the company's cadence, or the one fiscal year on the fallback, with the
    ``trailing-on-fiscal-year`` note its reason gives (the module docstring)."""
    cadence = cadence_of([q.end for q in quarters])
    last = [] if cadence is None else _a_year_of(quarters, cadence)
    newest = years.span[-1]
    reporting = years.income[newest].currency
    others = [q for q in last if q.currency not in (None, reporting)] if reporting else []
    fallback = _on_fiscal_year(newest)
    if cadence is not None and others:
        last, fallback = [], _in_another_currency(newest, others, reporting, cadence)
    if last:
        incomes, flows = last, [quarter_cash.get(q.end, _NONE) for q in last]
    else:
        income = years.income[newest]
        incomes, flows = [income], [cash.get(income.end, _NONE)]
    figures = TrailingFigures(
        period_end=incomes[-1].end,
        quarters=len(incomes),
        on_fiscal_year=not last,
        revenue=_total(incomes, "revenue"),
        operating_income=_total(incomes, "operatingIncome"),
        net_income=_total(incomes, "netIncome"),
        eps_diluted=_total(incomes, "epsDiluted"),
        sbc=_total(flows, "stockBasedCompensation"),
        cfo=_total(flows, _CFO),
        capex=_total(flows, "capitalExpenditure"),
        dividends=_total(flows, "netDividendsPaid"),
        buybacks=_total(flows, "commonStockRepurchased"),
        equity_issued=_total(flows, "commonStockIssuance"),
        interest_expense=_total(incomes, "interestExpense", size=True),
        depreciation=_total(flows, "depreciationAndAmortization"),
        cadence=cadence if cadence is not None and last else "quarterly",
    )
    read = tuple(TrailingPeriod(i.end, i.value("epsDiluted"), i.value(_SHARES)) for i in incomes)
    return figures, read, fallback


def _a_year_of(rows: Sequence[_Period], cadence: Cadence) -> list[_Period]:
    """The last year of ``rows`` on ``cadence``: the last four quarters or the last two
    half-years when there are as many and each ends the cadence's days after the one before
    (``anchor.consecutive_periods``); none otherwise."""
    count = PERIODS_PER_YEAR[cadence]
    last = list(rows[-count:])
    if len(last) < count or not consecutive_periods([p.end for p in last], cadence):
        return []
    return last


def _shares(
    quarters: Sequence[_Period], annual: Sequence[_Period]
) -> tuple[float | None, Provenance | None]:
    """The newest quarterly row's diluted weighted-average share count, else the newest
    year's."""
    for periods in (quarters, annual):
        row = periods[-1].facts.get(_SHARES) if periods else None
        if row is not None and row.value is not None:
            source = Provenance(INCOME_SOURCE, row.period_end, row.observed_at, row.entered_at)
            return float(row.value), source
    return None, None


def _tax_refusal(country: str, capital: Sequence[CapitalYear]) -> str | None:
    return next(
        (
            f"no statutory tax rate for {country} {y.year}"
            for y in capital
            if y.tax_rate is None and y.operating_income is not None
        ),
        None,
    )


def _tax_flag(country: str, rates: dict[int, TaxRate | None]) -> tuple[Flag, ...]:
    carried = [(year, rate) for year, rate in rates.items() if rate is not None and rate.estimate]
    if not carried:
        return ()
    used = carried[0][1]
    return (
        Flag(
            "tax-carried-forward",
            "Tax rate carried forward",
            f"The tax table has no {country} rate after {used.year_used}, so its "
            f"{used.year_used} rate is carried forward to fiscal {_listed(y for y, _ in carried)} "
            f"as an estimate under method {used.method}.",
        ),
    )


def _leases_flag(
    years: _Years, balance: dict[int, _Period], reported: dict[int, _Period]
) -> tuple[Flag, ...]:
    early = [
        year
        for year in years.span
        if (sheet := balance.get(year)) is not None
        and sheet.end < _LEASES_ON_BALANCE_SHEET
        and reported.get(year, _NONE).value("lease_rou_asset") is None
    ]
    if not early:
        return ()
    return (
        Flag(
            "leases-not-on-balance-sheet",
            "Leases not on balance sheet",
            f"The balance sheets for fiscal {_listed(early)} predate lease accounting (ASC 842) "
            "and show no lease assets, so invested capital in those years leaves operating "
            "leases out; they are not reconstructed.",
        ),
    )


def _on_fiscal_year(year: int) -> Flag:
    return Flag(
        "trailing-on-fiscal-year",
        "Trailing on fiscal year",
        "The statement periods on file are neither four consecutive quarters nor two consecutive "
        f"half-years, so the trailing figures are fiscal {year}'s.",
    )


def _in_another_currency(
    year: int, others: Sequence[_Period], reporting: str | None, cadence: Cadence
) -> Flag:
    """The ``trailing-on-fiscal-year`` note when a trailing period is in another currency than the
    fiscal years, its sentence naming the periods, quarters or half-years by ``cadence``, by their
    currency: "The quarter to 2026-09-30 is in USD while the fiscal years are in CAD, so the
    trailing figures are fiscal 2025's"."""
    one, many = _PERIOD_NOUNS[cadence]
    by_currency: dict[str | None, list[date]] = {}
    for q in others:
        by_currency.setdefault(q.currency, []).append(q.end)
    named = []
    for currency, ends in by_currency.items():
        days = [end.isoformat() for end in ends]
        listed = days[0] if len(days) == 1 else f"{', '.join(days[:-1])} and {days[-1]}"
        noun, verb = (one, "is") if len(days) == 1 else (many, "are")
        named.append(f"the {noun} to {listed} {verb} in {currency}")
    first = " and ".join(named)
    return Flag(
        "trailing-on-fiscal-year",
        "Trailing on fiscal year",
        f"{first[0].upper()}{first[1:]} while the fiscal years are in {reporting}, so the "
        f"trailing figures are fiscal {year}'s.",
    )


def _periods(conn: sqlite3.Connection, symbol: str, dataset: str) -> list[_Period]:
    """The dataset's periods, oldest first; an unknown dataset raises ``ValueError``."""
    if dataset not in _DATASETS:
        raise ValueError(f"not a statement dataset: {dataset}")
    by_end: dict[date, dict[str, FactRow]] = {}
    for row in facts_for(conn, symbol, dataset):
        by_end.setdefault(row.period_end, {})[row.field] = row
    return [_Period(end, facts) for end, facts in sorted(by_end.items())]


def _by_year(periods: Sequence[_Period], calendar: FiscalCalendar) -> dict[int, _Period]:
    """Each period under its fiscal year; of two in one year the later period end wins."""
    return {
        p.fiscal_year if p.fiscal_year is not None else calendar.fiscal_year(p.end): p
        for p in periods
    }


def _by_end(periods: Sequence[_Period]) -> dict[date, _Period]:
    return {p.end: p for p in periods}


def _total(periods: Sequence[_Period], name: str, size: bool = False) -> float | None:
    """The sum over the periods, each by its size with ``size``; ``None`` when any of them lacks
    the value."""
    values = [abs(v) if size else v for p in periods if (v := p.value(name)) is not None]
    return sum(values) if len(values) == len(periods) else None


def _carried(currencies: Sequence[str | None]) -> list[str]:
    """Each missing currency takes the one before it; leading ones take the first known."""
    last = next((c for c in currencies if c is not None), "unknown")
    out = []
    for currency in currencies:
        last = currency or last
        out.append(last)
    return out


def _listed(years: Iterable[int]) -> str:
    return ", ".join(str(y) for y in years)
