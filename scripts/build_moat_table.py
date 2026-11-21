"""Draft the moat table by the rule and write it (spec 2026-11-19 8.1, 8.2).

    uv run python scripts/build_moat_table.py first --database DB \\
        --log docs/gurufocus-removal.md --judged 2026-11-19 --out TOML
    uv run python scripts/build_moat_table.py new --database DB --current TOML \\
        --version V --out TOML
    uv run python scripts/build_moat_table.py read --database DB --current TOML

Each command opens the database read-only (``mode=ro``), makes no vendor call, values nothing and
writes only its ``--out`` file, which it loads back through ``load_moat_table`` before it reports,
so a file the engine would refuse fails here. It reads what the run of 2026-11-19 read
(``read_facts``) and drafts every company of the universe by the rule
(``fairband.policy.moat_rule``):

- ``first``: the first version, ``fairband-moat-v1``. Each company takes the rule's class, judged
  ``--judged``, and the log of the decision document's 6.7 (``--log``) is applied: its 74
  corrections become ``correction`` entries and its 15 entries questioned and kept carry their
  note. A log entry the rule does not bear out, a correction of a class the rule does not give, a
  kept class it does not give or a company the universe does not hold, refuses the version, every
  one named.
- ``new``: a new version ``--version`` of ``--current``. Every entry of the current file is kept
  as it is, and each company of the universe the file lacks is drafted, judged today; it prints
  those. No entry is dropped.
- ``read``: the yearly read of ``--current``. It prints each ``rule`` entry whose class the rule
  gives differently today, and each entry whose company the universe no longer holds, for the
  maintainer; it changes no entry.

A version's ``[meta]`` is dated today and names the universe's full refresh and its size. The
database must be at the schema the package's assembly reads.
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import cast

from fairband.engine.roic import aggregate_roic
from fairband.engine.route import NO_MOAT_CLASS, CompanyInputs
from fairband.engine.types import ValuationResult
from fairband.policy import Moat
from fairband.policy.moat import MoatEntry, MoatTable, load_moat_table
from fairband.policy.moat_rule import MoatFacts, ReturnYear, draft_classes, gross_margins
from fairband.policy.tax import load_tax_table
from fairband.refresh.inputs import build_inputs
from fairband.store.companies import CompanyRow, latest_companies
from fairband.store.refreshes import latest_deciles
from fairband.store.settings import effective_policy
from fairband.store.snapshots import latest_snapshot

FIRST_VERSION = "fairband-moat-v1"
RULE = "docs/method.md 4.9a"
_LOG_SECTION = "### 6.7 "
_PAIR = re.compile(r"^\*From (Wide|Narrow|None) to (Wide|Narrow|None) \((\d+)\):\*$")
_CORRECTIONS = ["Ticker", "Company", "Why", "Decided by"]
_KEPT = ["Ticker", "Company", "Class", "Why it stays", "Decided by"]
_CLASSES = ("Wide", "Narrow", "None")


def connect_read_only(path: Path) -> sqlite3.Connection:
    """The database at ``path``, opened read-only, rows by name as the store reads them."""
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def read_facts(conn: sqlite3.Connection) -> list[MoatFacts]:
    """What the rule reads of each company of the universe, by symbol: its industry and sector;
    its latest snapshot's phase and revenue (``snapshot_revenue``); the last ten return years and
    the fiscal revenues assembly reads at the latest snapshots' newest data date; and the gross
    margins of its income statements (``_gross_margins``). A company assembly fails on has no
    return year and no revenue, and a line on stderr names it."""
    companies = latest_companies(conn)
    today = _newest_data_date(conn, [c.symbol for c in companies])
    policy, tax, deciles = effective_policy(conn), load_tax_table(), latest_deciles(conn)

    def assemble(symbol: str) -> CompanyInputs:
        return build_inputs(conn, symbol, policy, tax, today, deciles)

    return [_facts(conn, company, assemble) for company in companies]


def _facts(
    conn: sqlite3.Connection, company: CompanyRow, assemble: Callable[[str], CompanyInputs]
) -> MoatFacts:
    symbol = company.symbol
    snapshot = latest_snapshot(conn, symbol)
    industry, sector = company.industry or "", company.sector or ""
    phase = None if snapshot is None else snapshot.phase
    margins = _gross_margins(conn, symbol)
    try:
        inputs = assemble(symbol)
        kept = aggregate_roic(inputs.capital_years).by_year[-10:]
    except Exception as exc:  # noqa: BLE001 - a company's failure is its own
        print(f"{symbol}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return MoatFacts(symbol, industry, sector, phase, (), None, (), margins)
    years = tuple(ReturnYear(y.nopat, y.average_capital) for y in kept)
    revenues = tuple(fy.revenue for fy in inputs.series)
    revenue = None if snapshot is None else snapshot_revenue(snapshot.result, lambda: inputs)
    return MoatFacts(symbol, industry, sector, phase, years, revenue, revenues, margins)


def _newest_data_date(conn: sqlite3.Connection, symbols: list[str]) -> date:
    """The newest data date of the latest snapshots of ``symbols``, the day assembly reads at."""
    row = conn.execute(
        "SELECT MAX(data_date) FROM snapshots WHERE id IN (SELECT MAX(id) FROM snapshots"
        " WHERE symbol IN (SELECT value FROM json_each(?)) GROUP BY symbol)",
        (json.dumps(symbols),),
    ).fetchone()
    if row[0] is None:
        raise SystemExit("the universe has no snapshot")
    return date.fromisoformat(row[0])


def snapshot_revenue(
    result: ValuationResult, assemble: Callable[[], CompanyInputs]
) -> float | None:
    """The trailing revenue in USD of a snapshot's result: its ``revenue_ttm`` input ÷ its
    ``fx_rate`` input where it has one, ``None`` without ``revenue_ttm``. A result refused
    "no moat class" cites none: then ``assemble()``'s trailing revenue ÷ its rate (spec 8.2)."""
    if result.refusal == NO_MOAT_CLASS:
        inputs = assemble()
        trailing = None if inputs.trailing is None else inputs.trailing.revenue
        if trailing is None:
            return None
        return trailing / inputs.fx_rate if inputs.fx_rate else trailing
    cited = {i.name: i.value for i in result.inputs}
    revenue, rate = cited.get("revenue_ttm"), cited.get("fx_rate")
    if revenue is None:
        return None
    return revenue / rate if rate else revenue


