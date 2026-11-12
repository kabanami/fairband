"""What the price needs on the company's detail (method 4.11): ``priceNeeds``, the sentences of
``engine.price_needs`` for the value the meter draws, the review's when it has one, else the
snapshot's. The module's AAPL is the Mature Growth company at twice its price, so its price is
well above its value."""

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
from fairband.engine.review import review_company
from fairband.engine.route import value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override
from fairband.store.reviews import insert_review
from fairband.store.snapshots import latest_snapshot

AGENT = Writer("agent", "claude-fable-5-2", "claude-code/2.1")
PRICE = 300.0


def _aapl() -> Any:
    return replace(mature_growth_inputs(), symbol="AAPL", price=PRICE, market_cap=300_000e6)


@pytest.fixture
def results(policy: Policy) -> dict[str, ValuationResult]:
    """The shared three companies, with AAPL at $300 against a value near $128."""
    deciles = universe_deciles()
    valued = value_company(_aapl(), deciles, policy, TODAY)
    no_peers = replace(young_growth_inputs(), symbol="AAL", peers=())
    refused = value_company(no_peers, deciles, policy, TODAY)
    growth = value_company(high_growth_inputs(), deciles, policy, TODAY)
    assert valued.designation == "well-above" and growth.designation == "well-below"
    return {"AAPL": valued, "AAL": refused, "HGCO": growth}


def _detail(client: TestClient, symbol: str) -> dict[str, Any]:
    response = client.get(f"/api/companies/{symbol}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_a_price_well_above_the_value_carries_what_it_needs(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    im = results["AAPL"].intermediates
    needs = _detail(client, "AAPL")["priceNeeds"]
    assert needs == price_needs("mature-growth", im, "well-above")
    assert needs == (
        f"The price needs long-run earnings growth of {im['implied_growth']:.1%} a year to year "
        "20. The route holds 6.3%."
    )


def test_a_price_not_well_above_the_value_carries_none(client: TestClient) -> None:
    assert _detail(client, "HGCO")["priceNeeds"] is None  # well below its value
    assert _detail(client, "AAL")["priceNeeds"] is None  # refused, with no review


def test_a_reviewed_row_reads_the_review_s_figures(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """The meter draws the review's band, so the sentence reads the review's result: under a
    belief of 8%, the route holds 8.0%, not the mechanical 6.3%."""
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, "AAPL")
        assert snapshot is not None
        override_id = insert_override(
            conn,
            "AAPL",
            "growth.belief",
            results["AAPL"].intermediates["belief"]["rate"],
            0.08,
            "ratio",
            "guidance raised",
            [{"kind": "guidance", "ref": "guidance:1", "note": "the Q3 call"}],
            "lasting",
            None,
            None,
            snapshot.id,
            AGENT,
            NOW,
            "applied",
            "",
        )
        belief = Override(override_id, "growth.belief", 0.08, "agent", AGENT.actor, NOW, "raised")
        review = review_company(
            _aapl(), universe_deciles(), policy, TODAY, [belief], results["AAPL"]
        )
        insert_review(conn, review, "AAPL", snapshot.id, None, clock=lambda: NOW)
    assert review.result.value is not None and review.result.designation == "well-above"
    body = _detail(client, "AAPL")
    assert body["review"]["designation"] == "well-above"
    needs = body["priceNeeds"]
    assert needs == price_needs("mature-growth", review.result.intermediates, "well-above")
    assert needs.endswith("The route holds 8.0%.")
