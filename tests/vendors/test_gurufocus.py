"""The GuruFocus adapter against ``httpx.MockTransport`` (never the network), and its normalizer
against the synthetic fixtures in ``tests/fixtures/gurufocus``.

ACME's responses hold every value, as strings where GuruFocus sends strings; BOLT's hold a null, a
``"-"`` and a key the response lacks.
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
from fairband.vendors import normalize_gf
from fairband.vendors.gurufocus import BASE_URL, GuruFocus
from fairband.vendors.http import VendorHttp, VendorResponse
from fairband.vendors.normalize_gf import num, summary_observations

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


def test_summary_keeps_the_exchange_symbol() -> None:
    request, response = fetch(TOKEN, lambda gf: gf.summary("BRK.B"))
    assert request.url.path == "/public/user/T0K3N/stock/BRK.B/summary"
    assert response.url == "https://api.gurufocus.com/public/user/<key>/stock/BRK.B/summary"


def test_the_client_asks_no_pe_series() -> None:
    """Spec 2026-11-19 6.3: Fairband builds the trailing P/E from FMP's data, so the client has no
    call for GuruFocus's series."""
    assert not hasattr(GuruFocus, "pe_ttm")


def test_the_client_asks_no_key_ratios() -> None:
    """Spec 2026-11-19 7.1: the engine reads no GuruFocus EPS, so neither the client nor the
    normalizer has the key ratios; the summary, which holds the moat score, is the one call."""
    assert not hasattr(GuruFocus, "keyratios")
    assert not hasattr(normalize_gf, "keyratios_observations")


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
