"""The engine's value types and the JSON form a snapshot stores.

``result_to_json`` writes sorted keys, so one result always gives the same string. Dates are ISO
``YYYY-MM-DD``; timestamps are UTC RFC 3339, and a timestamp without a time zone is refused.
``intermediates`` is written as it stands, so it must hold JSON values only. A NaN or infinity
anywhere is refused, since RFC 8259 JSON has no such number.

``result_from_json`` also reads a snapshot valued under method 0.5, which carries ``stance5`` and
``stance3`` and no designation: it drops the two stance keys and reads ``None`` for
``price_to_value`` and ``designation``. A result valued before method 0.8 carries no
``settings_hash``; it was valued under the policy file alone, so it reads the empty overlay's
hash. A result classified before method 0.9 carries neither ``positive_years_last_five`` nor
``positive_years_on_file`` in its phase evidence, and reads ``None`` for both.
"""

import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from fairband.policy.settings import EMPTY_SETTINGS_HASH

# JUDGMENT, kind judgment: an input an override sets, with the override's provenance (spec
# 2026-11-06 Tier 2, 10.4). The mechanical routes tag only DATA and RULE.
Tag = Literal["DATA", "RULE", "JUDGMENT"]
Kind = Literal["observed", "estimate", "rule", "judgment"]
Phase = Literal[
    "Start-up", "Young Growth", "High Growth", "Mature Growth", "Mature Stable", "Decline"
]
Designation = Literal["well-below", "below", "near", "above", "well-above"]
Route = Literal["mature-growth", "mature-stable", "revenue-growth", "decline", "start-up"]

PHASE_NUMBER: dict[Phase, int] = {
    "Start-up": 1,
    "Young Growth": 2,
    "High Growth": 3,
    "Mature Growth": 4,
    "Mature Stable": 5,
    "Decline": 6,
}


@dataclass(frozen=True)
class Provenance:
    source: str
    as_of: date | None
    observed_at: datetime | None
    entered_at: datetime | None


@dataclass(frozen=True)
class TaggedInput:
    name: str
    value: float | None
    unit: str
    tag: Tag
    kind: Kind
    provenance: Provenance
    estimate_method: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class Flag:
    """A warning: a short word for the screen column and one sentence for the drawer."""

    code: str
    word: str
    sentence: str


@dataclass(frozen=True)
class Levels:
    buy: float
    fair_low: float
    fair_high: float
    trim: float


@dataclass(frozen=True)
class PhaseEvidence:
    """The classifier's evidence. ``positive_years_last_five`` and ``positive_years_on_file``
    are the established test's two counts (``method.md`` 3.5): the fiscal years with an operating
    margin above zero among the last five and among all on file. Both are ``None`` where nothing
    was counted: a data gap, a row refused before the classifier ran, a result classified before
    method 0.9."""

    phase: Phase | None
    reason: str | None
    years_used: int
    positive_years_last_five: int | None
    positive_years_on_file: int | None
    growth_3y: float | None
    growth_word: str | None
    growth_decile: int | None
    revenue_slope: float | None
    margin: float | None
    margin_slope: float | None
    margin_direction: str | None
    fcf_sign: str | None
    dickinson: str | None
    checks: tuple[Flag, ...]


@dataclass(frozen=True)
class ValuationResult:
    symbol: str
    route: Route | None
    value: float | None
    levels: Levels | None
    price_to_value: float | None
    designation: Designation | None
    price: float | None
    price_date: date | None
    data_date: date
    valid_until: date
    phase: PhaseEvidence
    inputs: tuple[TaggedInput, ...]
    intermediates: dict[str, Any]
    flags: tuple[Flag, ...]
    refusal: str | None
    policy_version: str
    method_version: str
    settings_hash: str
    deciles_refresh_id: int | None


def result_to_json(r: ValuationResult) -> str:
    """The result as a JSON string with sorted keys; a NaN or infinity raises ``ValueError``."""
    return json.dumps(_plain(r), sort_keys=True, allow_nan=False)


def result_from_json(s: str) -> ValuationResult:
    """The result ``result_to_json`` wrote, with its dates, tuples and nested types restored; a
    0.5 snapshot's stance keys dropped and its missing designation ``None``; a missing settings
    hash the empty overlay's; the established test's missing counts ``None``."""
    d = json.loads(s)
    d.pop("stance5", None)
    d.pop("stance3", None)
    d.setdefault("price_to_value", None)
    d.setdefault("designation", None)
    d.setdefault("settings_hash", EMPTY_SETTINGS_HASH)
    d["phase"].setdefault("positive_years_last_five", None)
    d["phase"].setdefault("positive_years_on_file", None)
    return ValuationResult(
        **{
            **d,
            "levels": None if d["levels"] is None else Levels(**d["levels"]),
            "price_date": _date(d["price_date"]),
            "data_date": date.fromisoformat(d["data_date"]),
            "valid_until": date.fromisoformat(d["valid_until"]),
            "phase": PhaseEvidence(**{**d["phase"], "checks": _flags(d["phase"]["checks"])}),
            "inputs": tuple(_tagged_input(i) for i in d["inputs"]),
            "flags": _flags(d["flags"]),
        }
    )


def _plain(x: Any) -> Any:
    """Dataclasses to dicts, tuples to lists, dates to ISO text; anything else as it stands."""
    if is_dataclass(x) and not isinstance(x, type):
        return {f.name: _plain(getattr(x, f.name)) for f in fields(x)}
    if isinstance(x, tuple):
        return [_plain(v) for v in x]
    if isinstance(x, datetime):
        if x.tzinfo is None:
            raise ValueError(f"timestamp {x.isoformat()} has no time zone")
        return x.astimezone(UTC).isoformat()
    if isinstance(x, date):
        return x.isoformat()
    return x


def _date(s: str | None) -> date | None:
    return None if s is None else date.fromisoformat(s)


def _timestamp(s: str | None) -> datetime | None:
    return None if s is None else datetime.fromisoformat(s)


def _flags(rows: list[dict[str, Any]]) -> tuple[Flag, ...]:
    return tuple(Flag(**f) for f in rows)


def _tagged_input(d: dict[str, Any]) -> TaggedInput:
    p = d["provenance"]
    provenance = Provenance(
        source=p["source"],
        as_of=_date(p["as_of"]),
        observed_at=_timestamp(p["observed_at"]),
        entered_at=_timestamp(p["entered_at"]),
    )
    return TaggedInput(**{**d, "provenance": provenance})
