import hashlib
import re
import tomllib
from importlib import resources
from pathlib import Path

import pytest

from fairband.policy import BaseRateClass, load_policy

V1_SHA256 = "cfc46d15585c283322f50a710d3385f4921c186ed94679a542c0571a43b54bde"
V2_SHA256 = "f54a31ab4b4a6a0ca549218773191d0936de63ecce50ab5224b3511046a1070b"
V3_SHA256 = "470f3dcfad5ff8d1179face5578b48df658cf3778d8440ee8694d5324056db9b"
V4_SHA256 = "bda7ffc14dfda8dfc2d467489b5abc9c5816b04b6133de19d4ce12fd7448b903"


def _packaged_bytes() -> bytes:
    return resources.files("fairband.policy").joinpath("fairband-policy-v5.toml").read_bytes()


def test_values_match_design() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v5" and len(p.hash) == 64
    assert p.required_return == 0.09 and p.terminal_growth == 0.03
    assert p.runway_years == {"None": 5, "Narrow": 10, "Wide": 20}
    assert p.margin_of_safety == {"None": 0.45, "Narrow": 0.35, "Wide": 0.25}
    assert p.fair_band == (0.85, 1.15) and p.trim_multiple == 1.5
    assert p.wide_terminal_roic_cap == 0.13
    assert p.moat_wide_min == 8 and p.moat_narrow_min == 4
    assert len(p.base_rates) == 11
    assert p.base_rates[0] == BaseRateClass(325, 0.085, "$0-325 Mn", 0.40)
    assert p.base_rates[-1].median == 0.033 and p.inflation_addition == 0.02
    assert p.analyst_min == 5 and p.universe.cap_floor_usd == 2_000_000_000
    assert p.refresh.reuse_hours == 24 and p.refresh.gf_reuse_days == 7 and p.refresh.workers == 16


def test_carries_the_calibration_values() -> None:
    p = load_policy()
    assert p.marginal_return_span_years == 5 and p.marginal_capital_growth_min == 0.20
    assert p.fallback_return_years == 3 and p.fade_years == 5
    assert p.roic_sensitivity == (0.15, 0.09) and p.wide_terminal_roic_cap == 0.13
    assert p.required_return == 0.09 and p.terminal_growth == 0.03  # unchanged


def test_carries_the_growth_route_values() -> None:
    p = load_policy()
    assert p.high_growth_years == 5 and p.margin_convergence_year == 10
    assert p.peer_min == 3 and p.peer_margin_min_years == 5
    assert p.implied_margin_bounds == (-0.5, 1.0)
    assert p.fade_years == 5 and p.marginal_return_span_years == 5  # reused, unchanged
    assert p.universe.name_exclude_patterns[0] == r"\bnotes?\b"


def test_bounds_the_industry_fallback() -> None:
    assert load_policy().industry_peer_max == 10


def test_v5_is_the_packaged_policy() -> None:
    policy = load_policy()
    assert policy.version == "fairband-policy-v5"
    assert policy.universe.manual_admissions == ("V", "MA", "GPN")
    assert set(policy.universe.excluded_industries) >= {
        "Asset Management",
        "Financial - Capital Markets",
        "Financial - Credit Services",
        "Financial - Mortgages",
        "Financial - Conglomerates",
        "Investment - Banking & Investment Services",
    }
    assert policy.refresh.fmp_calls_per_minute == 2850
    assert policy.refresh.rate_limit_hold_s == 60
    assert policy.designation_edges == (0.65, 0.85, 1.15, 1.50)
    assert (policy.runoff_years, policy.runoff_recovery, policy.distress_sale_fraction) == (
        10,
        0.6,
        0.6,
    )
    assert (
        policy.z_distress,
        policy.z_safe,
        policy.f_score_low,
        policy.burn_cover_flag_years,
    ) == (1.1, 2.6, 1, 2)


