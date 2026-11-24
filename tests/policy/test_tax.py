import tomllib
from importlib import resources
from pathlib import Path

import pytest

from fairband.policy.tax import load_tax_table

# v1's sixteen jurisdictions, each with the ISO 3166-1 alpha-2 code FMP gives as a company's
# country; v2 keeps every one. Puerto Rico is not in the OECD series, so neither table has it.
_CODES = {
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "IE": "Ireland",
    "NL": "Netherlands",
    "CH": "Switzerland",
    "DE": "Germany",
    "FR": "France",
    "LU": "Luxembourg",
    "IL": "Israel",
    "SG": "Singapore",
    "JP": "Japan",
    "AU": "Australia",
    "BM": "Bermuda",
    "KY": "Cayman Islands",
    "JE": "Jersey",
}
_JURISDICTIONS = list(_CODES.values())


def test_exact_year() -> None:
    t = load_tax_table()
    r = t.rate_for("United States", 2022)
    assert r is not None and r.estimate is False and r.year_used == 2022 and 0.2 < r.rate < 0.3
    assert r.method is None and "OECD" in r.source


def test_later_year_carried_forward() -> None:
    t = load_tax_table()
    newest = max(y for (c, y) in t.years() if c == "United States")
    r = t.rate_for("United States", newest + 1)
    assert r is not None and r.estimate is True and r.year_used == newest
    assert r.method == "tax-rate-latest-oecd-year-v1"
    exact = t.rate_for("United States", newest)
    assert exact is not None and r.rate == exact.rate


def test_missing_earlier_year_and_unknown_country() -> None:
    t = load_tax_table()
    assert t.rate_for("United States", 1990) is None
    assert t.rate_for("Atlantis", 2022) is None


@pytest.mark.parametrize("country", _JURISDICTIONS)
def test_each_jurisdiction_covered_from_2014(country: str) -> None:
    t = load_tax_table()
    years = sorted(y for (c, y) in t.years() if c == country)
    assert years and years == list(range(2014, years[-1] + 1))


@pytest.mark.parametrize(("code", "name"), _CODES.items())
def test_country_code_or_name(code: str, name: str) -> None:
    t = load_tax_table()
    exact = t.rate_for(code, 2022)
    assert exact is not None and exact == t.rate_for(name, 2022)
    later = t.rate_for(code, 2040)
    assert later is not None and later.estimate is True


def test_v2_keeps_every_v1_rate() -> None:
    """v1 still loads, for the snapshots that cite it, and v2 has each of its rates unchanged
    under the same source (spec 2026-11-06 13.6)."""
    with resources.as_file(resources.files("fairband.policy") / "tax-rates-oecd-v1.toml") as path:
        v1 = load_tax_table(path)
    v2 = load_tax_table()
    assert len(v1.years()) == 207
    for country, year in v1.years():
        old, new = v1.rate_for(country, year), v2.rate_for(country, year)
        assert old is not None and new is not None
        assert (new.rate, new.year_used, new.estimate) == (old.rate, year, False)
    assert v2.source == v1.source


def test_the_united_states_2025_rate() -> None:
    r = load_tax_table().rate_for("US", 2025)
    assert r is not None and r.rate == 0.25569714 and r.estimate is False


@pytest.mark.parametrize(
    ("code", "year", "rate"),
    [
        ("GR", 2024, 0.22),
        ("SE", 2024, 0.206),
        ("IT", 2024, 0.2781),
        ("IN", 2024, 0.2517),
        ("HK", 2024, 0.165),
        # The series' statutory rate; 20% is Belgium's rate targeted at small business.
        ("BE", 2024, 0.25),
        ("BS", 2024, 0.0),
        ("GG", 2024, 0.0),
        ("AE", 2024, 0.09),
        ("CN", 2024, 0.25),
        ("TW", 2018, 0.20),
        ("TW", 2017, 0.17),
        ("CY", 2024, 0.125),
    ],
)
def test_the_new_countries(code: str, year: int, rate: float) -> None:
    """Jurisdictions v1 lacked, by their codes; Taiwan and Cyprus are written by hand."""
    r = load_tax_table().rate_for(code, year)
    assert r is not None and (r.rate, r.year_used, r.estimate) == (rate, year, False)


def test_a_hand_row_cites_its_own_source() -> None:
    """Taiwan's and Cyprus's rows cite the source on the row, the carried-forward estimate the
    newest year's row; a series row cites ``[meta]``."""
    t = load_tax_table()
    tw = t.rate_for("TW", 2024)
    assert tw is not None and tw.estimate is False
    assert tw.source == "the Income Tax Act, article 5, Ministry of Finance, Taiwan: 20% from 2018"
    cy = t.rate_for("CY", 2026)
    assert cy is not None and (cy.estimate, cy.year_used, cy.rate) == (True, 2025, 0.125)
    assert cy.source == "the Tax Department, Republic of Cyprus: 12.5% through 2025"
    for year in (2024, 2040):
        us = t.rate_for("US", year)
        assert us is not None and us.source == t.source and "OECD" in us.source


def test_a_row_source_that_is_not_a_string_is_refused(tmp_path: Path) -> None:
    table = tmp_path / "tax.toml"
    table.write_text(
        '[meta]\nsource = "s"\n\n'
        '[[rates]]\ncountry = "Taiwan"\nyear = 2024\nrate = 0.2\nsource = 5\n',
        encoding="utf-8",
    )
    with pytest.raises(TypeError, match="Taiwan 2024 source"):
        load_tax_table(table)


def test_every_jurisdiction_has_an_alias_and_a_rate_from_2024() -> None:
    """The OECD series' 146 jurisdictions and the two by hand, each named by its alpha-2 code
    with a 2024 rate on file; a country the series lacks still has none."""
    v2 = resources.files("fairband.policy").joinpath("tax-rates-oecd-v2.toml")
    aliases: dict[str, str] = tomllib.loads(v2.read_text("utf-8"))["country_aliases"]
    t = load_tax_table()
    countries = {c for c, _ in t.years()}
    assert len(countries) == 148 and set(aliases.values()) == countries
    assert len(aliases) == 148 and all(len(c) == 2 and c.isupper() for c in aliases)
    for code in aliases:
        r = t.rate_for(code, 2024)
        assert r is not None and r.estimate is False, code
    assert t.rate_for("PR", 2024) is None


def test_code_for_a_country_without_rates_is_refused(tmp_path: Path) -> None:
    table = tmp_path / "tax.toml"
    table.write_text(
        '[meta]\nsource = "s"\n\n[country_aliases]\nUS = "United Staets"\n\n'
        '[[rates]]\ncountry = "United States"\nyear = 2022\nrate = 0.25\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="United Staets"):
        load_tax_table(table)


def test_rate_given_as_a_percentage_is_refused(tmp_path: Path) -> None:
    table = tmp_path / "tax.toml"
    table.write_text(
        '[meta]\nsource = "s"\nurl = "u"\nretrieved = "2026-10-31"\n\n'
        '[[rates]]\ncountry = "United States"\nyear = 2022\nrate = 25.8\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="United States 2022"):
        load_tax_table(table)
