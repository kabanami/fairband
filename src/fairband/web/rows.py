"""The API's JSON shapes: a snapshot and its company as one screen row, an admitted company not yet
valued as a placeholder row, the rows grouped for the group view, and the company, snapshot,
refresh and progress records as the routes send them.

A screen row carries the ``ScreenRow`` keys of the design system's ``index.d.ts`` (``ticker`` to
``freshness``), so the page hands rows to ``ScreenTable`` as they come, and, in the same
camelCase, the extra columns of spec 6.3 and after. Numbers are JSON numbers or ``None``; dates
and timestamps are ISO text. ``mechanical`` is the snapshot's value. Every row, a placeholder too,
has ``watchlists``, the ids of the user's lists it is on, and ``flagCount``, the number of its
quality warnings (spec 2026-11-04 9.3 and 9.5).

Every row also has the agents' fields (spec 2026-11-06 Tier 2, 11 and 18.1; ``agent_fields``):
``reviewed`` and ``overrides``, the reviewed value and the count of the overrides inside it, or on
a row the route refused the secondary valuation's value standing in; ``agentStance``, the latest
published report's word, a column; and ``covered``, the coverage mark's record ``{at, actor,
expired}``, which no column draws and nothing sorts by, so it is no row key. Where ``reviewed`` is
filled, the row's band, levels, price ÷ value and designation (``LEVEL_KEYS``) are the filling
record's, the word at the latest price (18.1, plan 3); ``mechanical`` stays the snapshot's value.
The levels and the word of every row, a mechanical one too, are read on the policy in force, from
the record's stored value and its moat class (``record_standing``; spec 2026-11-23 thresholds,
5.3): the thresholds move no value, so a change of one shows with no revalue, and the figures
stored when the row was valued are not shown.
Where a review fills it, the row's ``flags`` and ``flagCount`` read the review's flags too, which
its stored result holds (spec 2026-11-13 8a); a secondary valuation has none, so a row it fills
keeps the snapshot's. A row with no agent's record has ``NO_AGENT_FIELDS``. The fields are
computed from records already read: the snapshots the records rest on (``rested_on``) are read
once for all the rows.

A row a review fills reads the state of the review the company holds (spec 2026-11-23 held
reviewed value, 5.3 and 5.7; ``held_block``, ``engine.held``): ``freshness`` is current, aging or
expired by the held review's own window, the window of the snapshot it was made on, and
``validUntil`` is that window's end. While a reason holds the value is expired early: ``freshness``
reads ``expired``, so the filter that hides expired rows hides it, and the field ``expiredEarly``
is true, which no column draws and nothing sorts by, so it is no row key. The row keeps its
number. A row no review fills reads its snapshot's window and is never expired early.

Every row also has the mark's two fields (spec 2026-11-19 7.5), which no column draws and nothing
sorts by, so neither is a row key: ``warnings``, the plain words of the snapshot's quality warnings
in the order of its flags (``warning_words``), never a review's, and ``marked``, whether the
mechanical value carries the mark: a value, no ``reviewed`` value and the policy's
``warning_mark_min`` warnings or more (``is_marked``). ``flags`` and ``flagCount`` stay, for the
agents' ``screen`` tool.
"""

import json
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from datetime import date
from typing import Any

from fairband.engine.designation import designation_for
from fairband.engine.flags import flag_count
from fairband.engine.held import held_state, secondary_state
from fairband.engine.levels import Standing, moat_of, standing_for, validity_state
from fairband.engine.types import PHASE_NUMBER, Levels, money_of, result_to_json
from fairband.policy import Moat, Policy
from fairband.refresh.held import trailing_end_of
from fairband.refresh.run import UNCLASSIFIED, Progress
from fairband.reports.refs import same_snapshot_rows
from fairband.store.companies import CompanyRow
from fairband.store.refreshes import RefreshRow
from fairband.store.reports import ReportRow
from fairband.store.reviews import HeldRow, ReviewRow
from fairband.store.secondary import SecondaryRow
from fairband.store.snapshots import SnapshotRow
from fairband.web.warning_words import is_marked, warning_words

