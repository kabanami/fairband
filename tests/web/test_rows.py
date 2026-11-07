"""The agents' fields on the screen's rows (spec 2026-11-06 Tier 2, 16 and 18.1), on the database of
``conftest.py``: AAPL valued on the Mature Growth route, AAL refused for its target margin and HGCO
valued on the revenue growth route, each with one snapshot. A row's ``reviewed`` is its current
review's value when the review rests on the row's snapshot or one the snapshot reprices; else, on a
row the route refused, its newest secondary valuation's value a share by the same rule, which stands
in there and is the second view beside a route's value (spec 11); else ``None``; ``overrides``
counts the overrides inside that review; ``agentStance`` and ``covered`` read the latest published
report."""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from support.engine_companies import mature_growth_inputs, universe_deciles, young_growth_inputs
from support.web import HOST, NOW, TODAY, _settings

from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import reprice
from fairband.engine.secondary import Part, secondary_value
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.store.ledger import OWNER, Writer
from fairband.store.overrides import drop_override, insert_override
from fairband.store.reports import insert_report
from fairband.store.reviews import insert_review
from fairband.store.secondary import insert_secondary, secondary_row
from fairband.store.snapshots import insert_snapshot, latest_snapshot
from fairband.web.app import create_app
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


def _aal_review(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult], margin: float | None
) -> float | None:
    """An applied margin.target override of AAL, whose route refused for its target margin, and
    the review on AAL's snapshot: valued at ``margin``, else refused; the review's value."""
    with closing(connect(db_path)) as conn:
        snapshot_id = _latest(db_path, "AAL")
        override_id = insert_override(
            conn,
            "AAL",
            "margin.target",
            None,
            0.2 if margin is None else margin,
            "ratio",
            "the peers by hand",
            [{"kind": "filing", "ref": "10-K 2025", "note": ""}],
            "lasting",
            None,
            None,
            snapshot_id,
            AGENT,
            NOW,
            "applied",
            "",
        )
        refused = results["AAL"]
        if margin is None:
            result = replace(refused, refusal="the reviewed margin is refused")
            review = Review(result, None, (), (override_id,))
        else:
            target = Override(override_id, "margin.target", margin, "agent", AGENT.actor, NOW, "")
            inputs = replace(young_growth_inputs(), symbol="AAL", peers=())
            review = review_company(inputs, universe_deciles(), policy, TODAY, [target], refused)
        insert_review(conn, review, "AAL", snapshot_id, None, clock=lambda: NOW)
    return review.result.value


def _latest(db_path: Path, symbol: str) -> int:
    """The id of the company's latest snapshot."""
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, symbol)
    assert snapshot is not None
    return snapshot.id


def _report(
    db_path: Path,
    symbol: str,
    stance: str,
    writer: Writer = AGENT,
    at: datetime = PUBLISHED,
    snapshot_id: int | None = None,
) -> None:
    """A published valuation review of ``symbol`` on ``snapshot_id``, its latest by default."""
    with closing(connect(db_path)) as conn:
        insert_report(
            conn,
            symbol,
            "valuation review",
            stance,
            SECTIONS,
            None,
            _latest(db_path, symbol) if snapshot_id is None else snapshot_id,
            None,
            None,
            None,
            writer,
            at,
        )


