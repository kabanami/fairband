"""Statutory corporate tax rates by country and year: the labelled fallback of research.md D9.

The packaged table, v2, holds the OECD combined (central plus sub-central) statutory rate for every
jurisdiction of the series, and Taiwan's and Cyprus's, which the series lacks, by hand;
``scripts/build_tax_table.py`` regenerates it from the series' CSV export. v1, the sixteen
jurisdictions of method 0.8 and earlier, stays in the package for the snapshots that cite it
(spec 2026-11-06 10).

A year after the newest year on file for a country takes that newest rate as a labelled estimate;
an earlier missing year or an unknown country gives ``None``, so the caller refuses with a reason
instead of silently using another year's rate. A country is named as the table names it or by the
ISO 3166-1 alpha-2 code of the table's ``[country_aliases]`` (``US``), the form FMP gives a
company's country.
"""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

LATEST_YEAR_METHOD = "tax-rate-latest-oecd-year-v1"

_TAX_FILE = "tax-rates-oecd-v2.toml"


@dataclass(frozen=True)
class TaxRate:
    rate: float
    year_used: int
    estimate: bool
    method: str | None
    source: str


class TaxTable:
    def __init__(
        self,
        rates: Mapping[tuple[str, int], float],
        source: str,
        aliases: Mapping[str, str] | None = None,
    ) -> None:
        self._rates = dict(rates)
        self._aliases = dict(aliases or {})
        self._newest: dict[str, int] = {}
        for country, year in self._rates:
            self._newest[country] = max(year, self._newest.get(country, year))
        self.source = source

    def rate_for(self, country: str, year: int) -> TaxRate | None:
        """The rate for ``year``; a later year carries the newest rate forward as an estimate.
        ``country`` is the OECD name or its code."""
        country = self._aliases.get(country, country)
        rate = self._rates.get((country, year))
        if rate is not None:
            return TaxRate(rate, year, estimate=False, method=None, source=self.source)
        newest = self._newest.get(country)
        if newest is None or year < newest:
            return None
        return TaxRate(
            self._rates[(country, newest)],
            newest,
            estimate=True,
            method=LATEST_YEAR_METHOD,
            source=self.source,
        )

    def years(self) -> set[tuple[str, int]]:
        return set(self._rates)


def load_tax_table(path: Path | None = None) -> TaxTable:
    """Parse the tax table (default: the packaged OECD v2 file). Rates must be fractions, and a
    country code must name a country with rates."""
    if path is None:
        data = resources.files("fairband.policy").joinpath(_TAX_FILE).read_bytes()
    else:
        data = path.read_bytes()
    raw = tomllib.loads(data.decode("utf-8"))
    try:
        source = raw["meta"]["source"]
    except (KeyError, TypeError) as e:
        raise ValueError("tax table: [meta] has no source") from e
    if not isinstance(source, str):
        raise TypeError("tax table: meta.source must be a string")
    rates: dict[tuple[str, int], float] = {}
    for row in raw.get("rates", []):
        country, year, rate = _row(row)
        if (country, year) in rates:
            raise ValueError(f"tax table: {country} {year} appears twice")
        rates[(country, year)] = rate
    aliases = _aliases(raw.get("country_aliases", {}), {c for c, _ in rates})
    return TaxTable(rates, source, aliases)


def _aliases(raw: Any, countries: set[str]) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise TypeError("tax table: [country_aliases] must be a table")
    for code, name in raw.items():
        if not isinstance(name, str):
            raise TypeError(f"tax table: country alias {code} must be a string")
        if name not in countries:
            raise ValueError(f"tax table: country alias {code} names {name}, which has no rates")
    return dict(raw)


def _row(row: Any) -> tuple[str, int, float]:
    try:
        country, year, rate = row["country"], row["year"], row["rate"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"tax table: a [[rates]] row lacks {e}: {row!r}") from e
    if not isinstance(country, str) or type(year) is not int:
        raise TypeError(f"tax table: a [[rates]] row has a bad country or year: {row!r}")
    if type(rate) not in (int, float) or not 0 <= rate < 1:
        raise ValueError(f"tax table: {country} {year} rate {rate!r} is not a fraction in [0, 1)")
    return country, year, float(rate)