NOT_YET_VALUED = "not yet valued"
GROUP_BY = ("sector", "industry", "phase", "cap")
NONE = "none"  # the group of the rows with no sector, no industry or no cap band
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
    "industry",
    "capBand",
    "marketCap",
    "moat",
    "impliedGrowth",
    "expectedReturn",
    "epv",
    "peReported",
    "peForward",
    "high52w",
    "low52w",
    "change1y",
    "change3y",
    "change5y",
    "drawdown",
    "flags",
    "flagCount",
    "watchlists",
    "refusal",
    "priceToValue",
    "designation",
    "agentStance",
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

# The agents' fields of a row with no agent's record: no reviewed value, no override inside it, no
# stance, no coverage mark, and no levels or flags over the snapshot's.
NO_AGENT_FIELDS: Mapping[str, Any] = {
    "reviewed": None,
    "overrides": 0,
    "agentStance": None,
    "covered": None,
    "levels": None,
    "flags": None,
    "held": None,
}
# The row keys the record that fills ``reviewed`` sets in place of the snapshot's (spec 2026-11-06
# Tier 2, 18.1, plan 3): its band, levels, price ÷ value and designation.
LEVEL_KEYS = (
    "fairValue",
    "fairLow",
    "fairHigh",
    "buyLevel",
    "trimLevel",
    "priceToValue",
    "designation",
)


def rested_on(
    snapshot: SnapshotRow, *records: ReviewRow | SecondaryRow | ReportRow | None
) -> set[int]:
    """The ids of the snapshots ``records`` rest on, the company's latest ``snapshot`` left out:
    the snapshots ``agent_fields`` needs read."""
    return {r.snapshot_id for r in records if r is not None and r.snapshot_id != snapshot.id}


def record_standing(
    value: float | None,
    moat: Moat | None,
    price: float | None,
    policy: Policy,
    record: SnapshotRow | ReviewRow | SecondaryRow,
) -> Standing | None:
    """The levels, price ÷ value and word of ``record``, whose value is ``value``, at ``price``
    (spec 2026-11-23 thresholds, 5.3): on ``policy``, the one in force, and the class ``moat``
    (``levels.standing_for``), whatever policy the record was valued under. With no class, the
    record's stored levels and the word the price has against them (``stored_standing``).
    ``None`` without a value above zero, or with neither a class nor four stored levels."""
    if value is None or value <= 0:
        return None
    if moat is not None:
        return standing_for(value, moat, price, policy)
    return stored_standing(value, price, record)


def stored_standing(
    value: float | None, price: float | None, record: SnapshotRow | ReviewRow | SecondaryRow
) -> Standing | None:
    """``record``'s levels as stored on the day it was made, and price ÷ ``value`` and the word
    ``price`` has against them, the edges those levels over the value: under the buy level Well
    below, and so on. A record of its day, whatever the policy in force: a published report's
    card reads it (spec 2026-11-23 thresholds, 5.4), and so does a record no moat class is known
    for. ``None`` without a value above zero or without four stored levels; no ratio and no word
    without a price above zero."""
    buy, low, high, trim = record.buy_level, record.fair_low, record.fair_high, record.trim_level
    if value is None or value <= 0 or buy is None or low is None or high is None or trim is None:
        return None
    levels = Levels(buy=buy, fair_low=low, fair_high=high, trim=trim)
    if price is None or price <= 0:
        return Standing(levels, None, None)
    edges = (buy / value, low / value, high / value, trim / value)
    ratio, word = designation_for(price, value, edges)
    return Standing(levels, ratio, word)


def result_json(snapshot: SnapshotRow, policy: Policy) -> dict[str, Any]:
    """The snapshot's result as the company detail serves it: ``result_to_json``'s dict with its
    ``levels``, ``price_to_value`` and ``designation`` read on ``policy``, the one in force
    (``record_standing``), so the drawer's meter and the agents' ``company`` tool show what the
    screen's row shows (spec 2026-11-23 thresholds, 5.3). A refusal's are as stored, none."""
    served: dict[str, Any] = json.loads(result_to_json(snapshot.result))
    found = record_standing(
        snapshot.value, moat_of(snapshot.result), snapshot.price, policy, snapshot
    )
    if found is not None:
        served["levels"] = asdict(found.levels)
        served["price_to_value"] = found.price_to_value
        served["designation"] = found.designation
    return served


