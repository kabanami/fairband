"""The vendor double the refresh tests share: one ``httpx.MockTransport`` that serves FMP's
fixtures, the one vendor Fairband calls.

The tests in this directory import it as ``vendor_double`` (pytest puts the directory on the path);
``conftest.py`` builds the client over it. The key is fake and exists only here.
"""

import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from fairband.vendors.fmp import Fmp

FIXTURES = Path(__file__).parent.parent / "fixtures"
FMP_KEY = "fake-fmp-key-0001"  # not a real key

# The FMP route to the name ``fairband.refresh.fetch`` (or ``fairband.refresh.passthrough``)
# stores its endpoint under; a request's ``period``, when it sends one, is appended
# (``income-statement`` + annual → ``income-annual``), but on the routes of
# ``_FISCAL_PERIOD_ROUTES``.
_FMP_ENDPOINTS = {
    "income-statement": "income",
    "balance-sheet-statement": "balance",
    "cash-flow-statement": "cashflow",
    "balance-sheet-statement-as-reported": "balance-asreported",
    "analyst-estimates": "estimates",
    "historical-price-eod/full": "price-history",
    "historical-price-eod/light": "fx-history",  # a forex pair's closes (``refresh.rates``)
    "company-screener": "screener",
    "stock-peers": "peers",
    "stock-price-change": "price-change",
    "price-target-consensus": "price-target",
    "grades-consensus": "grades",
    "earning-call-transcript": "transcript",
    "earning-call-transcript-dates": "transcript-dates",
    "news/stock": "news",
    "revenue-product-segmentation": "segments-product",
    "revenue-geographic-segmentation": "segments-geographic",
    "insider-trading/search": "insider-trades",
    "discounted-cash-flow": "dcf",
    "levered-discounted-cash-flow": "dcf-levered",
    "sec-filings-search/symbol": "sec-filings",
    "financial-reports-dates": "filing-report-dates",
    "financial-reports-json": "filing-report",
}
# The routes whose ``period`` is a fiscal period (``Q1``), not ``annual`` or ``quarter``: it names
# neither the fixture nor the endpoint (``financial-reports-json.ACME.json``, ``filing-report``).
_FISCAL_PERIOD_ROUTES = {"financial-reports-json"}
# The routes that name their one company in a parameter other than ``symbol``.
_SYMBOL_PARAMS = {"news/stock": "symbols"}


class Router:
    """Answers each request with the fixture for its route and symbol.

    FMP requests read ``fmp/<route>[.<period>][.<symbol>].json`` (a slash in the route becomes a
    dash; a forex pair is the symbol, ``historical-price-eod-light.USDSEK.json``; a filing
    report's fiscal period is left out, ``financial-reports-json.ACME.json``), or, where the
    symbol has none, the same name without the symbol (``ratios-ttm.json``), a fixture that
    serves every company. ``calls`` counts the requests per endpoint, named as the fetch stores
    them (``income-annual``, ``quote``), ``symbol_calls`` per symbol and ``hosts`` per host, so a
    test sees a request to any other vendor; a retry counts again, and ``requested`` keeps each
    endpoint's last query parameters, the key left out. An endpoint in
    ``fail``, or any request for a symbol in ``fail_symbols``, answers ``fail_status`` (HTTP 500
    unless set); an endpoint and symbol in ``fail_once`` answer it as many times as their count,
    then as they would. An endpoint and symbol in ``symbol_bodies`` answer 200 with that body
    instead of the fixture, and so, for every symbol, does an endpoint in ``bodies``;
    ``symbol_bodies`` comes first. A request with no fixture answers 404. The fetch workers call it
    from several threads, so it counts under a lock.
    """

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.symbol_calls: Counter[str] = Counter()
        self.hosts: Counter[str] = Counter()
        self.fail: set[str] = set()
        self.fail_symbols: set[str] = set()
        self.fail_status = 500
        self.fail_once: dict[tuple[str, str], int] = {}  # by endpoint and symbol: failures left
        self.requested: dict[str, dict[str, str]] = {}
        self.bodies: dict[str, bytes] = {}
        self.symbol_bodies: dict[tuple[str, str], bytes] = {}  # by endpoint and symbol
        self.transport = httpx.MockTransport(self._handle)
        self._lock = threading.Lock()

    def _handle(self, request: httpx.Request) -> httpx.Response:
        endpoint, symbol, fixture = _resolve(request)
        with self._lock:
            self.calls[endpoint] += 1
            self.symbol_calls[symbol] += 1
            self.hosts[request.url.host] += 1
            self.requested[endpoint] = {
                name: value for name, value in request.url.params.items() if name != "apikey"
            }
            failing_once = self.fail_once.get((endpoint, symbol), 0) > 0
            if failing_once:
                self.fail_once[endpoint, symbol] -= 1
        if failing_once or endpoint in self.fail or symbol in self.fail_symbols:
            return httpx.Response(self.fail_status)
        body = self.symbol_bodies.get((endpoint, symbol), self.bodies.get(endpoint))
        if body is None:
            if not fixture.is_file():
                return httpx.Response(404, json={"Error Message": f"no fixture {fixture.name}"})
            body = fixture.read_bytes()
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})


def _resolve(request: httpx.Request) -> tuple[str, str, Path]:
    """The endpoint name, the symbol (``""`` for none) and the fixture path for ``request``."""
    route = request.url.path.removeprefix("/stable/")
    period = None if route in _FISCAL_PERIOD_ROUTES else request.url.params.get("period")
    symbol = request.url.params.get(_SYMBOL_PARAMS.get(route, "symbol"), "")
    name = _FMP_ENDPOINTS.get(route, route)
    parts = (route.replace("/", "-"), period, symbol)
    fixture = FIXTURES / "fmp" / (".".join(part for part in parts if part) + ".json")
    # The symbol's own fixture first, else the one every company shares.
    shared = FIXTURES / "fmp" / (".".join(part for part in parts[:2] if part) + ".json")
    if not fixture.is_file() and shared.is_file():
        fixture = shared
    return (f"{name}-{period}" if period else name), symbol, fixture


class Clock:
    """A settable clock: the clients stamp responses with it, and the tests pass ``clock()``."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@dataclass(frozen=True)
class Clients:
    """The FMP adapter over the router, and the secrets the fetch scrubs from what it stores."""

    fmp: Fmp
    secrets: tuple[str, ...]
