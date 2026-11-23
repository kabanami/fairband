"""What the price needs on the company's detail (method 4.11): ``priceNeeds``, the sentences of
``engine.price_needs`` for the value the meter draws, the review's when it has one, else the
snapshot's, with the row's own required return. The module's AAPL is the Mature Growth company
at twice its price, so its price is well above its value; its AAL is the refused Young Growth
company at ten times its price, for the review that values it."""

from contextlib import closing
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import (
    high_growth_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.web import NOW, TODAY

from fairband.engine.overrides import Override
from fairband.engine.price_needs import price_needs
from fairband.engine.review import Review, review_company
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override
from fairband.store.reviews import insert_review
from fairband.store.snapshots import latest_snapshot

AGENT = Writer("agent", "claude-fable-5-2", "claude-code/2.1")
AT_R = (
    "The route charges growth at the hurdle rate, so growth adds no value and no growth rate "
    "reaches the price."
)


def _aapl(floored: bool = False) -> CompanyInputs:
    """The Mature Growth company at $300; ``floored``, with operating income at a twenty-second,
    so its return is below r with and without goodwill and the charge starts at r."""
    inputs = replace(mature_growth_inputs(), symbol="AAPL", price=300.0, market_cap=300_000e6)
    if not floored:
        return inputs
    poor = tuple(
        replace(y, operating_income=(y.operating_income or 0) / 22) for y in inputs.capital_years
    )
    return replace(inputs, capital_years=poor)


def _aal() -> CompanyInputs:
    """The Young Growth company with no peers, so its route refuses, at $1,500."""
    return replace(
        young_growth_inputs(), symbol="AAL", peers=(), price=1500.0, market_cap=150_000e6
    )


@pytest.fixture
def results(policy: Policy, request: pytest.FixtureRequest) -> dict[str, ValuationResult]:
    """The shared three companies as this module prices them; a test parametrized with
    ``results`` true reads AAPL floored."""
    deciles = universe_deciles()
    valued = value_company(_aapl(getattr(request, "param", False)), deciles, policy, TODAY)
    refused = value_company(_aal(), deciles, policy, TODAY)
    growth = value_company(high_growth_inputs(), deciles, policy, TODAY)
    assert valued.designation == "well-above" and growth.designation == "below"
    assert refused.value is None
    return {"AAPL": valued, "AAL": refused, "HGCO": growth}


def _detail(client: TestClient, symbol: str) -> dict[str, Any]:
    response = client.get(f"/api/companies/{symbol}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _review(
    db_path: Path,
    policy: Policy,
    inputs: CompanyInputs,
    mechanical: ValuationResult,
    tag: str,
    old: float | None,
    new: float,
) -> Review:
    """An applied override of ``tag`` on the company's latest snapshot and the review it
    produced, stored."""
    symbol = inputs.symbol
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, symbol)
        assert snapshot is not None
        override_id = insert_override(
            conn,
            symbol,
            tag,
            old,
            new,
            "ratio",
            "the evidence",
            [{"kind": "filing", "ref": "10-K 2025", "note": ""}],
            "lasting",
            None,
            None,
            snapshot.id,
            AGENT,
            NOW,
            "applied",
            "",
        )
        override = Override(override_id, tag, new, "agent", AGENT.actor, NOW, "the evidence")  # type: ignore[arg-type]
        review = review_company(inputs, universe_deciles(), policy, TODAY, [override], mechanical)
        insert_review(conn, review, symbol, snapshot.id, None, clock=lambda: NOW)
    assert review.result.value is not None
    return review


def test_a_price_well_above_the_value_carries_what_it_needs(
    client: TestClient, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    im = results["AAPL"].intermediates
    needs = _detail(client, "AAPL")["priceNeeds"]
    assert needs == price_needs("mature-growth", im, "well-above", policy.required_return)
    assert needs == (
        f"The price needs long-run earnings growth of {im['implied_growth']:.1%} a year to year "
        "20. The route holds 6.3%."
    )


def test_a_price_not_well_above_the_value_carries_none(client: TestClient) -> None:
    assert _detail(client, "HGCO")["priceNeeds"] is None  # well below its value
    assert _detail(client, "AAL")["priceNeeds"] is None  # refused, with no review


@pytest.mark.parametrize("results", [True], indirect=True)
def test_a_row_charged_at_the_hurdle_rate_gives_that_reason(
    client: TestClient, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """The detail passes the row's own required return, so a floored row says that growth adds
    no value at the hurdle rate, never that no rate in the range reaches the price."""
    im = results["AAPL"].intermediates
    assert im["runway_return"]["used"] == "floor" and im["implied_growth"] is None
    needs = _detail(client, "AAPL")["priceNeeds"]
    assert needs == price_needs("mature-growth", im, "well-above", policy.required_return)
    assert needs.startswith(AT_R) and needs.endswith("The route holds 6.3%.")
    assert "in the range the route reads" not in needs


def test_a_reviewed_row_reads_the_review_s_figures(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """The meter draws the review's band, so the sentence reads the review's result: under a
    belief of 8%, the route holds 8.0%, not the mechanical 6.3%."""
    mechanical = results["AAPL"]
    old = mechanical.intermediates["belief"]["rate"]
    review = _review(db_path, policy, _aapl(), mechanical, "growth.belief", old, 0.08)
    assert review.result.designation == "well-above"
    body = _detail(client, "AAPL")
    assert body["review"]["designation"] == "well-above"
    needs = body["priceNeeds"]
    assert needs == price_needs(
        "mature-growth", review.result.intermediates, "well-above", policy.required_return
    )
    assert needs.endswith("The route holds 8.0%.")


def test_a_review_within_reach_of_the_price_has_no_sentence(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """The word is the review's at the latest price, never the snapshot's: under a belief of
    20% the reviewed value is no longer far under the price, so nothing leads the band though
    the mechanical value's own word is still Well above."""
    mechanical = results["AAPL"]
    old = mechanical.intermediates["belief"]["rate"]
    review = _review(db_path, policy, _aapl(), mechanical, "growth.belief", old, 0.20)
    assert review.result.designation != "well-above"
    body = _detail(client, "AAPL")
    assert body["result"]["designation"] == "well-above"
    assert body["review"]["designation"] == review.result.designation
    assert body["priceNeeds"] is None


def test_a_refused_row_reads_the_review_that_values_it(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """A refused snapshot has no route and no word; the review that values it has both, and the
    meter draws its band, so the sentence is the review's (RKLB's case on the live data)."""
    review = _review(db_path, policy, _aal(), results["AAL"], "margin.target", None, 0.2)
    assert review.result.route == "revenue-growth"
    assert review.result.designation == "well-above"
    body = _detail(client, "AAL")
    assert body["result"]["value"] is None and body["result"]["route"] is None
    needs = body["priceNeeds"]
    assert needs is not None
    assert needs == price_needs(
        "revenue-growth", review.result.intermediates, "well-above", policy.required_return
    )
    assert "target operating margin" in needs and "by year" not in needs
