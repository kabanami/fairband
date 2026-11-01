"""The API's JSON shapes: a snapshot and its company as one screen row, an admitted company not yet
valued as a placeholder row, and the company, snapshot, refresh and progress records as the routes
send them.

A screen row carries the ``ScreenRow`` keys of the design system's ``index.d.ts`` (``ticker`` to
``freshness``), so the page hands rows to ``ScreenTable`` as they come, and, in the same
camelCase, the extra columns of spec 6.3. Numbers are JSON numbers or ``None``; dates and
timestamps are ISO text. Nothing is reviewed in this cut: ``reviewed`` is ``None``, ``overrides``
is 0 and ``mechanical`` is the snapshot's value.
"""

from datetime import date
from typing import Any

from fairband.engine.levels import validity_state
from fairband.engine.types import PHASE_NUMBER
from fairband.refresh.run import Progress
from fairband.store.companies import CompanyRow
from fairband.store.refreshes import RefreshRow
from fairband.store.snapshots import SnapshotRow

NOT_YET_VALUED = "not yet valued"

# The design system's ScreenRow keys.
SCREEN_ROW_KEYS = (
    "ticker",
    "name",
    "phase",
    "fairLow",
    "fairHigh",
    "fairValue",
    "buyLevel",
    "trimLevel",
    "price",
    "mechanical",
    "reviewed",
    "overrides",
    "enteredAt",
    "freshness",
)
# The extra columns, each one row key.
EXTRA_KEYS = (
    "sector",
    "capBand",
    "marketCap",
    "moat",
    "impliedGrowth",
    "expectedReturn",
    "epv",
    "peReported",
    "peClean",
    "peForward",
    "high52w",
    "low52w",
    "change1y",
    "change3y",
    "change5y",
    "drawdown",
    "flags",
    "refusal",
    "stance3",
    "stance5",
    "priceDate",
    "dataDate",
    "validUntil",
    "route",
)
ROW_KEYS = SCREEN_ROW_KEYS + EXTRA_KEYS

# ScreenTable's thirteen column keys, in its order. Three draw a row key under another name:
# band (fairLow to fairHigh), stance (from the price and the levels) and entered (enteredAt).
DESIGN_COLUMNS = (
    "ticker",
    "name",
    "phase",
    "band",
    "fairValue",
    "buyLevel",
    "trimLevel",
    "mechanical",
    "reviewed",
    "price",
    "stance",
    "overrides",
    "entered",
)
COLUMNS = DESIGN_COLUMNS + EXTRA_KEYS


def screen_row(
    snapshot: SnapshotRow, company: CompanyRow | None, today: date, aging_fraction: float
) -> dict[str, Any]:
    """The snapshot as a screen row; the name, sector, cap band and market cap come from
    ``company``, ``None`` without one. ``freshness`` is the validity state on ``today``."""
    result = snapshot.result
    phase = result.phase.phase
    im = result.intermediates
    multiples = _table(im, "multiples")
    facts = _table(im, "price_facts")
    market_cap = None if company is None else company.market_cap
    return {
        "ticker": snapshot.symbol,
        "name": None if company is None else company.name,
        "phase": None if phase is None else PHASE_NUMBER[phase],
        "fairLow": snapshot.fair_low,
        "fairHigh": snapshot.fair_high,
        "fairValue": snapshot.value,
        "buyLevel": snapshot.buy_level,
        "trimLevel": snapshot.trim_level,
        "price": snapshot.price,
        "mechanical": snapshot.value,
        "reviewed": None,
        "overrides": 0,
        "enteredAt": snapshot.created_at.isoformat(),
        "freshness": validity_state(
            snapshot.data_date, snapshot.valid_until, today, aging_fraction
        ),
        "sector": None if company is None else company.sector,
        "capBand": None if company is None else company.cap_band,
        "marketCap": None if market_cap is None else float(market_cap),
        "moat": im.get("moat"),
        "impliedGrowth": im.get("implied_growth"),
        "expectedReturn": _table(im, "expected_return").get("total"),
        "epv": im.get("epv"),
        "peReported": multiples.get("pe_reported"),
        "peClean": multiples.get("pe_clean"),
        "peForward": multiples.get("pe_forward"),
        "high52w": facts.get("high_52w"),
        "low52w": facts.get("low_52w"),
        "change1y": facts.get("change_1y"),
        "change3y": facts.get("change_3y"),
        "change5y": facts.get("change_5y"),
        "drawdown": facts.get("drawdown_from_peak"),
        "flags": [f.word for f in result.flags],
        "refusal": snapshot.refusal,
        "stance3": snapshot.stance3,
        "stance5": snapshot.stance5,
        "priceDate": _iso(snapshot.price_date),
        "dataDate": snapshot.data_date.isoformat(),
        "validUntil": snapshot.valid_until.isoformat(),
        "route": snapshot.route,
    }


