"""The stock splits on file (spec 2026-11-09 section 10).

``splits_for`` reads the ``split`` observations back as one ``SplitRow`` a split, oldest first. The
normalizer stores two observations a split, the numerator and the denominator, on the split date
(``split_observations``). Only the rows of the latest usable ``splits`` response are read: FMP's
list at the newest fetch is the whole truth, so a split it no longer lists, withdrawn or re-dated,
is not read though its observations stay on file; without a usable response there is no split. A
date that lacks one of the two, or whose denominator is zero, is skipped. The ratio, numerator ÷
denominator, is the new shares to one old share: 2 for a 2-for-1 split, 0.1 for a 1-for-10 reverse
split.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from fairband.store.observations import observations_for
from fairband.store.vendor import latest_response


@dataclass(frozen=True)
class SplitRow:
    """One split: from ``date`` on, ``numerator`` shares stand where ``denominator`` stood."""

    date: date
    numerator: float
    denominator: float

    @property
    def ratio(self) -> float:
        """The new shares to one old share, numerator ÷ denominator."""
        return self.numerator / self.denominator

    @property
    def word(self) -> str:
        """The split in words: ``2-for-1 split``, ``3-for-2 split``, ``1-for-10 reverse split``."""
        kind = "reverse split" if self.ratio < 1 else "split"
        return f"{_count(self.numerator)}-for-{_count(self.denominator)} {kind}"


def splits_for(conn: sqlite3.Connection, symbol: str) -> tuple[SplitRow, ...]:
    """The splits of the latest usable ``splits`` response for ``symbol``, oldest first."""
    response = latest_response(conn, "fmp", "splits", symbol, {"symbol": symbol})
    if response is None:
        return ()
    fields: dict[date, dict[str, float]] = defaultdict(dict)
    for row in observations_for(conn, symbol, "split"):
        if row.response_id == response.id and row.period is not None and row.value is not None:
            fields[row.period][row.field] = float(row.value)
    out: list[SplitRow] = []
    for when in sorted(fields):
        numerator, denominator = fields[when].get("numerator"), fields[when].get("denominator")
        if numerator is None or denominator is None or denominator == 0:
            continue
        out.append(SplitRow(when, numerator, denominator))
    return tuple(out)


def _count(n: float) -> str:
    """A whole number as an integer (``2``), any other to two decimals with trailing zeros dropped
    (``1.5``, ``1.05``)."""
    return str(int(n)) if n.is_integer() else f"{n:.2f}".rstrip("0").rstrip(".")
