"""The company page's two reads (the company page's design, 7.4, 10.3, 10.4 and 10.5) and the two
fields the company's detail gains (7.2 and 11.1), on the database of ``conftest.py``: AAPL valued
on the Mature Growth route, AAL refused for its target margin, HGCO valued on the revenue growth
route.

The page's company is ``page_payloads``' LFOX, which has no snapshot unless a test values one. Its
FMP answers are stored as the refresh stores them: each under the fetch's params, a quote with its
observations. The expected figures are the readers' (``vendors.page_fmp``) on the same payloads,
whose own tests read each field: these tests check what each read hands each reader."""

import json
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient
from refresh.vendor_double import FMP_KEY, Router
from support import page_payloads as pages
from support.engine_companies import (
    fx_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.payloads import store_payloads
from support.vendor import Vendor, passthrough_client
from support.web import HEADER, NOW, TODAY

from fairband.engine.overrides import Override
from fairband.engine.review import review_company
from fairband.engine.route import value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.refresh.fetch import EARNINGS_ROWS, PAGE_ENDPOINTS, fetch_company, page_params
from fairband.refresh.passthrough import Passthrough
from fairband.store.db import connect
from fairband.store.ledger import Writer
from fairband.store.observations import insert_observations
from fairband.store.overrides import insert_override
from fairband.store.reviews import insert_review
from fairband.store.settings import write_settings
from fairband.store.snapshots import insert_snapshot, latest_snapshot
from fairband.store.vendor import record_response
from fairband.vendors import fmp as fmp_api
from fairband.vendors import page_fmp
from fairband.vendors.fmp import ANNUAL_ESTIMATE_LIMIT, Fmp
from fairband.vendors.http import VendorHttp
from fairband.vendors.normalize_fmp import quote_observations

SYMBOL = pages.SYMBOL
AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)  # 90 minutes before the clock's NOW
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
OVERVIEW = f"/api/companies/{SYMBOL}/page/overview"
ESTIMATES = f"/api/companies/{SYMBOL}/page/estimates"
# Every answer the two reads draw, but the quote, which a test stores with its observations.
ANSWERS: dict[str, Any] = {
    "profile": pages.PROFILE,
    "price-history": pages.HISTORY,
    "earnings": pages.EARNINGS,
    "estimates-annual": pages.ESTIMATES,
    "ratios-ttm": pages.RATIOS,
    "key-metrics-ttm": pages.KEY_METRICS,
    "financial-growth": pages.GROWTH,
    "financial-scores": pages.SCORES,
    "price-change": pages.PRICE_CHANGE,
    "price-target": pages.TARGET,
    "grades": pages.GRADES,
    "dividends": pages.DIVIDENDS,
    "shares-float": pages.FLOAT,
    "news": pages.NEWS,
}
# LFOX's fiscal years on file, so the consensus starts after fiscal 2025.
INCOME = [
    {"symbol": SYMBOL, "date": f"{year}-12-31", "fiscalYear": str(year), "period": "FY"}
    | {"reportedCurrency": "SEK", "revenue": revenue}
    for year, revenue in ((2025, 3.27e12), (2024, 2.44e12))
]


def _params(endpoint: str, symbol: str) -> dict[str, str]:
    """The params the fetch stores ``endpoint``'s answer under (``fetch._calls``)."""
    if endpoint in PAGE_ENDPOINTS:
        return page_params(endpoint, symbol)
    extra = {
        "profile": {},
        "price-history": {},
        "earnings": {"limit": str(EARNINGS_ROWS)},
        "estimates-annual": {"period": "annual", "limit": str(ANNUAL_ESTIMATE_LIMIT)},
    }[endpoint]
    return {"symbol": symbol, **extra}


def _store(
    db_path: Path,
    endpoint: str,
    payload: Any,
    at: datetime,
    symbol: str = SYMBOL,
    *,
    status: int = 200,
    error: str | None = None,
) -> None:
    """``payload`` stored as the fetch stores ``symbol``'s answer to ``endpoint``, observed
    ``at``."""
    with closing(connect(db_path)) as conn:
        params = _params(endpoint, symbol)
        text = None if payload is None else json.dumps(payload)
        record_response(conn, "fmp", endpoint, params, symbol, status, text, error, at)


