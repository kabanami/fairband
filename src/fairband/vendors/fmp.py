"""The Financial Modeling Prep adapter: one method per route of the stable API.

Each method makes one ``VendorHttp.get`` and returns the ``VendorResponse``; build the client with
``BASE_URL`` and the key among its secrets, so the key is scrubbed from everything it emits. The
key travels as the ``apikey`` query parameter. Symbols arrive in the exchange form the store keeps
(``BRK.B``) and leave in FMP's form (``BRK-B``); this class is the only place that converts them on
the way out (``normalize_fmp.screener_rows`` and ``peer_symbols`` convert the screener's and the
peers' symbols on the way back).

Routes and parameters, checked on 2026-11-01 against the FMP stable documentation
(https://site.financialmodelingprep.com/developer/docs/stable, each route's page and its
documented response example):

- ``company-screener``: ``exchange``, ``marketCapMoreThan``, ``isEtf``, ``isFund``,
  ``isActivelyTrading``, ``limit``. Confirmed.
- ``profile``: ``symbol``. Confirmed.
- ``quote``: ``symbol``; ``batch-quote``: ``symbols`` (comma-separated). Both confirmed as routes.
  The documentation lists ``batch-quote`` for the higher plans only, and with no key here it is
  unchecked which of the two this account serves: ``quote`` serves one symbol, ``batch-quote``
  several.
- ``income-statement``, ``balance-sheet-statement``, ``cash-flow-statement``: ``symbol``,
  ``period`` (``annual`` or ``quarter``), ``limit``. Confirmed.
- ``balance-sheet-statement-as-reported``: ``symbol``, ``period``, ``limit``. Confirmed.
- ``analyst-estimates``: ``symbol``, ``period``, ``page``, ``limit``. Confirmed. Quarterly rows
  reach far into the future, so a quarterly request asks for 40 rows and the engine picks the
  quarters by period, never by row order (source-evidence DS-08/10/11); annual asks for 6.
- ``earnings``: ``symbol``, ``limit``, ``includeReportTimes``. Confirmed. ``includeReportTimes=true``
  adds ``periodEnding``, ``fiscalYear``, ``fiscalPeriod``, ``confirmed`` and ``time`` (live probe
  2026-10-29, source-evidence DS-19), so a street actual is keyed by its fiscal quarter end.
- ``historical-price-eod/full``: ``symbol``, ``from``, ``to``. Confirmed; ``to`` is left out, so
  the history runs to the latest close.
- ``stock-peers``: ``symbol``; the answer is a list of objects, each with a ``symbol``. From the
  growth routes spec (2026-11-02); not checked here, the documentation page refusing an automated
  read.

The agent's pass-throughs (spec 2026-11-06 Tier 2, 15.3), checked on 2026-11-06 against the
stable documentation's examples as a web search returns them (the pages themselves refuse an
automated read, so the parameter tables are unchecked):

- ``earning-call-transcript``: ``symbol``, ``year``, ``quarter``; the answer lists the call with
  its ``symbol``, ``period``, ``year``, ``date`` and ``content``.
- ``news/stock``: ``symbols`` (the one company here), ``limit``.
- ``revenue-product-segmentation``, ``revenue-geographic-segmentation``: ``symbol``; ``period``
  and ``structure`` are left out, so the years come in the nested form, a ``data`` object per
  fiscal year.
- ``insider-trading/search``: ``symbol``, ``page``, ``limit``; the documented example asks for
  page 0 with 100 rows, which this adapter asks for.
"""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Literal

from fairband.vendors.http import VendorHttp, VendorResponse
from fairband.vendors.limiter import RateLimiter

BASE_URL = "https://financialmodelingprep.com/stable"

type StatementKind = Literal["income", "balance", "cashflow"]
type Period = Literal["annual", "quarter"]

QUARTER_ESTIMATE_LIMIT = 40
ANNUAL_ESTIMATE_LIMIT = 6
INSIDER_TRADES_LIMIT = 100  # the documented example's page size

_STATEMENT_ROUTES: dict[StatementKind, str] = {
    "income": "income-statement",
    "balance": "balance-sheet-statement",
    "cashflow": "cash-flow-statement",
}

