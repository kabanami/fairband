"""The packaged table of expected inflation by currency and the script that builds it (spec
2026-11-10 7.3 and 11.1)."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from fairband.policy.inflation import load_inflation_table

_SCRIPT = Path(__file__).parents[2] / "scripts" / "build_inflation_table.py"
_YEARS = ("2027", "2028", "2029", "2030", "2031")
# The 23 reporting currencies of the rows refused as foreign filers (spec section 5).
_UNIVERSE = [
    "USD",
    "CAD",
    "EUR",
    "CNY",
    "BRL",
    "GBP",
    "MXN",
    "KRW",
    "ZAR",
    "JPY",
    "TWD",
    "ARS",
    "INR",
    "VND",
    "TRY",
    "PHP",
    "SEK",
    "COP",
    "CLP",
    "DKK",
    "KZT",
    "CHF",
    "IDR",
]


def _script() -> ModuleType:
    """``scripts/build_inflation_table.py``, which is not in a package, loaded from its path."""
    spec = importlib.util.spec_from_file_location("build_inflation_table", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_table_loads_every_currency_of_the_universe() -> None:
    t = load_inflation_table()
    for code in _UNIVERSE:
        found = t.rate_for(code)
        assert found is not None and found.years == (2027, 2028, 2029, 2030, 2031)
        assert len(found.rates) == 5
    assert t.vintage == "October 2026" and "PCPIPCH" in t.source
    assert t.retrieved == "2026-11-10"


def test_the_means_and_the_differentials() -> None:
    """Spec 11.1 on the packaged table, to three decimals of a percent."""
    t = load_inflation_table()
    usd, twd, ars, turkey = (t.rate_for(c) for c in ("USD", "TWD", "ARS", "TRY"))
    assert usd is not None and twd is not None and ars is not None and turkey is not None
    assert usd.mean == pytest.approx(0.02120, abs=5e-6)
    assert twd.mean == pytest.approx(0.01600, abs=5e-6)
    assert t.differential("USD") == 0.0
    assert t.differential("TWD") == pytest.approx(-0.00509, abs=5e-6)
    assert t.differential("JPY") == pytest.approx(0.0, abs=5e-6)
    assert t.differential("BRL") == pytest.approx(0.01097, abs=5e-6)
    assert t.differential("CHF") == pytest.approx(-0.01351, abs=5e-6)
    assert t.differential("KZT") == pytest.approx(0.04034, abs=5e-6)
    assert ars.mean == pytest.approx(0.12120, abs=5e-6)
    assert turkey.mean == pytest.approx(0.18480, abs=5e-6)
    assert t.differential("XXX") is None and t.rate_for("XXX") is None


def test_the_packaged_rows_are_the_imf_figures_as_fractions() -> None:
    """USA's and Taiwan's projections for 2027 to 2031 (spec section 5), each ÷ 100 exactly."""
    t = load_inflation_table()
    usd, twd = t.rate_for("USD"), t.rate_for("TWD")
    assert usd is not None and usd.economy == "USA"
    assert usd.rates == (0.028, 0.021, 0.019, 0.019, 0.019)
    assert twd is not None and twd.economy == "TWN"
    assert twd.rates == (0.018, 0.016, 0.015, 0.016, 0.015)
    eur = t.rate_for("EUR")
    assert eur is not None and eur.economy == "EURO"


def test_the_table_holds_every_pair_of_the_script() -> None:
    """Every currency the script maps had five projections at the October 2026 vintage, and each
    names the economy the script maps it to."""
    pairs = _script().CURRENCY_ECONOMIES
    t = load_inflation_table()
    for code, economy in pairs.items():
        found = t.rate_for(code)
        assert found is not None and found.economy == economy, code


_TABLE = """[meta]
source = "IMF World Economic Outlook, October 2026: inflation, average consumer prices (PCPIPCH), annual percent change"
url = "https://www.imf.org/external/datamapper/api/v1/PCPIPCH"
vintage = "October 2026"
retrieved = "2026-11-10"
years = [2027, 2028, 2029, 2030, 2031]

[[currencies]]
code = "USD"
economy = "USA"
rates = [0.028, 0.021, 0.019, 0.019, 0.019]

[[currencies]]
code = "TWD"
economy = "TWN"
rates = [0.018, 0.016, 0.015, 0.016, 0.015]
"""
_TWD_RATES = "rates = [0.018, 0.016, 0.015, 0.016, 0.015]"


def _twd(rates: str) -> str:
    """The table with Taiwan's rates written as ``rates``."""
    assert _TABLE.count(_TWD_RATES) == 1
    return _TABLE.replace(_TWD_RATES, f"rates = {rates}")


