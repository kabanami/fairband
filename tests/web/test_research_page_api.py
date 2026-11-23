"""The Research tab's read (the Research tab's design, 7.5 and 8.1), on the database of
``conftest.py``: AAPL valued on the Mature Growth route at a price of $150, AAL refused for its
target margin and HGCO valued on the revenue growth route, each with one snapshot and a secondary
valuation on it where a test asks for them (``secondaries``), and an agent's moat verdict on it
where a test publishes a report (``verdicts``, spec 2026-11-19 8.7).

``report_call`` is read on the database's own rows, their figures changed (``dataclasses.replace``):
a snapshot, a review and a secondary valuation; ``of_report`` on rows made here. The route is read
on reports published through the report route (``support.reports``)."""

import json
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from support.engine_companies import mature_growth_inputs, universe_deciles, young_growth_inputs
from support.page_payloads import QUOTE
from support.reports import AGENT, body, published, snapshot_id
from support.vendor import Vendor, passthrough_client
from support.web import HEADER, NOW, TODAY
from support.web_app import record_verdict

from fairband.engine.designation import designation_for
from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.refresh.passthrough import Passthrough
from fairband.reports.check import HEADINGS
from fairband.store.db import connect
from fairband.store.ledger import Writer
from fairband.store.observations import insert_observations
from fairband.store.overrides import insert_override
from fairband.store.refreshes import latest_refresh
from fairband.store.reports import ReportRow
from fairband.store.research import KillCriterionRow, NewsItemRow
from fairband.store.reviews import ReviewRow, insert_review, review_row
from fairband.store.secondary import SecondaryRow, secondary_row
from fairband.store.snapshots import SnapshotRow, insert_snapshot, latest_snapshot, snapshot_row
from fairband.store.vendor import record_response
from fairband.vendors.normalize_fmp import quote_observations
from fairband.vendors.page_fmp import head_quote
from fairband.web.research_page import of_report, report_call

REFUSED_REVIEW = "the reviewed margin is refused"
# The lists of the research read (``GET /api/companies/{symbol}/research``), in its order.
RESEARCH = (
    "overrides",
    "guidance",
    "judgments",
    "killCriteria",
    "newsItems",
    "notes",
    "findings",
    "ledger",
)
# A report whose sections are plain words, which rests on the company's latest snapshot.
PLAIN = [{"heading": h, "parts": ["Plain words."]} for h in HEADINGS]
# AAL's route, the revenue-growth route's, asks for the target margin in place of the ROIC.
REFUSED_JUDGMENTS = [
    {"judgment": kind, "decision": f"keep the {kind}"}
    for kind in ("phase", "moat", "belief", "target_margin")
]


@dataclass(frozen=True)
class _Rows:
    """The database's own rows: AAPL's snapshot valued at $100 and priced $150, AAL's refused one
    priced $150, a review of AAPL valued at $80, and AAL's secondary valuation of $12 a share; each
    with its levels at a fixed share of its value (``_band``)."""

    valued: SnapshotRow
    refused: SnapshotRow
    review: ReviewRow
    secondary: SecondaryRow


def _word(value: float, price: float) -> tuple[float, str]:
    """Price ÷ ``value`` and the word ``price`` has against the levels a row of ``value`` carries
    here (``_band``): the card's word, read on the record's own stored levels (spec 2026-11-23
    thresholds, 5.4)."""
    buy, low, high, trim = _band(value)
    return designation_for(price, value, (buy / value, low / value, high / value, trim / value))


