"""Build the packaged tax table from the OECD series' CSV export (spec 2026-11-06 10).

    uv run python scripts/build_tax_table.py <csv> <toml> [--retrieved YYYY-MM-DD]

The CSV is the SDMX export of ``SERIES_URL``, requested with the header
``Accept: application/vnd.sdmx.data+csv;version=1.0.0`` and saved outside the repository; it is
never committed. Its columns are labelled (``REF_AREA: Reference area``) and so are its values
(``GRC: Greece``). The table keeps the combined statutory rate, measure ``CIT_C``, sector ``S13``,
targeting ``ST``, for every jurisdiction and every year from 2014 the series gives, as a fraction:
``OBS_VALUE`` is a percentage, kept to its six decimals. Each jurisdiction is named as the OECD
names it, with its ISO 3166-1 alpha-2 code (the form FMP gives a company's country) as the alias.
``HAND_ROWS`` adds the jurisdictions the series lacks, each with its own source. The retrieval
date defaults to the CSV's modification date. The file written is loaded back through
``load_tax_table`` before the script reports, so a table the engine would refuse fails here.

``pycountry`` is a dev dependency, for this script only; the package never imports it.
"""

import argparse
import csv
import json
import textwrap
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pycountry

from fairband.policy.tax import load_tax_table

SOURCE = (
    "OECD Corporate Tax Statistics, Table II.1 statutory corporate income tax rates, "
    "combined central and sub-central"
)
SERIES_URL = (
    "https://sdmx.oecd.org/public/rest/data/OECD.CTP.TPS,DSD_TAX_CIT@DF_CIT,2.0/all"
    "?startPeriod=2014&dimensionAtObservation=AllDimensions"
)
EXPLORER_URL = (
    "https://data-explorer.oecd.org/vis?df[ds]=dsDisseminateFinalDMZ"
    "&df[id]=DSD_TAX_CIT%40DF_CIT&df[ag]=OECD.CTP.TPS"
)
FIRST_YEAR = 2014

_DATAFLOW = "DATAFLOW"
_AREA = "REF_AREA: Reference area"
_MEASURE = "MEASURE: Measure"
_SECTOR = "SECTOR: Institutional sector"
_TARGETING = "TARGETING: Targeting"
_UNIT = "UNIT_MEASURE: Unit of measure"
_YEAR = "TIME_PERIOD: Time period"
_VALUE = "OBS_VALUE"
_COLUMNS = (_DATAFLOW, _AREA, _MEASURE, _SECTOR, _TARGETING, _UNIT, _YEAR, _VALUE)

# A percentage to six decimals is a fraction to eight, as v1's rates are.
_PLACES = Decimal("1e-8")


@dataclass(frozen=True)
class Row:
    """One ``[[rates]]`` row: a series row has no source of its own, a hand row has one."""

    code: str
    country: str
    year: int
    rate: Decimal
    source: str | None = None


@dataclass(frozen=True)
class HandRate:
    """One rate for the years ``first`` to ``last`` of a jurisdiction the series lacks."""

    code: str
    country: str
    first: int
    last: int
    rate: Decimal
    source: str


_TAIWAN_ACT = "the Income Tax Act, article 5, Ministry of Finance, Taiwan"

HAND_ROWS = (
    HandRate("TW", "Taiwan", 2014, 2017, Decimal("0.17"), f"{_TAIWAN_ACT}: 17% from 2010 to 2017"),
    # Through the series' newest year at the retrieval of 2026-11-06.
    HandRate("TW", "Taiwan", 2018, 2026, Decimal("0.20"), f"{_TAIWAN_ACT}: 20% from 2018"),
    # Through 2025 only: a 2026 rate goes in with a government source for the enacted change;
    # until then the engine carries 2025's forward, flagged (method 4.3).
    HandRate(
        "CY",
        "Cyprus",
        2014,
        2025,
        Decimal("0.125"),
        "the Tax Department, Republic of Cyprus: 12.5% through 2025",
    ),
)


def read_series(path: Path) -> tuple[str, list[Row]]:
    """The dataflow's name and the combined statutory rate of every jurisdiction and year."""
    rows: dict[tuple[str, int], Row] = {}
    dataflows: set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in _COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path}: no column {', '.join(missing)}")
        for record in reader:
            if not (
                record[_MEASURE].startswith("CIT_C:")
                and record[_SECTOR].startswith("S13:")
                and record[_TARGETING].startswith("ST:")
            ):
                continue
            year = int(record[_YEAR])
            if year < FIRST_YEAR:
                continue
            if not record[_UNIT].startswith("PT_INC_TAX:"):
                raise SystemExit(f"{record[_AREA]} {year}: not a percentage: {record[_UNIT]}")
            row = _row(record[_AREA], year, record[_VALUE])
            if (row.code, year) in rows:
                raise SystemExit(f"{record[_AREA]} {year} appears twice")
            rows[(row.code, year)] = row
            dataflows.add(record[_DATAFLOW])
    if len(dataflows) != 1:
        raise SystemExit(f"{path}: expected one dataflow, found {sorted(dataflows)}")
    return dataflows.pop(), sorted(rows.values(), key=lambda r: (r.code, r.year))


