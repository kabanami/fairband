"""The engine's test companies: the universe deciles and small, complete companies, one for each
phase the engine routes (Mature Growth, Mature Stable, High Growth, Young Growth, Decline,
Start-up).

The engine tests take them as fixtures (``tests/engine/conftest.py``); the web tests value them
and store the results. Money is in USD and shares in units. Fiscal years are calendar years 2015
to 2025, the trailing twelve months end 2026-09-30, the data date is 2026-10-30 and the tests
value on 2026-10-31.

``in_sek`` restates any of them as a company reporting in SEK (spec 2026-11-10 section 7), and
``fx_inputs`` is FXCO, spec 11.2's company in SEK. ``as_live`` dates any of them as assembly
does.

Each company is valued on its file row of the moat table (``MOAT_FILE``), Mature Growth Co Wide
and the others None, the classes their GuruFocus Moat Scores gave before method 1.8 (8 and none);
``judged_moat`` puts any of them on an owner's or an agent's row.
"""

from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures
from fairband.engine.balance import BalanceYear, NewestSheet, SheetFigures
from fairband.engine.classifier import Deciles, FiscalYear, Series
from fairband.engine.revenue_growth import PeerFigures
from fairband.engine.roic import CapitalYear
from fairband.engine.route import CompanyInputs
from fairband.engine.types import Provenance
from fairband.policy import Moat

DATA_DATE = date(2026, 10, 30)
OBSERVED = datetime(2026, 10, 30, 21, 0, tzinfo=UTC)
# The moat table's file row each company is valued on, cited as assembly cites it (spec 2026-11-19
# 8.5): the table's version, as of the entry's date, entered when the refresh's stage wrote the
# row. The companies hold no note for it: the engine notes a class without a reason by its word.
MOAT_JUDGED = date(2026, 11, 19)
MOAT_AT = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
MOAT_FILE = Provenance("moat table fairband-moat-v1", MOAT_JUDGED, None, MOAT_AT)

# Every provenance key the route reads, with the source assembly would cite.
SOURCES = {
    "price": "FMP quote",
    "market_cap": "FMP quote",
    "shares_diluted": "FMP income-statement",
    "statements": "FMP income-statement",
    "balance_sheet": "FMP balance-sheet-statement",
    "estimates_quarter": "FMP analyst-estimates",
    "estimates_annual": "FMP analyst-estimates",
    "street_ttm_eps": "FMP earnings",
    "next_earnings": "FMP earnings-calendar",
    "tax_rate_latest": "OECD corporate tax statistics",
    "closes": "FMP historical-price-eod",
}


def fiscal_years(revenue: list[float], margin: list[float]) -> Series:
    """Fiscal years ending in 2025, oldest first; cash flows are fixed shares of revenue, with
    a positive free cash flow."""
    first = 2026 - len(revenue)
    return tuple(
        FiscalYear(
            year=first + k,
            period_end=date(first + k, 12, 31),
            currency="USD",
            revenue=rev,
            operating_income=m * rev,
            cfo=0.25 * rev,
            cfi=-0.10 * rev,
            cff=-0.12 * rev,
            capex=-0.06 * rev,
        )
        for k, (rev, m) in enumerate(zip(revenue, margin, strict=True))
    )


def capital_years(series: Series, tax_rate: float = 0.25) -> tuple[CapitalYear, ...]:
    """One balance sheet per fiscal year; invested capital is 0.83 × revenue:
    (0.40 − 0.10) − (0.20 − 0.02 − 0.01) + 0.50 + 0.05 + 0.10 + 0.05."""
    return tuple(
        CapitalYear(
            year=fy.year,
            operating_income=fy.operating_income,
            tax_rate=tax_rate,
            total_current_assets=0.40 * rev,
            cash_and_investments=0.10 * rev,
            total_current_liabilities=0.20 * rev,
            short_term_debt=0.02 * rev,
            current_lease_liability=0.01 * rev,
            net_ppe=0.50 * rev,
            lease_rou_asset=0.05 * rev,
            goodwill=0.10 * rev,
            intangibles=0.05 * rev,
        )
        for fy in series
        if (rev := fy.revenue) is not None
    )


