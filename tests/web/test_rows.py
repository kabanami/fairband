"""The agents' fields on the screen's rows (spec 2026-11-06 Tier 2, 16 and 18.1), on the database of
``conftest.py``: AAPL valued on the Mature Growth route, AAL refused for its target margin and HGCO
valued on the revenue growth route, each with one snapshot. A row's ``reviewed`` is its current
review's value when the review rests on the row's snapshot or one the snapshot reprices, else its
newest secondary valuation's value a share by the same rule, else ``None``; ``overrides`` counts the
overrides inside that review; ``agentStance`` and ``covered`` read the latest published report."""

from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from support.engine_companies import mature_growth_inputs, universe_deciles
from support.web import NOW, TODAY

from fairband.engine.overrides import Override
from fairband.engine.review import review_company
from fairband.engine.route import reprice
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.store.ledger import OWNER, Writer
from fairband.store.overrides import drop_override, insert_override
from fairband.store.reports import insert_report
from fairband.store.reviews import insert_review
from fairband.store.secondary import secondary_row
from fairband.store.snapshots import insert_snapshot, latest_snapshot
from fairband.web.rows import sort_rows

AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
PUBLISHED = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
SECTIONS = [{"heading": "Summary", "parts": ["The business."]}]
NO_AGENT = (None, 0, None, None)  # reviewed, overrides, agentStance, covered


def _rows(client: TestClient, query: str = "") -> dict[str, dict[str, Any]]:
    response = client.get(f"/api/screen{query}")
    assert response.status_code == 200, response.text
    return {row["ticker"]: row for row in response.json()["rows"]}


def _tickers(client: TestClient, query: str) -> list[str]:
    return list(_rows(client, query))


def _agents(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row["reviewed"], row["overrides"], row["agentStance"], row["covered"])


def _review(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> tuple[int, float]:
    """An applied growth.belief override of AAPL at 8% and the review it produced on AAPL's
    snapshot; the override's id and the review's value."""
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
            [{"kind": "transcript", "ref": "Q3 call", "note": ""}],
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
        inputs = replace(mature_growth_inputs(), symbol="AAPL")
        review = review_company(
            inputs, universe_deciles(), policy, TODAY, [belief], results["AAPL"]
        )
        insert_review(conn, review, "AAPL", snapshot.id, None, clock=lambda: NOW)
    value = review.result.value
    assert value is not None and value != results["AAPL"].value
    return override_id, value


def _report(
    db_path: Path, symbol: str, stance: str, writer: Writer = AGENT, at: datetime = PUBLISHED
) -> None:
    """A published valuation review of ``symbol`` on its latest snapshot."""
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, symbol)
        assert snapshot is not None
        insert_report(
            conn,
            symbol,
            "valuation review",
            stance,
            SECTIONS,
            None,
            snapshot.id,
            None,
            None,
            None,
            writer,
            at,
        )


def _snapshot(db_path: Path, result: ValuationResult) -> None:
    """A later snapshot of the company under the fixture's refresh."""
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, result, 1, clock=lambda: NOW)


