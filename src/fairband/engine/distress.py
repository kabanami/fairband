"""The distress measures of the Decline route (spec 2026-11-03 sections 10.6 to 10.8): the
synthetic rating and its ten-year probability of default π, Altman's Z″, Piotroski's F and
Graham's net current asset value.

Pure functions on plain figures and ``BalanceYear`` records; the route decides what each one
changes. π weights the distress-sale value (10.7) and the net current asset value floors the
run-off (10.6); Z″ and F are shown, never deciding the value (10.8). The Z″ coefficients and the
nine Piotroski signals are the models' own, in code (method 4.1a); the rating table, the default
probabilities and the Z″ zones are policy.
"""

from dataclasses import dataclass
from typing import Literal

from fairband.engine.balance import BalanceYear
from fairband.policy import Policy

ZZone = Literal["distress", "grey", "safe"]

# Altman's Z″, the non-manufacturer form (Altman 2000): X1 to X4's coefficients.
_Z_COEFFICIENTS = (6.56, 3.26, 6.72, 1.05)


@dataclass(frozen=True)
class Rating:
    """A synthetic rating (10.7): the rating, the interest coverage it was read from (EBIT ÷
    interest; ``None`` with no net debt), the ten-year probability of default ``pi`` as a
    fraction, and ``note`` "no net debt" when cash covers debt, else ``None``."""

    rating: str
    coverage: float | None
    pi: float
    note: str | None


@dataclass(frozen=True)
class ZScore:
    """Altman's Z″ (10.8): the four ratios, the score and its zone."""

    x1: float
    x2: float
    x3: float
    x4: float
    score: float
    zone: ZZone


@dataclass(frozen=True)
class FScore:
    """Piotroski's F (10.8): the nine signals by name in the spec's order, each ``True``,
    ``False`` or ``None`` (not read); ``score`` counts the ``True`` and ``read`` the not ``None``."""

    signals: tuple[tuple[str, bool | None], ...]
    score: int
    read: int


def rate(
    ebit: float, interest: float | None, debt: float, cash: float, policy: Policy
) -> Rating | None:
    """The synthetic rating and π by spec 10.7's rules, the first that fits deciding:

    1. cash at or above debt: no rating, π 0, "no net debt";
    2. net debt with ``interest`` ``None`` or 0: ``None``, π unavailable;
    3. coverage ``ebit ÷ interest``; an ``ebit`` at or below zero takes the lowest row (D)
       whatever the interest, else the last ``synthetic_rating`` row whose ``coverage_min`` is at
       or below the coverage;
    4. π is ``default_probability_10y`` of the rating.

    ``interest`` is the trailing expense as its size (method 4.2), so the coverage takes it as
    given."""
    if cash >= debt:
        return Rating("—", None, 0.0, "no net debt")
    if interest is None or interest == 0:
        return None
    coverage = ebit / interest
    table = policy.synthetic_rating
    if ebit <= 0:
        rating = table[0].rating
    else:
        rating = next(row.rating for row in reversed(table) if row.coverage_min <= coverage)
    return Rating(rating, coverage, policy.default_probability_10y[rating], None)


def altman_z(y: BalanceYear, policy: Policy) -> ZScore | None:
    """Z″ = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4 on one fiscal year: X1 working capital
    (current assets − current liabilities), X2 retained earnings and X3 operating income, each ÷
    total assets; X4 equity ÷ total liabilities. Below ``z_distress`` "distress", above ``z_safe``
    "safe", else "grey" (a score on an edge is "grey"). ``None`` when any of the seven lines is
    missing, or total assets or total liabilities is at or below zero."""
    ca, cl = y.total_current_assets, y.total_current_liabilities
    assets, liabilities = y.total_assets, y.total_liabilities
    retained, equity, ebit = y.retained_earnings, y.equity, y.operating_income
    if (
        ca is None
        or cl is None
        or assets is None
        or liabilities is None
        or retained is None
        or equity is None
        or ebit is None
    ):
        return None
    if assets <= 0 or liabilities <= 0:
        return None
    x1, x2, x3, x4 = (ca - cl) / assets, retained / assets, ebit / assets, equity / liabilities
    c1, c2, c3, c4 = _Z_COEFFICIENTS
    score = c1 * x1 + c2 * x2 + c3 * x3 + c4 * x4
    zone: ZZone = "grey"
    if score < policy.z_distress:
        zone = "distress"
    elif score > policy.z_safe:
        zone = "safe"
    return ZScore(x1, x2, x3, x4, score, zone)


def piotroski_f(this: BalanceYear, last: BalanceYear) -> FScore:
    """The nine signals of spec 10.8 on ``this`` fiscal year against ``last``, in order:
    ``roa_positive`` (net income ÷ total assets above zero), ``cfo_positive``, ``roa_up``,
    ``accrual`` (operating cash flow above net income), ``leverage_down`` (long-term debt ÷
    total assets lower), ``liquidity_up`` (current ratio higher), ``no_issuance`` (stock issued
    at or below zero), ``gross_margin_up`` (gross profit ÷ revenue higher) and ``turnover_up``
    (revenue ÷ total assets higher).

    A signal whose line is missing, or whose ratio has a zero denominator, is ``None``. The
    exception is ``no_issuance``: a missing stock-issued line reads as no issuance recorded, so
    the signal is ``True`` and always read."""
    roa = _ratio(this.net_income, this.total_assets)
    signals = (
        ("roa_positive", _above(roa, 0.0)),
        ("cfo_positive", _above(this.cfo, 0.0)),
        ("roa_up", _above(roa, _ratio(last.net_income, last.total_assets))),
        ("accrual", _above(this.cfo, this.net_income)),
        (
            "leverage_down",
            _above(
                _ratio(last.long_term_debt, last.total_assets),
                _ratio(this.long_term_debt, this.total_assets),
            ),
        ),
        (
            "liquidity_up",
            _above(
                _ratio(this.total_current_assets, this.total_current_liabilities),
                _ratio(last.total_current_assets, last.total_current_liabilities),
            ),
        ),
        ("no_issuance", this.stock_issued is None or this.stock_issued <= 0),
        (
            "gross_margin_up",
            _above(
                _ratio(this.gross_profit, this.revenue), _ratio(last.gross_profit, last.revenue)
            ),
        ),
        (
            "turnover_up",
            _above(
                _ratio(this.revenue, this.total_assets), _ratio(last.revenue, last.total_assets)
            ),
        ),
    )
    score = sum(1 for _, signal in signals if signal is True)
    read = sum(1 for _, signal in signals if signal is not None)
    return FScore(signals, score, read)


def ncav(y: BalanceYear) -> float | None:
    """Graham's net current asset value (10.6): total current assets − total liabilities;
    ``None`` when either line is missing."""
    if y.total_current_assets is None or y.total_liabilities is None:
        return None
    return y.total_current_assets - y.total_liabilities


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _above(a: float | None, b: float | None) -> bool | None:
    if a is None or b is None:
        return None
    return a > b