def _quote(db_path: Path, payload: Any, at: datetime, symbols: Sequence[str]) -> None:
    """A quote of ``symbols`` stored with each one's observations: one symbol's as the fetch
    stores it, several as a price refresh stores a batch, under no symbol."""
    if len(symbols) == 1:
        endpoint, params, symbol = "quote", {"symbol": symbols[0]}, symbols[0]
    else:
        endpoint, params, symbol = "batch-quote", {"symbols": ",".join(symbols)}, None
    with closing(connect(db_path)) as conn:
        found = record_response(
            conn, "fmp", endpoint, params, symbol, 200, json.dumps(payload), None, at
        )
        rows = [row for s in symbols for row in quote_observations(payload, s, found, at, at)]
        insert_observations(conn, rows)


def _store_all(db_path: Path, policy: Policy) -> None:
    """Every answer of LFOX at ``AT``, its quote, its two fiscal years, and a snapshot in SEK, its
    reporting currency (FXCO's result, spec 2026-11-10 11.2)."""
    for endpoint, payload in ANSWERS.items():
        _store(db_path, endpoint, payload, AT)
    _quote(db_path, pages.QUOTE, AT, [SYMBOL])
    in_sek = value_company(replace(fx_inputs(), symbol=SYMBOL), universe_deciles(), policy, TODAY)
    with closing(connect(db_path)) as conn:
        store_payloads(conn, SYMBOL, {"income-annual": INCOME}, AT)
        insert_snapshot(conn, in_sek, 1)


def _get(client: TestClient, path: str) -> Any:
    r = client.get(path)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_overview_whole(client: TestClient, db_path: Path, policy: Policy) -> None:
    _store_all(db_path, policy)
    today = NOW.date()
    quote = pages.QUOTE[0]
    answers = {endpoint: ANSWERS[endpoint] for endpoint in PAGE_ENDPOINTS}
    body = _get(client, OVERVIEW)
    assert body == {
        "symbol": SYMBOL,
        "dataDate": "2026-11-01",
        "quote": page_fmp.head_quote(quote),
        "company": page_fmp.company(pages.PROFILE),
        "statistics": page_fmp.statistics(answers, pages.PROFILE, quote, "SEK", today),
        "trading": page_fmp.trading(quote, pages.PROFILE, "2027-01-14"),
        "priceChange": page_fmp.price_change(pages.PRICE_CHANGE),
        "prices": page_fmp.prices(pages.HISTORY, quote),
        "news": {
            "stories": page_fmp.stories(pages.NEWS),
            "observedAt": AT.isoformat(),
            "stale": False,
            "limit": 60,
        },
    }
    # The design's 14.2: the enterprise value in the reporting currency, the market cap in US
    # dollars; the next earnings date the earlier of two future rows, past one without an actual.
    size = body["statistics"]["size"]
    assert size["enterpriseValue"] == {"value": 12480000000000, "currency": "SEK"}
    assert size["marketCap"] == {"value": 412600000000, "currency": "USD"}
    assert body["trading"]["nextEarnings"] == "2027-01-14"
    # The head's figures, which both reads carry (the design's 7.2).
    assert body["quote"] == {
        "price": 182.4,
        "change": 2.15,
        "changePercent": 1.1928,
        "day": "2026-11-16",
    }
    # The quote's day (16 Nov) is later than the history's newest (13 Nov): it closes the prices.
    assert body["prices"][-2:] == [
        ["2026-11-13", 180.25, 7650200],
        ["2026-11-16", 182.4, 8123400],
    ]


def test_the_estimates_whole(client: TestClient, db_path: Path, policy: Policy) -> None:
    _store_all(db_path, policy)
    body = _get(client, ESTIMATES)
    assert body == {
        "symbol": SYMBOL,
        "dataDate": "2026-11-01",
        "quote": _get(client, OVERVIEW)["quote"],
        "earnings": page_fmp.earnings(pages.EARNINGS, NOW.date()),
        "consensus": page_fmp.consensus(pages.ESTIMATES, date(2025, 12, 31), "SEK"),
        "target": page_fmp.target(pages.TARGET),
        "ratings": page_fmp.ratings(pages.GRADES),
    }
    # The consensus starts after the newest fiscal year on file, in the reporting currency.
    assert [row["fiscalYear"] for row in body["consensus"]] == [2026, 2027, 2028, 2029]
    assert body["consensus"][0]["eps"] == {"value": 61.2, "currency": "SEK"}
    assert body["target"]["consensus"] == {"value": 205.6, "currency": "USD"}
    assert body["quote"]["price"] == 182.4


