"""The moat class's write and its reads (spec 2026-11-19 8.6, 8.7), on the database of
``conftest.py`` with this module's moat table in place of the packaged file (``moat_file``): AAPL
Narrow, AAL and HGCO None, BF.B Narrow and STMT Wide, and no class for NEWC (an entrant) or BSIS.
Beside the conftest's three companies, BF.B (a ticker with a dot) is valued, NEWC is refused "no
moat class", BSIS is refused for its listed-share basis and STMT for its statements. The write
values the company again inside the request; ``run.build_inputs`` builds each company's inputs as
this module valued them, on its row of the moat table (``with_table_moat``), as
``test_reviews_api`` builds them for the override routes."""

import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi.testclient import TestClient
from support.engine_companies import (
    high_growth_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.moat import moat_table
from support.web import CREATED, HEADER, HOST, NOW, TODAY

from fairband import __main__ as cli
from fairband.engine import METHOD_VERSION
from fairband.engine.classifier import Deciles
from fairband.engine.levels import levels_for
from fairband.engine.overrides import current_reading
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import TaggedInput
from fairband.policy import Moat, Policy
from fairband.policy.moat import MoatTable
from fairband.policy.tax import TaxTable
from fairband.refresh import run
from fairband.refresh.inputs import with_table_moat
from fairband.store.db import connect
from fairband.store.ledger import LedgerRow, Writer, entries
from fairband.store.moat import MoatRow, moat_row
from fairband.store.overrides import insert_override
from fairband.store.refreshes import (
    create_refresh,
    current_refresh,
    latest_refresh,
    save_deciles,
)
from fairband.store.reviews import latest_review
from fairband.store.snapshots import SnapshotRow, insert_snapshot, latest_snapshot
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER

AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
FILING = {"kind": "filing", "ref": "10-K 2025, p. 12", "note": None}
REASON = "switching costs hold: the installed base renews at 95%"
NEEDS_A_REASON = "a moat verdict needs a reason"
NEEDS_EVIDENCE = "a moat verdict needs evidence"
RUNNING = "a refresh is running: set the class when it ends"
OWNERS_RETURN = "returning to Fairband's class is the owner's"
GUIDANCE_REF = "a guidance item cites its record as guidance:<id>"
SET_FIRST = "set the moat class first: moat_set"
BASIS = (
    "share basis unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the ADR"
    " ratio 10)"
)
NO_STATEMENTS = "no financial statements"
ONE_PART = {
    "parts": [{"name": "the business", "fcff": [1e10, 1.05e10, 1.1e10], "terminalGrowth": 0.03}],
    "reason": "the services segment carries the company",
    "evidence": [FILING],
}
# The module's moat table: the class each company's row holds before a test writes one.
MOATS: dict[str, Moat] = {
    "AAPL": "Narrow",
    "AAL": "None",
    "HGCO": "None",
    "BF.B": "Narrow",
    "STMT": "Wide",
}
GOLDEN = mature_growth_inputs()
INPUTS: dict[str, CompanyInputs] = {
    "AAPL": replace(GOLDEN, symbol="AAPL"),
    "AAL": replace(young_growth_inputs(), symbol="AAL", peers=()),
    "HGCO": high_growth_inputs(),
    "BF.B": replace(GOLDEN, symbol="BF.B"),
    "NEWC": replace(GOLDEN, symbol="NEWC"),
    "BSIS": replace(GOLDEN, symbol="BSIS", refusal=BASIS),
    "STMT": replace(GOLDEN, symbol="STMT", refusal=NO_STATEMENTS),
}


@pytest.fixture
def moat_file() -> MoatTable:
    return moat_table(MOATS)


@pytest.fixture(autouse=True)
def stored(db_path: Path, policy: Policy, monkeypatch: pytest.MonkeyPatch) -> None:
    """The universe deciles under the conftest's full refresh; a snapshot of BF.B, NEWC, BSIS and
    STMT valued on its row of the moat table; and ``run.build_inputs`` building each company's
    inputs on its row (module docstring)."""
    deciles = universe_deciles()
    with closing(connect(db_path)) as conn:
        save_deciles(conn, 1, deciles, CREATED)
        for symbol in ("BF.B", "NEWC", "BSIS", "STMT"):
            result = value_company(with_table_moat(conn, INPUTS[symbol]), deciles, policy, TODAY)
            insert_snapshot(conn, result, 1, clock=lambda: CREATED)

    def build(
        conn: sqlite3.Connection,
        symbol: str,
        policy: Policy,
        tax: TaxTable,
        today: date,
        deciles: Deciles | None = None,
    ) -> CompanyInputs:
        assert deciles is not None  # the stored deciles
        return with_table_moat(conn, INPUTS[symbol])

    monkeypatch.setattr(run, "build_inputs", build)


def _put(
    client: TestClient, body: dict[str, Any], symbol: str = "AAPL", headers: Any = HEADER
) -> Any:
    r = client.put(f"/api/companies/{symbol}/moat", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _refused_put(
    client: TestClient, body: dict[str, Any], symbol: str = "AAPL", headers: Any = HEADER
) -> tuple[int, Any]:
    r = client.put(f"/api/companies/{symbol}/moat", json=body, headers=headers)
    return r.status_code, r.json()


def _delete(client: TestClient, symbol: str = "AAPL", headers: Any = HEADER) -> tuple[int, Any]:
    r = client.delete(f"/api/companies/{symbol}/moat", headers=headers)
    return r.status_code, r.json()


def _row(db_path: Path, symbol: str = "AAPL") -> MoatRow | None:
    with closing(connect(db_path)) as conn:
        return moat_row(conn, symbol)


def _latest(db_path: Path, symbol: str = "AAPL") -> SnapshotRow:
    with closing(connect(db_path)) as conn:
        found = latest_snapshot(conn, symbol)
    assert found is not None
    return found


def _ledger(db_path: Path, symbol: str = "AAPL") -> list[LedgerRow]:
    with closing(connect(db_path)) as conn:
        return entries(conn, symbol)


def _moat_input(snapshot: SnapshotRow) -> TaggedInput:
    return next(i for i in snapshot.result.inputs if i.name == "moat_class")


def _state(db_path: Path) -> tuple[Any, ...]:
    """Everything a write touches: the moat table, the ledger, the refresh records and the
    snapshots."""
    with closing(connect(db_path)) as conn:
        return tuple(
            [tuple(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY 1")]
            for table in ("moat_classes", "ledger", "refreshes", "snapshots")
        )


def test_the_owner_sets_a_class(client: TestClient, db_path: Path, policy: Policy) -> None:
    """The owner's write (spec 8.6): the row becomes the owner's, its class before it Narrow; a
    ledger row "moat Narrow → Wide" on the snapshot it rested on; then the revalue of AAPL alone,
    a record of kind revalue naming it, whose snapshot cites the owner's Wide as a JUDGMENT; the row
    cites that snapshot, and the answer names both."""
    before = _latest(db_path)
    body = _put(client, {"class": "Wide"})
    after = _latest(db_path)
    assert after.id > before.id and after.value is not None
    assert after.value == pytest.approx(
        value_company(INPUTS["AAPL"], universe_deciles(), policy, TODAY).value
    )
    row = _row(db_path)
    assert row is not None
    assert (row.moat, row.source, row.previous, row.reason, row.evidence) == (
        "Wide",
        "owner",
        "Narrow",
        None,
        None,
    )
    assert (row.principal, row.actor, row.client, row.file_version) == ("owner", None, None, None)
    assert (row.judged_on, row.at, row.snapshot_id) == (NOW.date(), NOW, after.id)
    assert body == {
        "moatClass": {
            "class": "Wide",
            "source": "owner",
            "fileVersion": None,
            "judgedOn": NOW.date().isoformat(),
            "previous": "Narrow",
            "reason": None,
            "actor": None,
            "at": NOW.isoformat(),
            "fileClass": "Narrow",
        },
        "snapshot": {"id": after.id, "value": after.value, "refusal": None},
    }
    [entry] = _ledger(db_path)
    assert (entry.kind, entry.principal, entry.summary) == ("moat", "owner", "moat Narrow → Wide")
    assert (entry.snapshot_id, entry.ref_table, entry.ref_id, entry.at) == (
        before.id,
        None,
        None,
        NOW,
    )
    with closing(connect(db_path)) as conn:
        refresh = latest_refresh(conn)
    assert refresh is not None and after.refresh_id == refresh.id
    assert (refresh.kind, refresh.symbols, refresh.status, refresh.stage) == (
        "revalue",
        ("AAPL",),
        "done",
        "done",
    )
    assert (refresh.policy_version, refresh.method_version) == (policy.version, METHOD_VERSION)
    cited = _moat_input(after)
    assert (cited.tag, cited.provenance.source, cited.note) == ("JUDGMENT", "owner", "Wide")
    assert cited.provenance.as_of == NOW.date()
    # the other companies keep their snapshots
    assert _latest(db_path, "HGCO").refresh_id == 1


def test_the_status_line_s_run_stays_the_one_before_a_write(
    client: TestClient, db_path: Path
) -> None:
    """A write values one company. The refresh route answers its revalue as ``last`` and the run
    before it as ``shown``, the run the page's status line and stamp describe (the founder,
    2026-11-22: the line is about the last run of the whole screen)."""
    before = client.get("/api/refresh/current").json()
    assert before["shown"] == before["last"] and before["last"]["kind"] == "full"
    _put(client, {"class": "Wide"})
    after = client.get("/api/refresh/current").json()
    assert (after["last"]["kind"], after["last"]["status"]) == ("revalue", "done")
    assert after["last"]["id"] > before["last"]["id"]
    assert after["shown"] == before["last"]


def test_an_agent_needs_a_reason_and_evidence(client: TestClient, db_path: Path) -> None:
    """An agent's verdict needs a reason, then one evidence item or more, as an override does:
    each a 400, and nothing is stored."""
    before = _state(db_path)
    assert _refused_put(client, {"class": "Wide", "evidence": [FILING]}, headers=AGENT) == (
        400,
        {"detail": NEEDS_A_REASON},
    )
    for evidence in ({}, {"evidence": []}):
        assert _refused_put(
            client, {"class": "Wide", "reason": REASON} | evidence, headers=AGENT
        ) == (
            400,
            {"detail": NEEDS_EVIDENCE},
        )
    assert _state(db_path) == before


def test_an_agent_s_guidance_evidence_is_checked(client: TestClient, db_path: Path) -> None:
    """An agent's evidence item of kind ``guidance`` names a current guidance record of the company
    as ``guidance:<id>``, as an override's does (spec 8.6; ``reviews_api.require_guidance``): a
    record that is not the company's is a 404, a ref of another form a 400; nothing is stored."""
    before = _state(db_path)
    for ref, refused in (
        ("guidance:99999", (404, {"detail": "no guidance record 99999 for AAPL"})),
        ("guidance:x", (400, {"detail": GUIDANCE_REF})),
    ):
        cite = {"kind": "guidance", "ref": ref, "note": None}
        body = {"class": "Wide", "reason": REASON, "evidence": [FILING, cite]}
        assert _refused_put(client, body, headers=AGENT) == refused, ref
    assert _state(db_path) == before


def test_a_reason_of_spaces(client: TestClient, db_path: Path) -> None:
    """Review Focus 4: the owner's reason of spaces is stored as none, so neither the ledger nor
    the snapshot's note carries ": "; an agent's is a 400, "a moat verdict needs a reason"."""
    before = _state(db_path)
    blank = {"class": "Wide", "reason": "   ", "evidence": [FILING]}
    assert _refused_put(client, blank, headers=AGENT) == (400, {"detail": NEEDS_A_REASON})
    assert _state(db_path) == before
    _put(client, {"class": "Wide", "reason": " \n "})
    row = _row(db_path)
    assert row is not None and (row.source, row.reason) == ("owner", None)
    assert [e.summary for e in _ledger(db_path)] == ["moat Narrow → Wide"]
    assert _moat_input(_latest(db_path)).note == "Wide"


def test_the_other_refusals(client: TestClient, db_path: Path, policy: Policy) -> None:
    """A class outside the three is a 400; a company with no snapshot a 404, "no snapshot for
    <symbol>"; a write while a refresh runs a 409, the delete's too; none stores anything."""
    before = _state(db_path)
    status, body = _refused_put(client, {"class": "Medium"})
    assert status == 400 and body["detail"].startswith("class: ")
    assert _refused_put(client, {"class": "Wide"}, "ZZZZ") == (
        404,
        {"detail": "no snapshot for ZZZZ"},
    )
    assert _state(db_path) == before
    with closing(connect(db_path)) as conn:
        create_refresh(
            conn, "scoped", ["HGCO"], policy.version, METHOD_VERSION, NOW, policy.settings_hash
        )
    running = _state(db_path)
    assert _refused_put(client, {"class": "Wide"}) == (409, {"detail": RUNNING})
    agent = {"class": "Wide", "reason": REASON, "evidence": [FILING]}
    assert _refused_put(client, agent, headers=AGENT) == (409, {"detail": RUNNING})
    assert _delete(client) == (409, {"detail": RUNNING})
    assert _state(db_path) == running


def test_the_same_class_again_and_the_newest_write(client: TestClient, db_path: Path) -> None:
    """The class in force written again is a write like any other (spec 8.6): the row becomes the
    writer's, here an agent's with its reason and evidence, and the company is valued again, its
    snapshot citing the agent; the newest write is in force."""
    _put(client, {"class": "Wide"})
    owners = _latest(db_path)
    agent = {"class": "Wide", "reason": REASON, "evidence": [FILING]}
    body = _put(client, agent, headers=AGENT)
    again = _latest(db_path)
    assert again.id > owners.id
    row = _row(db_path)
    assert row is not None
    assert (row.moat, row.source, row.previous, row.reason) == ("Wide", "agent", "Wide", REASON)
    assert (row.principal, row.actor, row.client) == ("agent", "claude-opus-5-5", "claude-code/2.1")
    assert (row.evidence, row.snapshot_id) == ((FILING,), again.id)
    assert body["moatClass"]["source"] == "agent"
    assert body["moatClass"]["actor"] == "claude-opus-5-5"
    cited = _moat_input(again)
    assert (cited.tag, cited.provenance.source, cited.note) == (
        "JUDGMENT",
        "agent claude-opus-5-5",
        f"Wide: {REASON}",
    )
    _put(client, {"class": "Narrow"})
    newest = _row(db_path)
    assert newest is not None
    assert (newest.moat, newest.source, newest.previous, newest.reason) == (
        "Narrow",
        "owner",
        "Wide",
        None,
    )
    assert _moat_input(_latest(db_path)).note == "Narrow"
    assert [(e.principal, e.summary) for e in _ledger(db_path)] == [
        ("owner", "moat Wide → Narrow"),
        ("agent", f"moat Wide → Wide: {REASON}"),
        ("owner", "moat Narrow → Wide"),
    ]


def test_a_review_follows_the_new_snapshot(client: TestClient, db_path: Path) -> None:
    """A company with an applied override gets a review on the snapshot the write's revalue
    writes, as after any value stage (spec 8.6: ``follow_snapshot``)."""
    snapshot = _latest(db_path)
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    with closing(connect(db_path)) as conn:
        belief = insert_override(
            conn,
            "AAPL",
            "growth.belief",
            current_reading(snapshot.result, "growth.belief"),
            0.08,
            "ratio",
            "guidance raised",
            [FILING],
            "lasting",
            None,
            None,
            snapshot.id,
            writer,
            NOW,
            "applied",
            "",
        )
    body = _put(client, {"class": "Wide"})
    with closing(connect(db_path)) as conn:
        review = latest_review(conn, "AAPL")
    assert review is not None
    assert (review.snapshot_id, review.override_ids) == (body["snapshot"]["id"], (belief,))


def test_a_company_without_a_row(client: TestClient, db_path: Path) -> None:
    """Review Focus 2: an entrant the moat table holds no class for is refused "no moat class"
    and has none to return to (404); a write has no class before it, its ledger row reads "moat
    Wide", and the company is valued."""
    assert _latest(db_path, "NEWC").refusal == "no moat class"
    detail = client.get("/api/companies/NEWC").json()
    assert (detail["moat"], detail["moatClass"]) == (None, None)
    gone = {"detail": "the moat table holds no class for NEWC"}
    assert _delete(client, "NEWC") == (404, gone)
    body = _put(client, {"class": "Wide"}, "NEWC")
    valued = _latest(db_path, "NEWC")
    assert valued.value is not None and valued.refusal is None
    assert body["snapshot"] == {"id": valued.id, "value": valued.value, "refusal": None}
    assert (body["moatClass"]["previous"], body["moatClass"]["fileClass"]) == (None, None)
    assert [e.summary for e in _ledger(db_path, "NEWC")] == ["moat Wide"]
    assert client.get("/api/companies/NEWC").json()["moat"] == "Wide"
    assert _delete(client, "NEWC") == (404, gone)


def test_the_owner_returns_to_the_file_and_an_agent_cannot(
    client: TestClient, db_path: Path
) -> None:
    """``DELETE`` returns the owner's row to the file's entry and values the company again; an
    agent's is a 403 and changes nothing."""
    _put(client, {"class": "Wide", "reason": "the brand holds"})
    before = _state(db_path)
    assert _delete(client, headers=AGENT) == (403, {"detail": OWNERS_RETURN})
    assert _state(db_path) == before
    owners = _latest(db_path)
    status, body = _delete(client)
    returned = _latest(db_path)
    assert status == 200 and returned.id > owners.id
    assert body == {
        "moatClass": {
            "class": "Narrow",
            "source": "file",
            "fileVersion": "fairband-moat-v1",
            "judgedOn": "2026-11-19",
            "previous": None,
            "reason": None,
            "actor": None,
            "at": NOW.isoformat(),
            "fileClass": "Narrow",
        },
        "snapshot": {"id": returned.id, "value": returned.value, "refusal": None},
    }
    row = _row(db_path)
    assert row is not None
    assert (row.source, row.principal, row.snapshot_id, row.evidence) == (
        "file",
        "system",
        None,
        None,
    )
    cited = _moat_input(returned)
    assert (cited.tag, cited.provenance.source, cited.note) == (
        "RULE",
        "moat table fairband-moat-v1",
        "Narrow",
    )
    entry = _ledger(db_path)[0]
    assert (entry.kind, entry.principal, entry.summary, entry.snapshot_id) == (
        "moat",
        "owner",
        "moat Wide → Narrow: Fairband's class",
        owners.id,
    )


def test_a_dotted_symbol(client: TestClient, db_path: Path) -> None:
    """Review Focus 1: a ticker with a dot reaches the write and the return, in either case."""
    body = _put(client, {"class": "Wide"}, "BF.B")
    assert body["moatClass"] | {"at": None} == {
        "class": "Wide",
        "source": "owner",
        "fileVersion": None,
        "judgedOn": NOW.date().isoformat(),
        "previous": "Narrow",
        "reason": None,
        "actor": None,
        "at": None,
        "fileClass": "Narrow",
    }
    assert body["snapshot"]["id"] == _latest(db_path, "BF.B").id
    status, returned = _delete(client, "bf.b")
    assert (status, returned["moatClass"]["source"]) == (200, "file")
    assert client.get("/api/companies/BF.B").json()["moatClass"]["class"] == "Narrow"
    assert [e.summary for e in _ledger(db_path, "BF.B")] == [
        "moat Wide → Narrow: Fairband's class",
        "moat Narrow → Wide",
    ]


def test_the_write_calls_no_vendor(
    client: TestClient, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The conftest's app has no refresh worker and no pass-through; the write values the company
    on the facts the store holds with no fetch, no universe and no rates, and stores no vendor
    response."""

    def no_call(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the moat write calls no vendor")

    for name in ("fetch_company", "fetch_rates", "build_universe", "backfill_statement_facts"):
        monkeypatch.setattr(run, name, no_call)
    with closing(connect(db_path)) as conn:
        stored = conn.execute("SELECT COUNT(*) FROM vendor_responses").fetchone()[0]
    _put(client, {"class": "Wide"})
    _delete(client)
    with closing(connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM vendor_responses").fetchone()[0] == stored


def test_a_write_that_fails_in_its_revalue_stores_nothing(
    client: TestClient, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exception inside the revalue rolls the whole write back: the moat table, the ledger, the
    refresh records and the snapshots are as they were, and no refresh is left running to block
    the next write."""
    before = _state(db_path)

    def broken(*args: Any) -> Any:
        raise RuntimeError("assembly broke")

    monkeypatch.setattr(run, "build_inputs", broken)
    with pytest.raises(RuntimeError, match="assembly broke"):
        client.put("/api/companies/AAPL/moat", json={"class": "Wide"}, headers=HEADER)
    with pytest.raises(RuntimeError, match="assembly broke"):
        client.delete("/api/companies/AAPL/moat", headers=HEADER)
    assert _state(db_path) == before
    with closing(connect(db_path)) as conn:
        assert current_refresh(conn) is None


def test_the_detail_carries_the_row(client: TestClient, db_path: Path) -> None:
    """The detail's ``moatClass`` (spec 8.6): the file's row; the owner's with the file's class
    beside it; none without a row; and ``moat``, the row's class, a refused row's too."""
    aapl = client.get("/api/companies/AAPL").json()
    assert (aapl["moat"], aapl["moatClass"]) == (
        "Narrow",
        {
            "class": "Narrow",
            "source": "file",
            "fileVersion": "fairband-moat-v1",
            "judgedOn": "2026-11-19",
            "previous": None,
            "reason": None,
            "actor": None,
            "at": CREATED.isoformat(),
            "fileClass": "Narrow",
        },
    )
    _put(client, {"class": "Wide", "reason": "the brand holds"})
    owners = client.get("/api/companies/AAPL").json()
    assert (owners["moat"], owners["moatClass"]) == (
        "Wide",
        {
            "class": "Wide",
            "source": "owner",
            "fileVersion": None,
            "judgedOn": NOW.date().isoformat(),
            "previous": "Narrow",
            "reason": "the brand holds",
            "actor": None,
            "at": NOW.isoformat(),
            "fileClass": "Narrow",
        },
    )
    newc = client.get("/api/companies/NEWC").json()
    assert (newc["moat"], newc["moatClass"]) == (None, None)
    # AAL is refused for its target margin: its row's class all the same
    aal = client.get("/api/companies/AAL").json()
    assert (aal["result"]["value"], aal["result"]["refusal"]) == (
        None,
        "no target margin: 0 mature peers",
    )
    assert (aal["moat"], aal["moatClass"]["class"], aal["moatClass"]["source"]) == (
        "None",
        "None",
        "file",
    )


def test_the_secondary_valuation_reads_the_row(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """Spec 8.7: a company with no row is refused "set the moat class first: moat_set", whatever
    its snapshot's refusal, the listed-share basis's too; a company refused for its statements,
    before any moat entered its snapshot, takes its row's class for its levels, Wide's."""
    for symbol in ("NEWC", "BSIS"):
        r = client.post(f"/api/companies/{symbol}/secondary", json=ONE_PART, headers=AGENT)
        assert (r.status_code, r.json()) == (400, {"detail": SET_FIRST})
    stmt = _latest(db_path, "STMT")
    assert stmt.refusal == NO_STATEMENTS
    assert not any(i.name == "moat_class" for i in stmt.result.inputs)
    r = client.post("/api/companies/STMT/secondary", json=ONE_PART, headers=AGENT)
    assert r.status_code == 201, r.text
    body = r.json()
    wide = levels_for(body["valuePerShare"], "Wide", policy)
    assert (body["buyLevel"], body["fairLow"], body["fairHigh"], body["trimLevel"]) == (
        wide.buy,
        wide.fair_low,
        wide.fair_high,
        wide.trim,
    )
    assert body["buyLevel"] != levels_for(body["valuePerShare"], "None", policy).buy


def test_serve_hands_the_app_the_table_its_runs_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, moat_file: MoatTable
) -> None:
    """``serve`` reads the moat file once and hands the app the table each run loads, so the
    write and the refreshes read one version of the file."""
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    monkeypatch.setattr(cli, "load_moat_table", lambda: moat_file)
    made: Counter[int] = Counter()
    real = cli.create_app

    def create_app(*args: Any, **kwargs: Any) -> Any:
        made[id(kwargs.get("moat"))] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(cli, "create_app", create_app)
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: TestClient(app, base_url=HOST))
    assert cli.main(["serve"]) == 0
    assert made == Counter({id(moat_file): 1})
