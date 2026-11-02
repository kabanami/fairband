"""The FMP adapter's requests against ``httpx.MockTransport``; never the network."""

from collections.abc import Callable, Iterator
from datetime import date

import httpx
import pytest

from fairband.policy import load_policy
from fairband.vendors.fmp import BASE_URL, Fmp
from fairband.vendors.http import VendorHttp, VendorResponse

KEY = "test-fmp-key"  # not a real key


class Recorder:
    """Answers every request with an empty JSON list and keeps the requests."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, json=[])

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def fmp(recorder: Recorder) -> Iterator[Fmp]:
    policy = load_policy().refresh
    with VendorHttp(BASE_URL, [KEY], policy, transport=recorder.transport) as http:
        yield Fmp(http, KEY)


def _sent(request: httpx.Request) -> tuple[str, dict[str, str]]:
    assert request.url.host == "financialmodelingprep.com"
    assert request.url.scheme == "https"
    return request.url.path, dict(request.url.params)


def test_requests_carry_apikey_and_converted_symbol(fmp: Fmp, recorder: Recorder) -> None:
    response = fmp.statement("BRK.B", "income", "annual", 11)
    path, params = _sent(recorder.last)
    assert path == "/stable/income-statement"
    assert params == {"symbol": "BRK-B", "period": "annual", "limit": "11", "apikey": KEY}
    assert KEY not in response.url and response.url.endswith("&apikey=<key>")
    assert response.json == []


def test_quarter_estimates_use_limit_40(fmp: Fmp, recorder: Recorder) -> None:
    fmp.estimates("ACME", "quarter")
    path, params = _sent(recorder.last)
    assert path == "/stable/analyst-estimates"
    assert params == {"symbol": "ACME", "period": "quarter", "limit": "40", "apikey": KEY}
    fmp.estimates("ACME", "annual")
    assert _sent(recorder.last)[1]["limit"] == "6"


def _route(
    name: str, call: Callable[[Fmp], VendorResponse], route: str, params: dict[str, str]
) -> object:
    return pytest.param(call, route, params, id=name)


ROUTES = [
    _route(
        "screener",
        lambda f: f.screener(),
        "company-screener",
        {
            "exchange": "NYSE,NASDAQ,AMEX",
            "marketCapMoreThan": "2000000000",
            "isEtf": "false",
            "isFund": "false",
            "isActivelyTrading": "true",
            "limit": "10000",
        },
    ),
    _route("profile", lambda f: f.profile("BRK.B"), "profile", {"symbol": "BRK-B"}),
    _route("peers", lambda f: f.peers("BRK.B"), "stock-peers", {"symbol": "BRK-B"}),
    _route("quote", lambda f: f.quote(["BRK.B"]), "quote", {"symbol": "BRK-B"}),
    _route(
        "batch-quote",
        lambda f: f.quote(["BRK.B", "ACME"]),
        "batch-quote",
        {"symbols": "BRK-B,ACME"},
    ),
    _route(
        "balance",
        lambda f: f.statement("ACME", "balance", "annual", 11),
        "balance-sheet-statement",
        {"symbol": "ACME", "period": "annual", "limit": "11"},
    ),
    _route(
        "cashflow",
        lambda f: f.statement("ACME", "cashflow", "quarter", 8),
        "cash-flow-statement",
        {"symbol": "ACME", "period": "quarter", "limit": "8"},
    ),
    _route(
        "income",
        lambda f: f.statement("ACME", "income", "quarter", 8),
        "income-statement",
        {"symbol": "ACME", "period": "quarter", "limit": "8"},
    ),
    _route(
        "as-reported",
        lambda f: f.balance_as_reported("BRK.B", 11),
        "balance-sheet-statement-as-reported",
        {"symbol": "BRK-B", "period": "annual", "limit": "11"},
    ),
    _route(
        "estimates",
        lambda f: f.estimates("ACME", "annual", 4),
        "analyst-estimates",
        {"symbol": "ACME", "period": "annual", "limit": "4"},
    ),
    _route(
        "earnings",
        lambda f: f.earnings("BRK.B", 12),
        "earnings",
        {"symbol": "BRK-B", "limit": "12", "includeReportTimes": "true"},
    ),
    _route(
        "price-history",
        lambda f: f.price_history("BRK.B", date(2021, 11, 1)),
        "historical-price-eod/full",
        {"symbol": "BRK-B", "from": "2021-11-01"},
    ),
]


@pytest.mark.parametrize(("call", "route", "params"), ROUTES)
def test_routes_and_params(
    fmp: Fmp,
    recorder: Recorder,
    call: Callable[[Fmp], VendorResponse],
    route: str,
    params: dict[str, str],
) -> None:
    call(fmp)
    assert _sent(recorder.last) == (f"/stable/{route}", {**params, "apikey": KEY})


def test_quote_needs_a_symbol(fmp: Fmp, recorder: Recorder) -> None:
    with pytest.raises(ValueError, match="at least one symbol"):
        fmp.quote([])
    assert recorder.requests == []
