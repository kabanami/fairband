"""The vendor pass-throughs on the fixture router: each kind's call, stored scrubbed and reused
inside ``reuse_hours`` (at any age for a filing report), the filing kinds' parameters and unusable
payloads, the P/E history's three FMP answers under names of their own, the one limiter the
worker's client and the pass-through's share, and the slots that bound the vendor calls in
flight."""

import json
import re
import threading
import time
from collections.abc import Iterator
from contextlib import closing
from datetime import timedelta
from typing import Any

import httpx
import pytest
from refresh_env import Env
from support.pe_history import report_in
from vendor_double import FIXTURES, FMP_KEY

from fairband.config import Keys
from fairband.refresh import passthrough as passthrough_module
from fairband.refresh.backfill import backfill_statement_facts
from fairband.refresh.clients import build_clients, build_fmp
from fairband.refresh.fetch import fetch_company
from fairband.refresh.passthrough import (
    FILING_KINDS,
    KINDS,
    PASSTHROUGH_SLOTS,
    PASSTHROUGH_WAIT_S,
    PE_CLOSES,
    PE_QUARTERS,
    PE_QUARTERS_LIMIT,
    PE_RATE_YEARS,
    PE_RATES,
    PE_YEARS,
    SERIES_KIND,
    Passthrough,
    PassthroughBusy,
    filing_report_usable,
    series_answers,
)
from fairband.refresh.rates import rates_for
from fairband.reports.multiples import trailing_series, years_before
from fairband.reports.refs import Resolved, resolve
from fairband.store.vendor import (
    latest_response,
    response_payload,
    response_row,
    usable_responses,
)
from fairband.vendors import fmp as fmp_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorError, VendorHttp
from fairband.vendors.limiter import PaceTotals, RateLimiter

Q3 = {"year": "2026", "quarter": "3"}
WINDOW = {"from": "2025-11-11", "to": "2026-11-11"}
REPORT = {"year": "2027", "period": "Q1"}


def _fixture(name: str, vendor: str = "fmp") -> Any:
    return json.loads((FIXTURES / vendor / name).read_text())


def _passthrough(env: Env) -> Passthrough:
    clients = env.clients
    return Passthrough(clients.fmp, env.connect, env.policy, env.clock, clients.secrets)


def _stored(env: Env, response_id: int) -> tuple[str, str | None, dict[str, str], str | None]:
    """The stored row's endpoint, symbol, params and error."""
    with closing(env.connect()) as conn:
        row = response_row(conn, response_id)
    assert row is not None
    return row.endpoint, row.symbol, row.params, row.error


def test_kinds() -> None:
    """Six kinds, all FMP's; the P/E history is no kind of the generic route (spec 2026-11-19
    6.3): its three answers serve the multiples history read alone."""
    assert KINDS == (
        "transcript",
        "news",
        "segments",
        "insider-trades",
        "transcript-dates",
        "dcf",
    )
    assert SERIES_KIND == "pe-history" and SERIES_KIND not in KINDS + FILING_KINDS
    assert (PE_CLOSES, PE_QUARTERS, PE_RATES) == ("pe-closes", "pe-quarters", "pe-rates")
    assert (PE_YEARS, PE_RATE_YEARS, PE_QUARTERS_LIMIT) == (10, 11, 44)


def test_the_pair_s_closes_reach_a_year_behind_the_closes() -> None:
    """The founder's ruling of 2026-11-21: each period's EPS is read at its end's rate, and the
    first day's trailing year reaches a year behind the ten years of closes, so the pair's closes
    are eleven years in their key; the closes stay ten."""
    answers = series_answers("ASML", "EUR")
    assert answers["rates"].params == {"symbol": "USDEUR", "years": "11"}
    assert answers["closes"].params == {"symbol": "ASML", "years": "10"}
    assert "rates" not in series_answers("AAPL", "USD")


def test_the_filing_kinds_are_not_the_generic_route_s() -> None:
    """Spec 2026-11-11, 4: the three kinds sit in a list of their own; ``KINDS`` stays the
    generic route's (``test_kinds``)."""
    assert FILING_KINDS == ("filings", "filing-reports", "filing-report")
    assert not set(FILING_KINDS) & set(KINDS)


def test_the_filing_list_is_one_call_stored_with_its_window(env: Env) -> None:
    """One call for the window, its page of 1,000 rows in the reuse key: the same window is
    reused inside ``reuse_hours``, another window is another call."""
    passthrough = _passthrough(env)
    [(part, first)] = passthrough.fetch("filings", "ACME", WINDOW).items()
    assert part == "filings" and env.router.calls == {"sec-filings": 1}
    assert env.router.requested["sec-filings"] == {
        "symbol": "ACME",
        "from": "2025-11-11",
        "to": "2026-11-11",
        "page": "0",
        "limit": "1000",
    }
    params = {"symbol": "ACME", "from": "2025-11-11", "to": "2026-11-11", "limit": "1000"}
    assert _stored(env, first.row.id) == ("sec-filings", "ACME", params, None)
    assert first.row.provider == "fmp"
    assert first.payload == _fixture("sec-filings-search-symbol.ACME.json")
    again = passthrough.fetch("filings", "ACME", WINDOW)["filings"]
    assert again.reused is True and again.row == first.row
    other = passthrough.fetch("filings", "ACME", {"from": "2026-01-01", "to": "2026-11-11"})
    assert other["filings"].reused is False
    assert _stored(env, other["filings"].row.id)[2] == {**params, "from": "2026-01-01"}
    assert env.router.calls == {"sec-filings": 2}
    env.clock.now += timedelta(hours=env.policy.refresh.reuse_hours)
    assert passthrough.fetch("filings", "ACME", WINDOW)["filings"].reused is False
    assert env.router.calls == {"sec-filings": 3}


