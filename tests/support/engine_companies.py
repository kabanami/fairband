"""The engine's test companies: the universe deciles and small, complete companies, one for each
phase the engine routes (Mature Growth, Mature Stable, High Growth, Young Growth, Decline,
Start-up).

The engine tests take them as fixtures (``tests/engine/conftest.py``); the web tests value them
and store the results. Money is in USD and shares in units. Fiscal years are calendar years 2015
to 2025, the trailing twelve months end 2026-09-30, the data date is 2026-10-30 and the tests
value on 2026-10-31.
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures
from fairband.engine.balance import BalanceYear
from fairband.engine.classifier import Deciles, FiscalYear, Series
from fairband.engine.revenue_growth import PeerFigures
from fairband.engine.roic import CapitalYear
from fairband.engine.route import CompanyInputs
from fairband.engine.types import Provenance

DATA_DATE = date(2026, 10, 30)
OBSERVED = datetime(2026, 10, 30, 21, 0, tzinfo=UTC)

# Every provenance key the route reads, with the source assembly would cite.
SOURCES = {
    "price": "FMP quote",
    "market_cap": "FMP quote",
    "shares_diluted": "FMP income-statement",
    "statements": "FMP income-statement",
    "estimates_quarter": "FMP analyst-estimates",
    "estimates_annual": "FMP analyst-estimates",
    "street_ttm_eps": "FMP earnings",
    "moat_score": "GuruFocus summary",
    "gf_eps_ttm": "GuruFocus keyratios",
    "gf_eps_without_nri": "GuruFocus keyratios",
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


def universe_deciles() -> Deciles:
    """The classifier tests' universe: 8% revenue growth is decile 6 ("Moderate"), 2% is decile 4
    ("Low"); a margin slope of 1.5 points a year is decile 8 ("Rising"), a flat margin "Stable"."""
    return Deciles(
        growth_edges=(-0.10, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.30),
        margin_slope_edges=(-0.03, -0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02, 0.03),
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
        moat_score=8.0,
        gf_eps_ttm=5.30,
        gf_eps_without_nri=5.25,
        next_earnings=date(2027, 1, 28),
        closes=weekday_closes(date(2024, 10, 31), DATA_DATE, 100.0, 150.0),
        data_date=DATA_DATE,
        provenance={
            name: Provenance(source, DATA_DATE, OBSERVED, None) for name, source in SOURCES.items()
        },
        input_flags=(),
        refusal=None,
    )


def mature_stable_inputs() -> CompanyInputs:
    """A Mature Stable company: revenue up 2% a year from $20 bn at a flat 20% operating margin,
    a Wide moat, no consensus, and a price of $40 on 1 bn shares. A non-recurring gain of $0.10
    a share comes off trailing net income."""
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
        gf_eps_ttm=3.40,
        gf_eps_without_nri=3.30,
        closes=weekday_closes(date(2024, 10, 31), DATA_DATE, 38.0, 40.0),
    )


def _growth_revenue() -> list[float]:
    """The growth companies' revenue: up 35% a year from $1 bn, fiscal 2018 to 2025."""
    return [1_000e6 * 1.35**k for k in range(8)]


def high_growth_inputs() -> CompanyInputs:
    """A High Growth company: revenue up 35% a year from $1 bn over eight fiscal years, the
    operating margin negative and improving three points a year from -30% to -9%; no moat score,
    100 m shares at $150. Trailing revenue is $10 bn at a -9% margin. The NTM consensus is $12.4 bn
    of revenue (24% above trailing) at a loss a share; the annual revenue consensus from fiscal
    2027 grows 23.1% then 20%, on 20, 15 and 12 revenue analysts and 3 EPS analysts. Three mature
    peers at margins of 10%, 20% and 30%; debt $1 bn and cash $3 bn."""
    series = fiscal_years(_growth_revenue(), [-0.30 + 0.03 * k for k in range(8)])
    return replace(
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
        moat_score=None,
        gf_eps_ttm=-8.00,
        gf_eps_without_nri=-8.00,
        peers=(
            PeerFigures("PEER1", 10e9, 0.10, 10, 2.5, 0.12),
            PeerFigures("PEER2", 50e9, 0.20, 10, 1.5, 0.20),
            PeerFigures("PEER3", 20e9, 0.30, 10, 3.0, 0.15),
        ),
        debt=1_000e6,
        cash=3_000e6,
    )


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
    3.07, safe; Piotroski F 6 of 9); price $3.00. The value is $4.3180 a share, rating A−."""
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
    return replace(
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
        moat_score=None,
        gf_eps_ttm=0.45,
        gf_eps_without_nri=0.45,
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


def start_up_inputs() -> CompanyInputs:
    """Spec 13.2's Start-up row, money in USD as the spec states it: five fiscal years from 2021
    with no revenue and an operating loss of 50 a year; trailing revenue 0 and operating income
    −50; trailing operating cash flow −60 and capital spending −15, a burn of 75 a year; three
    mature peers at margins of 20%, 25% and 30% (target 25%) and sales-to-capital of 1.0, 1.5 and
    2.0 (median 1.5); tax 25%; no moat score; no kept ROIC year; a market cap of 2,000 on 100
    diluted shares at $20; debt 0 and cash 300. EV_price is 1,700, the year-10 revenue the price
    needs 1,725.73, the cash floor $3.00 a share and the burn cover 4.0 years."""
    series = tuple(
        replace(fy, operating_income=-50.0, cfo=-60.0, cfi=-15.0, cff=0.0, capex=-15.0)
        for fy in fiscal_years([0.0] * 5, [0.0] * 5)
    )
    return replace(
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
        moat_score=None,
        gf_eps_ttm=-0.48,
        gf_eps_without_nri=-0.48,
        closes=weekday_closes(date(2024, 10, 31), DATA_DATE, 25.0, 20.0),
        peers=(
            PeerFigures("PEER1", 10e9, 0.20, 10, 1.0, 0.12),
            PeerFigures("PEER2", 50e9, 0.25, 10, 1.5, 0.20),
            PeerFigures("PEER3", 20e9, 0.30, 10, 2.0, 0.15),
        ),
        debt=0.0,
        cash=300.0,
    )