def agent_fields(
    snapshot: SnapshotRow,
    review: ReviewRow | None,
    secondary: SecondaryRow | None,
    report: ReportRow | None,
    cited: Mapping[int, SnapshotRow],
    today: date,
    policy: Policy,
    table_moat: Moat | None,
    held: HeldRow | None = None,
) -> dict[str, Any]:
    """The agents' fields of the row of the company's latest ``snapshot`` (spec 2026-11-06 Tier 2,
    18.1), from its current review, its newest secondary valuation and its latest published
    report, each ``None`` without one; ``cited`` holds the snapshots they rest on, by id
    (``rested_on``), the latest aside. A record counts on the snapshot it rests on or on a later
    one that reprices it (``same_snapshot_rows``, the reports' rule). ``reviewed`` is the review's
    value when the review counts and has one, ``overrides`` the count of the overrides inside it;
    else, where the route refused (``snapshot`` has no value), the secondary valuation's value a
    share when it counts and is above zero, with no override inside: spec 11's secondary is the
    fallback, standing in on the row where neither the route nor the review values the company (the
    review, read first, fills the row wherever it values it); else ``None`` and 0. ``levels`` are
    the row's ``LEVEL_KEYS`` from the record that fills ``reviewed`` (plan 3): its value, and its
    four levels, price ÷ value and word at the snapshot's price on ``policy``, the effective one
    (``record_standing``), on the record's own moat class: a review's result's (``moat_of``), and
    ``table_moat``, the class of the company's row of the moat table, for a secondary valuation
    and for a review whose result holds none; ``None`` when ``reviewed`` is. ``flags`` are the review's flags when
    the review fills ``reviewed``, else ``None``: a secondary valuation has none, and a row it
    fills keeps the snapshot's (spec 2026-11-13 8a). ``agentStance`` is the report's word and
    ``covered`` its time, its actor (its principal where it names none, an owner's report) and
    whether the window of the snapshot it rests on ended before ``today`` (``window_ended``); both
    ``None`` without a report. ``held`` is the state of the review that fills ``reviewed``, on
    ``today`` and on ``policy`` (``held_block``), from ``held``, the company's row of the held
    reviews; ``None`` where no review fills the row."""
    fields = dict(NO_AGENT_FIELDS)
    if review is not None and review.value is not None and counts_on(snapshot, cited, review):
        fields |= {
            "reviewed": review.value,
            "overrides": len(review.override_ids),
            "levels": _record_levels(
                review.value, moat_of(review.result) or table_moat, review, snapshot.price, policy
            ),
            "flags": review.result.flags,
            "held": held_block(review, held, policy, today),
        }
    else:
        made_on = secondary_made_on(snapshot, cited, secondary)
        if secondary is not None and made_on is not None and secondary.value_per_share > 0:
            value = secondary.value_per_share
            fields |= {
                "reviewed": value,
                "levels": _record_levels(value, table_moat, secondary, snapshot.price, policy),
                "held": secondary_block(made_on, snapshot, policy, today),
            }
    if report is not None:
        fields["agentStance"] = report.stance
        fields["covered"] = {
            "at": report.created_at.isoformat(),
            "actor": report.principal if report.actor is None else report.actor,
            "expired": window_ended(snapshot, cited, report, today),
        }
    return fields