def _gross_margins(conn: sqlite3.Connection, symbol: str) -> tuple[float, ...]:
    """The margins of the newest of the company's three newest FMP ``income-annual`` answers by
    ``observed_at`` stored with a payload and no error whose payload is a non-empty list."""
    rows = conn.execute(
        "SELECT payload FROM vendor_responses WHERE provider = 'fmp'"
        " AND endpoint = 'income-annual' AND symbol = ? AND payload IS NOT NULL"
        " AND error IS NULL ORDER BY observed_at DESC LIMIT 3",
        (symbol,),
    )
    for (payload,) in rows:
        try:
            answer = json.loads(payload)
        except ValueError:
            continue
        if isinstance(answer, list) and answer:
            return gross_margins(answer)
    return ()


def universe_words(conn: sqlite3.Connection) -> str:
    """``[meta]``'s universe: "the universe of the full refresh of <its start date>, <n>
    companies"."""
    companies = latest_companies(conn)
    if not companies:
        raise SystemExit("the database holds no universe")
    row = conn.execute(
        "SELECT started_at FROM refreshes WHERE id = ?", (companies[0].refresh_id,)
    ).fetchone()
    day = datetime.fromisoformat(row["started_at"]).date()
    return f"the universe of the full refresh of {day.isoformat()}, {len(companies):,} companies"


@dataclass(frozen=True)
class Correction:
    """A class the log changes: the rule's class, the class in force, why and who decided."""

    symbol: str
    rule_class: Moat
    moat: Moat
    reason: str
    decided_by: str


@dataclass(frozen=True)
class Kept:
    """A class the log questioned and kept as the rule has it: why it stays and who decided."""

    symbol: str
    moat: Moat
    note: str
    decided_by: str


def parse_log(text: str) -> tuple[dict[str, Correction], dict[str, Kept]]:
    """The corrections and the kept entries of the decision document's 6.7, by symbol in the
    document's order, each cell word for word. A correction's table follows its heading, "*From
    Wide to None (5):*", whose count it must hold; the kept entries' table is the one headed
    "Class" and "Why it stays". Any other table of the section is read as no entry."""
    corrections: dict[str, Correction] = {}
    kept: dict[str, Kept] = {}
    heading: _Heading | None = None
    headings: list[_Heading] = []
    table: str | None = None  # "corrections", "kept", or None for no table or another one
    for line in _section(text):
        if not line.startswith("|"):
            table = None
            if found := _PAIR.match(line.strip()):
                heading = _Heading(line.strip(), _class(found[1]), _class(found[2]), int(found[3]))
                headings.append(heading)
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if cells == _CORRECTIONS:
            if heading is None:
                raise SystemExit("6.7: a table of corrections without its heading")
            table = "corrections"
        elif cells == _KEPT:
            table = "kept"
        elif table == "corrections" and heading is not None:
            symbol, _, reason, decided_by = _cells(cells, 4, line)
            _new(symbol, corrections, kept)
            corrections[symbol] = Correction(
                symbol, heading.rule_class, heading.moat, reason, decided_by
            )
            heading.rows += 1
        elif table == "kept":
            symbol, _, moat, note, decided_by = _cells(cells, 5, line)
            _new(symbol, corrections, kept)
            kept[symbol] = Kept(symbol, _class(moat), note, decided_by)
        else:
            table = None
    for h in headings:
        if h.rows != h.count:
            raise SystemExit(f"6.7: {h.line} heads a table of {h.rows}")
    return corrections, kept