def weekday_closes(
    first: date, last: date, start: float, end: float
) -> tuple[tuple[date, float], ...]:
    """A close on every weekday from ``first`` to ``last``, rising in a straight line."""
    days = [first + timedelta(days=k) for k in range((last - first).days + 1)]
    weekdays = [d for d in days if d.weekday() < 5]
    step = (end - start) / (len(weekdays) - 1)
    return tuple((d, start + k * step) for k, d in enumerate(weekdays))


def quarter(
    period_end: date, fiscal_year: int, period: str, eps: float, revenue: float | None = None
) -> QuarterEstimate:
    """A consensus quarter of 20 analysts, with a revenue mean when ``revenue`` is given."""
    return QuarterEstimate(period_end, fiscal_year, period, eps, revenue, None, 20)


def annual(
    year: int,
    net_income: float,
    eps: float,
    analysts: int,
    revenue: float | None = None,
    analysts_revenue: int | None = None,
) -> AnnualEstimate:
    """A consensus fiscal year: ``analysts`` count the EPS and the net income, ``analysts_revenue``
    the revenue."""
    return AnnualEstimate(
        year, date(year, 12, 31), eps, revenue, net_income, analysts, analysts, analysts_revenue
    )


QUARTER_SHEET_SOURCE = SOURCES["balance_sheet"]


def fiscal_sheet(
    series: Series, current_assets: float | None = None, liabilities: float | None = None
) -> NewestSheet:
    """The newest balance sheet as the builders state it: the newest fiscal year's of ``series``,
    labelled "fiscal <year>" and not a quarter's, with the floor's two lines ``current_assets``
    and ``liabilities`` and no minority interest."""
    fy = series[-1]
    return NewestSheet(fy.period_end, f"fiscal {fy.year}", False, current_assets, liabilities, None)


def on_sheet(i: CompanyInputs, sheet: NewestSheet) -> CompanyInputs:
    """``i`` with ``sheet`` as its newest balance sheet, cited as assembly cites it: under
    ``balance_sheet``, as of the sheet's period end (method 4.2)."""
    cited = Provenance(SOURCES["balance_sheet"], sheet.period_end, OBSERVED, None)
    return replace(i, sheet=sheet, provenance=i.provenance | {"balance_sheet": cited})


def on_quarter_sheet(
    i: CompanyInputs,
    current_assets: float | None = None,
    liabilities: float | None = None,
) -> CompanyInputs:
    """``i`` with its newest balance sheet the quarter's of 30 Sep 2026, "fiscal 2026 Q3" (spec
    2026-11-13 12.2), cited as assembly cites it, as of its period end; its floor's two lines
    ``current_assets`` and ``liabilities``, no minority interest, and its debt and cash as they
    were."""
    sheet = NewestSheet(
        date(2026, 9, 30), "fiscal 2026 Q3", True, current_assets, liabilities, None
    )
    return on_sheet(i, sheet)


# The note sheet-shift on ``shifted_sheet`` (spec 2026-11-13 12.5): the quarter's sheet presents
# no minority interest where fiscal 2025's sheet showed $45 m.
SHIFT_SENTENCE = (
    "The balance sheet of fiscal 2026 Q3 shows no minority interest where fiscal 2025 showed "
    "$45.0 million, so the vendor's line may be wrong."
)


def shifted_sheet(i: CompanyInputs) -> NewestSheet:
    """The newest balance sheet of ``i`` as a quarter's, of 30 Sep 2026, "fiscal 2026 Q3", its
    floor's two lines and its minority interest as they were, carrying the five lines the note
    ``sheet-shift`` compares (spec 2026-11-13 12.5): on the quarter and on fiscal 2025's sheet
    the debt of ``i`` as long-term debt and its cash as cash and equivalents, the short-term debt
    and investments at nil; the quarter's minority interest the sheet's, none on every fixture,
    against $45 m on fiscal 2025's sheet. So the note names the minority interest alone
    (``SHIFT_SENTENCE``), and the figures in force are as they were: no value moves. Without a
    sheet on file, a quarter's that presents neither floor line nor a minority interest."""
    sheet = i.sheet or NewestSheet(date(2026, 9, 30), "fiscal 2026 Q3", True, None, None, None)
    quarter = SheetFigures("fiscal 2026 Q3", 0.0, i.debt, i.cash, 0.0, sheet.minority_interest)
    return replace(
        sheet,
        period_end=date(2026, 9, 30),
        label="fiscal 2026 Q3",
        quarterly=True,
        figures=quarter,
        annual=replace(quarter, label="fiscal 2025", minority_interest=45e6),
    )