def test_the_synthetic_rating_table_is_damodarans_fifteen_rows() -> None:
    rows = load_policy().synthetic_rating
    assert [r.rating for r in rows] == [
        "D",
        "C",
        "CC",
        "CCC",
        "B-",
        "B",
        "B+",
        "BB",
        "BB+",
        "BBB",
        "A-",
        "A",
        "A+",
        "AA",
        "AAA",
    ]
    assert rows[0].coverage_min == float("-inf")
    assert [r.coverage_min for r in rows[1:]] == [
        0.2,
        0.65,
        0.8,
        1.25,
        1.5,
        1.75,
        2,
        2.25,
        2.5,
        3,
        4.25,
        5.5,
        6.5,
        8.5,
    ]


def test_the_default_probabilities_are_table_5s_ten_year_column() -> None:
    p = load_policy().default_probability_10y
    assert p == {
        "AAA": 0.0007,
        "AA": 0.0051,
        "A+": 0.0057,
        "A": 0.0066,
        "A-": 0.05,
        "BBB": 0.0754,
        "BB+": 0.1963,
        "BB": 0.1963,
        "B+": 0.2825,
        "B": 0.368,
        "B-": 0.4212,
        "CCC": 0.5902,
        "CC": 0.666,
        "C": 0.8103,
        "D": 1.0,
    }


@pytest.mark.parametrize(
    ("old", "new", "section", "message"),
    [
        ('coverage_min = "-inf"', "coverage_min = -1e9", "synthetic_rating", "the first row"),
        ('coverage_min = "-inf"', 'coverage_min = "-infinity"', "synthetic_rating", "'-infinity'"),
        ("coverage_min = 0.65,", "coverage_min = 0.2,", "synthetic_rating", "ascend strictly"),
        ("D = 1.0", "D = 0.99", "default_probability_10y", "D must be 1.0"),
        ("AAA = 0.0007", "AAA = 1.2", "default_probability_10y", "AAA, 1.2, is outside"),
    ],
)
def test_a_malformed_distress_table_is_refused(
    tmp_path: Path, old: str, new: str, section: str, message: str
) -> None:
    """The rating rows ascend strictly from -inf (the one string allowed); every probability is
    a fraction and D's is 1."""
    text = _packaged_bytes().decode()
    assert text.count(old) == 1
    copy = tmp_path / "policy.toml"
    copy.write_text(text.replace(old, new))
    with pytest.raises(
        ValueError, match=rf"\[values\.{section}\] is malformed .*{re.escape(message)}"
    ):
        load_policy(copy)


def test_v5_is_v4_with_the_new_values() -> None:
    """Every v4 value loads unchanged from v5, save the universe's six industries and admission
    list and the refresh's pace and hold; v5 adds the ten values of the designation and the
    routes."""
    v4_file = resources.files("fairband.policy").joinpath("fairband-policy-v4.toml")
    v4 = tomllib.loads(v4_file.read_text(encoding="utf-8"))["values"]
    v5 = load_policy().raw["values"]
    assert v4.keys() <= v5.keys()
    assert v5.keys() - v4.keys() == {
        "designation_edges",
        "runoff_years",
        "runoff_recovery",
        "distress_sale_fraction",
        "synthetic_rating",
        "default_probability_10y",
        "z_distress",
        "z_safe",
        "f_score_low",
        "burn_cover_flag_years",
    }
    kept = v4.keys() - {"universe", "refresh"}
    assert {k: v5[k] for k in kept} == {k: v4[k] for k in kept}
    u4, u5 = v4["universe"]["value"], v5["universe"]["value"]
    industries4 = u4.pop("excluded_industries")
    industries5 = u5.pop("excluded_industries")
    assert (
        industries5[: len(industries4)] == industries4 and len(industries5) == len(industries4) + 6
    )
    assert u5.pop("manual_admissions") == ["V", "MA", "GPN"] and u5 == u4
    r4, r5 = v4["refresh"]["value"], v5["refresh"]["value"]
    assert {
        k: v for k, v in r5.items() if k not in {"fmp_calls_per_minute", "rate_limit_hold_s"}
    } == r4


