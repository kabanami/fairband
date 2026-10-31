"""FMP payloads to store rows: the public entry to the FMP normalizers.

The statement normalizers live in ``normalize_fmp_statements`` and the observation, close and
screener normalizers in ``normalize_fmp_observations``; each module's docstring states its storage
rules. Every normalizer takes the parsed payload and the provenance (``symbol`` in the exchange
form, ``response_id``, ``observed_at``, ``entered_at``) and never raises on vendor data: a payload
that is not a list of objects gives no rows, and a row without a parseable ``date`` is skipped and
records nothing. Numbers parse to ``Decimal`` from a JSON number or a numeric string
(``Decimal(str(x))``); a boolean, a word, NaN or an infinity is not a number.
"""

from fairband.vendors.normalize_fmp_observations import (
    ScreenerRow,
    earnings_observations,
    estimate_observations,
    price_closes,
    profile_observations,
    quote_observations,
    screener_rows,
    value_as_date,
)
from fairband.vendors.normalize_fmp_statements import as_reported_balance_facts, statement_facts

__all__ = [
    "ScreenerRow",
    "as_reported_balance_facts",
    "earnings_observations",
    "estimate_observations",
    "price_closes",
    "profile_observations",
    "quote_observations",
    "screener_rows",
    "statement_facts",
    "value_as_date",
]
