"""The GuruFocus adapter against ``httpx.MockTransport`` (never the network), and its normalizer
against the synthetic fixtures in ``tests/fixtures/gurufocus``.

ACME's responses hold every value, as strings where GuruFocus sends strings; BOLT's hold a null, a
``"-"``, a key the response lacks and an EPS key under an unexpected category.
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from fairband.policy import load_policy
from fairband.store.observations import ObservationRow
from fairband.vendors.gurufocus import BASE_URL, GuruFocus
from fairband.vendors.http import VendorHttp, VendorResponse
from fairband.vendors.normalize_gf import (
    keyratios_observations,
    num,
    pe_ttm_rows,
    summary_observations,
)

TOKEN = "T0K3N"  # not a real token
FIXTURES = Path(__file__).parent.parent / "fixtures" / "gurufocus"
OBSERVED = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
ENTERED = datetime(2026, 11, 1, 9, 31, tzinfo=UTC)
TODAY = date(2026, 11, 1)
RID = 7


def load(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def fetch(
    token: str, call: Callable[[GuruFocus], VendorResponse]
) -> tuple[httpx.Request, VendorResponse]:
    """The one request ``call`` sends, answered with an empty object, and the response."""
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(answer)
    with VendorHttp(BASE_URL, [token], load_policy().refresh, transport=transport) as http:
        response = call(GuruFocus(http, token))
    [request] = requests
    return request, response


def test_token_only_in_path_and_scrubbed(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    request, response = fetch(TOKEN, lambda gf: gf.summary("AAPL"))
    assert (request.url.scheme, request.url.host) == ("https", "api.gurufocus.com")
    assert request.url.path == "/public/user/T0K3N/stock/AAPL/summary"
    assert request.url.query == b""
    assert TOKEN not in str(request.headers)
    assert response.url == "https://api.gurufocus.com/public/user/<key>/stock/AAPL/summary"
    assert caplog.records and TOKEN not in caplog.text


def test_keyratios_keeps_the_exchange_symbol() -> None:
    request, response = fetch(TOKEN, lambda gf: gf.keyratios("BRK.B"))
    assert request.url.path == "/public/user/T0K3N/stock/BRK.B/keyratios"
    assert response.url == "https://api.gurufocus.com/public/user/<key>/stock/BRK.B/keyratios"


def test_pe_ttm_reads_the_daily_trailing_pe_series() -> None:
    request, response = fetch(TOKEN, lambda gf: gf.pe_ttm("BRK.B"))
    assert request.url.path == "/public/user/T0K3N/stock/BRK.B/pettm"
    assert request.url.query == b""
    assert response.url == "https://api.gurufocus.com/public/user/<key>/stock/BRK.B/pettm"


def test_a_token_with_a_colon_stays_whole() -> None:
    # A real token is two halves joined by a colon; a relative URL that starts "half:" would parse
    # as a scheme and lose the first half.
    token = "T0K3N:T0K3N"
    request, response = fetch(token, lambda gf: gf.summary("AAPL"))
    assert request.url.path == "/public/user/T0K3N:T0K3N/stock/AAPL/summary"
    assert response.url == "https://api.gurufocus.com/public/user/<key>/stock/AAPL/summary"


def row(symbol: str, dataset: str, field: str, value: str | None, unit: str) -> ObservationRow:
    amount = None if value is None else Decimal(value)
    return ObservationRow(symbol, dataset, None, field, amount, unit, TODAY, OBSERVED, ENTERED, RID)


def test_summary_string_numbers_and_dashes() -> None:
    now = OBSERVED
    rows = summary_observations(
        {
            "summary": {
                "company_data": {
                    "moat_score": "7",
                    "z2score": "-",
                    "depositary_receipt_ratio": "-",
                }
            }
        },
        "X",
        1,
        now,
        now,
    )
    by = {r.field: r.value for r in rows}
    assert by == {"moat_score": Decimal(7), "depositary_receipt_ratio": None}


def test_summary_rows() -> None:
    assert summary_observations(load("summary.ACME"), "ACME", RID, OBSERVED, ENTERED) == [
        row("ACME", "gf-score", "moat_score", "7", "score"),
        row("ACME", "gf-score", "depositary_receipt_ratio", "1", "ratio"),
    ]


def test_summary_observations_leave_out_the_z_score() -> None:
    rows = summary_observations(load("summary.ACME"), "ACME", RID, OBSERVED, ENTERED)
    assert {r.field for r in rows} == {"moat_score", "depositary_receipt_ratio"}


def test_summary_null_and_missing_key_have_no_value() -> None:
    assert summary_observations(load("summary.BOLT"), "BOLT", RID, OBSERVED, ENTERED) == [
        row("BOLT", "gf-score", "moat_score", None, "score"),
        row("BOLT", "gf-score", "depositary_receipt_ratio", None, "ratio"),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"error": "Stock not found"},
        {"summary": None},
        {"summary": {"general": {}}},
        {"summary": {"company_data": None}},
        {"summary": {"company_data": []}},
    ],
)
def test_summary_without_company_data_gives_no_rows(payload: Any) -> None:
    assert summary_observations(payload, "ACME", RID, OBSERVED, ENTERED) == []


def test_keyratios_search_across_categories() -> None:
    assert keyratios_observations(load("keyratios.ACME"), "ACME", RID, OBSERVED, ENTERED) == [
        row("ACME", "gf-ratio", "eps_ttm", "6.11", "per-share"),
        row("ACME", "gf-ratio", "eps_without_nri", "5.87", "per-share"),
    ]
    # BOLT's "EPS (TTM)" sits under "Valuation Ratio", as "-".
    assert keyratios_observations(load("keyratios.BOLT"), "BOLT", RID, OBSERVED, ENTERED) == [
        row("BOLT", "gf-ratio", "eps_ttm", None, "per-share"),
        row("BOLT", "gf-ratio", "eps_without_nri", "-0.42", "per-share"),
    ]


def test_keyratios_first_category_wins_and_a_missing_key_has_no_value() -> None:
    payload = {"Fundamental": {"EPS (TTM)": "2.50"}, "Per Share Data": {"EPS (TTM)": "9.99"}}
    assert keyratios_observations(payload, "ACME", RID, OBSERVED, ENTERED) == [
        row("ACME", "gf-ratio", "eps_ttm", "2.50", "per-share"),
        row("ACME", "gf-ratio", "eps_without_nri", None, "per-share"),
    ]


@pytest.mark.parametrize(
    "payload", [None, [], {}, {"error": "Stock not found"}, {"EPS (TTM)": "6.11"}]
)
def test_keyratios_without_categories_gives_no_rows(payload: Any) -> None:
    assert keyratios_observations(payload, "ACME", RID, OBSERVED, ENTERED) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(7, "7"), (0, "0"), (3.41, "3.41"), ("3.41", "3.41"), (" -0.42 ", "-0.42")],
)
def test_num_reads_numbers_and_numeric_strings(raw: Any, expected: str) -> None:
    assert num(raw) == Decimal(expected)


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "  ",
        "-",
        "N/A",
        "n/a",
        "12.5%",
        "At Loss",
        "NaN",
        "inf",
        float("nan"),
        float("inf"),
        True,
        False,
        [],
        {},
    ],
)
def test_num_gives_none_for_what_is_not_a_number(raw: Any) -> None:
    assert num(raw) is None


def test_pe_ttm_rows_read_each_row_s_close() -> None:
    """A five-element row is the day's open, high, low and close, the close the P/E; a
    two-element row is the day's value. A value that is not a positive number is a loss: an "At
    Loss" row's zeros, a negative multiple, a word. A row without a date is left out."""
    payload = [
        ["2026-10-26", 18.1, 18.4, 17.9, 18.2],
        ["2026-10-27", "At Loss", 0, 0, 0],
        ["2026-10-28", 19.5],
        ["2026-10-29", -4.2],
        ["2026-10-30", "21.25"],
        ["2026-10-31", 0],
        ["not a date", 20.0],
        [20.0, 20.0],
        "2026-11-01",
        ["2026-11-02"],
    ]
    assert pe_ttm_rows(payload) == [
        (date(2026, 10, 26), 18.2),
        (date(2026, 10, 27), None),
        (date(2026, 10, 28), 19.5),
        (date(2026, 10, 29), None),
        (date(2026, 10, 30), 21.25),
        (date(2026, 10, 31), None),
    ]
    assert pe_ttm_rows(load("pettm.ACME")) == [
        (date(2026, 10, 28), 18.2),
        (date(2026, 10, 29), None),
        (date(2026, 10, 30), 18.5),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"error": "Stock not found"},
        [["not a date", 1.0]],
        [[1, 2, 3]],
        "x",
        [["2026-10-29", 0, 0, 0, 0], ["2026-10-30", "At Loss", 0, 0, 0], ["2026-10-31", 0]],
    ],
)
def test_pe_ttm_rows_without_dated_rows_are_none(payload: Any) -> None:
    """A payload that is not a list of dated rows, or whose dated rows hold no point above zero
    (GuruFocus's zero-filled catch-all), gives no series: the read says it could not be read."""
    assert pe_ttm_rows(payload) is None
