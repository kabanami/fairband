"""The agents' fields on the screen's rows (spec 2026-11-06 Tier 2, 16 and 18.1), on the database of
``conftest.py``: AAPL valued on the Mature Growth route, AAL refused for its target margin and HGCO
valued on the revenue growth route, each with one snapshot. A row's ``reviewed`` is its current
review's value when the review rests on the row's snapshot or one the snapshot reprices; else, on a
row the route refused, its newest secondary valuation's value a share by the same rule, the
fallback standing in there (spec 11); else ``None``; ``overrides`` counts the overrides inside that
review; ``agentStance`` and ``covered`` read the latest published report. Where ``reviewed`` is
filled, the row's band, levels, price ÷ value and designation are the filling record's, the word at
the latest price on the effective edges, and ``mechanical`` stays the engine's value (18.1, plan
3). Where a review fills ``reviewed``, the row's flag words and its count of quality warnings are
the review's; a secondary valuation has no flags, so a row it fills keeps the snapshot's (spec
2026-11-13 8a)."""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from support.engine_companies import mature_growth_inputs, universe_deciles, young_growth_inputs
from support.web import HEADER, HOST, NOW, TODAY, _settings

from fairband.engine.designation import designation_for
from fairband.engine.flags import flag_count
from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import reprice, value_company
from fairband.engine.secondary import Part, secondary_value
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.store.ledger import OWNER, Writer
from fairband.store.overrides import drop_override, insert_override
from fairband.store.reports import insert_report
from fairband.store.reviews import ReviewRow, insert_review, latest_review
from fairband.store.secondary import SecondaryRow, insert_secondary, secondary_row
from fairband.store.snapshots import SnapshotRow, insert_snapshot, latest_snapshot
from fairband.web.app import create_app
from fairband.web.rows import NO_AGENT_FIELDS, agent_fields, screen_row, sort_rows

AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
PUBLISHED = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
SECTIONS = [{"heading": "Summary", "parts": ["The business."]}]
NO_AGENT = (None, 0, None, None)  # reviewed, overrides, agentStance, covered
# The row's band, levels, price ÷ value and word: the filling record's where ``reviewed`` is set.
LEVELS = (
    "fairValue",
    "fairLow",
    "fairHigh",
    "buyLevel",
    "trimLevel",
    "priceToValue",
    "designation",
)
Edges = tuple[float, float, float, float]
EDGES: Edges = (0.1, 0.2, 0.3, 0.4)  # any four edges: the flags do not read them


def _rows(client: TestClient, query: str = "") -> dict[str, dict[str, Any]]:
    response = client.get(f"/api/screen{query}")
    assert response.status_code == 200, response.text
    return {row["ticker"]: row for row in response.json()["rows"]}


def _tickers(client: TestClient, query: str) -> list[str]:
    return list(_rows(client, query))


def _agents(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row["reviewed"], row["overrides"], row["agentStance"], row["covered"])


def _levels(row: dict[str, Any]) -> dict[str, Any]:
    """The row's band, levels, price ÷ value and word."""
    return {key: row[key] for key in LEVELS}


def _engines(snapshot: SnapshotRow) -> dict[str, Any]:
    """The engine's band, levels, price ÷ value and word: the snapshot's own."""
    figures = (snapshot.value, snapshot.fair_low, snapshot.fair_high, snapshot.buy_level)
    rest = (snapshot.trim_level, snapshot.price_to_value, snapshot.designation)
    return dict(zip(LEVELS, figures + rest, strict=True))


def _record(
    record: ReviewRow | SecondaryRow, value: float, price: float, edges: Edges
) -> dict[str, Any]:
    """The band and levels of ``record``, whose value is ``value``, with price ÷ value and its
    word at ``price`` on ``edges``."""
    ratio, word = designation_for(price, value, edges)
    figures = (value, record.fair_low, record.fair_high, record.buy_level, record.trim_level)
    return dict(zip(LEVELS, (*figures, ratio, word), strict=True))


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
    return _newest(db_path, symbol).id


def _newest(db_path: Path, symbol: str) -> SnapshotRow:
    """The company's latest snapshot."""
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, symbol)
    assert snapshot is not None
    return snapshot


def _current_review(db_path: Path, symbol: str) -> ReviewRow:
    """The company's current review."""
    with closing(connect(db_path)) as conn:
        review = latest_review(conn, symbol)
    assert review is not None
    return review


