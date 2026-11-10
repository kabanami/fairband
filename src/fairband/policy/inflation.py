"""Expected inflation by currency: the rates of a company in another currency (spec 2026-11-10 7.3).

The packaged table, v1, holds for each currency the IMF World Economic Outlook's projections of
consumer price inflation (``PCPIPCH``) of the currency's issuing economy for the five years after
the retrieval's year, as fractions; ``scripts/build_inflation_table.py`` writes it from the
datamapper's JSON. A currency's expected inflation π is the mean of its projections. The
differential d = (1 + π_currency) ÷ (1 + π_USD) − 1 restates a nominal USD rate in the currency:
(1 + rate) × (1 + d) − 1. USD is in the table and gives π_USD, so a table without it is refused;
a currency the table lacks gives ``None``, and the caller refuses with a reason.
"""

import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from itertools import pairwise
from pathlib import Path
from typing import Any

INFLATION_FILE = "inflation-imf-weo-v1.toml"

# A projection outside −50% to 500% is a figure in percent, not a fraction, or a misread.
_RATE_MIN = -0.5
_RATE_MAX = 5.0
_META = ("source", "url", "vintage", "retrieved", "years")


@dataclass(frozen=True)
class Inflation:
    """One currency's projections: the ISO 4217 code, the WEO's code for its economy (``TWN``,
    ``EURO``), the projection years and one rate a year, as fractions."""

    currency: str
    economy: str
    years: tuple[int, ...]
    rates: tuple[float, ...]

    @property
    def mean(self) -> float:
        """π: the mean of the projections."""
        return sum(self.rates) / len(self.rates)


class InflationTable:
    def __init__(
        self, rows: Iterable[Inflation], source: str, url: str, vintage: str, retrieved: str
    ) -> None:
        self._rows = {row.currency: row for row in rows}
        self.source = source
        self.url = url
        self.vintage = vintage
        self.retrieved = retrieved

    def rate_for(self, currency: str) -> Inflation | None:
        return self._rows.get(currency)

    def differential(self, currency: str) -> float | None:
        """(1 + π_currency) ÷ (1 + π_USD) − 1 on the means; 0.0 for USD; None for a currency
        the table lacks."""
        if currency == "USD":
            return 0.0
        row = self._rows.get(currency)
        if row is None:
            return None
        return (1 + row.mean) / (1 + self._rows["USD"].mean) - 1


def load_inflation_table(path: Path | None = None) -> InflationTable:
    """Parse the inflation table (default: the packaged IMF v1 file). ``[meta]`` must name the
    source, the url, the vintage, the retrieval date and the projection years; each currency
    appears once, with one rate a year, each a fraction from −0.5 to 5; USD must be there."""
    if path is None:
        data = resources.files("fairband.policy").joinpath(INFLATION_FILE).read_bytes()
    else:
        data = path.read_bytes()
    raw = tomllib.loads(data.decode("utf-8"))
    meta = raw.get("meta", {})
    if not isinstance(meta, dict):
        raise TypeError("inflation table: [meta] must be a table")
    for field in _META:
        if field not in meta:
            raise ValueError(f"inflation table: [meta] has no {field}")
    source, url, vintage, retrieved = (
        _text(meta[field], f"meta.{field}") for field in ("source", "url", "vintage", "retrieved")
    )
    years = _years(meta["years"])
    rows: dict[str, Inflation] = {}
    for entry in raw.get("currencies", []):
        row = _row(entry, years)
        if row.currency in rows:
            raise ValueError(f"inflation table: {row.currency} appears twice")
        rows[row.currency] = row
    if "USD" not in rows:
        raise ValueError("inflation table: no USD row, which the differential divides by")
    return InflationTable(rows.values(), source, url, vintage, retrieved)


def _text(x: Any, name: str) -> str:
    if not isinstance(x, str):
        raise TypeError(f"inflation table: {name} must be a string")
    return x


def _years(x: Any) -> tuple[int, ...]:
    if not isinstance(x, list) or not x or not all(type(y) is int for y in x):
        raise TypeError(f"inflation table: meta.years must be a list of years, not {x!r}")
    if not all(a < b for a, b in pairwise(x)):
        raise ValueError(f"inflation table: meta.years {x} do not ascend")
    return tuple(x)


def _row(entry: Any, years: tuple[int, ...]) -> Inflation:
    try:
        code, economy, rates = entry["code"], entry["economy"], entry["rates"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"inflation table: a [[currencies]] row lacks {e}: {entry!r}") from e
    if not isinstance(code, str) or not isinstance(economy, str) or not isinstance(rates, list):
        raise TypeError(f"inflation table: a [[currencies]] row is malformed: {entry!r}")
    if len(rates) != len(years):
        raise ValueError(f"inflation table: {code} has {len(rates)} rates for {len(years)} years")
    for rate in rates:
        if type(rate) not in (int, float) or not _RATE_MIN <= rate <= _RATE_MAX:
            raise ValueError(
                f"inflation table: {code} rate {rate!r} is not a fraction from −0.5 to 5"
            )
    return Inflation(code, economy, years, tuple(float(r) for r in rates))
