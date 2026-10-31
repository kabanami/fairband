"""FMP statements to facts: the normalized statements and the as-reported balance sheet.

``statement_facts`` stores each field under its FMP name (spec 6.5; the names are verbatim from
source-evidence "R1 statement field binding" and match the documented examples, checked
2026-11-01): one row per field per period, ``period_end`` and ``as_of`` the row's ``date``,
``fiscal_year`` and ``fiscal_period`` from ``fiscalYear`` and ``period``, ``currency`` from
``reportedCurrency``, ``unit`` ``currency``, ``shares`` or ``per-share``. A missing or null field
has no value and the reason ``null``; a value that is not a number, ``unparseable``. A normalized
balance-sheet zero for ``goodwill`` or ``intangibleAssets`` has no value and the reason
``vendor-zero`` (D17 rule Z: the issuer's as-reported balance sheet decides); every other zero is a
real zero.

``as_reported_balance_facts`` (dataset ``balance-asreported-annual``) reads the issuer's XBRL tags
in lower case. The documented response nests them under ``data`` (as source-evidence T055 also
records); a flat row is read the same way. ``intangibles_ex_goodwill`` is the D17 estimate
``bs10-intangibles-total-v1`` (kind ``estimate``), read from the first of
``intangibleassetsnetexcludinggoodwill``, ``finitelivedintangibleassetsnet`` and
``otherintangibleassetsnet`` that holds a value; which tag it came from is not stored.
``lease_rou_asset`` is ``operatingleaserightofuseasset`` and ``current_lease_liability`` is
``operatingleaseliabilitycurrent``. A line the row does not present has no value, kind
``observed`` and the reason ``not-presented``.

A row without a parseable ``date`` is skipped and records nothing; nothing here raises on vendor
data.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from typing import Any

from fairband.store.facts import FactRow
from fairband.vendors._fmp_parse import MONEY, PER_SHARE, SHARES, Source, dated, number

type _Fields = tuple[tuple[str, str], ...]  # (FMP field, unit)

_INCOME: _Fields = (
    ("revenue", MONEY),
    ("operatingIncome", MONEY),
    ("netIncome", MONEY),
    ("eps", PER_SHARE),
    ("epsDiluted", PER_SHARE),
    ("weightedAverageShsOutDil", SHARES),
    ("incomeTaxExpense", MONEY),
    ("incomeBeforeTax", MONEY),
)
_BALANCE: _Fields = tuple(
    (name, MONEY)
    for name in (
        "cashAndCashEquivalents",
        "shortTermInvestments",
        "totalCurrentAssets",
        "totalCurrentLiabilities",
        "shortTermDebt",
        "propertyPlantEquipmentNet",
        "goodwill",
        "intangibleAssets",
        "longTermDebt",
        "totalStockholdersEquity",
    )
)
_CASHFLOW: _Fields = tuple(
    (name, MONEY)
    for name in (
        "netCashProvidedByOperatingActivities",
        "netCashProvidedByInvestingActivities",
        "netCashProvidedByFinancingActivities",
        "capitalExpenditure",
        "stockBasedCompensation",
        "netDividendsPaid",
        "commonStockRepurchased",
        "commonStockIssuance",
    )
)
_STATEMENTS: dict[str, _Fields] = {
    "income-annual": _INCOME,
    "income-quarter": _INCOME,
    "balance-annual": _BALANCE,
    "cashflow-annual": _CASHFLOW,
    "cashflow-quarter": _CASHFLOW,
}
_VENDOR_ZERO = frozenset({"goodwill", "intangibleAssets"})

_AS_REPORTED = "balance-asreported-annual"
_BS10_METHOD = "bs10-intangibles-total-v1"
_BS10_TAGS = (
    "intangibleassetsnetexcludinggoodwill",
    "finitelivedintangibleassetsnet",
    "otherintangibleassetsnet",
)
_LEASE_TAGS = (
    ("lease_rou_asset", "operatingleaserightofuseasset"),
    ("current_lease_liability", "operatingleaseliabilitycurrent"),
)


def statement_facts(
    payload: Any,
    symbol: str,
    dataset: str,
    response_id: int,
    observed_at: datetime,
    entered_at: datetime,
) -> list[FactRow]:
    """One fact per statement field per period. ``dataset`` names the statement and period:
    ``income-annual``, ``income-quarter``, ``balance-annual``, ``cashflow-annual`` or
    ``cashflow-quarter``; any other raises ``ValueError``."""
    if dataset not in _STATEMENTS:
        raise ValueError(f"not an FMP statement dataset: {dataset}")
    source = Source(symbol, response_id, observed_at, entered_at)
    out: list[FactRow] = []
    for row, period_end in dated(payload):
        for name, unit in _STATEMENTS[dataset]:
            value, reason = _parse(row.get(name))
            if dataset == "balance-annual" and name in _VENDOR_ZERO and value == 0:
                value, reason = None, "vendor-zero"
            out.append(source.fact(row, dataset, period_end, name, value, unit, reason))
    return out


def as_reported_balance_facts(
    payload: Any, symbol: str, response_id: int, observed_at: datetime, entered_at: datetime
) -> list[FactRow]:
    """The BS-10 intangibles estimate and the two lease lines per as-reported annual period."""
    source = Source(symbol, response_id, observed_at, entered_at)
    out: list[FactRow] = []
    for row, period_end in dated(payload):
        data = row.get("data")
        tags: Mapping[str, Any] = data if isinstance(data, dict) else row
        bs10 = next((tag for tag in _BS10_TAGS if tags.get(tag) is not None), None)
        for name, tag in (("intangibles_ex_goodwill", bs10), *_LEASE_TAGS):
            raw = None if tag is None else tags.get(tag)
            value, reason = (None, "not-presented") if raw is None else _parse(raw)
            fact = source.fact(row, _AS_REPORTED, period_end, name, value, MONEY, reason)
            if name == "intangibles_ex_goodwill" and value is not None:
                fact = replace(fact, kind="estimate", estimate_method=_BS10_METHOD)
            out.append(fact)
    return out


def _parse(raw: Any) -> tuple[Decimal | None, str | None]:
    """The value and, when there is none, why: ``null`` or ``unparseable``."""
    if raw is None:
        return None, "null"
    value = number(raw)
    return (value, None) if value is not None else (None, "unparseable")