def test_a_well_formed_table_loads(tmp_path: Path) -> None:
    path = tmp_path / "inflation.toml"
    path.write_text(_TABLE)
    t = load_inflation_table(path)
    assert t.differential("TWD") == pytest.approx(1.016 / 1.0212 - 1)
    assert t.url == "https://www.imf.org/external/datamapper/api/v1/PCPIPCH"


@pytest.mark.parametrize(
    ("text", "named"),
    [
        (_TABLE + _TABLE[_TABLE.index('\n[[currencies]]\ncode = "TWD"') :], "TWD appears twice"),
        (_twd("[0.018, 0.016, 0.015, 0.016]"), "TWD has 4 rates for 5 years"),
        (_twd("[0.018, 0.016, 6.0, 0.016, 0.015]"), "TWD rate 6.0"),
        (_twd("[0.018, 0.016, -0.6, 0.016, 0.015]"), "TWD rate -0.6"),
        (_TABLE.replace('vintage = "October 2026"\n', ""), "vintage"),
        (_TABLE.replace('retrieved = "2026-11-10"\n', ""), "retrieved"),
        (_TABLE.replace('code = "USD"\neconomy = "USA"', 'code = "CAD"\neconomy = "CAN"'), "USD"),
    ],
)
def test_a_bad_table_is_refused(tmp_path: Path, text: str, named: str) -> None:
    """A currency twice, a rate count that is not the years', a rate outside −50% to 500%, a
    missing ``[meta]`` field, or no USD row to restate against: each names the currency or the
    field."""
    path = tmp_path / "inflation.toml"
    path.write_text(text)
    with pytest.raises(ValueError, match=named):
        load_inflation_table(path)


def _datamapper(tmp_path: Path) -> Path:
    """A small ``PCPIPCH`` response: USA and Taiwan with 2026 to 2031, Vietnam without 2031."""
    series = {
        "USA": dict(zip(_YEARS, (2.8, 2.1, 1.9, 1.9, 1.9), strict=True)) | {"2026": 3.6},
        "TWN": dict(zip(_YEARS, (1.8, 1.6, 1.5, 1.6, 1.5), strict=True)) | {"2026": 2},
        "VNM": dict(zip(_YEARS[:4], (4.9, 4.7, 4.6, 4.2), strict=True)) | {"2026": 4.7},
    }
    path = tmp_path / "pcpipch.json"
    path.write_text(json.dumps({"values": {"PCPIPCH": series}, "api": {"version": "1"}}))
    return path


def test_the_script_writes_the_rates_as_fractions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    indicators = tmp_path / "indicators.json"
    indicators.write_text(
        json.dumps({"indicators": {"PCPIPCH": {"source": "World Economic Outlook (October 2026)"}}})
    )
    out = tmp_path / "inflation.toml"
    _script().main(
        [
            str(_datamapper(tmp_path)),
            str(out),
            "--indicators",
            str(indicators),
            "--retrieved",
            "2026-11-10",
        ]
    )
    t = load_inflation_table(out)
    usd, twd = t.rate_for("USD"), t.rate_for("TWD")
    assert usd is not None and usd.rates == (0.028, 0.021, 0.019, 0.019, 0.019)
    assert twd is not None and twd.rates == (0.018, 0.016, 0.015, 0.016, 0.015)
    assert usd.years == (2027, 2028, 2029, 2030, 2031) and usd.economy == "USA"
    assert t.rate_for("VND") is None and t.rate_for("EUR") is None
    assert (t.vintage, t.retrieved) == ("October 2026", "2026-11-10")
    assert t.source.startswith("IMF World Economic Outlook, October 2026: ")
    captured = capsys.readouterr()
    assert "VND" in captured.err and "2031" in captured.err
    assert "EUR: EURO is not in the series" in captured.err
    assert str(out) in captured.out


def test_the_script_takes_the_vintage_and_the_years_given(tmp_path: Path) -> None:
    out = tmp_path / "inflation.toml"
    _script().main(
        [
            str(_datamapper(tmp_path)),
            str(out),
            "--vintage",
            "April 2026",
            "--years",
            "2026-2029",
            "--retrieved",
            "2026-05-01",
        ]
    )
    t = load_inflation_table(out)
    usd, vnd = t.rate_for("USD"), t.rate_for("VND")
    assert usd is not None and usd.years == (2026, 2027, 2028, 2029)
    assert usd.rates == (0.036, 0.028, 0.021, 0.019)
    assert vnd is not None and vnd.rates == (0.047, 0.049, 0.047, 0.046)
    assert t.vintage == "April 2026" and t.retrieved == "2026-05-01"