def test_v4_is_v3_with_the_industry_bound() -> None:
    """Every v3 value loads unchanged from v4; v4 adds only ``industry_peer_max``."""
    files = resources.files("fairband.policy")
    v3_file, v4_file = (
        files.joinpath("fairband-policy-v3.toml"),
        files.joinpath("fairband-policy-v4.toml"),
    )
    v3 = tomllib.loads(v3_file.read_text(encoding="utf-8"))
    v4 = tomllib.loads(v4_file.read_text(encoding="utf-8"))
    assert v4["values"].keys() - v3["values"].keys() == {"industry_peer_max"}
    assert {k: v for k, v in v4["values"].items() if k != "industry_peer_max"} == v3["values"]
    assert v4["meta"] == {"version": "fairband-policy-v4"}
    assert v3["meta"] == {"version": "fairband-policy-v3"}


def test_base_rates_carry_the_ninetieth_percentile_sales_growth() -> None:
    """The cap on the revenue-growth route's held rate, by sales class, as the book prints it:
    the smallest class's 40% below the next class's 45%."""
    p = load_policy()
    assert p.base_rates[1].sales_p90_5y == 0.45
    assert p.base_rates[2].sales_p90_5y == 0.20
    assert p.base_rates[-1].sales_p90_5y == 0.15
    assert [c.sales_p90_5y for c in p.base_rates] == [
        0.40,
        0.45,
        0.20,
        0.20,
        0.20,
        0.20,
        0.20,
        0.15,
        0.15,
        0.15,
        0.15,
    ]


def test_v4_is_unchanged() -> None:
    data = resources.files("fairband.policy").joinpath("fairband-policy-v4.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V4_SHA256


def test_v3_file_is_unchanged() -> None:
    data = resources.files("fairband.policy").joinpath("fairband-policy-v3.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V3_SHA256


def test_v2_file_is_unchanged() -> None:
    data = resources.files("fairband.policy").joinpath("fairband-policy-v2.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V2_SHA256


def test_v1_file_is_unchanged() -> None:
    data = resources.files("fairband.policy").joinpath("fairband-policy-v1.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V1_SHA256


def test_return_measure_note_is_recorded() -> None:
    raw = load_policy().raw
    note = raw["values"]["return_measure"]
    assert "value" not in note and "Return on invested capital" in note["note"]
    assert "source" in note


def test_every_value_has_a_source_line() -> None:
    raw = load_policy().raw
    for section, values in raw["values"].items():
        assert "source" in values, section


def test_hash_is_sha256_of_the_file_bytes(tmp_path: Path) -> None:
    copy = tmp_path / "policy.toml"
    copy.write_bytes(_packaged_bytes())
    expected = hashlib.sha256(_packaged_bytes()).hexdigest()
    assert load_policy().hash == load_policy(copy).hash == expected
    copy.write_bytes(_packaged_bytes() + b"\n# an edit\n")
    assert load_policy(copy).hash != expected


@pytest.mark.parametrize("section", ["required_return", "universe"])
def test_missing_value_names_its_section(tmp_path: Path, section: str) -> None:
    text = _packaged_bytes().decode()
    copy = tmp_path / "policy.toml"
    copy.write_text(text.replace(f"[values.{section}", f"[values.renamed_{section}"))
    with pytest.raises(ValueError, match=rf"\[values\.{section}\]"):
        load_policy(copy)


@pytest.mark.parametrize(
    ("symbol", "excluded"),
    [
        ("BRK.B", False),
        ("BF.A", False),
        ("ACME", False),
        ("XYZ.U", True),
        ("XYZ-U", True),
        ("ABC-PA", True),
        ("ABC.PA", True),
        ("DEF.WS", True),
        ("DEF-WS", True),
        ("GHI.R", True),
        ("GHI-R", True),
    ],
)
def test_symbol_patterns_match_both_vendor_forms(symbol: str, excluded: bool) -> None:
    """FMP's dash and the exchange's dot (``screener_rows`` turns ``XYZ-U`` into ``XYZ.U``); a
    share class such as ``BRK.B`` is not a preferred, warrant, unit or right."""
    patterns = load_policy().universe.symbol_exclude_patterns
    assert any(re.search(pattern, symbol) for pattern in patterns) is excluded