def held_block(
    review: ReviewRow, held: HeldRow | None, policy: Policy, today: date
) -> dict[str, Any]:
    """The state of ``review``, the review the company holds on its newest snapshot, as the API
    serves it (spec 2026-11-23 held reviewed value, 5.3; ``engine.held.held_state``): ``state``
    (``current``, ``aging``, ``expired`` or ``expired-early``), ``earlyAt``, the day a refresh
    first found a reason, ``reasons``, their sentences, ``reading`` and ``readingRefusal``, the
    newest good reading, ``readingLine``, the reading's sentence when it is no reason, and
    ``validUntil``, the end of the review's own window. It is read on ``today`` and on
    ``policy``'s fair band and aging fraction, from ``held``, the company's stored facts, which
    count only when they are this review's."""
    facts = held if held is not None and held.review_id == review.held_id else None
    result = review.result
    state = held_state(
        value=review.value,
        valid_from=result.data_date,
        valid_until=result.valid_until,
        newer_period=None if facts is None else facts.newer_period,
        dropped=() if facts is None else facts.dropped,
        reading_value=None if facts is None else facts.reading_value,
        reading_refusal=None if facts is None else facts.reading_refusal,
        early_at=None if facts is None else facts.early_at,
        band=policy.fair_band,
        today=today,
        aging_fraction=policy.aging_fraction,
    )
    return {
        "state": state.state,
        "earlyAt": _iso(state.early_at),
        "reasons": list(state.reasons),
        "reading": state.reading,
        "readingRefusal": state.reading_refusal,
        "readingLine": state.reading_line,
        "validUntil": result.valid_until.isoformat(),
    }


def secondary_made_on(
    snapshot: SnapshotRow, cited: Mapping[int, SnapshotRow], secondary: SecondaryRow | None
) -> SnapshotRow | None:
    """The snapshot ``secondary`` was made on, when the secondary valuation holds the company's
    row (spec 2026-11-23 held reviewed value, 5.9): the company's newest, made where the route
    refused. It holds whatever snapshot is the latest, until an agent makes a newer one or a made
    review values the company, which the caller reads first; it fills the Reviewed column where
    its value a share is above zero, which the caller reads too. ``None`` otherwise: for no
    secondary valuation, for one made on a snapshot the route valued, which filled no row before
    the secondary route refused such a call and fills none now, and for one whose snapshot is
    not on file."""
    if secondary is None:
        return None
    made_on = _rests_on(snapshot, cited, secondary)
    return made_on if made_on is not None and made_on.value is None else None


def secondary_block(
    made_on: SnapshotRow, snapshot: SnapshotRow, policy: Policy, today: date
) -> dict[str, Any]:
    """The state of a held secondary valuation made on ``made_on`` as the API serves it, in the
    shape of a review's (``held_block``): by the window of ``made_on``, and expired early when
    the latest ``snapshot`` holds a newer period or a value of the route's
    (``engine.held.secondary_state``). It has no reading."""
    state = secondary_state(
        valid_from=made_on.data_date,
        valid_until=made_on.valid_until,
        made_period=trailing_end_of(made_on.result),
        latest_period=trailing_end_of(snapshot.result),
        route_value=snapshot.value,
        today=today,
        aging_fraction=policy.aging_fraction,
    )
    return {
        "state": state.state,
        "earlyAt": None,
        "reasons": list(state.reasons),
        "reading": None,
        "readingRefusal": None,
        "readingLine": None,
        "validUntil": made_on.valid_until.isoformat(),
    }


def _record_levels(
    value: float | None,
    moat: Moat | None,
    record: SnapshotRow | ReviewRow | SecondaryRow,
    price: float | None,
    policy: Policy,
) -> dict[str, Any]:
    """The row's ``LEVEL_KEYS`` from ``record``, whose value is ``value``, at ``price``
    (``record_standing``); where that gives nothing (no value above zero, or neither a class nor
    stored levels), the record's stored levels with no price ÷ value and no word."""
    found = record_standing(value, moat, price, policy, record)
    if found is None:
        figures = (record.fair_low, record.fair_high, record.buy_level, record.trim_level)
        return dict(zip(LEVEL_KEYS, (value, *figures, None, None), strict=True))
    levels = found.levels
    figures = (levels.fair_low, levels.fair_high, levels.buy, levels.trim)
    return dict(
        zip(LEVEL_KEYS, (value, *figures, found.price_to_value, found.designation), strict=True)
    )


