"""A moat table for the tests: the classes a test names, in place of the packaged file, whose 1,558
real tickers no test loads (spec 2026-11-19 8.1, 8.4)."""

from collections.abc import Mapping
from datetime import date

from fairband.policy import Moat
from fairband.policy.moat import MoatEntry, MoatTable


def moat_table(
    classes: Mapping[str, Moat],
    *,
    version: str = "fairband-moat-v1",
    judged: date = date(2026, 11, 19),
) -> MoatTable:
    """A table of ``version`` holding each of ``classes`` as the rule's entry, judged on
    ``judged``, the day the table is cut too."""
    entries = {symbol: MoatEntry(symbol, moat, judged, "rule") for symbol, moat in classes.items()}
    return MoatTable(version, judged, "the tests' companies", "docs/method.md 4.9a", entries)