@pytest.fixture
def rows(db_path: Path, results: dict[str, ValuationResult], secondaries: dict[str, int]) -> _Rows:
    mechanical = results["AAPL"]
    with closing(connect(db_path)) as conn:
        valued = latest_snapshot(conn, "AAPL")
        refused = latest_snapshot(conn, "AAL")
        assert valued is not None and refused is not None and refused.refusal is not None
        review = Review(mechanical, mechanical.value, (), ())
        review_id = insert_review(conn, review, "AAPL", valued.id, None, clock=lambda: NOW)
        reviewed = review_row(conn, review_id)
        secondary = secondary_row(conn, secondaries["AAL"])
    assert reviewed is not None and secondary is not None
    buy, low, high, trim = _band(100.0)
    valued = replace(
        valued,
        value=100.0,
        buy_level=buy,
        fair_low=low,
        fair_high=high,
        trim_level=trim,
        price=150.0,
    )
    buy, low, high, trim = _band(80.0)
    reviewed = replace(
        reviewed, value=80.0, buy_level=buy, fair_low=low, fair_high=high, trim_level=trim
    )
    buy, low, high, trim = _band(12.0)
    secondary = replace(
        secondary,
        value_per_share=12.0,
        buy_level=buy,
        fair_low=low,
        fair_high=high,
        trim_level=trim,
    )
    return _Rows(valued, replace(refused, price=150.0), reviewed, secondary)


def _band(value: float) -> tuple[float, float, float, float]:
    """The four levels a row of ``value`` carries here: buy, the fair band's ends and trim."""
    return value * 0.7, value * 0.9, value * 1.1, value * 1.6


def _levels(value: float) -> dict[str, float]:
    buy, low, high, trim = _band(value)
    return {"buy": buy, "fairLow": low, "fairHigh": high, "trim": trim}


def _no_value(review: ReviewRow, refusal: str) -> ReviewRow:
    """``review`` refused: no value, no levels, ``refusal`` its sentence."""
    return replace(
        review,
        value=None,
        buy_level=None,
        fair_low=None,
        fair_high=None,
        trim_level=None,
        price_to_value=None,
        designation=None,
        refusal=refusal,
    )


# ------------------------------------------------------------------ the report's call


def test_the_call_of_a_report_with_no_review(
    rows: _Rows,
) -> None:
    """The snapshot's value and levels; its price, its days and its window. The word is the
    price's against the record's own stored levels: at 1.5 × the value it is above, under this
    row's stored trim level of 1.6 ×, though the policy's trim multiple in force is 1.35."""
    snapshot = rows.valued
    ratio, word = _word(100.0, 150.0)
    assert snapshot.price_date is not None and (ratio, word) == (1.5, "above")
    assert report_call(snapshot, None, None) == {
        "value": 100.0,
        "basis": "mechanical",
        "note": None,
        "levels": _levels(100.0),
        "priceToValue": ratio,
        "designation": word,
        "price": 150.0,
        "priceDate": snapshot.price_date.isoformat(),
        "dataDate": snapshot.data_date.isoformat(),
        "validUntil": snapshot.valid_until.isoformat(),
        "mechanicalValue": 100.0,
        "refusal": None,
    }


def test_the_call_takes_the_review_s_value_and_levels(
    rows: _Rows,
) -> None:
    call = report_call(rows.valued, rows.review, rows.secondary)
    assert (call["value"], call["basis"], call["note"]) == (80.0, "reviewed", None)
    assert call["levels"] == _levels(80.0)
    assert call["mechanicalValue"] == 100.0
    assert (call["priceToValue"], call["designation"]) == _word(80.0, 150.0)


def test_the_word_is_worked_out_at_the_report_s_price(
    rows: _Rows,
) -> None:
    """The word stored with a review is of the price it was valued at; the call's is the report's
    value against the price of the report's snapshot."""
    stored = replace(rows.review, price_to_value=0.5, designation="well-below")
    call = report_call(rows.valued, stored, None)
    expected = _word(80.0, 150.0)
    assert (call["priceToValue"], call["designation"]) == expected
    assert expected[1] != "well-below"


def test_a_review_with_no_value_falls_to_the_secondary_valuation(
    rows: _Rows,
) -> None:
    refused = _no_value(rows.review, REFUSED_REVIEW)
    call = report_call(rows.refused, refused, rows.secondary)
    assert (call["value"], call["basis"], call["note"]) == (
        12.0,
        "reviewed",
        "secondary valuation",
    )
    assert call["levels"] == _levels(12.0)
    assert (call["mechanicalValue"], call["refusal"]) == (None, None)
    assert (call["priceToValue"], call["designation"]) == _word(12.0, 150.0)