def _row(area: str, year: int, value: str) -> Row:
    alpha_3, _, name = area.partition(": ")
    country = pycountry.countries.get(alpha_3=alpha_3)
    if country is None or not name:
        raise SystemExit(f"{area}: no ISO 3166-1 alpha-2 code")
    try:
        percent = Decimal(value)
    except InvalidOperation as e:
        raise SystemExit(f"{area} {year}: rate {value!r} is not a number") from e
    return Row(country.alpha_2, name, year, (percent / 100).quantize(_PLACES))


def hand_rows(series: Iterable[Row]) -> list[Row]:
    """``HAND_ROWS`` year by year; a jurisdiction the series now gives must drop its hand rows."""
    given = {r.code for r in series}
    rows: list[Row] = []
    for hand in HAND_ROWS:
        if hand.code in given:
            raise SystemExit(f"{hand.code} is in the series now: drop its hand rows")
        for year in range(hand.first, hand.last + 1):
            rows.append(Row(hand.code, hand.country, year, hand.rate, hand.source))
    return sorted(rows, key=lambda r: (r.code, r.year))


def render(dataflow: str, retrieved: str, series: list[Row], by_hand: list[Row]) -> str:
    """The table in v1's layout: the header comments, ``[meta]``, the aliases, the rates."""
    aliases = {r.code: r.country for r in [*series, *by_hand]}
    hand_countries = " and ".join(dict.fromkeys(r.country for r in by_hand))
    header = (
        "Statutory corporate income tax rates: the OECD combined (central plus sub-central) "
        "rate, the labelled fallback for a company's marginal tax rate (research.md D9). Rates "
        "are decimal fractions. Country names are the OECD's. Series: dataflow "
        f"{dataflow}, MEASURE=CIT_C (combined corporate income tax rate), TARGETING=ST "
        f"(statutory), SECTOR=S13 (general government), retrieved {retrieved}. "
        f"{hand_countries}, which the series lacks, are written by hand at the end, each row with "
        "its own source; the engine cites [meta]'s source for every rate. A jurisdiction in "
        "neither, Puerto Rico among them, has no rows."
    )
    lines = [
        *(f"# {line}" for line in textwrap.wrap(header, 98, break_on_hyphens=False)),
        f"# Data explorer: {EXPLORER_URL}",
        "# Generated by scripts/build_tax_table.py from the series' CSV export; edit the script,",
        "# not this file.",
        "",
        "[meta]",
        f"source = {_string(SOURCE)}",
        f"url = {_string(SERIES_URL)}",
        f"retrieved = {_string(retrieved)}",
        "",
        "# The ISO 3166-1 alpha-2 code of each country below, the form FMP gives a company's country.",
        "[country_aliases]",
        *(f"{code} = {_string(aliases[code])}" for code in sorted(aliases)),
    ]
    for row in series:
        lines += _rate(row)
    lines += ["", "# Written by hand: the jurisdictions the OECD series lacks."]
    for row in by_hand:
        lines += _rate(row)
    return "\n".join(lines) + "\n"


def _rate(row: Row) -> list[str]:
    lines = [
        "",
        "[[rates]]",
        f"country = {_string(row.country)}",
        f"year = {row.year}",
        f"rate = {float(row.rate)!r}",
    ]
    if row.source is not None:
        lines.append(f"source = {_string(row.source)}")
    return lines


def _string(value: str) -> str:
    """A TOML basic string: JSON's escapes are TOML's."""
    return json.dumps(value, ensure_ascii=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("csv", type=Path, help="the OECD series' CSV export")
    parser.add_argument("toml", type=Path, help="the tax table to write")
    parser.add_argument(
        "--retrieved",
        type=date.fromisoformat,
        help="the date the CSV was fetched (default: its modification date)",
    )
    args = parser.parse_args(argv)
    retrieved = args.retrieved or date.fromtimestamp(args.csv.stat().st_mtime)
    dataflow, series = read_series(args.csv)
    by_hand = hand_rows(series)
    args.toml.write_text(render(dataflow, retrieved.isoformat(), series, by_hand), encoding="utf-8")
    table = load_tax_table(args.toml)
    countries = {c for c, _ in table.years()}
    print(
        f"{args.toml}: {len(countries)} jurisdictions "
        f"({len({r.code for r in series})} from the series, "
        f"{len({r.code for r in by_hand})} by hand), {len(table.years())} rates"
    )


if __name__ == "__main__":
    main()