# The universe request (spec 6.1); the universe build applies the policy's own filters after it.
_SCREENER_PARAMS = {
    "exchange": "NYSE,NASDAQ,AMEX",
    "marketCapMoreThan": "2000000000",
    "isEtf": "false",
    "isFund": "false",
    "isActivelyTrading": "true",
    "limit": "10000",
}


def to_fmp_symbol(symbol: str) -> str:
    """The exchange form in FMP's form: a share-class dot becomes a dash (``BRK.B`` → ``BRK-B``)."""
    return symbol.replace(".", "-")


class Fmp:
    """The FMP stable routes the screen reads and the agent's pass-throughs fetch; every method
    returns the response as received."""

    def __init__(self, http: VendorHttp, api_key: str) -> None:
        self._http = http
        self._api_key = api_key

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    @property
    def limiter(self) -> RateLimiter:
        """The HTTP client's limiter, which paces every call this adapter makes."""
        return self._http.limiter

    def screener(self) -> VendorResponse:
        return self._get("company-screener", _SCREENER_PARAMS)

    def profile(self, symbol: str) -> VendorResponse:
        return self._get("profile", {"symbol": to_fmp_symbol(symbol)})

    def quote(self, symbols: Sequence[str]) -> VendorResponse:
        """``quote`` for one symbol, ``batch-quote`` for several."""
        if not symbols:
            raise ValueError("a quote needs at least one symbol")
        if len(symbols) == 1:
            return self._get("quote", {"symbol": to_fmp_symbol(symbols[0])})
        return self._get("batch-quote", {"symbols": ",".join(map(to_fmp_symbol, symbols))})

    def statement(
        self, symbol: str, kind: StatementKind, period: Period, limit: int
    ) -> VendorResponse:
        params = {"symbol": to_fmp_symbol(symbol), "period": period, "limit": str(limit)}
        return self._get(_STATEMENT_ROUTES[kind], params)

    def balance_as_reported(self, symbol: str, limit: int) -> VendorResponse:
        params = {"symbol": to_fmp_symbol(symbol), "period": "annual", "limit": str(limit)}
        return self._get("balance-sheet-statement-as-reported", params)

    def estimates(self, symbol: str, period: Period, limit: int | None = None) -> VendorResponse:
        """The consensus rows; ``limit`` defaults to 40 for quarters and 6 for years."""
        if limit is None:
            limit = QUARTER_ESTIMATE_LIMIT if period == "quarter" else ANNUAL_ESTIMATE_LIMIT
        params = {"symbol": to_fmp_symbol(symbol), "period": period, "limit": str(limit)}
        return self._get("analyst-estimates", params)

    def earnings(self, symbol: str, limit: int) -> VendorResponse:
        params = {"symbol": to_fmp_symbol(symbol), "limit": str(limit)}
        return self._get("earnings", {**params, "includeReportTimes": "true"})

    def price_history(self, symbol: str, start: date) -> VendorResponse:
        params = {"symbol": to_fmp_symbol(symbol), "from": start.isoformat()}
        return self._get("historical-price-eod/full", params)

    def peers(self, symbol: str) -> VendorResponse:
        return self._get("stock-peers", {"symbol": to_fmp_symbol(symbol)})

    def transcript(self, symbol: str, year: int, quarter: int) -> VendorResponse:
        params = {"symbol": to_fmp_symbol(symbol), "year": str(year), "quarter": str(quarter)}
        return self._get("earning-call-transcript", params)

    def news(self, symbol: str, limit: int) -> VendorResponse:
        return self._get("news/stock", {"symbols": to_fmp_symbol(symbol), "limit": str(limit)})

    def segments_product(self, symbol: str) -> VendorResponse:
        return self._get("revenue-product-segmentation", {"symbol": to_fmp_symbol(symbol)})

    def segments_geographic(self, symbol: str) -> VendorResponse:
        return self._get("revenue-geographic-segmentation", {"symbol": to_fmp_symbol(symbol)})

    def insider_trades(self, symbol: str) -> VendorResponse:
        """The newest ``INSIDER_TRADES_LIMIT`` trades, the first page."""
        params = {"symbol": to_fmp_symbol(symbol), "page": "0", "limit": str(INSIDER_TRADES_LIMIT)}
        return self._get("insider-trading/search", params)

    def _get(self, route: str, params: Mapping[str, str]) -> VendorResponse:
        return self._http.get(route, {**params, "apikey": self._api_key})