def counts_on(
    snapshot: SnapshotRow,
    cited: Mapping[int, SnapshotRow],
    record: ReviewRow | SecondaryRow | ReportRow,
) -> bool:
    """Whether ``record`` counts on the company's latest ``snapshot``: it rests on it, or on an
    earlier one (among ``cited``, by ``rested_on``) that the latest reprices
    (``same_snapshot_rows``, the reports' rule). The screen's rows and the drawer read the agents'
    records by it."""
    found = _rests_on(snapshot, cited, record)
    return found is not None and same_snapshot_rows(found, snapshot)


def window_ended(
    snapshot: SnapshotRow, cited: Mapping[int, SnapshotRow], report: ReportRow, today: date
) -> bool:
    """Whether the window of the snapshot ``report`` rests on ended before ``today``, which fades
    its stance and its coverage mark; a snapshot not on file has no window left."""
    window = _rests_on(snapshot, cited, report)
    return window is None or window.valid_until < today


def _rests_on(
    snapshot: SnapshotRow,
    cited: Mapping[int, SnapshotRow],
    record: ReviewRow | SecondaryRow | ReportRow,
) -> SnapshotRow | None:
    """The snapshot ``record`` rests on: the latest ``snapshot``, else one of ``cited``."""
    return snapshot if record.snapshot_id == snapshot.id else cited.get(record.snapshot_id)