def test_an_estimate_dated_within_the_drift_of_the_newest_year_is_that_year(
    client: TestClient, db_path: Path
) -> None:
    """A 52/53-week fiscal year ends up to six days either side of its month and day: FMP may date
    the reported year's estimate a few days after the statement's period end. That row is the
    reported year, not a consensus year; the next year's, a year later, is."""
    _store(db_path, "profile", pages.PROFILE, AT)
    income = [
        {"symbol": SYMBOL, "date": day, "fiscalYear": year, "period": "FY", "revenue": 3.0e12}
        for day, year in (("2025-12-27", "2025"), ("2024-12-28", "2024"))
    ]
    reported, upcoming = (
        pages.ESTIMATES[-1] | {"date": "2025-12-31"},
        pages.ESTIMATES[-2] | {"date": "2026-12-31"},
    )
    _store(db_path, "estimates-annual", [upcoming, reported], AT)
    with closing(connect(db_path)) as conn:
        store_payloads(conn, SYMBOL, {"income-annual": income}, AT)
    consensus = _get(client, ESTIMATES)["consensus"]
    assert consensus == page_fmp.consensus([upcoming], None, "USD")
    assert [row["fiscalYear"] for row in consensus] == [2026]


def test_a_company_with_a_profile_and_nothing_else(client: TestClient, db_path: Path) -> None:
    """Review Focus 2: a company fetched before the page's calls, or whose ten calls all failed,
    opens with every figure ``None``, no price and no story."""
    _store(db_path, "profile", pages.PROFILE, AT)
    overview = _get(client, OVERVIEW)
    assert overview["dataDate"] == "2026-11-01"
    assert overview["company"] == page_fmp.company(pages.PROFILE)
    assert overview["statistics"] == page_fmp.statistics({}, pages.PROFILE, None, "USD", NOW.date())
    assert overview["statistics"]["size"]["marketCap"] is None
    assert overview["trading"] == page_fmp.trading(None, pages.PROFILE, None)
    assert overview["trading"]["open"] is None
    no_quote = {"price": None, "change": None, "changePercent": None, "day": None}
    assert overview["quote"] == no_quote
    assert set(overview["priceChange"].values()) == {None}
    assert overview["prices"] == []
    assert overview["news"] == {"stories": [], "observedAt": None, "stale": True, "limit": 60}
    estimates = _get(client, ESTIMATES)
    assert estimates == {
        "symbol": SYMBOL,
        "dataDate": None,  # the estimates tab draws no profile
        "quote": no_quote,
        "earnings": {"next": None, "rows": []},
        "consensus": [],
        "target": {"consensus": None, "median": None, "low": None, "high": None},
        "ratings": page_fmp.ratings(None),
    }
    assert set(estimates["ratings"].values()) == {None}


def test_a_bad_symbol_is_a_400_and_no_profile_a_404(client: TestClient) -> None:
    for tab in ("overview", "estimates"):
        r = client.get(f"/api/companies/a b/page/{tab}")
        assert (r.status_code, r.json()) == (400, {"detail": "'a b' is not a symbol"})
        # AAPL has a snapshot and no stored profile: the page reads need the profile alone
        r = client.get(f"/api/companies/aapl/page/{tab}")
        assert (r.status_code, r.json()) == (404, {"detail": "no page data for AAPL"})
        r = client.get(f"/api/companies/ZZZZ/page/{tab}")
        assert (r.status_code, r.json()) == (404, {"detail": "no page data for ZZZZ"})


