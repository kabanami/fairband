"""The script that drafts the moat table, ``scripts/build_moat_table.py`` (spec 2026-11-19 8.1,
8.2), loaded from its path: the log of the decision document's 6.7, the first version and a new
one, the yearly read, the TOML it writes, the revenue it reads from a snapshot, and its three
commands on a small database of two companies, opened read-only.

The database: HIGH, with eleven fiscal years of synthetic statements (revenue $1,000 m, a gross
margin of 50%, operating income $400 m, an invested capital of $1,000 m) and the Mature Growth test
company's snapshot; BARE, with no statement, no industry and no sector, its snapshot refused
"no moat class"; the universe of a full refresh started on 18 Nov 2026."""

import importlib.util
import json
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from support.engine_companies import fx_inputs, mature_growth_inputs, universe_deciles
from support.payloads import store_payloads

from fairband.engine.roic import aggregate_roic
from fairband.engine.route import CompanyInputs, refusal_result, value_company
from fairband.policy import load_policy
from fairband.policy.moat import MoatEntry, MoatTable, load_moat_table
from fairband.policy.moat_rule import MoatFacts, ReturnYear
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.policy.tax import load_tax_table
from fairband.refresh.inputs import build_inputs
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.db import connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh, latest_deciles
from fairband.store.settings import effective_policy
from fairband.store.snapshots import insert_snapshot
from fairband.store.vendor import record_response

_ROOT = Path(__file__).parents[2]
_SCRIPT = _ROOT / "scripts" / "build_moat_table.py"
DECISION = _ROOT / "docs" / "gurufocus-removal.md"
_JUDGED = date(2026, 11, 19)
_CUT = date(2026, 11, 25)
_V1 = "fairband-moat-v1"
_UNIVERSE = "the universe of the full refresh of 2026-11-18, 1,558 companies"
_RULE = "docs/method.md 4.9a"
_TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
_STARTED = datetime(2026, 11, 18, 17, 0, tzinfo=UTC)
M = 1e6


