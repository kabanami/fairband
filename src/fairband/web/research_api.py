"""The drawer's reads (spec 2026-11-06 Tier 2, 16, 18.2 and 18.3).

``agent_records`` gives the company detail (``GET /api/companies/{symbol}``) the agents' records
the drawer's main view leads with, read on the company's latest snapshot by the screen's rule
(``rows.counts_on``: a record counts on the snapshot it rests on or on a later one that reprices
it), each ``None`` without one:

- ``review``: the current review when it counts, ``{id, value, levels, priceToValue,
  designation, refusal, bridge, overrideCount, mechanical}``; ``levels`` ``{buy, fairLow,
  fairHigh, trim}`` (``None`` on a refusal); price ÷ value and its word read as the secondary's
  are (below), so a refused row's drawer can draw a valued review's band against today's price;
  ``mechanical`` the value the bridge starts from. Each bridge line is the stored step,
  ``{overrideId, tag, old, new, delta, refusal}``, with the input's label in a reader's words
  (``overrides.LABELS``), its unit (``overrides.TAGS``) in the review's reporting currency
  (``overrides.unit_in``: ``SEK a share`` for a money input of a row in SEK, spec 2026-11-10 7.3)
  and the override's reason and writer.
- ``secondary``: the newest secondary valuation when it counts, ``{id, form, valuePerShare,
  levels, priceToValue, designation, parts, drivers, createdAt, principal, actor}``: price ÷ value
  and its word at the latest snapshot's price on the effective policy's edges, as the snapshot's
  own are computed (``rows.standing``, as the screen's row reads it), ``None`` without levels or a
  positive price, so a refused row's drawer can draw the secondary's band against today's price;
  ``parts`` and ``drivers`` as the secondary read serves them (``reviews_api.secondary_json``), the
  parts form's parts with their values, or the drivers form's drivers.
- ``report``: the latest published report, ``{id, mode, stance, revision, createdAt, principal,
  actor, expired, summary, references}``, wherever it rests: ``expired`` when the window of its
  snapshot ended before today (``rows.window_ended``), ``summary`` its first section as submitted
  (``{heading, parts}``, the cites included) and ``references`` the refs that section cites, each
  with its number in the whole report's list (``render.references``), so a number in the drawer
  matches the report page.
- ``item``: the company's open work item, ``{id, state, mode, claimedBy, createdAt}``,
  ``createdAt`` the time it was posted.

Beside them it gives ``priceNeeds`` (``method.md`` 4.11): the sentences on what the price needs
when it is well above the value the meter draws, the review's when the review counts and has a
value, else the snapshot's; ``None`` otherwise.

``GET /api/companies/{symbol}/research`` answers what Details lists (18.3), each record as its own
read serves it: ``overrides``, ``guidance``, ``killCriteria``, ``newsItems``, ``notes`` and
``findings`` newest first; ``judgments``, the latest report's, in the order the agent gave them;
and ``ledger``, the company's twenty newest rows, newest first. A company with no snapshot is a
404, "no snapshot for <symbol>", as the detail answers; a symbol that is not one a 400.
"""

import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException

from fairband.engine.overrides import LABELS, TAGS, unit_in
from fairband.engine.price_needs import price_needs
from fairband.engine.types import ValuationResult, money_of
from fairband.policy import Policy
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.reports.render import references
from fairband.store.guidance import guidance_for
from fairband.store.inbox import open_item
from fairband.store.ledger import entries
from fairband.store.overrides import OverrideRow, overrides_for
from fairband.store.reports import ReportRow, latest_judgments, latest_report
from fairband.store.research import findings_for, kill_criteria_for, news_items_for, notes_for
from fairband.store.reviews import ReviewRow, latest_review
from fairband.store.secondary import SecondaryRow, latest_secondary
from fairband.store.snapshots import SnapshotRow, latest_snapshot, snapshot_rows
from fairband.web.agents_api import finding_json, record_json
from fairband.web.reviews_api import secondary_json
from fairband.web.rows import counts_on, rested_on, standing, window_ended

