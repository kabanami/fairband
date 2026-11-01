"""The universe deciles a full refresh saves (spec 6.6, "Deciles across refreshes").

``deciles_for_universe`` builds each symbol's fiscal-year series from the stored annual statements
(``series_for``) and ranks them with ``compute_deciles``. A symbol with no annual income statement
stored has an empty series and contributes nothing; ``compute_deciles`` leaves out, in turn, a
series it cannot rank (a data gap, a Start-up, no measurable growth, no operating margin).
"""

import sqlite3
from collections.abc import Sequence

from fairband.engine.classifier import Deciles, compute_deciles
from fairband.refresh.inputs_statements import series_for


def deciles_for_universe(
    conn: sqlite3.Connection, symbols: Sequence[str], refresh_id: int
) -> Deciles:
    """The growth and margin-slope deciles of ``symbols``, citing ``refresh_id``."""
    series = {symbol: series_for(conn, symbol) for symbol in symbols}
    return compute_deciles({s: years for s, years in series.items() if years}, refresh_id)