@dataclass
class _Heading:
    """A heading of corrections, "*From Wide to None (5):*", and the rows its table holds."""

    line: str
    rule_class: Moat
    moat: Moat
    count: int
    rows: int = 0


def _section(text: str) -> list[str]:
    """The lines of section 6.7, its heading left out."""
    lines = text.splitlines()
    starts = [k for k, line in enumerate(lines) if line.startswith(_LOG_SECTION)]
    if not starts:
        raise SystemExit("the decision document has no section 6.7")
    body = lines[starts[0] + 1 :]
    ends = [k for k, line in enumerate(body) if re.match(r"#{1,3} ", line)]
    return body[: ends[0]] if ends else body


def _cells(cells: list[str], count: int, line: str) -> list[str]:
    if len(cells) != count:
        raise SystemExit(f"6.7: not {count} cells: {line}")
    return cells


def _new(symbol: str, corrections: Mapping[str, object], kept: Mapping[str, object]) -> None:
    if symbol in corrections or symbol in kept:
        raise SystemExit(f"6.7: {symbol} twice")


def _class(word: str) -> Moat:
    if word not in _CLASSES:
        raise SystemExit(f"6.7: {word!r} is not Wide, Narrow or None")
    return cast(Moat, word)


def first_version(
    classes: Mapping[str, Moat],
    corrections: Mapping[str, Correction],
    kept: Mapping[str, Kept],
    judged: date,
    version: str,
    cut: date,
    universe: str,
) -> MoatTable:
    """Each company of ``classes``, the rule's draft, judged ``judged``, with the log applied:
    a correction's class with its rule class, reason and decider; a kept entry's note and
    decider. A log entry the rule does not bear out refuses the version, all of them named."""
    refusals = [
        f"{symbol}: the log names it; the universe does not hold it"
        for symbol in sorted({*corrections, *kept} - set(classes))
    ]
    entries: dict[str, MoatEntry] = {}
    for symbol in sorted(classes):
        drafted = classes[symbol]
        if symbol in corrections:
            c = corrections[symbol]
            if c.rule_class != drafted:
                corrected = f"the log corrects the rule's {c.rule_class}"
                refusals.append(f"{symbol}: {corrected}; the rule gives {drafted}")
            entries[symbol] = MoatEntry(
                symbol, c.moat, judged, "correction", c.rule_class, c.reason, c.decided_by
            )
        elif symbol in kept:
            k = kept[symbol]
            if k.moat != drafted:
                refusals.append(
                    f"{symbol}: the log keeps the rule's {k.moat}; the rule gives {drafted}"
                )
            entries[symbol] = MoatEntry(
                symbol, drafted, judged, "rule", decided_by=k.decided_by, note=k.note
            )
        else:
            entries[symbol] = MoatEntry(symbol, drafted, judged, "rule")
    if refusals:
        raise SystemExit("the rule does not bear out the log:\n" + "\n".join(sorted(refusals)))
    return MoatTable(version, cut, universe, RULE, entries)


def new_version(
    current: MoatTable, drafted: Mapping[str, Moat], today: date, version: str, universe: str
) -> MoatTable:
    """``current``'s entries as they are, and the rule's class of each company of ``drafted``
    that ``current`` lacks, judged ``today``; dated ``today``."""
    entries = dict(current.entries)
    for symbol in drafted:
        if symbol not in entries:
            entries[symbol] = MoatEntry(symbol, drafted[symbol], today, "rule")
    return MoatTable(version, today, universe, RULE, {s: entries[s] for s in sorted(entries)})


