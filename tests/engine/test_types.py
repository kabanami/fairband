import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any, get_args

import pytest

from fairband.engine import METHOD_VERSION
from fairband.engine.types import (
    PHASE_NUMBER,
    Flag,
    Levels,
    PhaseEvidence,
    Provenance,
    Route,
    TaggedInput,
    ValuationResult,
    result_from_json,
    result_to_json,
)


@pytest.fixture
def sample_result() -> ValuationResult:
    fetched = datetime(2026, 10, 30, 21, 0, tzinfo=UTC)
    shares = TaggedInput(
        name="diluted_shares",
        value=7_430.0,
        unit="million shares",
        tag="DATA",
        kind="observed",
        provenance=Provenance(
            source="fmp:income-statement",
            as_of=date(2026, 9, 30),
            observed_at=fetched,
            entered_at=None,
        ),
    )
    growth = TaggedInput(
        name="growth_belief",
        value=0.08,
        unit="ratio",
        tag="RULE",
        kind="estimate",
        provenance=Provenance(source="rule", as_of=None, observed_at=None, entered_at=fetched),
        estimate_method="consensus path capped by the base rate",
        note="three analysts",
    )
    check = Flag(code="short_history", word="short", sentence="Only four years of revenue.")
    return ValuationResult(
        symbol="MSFT",
        route="mature-growth",
        value=100.0,
        levels=Levels(buy=75.0, fair_low=85.0, fair_high=115.0, trim=150.0),
        stance5="HOLD — above fair band",
        stance3="hold",
        price=120.5,
        price_date=date(2026, 10, 30),
        data_date=date(2026, 10, 29),
        valid_until=date(2027, 1, 28),
        phase=PhaseEvidence(
            phase="Mature Growth",
            reason=None,
            years_used=5,
            growth_3y=0.11,
            growth_word="moderate",
            growth_decile=6,
            revenue_slope=0.1,
            margin=0.42,
            margin_slope=0.01,
            margin_direction="rising",
            fcf_sign="positive",
            dickinson="mature",
            checks=(check,),
        ),
        inputs=(shares, growth),
        intermediates={"a": [1, 2]},
        flags=(Flag(code="nri", word="NRI", sentence="Non-recurring items are large."),),
        refusal=None,
        policy_version="fairband-policy-v1",
        method_version=METHOD_VERSION,
        deciles_refresh_id=3,
    )


def test_result_json_round_trip(sample_result: ValuationResult) -> None:
    assert result_from_json(result_to_json(sample_result)) == sample_result
    revenue = replace(sample_result, route="revenue-growth")
    assert result_from_json(result_to_json(revenue)) == revenue


def test_routes() -> None:
    assert get_args(Route) == ("mature-growth", "mature-stable", "revenue-growth")


def test_refusal_json_round_trip(sample_result: ValuationResult) -> None:
    refusal = replace(
        sample_result,
        route=None,
        value=None,
        levels=None,
        stance5=None,
        stance3=None,
        price=None,
        price_date=None,
        refusal="no diluted share count",
        deciles_refresh_id=None,
    )
    assert result_from_json(result_to_json(refusal)) == refusal


def test_json_is_sorted_with_iso_dates_and_utc_timestamps(sample_result: ValuationResult) -> None:
    east = timezone(timedelta(hours=3))
    shares = sample_result.inputs[0]
    moved = replace(
        shares,
        provenance=replace(
            shares.provenance, observed_at=datetime(2026, 10, 31, 3, 0, tzinfo=east)
        ),
    )
    text = result_to_json(replace(sample_result, inputs=(moved,)))
    d = json.loads(text)
    assert text == json.dumps(d, sort_keys=True)
    assert d["data_date"] == "2026-10-29" and d["price_date"] == "2026-10-30"
    assert d["inputs"][0]["provenance"]["observed_at"] == "2026-10-31T00:00:00+00:00"


def test_naive_timestamp_is_refused(sample_result: ValuationResult) -> None:
    shares = sample_result.inputs[0]
    naive = replace(
        shares, provenance=replace(shares.provenance, entered_at=datetime(2026, 10, 31))
    )
    with pytest.raises(ValueError, match="time zone"):
        result_to_json(replace(sample_result, inputs=(naive,)))


@pytest.mark.parametrize(
    "change",
    [{"value": float("nan")}, {"intermediates": {"a": [1, float("nan")]}}],
    ids=["value", "intermediates"],
)
def test_non_finite_number_is_refused(
    sample_result: ValuationResult, change: dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match="JSON compliant"):
        result_to_json(replace(sample_result, **change))


def test_phase_numbers_and_method_version() -> None:
    assert list(PHASE_NUMBER.items()) == [
        ("Start-up", 1),
        ("Young Growth", 2),
        ("High Growth", 3),
        ("Mature Growth", 4),
        ("Mature Stable", 5),
        ("Decline", 6),
    ]
    assert METHOD_VERSION == "fairband-mechanical/0.4"
