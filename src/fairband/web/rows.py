"""The API's JSON shapes: a snapshot and its company as one screen row, an admitted company not yet
valued as a placeholder row, the rows grouped for the group view, and the company, snapshot,
refresh and progress records as the routes send them.

A screen row carries the ``ScreenRow`` keys of the design system's ``index.d.ts`` (``ticker`` to
``freshness``), so the page hands rows to ``ScreenTable`` as they come, and, in the same
camelCase, the extra columns of spec 6.3. Numbers are JSON numbers or ``None``; dates and
timestamps are ISO text. Nothing is reviewed in this cut: ``reviewed`` is ``None``, ``overrides``
is 0 and ``mechanical`` is the snapshot's value.
"""

import statistics
from collections.abc import Sequence
from datetime import date
from typing import Any

from fairband.engine.levels import validity_state
from fairband.engine.types import PHASE_NUMBER
from fairband.refresh.run import UNCLASSIFIED, Progress
from fairband.store.companies import CompanyRow
from fairband.store.refreshes import RefreshRow
from fairband.store.snapshots import SnapshotRow

NOT_YET_VALUED = "not yet valued"
GROUP_BY = ("sector", "phase", "cap")
NONE = "none"  # the group of the rows with no sector, or no cap band
_PHASE_NAMES = {number: name for name, number in PHASE_NUMBER.items()}

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
    "priceToValue",
    "designation",
    "priceDate",
    "dataDate",
    "validUntil",
    "route",
    "growthRouteValue",
    "targetMargin",
    "impliedMargin",
    "requiredRevenue",
    "burnCover",
    "rating",
    "distressProbability",
    "altmanZ",
    "piotroskiF",
    "impliedDeclineRate",
)
ROW_KEYS = SCREEN_ROW_KEYS + EXTRA_KEYS

# ScreenTable's thirteen column keys, in its order. Two draw a row key under another name: band
# (fairLow to fairHigh) and entered (enteredAt). The designation draws its own extra key.
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
    "designation",
    "overrides",
    "entered",
)
# Each column once: an extra key that is also a design column keeps its design place.
COLUMNS = DESIGN_COLUMNS + tuple(key for key in EXTRA_KEYS if key not in DESIGN_COLUMNS)


def screen_row(
    snapshot: SnapshotRow, company: CompanyRow | None, today: date, aging_fraction: float
) -> dict[str, Any]:
    """The snapshot as a screen row; the name, sector, cap band and market cap come from
    ``company``, ``None`` without one. ``freshness`` is the validity state on ``today``. The moat
    shows on a row with a value only: a growth refusal keeps the moat class for the price refresh,
    not for the screen. ``targetMargin`` is the peers' target and ``impliedMargin`` the margin the
    price needs, a growth row's; a row refused for its target margin has the latter alone.

    A Start-up row has ``requiredRevenue``, the year-10 revenue its price needs (``None`` when the
    requirement has a reason), and ``burnCover``, the years its cash covers the trailing burn
    (``None`` when not burning). A Decline row has its synthetic ``rating`` ("—" with no net debt,
    ``None`` unavailable), ``distressProbability`` π, ``altmanZ``, ``piotroskiF`` ("6 of 9") and
    the ``impliedDeclineRate``. A Decline row refused for a value at or below zero keeps them but
    the last, and has no route: each is read from the intermediates, which no other route
    writes."""
    result = snapshot.result
    phase = result.phase.phase
    im = result.intermediates
    multiples = _table(im, "multiples")
    facts = _table(im, "price_facts")
    rating = _table(im, "rating")
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
        "moat": None if snapshot.value is None else im.get("moat"),
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
        "priceToValue": snapshot.price_to_value,
        "designation": snapshot.designation,
        "priceDate": _iso(snapshot.price_date),
        "dataDate": snapshot.data_date.isoformat(),
        "validUntil": snapshot.valid_until.isoformat(),
        "route": snapshot.route,
        "growthRouteValue": _growth_route_value(snapshot),
        "targetMargin": _table(im, "target_margin").get("value"),
        "impliedMargin": im.get("implied_margin"),
        "requiredRevenue": _table(im, "requirement").get("revenue_y10"),
        "burnCover": _burn_cover(im),
        "rating": rating.get("rating"),
        "distressProbability": rating.get("pi"),
        "altmanZ": _table(im, "altman_z").get("score"),
        "piotroskiF": _piotroski_f(im),
        "impliedDeclineRate": im.get("implied_decline_rate"),
    }


def _growth_route_value(snapshot: SnapshotRow) -> float | None:
    """The growth route's value a share: a Mature Growth row's own value, a Mature Stable or
    revenue-growth row's cross-check (calibration spec 5.7, growth-routes spec 5.12) when it has
    one; ``None`` elsewhere."""
    if snapshot.route == "mature-growth":
        return snapshot.value
    if snapshot.route in ("mature-stable", "revenue-growth"):
        return _table(snapshot.result.intermediates, "growth_route").get("value_per_share")
    return None


def _burn_cover(im: dict[str, Any]) -> float | None:
    """A Start-up row's years of cash at the trailing burn; ``None`` when it is not burning, has
    no trailing cash flows, or is not a Start-up row."""
    cover = im.get("burn_cover_years")
    return cover if isinstance(cover, float) else None


def _piotroski_f(im: dict[str, Any]) -> str | None:
    """A Decline row's Piotroski F as its score of the signals read, "6 of 9"; ``None`` without a
    score or with no signal read."""
    f = _table(im, "piotroski_f")
    return f"{f['score']} of {f['read']}" if f.get("read") else None


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


def group_rows(
    rows: Sequence[dict[str, Any]], by: str, edges: tuple[float, float, float, float]
) -> list[dict[str, Any]]:
    """The rows grouped by ``by`` (``GROUP_BY``), ordered by group name. A group's name is the
    sector, the engine's phase name (``unclassified`` without a phase) or the cap band; ``none``
    for a row without a sector or a cap band. Each group gives its row count, the rows with a
    value (``valued``), the median of price ÷ value over the valued rows with a positive price,
    and the share of the valued rows whose price ÷ value is below the second designation edge
    (``edges[1]``: the ``below`` and ``well-below`` bands); ``None`` for the last two when they
    cover no row."""
    named: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        named.setdefault(_group_name(row, by), []).append(row)
    return [_group(name, members, edges[1]) for name, members in sorted(named.items())]


def _group_name(row: dict[str, Any], by: str) -> str:
    if by == "phase":
        phase = row["phase"]
        return UNCLASSIFIED if phase is None else _PHASE_NAMES[phase]
    name = row["sector"] if by == "sector" else row["capBand"]
    return NONE if name is None else str(name)


def _group(name: str, rows: list[dict[str, Any]], below_value: float) -> dict[str, Any]:
    valued = [r for r in rows if r["mechanical"] is not None]
    priced = [r for r in valued if r["price"] is not None and r["price"] > 0]
    ratios = [r["price"] / r["mechanical"] for r in priced]
    below = [x for x in ratios if x < below_value]
    return {
        "name": name,
        "count": len(rows),
        "valued": len(valued),
        "medianPriceToValue": statistics.median(ratios) if ratios else None,
        "shareBelowValue": len(below) / len(valued) if valued else None,
    }


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


def progress_json(progress: Progress, kind: str | None) -> dict[str, Any]:
    return {
        "id": progress.refresh_id,
        "kind": kind,
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