def test_a_refused_snapshot_its_review_values(
    rows: _Rows,
) -> None:
    buy, low, high, trim = _band(5.0)
    review = replace(
        rows.review, value=5.0, buy_level=buy, fair_low=low, fair_high=high, trim_level=trim
    )
    call = report_call(rows.refused, review, None)
    assert (call["value"], call["basis"], call["note"]) == (5.0, "reviewed", None)
    assert call["levels"] == _levels(5.0)
    assert (call["mechanicalValue"], call["refusal"]) == (None, None)


def test_no_value_at_all_gives_the_refusal(
    rows: _Rows,
) -> None:
    """The refusal is the review's where the report rests on one, else the snapshot's."""
    bare = report_call(rows.refused, None, None)
    reviewed = report_call(rows.refused, _no_value(rows.review, REFUSED_REVIEW), None)
    for call in (bare, reviewed):
        assert (call["value"], call["basis"], call["note"]) == (None, None, None)
        assert (call["levels"], call["priceToValue"], call["designation"]) == (None, None, None)
        assert (call["mechanicalValue"], call["price"]) == (None, 150.0)
    assert (bare["refusal"], reviewed["refusal"]) == (rows.refused.refusal, REFUSED_REVIEW)


def test_a_secondary_of_zero_does_not_count(
    rows: _Rows,
) -> None:
    nothing = replace(
        rows.secondary,
        value_per_share=0.0,
        buy_level=None,
        fair_low=None,
        fair_high=None,
        trim_level=None,
    )
    call = report_call(rows.refused, None, nothing)
    assert (call["value"], call["levels"], call["note"]) == (None, None, None)
    assert call["refusal"] == rows.refused.refusal


def test_a_snapshot_with_no_price(rows: _Rows) -> None:
    call = report_call(replace(rows.valued, price=None), None, None)
    assert (call["value"], call["levels"]) == (100.0, _levels(100.0))
    assert (call["price"], call["priceToValue"], call["designation"]) == (None, None, None)


# ------------------------------------------------------------------ the records of the report


def _report(report_id: int, *parts: Any) -> ReportRow:
    """Report ``report_id`` of AAPL, its Summary plain words and its Risks and kill criteria
    ``parts``."""
    return ReportRow(
        id=report_id,
        symbol="AAPL",
        revision=1,
        mode="full report",
        stance="hold",
        sections=(
            {"heading": "Summary", "parts": ["Plain words, kill:1 in them."]},
            {"heading": "Risks and kill criteria", "parts": list(parts)},
        ),
        reuses_full_report_of=None,
        snapshot_id=1,
        review_id=None,
        secondary_id=None,
        work_item_id=None,
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        created_at=NOW,
    )


def _criterion(criterion_id: int, report_id: int | None) -> KillCriterionRow:
    return KillCriterionRow(
        id=criterion_id,
        symbol="AAPL",
        text=f"criterion {criterion_id}",
        state="open",
        report_id=report_id,
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        at=NOW,
        state_reason=None,
        state_at=None,
    )


def _news(item_id: int, report_id: int | None, criterion_id: int | None = None) -> NewsItemRow:
    return NewsItemRow(
        id=item_id,
        symbol="AAPL",
        date=NOW.date(),
        headline=f"item {item_id}",
        source="https://example.com/news",
        text="what happened",
        kill_criterion_id=criterion_id,
        report_id=report_id,
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        at=NOW,
    )