def _script() -> ModuleType:
    """``scripts/build_moat_table.py``, which is not in a package, loaded from its path."""
    spec = importlib.util.spec_from_file_location("build_moat_table", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()


def test_parse_log_reads_the_decision_document() -> None:
    corrections, kept = script.parse_log(DECISION.read_text(encoding="utf-8"))
    assert len(corrections) == 74 and len(kept) == 15 and "BF.B" in kept
    assert Counter((c.rule_class, c.moat) for c in corrections.values()) == {
        ("Wide", "None"): 5,
        ("Wide", "Narrow"): 28,
        ("Narrow", "Wide"): 25,
        ("Narrow", "None"): 1,
        ("None", "Narrow"): 15,
    }
    smci = corrections["SMCI"]
    assert (smci.symbol, smci.rule_class, smci.moat) == ("SMCI", "Wide", "None")
    assert smci.reason.startswith("It assembles servers from other companies' parts, and rivals")
    assert smci.reason.endswith("so it has no pricing power.")
    assert smci.decided_by == "the founder"
    bfb = kept["BF.B"]
    assert (bfb.symbol, bfb.moat) == ("BF.B", "Narrow")
    assert bfb.note.startswith("A strong spirits brand, but it is in Decline")
    assert bfb.decided_by == "the founder, on Claude's proposal"
    assert kept["SONY"].moat == "Wide" and kept["APPN"].moat == "None"


_HEAD = """\
# A decision

### 6.6 The draft

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| EARLY | Early Corp | Before the log. | nobody |

### 6.7 The corrections by hand: the log

**The classes changed.**

"""
_BARE = """\
*From Narrow to None (1):*

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| BARE | Bare Corp | It sells what a rival sells. | the founder |

"""
_OMC = """\
*From Wide to Narrow ({count}):*

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| OMC | Omnicom Group Inc. | An agency. | the founder, on Claude's proposal |

"""
_TAIL = """\
**Questioned and kept as the rule has them.**

| Ticker | Company | Class | Why it stays | Decided by |
|---|---|---|---|---|
| HIGH | High Corp | Wide | Its returns are high. | Claude, after the closer look |

**What the corrected table gives.**

| | Wide | Narrow | None |
|---|---|---|---|
| The draft | 1 | 1 | 1 |

### 6.8 What is open

| Ticker | Company | Why | Decided by |
|---|---|---|---|
| LATER | Later Corp | After the log. | nobody |
"""


def _log(*tables: str) -> str:
    return _HEAD + "".join(tables) + _TAIL


def test_parse_log_reads_the_section_alone_and_refuses_a_table_its_heading_miscounts() -> None:
    corrections, kept = script.parse_log(_log(_BARE, _OMC.format(count=1)))
    assert list(corrections) == ["BARE", "OMC"] and list(kept) == ["HIGH"]
    assert corrections["OMC"] == script.Correction(
        "OMC", "Wide", "Narrow", "An agency.", "the founder, on Claude's proposal"
    )
    assert kept["HIGH"] == script.Kept(
        "HIGH", "Wide", "Its returns are high.", "Claude, after the closer look"
    )
    with pytest.raises(SystemExit, match=r"From Wide to Narrow \(2\):\* heads a table of 1$"):
        script.parse_log(_log(_BARE, _OMC.format(count=2)))
    with pytest.raises(SystemExit, match="BARE twice"):
        script.parse_log(_log(_BARE, _BARE.replace("Narrow to None", "Wide to None")))
    with pytest.raises(SystemExit, match="no section 6.7"):
        script.parse_log("# A decision\n\n### 6.6 The draft\n")


def _logged_classes(
    corrections: dict[str, Any], kept: dict[str, Any], **changes: str
) -> dict[str, Any]:
    """The rule's class of each company of the log as the log has it, AAPL's Wide, and
    ``changes``."""
    rule = {s: c.rule_class for s, c in corrections.items()} | {s: k.moat for s, k in kept.items()}
    return {"AAPL": "Wide", **rule, **changes}


def test_first_version_applies_the_log_and_refuses_one_the_rule_does_not_bear_out() -> None:
    corrections, kept = script.parse_log(DECISION.read_text(encoding="utf-8"))
    classes = _logged_classes(corrections, kept)
    table = script.first_version(classes, corrections, kept, _JUDGED, _V1, _CUT, _UNIVERSE)
    assert (table.version, table.date, table.universe, table.rule) == (_V1, _CUT, _UNIVERSE, _RULE)
    assert list(table.entries) == sorted(classes) and len(table.entries) == 90
    assert table.entries["AAPL"] == MoatEntry("AAPL", "Wide", _JUDGED, "rule")
    smci = corrections["SMCI"]
    assert table.entries["SMCI"] == MoatEntry(
        "SMCI", "None", _JUDGED, "correction", "Wide", smci.reason, "the founder"
    )
    sony = kept["SONY"]
    assert table.entries["SONY"] == MoatEntry(
        "SONY", "Wide", _JUDGED, "rule", decided_by=sony.decided_by, note=sony.note
    )
    entries = table.entries.values()
    assert Counter(e.source for e in entries) == {"rule": 16, "correction": 74}
    assert sum(e.note is not None for e in entries) == 15

    # the log corrects a class the rule does not give, keeps one it does not give, or names a
    # company the universe does not hold: each is named, all in one refusal
    wrong = _logged_classes(corrections, kept, SMCI="Narrow", **{"BF.B": "Wide"})
    with pytest.raises(SystemExit) as refused:
        script.first_version(wrong, corrections, kept, _JUDGED, _V1, _CUT, _UNIVERSE)
    assert "SMCI: the log corrects the rule's Wide; the rule gives Narrow" in str(refused.value)
    assert "BF.B: the log keeps the rule's Narrow; the rule gives Wide" in str(refused.value)
    without = {s: c for s, c in classes.items() if s not in ("TTMI", "SONY")}
    with pytest.raises(SystemExit) as missing:
        script.first_version(without, corrections, kept, _JUDGED, _V1, _CUT, _UNIVERSE)
    assert "SONY: the log names it; the universe does not hold it" in str(missing.value)
    assert "TTMI: the log names it; the universe does not hold it" in str(missing.value)


def _current() -> MoatTable:
    """A version of 25 Nov 2026: AAPL the rule's Wide, SMCI corrected from the rule's Wide,
    SONY the rule's Wide questioned and kept, GONE the rule's Narrow."""
    entries = {
        "SMCI": MoatEntry("SMCI", "None", _JUDGED, "correction", "Wide", "Servers.", "the founder"),
        "AAPL": MoatEntry("AAPL", "Wide", _JUDGED, "rule"),
        "SONY": MoatEntry("SONY", "Wide", _JUDGED, "rule", decided_by="Claude", note="Kept."),
        "GONE": MoatEntry("GONE", "Narrow", _JUDGED, "rule"),
    }
    return MoatTable(_V1, _CUT, _UNIVERSE, _RULE, entries)


def test_new_version_and_the_yearly_read() -> None:
    current = _current()
    # today the rule gives AAPL and SMCI Narrow; GONE left the universe; NEWA and NEWB entered
    drafted = {"AAPL": "Narrow", "SMCI": "Narrow", "SONY": "Wide", "NEWA": "Wide", "NEWB": "None"}
    today = date(2027, 11, 20)
    new = script.new_version(current, drafted, today, "fairband-moat-v2", "the universe of now")
    assert (new.version, new.date, new.universe, new.rule) == (
        "fairband-moat-v2",
        today,
        "the universe of now",
        _RULE,
    )
    assert list(new.entries) == ["AAPL", "GONE", "NEWA", "NEWB", "SMCI", "SONY"]
    for symbol, entry in current.entries.items():
        assert new.entries[symbol] == entry  # kept as it is, whatever the rule gives today
    assert new.entries["NEWA"] == MoatEntry("NEWA", "Wide", today, "rule")
    assert new.entries["NEWB"] == MoatEntry("NEWB", "None", today, "rule")

    # the rule's entries alone: SMCI is a correction, and GONE is not drafted today
    assert script.yearly_read(current, drafted) == [("AAPL", "Wide", "Narrow")]
    assert script.yearly_read(new, drafted) == [("AAPL", "Wide", "Narrow")]


def test_a_reason_round_trips(tmp_path: Path) -> None:
    reason = 'Its "moat" is a back\\slash claim,\nwritten on two lines; a résumé of Nestlé\'s.'
    entries = {
        "SMCI": MoatEntry("SMCI", "None", _JUDGED, "correction", "Wide", reason, "the founder"),
        "BF.B": MoatEntry(
            "BF.B", "Narrow", _JUDGED, "rule", decided_by="the «founder»", note=reason
        ),
        "AAPL": MoatEntry("AAPL", "Wide", _CUT, "rule"),
    }
    table = MoatTable(_V1, _CUT, 'the "universe"', _RULE, entries)
    text = script.render(table)
    assert "résumé of Nestlé's" in text and '\\"moat\\"' in text and "back\\\\slash" in text
    path = tmp_path / "moat.toml"
    path.write_text(text, encoding="utf-8")
    read = load_moat_table(path)
    assert read == table
    assert list(read.entries) == ["AAPL", "BF.B", "SMCI"]
    assert read.entries["SMCI"].reason == reason and read.entries["BF.B"].note == reason


def _no_assembly() -> CompanyInputs:
    raise AssertionError("assembly is read for a snapshot refused 'no moat class' alone")


def _trailing_revenue(inputs: CompanyInputs) -> float:
    assert inputs.trailing is not None and inputs.trailing.revenue is not None
    return inputs.trailing.revenue


def test_the_snapshot_s_revenue() -> None:
    policy, deciles = load_policy(), universe_deciles()
    usd_inputs, sek_inputs = mature_growth_inputs(), fx_inputs()  # SEK at 8.0 a dollar
    # a valued row: its revenue_ttm input, at its fx_rate input where it has one
    usd = value_company(usd_inputs, deciles, policy, _TODAY)
    sek = value_company(sek_inputs, deciles, policy, _TODAY)
    assert script.snapshot_revenue(usd, _no_assembly) == _trailing_revenue(usd_inputs)
    assert script.snapshot_revenue(sek, _no_assembly) == _trailing_revenue(sek_inputs) / 8.0
    # a row refused before its route for another reason cites no revenue: none
    refused = refusal_result("NOFS", "no financial statements", policy, _TODAY)
    assert script.snapshot_revenue(refused, _no_assembly) is None
    # a row refused "no moat class": assembly's trailing revenue at assembly's rate
    entrant = refusal_result("NEWCO", "no moat class", policy, _TODAY)
    assert script.snapshot_revenue(entrant, lambda: usd_inputs) == _trailing_revenue(usd_inputs)
    assert script.snapshot_revenue(entrant, lambda: sek_inputs) == (
        _trailing_revenue(sek_inputs) / 8.0
    )
    assert script.snapshot_revenue(entrant, lambda: replace(sek_inputs, trailing=None)) is None


def _company(symbol: str, refresh_id: int, industry: str | None, sector: str | None) -> CompanyRow:
    return CompanyRow(
        symbol=symbol,
        refresh_id=refresh_id,
        name=f"{symbol.capitalize()} Corp",
        exchange="NASDAQ",
        sector=sector,
        industry=industry,
        country="US",
        currency="USD",
        is_adr=False,
        cap_band="mid",
        market_cap=Decimal(4_000 * M),
        eligible=True,
        exclusion_reason=None,
        observed_at=_STARTED,
    )


def _statement(symbol: str, year: int, **lines: float) -> dict[str, Any]:
    return {
        "date": f"{year}-12-31",
        "symbol": symbol,
        "reportedCurrency": "USD",
        "fiscalYear": str(year),
        "period": "FY",
        **lines,
    }


def _income(symbol: str, gross: float) -> list[dict[str, Any]]:
    lines = {"revenue": 1_000 * M, "grossProfit": gross * M, "operatingIncome": 400 * M}
    return [_statement(symbol, y, **lines) for y in range(2015, 2026)]


def _balance(symbol: str) -> list[dict[str, Any]]:
    lines = {
        "totalCurrentAssets": 500 * M,
        "cashAndCashEquivalents": 100 * M,
        "totalCurrentLiabilities": 200 * M,
        "propertyPlantEquipmentNet": 800 * M,
    }
    return [_statement(symbol, y, **lines) for y in range(2015, 2026)]


def _answer(
    conn: sqlite3.Connection, symbol: str, day: int, payload: object, error: str | None
) -> None:
    """An answer to the annual income statements of ``symbol``, received on ``day`` Nov 2026."""
    at = datetime(2026, 11, day, tzinfo=UTC)
    text = json.dumps(payload)
    record_response(conn, "fmp", "income-annual", {"symbol": symbol}, symbol, 200, text, error, at)


def _database(path: Path) -> None:
    """The two companies. HIGH's income statements are answered twice more, an empty answer and,
    the newest, one with an error, both passed over; BARE's four answers hold statements in the
    oldest only, which its three newest leave unread."""
    conn = connect(path)
    migrate(conn)
    policy = load_policy()
    refresh = create_refresh(
        conn, "full", None, policy.version, "1.7", _STARTED, EMPTY_SETTINGS_HASH
    )
    finish_refresh(conn, refresh, "done", _STARTED)
    high, bare = (
        _company("HIGH", refresh, "Widgets", "Industrials"),
        _company("BARE", refresh, None, None),
    )
    insert_companies(conn, [high, bare])
    statements = {"income-annual": _income("HIGH", 500), "balance-annual": _balance("HIGH")}
    store_payloads(conn, "HIGH", statements, _STARTED)
    _answer(conn, "HIGH", 19, [], None)
    _answer(conn, "HIGH", 20, _income("HIGH", 100), "a body the normalizer refused")
    _answer(conn, "BARE", 1, _income("BARE", 500), None)
    for day in (2, 3, 4):
        _answer(conn, "BARE", day, [], None)
    valued = value_company(mature_growth_inputs(), universe_deciles(), policy, _TODAY)
    insert_snapshot(conn, replace(valued, symbol="HIGH"), refresh, clock=lambda: _STARTED)
    entrant = refusal_result("BARE", "no moat class", policy, _TODAY)
    insert_snapshot(conn, entrant, refresh, clock=lambda: _STARTED)
    conn.close()


def test_read_facts_on_a_small_database(tmp_path: Path) -> None:
    path = tmp_path / "fairband.db"
    _database(path)
    with closing(script.connect_read_only(path)) as conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("CREATE TABLE written (a)")
        facts = {f.symbol: f for f in script.read_facts(conn)}
        policy, tax, deciles = effective_policy(conn), load_tax_table(), latest_deciles(conn)
        inputs = build_inputs(conn, "HIGH", policy, tax, _TODAY, deciles)
    assert list(facts) == ["BARE", "HIGH"]
    high = facts["HIGH"]
    kept = aggregate_roic(inputs.capital_years).by_year
    assert high.years == tuple(ReturnYear(y.nopat, y.average_capital) for y in kept)
    assert len(high.years) == 10 and {y.capital for y in high.years} == {1_000 * M}
    assert (high.industry, high.sector, high.phase) == ("Widgets", "Industrials", "Mature Growth")
    assert high.revenue_usd == _trailing_revenue(mature_growth_inputs())
    assert high.fiscal_revenues == (1_000 * M,) * 11
    assert high.gross_margins == (0.5,) * 10
    assert facts["BARE"] == MoatFacts("BARE", "", "", None, (), None, (), ())


def test_the_three_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "fairband.db"
    _database(db)
    universe = "the universe of the full refresh of 2026-11-18, 2 companies"
    today = date.today()
    log = tmp_path / "decision.md"
    first = tmp_path / "first.toml"
    args = ["first", "--database", str(db), "--log", str(log), "--judged", "2026-11-19"]
    log.write_text(_log(_BARE, _OMC.format(count=1)), encoding="utf-8")
    with pytest.raises(SystemExit, match="OMC: the log names it; the universe does not hold it"):
        script.main([*args, "--out", str(first)])
    assert not first.exists()

    # HIGH is the rule's Wide, by the return route; BARE, with no return year, its Narrow
    log.write_text(_log(_BARE), encoding="utf-8")
    script.main([*args, "--out", str(first)])
    table = load_moat_table(first)
    assert (table.version, table.universe, table.rule) == (_V1, universe, _RULE)
    assert table.date in (today, date.today())
    assert table.entries["HIGH"] == MoatEntry(
        "HIGH",
        "Wide",
        _JUDGED,
        "rule",
        decided_by="Claude, after the closer look",
        note="Its returns are high.",
    )
    assert table.entries["BARE"] == MoatEntry(
        "BARE",
        "None",
        _JUDGED,
        "correction",
        "Narrow",
        "It sells what a rival sells.",
        "the founder",
    )
    assert "2 companies" in capsys.readouterr().out

    # a new version keeps the current file's entries and drafts BARE, which it lacks, today
    entries = {
        "HIGH": MoatEntry("HIGH", "Narrow", _JUDGED, "rule"),
        "GONE": MoatEntry("GONE", "Wide", _JUDGED, "rule"),
    }
    current = tmp_path / "current.toml"
    current.write_text(script.render(MoatTable(_V1, _CUT, _UNIVERSE, _RULE, entries)), "utf-8")
    new = tmp_path / "new.toml"
    v2 = ["--version", "fairband-moat-v2", "--out", str(new)]
    script.main(["new", "--database", str(db), "--current", str(current), *v2])
    table = load_moat_table(new)
    assert (table.version, table.universe) == ("fairband-moat-v2", universe)
    assert list(table.entries) == ["BARE", "GONE", "HIGH"]
    assert (table.entries["HIGH"], table.entries["GONE"]) == (entries["HIGH"], entries["GONE"])
    bare = table.entries["BARE"]
    assert (bare.moat, bare.source, bare.note) == ("Narrow", "rule", None)
    assert bare.judged in (today, date.today())
    assert "BARE Narrow" in capsys.readouterr().out

    # the yearly read lists HIGH, which the rule gives Wide today, and GONE, which left
    script.main(["read", "--database", str(db), "--current", str(current)])
    out = capsys.readouterr().out
    assert "HIGH: Narrow in the file, Wide by the rule" in out
    assert "GONE: in the file, not in the universe" in out
