"""The balance sheets the engine reads. ``BalanceYear``: one fiscal year's balance sheet with the
lines read beside it, the record the Decline route's liquidation floor and distress signals read
(spec 2026-11-03 sections 10.6 and 10.8). ``NewestSheet``: the newest balance sheet on file, a
fiscal year's or a quarter's (spec 2026-11-13 12.2)."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class BalanceYear:
    """A fiscal year with an annual balance sheet, ending at its ``period_end``: the balance
    sheet's lines (``equity`` is ``totalStockholdersEquity``), the same fiscal year's income
    statement lines, and its cash flow's operating cash flow and stock issued
    (``commonStockIssuance``, FMP's sign). A line the statement does not present is ``None``."""

    year: int
    period_end: date
    total_current_assets: float | None
    total_current_liabilities: float | None
    total_assets: float | None
    total_liabilities: float | None
    retained_earnings: float | None
    equity: float | None
    long_term_debt: float | None
    revenue: float | None
    gross_profit: float | None
    operating_income: float | None
    net_income: float | None
    cfo: float | None
    stock_issued: float | None


@dataclass(frozen=True)
class NewestSheet:
    """The newest balance sheet on file, a fiscal year's or a quarter's (spec 2026-11-13 12.2):
    its period, the two lines of the liquidation floor and the minority interest as the sheet
    presents them, each ``None`` when it does not."""

    period_end: date
    label: str  # "fiscal 2026 Q3", "fiscal 2025"
    quarterly: bool
    total_current_assets: float | None
    total_liabilities: float | None
    minority_interest: float | None
