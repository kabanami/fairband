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
2026-11-13 8a). The row's ``warnings`` and ``marked`` read the snapshot's flags alone, never a
review's (spec 2026-11-19 7.5)."""

import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import (
    fx_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.web import HEADER, HOST, NOW, TODAY, _settings

from fairband.engine.flags import flag_count
from fairband.engine.levels import moat_of, standing_for, validity_state
from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import reprice, value_company
from fairband.engine.secondary import Part, secondary_value
from fairband.engine.types import Flag, ValuationResult
from fairband.policy import Moat, Policy
from fairband.policy.settings import apply_overlay
from fairband.store.db import connect
from fairband.store.ledger import OWNER, Writer
from fairband.store.moat import moat_row
from fairband.store.overrides import drop_override, insert_override
from fairband.store.reports import insert_report
from fairband.store.reviews import (
    ReviewRow,
    clear_held,
    held_row,
    insert_review,
    latest_review,
    set_held_state,
)
from fairband.store.secondary import SecondaryRow, insert_secondary, secondary_row
from fairband.store.snapshots import (
    SnapshotRow,
    insert_snapshot,
    latest_snapshot,
    snapshot_row,
)
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
    record: ReviewRow | SecondaryRow,
    value: float,
    price: float,
    policy: Policy,
    table_moat: Moat | None = None,
) -> dict[str, Any]:
    """The band, levels, price ÷ value and word a row shows for ``record``, whose value is
    ``value``, at ``price``: on ``policy`` and the record's own moat class, a review's result's,
    else ``table_moat``, the company's class in the moat table, which a secondary valuation
    reads (spec 2026-11-23 thresholds, 5.3)."""
    moat = (moat_of(record.result) if isinstance(record, ReviewRow) else None) or table_moat
    assert moat is not None
    return _in_force(value, moat, price, policy)


def _table_moat(db_path: Path, symbol: str) -> Moat | None:
    """The class of the company's row of the moat table, none without a row."""
    with closing(connect(db_path)) as conn:
        row = moat_row(conn, symbol)
    return None if row is None else row.moat


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


def snapshot_of(db_path: Path, snapshot_id: int) -> SnapshotRow:
    with closing(connect(db_path)) as conn:
        found = snapshot_row(conn, snapshot_id)
    assert found is not None
    return found


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


