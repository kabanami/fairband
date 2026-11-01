"""The engine's test companies: the universe deciles and three small, complete companies.

The engine tests take them as fixtures (``tests/engine/conftest.py``); the web tests value them
and store the results. Money is in USD and shares in units. Fiscal years are calendar years 2015
to 2025, the trailing twelve months end 2026-09-30, the data date is 2026-10-30 and the tests
value on 2026-10-31.
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures
from fairband.engine.classifier import Deciles, FiscalYear, Series
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


def quarter(period_end: date, fiscal_year: int, period: str, eps: float) -> QuarterEstimate:
    return QuarterEstimate(period_end, fiscal_year, period, eps, None, None, 20)


def annual(year: int, net_income: float, eps: float, analysts: int) -> AnnualEstimate:
    return AnnualEstimate(year, date(year, 12, 31), eps, None, net_income, analysts, analysts)


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


def young_growth_inputs() -> CompanyInputs:
    """A Young Growth company: revenue up 35% a year from $1 bn, the operating margin negative
    and falling three points a year."""
    series = fiscal_years(
        [1_000e6 * 1.35**k for k in range(6)], [-0.05 - 0.03 * k for k in range(6)]
    )
    return replace(
        mature_growth_inputs(),
        symbol="YGCO",
        name="Young Growth Co",
        series=series,
        capital_years=capital_years(series),
    )
