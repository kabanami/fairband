"""The currency of a record's money figure (spec 2026-11-15 9.1; ``method.md`` 16.2).

A finding and a guidance record may name the currency the company states a money figure in, a
figure whose unit is one of ``MONEY_UNITS``: three capital letters, checked for their form and not
against a list (``check_currency``), stored as given, also when it is the reporting currency. A
record that names none is in the company's reporting currency, as every record before it.

``reporting_currency`` is that currency, the one every reader outside a report's Appendix A labels
such a record with: the currency of the company's latest snapshot as its money reads
(``engine.types.money_of``), USD where the company has no snapshot, so a snapshot refused before
its currency was read says USD. ``currency_of`` is the currency a read answers for a figure: the
stored code, else the reporting currency; ``None`` for a figure that is not money.
"""

import re
import sqlite3

from fairband.engine.types import money_of
from fairband.policy.settings import exchange_symbol
from fairband.store.snapshots import latest_snapshot

MONEY_UNITS: frozenset[str] = frozenset({"currency", "per-share"})
_CODE = re.compile(r"[A-Z]{3}")


def check_currency(currency: str | None, unit: str | None) -> None:
    """Refuse a ``currency`` that is not three capital letters, then one on a figure of ``unit``
    that is not money, with the sentence the writer can act on; nothing to check without one."""
    if currency is None:
        return
    if _CODE.fullmatch(currency) is None:
        raise ValueError(f"a currency is three capital letters, not {currency!r}")
    if unit not in MONEY_UNITS:
        raise ValueError("a currency goes with a money figure")


def reporting_currency(conn: sqlite3.Connection, symbol: str) -> str:
    """The company's reporting currency: its latest snapshot's, as ``money_of`` reads it; USD with
    no snapshot."""
    snapshot = latest_snapshot(conn, exchange_symbol(symbol))
    return "USD" if snapshot is None else money_of(snapshot.result)[1]


def currency_of(stored: str | None, unit: str | None, reporting: str) -> str | None:
    """The currency a figure of ``unit`` is in: for a money figure the ``stored`` code, else
    ``reporting``; ``None`` for a figure that is not money."""
    if unit not in MONEY_UNITS:
        return None
    return reporting if stored is None else stored