def test_the_report_s_own_criteria_and_those_it_cites() -> None:
    """Report 5 recorded criterion 9 and cites it and criterion 7; criterion 8 is another report's
    and criterion 1 is no report's, cited nowhere: a cite of 12 does not name it, nor do the words
    of a plain part."""
    report = _report(
        5,
        "The thesis ends if growth falls below ",
        {"cite": "5.0%", "ref": "kill:7/threshold"},
        " or ",
        {"cite": "4.0%", "ref": "kill:9"},
        ", or below ",
        {"cite": "3.0%", "ref": "kill:12"},
        ".",
    )
    criteria = [_criterion(9, 5), _criterion(8, 4), _criterion(7, None), _criterion(1, None)]
    found, _ = of_report(report, criteria, [])
    assert [c.id for c in found] == [9, 7]


def test_the_news_items_of_the_report_s_id_alone() -> None:
    """The items report 5 recorded, in the store's order: not another report's, nor an item of no
    report that touches a criterion the report cites."""
    report = _report(5, {"cite": "5.0%", "ref": "kill:7"})
    news = [_news(6, 5), _news(5, None, 7), _news(4, 3), _news(3, 5)]
    _, found = of_report(report, [_criterion(7, None)], news)
    assert [n.id for n in found] == [6, 3]


# ------------------------------------------------------------------ the read


def _page(client: TestClient, symbol: str = "AAPL", report: int | None = None) -> dict[str, Any]:
    params = {} if report is None else {"report": report}
    r = client.get(f"/api/companies/{symbol}/page/research", params=params)
    assert r.status_code == 200, r.text
    found: dict[str, Any] = r.json()
    return found


def _quote(db_path: Path, symbol: str) -> list[dict[str, Any]]:
    """A quote of ``symbol`` stored with its observations as the fetch stores one; its payload."""
    payload = [QUOTE[0] | {"symbol": symbol}]
    with closing(connect(db_path)) as conn:
        params = {"symbol": symbol}
        found = record_response(
            conn, "fmp", "quote", params, symbol, 200, json.dumps(payload), None, NOW
        )
        insert_observations(conn, quote_observations(payload, symbol, found, NOW, NOW))
    return payload


def _aal_review(db_path: Path, policy: Policy, results: dict[str, ValuationResult]) -> int:
    """An applied margin.target override of AAL at 20%, whose route refused for its target margin,
    and the review it produced on AAL's snapshot, which values it; the review's id."""
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, "AAL")
        assert snapshot is not None
        override_id = insert_override(
            conn,
            "AAL",
            "margin.target",
            None,
            0.2,
            "ratio",
            "the peers by hand",
            [{"kind": "filing", "ref": "10-K 2025", "note": ""}],
            "lasting",
            None,
            None,
            snapshot.id,
            writer,
            NOW,
            "applied",
            "",
        )
        target = Override(override_id, "margin.target", 0.2, "agent", writer.actor, NOW, "")
        inputs = replace(young_growth_inputs(), symbol="AAL", peers=())
        review = review_company(inputs, universe_deciles(), policy, TODAY, [target], results["AAL"])
        assert review.result.value is not None
        return insert_review(conn, review, "AAL", snapshot.id, None, clock=lambda: NOW)


@pytest.mark.usefixtures("verdicts")  # a report needs it on its snapshot
def test_the_latest_report_and_a_named_revision(client: TestClient) -> None:
    sid = snapshot_id(client)
    older = published(client, body(sid))
    newer = published(client, body(sid, stance="trim"))
    latest = _page(client)
    assert (latest["symbol"], latest["dataDate"], latest["report"]["id"]) == (
        "AAPL",
        None,
        newer["id"],
    )
    assert _page(client, "aapl", older["id"])["report"]["id"] == older["id"]
    assert [r["id"] for r in latest["reports"]] == [newer["id"], older["id"]]
    assert all("sections" not in r for r in latest["reports"])
    assert latest["reports"] == client.get("/api/companies/AAPL/reports").json()["reports"]