def test_the_rows_carry_the_agents_fields(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    _, value = _review(db_path, policy, results)
    _report(db_path, "AAPL", "hold")
    rows = _rows(client)
    covered = {"at": "2026-11-01T08:00:00+00:00", "actor": "claude-opus-5-5", "expired": False}
    assert _agents(rows["AAPL"]) == (value, 1, "hold", covered)
    assert rows["AAPL"]["mechanical"] == rows["AAPL"]["fairValue"] == results["AAPL"].value
    for symbol in ("AAL", "HGCO"):
        assert _agents(rows[symbol]) == NO_AGENT, symbol
    # a numeric column: the reviewed row first either way, the rows with none after it
    assert _tickers(client, "?sort=reviewed") == ["AAPL", "AAL", "HGCO"]
    assert _tickers(client, "?sort=reviewed&dir=desc") == ["AAPL", "AAL", "HGCO"]


def test_an_owners_report_names_the_owner(client: TestClient, db_path: Path) -> None:
    """A report the owner published names no model: the mark's title names the principal."""
    _report(db_path, "HGCO", "avoid", writer=OWNER)
    covered = _rows(client)["HGCO"]["covered"]
    assert covered == {"at": "2026-11-01T08:00:00+00:00", "actor": "owner", "expired": False}


def test_a_review_on_an_older_snapshot_is_not_the_rows_reviewed_value(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    _, value = _review(db_path, policy, results)
    cited = results["AAPL"]
    assert cited.value is not None
    repriced = reprice(cited, 160.0, date(2026, 11, 2), policy)
    _snapshot(db_path, repriced)
    aapl = _rows(client)["AAPL"]
    assert (aapl["reviewed"], aapl["overrides"], aapl["price"]) == (value, 1, 160.0)  # a reprice
    _snapshot(db_path, replace(repriced, value=cited.value + 1.0))  # a revalue
    aapl = _rows(client)["AAPL"]
    assert (aapl["reviewed"], aapl["overrides"], aapl["mechanical"]) == (None, 0, cited.value + 1.0)


def test_a_dropped_override_leaves_no_reviewed_value(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    override_id, _ = _review(db_path, policy, results)
    with closing(connect(db_path)) as conn:
        drop_override(conn, override_id, "guidance withdrawn", NOW)
    assert _agents(_rows(client)["AAPL"]) == NO_AGENT


def test_a_secondary_stands_in_where_the_route_refuses(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None and results["AAL"].value is None
    _, value = _review(db_path, policy, results)
    rows = _rows(client)
    aal = rows["AAL"]
    assert (aal["reviewed"], aal["overrides"], aal["mechanical"]) == (
        secondary.value_per_share,
        0,
        None,
    )
    assert rows["HGCO"]["reviewed"] == secondary.value_per_share  # beside the route's value too
    assert (rows["AAPL"]["reviewed"], rows["AAPL"]["overrides"]) == (value, 1)  # the review leads
    # a reprice keeps it; a later data date leaves it on the snapshot it was made on
    refused = results["AAL"]
    _snapshot(db_path, replace(refused, price=140.0))
    assert _rows(client)["AAL"]["reviewed"] == secondary.value_per_share
    _snapshot(db_path, replace(refused, data_date=date(2026, 11, 2)))
    assert _agents(_rows(client)["AAL"]) == NO_AGENT


def test_covered_expires_with_the_window(
    client_with_clock: Callable[[datetime], TestClient],
    db_path: Path,
    results: dict[str, ValuationResult],
) -> None:
    """The mark fades when the window of the snapshot the report rests on ends, whatever the
    company's later snapshots say."""
    _report(db_path, "AAPL", "buy")
    assert results["AAPL"].valid_until == date(2027, 1, 28)
    last_day = client_with_clock(datetime(2027, 1, 28, 23, 59, tzinfo=UTC))
    after = client_with_clock(datetime(2027, 1, 29, 0, 0, tzinfo=UTC))
    assert _rows(last_day)["AAPL"]["covered"]["expired"] is False
    assert _rows(after)["AAPL"]["covered"]["expired"] is True
    later = date(2027, 4, 28)
    _snapshot(db_path, replace(results["AAPL"], data_date=date(2027, 1, 27), valid_until=later))
    assert _rows(after)["AAPL"]["covered"]["expired"] is True
    assert _rows(after)["AAPL"]["agentStance"] == "buy"


def test_sort_by_stance_orders_the_words(client: TestClient, db_path: Path) -> None:
    rows = [
        {"ticker": ticker, "agentStance": stance}
        for ticker, stance in (
            ("A", "avoid"),
            ("B", None),
            ("C", "trim"),
            ("D", "buy"),
            ("E", "hold"),
        )
    ]
    ascending = sort_rows(rows, "agentStance", descending=False)
    assert [r["ticker"] for r in ascending] == ["D", "E", "C", "A", "B"]
    descending = sort_rows(rows, "agentStance", descending=True)
    assert [r["ticker"] for r in descending] == ["A", "C", "E", "D", "B"]
    _report(db_path, "AAPL", "trim")
    _report(db_path, "HGCO", "buy")
    assert _tickers(client, "?sort=agentStance") == ["HGCO", "AAPL", "AAL"]
    assert _tickers(client, "?sort=agentStance&dir=desc") == ["AAPL", "HGCO", "AAL"]