def _secondary(
    db_path: Path, policy: Policy, symbol: str, snapshot_id: int, fcff: tuple[float, ...]
) -> int:
    """A secondary valuation of ``symbol`` on ``snapshot_id``, one part on ``fcff`` over a billion
    shares; its id."""
    part = Part("the business", fcff, 0.0, None)
    valuation = secondary_value(
        parts=[part], debt=0.0, cash=0.0, shares=1e9, price=150.0, moat="Wide", policy=policy
    )
    with closing(connect(db_path)) as conn:
        return insert_secondary(
            conn,
            symbol,
            snapshot_id,
            [part],
            valuation,
            "a second view",
            [{"kind": "filing", "ref": "10-K 2025", "note": None}],
            "none",
            "none",
            policy.version,
            policy.settings_hash,
            None,
            AGENT,
            NOW,
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
    """Spec 11: a secondary valuation stands in on the row where the route refuses, and beside a
    route's value it is the second view, which the drawer's Details and the report show: a valued
    row with a secondary and no review has no reviewed value."""
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
        hgco = secondary_row(conn, secondaries["HGCO"])
    assert secondary is not None and hgco is not None and results["AAL"].value is None
    _, value = _review(db_path, policy, results)
    rows = _rows(client)
    aal = rows["AAL"]
    assert (aal["reviewed"], aal["overrides"], aal["mechanical"]) == (
        secondary.value_per_share,
        0,
        None,
    )
    assert results["HGCO"].value is not None and hgco.value_per_share > 0
    assert _agents(rows["HGCO"]) == NO_AGENT  # beside the route's value: the second view
    assert (rows["AAPL"]["reviewed"], rows["AAPL"]["overrides"]) == (value, 1)  # the review leads
    # a reprice keeps it; a later data date leaves it on the snapshot it was made on
    refused = results["AAL"]
    _snapshot(db_path, replace(refused, price=140.0))
    assert _rows(client)["AAL"]["reviewed"] == secondary.value_per_share
    _snapshot(db_path, replace(refused, data_date=date(2026, 11, 2)))
    assert _agents(_rows(client)["AAL"]) == NO_AGENT


def test_a_refused_review_on_a_valued_row_leaves_no_reviewed_value(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """The current review on the latest snapshot refused, so it has no value, and the route
    valued the row: the secondary valuation on that snapshot is the second view, not the cell's
    value."""
    override_id, _ = _review(db_path, policy, results)
    mechanical = results["AAPL"]
    refused = replace(
        mechanical,
        value=None,
        levels=None,
        price_to_value=None,
        designation=None,
        refusal="the reviewed belief is refused",
    )
    with closing(connect(db_path)) as conn:
        review = Review(refused, mechanical.value, (), (override_id,))
        insert_review(conn, review, "AAPL", _latest(db_path, "AAPL"), None, clock=lambda: NOW)
        secondary = secondary_row(conn, secondaries["AAPL"])
    assert secondary is not None and secondary.value_per_share > 0
    aapl = _rows(client)["AAPL"]
    assert (aapl["reviewed"], aapl["overrides"], aapl["mechanical"]) == (None, 0, mechanical.value)


def test_on_a_refused_row_a_valued_review_leads_the_secondary(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """AAL's route refused and its secondary valuation counts: a valued review fills the cell with
    its value and its override; a newer review that refuses leaves the secondary to stand in, with
    no override inside it."""
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None and results["AAL"].value is None
    value = _aal_review(db_path, policy, results, 0.2)
    assert value is not None and value != secondary.value_per_share
    aal = _rows(client)["AAL"]
    assert (aal["reviewed"], aal["overrides"], aal["mechanical"]) == (value, 1, None)
    assert _aal_review(db_path, policy, results, None) is None
    aal = _rows(client)["AAL"]
    assert (aal["reviewed"], aal["overrides"]) == (secondary.value_per_share, 0)


def test_a_secondary_at_or_below_zero_fills_no_reviewed_value(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """The record stays for the Details; the cell shows an em dash and "Has a review", which keeps
    a row whose ``reviewed`` is set, does not keep it."""
    loss = _secondary(db_path, policy, "AAL", _latest(db_path, "AAL"), (-5e9,) * 3)
    with closing(connect(db_path)) as conn:
        found = secondary_row(conn, loss)
    assert found is not None and found.value_per_share < 0
    assert _agents(_rows(client)["AAL"]) == NO_AGENT


def test_the_rows_read_the_agents_records_in_a_fixed_number_of_queries(
    tmp_path: Path, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """The reviews, the secondary valuations, the reports and the snapshots they rest on are read
    in one query each for all the rows: covering three companies on older snapshots costs the
    screen what covering one does. The secondary stands in on AAL's refused row alone."""
    first = {symbol: _latest(db_path, symbol) for symbol in results}
    for result in results.values():
        _snapshot(db_path, replace(result, price=140.0))  # a price refresh: each record is older
    statements: list[str] = []

    def traced() -> sqlite3.Connection:
        conn = connect(db_path)
        conn.set_trace_callback(statements.append)
        return conn

    app = create_app(_settings(tmp_path, db_path), policy, traced, clock=lambda: NOW)
    client = TestClient(app, base_url=HOST)

    def cover(symbol: str) -> None:
        _secondary(db_path, policy, symbol, first[symbol], tuple(x * 1e8 for x in (100.0,) * 5))
        _report(db_path, symbol, "hold", snapshot_id=first[symbol])

    def read() -> tuple[int, dict[str, dict[str, Any]]]:
        """The screen's rows and the number of statements reading them took."""
        statements.clear()
        found = _rows(client)
        return len(statements), found

    cover("AAL")
    one, rows = read()
    assert rows["AAL"]["reviewed"] is not None and rows["AAL"]["covered"] is not None
    cover("AAPL")
    cover("HGCO")
    three, rows = read()
    for symbol in results:
        assert rows[symbol]["covered"] is not None, symbol
    assert [s for s in results if rows[s]["reviewed"] is not None] == ["AAL"]
    assert three == one
    cited = [
        s for s in statements if "FROM snapshots WHERE id IN (SELECT value FROM json_each" in s
    ]
    assert cited == [  # the three older snapshots in one read
        f"SELECT * FROM snapshots WHERE id IN (SELECT value FROM json_each('{sorted(first.values())}'))"
    ]
    client.close()


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


def test_sort_by_stance_orders_the_words(client: TestClient, db_path: Path, policy: Policy) -> None:
    """The policy's words in its order, buy first; a row without a report last either way."""
    assert policy.stance_words == ("buy", "hold", "trim", "avoid")
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
    ascending = sort_rows(rows, "agentStance", False, policy.stance_words)
    assert [r["ticker"] for r in ascending] == ["D", "E", "C", "A", "B"]
    descending = sort_rows(rows, "agentStance", True, policy.stance_words)
    assert [r["ticker"] for r in descending] == ["A", "C", "E", "D", "B"]
    _report(db_path, "AAPL", "trim")
    _report(db_path, "HGCO", "buy")
    assert _tickers(client, "?sort=agentStance") == ["HGCO", "AAPL", "AAL"]
    assert _tickers(client, "?sort=agentStance&dir=desc") == ["AAPL", "HGCO", "AAL"]
