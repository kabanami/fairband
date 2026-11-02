"""The vendor double the refresh tests share: one ``httpx.MockTransport`` that serves the fixtures.

The tests in this directory import it as ``vendor_double`` (pytest puts the directory on the path);
``conftest.py`` builds the clients over it. The keys are fake and exist only here.
"""

import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus

FIXTURES = Path(__file__).parent.parent / "fixtures"
FMP_KEY = "fake-fmp-key-0001"  # not a real key
GF_TOKEN = "fakegfhalf:fakegfhalf2"  # not a real token; a real one has two halves and a colon

# The FMP route to the name ``fairband.refresh.fetch`` stores its endpoint under; a request's
# ``period``, when it sends one, is appended (``income-statement`` + annual → ``income-annual``).
_FMP_ENDPOINTS = {
    "income-statement": "income",
    "balance-sheet-statement": "balance",
    "cash-flow-statement": "cashflow",
    "balance-sheet-statement-as-reported": "balance-asreported",
    "analyst-estimates": "estimates",
    "historical-price-eod/full": "price-history",
    "company-screener": "screener",
    "stock-peers": "peers",
}


class Router:
    """Answers each request with the fixture for its route and symbol.

    FMP requests read ``fmp/<route>[.<period>][.<symbol>].json`` (a slash in the route becomes a
    dash), GuruFocus requests ``gurufocus/<route>.<symbol>.json``. ``calls`` counts the requests per
    endpoint, named as the fetch stores them (``income-annual``, ``quote``, ``summary``), and
    ``symbol_calls`` per symbol; a retry counts again, and ``requested`` keeps each endpoint's last
    query parameters, the key left out. An endpoint in ``fail``, or any request for a symbol in
    ``fail_symbols``, answers ``fail_status`` (HTTP 500 unless set). An endpoint and symbol in
    ``symbol_bodies`` answer 200 with that body instead of the fixture, and so, for every symbol,
    does an endpoint in ``bodies``; ``symbol_bodies`` comes first. A request with no fixture answers
    404. The fetch workers call it from several threads, so it counts under a lock.
    """

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.symbol_calls: Counter[str] = Counter()
        self.fail: set[str] = set()
        self.fail_symbols: set[str] = set()
        self.fail_status = 500
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
            self.requested[endpoint] = {
                name: value for name, value in request.url.params.items() if name != "apikey"
            }
        if endpoint in self.fail or symbol in self.fail_symbols:
            return httpx.Response(self.fail_status)
        body = self.symbol_bodies.get((endpoint, symbol), self.bodies.get(endpoint))
        if body is None:
            if not fixture.is_file():
                return httpx.Response(404, json={"Error Message": f"no fixture {fixture.name}"})
            body = fixture.read_bytes()
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})


def _resolve(request: httpx.Request) -> tuple[str, str, Path]:
    """The endpoint name, the symbol (``""`` for none) and the fixture path for ``request``."""
    if request.url.host == "api.gurufocus.com":
        *_, symbol, route = request.url.path.split("/")  # /public/user/<token>/stock/<s>/<route>
        return route, symbol, FIXTURES / "gurufocus" / f"{route}.{symbol}.json"
    route = request.url.path.removeprefix("/stable/")
    period = request.url.params.get("period")
    symbol = request.url.params.get("symbol", "")
    name = _FMP_ENDPOINTS.get(route, route)
    parts = (route.replace("/", "-"), period, symbol)
    fixture = FIXTURES / "fmp" / (".".join(part for part in parts if part) + ".json")
    return (f"{name}-{period}" if period else name), symbol, fixture


class Clock:
    """A settable clock: the clients stamp responses with it, and the tests pass ``clock()``."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@dataclass(frozen=True)
class Clients:
    """The two adapters over the router, and the secrets the fetch scrubs from what it stores."""

    fmp: Fmp
    gf: GuruFocus | None
    secrets: tuple[str, ...]