def on_shifted_sheet(i: CompanyInputs) -> CompanyInputs:
    """``i`` on its ``shifted_sheet``, cited as assembly cites it (``on_sheet``)."""
    return on_sheet(i, shifted_sheet(i))


def unshifted(i: CompanyInputs) -> CompanyInputs:
    """``i`` with its newest balance sheet as it is but for the two sheets' five lines, which only
    the note ``sheet-shift`` reads."""
    assert i.sheet is not None
    return replace(i, sheet=replace(i.sheet, figures=None, annual=None))


def with_minority(i: CompanyInputs, line: float | None) -> CompanyInputs:
    """``i`` with its newest balance sheet's minority interest at ``line``, as the sheet would
    present it: ``None`` for a line not presented, a figure at or below zero as it stands (spec
    2026-11-13 13)."""
    assert i.sheet is not None
    return replace(i, sheet=replace(i.sheet, minority_interest=line))


def with_ntm_revenue(i: CompanyInputs, revenue: float) -> CompanyInputs:
    """``i`` with its NTM consensus revenue at ``revenue``: the four quarters' revenue means, the
    company's whole quarterly consensus, sum to it exactly, the whole of it in the first."""
    assert len(i.quarter_estimates) == 4
    means = (revenue, 0.0, 0.0, 0.0)
    quarters = tuple(replace(q, revenue=x) for q, x in zip(i.quarter_estimates, means, strict=True))
    return replace(i, quarter_estimates=quarters)


def half_yearly(i: CompanyInputs) -> CompanyInputs:
    """``i`` reporting half-yearly (spec 2026-11-10 8): its trailing figures the same sums on the
    half-year cadence, two periods, and its four NTM quarters as two consensus half-years, each
    the second of its two quarters with the two quarters' means summed."""
    assert i.trailing is not None and len(i.quarter_estimates) == 4
    q = i.quarter_estimates
    halves = (_half_year(q[0], q[1], "H1"), _half_year(q[2], q[3], "H2"))
    trailing = replace(i.trailing, quarters=2, cadence="half-yearly")
    return replace(i, trailing=trailing, quarter_estimates=halves)


def _half_year(first: QuarterEstimate, second: QuarterEstimate, label: str) -> QuarterEstimate:
    return replace(
        second,
        fiscal_period=label,
        eps=_plus(first.eps, second.eps),
        revenue=_plus(first.revenue, second.revenue),
        net_income=_plus(first.net_income, second.net_income),
    )


