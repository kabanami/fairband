"""What the Research tab's read works out from a report's records, reading no store (the Research
tab's design, 7.5 and 8.1).

``report_call`` answers the value card's figures, ``{value, basis, note, levels, priceToValue,
designation, price, priceDate, dataDate, validUntil, mechanicalValue, refusal}``, from the records
the report rests on: its snapshot, and its review and its secondary valuation where it names them.

- The value is the first of three that exists: the review's, ``reviewed``; the snapshot's,
  ``mechanical``; the secondary valuation's where it is above zero, ``reviewed`` with the note
  "secondary valuation", as the report page's head names it. ``levels``, ``{buy, fairLow,
  fairHigh, trim}``, are the same record's.
- ``priceToValue`` and ``designation`` are that value against the price of the report's snapshot
  on the policy's edges, as ``rows.standing`` works them out, never the word stored with a record;
  ``None`` without a value or a price.
- ``price``, ``priceDate``, ``dataDate`` and ``validUntil`` are the snapshot's, the days as ISO
  text; ``mechanicalValue`` the snapshot's value, ``None`` on a refused one.
- ``refusal``, where no record gives a value: the review's where the report rests on one, else the
  snapshot's; ``None`` where a record gives one.

``of_report`` answers the records the report's cards draw (7.4's rules 8 and 9) from the
company's: the kill criteria that carry the report's id and those a cite of the report names
(``kill:<id>``, read from every section's parts), each once; and the news items that carry its id.
Each keeps the order the store reads them in.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from fairband.reports.check import parts
from fairband.reports.refs import KILL_FORM, record_id_of
from fairband.store.reports import ReportRow
from fairband.store.research import KillCriterionRow, NewsItemRow
from fairband.store.reviews import ReviewRow
from fairband.store.secondary import SecondaryRow
from fairband.store.snapshots import SnapshotRow
from fairband.web.rows import standing

Basis = Literal["reviewed", "mechanical"]


def report_call(
    snapshot: SnapshotRow,
    review: ReviewRow | None,
    secondary: SecondaryRow | None,
    edges: tuple[float, float, float, float],
) -> dict[str, Any]:
    """The value card's figures (module docstring) from the report's ``snapshot`` and the
    ``review`` and ``secondary`` valuation it rests on, each ``None`` where it names none, on the
    policy's designation ``edges``."""
    found = _value(snapshot, review, secondary)
    value, basis, note, levels = (None, None, None, None) if found is None else found
    ratio, word = standing(value, snapshot.price, edges)
    refusal = None
    if found is None:
        refusal = snapshot.refusal if review is None else review.refusal
    return {
        "value": value,
        "basis": basis,
        "note": note,
        "levels": levels,
        "priceToValue": ratio,
        "designation": word,
        "price": snapshot.price,
        "priceDate": None if snapshot.price_date is None else snapshot.price_date.isoformat(),
        "dataDate": snapshot.data_date.isoformat(),
        "validUntil": snapshot.valid_until.isoformat(),
        "mechanicalValue": snapshot.value,
        "refusal": refusal,
    }


def _value(
    snapshot: SnapshotRow, review: ReviewRow | None, secondary: SecondaryRow | None
) -> tuple[float, Basis, str | None, dict[str, float] | None] | None:
    """The value, its basis, its note and the same record's levels, by the order of three (module
    docstring); ``None`` where no record gives a value."""
    if review is not None and review.value is not None:
        levels = _levels(review.buy_level, review.fair_low, review.fair_high, review.trim_level)
        return review.value, "reviewed", None, levels
    if snapshot.value is not None:
        levels = _levels(
            snapshot.buy_level, snapshot.fair_low, snapshot.fair_high, snapshot.trim_level
        )
        return snapshot.value, "mechanical", None, levels
    if secondary is not None and secondary.value_per_share > 0:
        levels = _levels(
            secondary.buy_level, secondary.fair_low, secondary.fair_high, secondary.trim_level
        )
        return secondary.value_per_share, "reviewed", "secondary valuation", levels
    return None


def _levels(
    buy: float | None, fair_low: float | None, fair_high: float | None, trim: float | None
) -> dict[str, float] | None:
    """The four levels by the page's names; ``None`` where one is missing."""
    if buy is None or fair_low is None or fair_high is None or trim is None:
        return None
    return {"buy": buy, "fairLow": fair_low, "fairHigh": fair_high, "trim": trim}


def of_report(
    report: ReportRow, criteria: Sequence[KillCriterionRow], news: Sequence[NewsItemRow]
) -> tuple[list[KillCriterionRow], list[NewsItemRow]]:
    """The kill criteria and the news items of the company's ``criteria`` and ``news`` that
    ``report``'s cards draw (module docstring), in their order."""
    cited = _cited_criteria(report)
    return (
        [c for c in criteria if c.report_id == report.id or c.id in cited],
        [n for n in news if n.report_id == report.id],
    )


def _cited_criteria(report: ReportRow) -> set[int]:
    """The ids of the kill criteria the report's cites name: a ref of the ``kill`` form, its id
    the path's first step."""
    found: set[int] = set()
    for _, part in parts(report.sections):
        ref = str(part.get("ref", "")).strip() if isinstance(part, Mapping) else ""
        form, _, path = ref.partition(":")
        cited = record_id_of(path.partition("/")[0])
        if form == KILL_FORM and cited is not None:
            found.add(cited)
    return found