@pytest.mark.usefixtures("verdicts")  # a report needs it on its snapshot
def test_the_report_is_the_report_read_s_answer(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """The report whole as its own read answers it, the call worked out from its snapshot, and
    the kill criteria and news items it recorded, each as the research read serves it; a
    criterion recorded on its own is not the report's."""
    sid = snapshot_id(client)
    news = {
        "date": "2026-10-28",
        "headline": "Guidance raised",
        "source": "https://example.com/news",
        "text": "The company raised its guidance.",
    }
    criterion = {"text": "revenue falls two quarters running"}
    report = published(client, body(sid, killCriteria=[criterion], newsItems=[news]))
    r = client.post("/api/companies/AAPL/kill-criteria", json={"text": "apart"}, headers=AGENT)
    assert r.status_code == 201, r.text
    answer = _page(client)
    assert answer["report"] == client.get(f"/api/reports/{report['id']}").json()
    with closing(connect(db_path)) as conn:
        snapshot = snapshot_row(conn, sid)
    assert snapshot is not None and snapshot.value is not None
    assert answer["call"] == report_call(snapshot, None, None)
    assert (answer["call"]["value"], answer["call"]["basis"]) == (snapshot.value, "mechanical")
    research = client.get("/api/companies/AAPL/research").json()
    own = [k for k in research["killCriteria"] if k["reportId"] == report["id"]]
    assert [k["text"] for k in own] == [criterion["text"]]
    assert answer["ofReport"] == {"killCriteria": own, "newsItems": research["newsItems"]}


@pytest.mark.usefixtures("verdicts")  # a report needs it on its snapshot
def test_the_call_is_of_the_records_the_report_rests_on(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """AAL's first report rests on its secondary valuation, the fallback of its refused snapshot;
    a review then values AAL and the second rests on it. Each revision's call is of its own
    records, whatever the company's today."""
    sid = snapshot_id(client, "AAL")
    refused = body(sid, sections=PLAIN, judgments=REFUSED_JUDGMENTS)
    first = published(client, refused, "AAL")
    review_id = _aal_review(db_path, policy, results)
    second = published(client, refused, "AAL")
    assert (first["secondaryId"], first["reviewId"]) == (secondaries["AAL"], None)
    assert (second["secondaryId"], second["reviewId"]) == (None, review_id)
    with closing(connect(db_path)) as conn:
        snapshot = snapshot_row(conn, sid)
        secondary = secondary_row(conn, secondaries["AAL"])
        review = review_row(conn, review_id)
    assert snapshot is not None and secondary is not None and review is not None
    fallback = _page(client, "AAL", first["id"])["call"]
    assert fallback == report_call(snapshot, None, secondary)
    assert (fallback["value"], fallback["note"]) == (
        secondary.value_per_share,
        "secondary valuation",
    )
    reviewed = _page(client, "AAL")["call"]
    assert reviewed == report_call(snapshot, review, None)
    assert (reviewed["value"], reviewed["basis"]) == (review.value, "reviewed")


@pytest.mark.usefixtures("verdicts")  # a report needs it on its snapshot
def test_another_company_s_report_and_none(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    inputs = replace(mature_growth_inputs(), symbol="MSFT")
    with closing(connect(db_path)) as conn:
        refresh = latest_refresh(conn)
        assert refresh is not None
        result = value_company(inputs, universe_deciles(), policy, TODAY)
        sid = insert_snapshot(conn, result, refresh.id, clock=lambda: NOW)
    record_verdict(db_path, "MSFT", sid)
    report = published(client, body(sid, sections=PLAIN), "MSFT")
    r = client.get("/api/companies/AAPL/page/research", params={"report": report["id"]})
    detail = f"report {report['id']} is MSFT's, not AAPL's"
    assert (r.status_code, r.json()) == (404, {"detail": detail})
    r = client.get("/api/companies/AAPL/page/research", params={"report": 999})
    assert (r.status_code, r.json()) == (404, {"detail": "no report 999"})


def test_a_company_with_no_report(client: TestClient) -> None:
    answer = _page(client, "HGCO")
    assert (answer["report"], answer["call"], answer["ofReport"], answer["reports"]) == (
        None,
        None,
        None,
        [],
    )
    assert list(answer["records"]) == [
        *RESEARCH,
        "reviews",
        "secondaryValuations",
        "ledgerCount",
    ]
    assert answer["records"] == {key: [] for key in answer["records"]} | {"ledgerCount": 0}


def test_a_company_with_no_snapshot(client: TestClient) -> None:
    r = client.get("/api/companies/ZZZZ/page/research")
    assert (r.status_code, r.json()) == (404, {"detail": "no page data for ZZZZ"})
    assert client.get("/api/companies/a$b/page/research").status_code == 400


def test_the_read_carries_the_head_s_quote(client: TestClient, db_path: Path) -> None:
    payload = _quote(db_path, "AAPL")
    assert _page(client)["quote"] == head_quote(payload[0])
    assert _page(client, "HGCO")["quote"] == head_quote(None)


def test_the_records_carry_the_reviews_the_secondary_valuations_and_the_ledger_s_count(
    client: TestClient,
    db_path: Path,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """The research read's lists as it answers them, the company's reviews as their own read
    serves them but for each bridge line, which carries its label, unit, reason and writer as the
    company detail's does (a review here has no line), its secondary valuations as their read
    serves them, and the count of every ledger row of the company, where the ledger's list is cut
    at the newest twenty."""
    sid = snapshot_id(client)
    mechanical = results["AAPL"]
    with closing(connect(db_path)) as conn:
        insert_review(
            conn, Review(mechanical, mechanical.value, (), ()), "AAPL", sid, None, clock=lambda: NOW
        )
    for n in range(25):
        r = client.post("/api/companies/AAPL/notes", json={"text": f"note {n}"}, headers=HEADER)
        assert r.status_code == 201, r.text
    records = _page(client)["records"]
    base = "/api/companies/AAPL"
    assert {key: records[key] for key in RESEARCH} == client.get(f"{base}/research").json()
    assert records["reviews"] == client.get(f"{base}/reviews").json()["reviews"]
    secondary = client.get(f"{base}/secondary").json()["secondaryValuations"]
    assert records["secondaryValuations"] == secondary
    assert (len(records["reviews"]), [s["id"] for s in secondary]) == (1, [secondaries["AAPL"]])
    assert (records["ledgerCount"], len(records["ledger"])) == (25, 20)


def test_a_review_s_bridge_lines_carry_their_label_and_unit(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Each bridge line of a review in ``records`` carries its input's label in a reader's words,
    its unit in the review's reporting currency and its override's reason and writer, as the
    company detail's lines do (``research_api.bridge_lines``), so the Records view draws the
    review's bridge without working them out; the reviews read keeps its stored lines."""
    _aal_review(db_path, policy, results)
    [review] = _page(client, "AAL")["records"]["reviews"]
    [served] = client.get("/api/companies/AAL/reviews").json()["reviews"]
    [stored] = served["bridge"]
    assert set(stored) == {"tag", "overrideId", "old", "new", "delta", "refusal"}
    detail = client.get("/api/companies/AAL").json()["review"]
    assert review == served | {"bridge": detail["bridge"]}
    [line] = review["bridge"]
    assert line == stored | {
        "label": "target margin",
        "unit": "ratio",
        "reason": "the peers by hand",
        "principal": "agent",
        "actor": "claude-opus-5-5",
    }


@pytest.mark.usefixtures("verdicts")  # a report needs it on its snapshot
def test_the_read_calls_no_vendor(
    tmp_path: Path, db_path: Path, policy: Policy, vendor: Vendor, passthrough: Passthrough
) -> None:
    """An app with a pass-through whose every call fails: the read answers from the store, the
    report's references among it, and the vendor is never asked."""
    vendor.answer = lambda request: httpx.Response(500)
    with passthrough_client(tmp_path, db_path, policy, passthrough) as client:
        report = published(client, body(snapshot_id(client)))
        answer = _page(client)
    assert answer["report"]["id"] == report["id"] and answer["report"]["references"]
    assert vendor.paths == []