LEDGER_ROWS = 20  # the company's newest ledger rows Details lists
# Each input's bridge label and unit by its tag as a stored bridge line names it.
_LABELS: dict[str, str] = {tag: label for tag, label in LABELS.items()}
_UNITS: dict[str, str] = {tag: spec.unit for tag, spec in TAGS.items()}


def agent_records(
    conn: sqlite3.Connection, snapshot: SnapshotRow, today: date, policy: Policy, tax: TaxTable
) -> dict[str, Any]:
    """The detail's ``review``, ``secondary``, ``report`` and ``item`` (module docstring) on the
    company's latest ``snapshot``; ``policy`` is the effective one and ``tax`` the statements'
    table, by which the Summary's references read their sources."""
    symbol = snapshot.symbol
    review = latest_review(conn, symbol)
    secondary = latest_secondary(conn, symbol)
    report = latest_report(conn, symbol)
    cited = snapshot_rows(conn, rested_on(snapshot, review, secondary, report))
    item = open_item(conn, symbol)
    edges = policy.designation_edges
    counted = review if review is not None and counts_on(snapshot, cited, review) else None
    return {
        "review": (
            None
            if counted is None
            else _review(
                counted, {o.id: o for o in overrides_for(conn, symbol)}, snapshot.price, edges
            )
        ),
        "priceNeeds": _price_needs(snapshot, counted, edges),
        "secondary": (
            _secondary(secondary, snapshot.price, edges)
            if secondary is not None and counts_on(snapshot, cited, secondary)
            else None
        ),
        "report": (
            None
            if report is None
            else _report(conn, report, window_ended(snapshot, cited, report, today), policy, tax)
        ),
        "item": (
            None
            if item is None
            else {
                "id": item.id,
                "state": item.state,
                "mode": item.mode,
                "claimedBy": item.claimed_by,
                "createdAt": item.posted_at.isoformat(),
            }
        ),
    }


def add_research_routes(app: FastAPI, conn_factory: Callable[[], sqlite3.Connection]) -> None:
    """Register the research read."""

    @app.get("/api/companies/{symbol}/research")
    def research(symbol: str) -> dict[str, Any]:
        """The records Details lists (module docstring)."""
        try:
            company = exchange_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        with closing(conn_factory()) as conn:
            if latest_snapshot(conn, company) is None:
                raise HTTPException(404, f"no snapshot for {company}")
            return {
                "overrides": [record_json(o) for o in overrides_for(conn, company)],
                "guidance": [record_json(g) for g in guidance_for(conn, company)],
                "judgments": [record_json(j) for j in latest_judgments(conn, company)],
                "killCriteria": [record_json(k) for k in kill_criteria_for(conn, company)],
                "newsItems": [record_json(n) for n in news_items_for(conn, company)],
                "notes": [record_json(n) for n in notes_for(conn, company)],
                "findings": [finding_json(f) for f in findings_for(conn, company)],
                "ledger": [record_json(e) for e in entries(conn, company, LEDGER_ROWS)],
            }


def _levels(
    buy: float | None, fair_low: float | None, fair_high: float | None, trim: float | None
) -> dict[str, float] | None:
    if buy is None or fair_low is None or fair_high is None or trim is None:
        return None
    return {"buy": buy, "fairLow": fair_low, "fairHigh": fair_high, "trim": trim}


def _standing(
    value: float | None,
    levels: dict[str, float] | None,
    price: float | None,
    edges: tuple[float, float, float, float],
) -> tuple[float | None, str | None]:
    """Price ÷ ``value`` and its word at ``price`` on ``edges`` (``rows.standing``, which the
    screen's row reads too, so the drawer and the row say one word); ``None`` without levels, a
    value above zero or a positive price."""
    if levels is None:
        return None, None
    return standing(value, price, edges)