def placeholder_row(company: CompanyRow) -> dict[str, Any]:
    """The row of an admitted company with no snapshot yet: its name, sector, cap band and
    market cap, the refusal "not yet valued", freshness ``current`` and ``None`` elsewhere (no
    override, as on every row of this cut)."""
    row: dict[str, Any] = dict.fromkeys(ROW_KEYS)
    market_cap = company.market_cap
    row |= {
        "ticker": company.symbol,
        "name": company.name,
        "overrides": 0,
        "freshness": "current",
        "sector": company.sector,
        "capBand": company.cap_band,
        "marketCap": None if market_cap is None else float(market_cap),
        "refusal": NOT_YET_VALUED,
    }
    return row


def sort_rows(rows: list[dict[str, Any]], key: str, descending: bool) -> list[dict[str, Any]]:
    """The rows ordered by ``key``, those where it is ``None`` last in either direction; ties
    keep their order."""
    present = [r for r in rows if r[key] is not None]
    missing = [r for r in rows if r[key] is None]
    return sorted(present, key=lambda r: r[key], reverse=descending) + missing


def company_json(company: CompanyRow) -> dict[str, Any]:
    return {
        "symbol": company.symbol,
        "refreshId": company.refresh_id,
        "name": company.name,
        "exchange": company.exchange,
        "sector": company.sector,
        "industry": company.industry,
        "country": company.country,
        "currency": company.currency,
        "isAdr": company.is_adr,
        "capBand": company.cap_band,
        "marketCap": None if company.market_cap is None else float(company.market_cap),
        "eligible": company.eligible,
        "exclusionReason": company.exclusion_reason,
        "observedAt": company.observed_at.isoformat(),
    }


def snapshot_json(snapshot: SnapshotRow) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "refreshId": snapshot.refresh_id,
        "decilesRefreshId": snapshot.deciles_refresh_id,
        "createdAt": snapshot.created_at.isoformat(),
    }


def refresh_json(refresh: RefreshRow) -> dict[str, Any]:
    return {
        "id": refresh.id,
        "kind": refresh.kind,
        "status": refresh.status,
        "stage": refresh.stage,
        "startedAt": refresh.started_at.isoformat(),
        "finishedAt": _iso(refresh.finished_at),
        "message": refresh.message,
        "calibration": refresh.calibration,
    }


def progress_json(progress: Progress) -> dict[str, Any]:
    return {
        "id": progress.refresh_id,
        "stage": progress.stage,
        "done": progress.done,
        "failed": progress.failed,
        "remaining": progress.remaining,
        "current": progress.current,
    }


def _table(intermediates: dict[str, Any], name: str) -> dict[str, Any]:
    """The intermediate ``name`` when it is a table; an empty one when absent or ``None``."""
    value = intermediates.get(name)
    return value if isinstance(value, dict) else {}


def _iso(d: date | None) -> str | None:
    return None if d is None else d.isoformat()