def test_the_reports_on_file_are_one_call(env: Env) -> None:
    """FMP's list of the filing reports it holds: one call, stored and reused inside
    ``reuse_hours``, called again after it."""
    passthrough = _passthrough(env)
    [(part, first)] = passthrough.fetch("filing-reports", "ACME", {}).items()
    again = passthrough.fetch("filing-reports", "ACME", {})["filing-reports"]
    assert part == "filing-reports"
    assert env.router.calls == {"filing-report-dates": 1}
    assert env.router.requested["filing-report-dates"] == {"symbol": "ACME"}
    assert (first.reused, again.reused) == (False, True) and first.row == again.row
    assert first.payload == _fixture("financial-reports-dates.ACME.json")
    stored = ("filing-report-dates", "ACME", {"symbol": "ACME"}, None)
    assert _stored(env, first.row.id) == stored
    env.clock.now += timedelta(hours=env.policy.refresh.reuse_hours)
    assert passthrough.fetch("filing-reports", "ACME", {})["filing-reports"].reused is False
    assert env.router.calls == {"filing-report-dates": 2}


def test_a_report_is_reused_whatever_its_age(env: Env) -> None:
    """Spec 2026-11-15 10 (B-167): a filing does not change once filed, and a ``filing:`` ref
    names its copy by the response id, so a usable report is reused at any age, 31 days and 400
    days after it was stored: no vendor call, no second copy."""
    passthrough = _passthrough(env)
    first = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    report = {"symbol": "ACME", "year": "2027", "period": "Q1"}
    assert env.router.requested["filing-report"] == report
    assert _stored(env, first.row.id) == ("filing-report", "ACME", report, None)
    assert first.payload == _fixture("financial-reports-json.ACME.json")
    for days in (31, 400):
        env.clock.now = first.row.observed_at + timedelta(days=days)
        again = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
        assert (again.reused, again.row, again.payload) == (True, first.row, first.payload), days
    assert env.router.calls == {"filing-report": 1}
    with closing(env.connect()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM vendor_responses").fetchone()[0] == 1


def test_a_report_stored_unusable_is_fetched_again_at_any_age(env: Env) -> None:
    """Spec 2026-11-15 10: a copy stored with an error is never reused, 31 days on as at once;
    the usable copy a later ask stores is the one reused after, 400 days on."""
    env.router.bodies["filing-report"] = b'{"Error Message": "No Data for this symbol"}'
    passthrough = _passthrough(env)
    unread = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert unread.row.error is not None and unread.row.error.startswith("unusable payload")
    env.clock.now = unread.row.observed_at + timedelta(days=31)
    again = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert (again.reused, again.row.error) == (False, unread.row.error)
    assert again.row.id > unread.row.id
    del env.router.bodies["filing-report"]  # the fixture's report: usable
    read = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert (read.reused, read.row.error) == (False, None)
    env.clock.now = read.row.observed_at + timedelta(days=400)
    later = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert (later.reused, later.row) == (True, read.row)
    assert env.router.calls == {"filing-report": 3}


@pytest.mark.parametrize(
    ("kind", "params", "endpoint"),
    [("filings", WINDOW, "sec-filings"), ("filing-reports", {}, "filing-report-dates")],
)
def test_the_filing_lists_keep_reuse_hours(
    env: Env, kind: str, params: dict[str, str], endpoint: str
) -> None:
    """Spec 2026-11-15 10: the filing list and the list of reports keep their window: stored 25
    hours before the clock (``reuse_hours`` is 24), each is fetched again."""
    assert env.policy.refresh.reuse_hours == 24
    passthrough = _passthrough(env)
    first = passthrough.fetch(kind, "ACME", params)[kind]
    env.clock.now = first.row.observed_at + timedelta(hours=25)
    again = passthrough.fetch(kind, "ACME", params)[kind]
    assert again.reused is False and again.row.id > first.row.id
    assert env.router.calls == {endpoint: 2}


def test_a_report_fmp_does_not_hold_is_stored_unusable_and_never_reused(env: Env) -> None:
    """FMP answers a period it does not hold with HTTP 200 and ``{"Error Message": ...}``: stored
    with the error ``unusable payload: ...``, answered as fetched, never reused."""
    env.router.bodies["filing-report"] = b'{"Error Message": "No Data for this symbol"}'
    passthrough = _passthrough(env)
    first = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert first.payload == {"Error Message": "No Data for this symbol"}
    assert first.row.error is not None and first.row.error.startswith("unusable payload")
    second = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert second.reused is False and second.row.id > first.row.id
    assert env.router.calls == {"filing-report": 2}


@pytest.mark.parametrize(
    ("payload", "usable"),
    [
        ({"symbol": "ACME", "period": "Q1", "year": "2027", "LEASES": [{"LEASES": ["x"]}]}, True),
        ({"symbol": "ACME", "Error Message": "No Data", "LEASES": []}, False),
        ({"Error Message": "No Data for this symbol"}, False),
        ({"symbol": "ACME", "period": "Q1", "year": "2027"}, False),  # no sheet
        ([], False),
        ("No Data", False),
    ],
)
def test_a_filing_report_is_usable_when_it_holds_a_sheet(payload: Any, usable: bool) -> None:
    assert filing_report_usable(payload) is usable


@pytest.mark.parametrize(
    ("kind", "endpoint", "params", "unread", "error"),
    [
        (
            "filings",
            "sec-filings",
            WINDOW,
            {"Error Message": "Invalid"},
            'unusable payload: {"Error Message": "Invalid"}',
        ),
        ("filing-reports", "filing-report-dates", {}, {}, "unusable payload: {}"),
    ],
)
def test_a_filing_list_that_is_not_a_list_is_stored_unusable(
    env: Env, kind: str, endpoint: str, params: dict[str, str], unread: Any, error: str
) -> None:
    """A filing list or a list of reports that is not a list is stored with its error, answered
    as fetched, and never reused."""
    env.router.bodies[endpoint] = json.dumps(unread).encode()
    passthrough = _passthrough(env)
    first = passthrough.fetch(kind, "ACME", params)[kind]
    assert (first.reused, first.payload, first.row.error) == (False, unread, error)
    assert passthrough.fetch(kind, "ACME", params)[kind].reused is False
    assert env.router.calls == {endpoint: 2}


@pytest.mark.parametrize(
    ("kind", "params", "sentence"),
    [
        ("filing-report", {"year": "2027"}, "a filing report needs year and period"),
        ("filing-report", {"period": "Q1"}, "a filing report needs year and period"),
        ("filing-report", {"year": "2027", "period": "Q5"}, "period is FY or Q1 to Q4"),
        ("filing-report", {"year": "2027", "period": "q1"}, "period is FY or Q1 to Q4"),
        (
            "filing-report",
            {"year": "soon", "period": "Q1"},
            "year must be a whole number, not 'soon'",
        ),
        ("filings", {}, "from and to are ISO dates, from on or before to"),
        ("filings", {"from": "2025-11-11"}, "from and to are ISO dates, from on or before to"),
        ("filings", {"to": "2026-11-11"}, "from and to are ISO dates, from on or before to"),
        (
            "filings",
            {"from": "2026-11-11", "to": "2025-11-11"},
            "from and to are ISO dates, from on or before to",
        ),
        (
            "filings",
            {"from": "yesterday", "to": "2026-11-11"},
            "from and to are ISO dates, from on or before to",
        ),
        (
            "filings",
            {"from": "2025-11-11", "to": "2026-13-01"},
            "from and to are ISO dates, from on or before to",
        ),
    ],
)
def test_a_bad_filing_request_is_a_value_error_before_any_call(
    env: Env, kind: str, params: dict[str, str], sentence: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(sentence)):
        _passthrough(env).fetch(kind, "ACME", params)
    assert not env.router.calls


def test_a_key_inside_a_link_does_not_reach_the_store(env: Env) -> None:
    """Spec 2026-11-11, 10: FMP's list of reports answers links; one that carried the key is
    stored scrubbed, and the answer carries ``<key>`` in its place."""
    body = json.dumps(
        [
            {
                "symbol": "ACME",
                "fiscalYear": 2027,
                "period": "Q1",
                "linkJson": f"https://example.invalid/r?apikey={FMP_KEY}",
            }
        ]
    )
    env.router.bodies["filing-report-dates"] = body.encode()
    fetched = _passthrough(env).fetch("filing-reports", "ACME", {})["filing-reports"]
    with closing(env.connect()) as conn:
        assert FMP_KEY not in (response_payload(conn, fetched.row.id) or "")
    assert FMP_KEY not in json.dumps(fetched.payload)
    assert fetched.payload[0]["linkJson"] == "https://example.invalid/r?apikey=<key>"


def test_a_transcript_is_fetched_stored_and_reused(env: Env) -> None:
    passthrough = _passthrough(env)
    [(part, first)] = passthrough.fetch("transcript", "ACME", Q3).items()
    second = passthrough.fetch("transcript", "ACME", Q3)["transcript"]
    assert part == "transcript"
    assert env.router.calls == {"transcript": 1}
    assert env.router.requested["transcript"] == {"symbol": "ACME", "year": "2026", "quarter": "3"}
    assert (first.reused, second.reused) == (False, True)
    assert first.row == second.row and first.row.observed_at == env.clock()
    assert first.payload == second.payload == _fixture("earning-call-transcript.ACME.json")
    params = {"symbol": "ACME", "year": "2026", "quarter": "3"}
    assert _stored(env, first.row.id) == ("transcript", "ACME", params, None)
    assert first.row.provider == "fmp" and first.row.http_status == 200
    # Another quarter is another call; past the reuse window the same one is called again.
    other = passthrough.fetch("transcript", "ACME", {"year": "2026", "quarter": "2"})
    assert other["transcript"].reused is False
    env.clock.now += timedelta(hours=env.policy.refresh.reuse_hours)
    third = passthrough.fetch("transcript", "ACME", Q3)["transcript"]
    assert third.reused is False and third.row.id > other["transcript"].row.id
    assert env.router.calls == {"transcript": 3}


def test_transcript_dates_is_one_call(env: Env) -> None:
    """The fiscal year, the quarter and the date of every call on file: one FMP call, stored and
    reused inside ``reuse_hours`` like the transcript itself."""
    passthrough = _passthrough(env)
    [(part, first)] = passthrough.fetch("transcript-dates", "ACME", {}).items()
    again = passthrough.fetch("transcript-dates", "ACME", {})["transcript-dates"]
    assert part == "transcript-dates"
    assert env.router.calls == {"transcript-dates": 1}
    assert env.router.requested["transcript-dates"] == {"symbol": "ACME"}
    assert (first.reused, again.reused) == (False, True) and first.row == again.row
    assert first.payload == _fixture("earning-call-transcript-dates.ACME.json")
    assert _stored(env, first.row.id) == ("transcript-dates", "ACME", {"symbol": "ACME"}, None)
    assert first.row.provider == "fmp"
    env.clock.now += timedelta(hours=env.policy.refresh.reuse_hours)
    assert passthrough.fetch("transcript-dates", "ACME", {})["transcript-dates"].reused is False
    assert env.router.calls == {"transcript-dates": 2}


def test_a_list_of_calls_that_is_not_a_list_is_stored_unusable(env: Env) -> None:
    """Spec 2026-11-18 8.1: FMP answers some failures with HTTP 200 and ``{"Error Message":
    ...}``. A list of calls that is not a list is stored with its error, answered as fetched, and
    fetched again by the next request, as the segments' is, so neither the pass-through nor the
    refresh, which stores the list under the same key, reuses it. A list is usable, the empty
    list of a company with no call on file among them, and reused."""
    env.router.bodies["transcript-dates"] = b'{"Error Message": "x"}'
    passthrough = _passthrough(env)
    first = passthrough.fetch("transcript-dates", "ACME", {})["transcript-dates"]
    assert (first.reused, first.payload) == (False, {"Error Message": "x"})
    assert first.row.error == 'unusable payload: {"Error Message": "x"}'
    assert passthrough.fetch("transcript-dates", "ACME", {})["transcript-dates"].reused is False
    env.router.bodies["transcript-dates"] = b"[]"
    empty = passthrough.fetch("transcript-dates", "ACME", {})["transcript-dates"]
    assert (empty.reused, empty.payload, empty.row.error) == (False, [], None)
    assert passthrough.fetch("transcript-dates", "ACME", {})["transcript-dates"].reused is True
    assert env.router.calls == {"transcript-dates": 3}


def test_segments_fetch_two_endpoints(env: Env) -> None:
    passthrough = _passthrough(env)
    parts = passthrough.fetch("segments", "ACME", {})
    assert list(parts) == ["product", "geographic"]
    product, geographic = parts["product"], parts["geographic"]
    assert env.router.calls == {"segments-product": 1, "segments-geographic": 1}
    assert product.payload == _fixture("revenue-product-segmentation.ACME.json")
    assert geographic.payload == _fixture("revenue-geographic-segmentation.ACME.json")
    assert _stored(env, product.row.id) == ("segments-product", "ACME", {"symbol": "ACME"}, None)
    assert _stored(env, geographic.row.id)[0] == "segments-geographic"
    again = passthrough.fetch("segments", "ACME", {})
    assert [f.reused for f in again.values()] == [True, True]
    assert env.router.calls == {"segments-product": 1, "segments-geographic": 1}


def test_a_segments_part_that_is_not_a_list_is_stored_unusable(env: Env) -> None:
    """Spec 2026-11-17 8.1: FMP answers some failures with HTTP 200 and ``{"Error Message":
    ...}``. A segments part that is not a list is stored with its error, answered as fetched, and
    fetched again by the next request, as the news is; the part beside it, a list, is reused."""
    env.router.bodies["segments-product"] = b'{"Error Message": "x"}'
    passthrough = _passthrough(env)
    first = passthrough.fetch("segments", "ACME", {})
    product = first["product"]
    assert (product.reused, product.payload) == (False, {"Error Message": "x"})
    assert product.row.error == 'unusable payload: {"Error Message": "x"}'
    assert first["geographic"].row.error is None
    again = passthrough.fetch("segments", "ACME", {})
    assert [part.reused for part in again.values()] == [False, True]
    assert again["product"].row.id > product.row.id
    assert env.router.calls == {"segments-product": 2, "segments-geographic": 1}


def test_dcf_fetches_two_endpoints(env: Env) -> None:
    passthrough = _passthrough(env)
    parts = passthrough.fetch("dcf", "ACME", {})
    assert list(parts) == ["dcf", "levered"]
    dcf, levered = parts["dcf"], parts["levered"]
    assert env.router.calls == {"dcf": 1, "dcf-levered": 1}
    assert env.router.requested["dcf"] == env.router.requested["dcf-levered"] == {"symbol": "ACME"}
    assert dcf.payload == _fixture("discounted-cash-flow.ACME.json")
    assert levered.payload == _fixture("levered-discounted-cash-flow.ACME.json")
    assert _stored(env, dcf.row.id) == ("dcf", "ACME", {"symbol": "ACME"}, None)
    assert _stored(env, levered.row.id) == ("dcf-levered", "ACME", {"symbol": "ACME"}, None)
    assert dcf.row.provider == levered.row.provider == "fmp"
    again = passthrough.fetch("dcf", "ACME", {})
    assert [f.reused for f in again.values()] == [True, True]
    assert env.router.calls == {"dcf": 1, "dcf-levered": 1}


QUARTERS = {"symbol": "ACME", "period": "quarter", "limit": "44"}  # the quarters' key and query
# The refresh's own answers the series' must never stand in for: its five-year closes, its
# quarterly income statements and its three-year pair history.
REFRESH_ANSWERS = (("price-history", "ACME"), ("income-quarter", "ACME"), ("fx-history", "USDTWD"))


def _serve_twco(env: Env) -> None:
    """TWCO reports in TWD; the router serves it ACME's closes and quarters."""
    with closing(env.connect()) as conn:
        report_in(conn, "TWCO", "TWD")
    for endpoint, name in (
        ("price-history", "historical-price-eod-full.ACME.json"),
        ("income-quarter", "income-statement.quarter.ACME.json"),
    ):
        env.router.symbol_bodies[endpoint, "TWCO"] = (FIXTURES / "fmp" / name).read_bytes()


def test_pe_history_stores_closes_and_quarters_under_their_own_names(env: Env) -> None:
    """Spec 2026-11-19 6.3: ACME reports in USD, so two FMP calls, the daily closes of the ten
    years to the clock's day and the newest 44 quarterly income statements, each stored under
    the series' own endpoint, the closes with the years in their key in place of the start
    date."""
    parts = _passthrough(env).fetch("pe-history", "ACME", {})
    assert set(parts) == {"closes", "quarters"}
    closes, quarters = parts["closes"], parts["quarters"]
    assert (closes.row.provider, closes.row.endpoint) == ("fmp", "pe-closes")
    assert (quarters.row.provider, quarters.row.endpoint) == ("fmp", "pe-quarters")
    assert env.router.calls == {"price-history": 1, "income-quarter": 1}
    start = years_before(env.clock().date(), 10).isoformat()
    assert env.router.requested["price-history"] == {"symbol": "ACME", "from": start}
    assert env.router.requested["income-quarter"] == QUARTERS
    years = {"symbol": "ACME", "years": "10"}
    assert _stored(env, closes.row.id) == ("pe-closes", "ACME", years, None)
    assert _stored(env, quarters.row.id) == ("pe-quarters", "ACME", QUARTERS, None)
    assert closes.payload == _fixture("historical-price-eod-full.ACME.json")
    assert quarters.payload == _fixture("income-statement.quarter.ACME.json")
    assert (closes.reused, quarters.reused) == (False, False)


def test_pe_history_adds_the_pair_for_a_company_in_another_currency(env: Env) -> None:
    """TWCO reports in TWD, its newest snapshot's currency: a third call, the pair's closes from
    eleven years before the clock's day, a year behind the closes' ten, since the first day's
    trailing year reaches back that far, stored under the pair as the rates stage stores its
    history, but under the series' own endpoint."""
    _serve_twco(env)
    parts = _passthrough(env).fetch("pe-history", "TWCO", {})
    assert set(parts) == {"closes", "quarters", "rates"}
    assert env.router.calls == {"price-history": 1, "income-quarter": 1, "fx-history": 1}
    today = env.clock().date()
    start = years_before(today, 11).isoformat()
    assert env.router.requested["fx-history"] == {"symbol": "USDTWD", "from": start}
    closes_from = years_before(today, 10).isoformat()
    assert env.router.requested["price-history"] == {"symbol": "TWCO", "from": closes_from}
    years = {"symbol": "USDTWD", "years": "11"}
    rates = parts["rates"]
    assert _stored(env, rates.row.id) == ("pe-rates", "USDTWD", years, None)
    assert rates.payload == _fixture("historical-price-eod-light.USDTWD.json")
    ten = {"symbol": "TWCO", "years": "10"}
    assert _stored(env, parts["closes"].row.id) == ("pe-closes", "TWCO", ten, None)


def test_pe_history_is_reused_within_reuse_hours(env: Env) -> None:
    """Each answer is reused while it is younger than ``reuse_hours``, across midnight too (the
    key holds the years, not the start date), and fetched again after."""
    passthrough = _passthrough(env)
    first = passthrough.fetch("pe-history", "ACME", {})
    env.clock.now += timedelta(hours=env.policy.refresh.reuse_hours - 1)  # the next day
    again = passthrough.fetch("pe-history", "ACME", {})
    assert all(fetched.reused for fetched in again.values())
    assert {part: f.row for part, f in again.items()} == {p: f.row for p, f in first.items()}
    assert env.router.calls == {"price-history": 1, "income-quarter": 1}
    env.clock.now += timedelta(hours=1)
    later = passthrough.fetch("pe-history", "ACME", {})
    assert not any(fetched.reused for fetched in later.values())
    assert env.router.calls == {"price-history": 2, "income-quarter": 2}


def test_the_refresh_s_closes_quarters_and_rates_stay_the_newest(env: Env) -> None:
    """Spec 6.3: a deeper answer stored as ``price-history`` would become the newest copy of the
    five-year closes for every reader, the engine among them; one stored as ``income-quarter`` or
    as ``fx-history`` would stand in for the refresh's quarters or its three-year rates. The
    series' answers add no row under any of the three."""
    with closing(env.connect()) as conn:
        clients = env.clients
        fetch_company(conn, clients.fmp, "ACME", env.policy, env.clock(), clients.secrets)
        before = {key: usable_responses(conn, "fmp", *key) for key in REFRESH_ANSWERS}
        closes = latest_response(conn, "fmp", "price-history", "ACME", {"symbol": "ACME"})
    assert closes is not None and before["fx-history", "USDTWD"] == []
    _serve_twco(env)
    passthrough = _passthrough(env)
    passthrough.fetch("pe-history", "ACME", {})
    passthrough.fetch("pe-history", "TWCO", {})
    with closing(env.connect()) as conn:
        assert {key: usable_responses(conn, "fmp", *key) for key in REFRESH_ANSWERS} == before
        after = latest_response(conn, "fmp", "price-history", "ACME", {"symbol": "ACME"})
        assert after is not None and after.id == closes.id
        assert rates_for(conn, "TWD") is None  # no pair history for the rates stage's readers


def test_the_backfill_writes_no_fact_from_the_deep_quarters(env: Env) -> None:
    """The statement backfill reads every stored response of a statement endpoint whatever its
    params; the series' quarters are not one, so no fact and no observation comes of them."""
    _serve_twco(env)
    passthrough = _passthrough(env)
    passthrough.fetch("pe-history", "ACME", {})
    passthrough.fetch("pe-history", "TWCO", {})
    with closing(env.connect()) as conn:
        assert backfill_statement_facts(conn, env.clock()) == 0
        assert conn.execute("SELECT count(*) FROM facts").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM observations").fetchone()[0] == 0


def test_an_empty_answer_is_stored_usable_and_reused(env: Env) -> None:
    """A company listed last month: FMP answers both deep calls with an empty list. Each is
    stored usable and reused like any other answer, and the series reads with no point (spec
    6.3, a series with no point; Review Focus 3)."""
    for endpoint in ("price-history", "income-quarter"):
        env.router.symbol_bodies[endpoint, "NEWCO"] = b"[]"
    passthrough = _passthrough(env)
    parts = passthrough.fetch("pe-history", "NEWCO", {})
    assert [fetched.row.error for fetched in parts.values()] == [None, None]
    series = trailing_series({part: f.payload for part, f in parts.items()}, "USD")
    assert series is not None and (series.points, series.since) == ((), None)
    assert all(f.reused for f in passthrough.fetch("pe-history", "NEWCO", {}).values())
    assert env.router.calls == {"price-history": 1, "income-quarter": 1}


def test_an_answer_that_is_not_a_list_is_stored_unusable_and_fetched_again(env: Env) -> None:
    """FMP's error object in place of the quarters: stored with the error ``unusable payload:
    ...``, answered as fetched and never reused, while the closes beside it are."""
    env.router.bodies["income-quarter"] = b'{"Error Message": "Limit Reach"}'
    passthrough = _passthrough(env)
    first = passthrough.fetch("pe-history", "ACME", {})
    quarters = first["quarters"]
    assert quarters.payload == {"Error Message": "Limit Reach"}
    assert quarters.row.error == 'unusable payload: {"Error Message": "Limit Reach"}'
    assert first["closes"].row.error is None
    second = passthrough.fetch("pe-history", "ACME", {})
    assert (second["closes"].reused, second["quarters"].reused) == (True, False)
    assert second["quarters"].row.id > quarters.row.id
    assert env.router.calls == {"price-history": 1, "income-quarter": 2}


def test_a_failed_part_is_stored_and_raised_after_the_ones_before_it(env: Env) -> None:
    """The quarters' call fails: the closes stored before it stand, the failure is stored with its
    message, scrubbed, and raised; the next fetch reuses the closes and asks the quarters again."""
    env.router.fail.add("income-quarter")
    env.router.fail_status = 403
    passthrough = _passthrough(env)
    with pytest.raises(VendorError) as caught:
        passthrough.fetch("pe-history", "ACME", {})
    assert FMP_KEY not in str(caught.value) and caught.value.status == 403
    with closing(env.connect()) as conn:
        rows = conn.execute("SELECT endpoint, http_status, error FROM vendor_responses")
        assert [tuple(row) for row in rows] == [
            ("pe-closes", 200, None),
            ("pe-quarters", 403, str(caught.value)),
        ]
    env.router.fail.clear()
    again = passthrough.fetch("pe-history", "ACME", {})
    assert (again["closes"].reused, again["quarters"].reused) == (True, False)


def test_a_fetched_response_is_citable(env: Env) -> None:
    product = _passthrough(env).fetch("segments", "ACME", {})["product"]
    ref = f"response:{product.row.id}/0/data/Widgets"
    with closing(env.connect()) as conn:
        assert resolve(conn, "ACME", ref, env.policy) == Resolved(2900000000, None, None, None)
        assert resolve(conn, "BOLT", ref, env.policy) is None  # another company's response


@pytest.mark.parametrize(
    ("kind", "params", "provider", "endpoint", "stored", "requested", "fixture"),
    [
        pytest.param(
            "news",
            {},
            "fmp",
            "news",
            {"symbol": "ACME", "limit": "20"},
            {"symbols": "ACME", "limit": "20"},
            "fmp/news-stock.ACME.json",
            id="news-default-limit",
        ),
        pytest.param(
            "news",
            {"limit": "5"},
            "fmp",
            "news",
            {"symbol": "ACME", "limit": "5"},
            {"symbols": "ACME", "limit": "5"},
            "fmp/news-stock.ACME.json",
            id="news-limit",
        ),
        pytest.param(
            "insider-trades",
            {},
            "fmp",
            "insider-trades",
            {"symbol": "ACME", "limit": "100"},  # the page size is in the reuse key
            {"symbol": "ACME", "page": "0", "limit": "100"},
            "fmp/insider-trading-search.ACME.json",
            id="insider-trades",
        ),
        pytest.param(
            "filings",
            WINDOW,
            "fmp",
            "sec-filings",
            {**WINDOW, "symbol": "ACME", "limit": "1000"},  # the page size is in the reuse key
            {**WINDOW, "symbol": "ACME", "page": "0", "limit": "1000"},
            "fmp/sec-filings-search-symbol.ACME.json",
            id="filings",
        ),
        pytest.param(
            "filing-reports",
            {},
            "fmp",
            "filing-report-dates",
            {"symbol": "ACME"},
            {"symbol": "ACME"},
            "fmp/financial-reports-dates.ACME.json",
            id="filing-reports",
        ),
        pytest.param(
            "filing-report",
            REPORT,
            "fmp",
            "filing-report",
            {**REPORT, "symbol": "ACME"},
            {**REPORT, "symbol": "ACME"},
            "fmp/financial-reports-json.ACME.json",
            id="filing-report",
        ),
    ],
)
def test_each_kind_stores_its_call(
    env: Env,
    kind: str,
    params: dict[str, str],
    provider: str,
    endpoint: str,
    stored: dict[str, str],
    requested: dict[str, str],
    fixture: str,
) -> None:
    [fetched] = _passthrough(env).fetch(kind, "ACME", params).values()
    assert env.router.requested[endpoint] == requested
    assert fetched.row.provider == provider
    assert _stored(env, fetched.row.id) == (endpoint, "ACME", stored, None)
    vendor, _, name = fixture.partition("/")
    assert fetched.payload == _fixture(name, vendor)


def test_the_stored_payload_and_the_answer_carry_no_key(env: Env) -> None:
    """A vendor that echoed a key in its body: the store and the answer hold ``<key>``."""
    echoed = [{"title": f"see https://example.com/?apikey={FMP_KEY}&token={FMP_KEY}"}]
    env.router.bodies["news"] = json.dumps(echoed).encode()
    fetched = _passthrough(env).fetch("news", "ACME", {})["news"]
    with closing(env.connect()) as conn:
        payload = response_payload(conn, fetched.row.id)
    assert payload is not None and FMP_KEY not in payload
    assert fetched.payload == [{"title": "see https://example.com/?apikey=<key>&token=<key>"}]


def test_a_vendor_error_is_stored_and_raised_scrubbed(env: Env) -> None:
    env.router.fail.add("transcript")
    env.router.fail_status = 403
    passthrough = _passthrough(env)
    with pytest.raises(VendorError) as caught:
        passthrough.fetch("transcript", "ACME", Q3)
    message = str(caught.value)
    assert caught.value.status == 403 and FMP_KEY not in message and "apikey=<key>" in message
    with closing(env.connect()) as conn:
        rows = conn.execute("SELECT endpoint, http_status, payload, error FROM vendor_responses")
        assert [tuple(r) for r in rows] == [("transcript", 403, None, message)]
    env.router.fail.clear()
    assert passthrough.fetch("transcript", "ACME", Q3)["transcript"].reused is False


@pytest.mark.parametrize(
    ("kind", "params", "message"),
    [
        ("sec-filings", {}, "unknown vendor kind: sec-filings"),  # an endpoint, not a kind
        ("transcript", {"year": "2026"}, "a transcript needs year and quarter"),
        ("transcript", {"quarter": "3"}, "a transcript needs year and quarter"),
        ("transcript", {"year": "2026", "quarter": "5"}, "quarter must be 1 to 4"),
        ("transcript", {"year": "last", "quarter": "3"}, "year must be a whole number"),
        ("news", {"limit": "0"}, "limit is 1 to 100"),
        ("news", {"limit": "101"}, "limit is 1 to 100"),
    ],
)
def test_a_bad_request_is_a_value_error_before_any_call(
    env: Env, kind: str, params: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _passthrough(env).fetch(kind, "ACME", params)
    assert env.router.calls == {}


def test_a_shared_limiter_paces_both_clients(env: Env) -> None:
    """The worker's client and the pass-through's take their slots from one ``RateLimiter``:
    ``totals()`` counts both, and the pass-through's call waits behind the worker's. The fetch
    stores ACME's newest call's transcript, fiscal 2026 Q3, so the pass-through asks Q2."""
    sleeps: list[float] = []
    pace = env.policy.refresh.fmp_calls_per_minute
    limiter = RateLimiter(pace, env.clock, sleeps.append)
    keys = Keys(FMP_KEY)
    transport = env.router.transport
    worker_fmp, secrets = build_clients(keys, env.policy, transport=transport, limiter=limiter)
    passthrough_fmp = build_fmp(keys, env.policy, transport=transport, limiter=limiter)
    try:
        assert worker_fmp.limiter is passthrough_fmp.limiter is limiter
        with closing(env.connect()) as conn:
            outcome = fetch_company(conn, worker_fmp, "ACME", env.policy, env.clock(), secrets)
        passthrough = Passthrough(passthrough_fmp, env.connect, env.policy, env.clock, secrets)
        q2 = {"year": "2026", "quarter": "2"}
        fetched = passthrough.fetch("transcript", "ACME", q2)["transcript"]
    finally:
        worker_fmp.close()
        passthrough_fmp.close()
    # The worker's 31 FMP calls and the newest call's transcript.
    assert fetched.reused is False and outcome.calls == 32
    # The clock stands still, so the n-th call waits n slots: 0 + 1 + ... + 32.
    interval = limiter.interval.total_seconds()  # 60 / pace, to the microsecond
    assert limiter.totals() == PaceTotals(33, pytest.approx(528 * interval), 0)
    assert sleeps[-1] == pytest.approx(32 * interval)


class Held:
    """A pass-through over FMP whose transcript calls the vendor holds until ``release``; any other
    call answers ``[]``. ``called`` names each held call that reached the vendor (``2026-Q1``);
    ``hold`` starts four, one per quarter of 2026, on threads of their own, each holding a slot
    until released, and returns once all four are at the vendor."""

    def __init__(self, env: Env) -> None:
        self.entered = threading.Semaphore(0)
        self.release = threading.Event()
        self.called: list[str] = []
        self.answered: list[bool] = []  # each threaded fetch's ``reused``
        self.threads: list[threading.Thread] = []
        transport = httpx.MockTransport(self._answer)
        refresh = env.policy.refresh
        self.http = VendorHttp(fmp_api.BASE_URL, [FMP_KEY], refresh, transport=transport)
        fmp = Fmp(self.http, FMP_KEY)
        self.passthrough = Passthrough(fmp, env.connect, env.policy, env.clock, (FMP_KEY,))

    def _answer(self, request: httpx.Request) -> httpx.Response:
        if not request.url.path.endswith("/earning-call-transcript"):
            return httpx.Response(200, json=[])
        self.called.append(f"{request.url.params['year']}-Q{request.url.params['quarter']}")
        self.entered.release()
        self.release.wait(5)
        return httpx.Response(200, json=[])

    def start(self, kind: str, params: dict[str, str]) -> threading.Thread:
        def fetch() -> None:
            [fetched] = self.passthrough.fetch(kind, "ACME", params).values()
            self.answered.append(fetched.reused)

        thread = threading.Thread(target=fetch)
        self.threads.append(thread)
        thread.start()
        return thread

    def hold(self) -> None:
        for quarter in "1234":
            self.start("transcript", {"year": "2026", "quarter": quarter})
        for _ in range(PASSTHROUGH_SLOTS):
            assert self.entered.acquire(timeout=5)

    def finish(self) -> None:
        """Release the held calls and wait for every thread."""
        self.release.set()
        for thread in self.threads:
            thread.join(5)
        assert not any(thread.is_alive() for thread in self.threads)


@pytest.fixture
def held(env: Env) -> Iterator[Held]:
    held = Held(env)
    try:
        yield held
    finally:
        held.finish()
        held.http.close()


def test_a_fifth_vendor_call_waits_for_a_slot(held: Held) -> None:
    """Four vendor calls in flight hold the ``PASSTHROUGH_SLOTS``: a fifth waits until one ends,
    and a reuse takes no slot meanwhile."""
    assert PASSTHROUGH_SLOTS == 4 and PASSTHROUGH_WAIT_S == 10.0
    held.passthrough.fetch("news", "ACME", {})  # stored: the next one is a reuse
    held.hold()
    fifth = held.start("transcript", {"year": "2025", "quarter": "4"})
    fifth.join(0.2)
    assert fifth.is_alive() and len(held.called) == 4  # the fifth waits for a slot
    held.start("news", {}).join(5)
    assert held.answered == [True]  # a reuse needs no slot
    held.finish()
    assert sorted(held.called) == ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]
    assert held.answered == [True] + [False] * 5


def test_a_call_that_waits_past_the_bound_is_busy(
    held: Held, env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With every slot held past ``PASSTHROUGH_WAIT_S``, the call gives up: ``PassthroughBusy``,
    nothing called and nothing stored; once a slot frees, the same call goes through. The P/E
    history's calls wait for a slot as any other."""
    monkeypatch.setattr(passthrough_module, "PASSTHROUGH_WAIT_S", 0.2)
    held.hold()
    began = time.monotonic()
    with pytest.raises(PassthroughBusy) as caught:
        held.passthrough.fetch("transcript", "ACME", {"year": "2025", "quarter": "4"})
    assert time.monotonic() - began >= 0.15  # it waited for a slot first
    assert str(caught.value) == "the pass-throughs are busy: four calls are in flight, try again"
    with pytest.raises(PassthroughBusy):
        held.passthrough.fetch("pe-history", "ACME", {})
    assert len(held.called) == 4
    with closing(env.connect()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM vendor_responses").fetchone()[0] == 0
    held.finish()
    fetched = held.passthrough.fetch("transcript", "ACME", {"year": "2025", "quarter": "4"})
    assert fetched["transcript"].reused is False and "2025-Q4" in held.called
    assert not any(f.reused for f in held.passthrough.fetch("pe-history", "ACME", {}).values())
