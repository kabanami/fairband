"""The universe of the full-refresh tests: six screener listings and, for each admitted company,
every answer its fetch asks for, served by symbol (``Router.symbol_bodies``).

Admitted, with the revenue growth over the last three fiscal years that the deciles rank:

- ACME and AXLE: the synthetic company of ``synthetic`` under two symbols, revenue up $100 m a
  year at a 20% operating margin (5.3%). The two highest, so decile 10, "Very High": Mature Growth,
  valued on the synthetic NTM consensus.
- MILD: revenue up $30 m a year at 20% (2.4%). Decile 4, "Low": Mature Stable.
- NEWT: revenue up $10 m a year at a -10% margin that does not improve (0.9%): Young Growth. It
  lists in an industry of its own, so the industry fallback for its peers finds no mature company.

Not admitted: FIRB, a regional bank (recorded, excluded by industry), and TINY, below the $2 bn
floor (skipped). The quote, profile, closes, annual consensus, peers, splits and GuruFocus answers
are ACME's fixtures with the symbol changed.
"""

import json
from typing import Any

from synthetic import M, Payload, bodies, estimates_quarter
from vendor_double import FIXTURES, Router

B = 1_000_000_000
ADMITTED = ("ACME", "AXLE", "MILD", "NEWT")

# ACME's fixture for each endpoint the synthetic company does not cover.
_FIXTURES = {
    "estimates-annual": "fmp/analyst-estimates.annual.ACME.json",
    "profile": "fmp/profile.ACME.json",
    "quote": "fmp/quote.ACME.json",
    "price-history": "fmp/historical-price-eod-full.ACME.json",
    "peers": "fmp/stock-peers.ACME.json",
    "splits": "fmp/splits.ACME.json",
    "summary": "gurufocus/summary.ACME.json",
    "keyratios": "gurufocus/keyratios.ACME.json",
}
# Revenue step in $ m a year and operating margin in %, where the synthetic company's differ.
_SHAPES = {"MILD": (30, 20), "NEWT": (10, -10)}


def listing(symbol: str, market_cap: float, **fields: Any) -> dict[str, Any]:
    """A screener row for an admissible NASDAQ industrial, with ``fields`` changed."""
    return {
        "symbol": symbol,
        "companyName": f"{symbol.capitalize()} Corp",
        "marketCap": market_cap,
        "sector": "Industrials",
        "industry": "Specialty Industrial Machinery",
        "exchangeShortName": "NASDAQ",
        "country": "US",
        "isEtf": False,
        "isFund": False,
        "isActivelyTrading": True,
        **fields,
    }


SCREENER = [
    listing("ACME", 5 * B),
    listing("FIRB", 4 * B, sector="Financial Services", industry="Banks - Regional"),
    listing("AXLE", 12 * B),
    listing("TINY", 1 * B),
    listing("MILD", 3 * B),
    listing("NEWT", 2.5 * B, industry="Electrical Equipment & Parts"),
]


def serve_universe(router: Router) -> None:
    """Serve the screener and every admitted company's answers."""
    router.bodies["screener"] = json.dumps(SCREENER).encode()
    for symbol in ADMITTED:
        for endpoint, body in company(symbol).items():
            router.symbol_bodies[(endpoint, symbol)] = body


def company(symbol: str) -> dict[str, bytes]:
    """The answers for ``symbol`` by endpoint."""
    payloads = {**bodies(), "estimates-quarter": estimates_quarter()}
    if symbol in _SHAPES:
        payloads["income-annual"] = reshaped(payloads["income-annual"], *_SHAPES[symbol])
    answers = {endpoint: json.dumps(payload) for endpoint, payload in payloads.items()}
    for endpoint, fixture in _FIXTURES.items():
        answers[endpoint] = (FIXTURES / fixture).read_text()
    return {endpoint: text.replace("ACME", symbol).encode() for endpoint, text in answers.items()}


def reshaped(rows: Payload, step: int, margin_pct: int) -> Payload:
    """The synthetic annual income statements with revenue $1,000 m in 2014, up ``step`` $ m a
    year, at an operating margin of ``margin_pct`` %; net income is three quarters of it."""
    shaped = []
    for row in rows:
        revenue = (1000 + step * (int(row["fiscalYear"]) - 2014)) * M
        operating = revenue * margin_pct // 100
        net = operating * 3 // 4
        shaped.append(
            {
                **row,
                "revenue": revenue,
                "operatingIncome": operating,
                "netIncome": net,
                "epsDiluted": net / (100 * M),
            }
        )
    return shaped