def test_the_data_date_is_the_oldest_answer_s_day(client: TestClient, db_path: Path) -> None:
    """The oldest day among the answers the tab draws, the news left out (the design's 7.4): the
    overview draws no price target and no grades, and the estimates no profile; both draw the
    quote, the head's."""

    def on(day: int) -> datetime:
        return datetime(2026, 10, day, 12, 0, tzinfo=UTC)

    for endpoint, day in (
        ("profile", 31),
        ("price-history", 30),
        ("earnings", 29),
        ("ratios-ttm", 28),
        ("estimates-annual", 30),
        ("price-target", 25),
        ("news", 20),
    ):
        _store(db_path, endpoint, ANSWERS[endpoint], on(day))
    _quote(db_path, pages.QUOTE, on(31), [SYMBOL])
    assert _get(client, OVERVIEW)["dataDate"] == "2026-10-28"
    assert _get(client, ESTIMATES)["dataDate"] == "2026-10-25"
    _store(db_path, "dividends", pages.DIVIDENDS, on(27))  # a drawn answer, older again
    _store(db_path, "grades", pages.GRADES, on(24))
    assert _get(client, OVERVIEW)["dataDate"] == "2026-10-27"
    assert _get(client, ESTIMATES)["dataDate"] == "2026-10-24"
    # The quote read is the one the newest observation cites, the last stored, whatever its day.
    _quote(db_path, pages.QUOTE, on(26), [SYMBOL])
    assert _get(client, OVERVIEW)["dataDate"] == "2026-10-26"
    assert _get(client, ESTIMATES)["dataDate"] == "2026-10-24"
    _quote(db_path, pages.QUOTE, on(22), [SYMBOL])
    assert _get(client, OVERVIEW)["dataDate"] == "2026-10-22"
    assert _get(client, ESTIMATES)["dataDate"] == "2026-10-22"


def test_the_news_is_stale_on_the_far_side_of_the_window(
    client_with_clock: Callable[[datetime], TestClient], db_path: Path, policy: Policy
) -> None:
    """Stale when observed at or before the clock less the effective policy's reuse window."""
    _store(db_path, "profile", pages.PROFILE, AT)
    _store(db_path, "news", pages.NEWS, AT)
    window = timedelta(hours=policy.refresh.reuse_hours)

    def news(now: datetime) -> Mapping[str, Any]:
        found: Mapping[str, Any] = _get(client_with_clock(now), OVERVIEW)["news"]
        assert (found["observedAt"], found["stories"]) == (
            AT.isoformat(),
            page_fmp.stories(pages.NEWS),
        )
        return found

    assert news(AT + window - timedelta(seconds=1))["stale"] is False
    assert news(AT + window)["stale"] is True
    with closing(connect(db_path)) as conn:
        write_settings(conn, {"refresh.reuse_hours": 1}, None, NOW, policy)
    assert news(AT + timedelta(minutes=59))["stale"] is False
    assert news(AT + timedelta(hours=1))["stale"] is True


def test_the_newest_answer_wins_and_an_errored_one_is_passed_over(
    client: TestClient, db_path: Path
) -> None:
    _store(db_path, "profile", pages.PROFILE, AT)
    older = [pages.RATIOS[0] | {"grossProfitMarginTTM": 0.5}]
    newer = [pages.RATIOS[0] | {"grossProfitMarginTTM": 0.6}]
    _store(db_path, "ratios-ttm", older, datetime(2026, 10, 29, tzinfo=UTC))
    _store(db_path, "ratios-ttm", newer, datetime(2026, 10, 30, tzinfo=UTC))
    error = {"Error Message": "Limit Reach"}
    _store(db_path, "ratios-ttm", error, AT, error="unusable payload: {...}")
    _store(db_path, "ratios-ttm", None, AT, status=500, error="HTTP 500")
    body = _get(client, OVERVIEW)
    assert body["statistics"]["margins"]["gross"] == 0.6
    assert body["dataDate"] == "2026-10-30"


