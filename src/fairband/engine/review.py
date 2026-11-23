"""The review: the engine's value under an agent's applied overrides, and the bridge to it from the
mechanical value (spec 2026-11-06 Tier 2, 10.4; ``method.md`` 14).

``review_company`` applies the overrides one at a time in the bridge's order
(``overrides.BRIDGE_ORDER``, the method's step order), each line's ``value_company`` run on that
override and every earlier one. A line's delta is its value less the value of the last step that
valued: the mechanical value, or an earlier line's. A line whose step refuses carries the refusal
in place of a delta, and the next valuing line measures from the last step that valued, so the
deltas sum to the reviewed value less the mechanical one. Where no earlier step valued (a
mechanical refusal, a Start-up row say), the first valuing line's delta is its whole value: the
bridge starts at no mechanical value. The review's result is the last line's, so a review whose
last step refuses is that refusal; its levels read the reviewed moat. ``old`` is the engine's
reading of the input on the mechanical result (``overrides.current_reading``).

An override the store scaled at a split (``Override.rescaled``, spec 2026-11-14 7) gives the
review's result the note ``override-split-scaled``, "Override scaled at a split", naming each such
input in the bridge's order: "A split took effect after these inputs were entered, so each applies
on the new basis: earnings.ntm, value.outside." It comes last among the result's flags but
``fx-stale``, which stays last (``method.md`` 8). The mechanical result never carries it.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import BRIDGE_ORDER, Override, OverrideTag, current_reading
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import Flag, ValuationResult
from fairband.policy import Policy

REVIEW_METHOD = "fairband-review/2"
SPLIT_SCALED = "override-split-scaled"
_FX_STALE = "fx-stale"  # last among a row's flags (method 8)


@dataclass(frozen=True)
class BridgeLine:
    """One override's step: the input, the override's id, the engine's reading and the override's
    value, and the change in the value a share, or the refusal the step met."""

    tag: OverrideTag
    override_id: int | None
    old: float | str | None
    new: float | str
    delta: float | None
    refusal: str | None


@dataclass(frozen=True)
class Review:
    """The reviewed result, the mechanical value it starts from, the bridge's lines in order and
    the ids of the overrides inside."""

    result: ValuationResult
    mechanical_value: float | None
    bridge: tuple[BridgeLine, ...]
    override_ids: tuple[int, ...]


def review_company(
    inputs: CompanyInputs,
    deciles: Deciles | None,
    policy: Policy,
    today: date,
    overrides: Sequence[Override],
    mechanical: ValuationResult,
) -> Review:
    """The review of ``mechanical``, the company's mechanical result on ``inputs``, under
    ``overrides``, at most one for each input. Without an override it is the mechanical result
    with an empty bridge."""
    ordered = sorted(overrides, key=lambda o: BRIDGE_ORDER.index(o.tag))
    tags = [o.tag for o in ordered]
    if len(set(tags)) != len(tags):
        raise ValueError(f"one override for each input: {', '.join(tags)}")
    applied: dict[OverrideTag, Override] = {}
    result, last, lines = mechanical, mechanical.value, []
    for o in ordered:
        applied[o.tag] = o
        result = value_company(inputs, deciles, policy, today, dict(applied))
        old = current_reading(mechanical, o.tag)
        if result.value is None:
            lines.append(BridgeLine(o.tag, o.id, old, o.value, None, result.refusal))
            continue
        delta = result.value if last is None else result.value - last
        lines.append(BridgeLine(o.tag, o.id, old, o.value, delta, None))
        last = result.value
    ids = tuple(o.id for o in ordered if o.id is not None)
    return Review(_split_scaled(result, ordered), mechanical.value, tuple(lines), ids)


def _split_scaled(result: ValuationResult, ordered: Sequence[Override]) -> ValuationResult:
    """``result`` with the note ``override-split-scaled`` naming each of the ``ordered``
    overrides that a split scaled, before a trailing ``fx-stale`` (module docstring); as it is
    with none."""
    scaled = [o.tag for o in ordered if o.rescaled is not None]
    if not scaled:
        return result
    note = Flag(
        SPLIT_SCALED,
        "Override scaled at a split",
        "A split took effect after these inputs were entered, so each applies on the new basis: "
        f"{', '.join(scaled)}.",
    )
    kept = tuple(f for f in result.flags if f.code != _FX_STALE)
    stale = tuple(f for f in result.flags if f.code == _FX_STALE)
    return replace(result, flags=(*kept, note, *stale))
