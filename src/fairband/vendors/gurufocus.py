"""The GuruFocus adapter: the two calls per company of spec 6.5, ``summary`` and ``keyratios``, and
the agent's pass-through of the daily trailing P/E series, ``pettm`` (spec 2026-11-06 Tier 2, 13.7
and 15.3), the route the stocks repository's notes record as working, with daily rows since 1997.

Each method makes one ``VendorHttp.get`` and returns the ``VendorResponse``; build the client with
``BASE_URL`` and the token among its secrets, so the token is scrubbed from everything it emits.
The token travels in the URL path, ``https://api.gurufocus.com/public/user/{token}/stock/...``;
this class holds it only to build that path and never logs it. Symbols stay in the exchange form
the store keeps (``BRK.B``), which is GuruFocus's form too.

GuruFocus answers some failures with HTTP 200 (an unknown path under ``stock/{symbol}/`` returns a
zero-filled series), so a caller judges a response by its content: ``normalize_gf`` gives no rows
for a payload without the expected shape.
"""

from fairband.vendors.http import VendorHttp, VendorResponse

BASE_URL = "https://api.gurufocus.com/public/user"
PROVIDER = "gf"  # GuruFocus's name in the store, the refresh's responses and the pass-through's
PE_TTM = "pettm"  # the trailing P/E series' route, and the endpoint its responses are stored under


class GuruFocus:
    """The GuruFocus routes the screen reads and the agent's pass-through fetches; every method
    returns the response as received."""

    def __init__(self, http: VendorHttp, token: str) -> None:
        self._http = http
        self._token = token

    def close(self) -> None:
        """Close the HTTP client."""
        self._http.close()

    def summary(self, symbol: str) -> VendorResponse:
        """``stock/{symbol}/summary``: the moat score, Altman Z″ and ADR ratio."""
        return self._get(symbol, "summary")

    def keyratios(self, symbol: str) -> VendorResponse:
        """``stock/{symbol}/keyratios``: EPS (TTM) and EPS without NRI among the key ratios."""
        return self._get(symbol, "keyratios")

    def pe_ttm(self, symbol: str) -> VendorResponse:
        """``stock/{symbol}/pettm``: the trailing P/E, a row a day (``normalize_gf.pe_ttm_rows``
        reads them)."""
        return self._get(symbol, PE_TTM)

    def _get(self, symbol: str, route: str) -> VendorResponse:
        # The leading slash keeps the path a path: a real token is two halves joined by a colon,
        # and a relative URL that starts "half:" parses as a scheme, which drops the first half.
        # httpx appends a path that starts with a slash to the base URL's path.
        return self._http.get(f"/{self._token}/stock/{symbol}/{route}", {})