def screen_row(
    snapshot: SnapshotRow,
    company: CompanyRow | None,
    today: date,
    aging_fraction: float,
    watchlists: Sequence[int],
    agents: Mapping[str, Any],
    *,
    mark_min: int,
    policy: Policy,
) -> dict[str, Any]:
    """The snapshot as a screen row; the name, sector, industry, cap band and market cap come
    from ``company``, ``None`` without one. ``freshness`` is the validity state on ``today``, aging
    from ``aging_fraction`` of the window; ``watchlists`` are the ids of the lists the company is
    on; ``agents`` are its agents' fields (``agent_fields``, else ``NO_AGENT_FIELDS``), whose
    ``levels``, when set, stand in the row's ``LEVEL_KEYS`` for the snapshot's; ``mechanical``
    stays the snapshot's value (spec 2026-11-06 Tier 2, 18.1, plan 3). The snapshot's own levels,
    price ÷ value and word are read on ``policy``, the effective one, from its value and its moat
    class (``record_standing``), not from the figures stored at its valuation (spec 2026-11-23
    thresholds, 5.3); a refusal has none. ``flags`` are the flags'
    words and ``flagCount`` counts the quality warnings among them, a refusal's too: the review's
    flags where ``agents`` holds them, else the snapshot's (spec 2026-11-13 8a). ``warnings`` are
    the plain words of the snapshot's own quality warnings, never a review's, and ``marked`` holds
    on a mechanical value with no reviewed value in ``agents`` and ``mark_min``, the effective
    policy's ``warning_mark_min``, warnings or more (spec 2026-11-19 7.5). The moat shows on
    a row with a value only: a growth refusal keeps the moat class for the price refresh, not for
    the screen. ``targetMargin`` is the peers' target and ``impliedMargin`` the margin the price
    needs, a growth row's; a row refused for its target margin has the latter alone.

    Every money column is in US dollars, as the value and the price are (spec 2026-11-10 7.4):
    on a row in another currency the EPV, the cross-check's value a share and the year-10 revenue,
    which the route wrote in the reporting currency, are ÷ the row's rate (``types.money_of``),
    a USD row's ÷ 1.

    A Start-up row has ``requiredRevenue``, the year-10 revenue its price needs (``None`` when the
    requirement has a reason), and ``burnCover``, the years its cash covers the trailing burn
    (``None`` when not burning). A Decline row has its synthetic ``rating`` ("—" with no net debt,
    ``None`` unavailable), ``distressProbability`` π, ``altmanZ``, ``piotroskiF`` ("6 of 9") and
    the ``impliedDeclineRate``. A Decline row refused for a value at or below zero keeps them but
    the last, and has no route: each is read from the intermediates, which no other route
    writes."""
    result = snapshot.result
    flags = result.flags if agents["flags"] is None else agents["flags"]
    warnings = warning_words(result.flags)
    phase = result.phase.phase
    im = result.intermediates
    multiples = _table(im, "multiples")
    facts = _table(im, "price_facts")
    rating = _table(im, "rating")
    rate, _ = money_of(result)
    market_cap = None if company is None else company.market_cap
    own = _record_levels(snapshot.value, moat_of(result), snapshot, snapshot.price, policy)
    row = {
        "ticker": snapshot.symbol,
        "name": None if company is None else company.name,
        "phase": None if phase is None else PHASE_NUMBER[phase],
        "fairLow": own["fairLow"],
        "fairHigh": own["fairHigh"],
        "fairValue": snapshot.value,
        "buyLevel": own["buyLevel"],
        "trimLevel": own["trimLevel"],
        "price": snapshot.price,
        "mechanical": snapshot.value,
        "reviewed": agents["reviewed"],
        "overrides": agents["overrides"],
        "enteredAt": snapshot.created_at.isoformat(),
        "freshness": validity_state(
            snapshot.data_date, snapshot.valid_until, today, aging_fraction
        ),
        "sector": None if company is None else company.sector,
        "industry": None if company is None else company.industry,
        "capBand": None if company is None else company.cap_band,
        "marketCap": None if market_cap is None else float(market_cap),
        "moat": None if snapshot.value is None else im.get("moat"),
        "impliedGrowth": im.get("implied_growth"),
        "expectedReturn": _table(im, "expected_return").get("total"),
        "epv": _in_usd(im.get("epv"), rate),
        "peReported": multiples.get("pe_reported"),
        "peForward": multiples.get("pe_forward"),
        "high52w": facts.get("high_52w"),
        "low52w": facts.get("low_52w"),
        "change1y": facts.get("change_1y"),
        "change3y": facts.get("change_3y"),
        "change5y": facts.get("change_5y"),
        "drawdown": facts.get("drawdown_from_peak"),
        "flags": [f.word for f in flags],
        "refusal": snapshot.refusal,
        "priceToValue": own["priceToValue"],
        "designation": own["designation"],
        "agentStance": agents["agentStance"],
        "priceDate": _iso(snapshot.price_date),
        "dataDate": snapshot.data_date.isoformat(),
        "validUntil": snapshot.valid_until.isoformat(),
        "route": snapshot.route,
        "growthRouteValue": _growth_route_value(snapshot, rate),
        "targetMargin": _table(im, "target_margin").get("value"),
        "impliedMargin": im.get("implied_margin"),
        "requiredRevenue": _in_usd(_table(im, "requirement").get("revenue_y10"), rate),
        "burnCover": _burn_cover(im),
        "rating": rating.get("rating"),
        "distressProbability": rating.get("pi"),
        "altmanZ": _table(im, "altman_z").get("score"),
        "piotroskiF": _piotroski_f(im),
        "impliedDeclineRate": im.get("implied_decline_rate"),
        "watchlists": list(watchlists),
        "flagCount": flag_count(flags),
        "covered": agents["covered"],
        "warnings": warnings,
        "marked": is_marked(snapshot.value, agents["reviewed"], warnings, mark_min),
    }
    if agents["levels"] is not None:
        row |= agents["levels"]
    held = agents.get("held")
    row["expiredEarly"] = held is not None and held["state"] == "expired-early"
    if held is not None:  # the row reads the state and the window of the review it shows
        row["freshness"] = "expired" if row["expiredEarly"] else held["state"]
        row["validUntil"] = held["validUntil"]
    return row


def _growth_route_value(snapshot: SnapshotRow, rate: float) -> float | None:
    """The growth route's value a share in US dollars: a Mature Growth row's own value, a Mature
    Stable or revenue-growth row's cross-check (calibration spec 5.7, growth-routes spec 5.12),
    in the reporting currency, ÷ ``rate``, when it has one; ``None`` elsewhere."""
    if snapshot.route == "mature-growth":
        return snapshot.value
    if snapshot.route in ("mature-stable", "revenue-growth"):
        cross_check = _table(snapshot.result.intermediates, "growth_route").get("value_per_share")
        return _in_usd(cross_check, rate)
    return None


