"""The engine's value types and the JSON form a snapshot stores.

``result_to_json`` writes sorted keys, so one result always gives the same string. Dates are ISO
``YYYY-MM-DD``; timestamps are UTC RFC 3339, and a timestamp without a time zone is refused.
``intermediates`` is written as it stands, so it must hold JSON values only. A NaN or infinity
anywhere is refused, since RFC 8259 JSON has no such number.
"""

import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

Tag = Literal["DATA", "RULE"]
Kind = Literal["observed", "estimate", "rule"]
Phase = Literal[
    "Start-up", "Young Growth", "High Growth", "Mature Growth", "Mature Stable", "Decline"
]
Stance5 = Literal["BUY", "ACCUMULATE / HOLD", "HOLD", "HOLD — above fair band", "TRIM"]
Stance3 = Literal["buy", "hold", "trim"]
Route = Literal["mature-growth", "mature-stable", "revenue-growth"]

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
    phase: Phase | None
    reason: str | None
    years_used: int
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
    stance5: Stance5 | None
    stance3: Stance3 | None
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
    deciles_refresh_id: int | None


def result_to_json(r: ValuationResult) -> str:
    """The result as a JSON string with sorted keys; a NaN or infinity raises ``ValueError``."""
    return json.dumps(_plain(r), sort_keys=True, allow_nan=False)


def result_from_json(s: str) -> ValuationResult:
    """The result ``result_to_json`` wrote, with its dates, tuples and nested types restored."""
    d = json.loads(s)
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