def _refused_review(db_path: Path, results: dict[str, ValuationResult], override_id: int) -> None:
    """A newer review of AAPL on its latest snapshot, with ``override_id`` inside, that
    refused."""
    mechanical = results["AAPL"]
    refused = replace(
        mechanical,
        value=None,
        levels=None,
        price_to_value=None,
        designation=None,
        refusal="the reviewed belief is refused",
    )
    review = Review(refused, mechanical.value, (), (override_id,))
    with closing(connect(db_path)) as conn:
        insert_review(conn, review, "AAPL", _latest(db_path, "AAPL"), None, clock=lambda: NOW)


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
    # the fair value follows the reviewed value; the Mechanical column keeps the engine's (plan 3)
    assert (rows["AAPL"]["mechanical"], rows["AAPL"]["fairValue"]) == (results["AAPL"].value, value)
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
    """Spec 11: a secondary valuation stands in on the row where the route refuses, the fallback.
    One made before plan 3 on a valued snapshot stays on file for the drawer's Details and fills
    nothing: a valued row with a secondary and no review has no reviewed value."""
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
    assert _agents(rows["HGCO"]) == NO_AGENT  # the route values the row: the fallback fills nothing
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
    valued the row: the secondary valuation on that snapshot, made before plan 3, is not the
    cell's value; the fallback stands in only where the route refused."""
    override_id, _ = _review(db_path, policy, results)
    _refused_review(db_path, results, override_id)
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAPL"])
    assert secondary is not None and secondary.value_per_share > 0
    mechanical = results["AAPL"].value
    aapl = _rows(client)["AAPL"]
    assert (aapl["reviewed"], aapl["overrides"], aapl["mechanical"]) == (None, 0, mechanical)


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
    edges = policy.designation_edges
    # the levels follow the record that fills the cell (18.1, plan 3)
    assert _levels(aal) == _record(_current_review(db_path, "AAL"), value, 150.0, edges)
    assert _aal_review(db_path, policy, results, None) is None
    aal = _rows(client)["AAL"]
    assert (aal["reviewed"], aal["overrides"]) == (secondary.value_per_share, 0)
    assert _levels(aal) == _record(secondary, secondary.value_per_share, 150.0, edges)