def _price_needs(
    snapshot: SnapshotRow, review: ReviewRow | None, edges: tuple[float, float, float, float]
) -> str | None:
    """What the price needs (``engine.price_needs``, ``method.md`` 4.11) of the value the meter
    draws: the counted ``review``'s when it has a value, read from the review's own result at
    its word at the latest snapshot's price, else the snapshot's; each with the required return
    its own result read, so a row charged at r in every year gives that reason."""
    if review is not None and review.value is not None:
        levels = _levels(review.buy_level, review.fair_low, review.fair_high, review.trim_level)
        _, word = _standing(review.value, levels, snapshot.price, edges)
        reviewed = review.result
        return price_needs(reviewed.route, reviewed.intermediates, word, _required_return(reviewed))
    result = snapshot.result
    return price_needs(
        result.route, result.intermediates, snapshot.designation, _required_return(result)
    )


def _required_return(result: ValuationResult) -> float | None:
    """The required return ``result``'s route read, its RULE input: the policy's r as the row was
    valued, restated in the reporting currency of a company in another one; ``None`` on a result
    without the input (a refusal before the route's rules)."""
    for tagged in result.inputs:
        if tagged.name == "required_return":
            return tagged.value
    return None


def _review(
    review: ReviewRow,
    overrides: Mapping[int, OverrideRow],
    price: float | None,
    edges: tuple[float, float, float, float],
) -> dict[str, Any]:
    """The review, its designation at ``price``, the latest snapshot's."""
    levels = _levels(review.buy_level, review.fair_low, review.fair_high, review.trim_level)
    ratio, word = _standing(review.value, levels, price, edges)
    currency = money_of(review.result)[1]
    return {
        "id": review.id,
        "value": review.value,
        "levels": levels,
        "priceToValue": ratio,
        "designation": word,
        "refusal": review.refusal,
        "bridge": [
            _line(line, overrides.get(line["override_id"]), currency) for line in review.bridge
        ],
        "overrideCount": len(review.override_ids),
        "mechanical": review.mechanical_value,
    }


def _line(line: Mapping[str, Any], override: OverrideRow | None, currency: str) -> dict[str, Any]:
    """A bridge line with its input's label, its unit in the review's ``currency`` and its
    override's reason and writer."""
    tag = str(line["tag"])
    unit = _UNITS.get(tag)
    return {
        "overrideId": line["override_id"],
        "tag": tag,
        "label": _LABELS.get(tag, tag),
        "old": line["old"],
        "new": line["new"],
        "unit": None if unit is None else unit_in(unit, currency),
        "delta": line["delta"],
        "refusal": line["refusal"],
        "reason": None if override is None else override.reason,
        "principal": None if override is None else override.principal,
        "actor": None if override is None else override.actor,
    }


def _secondary(
    secondary: SecondaryRow, price: float | None, edges: tuple[float, float, float, float]
) -> dict[str, Any]:
    """The secondary valuation, its designation at ``price``, the latest snapshot's."""
    value = secondary.value_per_share
    levels = _levels(
        secondary.buy_level, secondary.fair_low, secondary.fair_high, secondary.trim_level
    )
    ratio, word = _standing(value, levels, price, edges)
    served = secondary_json(secondary)
    return {
        "id": secondary.id,
        "form": secondary.form,
        "valuePerShare": value,
        "levels": levels,
        "priceToValue": ratio,
        "designation": word,
        "parts": served["parts"],
        "drivers": served["drivers"],
        "createdAt": secondary.created_at.isoformat(),
        "principal": secondary.principal,
        "actor": secondary.actor,
    }


def _report(
    conn: sqlite3.Connection, report: ReportRow, expired: bool, policy: Policy, tax: TaxTable
) -> dict[str, Any]:
    first = report.sections[0] if report.sections else {}
    return {
        "id": report.id,
        "mode": report.mode,
        "stance": report.stance,
        "revision": report.revision,
        "createdAt": report.created_at.isoformat(),
        "principal": report.principal,
        "actor": report.actor,
        "expired": expired,
        "summary": {"heading": first.get("heading"), "parts": list(first.get("parts", []))},
        "references": references(conn, report, policy, tax, section=1),
    }
