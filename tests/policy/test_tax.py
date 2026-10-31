from pathlib import Path

import pytest

from fairband.policy.tax import load_tax_table

# The jurisdictions the brief asks for; Puerto Rico is not in the OECD table, so it is omitted.
_JURISDICTIONS = [
    "United States",
    "Canada",
    "United Kingdom",
    "Ireland",
    "Netherlands",
    "Switzerland",
    "Germany",
    "France",
    "Luxembourg",
    "Israel",
    "Singapore",
    "Japan",
    "Australia",
    "Bermuda",
    "Cayman Islands",
    "Jersey",
]


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


def test_rate_given_as_a_percentage_is_refused(tmp_path: Path) -> None:
    table = tmp_path / "tax.toml"
    table.write_text(
        '[meta]\nsource = "s"\nurl = "u"\nretrieved = "2026-10-31"\n\n'
        '[[rates]]\ncountry = "United States"\nyear = 2022\nrate = 25.8\n'
    )
    with pytest.raises(ValueError, match="United States 2022"):
        load_tax_table(table)