def yearly_read(current: MoatTable, drafted: Mapping[str, Moat]) -> list[tuple[str, Moat, Moat]]:
    """Each ``rule`` entry of ``current`` whose class the rule gives differently today, by symbol:
    the symbol, the file's class and the rule's."""
    return [
        (symbol, entry.moat, drafted[symbol])
        for symbol, entry in sorted(current.entries.items())
        if entry.source == "rule" and symbol in drafted and drafted[symbol] != entry.moat
    ]


def render(table: MoatTable) -> str:
    """The file: ``[meta]``, then one ``[[classes]]`` an entry, by symbol."""
    lines = [
        "[meta]",
        f"version = {_string(table.version)}",
        f"date = {table.date.isoformat()}",
        f"universe = {_string(table.universe)}",
        f"rule = {_string(table.rule)}",
    ]
    for symbol in sorted(table.entries):
        entry = table.entries[symbol]
        lines += [
            "",
            "[[classes]]",
            f"symbol = {_string(entry.symbol)}",
            f"class = {_string(entry.moat)}",
            f"judged = {entry.judged.isoformat()}",
            f"source = {_string(entry.source)}",
        ]
        optional = (
            ("rule_class", entry.rule_class),
            ("reason", entry.reason),
            ("note", entry.note),
            ("decided_by", entry.decided_by),
        )
        lines += [f"{field} = {_string(value)}" for field, value in optional if value is not None]
    return "\n".join(lines) + "\n"


def _string(value: str) -> str:
    """A TOML basic string: JSON's escapes are TOML's."""
    return json.dumps(value, ensure_ascii=False)


def _write(table: MoatTable, out: Path) -> MoatTable:
    """Write ``table`` to ``out`` and read it back as the engine would."""
    out.write_text(render(table), encoding="utf-8")
    return load_moat_table(out)


def _drafted(database: Path) -> tuple[dict[str, Moat], str]:
    """The rule's class of each company of the universe of ``database``, and the universe's
    words for ``[meta]``."""
    with closing(connect_read_only(database)) as conn:
        return draft_classes(read_facts(conn)), universe_words(conn)


def _first(args: argparse.Namespace) -> None:
    corrections, kept = parse_log(args.log.read_text(encoding="utf-8"))
    classes, universe = _drafted(args.database)
    table = first_version(
        classes, corrections, kept, args.judged, FIRST_VERSION, date.today(), universe
    )
    written = _write(table, args.out)
    counts = Counter(e.moat for e in written.entries.values())
    print(
        f"{args.out}: {len(written.entries):,} companies, Wide {counts['Wide']:,}, "
        f"Narrow {counts['Narrow']:,}, None {counts['None']:,}; {len(corrections)} corrections, "
        f"{len(kept)} kept with a note"
    )


def _new_version(args: argparse.Namespace) -> None:
    current = load_moat_table(args.current)
    drafted, universe = _drafted(args.database)
    today = date.today()
    table = new_version(current, drafted, today, args.version, universe)
    written = _write(table, args.out)
    added = [e for e in written.entries.values() if e.symbol not in current.entries]
    print(
        f"{args.out}: {len(written.entries):,} companies, {len(added)} drafted, "
        f"judged {today.isoformat()}"
    )
    for entry in added:
        print(f"  {entry.symbol} {entry.moat}")


def _read(args: argparse.Namespace) -> None:
    current = load_moat_table(args.current)
    drafted, _ = _drafted(args.database)
    differ = yearly_read(current, drafted)
    left = sorted(set(current.entries) - set(drafted))
    print(f"{args.current}: {len(differ)} rule entries the rule gives differently today")
    for symbol, held, rule in differ:
        print(f"  {symbol}: {held} in the file, {rule} by the rule")
    print(f"{len(left)} entries whose company the universe no longer holds")
    for symbol in left:
        print(f"  {symbol}: in the file, not in the universe")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    first = commands.add_parser("first", help="the first version, from the log of 6.7")
    first.add_argument("--database", type=Path, required=True)
    first.add_argument("--log", type=Path, required=True, help="the decision document")
    first.add_argument("--judged", type=date.fromisoformat, required=True)
    first.add_argument("--out", type=Path, required=True)
    first.set_defaults(run=_first)
    new = commands.add_parser("new", help="a new version: the current one and the entrants")
    new.add_argument("--database", type=Path, required=True)
    new.add_argument("--current", type=Path, required=True)
    new.add_argument("--version", required=True)
    new.add_argument("--out", type=Path, required=True)
    new.set_defaults(run=_new_version)
    read = commands.add_parser("read", help="the yearly read: what the rule gives differently")
    read.add_argument("--database", type=Path, required=True)
    read.add_argument("--current", type=Path, required=True)
    read.set_defaults(run=_read)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
