"""The state of a held reviewed value and its sentences (spec 2026-11-23 held reviewed value,
5.3; ``engine/held.py``)."""

from datetime import date
from typing import Any

from fairband.engine.held import HeldState, held_state, reading_outside

CHANGED = "the input the override corrected changed"
DROPPED = {
    "id": 36,
    "tag": "earnings.nri_gap",
    "reason": CHANGED,
    "at": "2026-11-14T08:00:00+00:00",
}
FACTS: dict[str, Any] = {
    "value": 75.29,
    "valid_from": date(2026, 11, 1),
    "valid_until": date(2027, 2, 1),
    "newer_period": None,
    "dropped": (),
    "reading_value": None,
    "reading_refusal": None,
    "early_at": None,
    "band": (0.90, 1.10),
    "today": date(2026, 11, 23),
    "aging_fraction": 0.75,
}


def _state(**facts: Any) -> HeldState:
    return held_state(**(FACTS | facts))


def test_the_three_reasons_read_as_their_sentences() -> None:
    """Spec 5.3: each reason is shown as its sentence, in the order 1, 2, 3, and a value with a
    reason is expired early from the day a refresh first found one."""
    state = _state(
        newer_period=date(2026, 12, 26),
        dropped=(DROPPED,),
        reading_value=229.25,
        early_at=date(2026, 11, 14),
    )
    assert state == HeldState(
        state="expired-early",
        early_at=date(2026, 11, 14),
        reasons=(
            "The company has reported a newer period (to 26 Dec 2026).",
            (
                "Override 36 (non-recurring gap) no longer applies: "
                "the input the override corrected changed."
            ),
            "Computed again on today's data, the review gives $229.25 (+204%).",
        ),
        reading=229.25,
        reading_refusal=None,
        reading_line=None,
    )


def test_a_reading_inside_the_band_is_no_reason() -> None:
    """The spec's 7: a reading 12% above the held value expires it early by reason 3, and one 8%
    above does not. The second keeps its sentence, as a line of its own that is no reason."""
    inside = _state(value=100.0, reading_value=108.0)
    assert (inside.state, inside.reasons, inside.reading) == ("current", (), 108.0)
    assert (
        inside.reading_line == "Computed again on today's data, the review gives $108.00 (+8.0%)."
    )
    outside = _state(value=100.0, reading_value=112.0, early_at=date(2026, 11, 20))
    assert (outside.state, outside.early_at) == ("expired-early", date(2026, 11, 20))
    assert outside.reasons == (
        "Computed again on today's data, the review gives $112.00 (+12.0%).",
    )
    assert outside.reading_line is None
    edge = _state(value=100.0, reading_value=110.0)  # the band's ends are inside it
    assert (edge.state, edge.reasons) == ("current", ())


def test_reason_3_follows_the_band_in_force() -> None:
    """Review Focus 5: a reading at 0.92 × the held value is no reason at the default band and is
    one once the band's low is 0.95, with no refresh between: the state is read, not stored."""
    facts = {"value": 100.0, "reading_value": 92.0}
    assert _state(**facts).state == "current"
    narrowed = _state(**facts, band=(0.95, 1.05))
    assert (narrowed.state, narrowed.early_at) == ("expired-early", None)
    assert narrowed.reasons == ("Computed again on today's data, the review gives $92.00 (−8.0%).",)
    assert reading_outside(100.0, 92.0, None, (0.95, 1.05))
    assert not reading_outside(100.0, 92.0, None, (0.90, 1.10))


def test_a_reading_that_refuses_is_a_reason() -> None:
    """Spec 5.3: a reading that refuses on the data counts. A held review with no value has no
    reason 3, and a company with no reading yet has none."""
    refused = _state(reading_refusal="no positive trailing earnings")
    assert refused.state == "expired-early"
    assert refused.reasons == (
        "Computed again, the review gives no value: no positive trailing earnings.",
    )
    assert (refused.reading, refused.reading_refusal) == (None, "no positive trailing earnings")
    assert _state(value=None, reading_value=229.25).reasons == ()
    assert _state().reasons == ()


def test_an_override_s_words_and_a_large_figure() -> None:
    """An override the bridge has no label for is named by its tag; money takes a thousands
    separator, and a change of 100% or more no decimal."""
    state = _state(
        value=1_000.0,
        reading_value=2_345.678,
        dropped=({"id": 7, "tag": "legacy.input", "reason": "moved", "at": None},),
    )
    assert state.reasons == (
        "Override 7 (legacy.input) no longer applies: moved.",
        "Computed again on today's data, the review gives $2,345.68 (+135%).",
    )


def test_a_value_with_no_reason_reads_by_its_date() -> None:
    """A held value with no reason is current, aging or expired by its window, as any value is
    (``levels.validity_state``); a reason wins over the date."""
    assert _state(today=date(2026, 11, 23)).state == "current"
    assert _state(today=date(2027, 1, 20)).state == "aging"
    assert _state(today=date(2027, 2, 2)).state == "expired"
    late = _state(today=date(2027, 2, 2), newer_period=date(2026, 12, 26))
    assert late.state == "expired-early"