def test_a_counting_review_sets_the_rows_levels(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 18.1, plan 3: where the review fills Reviewed, the row's band, levels, price ÷ value
    and designation are the review's, the word at the latest price on the effective edges and
    never the word stored with the review; the Mechanical column, the moat and the intermediates
    stay the engine's. Repriced at $115, the review's $143.32 reads below, where the mechanical
    $127.68 reads near and the review was stored near at $150. The research read says the same
    word."""
    _, value = _review(db_path, policy, results)
    review = _current_review(db_path, "AAPL")
    edges = policy.designation_edges
    aapl = _rows(client)["AAPL"]
    assert _levels(aapl) == _record(review, value, 150.0, edges)
    assert (aapl["reviewed"], aapl["mechanical"]) == (value, results["AAPL"].value)
    _snapshot(db_path, reprice(results["AAPL"], 115.0, date(2026, 11, 2), policy))
    latest = _newest(db_path, "AAPL")
    aapl = _rows(client)["AAPL"]
    assert _levels(aapl) == _record(review, value, 115.0, edges)
    assert (review.designation, latest.designation, aapl["designation"]) == (
        "near",
        "near",
        "below",
    )
    assert (aapl["mechanical"], aapl["price"]) == (latest.value, 115.0)
    im = latest.result.intermediates
    assert (aapl["moat"], aapl["impliedGrowth"]) == (im["moat"], im["implied_growth"])
    found = client.get("/api/companies/AAPL").json()["review"]
    assert (found["priceToValue"], found["designation"]) == (
        aapl["priceToValue"],
        aapl["designation"],
    )


def test_a_refused_review_leaves_the_engines_levels(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """Plan 3, Review Focus 3: a newer review that refused on a valued row fills nothing, so the
    row's band, levels and word are the engine's again; the secondary made before plan 3 on that
    snapshot fills nothing either."""
    override_id, value = _review(db_path, policy, results)
    assert _rows(client)["AAPL"]["fairValue"] == value
    _refused_review(db_path, results, override_id)
    aapl = _rows(client)["AAPL"]
    assert (aapl["reviewed"], aapl["overrides"]) == (None, 0)
    assert _levels(aapl) == _engines(_newest(db_path, "AAPL"))
    assert aapl["fairValue"] == aapl["mechanical"] == results["AAPL"].value


def test_a_refused_rows_secondary_sets_the_levels(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """Spec 18.1, plan 3: on AAL's refused row the secondary valuation fills Reviewed, and the
    row's band, levels and word are its own, the word at the latest price: below at $150, the
    price it was made at, and near once a reprice to $200 puts the price at 1.12 × its $178.24.
    The Mechanical column stays empty and the refusal stays; the research read says the same
    word."""
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None
    value, edges = secondary.value_per_share, policy.designation_edges
    refused = results["AAL"]
    aal = _rows(client)["AAL"]
    assert _levels(aal) == _record(secondary, value, 150.0, edges)
    assert aal["designation"] == secondary.designation == "below"
    assert (aal["mechanical"], aal["refusal"], aal["moat"]) == (None, refused.refusal, None)
    _snapshot(db_path, replace(refused, price=200.0))  # a reprice
    aal = _rows(client)["AAL"]
    assert _levels(aal) == _record(secondary, value, 200.0, edges)
    assert (aal["designation"], aal["mechanical"]) == ("near", None)
    found = client.get("/api/companies/AAL").json()["secondary"]
    assert (found["priceToValue"], found["designation"]) == (
        aal["priceToValue"],
        aal["designation"],
    )


def test_the_rows_word_reads_the_effective_edges(
    client: TestClient, secondaries: dict[str, int]
) -> None:
    """The row's word reads the settings' edges at once, as the drawer's does: AAL's secondary at
    0.84 × its value is below under the default edges and near under a fair band from 0.6, the
    Narrow margin of safety at 45% so the edges still ascend."""
    assert _rows(client)["AAL"]["designation"] == "below"
    safety = {"None": 0.45, "Narrow": 0.45, "Wide": 0.25}
    changes = {"fair_band": [0.6, 1.15], "margin_of_safety": safety}
    assert client.put("/api/settings", json={"changes": changes}, headers=HEADER).status_code == 200
    detail = client.get("/api/companies/AAL").json()
    assert detail["designationEdges"] == [1 - 0.45, 0.6, 1.15, 1.5]
    assert _rows(client)["AAL"]["designation"] == detail["secondary"]["designation"] == "near"


def test_a_revalued_row_returns_to_the_engines_levels(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """Plan 3, Review Focus 2: AAL's secondary counts on its refused snapshot until a revalue
    values the row, its mature peers found: the secondary no longer counts, Reviewed is empty and
    the band, levels and word are the engine's new ones. A revalue of AAPL leaves its review on
    the older snapshot the same way."""
    assert _rows(client)["AAL"]["reviewed"] is not None
    inputs = replace(young_growth_inputs(), symbol="AAL")
    valued = value_company(inputs, universe_deciles(), policy, TODAY)
    assert valued.value is not None
    _snapshot(db_path, valued)
    aal = _rows(client)["AAL"]
    assert _agents(aal) == NO_AGENT
    assert _levels(aal) == _engines(_newest(db_path, "AAL"))
    assert aal["fairValue"] == aal["mechanical"] == valued.value
    _, value = _review(db_path, policy, results)
    assert _rows(client)["AAPL"]["fairValue"] == value
    cited = results["AAPL"]
    assert cited.value is not None
    _snapshot(db_path, replace(cited, value=cited.value + 1.0))  # a revalue
    aapl = _rows(client)["AAPL"]
    assert (aapl["reviewed"], aapl["mechanical"]) == (None, cited.value + 1.0)
    assert _levels(aapl) == _engines(_newest(db_path, "AAPL"))


def test_agent_fields_read_the_edges_and_the_price_they_are_given(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """``agent_fields`` reads the word on the edges its caller passes, the effective policy's, at
    the latest snapshot's price; without a positive price the record's band and levels stand with
    no price ÷ value or word. ``screen_row`` writes them over the snapshot's and keeps the
    mechanical value, no ``levels`` key of its own; a row with no agent's record keeps the
    snapshot's (``NO_AGENT_FIELDS``)."""
    _, value = _review(db_path, policy, results)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    low = (0.1, 0.2, 0.3, 0.4)
    fields = agent_fields(snapshot, review, None, None, {}, TODAY, low)
    assert fields["levels"] == _record(review, value, 150.0, low)
    assert fields["levels"]["designation"] == "well-above"
    row = screen_row(snapshot, None, TODAY, 0.6667, [], fields)
    assert _levels(row) == fields["levels"] and row["mechanical"] == snapshot.value
    assert "levels" not in row
    for price in (None, 0.0):
        unpriced = agent_fields(replace(snapshot, price=price), review, None, None, {}, TODAY, low)
        assert unpriced["levels"] == fields["levels"] | {"priceToValue": None, "designation": None}
    assert NO_AGENT_FIELDS["levels"] is None
    assert _levels(screen_row(snapshot, None, TODAY, 0.6667, [], NO_AGENT_FIELDS)) == (
        _engines(snapshot)
    )


def test_a_counting_review_sets_the_rows_flags(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-13 8a: where a review fills the row, the row's flag words and its count of
    quality warnings are the review's; a row with no agent's record keeps the snapshot's."""
    _review(db_path, policy, results)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    assert flag_count(snapshot.result.flags) == 1
    settled = replace(review, result=replace(review.result, flags=()))
    fields = agent_fields(snapshot, settled, None, None, {}, TODAY, EDGES)
    assert fields["flags"] == ()
    row = screen_row(snapshot, None, TODAY, 0.6667, [], fields)
    assert (row["flags"], row["flagCount"]) == ([], 0)
    kept = screen_row(snapshot, None, TODAY, 0.6667, [], NO_AGENT_FIELDS)
    assert kept["flags"] == [f.word for f in snapshot.result.flags] and kept["flagCount"] == 1
    assert NO_AGENT_FIELDS["flags"] is None


def test_the_screen_reads_a_counting_reviews_flags(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-13 8a, through the screen: AAPL's row holds its stored review's flag words and
    count. AAL's refused row, which a review values, holds the review's seven flags and two
    warnings in place of its snapshot's three notes and none, so the sort by warnings moves it
    from first to between AAPL's one and HGCO's three."""
    assert _tickers(client, "?sort=flagCount") == ["AAL", "AAPL", "HGCO"]
    _review(db_path, policy, results)
    _aal_review(db_path, policy, results, 0.2)
    rows = _rows(client)
    for symbol in ("AAPL", "AAL"):
        flags = _current_review(db_path, symbol).result.flags
        assert (rows[symbol]["flags"], rows[symbol]["flagCount"]) == (
            [f.word for f in flags],
            flag_count(flags),
        ), symbol
    assert (len(results["AAL"].flags), flag_count(results["AAL"].flags)) == (3, 0)
    assert (len(rows["AAL"]["flags"]), rows["AAL"]["flagCount"]) == (7, 2)
    assert _tickers(client, "?sort=flagCount") == ["AAPL", "AAL", "HGCO"]


def test_a_refused_review_leaves_the_engines_flags(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """Spec 2026-11-13 8a: a newer review that refused on a valued row fills nothing, so the
    row's flags and count are the snapshot's, whatever flags the refusal carries; the secondary
    made before plan 3 on that snapshot fills nothing either."""
    override_id, _ = _review(db_path, policy, results)
    _refused_review(db_path, results, override_id)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    assert review.value is None
    bare = replace(review, result=replace(review.result, flags=()))
    fields = agent_fields(snapshot, bare, None, None, {}, TODAY, EDGES)
    assert fields["flags"] is None
    engines = ([f.word for f in snapshot.result.flags], flag_count(snapshot.result.flags))
    assert engines[1] == 1
    for row in (screen_row(snapshot, None, TODAY, 0.6667, [], fields), _rows(client)["AAPL"]):
        assert (row["flags"], row["flagCount"]) == engines


def test_a_refused_rows_secondary_leaves_the_engines_flags(
    client: TestClient, db_path: Path, secondaries: dict[str, int]
) -> None:
    """Spec 2026-11-13 8a: on AAL's refused row the secondary valuation fills Reviewed and has no
    flags, so the row's flags and count stay the snapshot's: three notes and no warning."""
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None
    snapshot = _newest(db_path, "AAL")
    fields = agent_fields(snapshot, None, secondary, None, {}, TODAY, EDGES)
    assert (fields["reviewed"], fields["flags"]) == (secondary.value_per_share, None)
    engines = ([f.word for f in snapshot.result.flags], flag_count(snapshot.result.flags))
    assert (len(engines[0]), engines[1]) == (3, 0)
    for row in (screen_row(snapshot, None, TODAY, 0.6667, [], fields), _rows(client)["AAL"]):
        assert (row["flags"], row["flagCount"]) == engines


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