def test_a_cleared_review_leaves_no_reviewed_value(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-23 held reviewed value, 5.1: a dropped override alone does not end the review
    the company holds, as a refresh's drop does not; the row is mechanical again once the held
    review is cleared, as an agent's drop of the last override clears it."""
    override_id, value = _review(db_path, policy, results)
    with closing(connect(db_path)) as conn:
        drop_override(conn, override_id, "guidance withdrawn", NOW)
    assert _rows(client)["AAPL"]["reviewed"] == value
    with closing(connect(db_path)) as conn:
        clear_held(conn, "AAPL")
    assert _agents(_rows(client)["AAPL"]) == NO_AGENT


def test_a_held_row_reads_expired_early_and_keeps_its_number(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-23 held reviewed value, 5.3 and 5.7: a reviewed row's freshness is its held
    review's state. With a reason stored it reads expired, with ``expiredEarly``, so the filter
    that hides expired rows hides it, and it keeps its number. The detail's review gives the
    state, the day, the sentences and the reading; with no reason the state is the window's."""
    _, value = _review(db_path, policy, results)
    row = _rows(client)["AAPL"]
    assert (row["reviewed"], row["expiredEarly"]) == (value, False)
    block = client.get("/api/companies/AAPL").json()["review"]["held"]
    assert (block["state"], block["reasons"], block["earlyAt"]) == (row["freshness"], [], None)
    with closing(connect(db_path)) as conn:
        held = held_row(conn, "AAPL")
        assert held is not None
        facts = replace(
            held,
            newer_period=date(2026, 12, 26),
            reading_value=value * 2,
            early_at=date(2026, 11, 14),
        )
        set_held_state(conn, facts)
    row = _rows(client)["AAPL"]
    assert (row["reviewed"], row["freshness"], row["expiredEarly"]) == (value, "expired", True)
    assert client.get("/api/companies/AAPL").json()["review"]["held"] == {
        "state": "expired-early",
        "earlyAt": "2026-11-14",
        "reasons": [
            "The company has reported a newer period (to 26 Dec 2026).",
            f"Computed again on today's data, the review gives ${value * 2:,.2f} (+100%).",
        ],
        "reading": value * 2,
        "readingRefusal": None,
        "readingLine": None,
        "validUntil": row["validUntil"],
    }


def test_a_reviewed_row_s_window_is_its_held_review_s(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 5.2 and 5.7: the row's "valid until" is the window of the snapshot the review was
    made on, which its copies keep, whatever the latest snapshot's window is; a row no review
    fills keeps the snapshot's window and state, and is never expired early."""
    _review(db_path, policy, results)
    with closing(connect(db_path)) as conn:
        review = latest_review(conn, "AAPL")
        assert review is not None
        ended = (NOW.date() - timedelta(days=1)).isoformat()
        conn.execute(
            "UPDATE reviews SET result = json_set(result, '$.valid_until', ?) WHERE id = ?",
            (ended, review.id),
        )
        conn.commit()
    rows = _rows(client)
    snapshot = _newest(db_path, "AAPL")
    assert snapshot.valid_until.isoformat() != ended
    held = rows["AAPL"]
    assert (held["validUntil"], held["freshness"], held["expiredEarly"]) == (
        ended,
        "expired",
        False,
    )
    plain = rows["HGCO"]
    other = _newest(db_path, "HGCO")
    assert plain["reviewed"] is None and plain["expiredEarly"] is False
    assert plain["validUntil"] == other.valid_until.isoformat()
    assert plain["freshness"] == validity_state(
        other.data_date, other.valid_until, NOW.date(), policy.aging_fraction
    )


def test_a_secondary_stands_in_where_the_route_refuses(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """Spec 11: a secondary valuation stands in on the row where the route refuses, the fallback.
    One made before plan 3 on a valued snapshot stays on file and fills nothing: a valued row
    with a secondary and no review has no reviewed value."""
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
    # a reprice keeps it, and so does a refresh that replaces its snapshot with other data: it
    # holds until a newer one or a made review that values the company (spec 2026-11-23 held
    # reviewed value, 5.9)
    refused = results["AAL"]
    _snapshot(db_path, replace(refused, price=140.0))
    assert _rows(client)["AAL"]["reviewed"] == secondary.value_per_share
    _snapshot(db_path, replace(refused, data_date=date(2026, 11, 2)))
    stays = _rows(client)["AAL"]
    assert (stays["reviewed"], stays["expiredEarly"]) == (secondary.value_per_share, False)
    made_on = snapshot_of(db_path, secondary.snapshot_id)
    assert stays["validUntil"] == made_on.valid_until.isoformat()  # the window of its making
    held = client.get("/api/companies/AAL").json()["secondary"]["held"]
    assert (held["state"], held["reasons"], held["reading"]) == (stays["freshness"], [], None)


def test_a_secondary_valuation_expires_early_when_the_route_values_the_company(
    client: TestClient,
    db_path: Path,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """Spec 5.9 and 7: the route now values AAL, whose row a secondary valuation filled. The
    secondary still fills the Reviewed column, expired early, and its detail names the route's
    value; the Mechanical column shows that value."""
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None
    valued = replace(results["HGCO"], symbol="AAL")
    assert valued.value is not None
    _snapshot(db_path, valued)
    row = _rows(client)["AAL"]
    assert (row["reviewed"], row["mechanical"]) == (secondary.value_per_share, valued.value)
    assert (row["freshness"], row["expiredEarly"]) == ("expired", True)
    held = client.get("/api/companies/AAL").json()["secondary"]["held"]
    assert held["state"] == "expired-early"
    assert held["reasons"][-1] == f"The route now values the company, at ${valued.value:,.2f}."


def test_a_secondary_valuation_expires_early_at_a_newer_period(
    client: TestClient,
    db_path: Path,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """Spec 5.9: a newer period on file than the one the secondary valuation was made on expires
    it early, by the review's first sentence; the row keeps the figure."""
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
        assert secondary is not None
        conn.execute(
            "UPDATE snapshots SET result = json_set(result, '$.intermediates.trailing_end',"
            " '2026-09-30') WHERE id = ?",
            (secondary.snapshot_id,),
        )
        conn.commit()
    refused = results["AAL"]
    later = replace(refused, intermediates=refused.intermediates | {"trailing_end": "2026-12-31"})
    _snapshot(db_path, later)
    row = _rows(client)["AAL"]
    assert (row["reviewed"], row["expiredEarly"]) == (secondary.value_per_share, True)
    held = client.get("/api/companies/AAL").json()["secondary"]["held"]
    assert held["reasons"] == ["The company has reported a newer period (to 31 Dec 2026)."]


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
    # the levels follow the record that fills the cell (18.1, plan 3)
    assert _levels(aal) == _record(_current_review(db_path, "AAL"), value, 150.0, policy)
    assert _aal_review(db_path, policy, results, None) is None
    aal = _rows(client)["AAL"]
    assert (aal["reviewed"], aal["overrides"]) == (secondary.value_per_share, 0)
    table = _table_moat(db_path, "AAL")
    assert _levels(aal) == _record(secondary, secondary.value_per_share, 150.0, policy, table)


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
    aapl = _rows(client)["AAPL"]
    assert _levels(aapl) == _record(review, value, 150.0, policy)
    assert (aapl["reviewed"], aapl["mechanical"]) == (value, results["AAPL"].value)
    _snapshot(db_path, reprice(results["AAPL"], 115.0, date(2026, 11, 2), policy))
    latest = _newest(db_path, "AAPL")
    aapl = _rows(client)["AAPL"]
    assert _levels(aapl) == _record(review, value, 115.0, policy)
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
    price it was made at, and above once a reprice to $200 puts the price at 1.12 × its $178.24,
    over the band's 1.10.
    The Mechanical column stays empty and the refusal stays; the research read says the same
    word."""
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None
    value, table = secondary.value_per_share, _table_moat(db_path, "AAL")
    refused = results["AAL"]
    aal = _rows(client)["AAL"]
    assert _levels(aal) == _record(secondary, value, 150.0, policy, table)
    assert aal["designation"] == secondary.designation == "below"
    assert (aal["mechanical"], aal["refusal"], aal["moat"]) == (None, refused.refusal, None)
    _snapshot(db_path, replace(refused, price=200.0))  # a reprice
    aal = _rows(client)["AAL"]
    assert _levels(aal) == _record(secondary, value, 200.0, policy, table)
    assert (aal["designation"], aal["mechanical"]) == ("above", None)
    found = client.get("/api/companies/AAL").json()["secondary"]
    assert (found["priceToValue"], found["designation"]) == (
        aal["priceToValue"],
        aal["designation"],
    )


def test_the_rows_word_reads_the_effective_edges(
    client: TestClient, secondaries: dict[str, int]
) -> None:
    """The row's word reads the settings' edges at once, as the drawer's does: AAL's secondary at
    0.84 × its value is below under the default edges and near under a fair band from 0.6, every
    margin of safety at 45% so each class's edges still ascend."""
    assert _rows(client)["AAL"]["designation"] == "below"
    safety = {"None": 0.45, "Narrow": 0.45, "Wide": 0.45}
    changes = {"fair_band": [0.6, 1.15], "margin_of_safety": safety}
    assert client.put("/api/settings", json={"changes": changes}, headers=HEADER).status_code == 200
    detail = client.get("/api/companies/AAL").json()
    assert detail["designationEdges"] == [1 - 0.45, 0.6, 1.15, 1.35]
    assert _rows(client)["AAL"]["designation"] == detail["secondary"]["designation"] == "near"


def test_a_revalued_row_returns_to_the_engines_levels(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """AAL's secondary valuation fills its refused row; a revalue then values the row, its mature
    peers found. The secondary still fills Reviewed, expired early (spec 2026-11-23 held reviewed
    value, 5.9), with its own band, and Mechanical shows the engine's new value. A snapshot of
    other data written with no refresh, which carries no review, leaves AAPL's review on the
    older snapshot: the row shows the engine's value and levels."""
    assert _rows(client)["AAL"]["reviewed"] is not None
    inputs = replace(young_growth_inputs(), symbol="AAL")
    valued = value_company(inputs, universe_deciles(), policy, TODAY)
    assert valued.value is not None
    _snapshot(db_path, valued)
    aal = _rows(client)["AAL"]
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None
    assert (aal["reviewed"], aal["mechanical"]) == (secondary.value_per_share, valued.value)
    assert (aal["freshness"], aal["expiredEarly"]) == ("expired", True)
    moat = _table_moat(db_path, "AAL")
    assert moat is not None and aal["fairValue"] == secondary.value_per_share
    assert _levels(aal) == _in_force(secondary.value_per_share, moat, valued.price, policy)
    _, value = _review(db_path, policy, results)
    assert _rows(client)["AAPL"]["fairValue"] == value
    cited = results["AAPL"]
    assert cited.value is not None
    _snapshot(db_path, replace(cited, value=cited.value + 1.0))  # a revalue
    aapl = _rows(client)["AAPL"]
    assert (aapl["reviewed"], aapl["mechanical"]) == (None, cited.value + 1.0)
    # the engine's value, with the levels and the word read on it (the stored levels are the
    # older value's here, which this stand-in for a revalue kept)
    assert _levels(aapl) == _mechanical(_newest(db_path, "AAPL"), policy)
    assert aapl["fairLow"] == pytest.approx((cited.value + 1.0) * policy.fair_band[0])


def _in_force(value: float, moat: Moat, price: float | None, policy: Policy) -> dict[str, Any]:
    """The band, levels, price ÷ value and word of ``value`` on ``moat`` at ``price`` under
    ``policy``, as ``standing_for`` gives them."""
    s = standing_for(value, moat, price, policy)
    figures = (value, s.levels.fair_low, s.levels.fair_high, s.levels.buy, s.levels.trim)
    return dict(zip(LEVELS, (*figures, s.price_to_value, s.designation), strict=True))


def _mechanical(snapshot: SnapshotRow, policy: Policy) -> dict[str, Any]:
    return _levels(
        screen_row(snapshot, None, TODAY, 0.6667, [], NO_AGENT_FIELDS, mark_min=3, policy=policy)
    )


def test_agent_fields_read_the_policy_and_the_price_they_are_given(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-23 thresholds, 5.3: ``agent_fields`` reads the record's levels and word on the
    policy its caller passes, the effective one, at the latest snapshot's price, on the record's
    own moat class; without a positive price the band and levels stand with no price ÷ value or
    word. ``screen_row`` writes them over the snapshot's and keeps the mechanical value, no
    ``levels`` key of its own; a row with no agent's record reads the snapshot's value the same
    way (``NO_AGENT_FIELDS``)."""
    _, value = _review(db_path, policy, results)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    moat = moat_of(review.result)
    assert moat is not None
    changed = apply_overlay(policy, {"trim_multiple": 1.2, "fair_band": [0.95, 1.05]})
    fields = agent_fields(snapshot, review, None, None, {}, TODAY, changed, None)
    assert fields["levels"] == _in_force(value, moat, 150.0, changed)
    assert fields["levels"]["trimLevel"] == pytest.approx(value * 1.2)
    row = screen_row(snapshot, None, TODAY, 0.6667, [], fields, mark_min=3, policy=changed)
    assert _levels(row) == fields["levels"] and row["mechanical"] == snapshot.value
    assert "levels" not in row
    for price in (None, 0.0):
        unpriced = agent_fields(
            replace(snapshot, price=price), review, None, None, {}, TODAY, changed, None
        )
        assert unpriced["levels"] == fields["levels"] | {"priceToValue": None, "designation": None}
    assert NO_AGENT_FIELDS["levels"] is None


def test_a_mechanical_row_reads_its_levels_on_the_policy_in_force(
    db_path: Path, policy: Policy
) -> None:
    """Spec 2026-11-23 thresholds, 5.3: a mechanical row's levels, price ÷ value and word come
    from its stored value, its moat class and the policy in force, not from the figures stored
    when it was valued: a changed trim multiple and band show with no revalue, and the value
    stays. Under the policy it was valued with, the figures are the stored ones. A row with no
    price has its levels and no word."""
    snapshot = _newest(db_path, "AAPL")
    value, moat = snapshot.value, moat_of(snapshot.result)
    assert value is not None and moat is not None
    assert _mechanical(snapshot, policy) == _engines(snapshot)
    changed = apply_overlay(policy, {"trim_multiple": 1.2, "fair_band": [0.95, 1.05]})
    row = screen_row(snapshot, None, TODAY, 0.6667, [], NO_AGENT_FIELDS, mark_min=3, policy=changed)
    assert row["trimLevel"] == pytest.approx(value * 1.2)
    assert (row["fairLow"], row["fairHigh"]) == pytest.approx((value * 0.95, value * 1.05))
    assert row["fairValue"] == row["mechanical"] == value
    assert _levels(row) == _in_force(value, moat, snapshot.price, changed)
    unpriced = _mechanical(replace(snapshot, price=None), policy)
    assert unpriced == _engines(snapshot) | {"priceToValue": None, "designation": None}


def test_a_row_valued_under_an_older_policy_reads_the_policy_in_force(
    db_path: Path, policy: Policy
) -> None:
    """Review Focus: a snapshot valued under policy v18, whose stored levels are v18's, shows
    v19's levels and word before any revalue."""
    snapshot = _newest(db_path, "AAPL")
    value, moat = snapshot.value, moat_of(snapshot.result)
    assert value is not None and moat is not None
    old = replace(
        snapshot,
        policy_version="fairband-policy-v18",
        buy_level=value * 0.75,
        fair_low=value * 0.85,
        fair_high=value * 1.15,
        trim_level=value * 1.5,
        designation="near",
    )
    assert _mechanical(old, policy) == _in_force(value, moat, snapshot.price, policy)
    assert _mechanical(old, policy)["trimLevel"] == pytest.approx(value * 1.35)


def test_a_reviewed_row_reads_well_below_from_its_own_buy_level(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-23 thresholds, 5.2: at 0.78 × the review's value a Wide row is under its buy
    level and reads Well below; a Narrow row reads Below."""
    _, value = _review(db_path, policy, results)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    priced = replace(snapshot, price=0.78 * value)
    for moat, word in (("Wide", "well-below"), ("Narrow", "below")):
        result = replace(review.result, intermediates=review.result.intermediates | {"moat": moat})
        fields = agent_fields(
            priced, replace(review, result=result), None, None, {}, TODAY, policy, None
        )
        assert fields["levels"]["designation"] == word, moat
        assert fields["levels"]["buyLevel"] == pytest.approx(
            value * (1 - policy.margin_of_safety[moat])  # type: ignore[index]
        )


def test_a_record_with_no_class_in_its_result_reads_the_tables_or_its_stored_levels(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Review Focus: a result with no ``moat`` among its intermediates reads its levels on the
    moat table's class; with no class at all the reader gives the record's stored levels, and the
    word the price has against them, and does not raise."""
    _, value = _review(db_path, policy, results)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    bare = {k: v for k, v in review.result.intermediates.items() if k != "moat"}
    unclassed = replace(review, result=replace(review.result, intermediates=bare))
    changed = apply_overlay(policy, {"trim_multiple": 1.2})
    on_table = agent_fields(snapshot, unclassed, None, None, {}, TODAY, changed, "Narrow")
    assert on_table["levels"] == _in_force(value, "Narrow", 150.0, changed)
    stored = agent_fields(snapshot, unclassed, None, None, {}, TODAY, changed, None)["levels"]
    assert (stored["buyLevel"], stored["fairLow"], stored["fairHigh"], stored["trimLevel"]) == (
        review.buy_level,
        review.fair_low,
        review.fair_high,
        review.trim_level,
    )
    assert stored["priceToValue"] == 150.0 / value
    assert review.fair_low is not None and review.fair_high is not None
    assert review.fair_low <= 150.0 <= review.fair_high and stored["designation"] == "near"


def test_a_row_in_another_currency_reads_its_levels_on_the_dollar_value(
    db_path: Path, policy: Policy
) -> None:
    """Review Focus: a company in another currency has its levels in force on the value in US
    dollars, the snapshot's own value, not on the route's value in the currency."""
    _snapshot(db_path, value_company(fx_inputs(), universe_deciles(), policy, TODAY))
    snapshot = _newest(db_path, "FXCO")
    value, moat = snapshot.value, moat_of(snapshot.result)
    assert value is not None and moat is not None
    assert snapshot.result.intermediates["value_in_currency"] != value
    row = _mechanical(snapshot, policy)
    assert row["buyLevel"] == pytest.approx(value * (1 - policy.margin_of_safety[moat]))
    assert row == _in_force(value, moat, snapshot.price, policy)


def test_a_counting_review_sets_the_rows_flags(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-13 8a: where a review fills the row, the row's flag words and its count of
    quality warnings are the review's; a row with no agent's record keeps the snapshot's."""
    _review(db_path, policy, results)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    assert flag_count(snapshot.result.flags) == 1
    settled = replace(review, result=replace(review.result, flags=()))
    fields = agent_fields(snapshot, settled, None, None, {}, TODAY, policy, None)
    assert fields["flags"] == ()
    row = screen_row(snapshot, None, TODAY, 0.6667, [], fields, mark_min=3, policy=policy)
    assert (row["flags"], row["flagCount"]) == ([], 0)
    kept = screen_row(snapshot, None, TODAY, 0.6667, [], NO_AGENT_FIELDS, mark_min=3, policy=policy)
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
    fields = agent_fields(snapshot, bare, None, None, {}, TODAY, policy, None)
    assert fields["flags"] is None
    engines = ([f.word for f in snapshot.result.flags], flag_count(snapshot.result.flags))
    assert engines[1] == 1
    for row in (
        screen_row(snapshot, None, TODAY, 0.6667, [], fields, mark_min=3, policy=policy),
        _rows(client)["AAPL"],
    ):
        assert (row["flags"], row["flagCount"]) == engines


def test_a_refused_rows_secondary_leaves_the_engines_flags(
    client: TestClient, db_path: Path, policy: Policy, secondaries: dict[str, int]
) -> None:
    """Spec 2026-11-13 8a: on AAL's refused row the secondary valuation fills Reviewed and has no
    flags, so the row's flags and count stay the snapshot's: three notes and no warning."""
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None
    snapshot = _newest(db_path, "AAL")
    fields = agent_fields(snapshot, None, secondary, None, {}, TODAY, policy, None)
    assert (fields["reviewed"], fields["flags"]) == (secondary.value_per_share, None)
    engines = ([f.word for f in snapshot.result.flags], flag_count(snapshot.result.flags))
    assert (len(engines[0]), engines[1]) == (3, 0)
    for row in (
        screen_row(snapshot, None, TODAY, 0.6667, [], fields, mark_min=3, policy=policy),
        _rows(client)["AAL"],
    ):
        assert (row["flags"], row["flagCount"]) == engines


def test_the_row_reads_the_snapshots_flags_not_the_reviews(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult], secondaries: dict[str, int]
) -> None:
    """Spec 2026-11-19 7.5: ``warnings`` are the plain words of the snapshot's quality warnings,
    whatever flags a counting review holds, where ``flags`` and ``flagCount`` read the review's;
    ``marked`` holds on a mechanical value with ``mark_min`` warnings or more and no reviewed
    value. A review that fills the row takes the mark away, a refused review fills nothing and
    leaves it, two warnings under three have none, and a refused row has none whatever its
    warnings, a secondary standing in or not."""
    _review(db_path, policy, results)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    assert [f.code for f in snapshot.result.flags] == ["value-spread"]
    three = (
        Flag("heavy-capex", "Heavy capex", ""),
        Flag("fcf-sign", "Free cash flow disagrees", ""),  # a note
        Flag("negative-fcf", "Negative free cash flow", ""),
        Flag("equity-raise", "Equity raise", ""),
    )
    words = ["heavy capital spending", "negative free cash flow", "new shares issued"]

    def row(found: SnapshotRow, fields: Mapping[str, Any], mark_min: int = 3) -> dict[str, Any]:
        return screen_row(found, None, TODAY, 0.6667, [], fields, mark_min=mark_min, policy=policy)

    def mark(found: SnapshotRow, fields: Mapping[str, Any], mark_min: int = 3) -> tuple[Any, Any]:
        """The row's ``warnings`` and ``marked``."""
        drawn = row(found, fields, mark_min)
        return drawn["warnings"], drawn["marked"]

    # a counting review with three warnings: the row's flags are its, the warnings the snapshot's
    warned_review = replace(review, result=replace(review.result, flags=three))
    fields = agent_fields(snapshot, warned_review, None, None, {}, TODAY, policy, None)
    drawn = row(snapshot, fields)
    assert (drawn["flags"], drawn["flagCount"]) == ([f.word for f in three], 3)
    assert mark(snapshot, fields) == (["value sensitive to its inputs"], False)

    # the snapshot with three warnings: marked alone, unmarked under a review that fills the row,
    # still marked under a review that refused, which fills nothing
    warned = replace(snapshot, result=replace(snapshot.result, flags=three))
    assert mark(warned, NO_AGENT_FIELDS) == (words, True)
    settled = replace(review, result=replace(review.result, flags=()))
    filled = agent_fields(warned, settled, None, None, {}, TODAY, policy, None)
    assert row(warned, filled)["flags"] == [] and mark(warned, filled) == (words, False)
    refused = agent_fields(
        warned, replace(settled, value=None), None, None, {}, TODAY, policy, None
    )
    assert refused["reviewed"] is None and mark(warned, refused) == (words, True)
    # the cut-off is the caller's, and two warnings are under three
    assert mark(warned, NO_AGENT_FIELDS, mark_min=4) == (words, False)
    two = replace(snapshot, result=replace(snapshot.result, flags=three[:3]))
    assert mark(two, NO_AGENT_FIELDS) == (words[:2], False)

    # a refused row: its warnings read, and no mark, a secondary standing in or not
    aal = _newest(db_path, "AAL")
    refused_row = replace(aal, result=replace(aal.result, flags=three))
    assert refused_row.value is None
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    stood_in = agent_fields(refused_row, None, secondary, None, {}, TODAY, policy, None)
    assert stood_in["reviewed"] is not None
    for standing_in in (NO_AGENT_FIELDS, stood_in):
        assert mark(refused_row, standing_in) == (words, False)


def test_a_secondary_at_or_below_zero_fills_no_reviewed_value(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """The record stays on file; the cell shows an em dash and "Has a review", which keeps
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