def _plus(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


def universe_deciles() -> Deciles:
    """The classifier tests' universe: 8% revenue growth is decile 6 ("Moderate"), 2% is decile 4
    ("Low"); a margin slope of 1.5 points a year is decile 9 ("Rising"), -1.5 points decile 2
    ("Declining") and a flat margin decile 6 ("Stable")."""
    return Deciles(
        growth_edges=(-0.10, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.30),
        margin_slope_edges=(-0.03, -0.012, -0.01, -0.005, 0.0, 0.005, 0.01, 0.012, 0.03),
        n_growth=100,
        n_margin=80,
        refresh_id=1,
    )


def mature_growth_inputs() -> CompanyInputs:
    """A Mature Growth company: revenue up 8% a year from $10 bn, the operating margin up 1.5
    points a year from 15% to 30%, an aggregate ROIC near 22% and a Wide moat. The NTM consensus
    is $5.90 a share, the annual path 12% then 10%, and the price $150."""
    series = fiscal_years(
        [10_000e6 * 1.08**k for k in range(11)], [0.15 + 0.015 * k for k in range(11)]
    )
    return CompanyInputs(
        symbol="MGCO",
        name="Mature Growth Co",
        country="United States",
        currency="USD",
        is_adr=False,
        market_cap=150_000e6,
        price=150.0,
        price_date=date(2026, 10, 30),
        shares_diluted=1_000e6,
        series=series,
        capital_years=capital_years(series),
        tax_rate_latest=0.25,
        trailing=TrailingFigures(
            period_end=date(2026, 9, 30),
            quarters=4,
            on_fiscal_year=False,
            revenue=22_800e6,
            operating_income=7_000e6,
            net_income=5_300e6,
            eps_diluted=5.30,
            sbc=400e6,
            cfo=6_000e6,
            capex=-1_400e6,
            dividends=-1_000e6,
            buybacks=-2_000e6,
            equity_issued=100e6,
        ),
        quarter_estimates=(
            quarter(date(2026, 12, 31), 2026, "Q4", 1.40),
            quarter(date(2027, 3, 31), 2027, "Q1", 1.45),
            quarter(date(2027, 6, 30), 2027, "Q2", 1.50),
            quarter(date(2027, 9, 30), 2027, "Q3", 1.55),
        ),
        annual_estimates=(
            annual(2027, 6_000e6, 6.00, 12),
            annual(2028, 6_720e6, 6.72, 10),
            annual(2029, 7_392e6, 7.39, 6),
        ),
        street_ttm_eps=5.35,  # 0.05 above GAAP, under half the after-tax SBC: SBC is a cost
        moat_class="Wide",
        next_earnings=date(2027, 1, 28),
        closes=weekday_closes(date(2024, 10, 31), DATA_DATE, 100.0, 150.0),
        data_date=DATA_DATE,
        provenance={
            **{name: Provenance(src, DATA_DATE, OBSERVED, None) for name, src in SOURCES.items()},
            "moat_class": MOAT_FILE,
        },
        input_flags=(),
        refusal=None,
    )


def mature_stable_inputs() -> CompanyInputs:
    """A Mature Stable company: revenue up 2% a year from $20 bn at a flat 20% operating margin,
    a Wide moat, no consensus, and a price of $40 on 1 bn shares. Its E is its trailing net income,
    $3,400 m: the engine takes no non-recurring gap (spec 2026-11-19 7.1)."""
    series = fiscal_years([20_000e6 * 1.02**k for k in range(11)], [0.20] * 11)
    return replace(
        mature_growth_inputs(),
        symbol="MSCO",
        name="Mature Stable Co",
        market_cap=40_000e6,
        price=40.0,
        series=series,
        capital_years=capital_years(series),
        trailing=TrailingFigures(
            period_end=date(2026, 9, 30),
            quarters=4,
            on_fiscal_year=False,
            revenue=24_000e6,
            operating_income=4_800e6,
            net_income=3_400e6,
            eps_diluted=3.40,
            sbc=100e6,
            cfo=4_500e6,
            capex=-1_000e6,
            dividends=-1_500e6,
            buybacks=-500e6,
            equity_issued=0.0,
        ),
        quarter_estimates=(),
        annual_estimates=(),
        street_ttm_eps=None,
        closes=weekday_closes(date(2024, 10, 31), DATA_DATE, 38.0, 40.0),
    )


def _growth_revenue() -> list[float]:
    """The growth companies' revenue: up 35% a year from $1 bn, fiscal 2018 to 2025."""
    return [1_000e6 * 1.35**k for k in range(8)]


def high_growth_inputs() -> CompanyInputs:
    """A High Growth company: revenue up 35% a year from $1 bn over eight fiscal years, the
    operating margin negative and improving three points a year from -30% to -9%; the moat class
    None, 100 m shares at $150. Trailing revenue is $10 bn at a -9% margin. The NTM consensus is
    $12.4 bn of revenue (24% above trailing) at a loss a share; the annual revenue consensus from
    fiscal 2027 grows 23.1% then 20%, on 20, 15 and 12 revenue analysts and 3 EPS analysts. Three
    mature peers at margins of 10%, 20% and 30%; debt $1 bn and cash $3 bn, from the newest
    balance sheet, fiscal 2025's, cited as of its period end, which presents no minority
    interest."""
    series = fiscal_years(_growth_revenue(), [-0.30 + 0.03 * k for k in range(8)])
    grown = replace(
        mature_growth_inputs(),
        symbol="HGCO",
        name="High Growth Co",
        market_cap=15_000e6,
        shares_diluted=100e6,
        series=series,
        capital_years=capital_years(series),
        trailing=TrailingFigures(
            period_end=date(2026, 9, 30),
            quarters=4,
            on_fiscal_year=False,
            revenue=10_000e6,
            operating_income=-900e6,
            net_income=-800e6,
            eps_diluted=-8.00,
            sbc=900e6,
            cfo=-200e6,
            capex=-500e6,
            dividends=0.0,
            buybacks=0.0,
            equity_issued=300e6,
        ),
        quarter_estimates=(
            quarter(date(2026, 12, 31), 2026, "Q4", -1.20, 2_800e6),
            quarter(date(2027, 3, 31), 2027, "Q1", -1.00, 3_000e6),
            quarter(date(2027, 6, 30), 2027, "Q2", -0.80, 3_200e6),
            quarter(date(2027, 9, 30), 2027, "Q3", -0.60, 3_400e6),
        ),
        annual_estimates=(
            annual(2027, -300e6, -3.00, 3, 13_000e6, 20),
            annual(2028, -100e6, -1.00, 3, 16_000e6, 15),
            annual(2029, 100e6, 1.00, 3, 19_200e6, 12),
        ),
        street_ttm_eps=None,
        moat_class="None",
        peers=(
            PeerFigures("PEER1", 10e9, 0.10, 10, 2.5, 0.12),
            PeerFigures("PEER2", 50e9, 0.20, 10, 1.5, 0.20),
            PeerFigures("PEER3", 20e9, 0.30, 10, 3.0, 0.15),
        ),
        debt=1_000e6,
        cash=3_000e6,
    )
    return on_sheet(grown, fiscal_sheet(series))


def young_growth_inputs() -> CompanyInputs:
    """A Young Growth company: the High Growth company with an operating margin that falls three
    points a year from -5% instead. Its revenue, invested capital, trailing figures, consensus and
    peers are the High Growth company's, so the two value the same, the phase apart."""
    series = fiscal_years(_growth_revenue(), [-0.05 - 0.03 * k for k in range(8)])
    return replace(
        high_growth_inputs(),
        symbol="YGCO",
        name="Young Growth Co",
        series=series,
        capital_years=capital_years(series),
    )


def decline_inputs() -> CompanyInputs:
    """Spec 13.1's Decline row, money in USD millions and 100 m shares, so a share's figures are
    the spec's: five fiscal years from 2021 with revenue 1,125, 1,200, 1,120, 1,050 and 1,000 (a
    five-year slope of −40 a year, so d = −4%; growth −5.9% a year, "Close to zero or negative" on
    the test deciles; three falls in four steps) at operating margins of 7%, 8%, 8%, 9% and 8%;
    trailing revenue 1,000 and operating income 80; a kept ROIC year (2025) with revenue 1,000 on
    an average invested capital of 500; the NTM consensus revenue 970 and the annual consensus
    falling 3% a year from fiscal 2027; interest 20 over the four quarters, debt 200, cash 100;
    two balance sheets, the newest with current assets 300 and total liabilities 500 (Altman Z″
    3.07, safe; Piotroski F 6 of 9), which is the newest balance sheet the floor reads (NCAV
    −200, no floor), cited as of its period end and presenting no minority interest; price $3.00.
    The value is $4.9533 a share, rating A−."""
    series = fiscal_years(
        [1_125e6, 1_200e6, 1_120e6, 1_050e6, 1_000e6], [0.07, 0.08, 0.08, 0.09, 0.08]
    )
    capital = tuple(
        CapitalYear(
            year=year,
            operating_income=income,
            tax_rate=0.25,
            total_current_assets=300e6,
            cash_and_investments=100e6,
            total_current_liabilities=200e6,
            short_term_debt=20e6,
            current_lease_liability=0.0,
            net_ppe=480e6,  # invested capital: (300 − 100) − (200 − 20) + 480 = 500
            lease_rou_asset=0.0,
            goodwill=0.0,
            intangibles=0.0,
        )
        for year, income in ((2024, 94.5e6), (2025, 80e6))
    )
    declining = replace(
        mature_growth_inputs(),
        symbol="DCCO",
        name="Decline Co",
        market_cap=300e6,
        price=3.0,
        shares_diluted=100e6,
        series=series,
        capital_years=capital,
        trailing=TrailingFigures(
            period_end=date(2026, 9, 30),
            quarters=4,
            on_fiscal_year=False,
            revenue=1_000e6,
            operating_income=80e6,
            net_income=45e6,
            eps_diluted=0.45,
            sbc=5e6,
            cfo=100e6,
            capex=-30e6,
            dividends=-20e6,
            buybacks=0.0,
            equity_issued=0.0,
            interest_expense=20e6,
            depreciation=40e6,
        ),
        quarter_estimates=(
            quarter(date(2026, 12, 31), 2026, "Q4", 0.11, 245e6),
            quarter(date(2027, 3, 31), 2027, "Q1", 0.11, 243e6),
            quarter(date(2027, 6, 30), 2027, "Q2", 0.11, 242e6),
            quarter(date(2027, 9, 30), 2027, "Q3", 0.11, 240e6),
        ),
        annual_estimates=(
            annual(2027, 43e6, 0.43, 8, 1_000e6, 10),
            annual(2028, 41e6, 0.41, 7, 970e6, 8),
            annual(2029, 39e6, 0.39, 6, 940.9e6, 6),
        ),
        street_ttm_eps=None,
        moat_class="None",
        closes=weekday_closes(date(2024, 10, 31), DATA_DATE, 4.0, 3.0),
        debt=200e6,
        cash=100e6,
        balance_years=(
            BalanceYear(
                year=2024,
                period_end=date(2024, 12, 31),
                total_current_assets=310e6,
                total_current_liabilities=210e6,
                total_assets=900e6,
                total_liabilities=480e6,
                retained_earnings=240e6,
                equity=420e6,
                long_term_debt=200e6,
                revenue=1_050e6,
                gross_profit=360e6,
                operating_income=94.5e6,
                net_income=55e6,
                cfo=105e6,
                stock_issued=0.0,
            ),
            BalanceYear(
                year=2025,
                period_end=date(2025, 12, 31),
                total_current_assets=300e6,
                total_current_liabilities=200e6,
                total_assets=900e6,
                total_liabilities=500e6,
                retained_earnings=250e6,
                equity=400e6,
                long_term_debt=180e6,
                revenue=1_000e6,
                gross_profit=340e6,
                operating_income=80e6,
                net_income=45e6,
                cfo=100e6,
                stock_issued=0.0,
            ),
        ),
    )
    return on_sheet(declining, fiscal_sheet(series, 300e6, 500e6))


def start_up_inputs() -> CompanyInputs:
    """Spec 13.2's Start-up row, money in USD as the spec states it: five fiscal years from 2021
    with no revenue and an operating loss of 50 a year; trailing revenue 0 and operating income
    −50; trailing operating cash flow −60 and capital spending −15, a burn of 75 a year; three
    mature peers at margins of 20%, 25% and 30% (target 25%) and sales-to-capital of 1.0, 1.5 and
    2.0 (median 1.5); tax 25%; the moat class None; no kept ROIC year; a market cap of 2,000 on
    100 diluted shares at $20; debt 0 and cash 300, from the newest balance sheet, fiscal 2025's,
    cited as of its period end, which presents no minority interest. EV_price is 1,700, the
    year-10 revenue the price needs 1,725.73, the cash floor $3.00 a share and the burn cover 4.0
    years."""
    series = tuple(
        replace(fy, operating_income=-50.0, cfo=-60.0, cfi=-15.0, cff=0.0, capex=-15.0)
        for fy in fiscal_years([0.0] * 5, [0.0] * 5)
    )
    starting = replace(
        mature_growth_inputs(),
        symbol="SUCO",
        name="Start-up Co",
        market_cap=2_000.0,
        price=20.0,
        shares_diluted=100.0,
        series=series,
        capital_years=(),
        trailing=TrailingFigures(
            period_end=date(2026, 9, 30),
            quarters=4,
            on_fiscal_year=False,
            revenue=0.0,
            operating_income=-50.0,
            net_income=-48.0,
            eps_diluted=-0.48,
            sbc=5.0,
            cfo=-60.0,
            capex=-15.0,
            dividends=0.0,
            buybacks=0.0,
            equity_issued=0.0,
        ),
        quarter_estimates=(),
        annual_estimates=(),
        street_ttm_eps=None,
        moat_class="None",
        closes=weekday_closes(date(2024, 10, 31), DATA_DATE, 25.0, 20.0),
        peers=(
            PeerFigures("PEER1", 10e9, 0.20, 10, 1.0, 0.12),
            PeerFigures("PEER2", 50e9, 0.25, 10, 1.5, 0.20),
            PeerFigures("PEER3", 20e9, 0.30, 10, 2.0, 0.15),
        ),
        debt=0.0,
        cash=300.0,
    )
    return on_sheet(starting, fiscal_sheet(series))


SEK_RATE = 8.0  # SEK per USD on the price date
SEK_DIFFERENTIAL = 0.02  # spec 2026-11-10 11.1's test table: SEK at 4.04% against USD at 2.00%
FX_DATE = date(2026, 10, 31)  # the price date and the rate's close of a company in SEK
_PER_SHARE = frozenset({"eps", "eps_diluted"})  # the figures a share among the records' fields
_NOT_MONEY = frozenset({"tax_rate"})  # the one float field of the records that is not money


def _scaled[R](row: R, total: float, per_share: float) -> R:
    """``row``, a record of the inputs, with every money figure × ``total`` and every figure a
    share × ``per_share``: each float field but the tax rate."""
    changes: dict[str, Any] = {}
    for f in fields(row):  # type: ignore[arg-type]
        value = getattr(row, f.name)
        if isinstance(value, float) and f.name not in _NOT_MONEY:
            changes[f.name] = value * (per_share if f.name in _PER_SHARE else total)
    return replace(row, **changes)  # type: ignore[type-var]


def _times(x: float | None, k: float) -> float | None:
    return None if x is None else x * k


def _restated(i: CompanyInputs, total: float, per_share: float) -> CompanyInputs:
    """``i`` with every money figure of its statements, consensus and balance sheets × ``total``
    and every figure a share × ``per_share``; its price, market cap, share count and peers as they
    were."""
    return replace(
        i,
        series=tuple(_scaled(fy, total, per_share) for fy in i.series),
        capital_years=tuple(_scaled(cy, total, per_share) for cy in i.capital_years),
        trailing=None if i.trailing is None else _scaled(i.trailing, total, per_share),
        quarter_estimates=tuple(_scaled(q, total, per_share) for q in i.quarter_estimates),
        annual_estimates=tuple(_scaled(a, total, per_share) for a in i.annual_estimates),
        street_ttm_eps=_times(i.street_ttm_eps, per_share),
        debt=_times(i.debt, total),
        cash=_times(i.cash, total),
        sheet=None if i.sheet is None else _scaled(i.sheet, total, per_share),
        balance_years=tuple(_scaled(b, total, per_share) for b in i.balance_years),
    )


def in_sek(
    i: CompanyInputs, rate: float = SEK_RATE, differential: float = SEK_DIFFERENTIAL
) -> CompanyInputs:
    """``i`` reporting in SEK, as assembly hands such a company to the engine: every money figure
    of its statements, consensus and balance sheets × ``rate`` (SEK per USD on the price date,
    2026-10-31), the street actuals among them; the quote's price and market
    cap in USD, the peers' market caps too; the rate and the inflation differential
    ``differential`` cited, the differential with its note."""
    restated = _restated(i, rate, rate)
    imf = "IMF World Economic Outlook, October 2026: inflation, average consumer prices (PCPIPCH)"
    return replace(
        restated,
        currency="SEK",
        series=tuple(replace(fy, currency="SEK") for fy in restated.series),
        price_date=FX_DATE,
        fx_rate=rate,
        fx_date=FX_DATE,
        inflation_differential=differential,
        provenance={
            **i.provenance,
            "fx_rate": Provenance("FMP historical-price-eod/light USDSEK", FX_DATE, OBSERVED, None),
            "inflation_differential": Provenance(imf, date(2026, 10, 8), None, None),
        },
        notes={
            **i.notes,
            "inflation_differential": "SEK 4.040% against USD 2.000%, the IMF World Economic "
            "Outlook October 2026 means of 2027 to 2031",
        },
    )


def fx_inputs() -> CompanyInputs:
    """FXCO, spec 2026-11-10 11.2's company: the Mature Growth company at a tenth of its size,
    100 m shares, reporting in SEK at 8.0 SEK per USD on 2026-10-31 with an inflation differential
    of 2%. It quotes USD 50.00 for a market cap of USD 5,000 m, so its route reads a price of
    400.00 and a market cap of 40,000 m in SEK; every total is MGCO's × 0.8 and every figure a
    share MGCO's × 8.0, in SEK."""
    tenth = _restated(mature_growth_inputs(), 0.1, 1.0)
    return replace(
        in_sek(tenth),
        symbol="FXCO",
        name="Foreign Filer Co",
        price=50.0,
        market_cap=5_000e6,
        shares_diluted=100e6,
        closes=weekday_closes(date(2024, 10, 31), DATA_DATE, 40.0, 50.0),
    )


ABOVE_BOUND = "ARS: expected inflation 12.1% above the 10% bound"


def ars_refused_inputs() -> CompanyInputs:
    """ARSX, FXCO reporting in ARS and listed as an ADR of two ordinary shares, refused for its
    currency's expected inflation as assembly hands such a row to the engine (spec 2026-11-10 7.3):
    the code known, no rate read, so no rate, rate date or differential, and ``currency_refused``.
    Its result carries the intermediate ``currency`` alone (fix round 1 of task 6)."""
    return replace(
        fx_inputs(),
        symbol="ARSX",
        currency="ARS",
        is_adr=True,
        adr_ratio=2.0,
        refusal=ABOVE_BOUND,
        fx_rate=1.0,
        fx_date=None,
        inflation_differential=0.0,
        currency_refused=True,
    )


def as_live(inputs: CompanyInputs) -> CompanyInputs:
    """``inputs`` with the statements' and the share count's dates as assembly writes them: the
    statements at the newest fiscal year's end (31 Dec 2025 for HGCO), the share count at the
    newest period's, the trailing period end (30 Sep 2026)."""
    assert inputs.trailing is not None
    p = inputs.provenance
    dated = {
        "statements": replace(p["statements"], as_of=inputs.series[-1].period_end),
        "shares_diluted": replace(p["shares_diluted"], as_of=inputs.trailing.period_end),
    }
    return replace(inputs, provenance=p | dated)


def judged_moat(
    inputs: CompanyInputs, moat: Moat, writer: str, at: datetime, reason: str | None = None
) -> CompanyInputs:
    """``inputs`` on an owner's or an agent's row of the moat table, as assembly reads it (spec
    2026-11-19 8.5): the class ``moat``, judged, cited to ``writer`` ("owner", "agent
    claude-opus-5-5") as of the write's day and entered at ``at``, its note the class with the
    reason after it, where there is one."""
    cited = Provenance(writer, at.date(), None, at)
    note = moat if reason is None else f"{moat}: {reason}"
    return replace(
        inputs,
        moat_class=moat,
        moat_judged=True,
        provenance=inputs.provenance | {"moat_class": cited},
        notes=inputs.notes | {"moat_class": note},
    )