def _in_usd(figure: float | None, rate: float) -> float | None:
    """A money figure the route wrote in the row's reporting currency, in US dollars: ÷ the
    row's ``rate`` (1 on a USD row); ``None`` as it is."""
    return None if figure is None else figure / rate


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


def placeholder_row(company: CompanyRow, watchlists: Sequence[int]) -> dict[str, Any]:
    """The row of an admitted company with no snapshot yet: its name, sector, industry, cap band
    and market cap, the refusal "not yet valued", freshness ``current``, its lists, no flag, no
    warning and no mark, no agent's fields (``NO_AGENT_FIELDS``: a report or a review rests on a
    snapshot; ``levels`` and ``held`` are no row keys, and ``flags`` stands for the row's flags,
    not in them), no early expiry and ``None`` elsewhere."""
    row: dict[str, Any] = dict.fromkeys(ROW_KEYS)
    aside = ("levels", "flags", "held")
    row |= {key: value for key, value in NO_AGENT_FIELDS.items() if key not in aside}
    market_cap = company.market_cap
    row |= {
        "ticker": company.symbol,
        "name": company.name,
        "freshness": "current",
        "sector": company.sector,
        "industry": company.industry,
        "capBand": company.cap_band,
        "marketCap": None if market_cap is None else float(market_cap),
        "refusal": NOT_YET_VALUED,
        "watchlists": list(watchlists),
        "flagCount": 0,
        "warnings": [],
        "marked": False,
        "expiredEarly": False,
    }
    return row


def sort_rows(
    rows: list[dict[str, Any]], key: str, descending: bool, stances: Sequence[str]
) -> list[dict[str, Any]]:
    """The rows ordered by ``key``, those where it is ``None`` last in either direction; ties
    keep their order. The agent's stance orders by its word's place in ``stances``, the policy's
    ``stance_words`` (spec 2026-11-06 Tier 2, 18.1), a word outside them after them."""
    present = [r for r in rows if r[key] is not None]
    missing = [r for r in rows if r[key] is None]
    return sorted(present, key=_order(key, stances), reverse=descending) + missing


def _order(key: str, stances: Sequence[str]) -> Callable[[dict[str, Any]], Any]:
    """What a row sorts by for ``key``: its value, or the rank of the agent's stance word."""
    if key == "agentStance":
        rank = {word: i for i, word in enumerate(stances)}
        return lambda r: rank.get(r[key], len(rank))
    return lambda r: r[key]


def group_rows(rows: Sequence[dict[str, Any]], by: str, below_value: float) -> list[dict[str, Any]]:
    """The rows grouped by ``by`` (``GROUP_BY``), ordered by group name. A group's name is the
    sector, the industry (the level under the sector), the engine's phase name (``unclassified``
    without a phase) or the cap band; ``none`` for a row without a sector, an industry or a cap
    band. Each group gives its row count, the rows with a value (``valued``), the median of
    price ÷ value over the valued rows with a positive price, and the share of the valued rows
    whose price ÷ value is below ``below_value``, the fair band's low end, every class's second
    designation edge (the ``below`` and ``well-below`` bands); ``None`` for the last two when
    they cover no row. Every figure reads the engine's (mechanical) value (``_group``)."""
    named: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        named.setdefault(_group_name(row, by), []).append(row)
    return [_group(name, members, below_value) for name, members in sorted(named.items())]


def _group_name(row: dict[str, Any], by: str) -> str:
    if by == "phase":
        phase = row["phase"]
        return UNCLASSIFIED if phase is None else _PHASE_NAMES[phase]
    name = row["capBand"] if by == "cap" else row[by]
    return NONE if name is None else str(name)


def _group(name: str, rows: list[dict[str, Any]], below_value: float) -> dict[str, Any]:
    """One group of ``group_rows``, read on the engine's (mechanical) value, ``mechanical``, never
    the row's own ``fairValue``, which follows the reviewed value where ``reviewed`` is filled: a
    row is valued when the engine values it, its price ÷ value is over the mechanical value, and
    below value is that ratio under ``below_value``, the mechanical Below or Well below band."""
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
