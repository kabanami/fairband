"""The references a report cites (spec 2026-11-06 Tier 2, 13.2): one builder per form, so the
reads that hand a ref beside each figure and the resolver that reads it back agree on its text.

- ``fact:<symbol>/<line>/<period>``: a stored statement line as the engine reads it, ``<line>``
  the engine's field name (``fairband.reports.tables.LINES`` for a fiscal year, the trailing
  figures' fields for ``ttm``) and ``<period>`` the fiscal year as text or ``ttm``;
- ``table:<symbol>/<table>/<row>/<period>``: a cell of the financial tables (13.5);
- ``estimate:<symbol>/<period>/<field>``: a stored consensus figure, ``<period>`` the fiscal year
  (``2026``) or the quarter (``2026-Q4``) and ``<field>`` the engine's name (``eps``,
  ``net_income``, ``analysts_eps``);
- ``close:<symbol>/<date>``: a stored daily close;
- ``peer:<symbol>/<peer>/<field>``: a figure of one of the company's mature peers as assembly
  reads it (``market_cap``, ``margin``, ``margin_years``, ``sales_to_capital``, ``roic``).

The last three name the reads' figures that no form of 13.2 names; a ``response:`` ref would need
the payload's own layout.
"""


def fact_ref(symbol: str, line: str, period: str) -> str:
    return f"fact:{symbol}/{line}/{period}"


def table_ref(symbol: str, table: str, row: str, period: str) -> str:
    return f"table:{symbol}/{table}/{row}/{period}"


def estimate_ref(symbol: str, period: str, field: str) -> str:
    return f"estimate:{symbol}/{period}/{field}"


def close_ref(symbol: str, day: str) -> str:
    return f"close:{symbol}/{day}"


def peer_ref(symbol: str, peer: str, field: str) -> str:
    return f"peer:{symbol}/{peer}/{field}"
