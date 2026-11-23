"""The state of a held reviewed value (spec 2026-11-23 held reviewed value, 5.3).

A reviewed value is held until the next made review. It is expired when its window's date has
passed, as any value is, and expired early while one of three reasons holds, each shown as its
sentence:

1. a newer period is on file than the one the review was made on: "The company has reported a
   newer period (to 26 Dec 2026).";
2. an override inside it no longer applies, the system dropped it since: "Override 36
   (non-recurring gap) no longer applies: the input the override corrected changed.", the
   override named by its bridge line's label (``overrides.LABELS``), by its tag without one;
3. computed again by a refresh, the review gives a value outside the held value's fair band,
   "Computed again on today's data, the review gives $229.25 (+204%).", or gives none,
   "Computed again, the review gives no value: <the refusal>.".

A refresh stores the facts (``refresh.held.read_again``); ``held_state`` reads them here, on the
fair band in force, so reason 3 follows a changed band at once, as the levels do. The state is
``expired-early`` with a reason, whatever the date, else the window's (``levels.validity_state``).
A reading inside the band is no reason; its sentence is still given, as ``reading_line``, for the
detail of a value that expired early for another reason.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from fairband.engine.levels import validity_state
from fairband.engine.overrides import LABELS

# The start of the refusal of a reading that failed (``refresh.reviews``): such a reading is no
# reason, and the last good reading stands.
READING_FAILED = "review failed"

State = Literal["current", "aging", "expired", "expired-early"]


@dataclass(frozen=True)
class HeldState:
    """A held value's state on a day: the state, the day a refresh first found a reason (``None``
    with none stored), the sentences of the reasons that hold in the order 1, 2, 3, the newest
    good reading's value or its refusal, and the reading's sentence when it is no reason."""

    state: State
    early_at: date | None
    reasons: tuple[str, ...]
    reading: float | None
    reading_refusal: str | None
    reading_line: str | None


def held_state(
    *,
    value: float | None,
    valid_from: date,
    valid_until: date,
    newer_period: date | None,
    dropped: Sequence[Mapping[str, Any]],
    reading_value: float | None,
    reading_refusal: str | None,
    early_at: date | None,
    band: tuple[float, float],
    today: date,
    aging_fraction: float,
) -> HeldState:
    """The state of a held review whose value a share is ``value`` and whose window runs from
    ``valid_from`` to ``valid_until``, on ``today`` and on ``band``, the fair band in force, from
    the facts a refresh stored (module docstring): ``newer_period``, ``dropped`` (each ``{id,
    tag, reason}``), the newest good reading and ``early_at``."""
    reasons: list[str] = []
    if newer_period is not None:
        reasons.append(f"The company has reported a newer period (to {_day(newer_period)}).")
    for override in dropped:
        tag = str(override["tag"])
        label = LABELS.get(tag, tag)  # type: ignore[call-overload]
        reasons.append(
            f"Override {override['id']} ({label}) no longer applies: {override['reason']}."
        )
    sentence = _reading_sentence(value, reading_value, reading_refusal)
    outside = reading_outside(value, reading_value, reading_refusal, band)
    if outside and sentence is not None:
        reasons.append(sentence)
    if reasons:
        state: State = "expired-early"
    else:
        state = validity_state(valid_from, valid_until, today, aging_fraction)
    return HeldState(
        state=state,
        early_at=early_at if reasons else None,
        reasons=tuple(reasons),
        reading=reading_value,
        reading_refusal=reading_refusal,
        reading_line=None if outside else sentence,
    )


def reading_outside(
    value: float | None,
    reading_value: float | None,
    reading_refusal: str | None,
    band: tuple[float, float],
) -> bool:
    """Whether the newest good reading is reason 3 against the held ``value``: its value ÷ the
    held value is under ``band``'s low or over its high, the fair band in force, or the reading
    refuses on the data. Both values are a share on the same basis and in US dollars. A held
    review with no value above zero, and a company with no reading yet, give no reason."""
    if value is None or value <= 0:
        return False
    if reading_value is None:
        return reading_refusal is not None
    low, high = band
    return not low <= reading_value / value <= high


def _reading_sentence(
    value: float | None, reading_value: float | None, reading_refusal: str | None
) -> str | None:
    """The sentence of the newest good reading against the held ``value``; ``None`` without a
    held value above zero or without a reading."""
    if value is None or value <= 0:
        return None
    if reading_value is None:
        if reading_refusal is None:
            return None
        return f"Computed again, the review gives no value: {reading_refusal}."
    change = _percent(reading_value / value - 1)
    return f"Computed again on today's data, the review gives ${reading_value:,.2f} ({change})."


def _percent(change: float) -> str:
    """A change as a signed percent: one decimal under 100%, none from 100%, the minus sign as
    the flags print one."""
    points = change * 100
    text = f"{points:+.0f}%" if abs(points) >= 100 else f"{points:+.1f}%"
    return text.replace("-", "−")


def _day(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def secondary_state(
    *,
    valid_from: date,
    valid_until: date,
    made_period: date | None,
    latest_period: date | None,
    route_value: float | None,
    today: date,
    aging_fraction: float,
) -> HeldState:
    """The state of a held secondary valuation (spec 2026-11-23 held reviewed value, 5.9), whose
    window, the one of the snapshot it was made on, runs from ``valid_from`` to ``valid_until``.
    It is expired early while a newer period is on file than the one it was made on
    (``latest_period`` after ``made_period``; without both the reason is not read), with the
    review's first sentence, or while the route values the company, ``route_value`` a share:
    "The route now values the company, at $X.". Else it reads by its date. It has no reading,
    and no refresh stores a day for it."""
    reasons: list[str] = []
    if made_period is not None and latest_period is not None and latest_period > made_period:
        reasons.append(f"The company has reported a newer period (to {_day(latest_period)}).")
    if route_value is not None:
        reasons.append(f"The route now values the company, at ${route_value:,.2f}.")
    if reasons:
        state: State = "expired-early"
    else:
        state = validity_state(valid_from, valid_until, today, aging_fraction)
    return HeldState(state, None, tuple(reasons), None, None, None)
