"""The moat table's reader (spec 2026-11-19 8.1) on files under ``tmp_path`` in the spec's layout:
a ``[meta]`` and one ``[[classes]]`` an entry."""

import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pytest

from fairband.policy.moat import MoatEntry, load_moat_table

Fields = Mapping[str, str | date]

_META: Fields = {
    "version": "fairband-moat-v1",
    "date": date(2026, 11, 25),
    "universe": "the universe of the full refresh of 2026-11-18, 1,558 companies",
    "rule": "docs/method.md 4.9a",
}
_JUDGED = date(2026, 11, 19)
_AAPL: Fields = {"symbol": "AAPL", "class": "Wide", "judged": _JUDGED, "source": "rule"}
# A reason may hold a quotation mark, a backslash, an accented letter and a line break.
_SMCI_REASON = (
    "It assembles servers from other companies' parts, and rivals sell the same.\n"
    'Its "moat" is a c\\o-design claim; résumé of the log.'
)
_SMCI: Fields = {
    "symbol": "SMCI",
    "class": "None",
    "judged": _JUDGED,
    "source": "correction",
    "rule_class": "Wide",
    "reason": _SMCI_REASON,
    "decided_by": "the founder",
}
_SONY: Fields = {
    "symbol": "SONY",
    "class": "Wide",
    "judged": _JUDGED,
    "source": "rule",
    "note": "First doubted as a mixed group.",
    "decided_by": "Claude, after the closer look the founder asked for",
}


def _value(x: str | date) -> str:
    """A TOML date as a bare date, a string as a basic string."""
    return x.isoformat() if isinstance(x, date) else json.dumps(x, ensure_ascii=False)


def _file(
    tmp_path: Path, entries: Sequence[Fields], meta: Fields = _META, header: str = "classes"
) -> Path:
    blocks = ["[meta]\n" + "".join(f"{k} = {_value(v)}\n" for k, v in meta.items())]
    for entry in entries:
        blocks.append(f"[[{header}]]\n" + "".join(f"{k} = {_value(v)}\n" for k, v in entry.items()))
    path = tmp_path / "moat.toml"
    path.write_text("\n".join(blocks), encoding="utf-8")
    return path


def _without(entry: Fields, field: str) -> Fields:
    return {k: v for k, v in entry.items() if k != field}


def test_a_file_loads_its_meta_and_its_entries(tmp_path: Path) -> None:
    table = load_moat_table(_file(tmp_path, [_SONY, _AAPL, _SMCI]))
    assert table.version == "fairband-moat-v1"
    assert table.date == date(2026, 11, 25)
    assert table.universe == "the universe of the full refresh of 2026-11-18, 1,558 companies"
    assert table.rule == "docs/method.md 4.9a"
    assert list(table.entries) == ["SONY", "AAPL", "SMCI"]
    assert table.entries["AAPL"] == MoatEntry("AAPL", "Wide", _JUDGED, "rule")


def test_a_correction_and_a_kept_entry(tmp_path: Path) -> None:
    table = load_moat_table(_file(tmp_path, [_AAPL, _SMCI, _SONY]))
    smci, sony = table.entries["SMCI"], table.entries["SONY"]
    assert (smci.moat, smci.source, smci.judged) == ("None", "correction", _JUDGED)
    assert (smci.rule_class, smci.reason, smci.decided_by) == ("Wide", _SMCI_REASON, "the founder")
    assert smci.note is None
    assert (sony.moat, sony.source, sony.rule_class, sony.reason) == ("Wide", "rule", None, None)
    assert sony.note == "First doubted as a mixed group."
    assert sony.decided_by == "Claude, after the closer look the founder asked for"


TWICE = [_AAPL, _SMCI, _AAPL]
MEDIUM = [{**_AAPL, "class": "Medium"}]
NO_REASON = [_without(_SMCI, "reason")]
NO_RULE_CLASS = [_without(_SMCI, "rule_class")]
NO_DECIDED_BY = [_without(_SMCI, "decided_by")]
RULE_WITH_RULE_CLASS = [{**_AAPL, "rule_class": "Narrow"}]
RULE_WITH_REASON = [{**_AAPL, "reason": "A reason the rule's class does not take."}]
GUESS = [{**_AAPL, "source": "guess"}]


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        (TWICE, "AAPL appears twice"),
        (MEDIUM, "AAPL class 'Medium' is not Wide, Narrow or None"),
        (NO_REASON, "SMCI is a correction without reason"),
        (NO_RULE_CLASS, "SMCI is a correction without rule_class"),
        (NO_DECIDED_BY, "SMCI is a correction without decided_by"),
        (RULE_WITH_RULE_CLASS, "AAPL is the rule's class and holds rule_class"),
        (RULE_WITH_REASON, "AAPL is the rule's class and holds reason"),
        (GUESS, "AAPL source 'guess' is not rule or correction"),
    ],
)
def test_a_malformed_file_is_refused(tmp_path: Path, entries: list[Fields], message: str) -> None:
    with pytest.raises(ValueError, match=f"^moat table: {re.escape(message)}$"):
        load_moat_table(_file(tmp_path, entries))


@pytest.mark.parametrize(
    ("entries", "header"),
    [
        pytest.param([], "classes", id="no [[classes]] at all"),
        pytest.param([_AAPL, _SMCI], "class", id="rows under [[class]]"),
    ],
)
def test_a_file_with_no_entry_is_refused(
    tmp_path: Path, entries: list[Fields], header: str
) -> None:
    """A refresh deletes each file row whose company the file no longer holds (spec 8.4), so a
    file emptied, or its rows under a header the reader does not read, would delete them all."""
    path = _file(tmp_path, entries, header=header)
    with pytest.raises(ValueError, match=r"^moat table: the file has no \[\[classes\]\] entry$"):
        load_moat_table(path)


def test_a_judged_that_is_not_a_date_is_refused(tmp_path: Path) -> None:
    path = _file(tmp_path, [{**_AAPL, "judged": "2026-11-19"}])
    with pytest.raises(TypeError, match="^moat table: AAPL judged"):
        load_moat_table(path)


@pytest.mark.parametrize("field", ["version", "date", "universe", "rule"])
def test_a_meta_without_a_field_is_refused_by_name(tmp_path: Path, field: str) -> None:
    path = _file(tmp_path, [_AAPL], meta=_without(_META, field))
    with pytest.raises(ValueError, match=f"^moat table: \\[meta\\] has no {field}$"):
        load_moat_table(path)