def test_the_quote_row_comes_through_the_observation(client: TestClient, db_path: Path) -> None:
    """The design's 10.4: the row of the response the newest ``quote`` observation cites, a
    single quote's, then a price refresh's batch, stored under no symbol. ``BRK.B``'s row is
    ``BRK-B`` in FMP's form, read by a path in either case."""
    _store(db_path, "profile", pages.PROFILE, AT)
    _store(db_path, "price-history", pages.HISTORY, AT)
    _quote(db_path, pages.QUOTE, AT, [SYMBOL])
    head = _get(client, OVERVIEW)["quote"]
    assert (head["price"], head["change"], head["day"]) == (182.4, 2.15, "2026-11-16")
    # A later batch, its row on the history's newest day: no day is added to the prices.
    on_the_13th = 1794600000  # 13 Nov 2026, 20:00 UTC
    row = pages.QUOTE[0] | {"price": 185.0, "change": 4.75, "timestamp": on_the_13th}
    batch = [pages.BATCH_QUOTE[0], row]
    later = AT + timedelta(minutes=30)
    _quote(db_path, batch, later, ["BRK.B", SYMBOL])
    body = _get(client, OVERVIEW)
    assert body["quote"] == page_fmp.head_quote(row)
    assert (body["quote"]["price"], body["quote"]["day"]) == (185.0, "2026-11-13")
    assert body["trading"] == page_fmp.trading(row, pages.PROFILE, None)
    assert body["prices"] == page_fmp.prices(pages.HISTORY, row)
    assert body["prices"][-1] == ["2026-11-13", 180.25, 7650200]
    assert body["statistics"]["size"]["marketCap"] == {"value": 412600000000, "currency": "USD"}
    # The estimates read carries the same row's head figures, and the date of its response.
    estimates = _get(client, ESTIMATES)
    assert (estimates["quote"], estimates["dataDate"]) == (body["quote"], "2026-11-01")
    _store(db_path, "profile", pages.PROFILE, AT, symbol="BRK.B")
    brk = _get(client, "/api/companies/brk.b/page/overview")
    assert (brk["symbol"], brk["quote"]["price"]) == ("BRK.B", 512.3)
    assert _get(client, "/api/companies/brk.b/page/estimates")["quote"] == brk["quote"]


def test_the_reads_call_no_vendor(
    tmp_path: Path, db_path: Path, policy: Policy, vendor: Vendor, passthrough: Passthrough
) -> None:
    """An app with a pass-through whose every call fails: both reads answer from the store, the
    stale news among them, and the vendor is never asked."""
    vendor.answer = lambda request: httpx.Response(500)
    _store(db_path, "profile", pages.PROFILE, AT)
    _store(db_path, "news", pages.NEWS, AT - timedelta(days=3))
    with passthrough_client(tmp_path, db_path, policy, passthrough) as client:
        news = _get(client, OVERVIEW)["news"]
        _get(client, ESTIMATES)
    assert (news["stale"], len(news["stories"])) == (True, 3)
    assert vendor.paths == []


def test_the_reads_find_what_the_fetch_stores(
    db_path: Path, client: TestClient, policy: Policy
) -> None:
    """The refresh's fetch of ACME over the fixtures, then both reads: each answer they draw is
    found under the params the fetch stored it with, so a figure of each is there."""
    router = Router()
    with (
        VendorHttp(
            fmp_api.BASE_URL,
            [FMP_KEY],
            policy.refresh,
            transport=router.transport,
            sleep=lambda _: None,
            clock=lambda: NOW,
        ) as http,
        closing(connect(db_path)) as conn,
    ):
        outcome = fetch_company(conn, Fmp(http, FMP_KEY), None, "ACME", policy, NOW, [FMP_KEY])
    assert outcome.failed == ("summary", "keyratios")  # no GuruFocus client
    overview = _get(client, "/api/companies/ACME/page/overview")
    estimates = _get(client, "/api/companies/ACME/page/estimates")
    statistics = overview["statistics"]
    one_of_each = {
        "profile": overview["company"]["sector"],
        "quote": overview["quote"]["price"],
        "price-history": overview["prices"][0],
        "earnings": overview["trading"]["nextEarnings"],
        "ratios-ttm": statistics["margins"]["gross"],
        "key-metrics-ttm": statistics["returns"]["roe"],
        "financial-growth": statistics["growth"]["revenue"],
        "financial-scores": statistics["health"]["altmanZ"],
        "price-change": overview["priceChange"]["d1"],
        "dividends": statistics["dividends"]["frequency"],
        "shares-float": statistics["size"]["freeFloat"],
        "news": overview["news"]["observedAt"],
        "estimates-annual": estimates["consensus"][0],
        "price-target": estimates["target"]["consensus"],
        "grades": estimates["ratings"]["consensus"],
    }
    assert {name for name, figure in one_of_each.items() if figure is None} == set()
    assert (overview["dataDate"], estimates["dataDate"]) == ("2026-11-01", "2026-11-01")
    assert estimates["quote"] == overview["quote"]
    assert overview["news"]["stale"] is False


