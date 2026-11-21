"""Fairband's moat table: one class, Wide, Narrow or None, for every company (spec 2026-11-19 8.1).

The packaged file, ``moat-classes-v1.toml``, beside the tax table, holds the newest version only;
git holds the history. Its ``[meta]`` names the version (``fairband-moat-v1``), the day the version
was cut, the universe it covers and the rule that drafted it (``docs/method.md`` 4.9a). Each
``[[classes]]`` entry holds a company's symbol, its class, the day it was judged and its source:
``rule``, the rule's class, or ``correction``. A correction holds the class the rule gave
(``rule_class``), the ``reason`` and who ``decided_by``, word for word from the log of the decision
document's 6.7; a rule entry questioned and kept holds a ``note`` and ``decided_by``.

The reader refuses a file with no entry, a symbol twice, a class outside the three, a source other
than ``rule`` or ``correction``, a correction without its three fields, a rule entry with
``rule_class`` or ``reason``, a ``judged`` that is not a TOML date, and a ``[meta]`` missing a
field, which it names. A file with no entry is refused, rows under a misspelled header
(``[[class]]``) included, because a refresh deletes each file row whose company the file no
longer holds (spec 8.4). A reason or a note is any TOML string.
"""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any, Literal, cast

from fairband.policy import Moat

MOAT_FILE = "moat-classes-v1.toml"

_CLASSES: tuple[Moat, ...] = ("Wide", "Narrow", "None")
_SOURCES = ("rule", "correction")
_META = ("version", "date", "universe", "rule")
_CORRECTION = ("rule_class", "reason", "decided_by")
_NOT_RULE = ("rule_class", "reason")


@dataclass(frozen=True)
class MoatEntry:
    """One company's class. ``rule_class``, ``reason`` and ``decided_by`` are a correction's;
    ``note`` and ``decided_by`` a questioned and kept entry's."""

    symbol: str
    moat: Moat
    judged: date
    source: Literal["rule", "correction"]
    rule_class: Moat | None = None
    reason: str | None = None
    decided_by: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class MoatTable:
    """One version of the table: its ``[meta]``, and its entries by symbol in the file's order."""

    version: str
    date: date
    universe: str
    rule: str
    entries: Mapping[str, MoatEntry]


def load_moat_table(path: Path | None = None) -> MoatTable:
    """Parse the moat table (default: the packaged ``MOAT_FILE``)."""
    if path is None:
        data = resources.files("fairband.policy").joinpath(MOAT_FILE).read_bytes()
    else:
        data = path.read_bytes()
    raw = tomllib.loads(data.decode("utf-8"))
    meta = raw.get("meta", {})
    if not isinstance(meta, dict):
        raise TypeError("moat table: [meta] must be a table")
    for field in _META:
        if field not in meta:
            raise ValueError(f"moat table: [meta] has no {field}")
    version, universe, rule = (
        _text(meta[field], f"meta.{field}") for field in ("version", "universe", "rule")
    )
    cut = _date(meta["date"], "meta.date")
    classes = raw.get("classes", [])
    if not isinstance(classes, list):
        raise TypeError("moat table: [[classes]] must be an array of tables")
    if not classes:
        raise ValueError("moat table: the file has no [[classes]] entry")
    entries: dict[str, MoatEntry] = {}
    for item in classes:
        entry = _entry(item)
        if entry.symbol in entries:
            raise ValueError(f"moat table: {entry.symbol} appears twice")
        entries[entry.symbol] = entry
    return MoatTable(version, cut, universe, rule, entries)


def _entry(item: Any) -> MoatEntry:
    if not isinstance(item, dict):
        raise TypeError(f"moat table: a [[classes]] entry is not a table: {item!r}")
    if "symbol" not in item:
        raise ValueError(f"moat table: a [[classes]] entry has no symbol: {item!r}")
    symbol = item["symbol"]
    if not isinstance(symbol, str):
        raise TypeError(f"moat table: a [[classes]] entry's symbol must be a string: {item!r}")
    for field in ("class", "judged", "source"):
        if field not in item:
            raise ValueError(f"moat table: {symbol} has no {field}")
    moat = _class(item["class"], f"{symbol} class")
    judged = _date(item["judged"], f"{symbol} judged")
    source = item["source"]
    if source not in _SOURCES:
        raise ValueError(f"moat table: {symbol} source {source!r} is not rule or correction")
    if source == "correction":
        for field in _CORRECTION:
            if field not in item:
                raise ValueError(f"moat table: {symbol} is a correction without {field}")
    else:
        for field in _NOT_RULE:
            if field in item:
                raise ValueError(f"moat table: {symbol} is the rule's class and holds {field}")
    rule_class = item.get("rule_class")
    return MoatEntry(
        symbol,
        moat,
        judged,
        cast(Literal["rule", "correction"], source),
        rule_class=None if rule_class is None else _class(rule_class, f"{symbol} rule_class"),
        reason=_optional_text(item, "reason", symbol),
        decided_by=_optional_text(item, "decided_by", symbol),
        note=_optional_text(item, "note", symbol),
    )


def _class(x: Any, name: str) -> Moat:
    if x not in _CLASSES:
        raise ValueError(f"moat table: {name} {x!r} is not Wide, Narrow or None")
    return cast(Moat, x)


def _date(x: Any, name: str) -> date:
    """A TOML local date; a date-time, which Python's ``datetime`` subclasses, is not one."""
    if type(x) is not date:
        raise TypeError(f"moat table: {name} {x!r} is not a date")
    return x


def _text(x: Any, name: str) -> str:
    if not isinstance(x, str):
        raise TypeError(f"moat table: {name} must be a string")
    return x


def _optional_text(item: dict[str, Any], field: str, symbol: str) -> str | None:
    return None if field not in item else _text(item[field], f"{symbol} {field}")
