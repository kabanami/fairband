"""The moat table's reader (spec 2026-11-19 8.1) on files under ``tmp_path`` in the spec's layout:
a ``[meta]`` and one ``[[classes]]`` an entry; then the packaged file, read by default, against
the log of the decision document's 6.7."""

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pytest

from fairband.policy.moat import MoatEntry, load_moat_table

DECISION = Path(__file__).parents[2] / "docs" / "gurufocus-removal.md"

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


# The packaged file: refresh 68's 1,558 companies judged on 19 Nov 2026, the rule's draft with the
# log of the decision document's 6.7 applied; each company that entered since, the rule's class
# judged the day of the cut.

_AGENT = "an agent's review, which takes precedence"
_CLAUDE = "Claude, after the closer look the founder asked for"
_ON_PROPOSAL = "the founder, on Claude's proposal"
_CRM_NOTE = (
    "A ROIC of 5% over ten years and 7% over five, after large purchases. Its review of"
    " 2026-11-10 confirmed GuruFocus's Wide before the moat was a standing step of a review."
)
_CUT_UNIVERSE = re.compile(
    r"the universe of the full refresh of (\d{4}-\d{2}-\d{2}), ([\d,]+) companies"
)


def _log() -> dict[str, tuple[str, list[str]]]:
    """Each row of the decision document's 6.7 by its first cell: the heading line above its
    table (a line that opens with ``*``) and its cells."""
    text = DECISION.read_text(encoding="utf-8")
    section = text.split("\n### 6.7 ", 1)[1].split("\n### ", 1)[0]
    rows: dict[str, tuple[str, list[str]]] = {}
    heading = ""
    for line in section.splitlines():
        if line.startswith("*"):
            heading = line
        elif line.startswith("| "):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows[cells[0]] = (heading, cells)
    return rows


def test_refresh_68_s_companies_take_the_corrected_classes() -> None:
    first = [e for e in load_moat_table().entries.values() if e.judged == date(2026, 11, 19)]
    assert len(first) == 1558
    assert Counter(e.moat for e in first) == {"Wide": 162, "Narrow": 1320, "None": 76}
    assert sum(e.source == "correction" for e in first) == 74
    assert sum(e.note is not None for e in first) == 15


def test_every_reason_and_note_is_the_decision_document_s() -> None:
    """A correction's pair is its table's heading, and its reason and decider are its row's
    cells; a kept entry's class, note and decider likewise. The 89 rows of the log are these
    entries, and no other entry names a decider."""
    log = _log()
    entries = load_moat_table().entries.values()
    corrections = [e for e in entries if e.source == "correction"]
    kept = [e for e in entries if e.note is not None]
    for e in corrections:
        heading, cells = log[e.symbol]
        assert heading.startswith(f"*From {e.rule_class} to {e.moat} ("), e.symbol
        assert cells[2:] == [e.reason, e.decided_by], e.symbol
    for e in kept:
        heading, cells = log[e.symbol]
        assert heading.startswith("**Questioned and kept as the rule has them"), e.symbol
        assert (e.source, cells[2:]) == ("rule", [e.moat, e.note, e.decided_by]), e.symbol
    logged = {
        symbol
        for symbol, (heading, _) in log.items()
        if symbol != "Ticker" and heading.startswith(("*From ", "**Questioned"))
    }
    assert len(logged) == 89
    assert {e.symbol for e in [*corrections, *kept]} == logged
    assert {e.symbol for e in entries if e.decided_by is not None} == logged


def test_the_entries_the_spec_names() -> None:
    entries = load_moat_table().entries
    judged = date(2026, 11, 19)
    smci, ttmi, nvo = entries["SMCI"], entries["TTMI"], entries["NVO"]
    assert (smci.moat, smci.judged, smci.source) == ("None", judged, "correction")
    assert (smci.rule_class, smci.decided_by) == ("Wide", "the founder")
    assert smci.reason is not None
    assert smci.reason.startswith(
        "It assembles servers from other companies' parts, and rivals sell the same. "
    )
    assert (ttmi.moat, ttmi.judged, ttmi.source, ttmi.rule_class, ttmi.decided_by) == (
        "None",
        judged,
        "correction",
        "Narrow",
        _AGENT,
    )
    assert (
        ttmi.reason == "An agent's review of 2026-11-11 judged that it has no moat (override 31)."
    )
    assert (nvo.moat, nvo.judged, nvo.source, nvo.rule_class, nvo.decided_by) == (
        "Narrow",
        judged,
        "correction",
        "Wide",
        _AGENT,
    )
    assert nvo.reason is not None
    assert nvo.reason.startswith("An agent's review of 2026-11-11 judged the moat Narrow")
    relx, sony = entries["RELX"], entries["SONY"]
    assert (relx.moat, relx.judged, relx.source, relx.rule_class, relx.decided_by) == (
        "Wide",
        judged,
        "rule",
        None,
        _AGENT,
    )
    assert relx.note is not None
    assert relx.note.startswith("An agent's review of 2026-11-11 judged it Wide (override 45)")
    assert (sony.moat, sony.judged, sony.source, sony.decided_by) == (
        "Wide",
        judged,
        "rule",
        _CLAUDE,
    )
    assert sony.note is not None
    assert sony.note.startswith("First doubted as a mixed group. ")
    # Section 5, point 1: CRM stays Narrow, with the decision document's corrected sentence.
    assert entries["CRM"] == MoatEntry(
        "CRM", "Narrow", judged, "rule", decided_by=_ON_PROPOSAL, note=_CRM_NOTE
    )
    # The spec's example (8.1), and FRVO, the rule's Narrow for fewer than ten years (section 5).
    assert entries["AAPL"] == MoatEntry("AAPL", "Wide", judged, "rule")
    assert entries["FRVO"] == MoatEntry("FRVO", "Narrow", judged, "rule")


def test_the_meta_and_the_later_entries() -> None:
    """The version and the rule are named; the universe is a full refresh's from refresh 68 on,
    and the file holds an entry for each of its companies or more (none is dropped); each company
    that entered since refresh 68 is the rule's class, judged the day of the cut."""
    table = load_moat_table()
    assert (table.version, table.rule) == ("fairband-moat-v1", "docs/method.md 4.9a")
    found = _CUT_UNIVERSE.fullmatch(table.universe)
    assert found is not None, table.universe
    assert date(2026, 11, 18) <= date.fromisoformat(found[1]) <= table.date
    assert len(table.entries) >= int(found[2].replace(",", ""))
    assert table.date > date(2026, 11, 19)
    later = [e for e in table.entries.values() if e.judged != date(2026, 11, 19)]
    assert all(e == MoatEntry(e.symbol, e.moat, table.date, "rule") for e in later)
    assert list(table.entries) == sorted(table.entries)