def test_the_detail_carries_the_moat_in_force_and_the_note_count(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """The design's 7.2: the counted review's moat where it has a value, else the snapshot's where
    it has one, else none; and 11.1: the count of the company's notes."""
    aapl = _get(client, "/api/companies/AAPL")
    assert (aapl["moat"], aapl["noteCount"]) == ("Wide", 0)
    # refused for its target margin, AAL keeps a moat class among its intermediates, and no moat
    assert results["AAL"].intermediates["moat"] == "None"
    assert _get(client, "/api/companies/AAL")["moat"] is None
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, "AAPL")
        assert snapshot is not None
        found = insert_override(
            conn,
            "AAPL",
            "moat.class",
            "Wide",
            "Narrow",
            "class",
            "pricing power is fading",
            [{"kind": "filing", "ref": "10-K 2025", "note": None}],
            "lasting",
            None,
            None,
            snapshot.id,
            AGENT,
            NOW,
            "applied",
            "",
        )
        narrow = Override(found, "moat.class", "Narrow", "agent", AGENT.actor, NOW, "fading")
        inputs = replace(mature_growth_inputs(), symbol="AAPL")
        reviewed = review_company(
            inputs, universe_deciles(), policy, TODAY, [narrow], results["AAPL"]
        )
        assert reviewed.result.value is not None
        assert reviewed.result.intermediates["moat"] == "Narrow"
        # a counted review with no value: the snapshot's moat stands
        no_value = replace(reviewed.result, value=None, levels=None, refusal="refused")
        insert_review(
            conn, replace(reviewed, result=no_value), "AAPL", snapshot.id, None, clock=lambda: NOW
        )
        detail = _get(client, "/api/companies/AAPL")
        assert (detail["review"]["refusal"], detail["moat"]) == ("refused", "Wide")
        insert_review(conn, reviewed, "AAPL", snapshot.id, None, clock=lambda: NOW)
    for text in ("margins look peaked", "the services segment carries the company"):
        r = client.post("/api/companies/AAPL/notes", json={"text": text}, headers=HEADER)
        assert r.status_code == 201, r.text
    aapl = _get(client, "/api/companies/AAPL")
    assert aapl["review"]["value"] == reviewed.result.value  # it counts on the latest snapshot
    assert (aapl["moat"], aapl["noteCount"]) == ("Narrow", 2)


def test_a_refused_row_with_a_counted_valued_review_has_the_review_s_moat(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """AAL's snapshot is refused for its target margin and has no moat; an applied margin.target
    override gives a counted review that values it, and the detail's moat is that review's."""
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, "AAL")
        assert snapshot is not None and snapshot.value is None
        found = insert_override(
            conn,
            "AAL",
            "margin.target",
            None,
            0.2,
            "ratio",
            "the peers by hand",
            [{"kind": "filing", "ref": "10-K 2025", "note": None}],
            "lasting",
            None,
            None,
            snapshot.id,
            AGENT,
            NOW,
            "applied",
            "",
        )
        target = Override(found, "margin.target", 0.2, "agent", AGENT.actor, NOW, "peers")
        inputs = replace(young_growth_inputs(), symbol="AAL", peers=())
        reviewed = review_company(
            inputs, universe_deciles(), policy, TODAY, [target], results["AAL"]
        )
        insert_review(conn, reviewed, "AAL", snapshot.id, None, clock=lambda: NOW)
    moat = reviewed.result.intermediates["moat"]
    assert reviewed.result.value is not None and isinstance(moat, str)
    detail = _get(client, "/api/companies/AAL")
    assert detail["review"]["value"] == reviewed.result.value
    assert detail["moat"] == moat
