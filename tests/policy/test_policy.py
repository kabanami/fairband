import hashlib
import re
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from fairband.policy import BaseRateClass, load_policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH, SETTINGS

V1_SHA256 = "cfc46d15585c283322f50a710d3385f4921c186ed94679a542c0571a43b54bde"
V2_SHA256 = "f54a31ab4b4a6a0ca549218773191d0936de63ecce50ab5224b3511046a1070b"
V3_SHA256 = "470f3dcfad5ff8d1179face5578b48df658cf3778d8440ee8694d5324056db9b"
V4_SHA256 = "bda7ffc14dfda8dfc2d467489b5abc9c5816b04b6133de19d4ce12fd7448b903"
V5_SHA256 = "809a5fa620dfdd862d1ceb62e200694b1a20df869029e36c7e44c0e699ac96f2"
V6_SHA256 = "393d0f68f8fa5c67ce7f0a662c7cdfb4775e4709b28f1f85a3d43d628940d4ac"
V7_SHA256 = "c964db4e36f8e233b866244b26db1c468f3c64f13e0c0bea985a0dbb8c551c91"
V8_SHA256 = "129b080fff5d759e2b76cfe2d73ddfbcda68db8a50980d90ff7b4592c6cf8f06"
V9_SHA256 = "31015452f41a00c3040688280a30eaad9473dfdb0dda9b78c6ee241ef3d0ea0a"
V10_SHA256 = "09d375d874f9009303c0d9297fee53d4083ce42a48bb515b23982114042cccbd"
# The six values policy v8 adds for the agents (spec 2026-11-06 Tier 2, section 19).
V8_VALUES = {
    "override_ranges",
    "override_primary_evidence_above_p90",
    "secondary_parts_max",
    "secondary_years_min",
    "secondary_years_max",
    "stance_words",
}
# The value policy v9 adds, the secondary valuation's driver ranges; it also adds three pairs to
# ``override_ranges``, the cycle gap's and the two NTM anchors' (spec 2026-11-06 Tier 2 as amended
# 2026-11-07, section 19).
V9_VALUES = {"secondary_driver_ranges"}
# The two values policy v10 adds, the step-series gap and the split tolerance; it also adds two
# pairs to ``override_ranges``, the outside value's and the diluted count's (spec 2026-11-09,
# section 11).
V10_VALUES = {"step_series_gap_max", "split_implied_count_tolerance"}
# The two values policy v11 adds, the inflation bound and the stale-rate bound; it also adds the
# rate history depth to ``refresh`` (spec 2026-11-10, section 9).
V11_VALUES = {"inflation_max", "fx_stale_days"}
V11_SHA256 = "97b03abbddcf6c8dccec9a61b56e4d2248c152e85a365dc2119667ee62992c95"
# The value policy v12 adds, the cap on the return read on capital without goodwill and
# intangibles (method 4.6 rule 5; founder 2026-11-12).
V12_VALUES = {"return_without_goodwill_cap"}
V12_SHA256 = "eb1bb08f7f03676d83e97a2a61c0d82695f7c34a22e9308dd25135f3af908957"
# The four values policy v13 adds, the three stock-pay thresholds and the share-count band; it
# also adds the trailing stock pay's pair to ``override_ranges`` and widens the runway return's
# (spec 2026-11-13, sections 7.1, 8, 10 and 14).
V13_VALUES = {
    "sbc_material_share",
    "sbc_basis_tax_share",
    "sbc_basis_gap_multiple",
    "share_count_gap_band",
}
V13_SHA256 = "f2ec6e5841f35a7068a4c733ca52fc9a9daa6dacea3d6d9131a21616803a83d0"
V14_SHA256 = "fc70b926134b6c8d8f2583128e4c2394701358d5f50330786e9c433a39a4bbc1"
# The value policy v15 adds, the multiple of the note sheet-shift (spec 2026-11-13, section 12.5).
V15_VALUES = {"sheet_shift_multiple"}
V15_SHA256 = "c86d987799e4d15575812ffe452472bc2d716cff744f78aa00575d8239f3f34b"
# The four pairs policy v16 adds to ``override_ranges``, as the file writes them: the committed
# shares', the one-time item's and the two revenue steps' (spec 2026-11-14, section 10).
V16_RANGES = {
    "shares.committed": [0.0, 1e12],
    "earnings.ntm_nri": [-100.0, 100.0],
    "revenue.step_2": [-0.80, 3.00],
    "revenue.step_3": [-0.80, 3.00],
}
# The value policy v16 adds, the size above which a thin revenue step is not read (spec 2026-11-14,
# sections 6.2 and 10, as narrowed on 2026-11-15).
V16_VALUES = {"thin_revenue_step_max"}
BAND_RULE = "the low must be below 1 and the high above 1"


def _packaged_bytes() -> bytes:
    return resources.files("fairband.policy").joinpath("fairband-policy-v16.toml").read_bytes()


def _file_values(name: str) -> dict[str, Any]:
    """The ``[values]`` of a packaged policy file, read as TOML without the loader."""
    data = resources.files("fairband.policy").joinpath(name).read_text(encoding="utf-8")
    values: dict[str, Any] = tomllib.loads(data)["values"]
    return values


def _packaged_with(tmp_path: Path, name: str, value: str) -> Path:
    """A copy of the packaged file with ``[values.<name>]``'s value written as ``value``."""
    text = _packaged_bytes().decode()
    old = f"[values.{name}]\nvalue = "
    assert text.count(old) == 1
    start = text.index(old) + len(old)
    end = text.index("\n", start)
    copy = tmp_path / "policy.toml"
    copy.write_text(text[:start] + value + text[end:])
    return copy


def test_values_match_design() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v16" and len(p.hash) == 64
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


def test_v16_is_the_packaged_policy() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v16"
    assert p.override_ranges["shares.committed"] == (0.0, 1e12)
    assert p.override_ranges["earnings.ntm_nri"] == (-100.0, 100.0)
    assert p.override_ranges["revenue.step_2"] == (-0.80, 3.00)
    assert p.override_ranges["revenue.step_3"] == (-0.80, 3.00)


def test_v15_holds_the_sheet_shift_multiple() -> None:
    """The v15 file's own value, read without the loader, which loads v16."""
    v15 = _file_values("fairband-policy-v15.toml")
    assert v15["sheet_shift_multiple"]["value"] == 3.0


def test_v14_holds_the_minority_range() -> None:
    """The v14 file's own range, read without the loader, which loads v16."""
    v14 = _file_values("fairband-policy-v14.toml")
    assert v14["override_ranges"]["value"]["balance.minority"] == [0.0, 1e15]


def test_v13_holds_its_four_values_and_two_ranges() -> None:
    """The v13 file's own values, read without the loader, which loads v16."""
    v13 = _file_values("fairband-policy-v13.toml")
    assert (
        v13["sbc_material_share"]["value"],
        v13["sbc_basis_tax_share"]["value"],
        v13["sbc_basis_gap_multiple"]["value"],
    ) == (0.02, 0.5, 10.0)
    assert v13["share_count_gap_band"]["value"] == [0.7, 1.3]
    assert v13["override_ranges"]["value"]["return.runway"] == [0.0, 5.0]
    assert v13["override_ranges"]["value"]["earnings.sbc"] == [0.0, 1e15]


def test_the_packaged_policy_keeps_the_earlier_versions_values() -> None:
    """The values v8 to v13 added, as v16 carries them; the override ranges as v16 has them,
    the minority interest's that v14 adds and the four that v16 adds among them."""
    policy = load_policy()
    assert (
        policy.sbc_material_share,
        policy.sbc_basis_tax_share,
        policy.sbc_basis_gap_multiple,
    ) == (0.02, 0.5, 10.0)
    assert policy.share_count_gap_band == (0.7, 1.3)
    assert policy.return_without_goodwill_cap == 0.25
    assert policy.inflation_max == 0.10
    assert policy.fx_stale_days == 7
    assert policy.refresh.fx_history_years == 3
    assert policy.step_series_gap_max == 0.05
    assert policy.split_implied_count_tolerance == 0.15
    assert policy.override_ranges["value.outside"] == (-1000.0, 1000.0)
    assert policy.override_ranges["shares.diluted"] == (0.0, 1e12)
    assert policy.override_ranges == {
        "growth.belief": (-0.20, 0.60),
        "path.hold": (-0.20, 3.00),
        "path.step_2": (-0.80, 3.00),
        "path.step_3": (-0.80, 3.00),
        "margin.target": (-0.50, 0.60),
        "capital.sales_to_capital": (0.1, 10.0),
        "return.runway": (0.0, 5.0),
        "earnings.nri_gap": (-100.0, 100.0),
        "earnings.cycle_gap": (-100.0, 100.0),
        "earnings.ntm": (0.0, 1000.0),
        "revenue.ntm": (0.0, 1e15),
        "decline.rate": (-0.50, 0.0),
        "balance.debt": (0.0, 1e15),
        "balance.cash": (0.0, 1e15),
        "value.outside": (-1000.0, 1000.0),
        "shares.diluted": (0.0, 1e12),
        "earnings.sbc": (0.0, 1e15),
        "balance.minority": (0.0, 1e15),
        "shares.committed": (0.0, 1e12),
        "earnings.ntm_nri": (-100.0, 100.0),
        "revenue.step_2": (-0.80, 3.00),
        "revenue.step_3": (-0.80, 3.00),
    }
    assert policy.override_primary_evidence_above_p90 is True
    assert (
        policy.secondary_parts_max,
        policy.secondary_years_min,
        policy.secondary_years_max,
    ) == (10, 3, 15)
    assert policy.stance_words == ("buy", "hold", "trim", "avoid")
    assert policy.secondary_driver_ranges == {
        "revenue_growth": (-0.80, 3.00),
        "operating_margin": (-0.50, 0.60),
        "tax_rate": (0.0, 0.50),
        "sales_to_capital": (0.1, 10.0),
    }
    for name in sorted(V8_VALUES | V9_VALUES | V10_VALUES | V11_VALUES | V12_VALUES | V13_VALUES):
        assert policy.raw["values"][name]["source"].strip(), name
    assert policy.own_sales_to_capital_min_share == 0.5
    assert policy.loss_ramp_margin_bound == -1.0
    for name in ("own_sales_to_capital_min_share", "loss_ramp_margin_bound"):
        assert policy.raw["values"][name]["source"].strip(), name
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


def test_derives_the_edges_and_the_wide_cap() -> None:
    p = load_policy()
    assert p.designation_edges == (0.65, 0.85, 1.15, 1.5)
    assert p.wide_terminal_roic_cap == 0.13
    assert p.wide_terminal_roic_spread == 0.04 and p.repricing_horizon_years == 3
    assert p.settings_hash == EMPTY_SETTINGS_HASH
    assert "designation_edges" not in p.raw["values"]


def test_v8_is_v7_with_the_six_values_added() -> None:
    """Every v7 value loads unchanged from v8; v8 adds the override ranges, the evidence rule, the
    secondary valuation's bounds and the stance words, none a setting (spec 2026-11-06 Tier 2,
    section 19)."""
    v7 = _file_values("fairband-policy-v7.toml")
    v8 = _file_values("fairband-policy-v8.toml")
    assert v8.keys() - v7.keys() == V8_VALUES
    assert {k: v8[k] for k in v7} == v7
    assert not {s.name for s in SETTINGS} & V8_VALUES


def test_v9_is_v8_with_the_values_added() -> None:
    """Every v8 value loads unchanged from v9, save the override ranges, which gain the cycle gap's
    pair and the two NTM anchors'; v9 adds the secondary valuation's driver ranges, neither a
    setting (spec 2026-11-06 Tier 2 as amended 2026-11-07, section 19)."""
    v8 = _file_values("fairband-policy-v8.toml")
    v9 = _file_values("fairband-policy-v9.toml")
    assert v9.keys() - v8.keys() == V9_VALUES
    kept = v8.keys() - {"override_ranges"}
    assert {k: v9[k] for k in kept} == {k: v8[k] for k in kept}
    ranges8, ranges9 = v8["override_ranges"], v9["override_ranges"]
    assert ranges9["value"] == ranges8["value"] | {
        "earnings.cycle_gap": [-100.0, 100.0],
        "earnings.ntm": [0.0, 1000.0],
        "revenue.ntm": [0.0, 1e15],
    }
    assert ranges9["source"] == ranges8["source"]
    assert "the cycle gap" in ranges9["note"] and "the two NTM anchors" in ranges9["note"]
    assert "a multiple for sales-to-capital" in v9["secondary_driver_ranges"]["note"]
    assert not {s.name for s in SETTINGS} & (V9_VALUES | {"override_ranges"})


def test_v10_is_v9_with_the_four_values_added() -> None:
    """Every v9 value loads unchanged from v10, save the override ranges, which gain the outside
    value's pair and the diluted count's; v10 adds the step-series gap and the split tolerance,
    none a setting (spec 2026-11-09, section 11)."""
    v9 = _file_values("fairband-policy-v9.toml")
    v10 = _file_values("fairband-policy-v10.toml")
    assert v10.keys() - v9.keys() == V10_VALUES
    kept = v9.keys() - {"override_ranges"}
    assert {k: v10[k] for k in kept} == {k: v9[k] for k in kept}
    ranges9, ranges10 = v9["override_ranges"], v10["override_ranges"]
    assert ranges10["value"] == ranges9["value"] | {
        "value.outside": [-1000.0, 1000.0],
        "shares.diluted": [0.0, 1e12],
    }
    assert ranges10["source"] == ranges9["source"]
    assert "the outside value" in ranges10["note"] and "the diluted count" in ranges10["note"]
    assert not {s.name for s in SETTINGS} & (V10_VALUES | {"override_ranges"})


def test_v11_is_v10_with_the_three_values_added() -> None:
    """Every v10 value loads unchanged from v11, save the refresh values, which gain the rate
    history depth and its source; v11 adds the inflation bound and the stale-rate bound, none a
    setting (spec 2026-11-10, section 9)."""
    v10 = _file_values("fairband-policy-v10.toml")
    v11 = _file_values("fairband-policy-v11.toml")
    assert v11.keys() - v10.keys() == V11_VALUES
    kept = v10.keys() - {"refresh"}
    assert {k: v11[k] for k in kept} == {k: v10[k] for k in kept}
    refresh10, refresh11 = v10["refresh"], v11["refresh"]
    assert refresh11["value"] == refresh10["value"] | {"fx_history_years": 3}
    assert refresh11["source"].startswith(refresh10["source"] + "; fx_history_years: ")
    assert "spec 2026-11-10" in refresh11["source"]
    for name in V11_VALUES:
        assert "spec 2026-11-10" in v11[name]["source"], name
    settings = {s.name for s in SETTINGS}
    assert not settings & V11_VALUES and "refresh.fx_history_years" not in settings


def test_v12_is_v11_with_the_cap_added() -> None:
    """Every v11 value loads unchanged from v12; v12 adds the cap on the return read on capital
    without goodwill and intangibles, not a setting (method 4.6 rule 5)."""
    v11 = _file_values("fairband-policy-v11.toml")
    v12 = _file_values("fairband-policy-v12.toml")
    assert v12.keys() - v11.keys() == V12_VALUES
    assert {k: v12[k] for k in v11} == v11
    assert "founder 2026-11-12" in v12["return_without_goodwill_cap"]["source"]
    assert "no source gives the number" in v12["return_without_goodwill_cap"]["source"]
    assert not {s.name for s in SETTINGS} & V12_VALUES


def test_v13_is_v12_with_the_four_values_added_and_two_ranges() -> None:
    """Every v12 value loads unchanged from v13 but the override ranges, which gain
    ``earnings.sbc`` and widen ``return.runway``; each new value's source names the spec."""
    v12 = _file_values("fairband-policy-v12.toml")
    v13 = _file_values("fairband-policy-v13.toml")
    assert v13.keys() - v12.keys() == V13_VALUES
    kept = v12.keys() - {"override_ranges"}
    assert {k: v13[k] for k in kept} == {k: v12[k] for k in kept}
    old, new = v12["override_ranges"]["value"], v13["override_ranges"]["value"]
    assert new == old | {"return.runway": [0.0, 5.0], "earnings.sbc": [0.0, 1e15]}
    for name in V13_VALUES:
        assert "spec 2026-11-13" in v13[name]["source"], name
    assert v13["override_ranges"]["source"] == v12["override_ranges"]["source"]
    assert "the trailing stock pay" in v13["override_ranges"]["note"]
    assert not {s.name for s in SETTINGS} & V13_VALUES


def test_v14_is_v13_with_the_minority_range() -> None:
    """v14 adds no value: every v13 value loads unchanged but the override ranges, which gain
    ``balance.minority``, and their note names it."""
    v13 = _file_values("fairband-policy-v13.toml")
    v14 = _file_values("fairband-policy-v14.toml")
    assert v14.keys() == v13.keys()
    kept = v13.keys() - {"override_ranges"}
    assert {k: v14[k] for k in kept} == {k: v13[k] for k in kept}
    old, new = v13["override_ranges"]["value"], v14["override_ranges"]["value"]
    assert new == old | {"balance.minority": [0.0, 1e15]}
    assert "balance.minority" in v14["override_ranges"]["note"]


def test_v15_is_v14_with_the_one_value_added() -> None:
    """Every v14 value loads unchanged from v15; the one new key is the multiple of the note
    sheet-shift, its source naming the spec, and it is no setting."""
    v14 = _file_values("fairband-policy-v14.toml")
    v15 = _file_values("fairband-policy-v15.toml")
    assert v15.keys() - v14.keys() == V15_VALUES and v14.keys() <= v15.keys()
    assert {k: v15[k] for k in v14} == v14
    assert v15["sheet_shift_multiple"]["value"] == 3.0
    assert "spec 2026-11-13" in v15["sheet_shift_multiple"]["source"]
    assert not {s.name for s in SETTINGS} & V15_VALUES


def test_v16_is_v15_with_the_four_ranges_and_the_one_value() -> None:
    """Every v15 value loads unchanged from v16 but the override ranges, which gain the pairs of
    ``shares.committed``, ``earnings.ntm_nri``, ``revenue.step_2`` and ``revenue.step_3``, their
    note gaining one sentence naming each new tag and the spec; and the one new key is
    ``thin_revenue_step_max``, 50%, its source naming spec 2026-11-14 6.2, no setting."""
    v15 = _file_values("fairband-policy-v15.toml")
    v16 = load_policy().raw["values"]
    assert v16.keys() - v15.keys() == V16_VALUES and v15.keys() <= v16.keys()
    assert v16["thin_revenue_step_max"]["value"] == 0.5
    assert "spec 2026-11-14, section 6.2" in v16["thin_revenue_step_max"]["source"]
    assert load_policy().thin_revenue_step_max == 0.5
    assert not {s.name for s in SETTINGS} & V16_VALUES
    kept = v15.keys() - {"override_ranges"}
    assert {k: v16[k] for k in kept} == {k: v15[k] for k in kept}
    old, new = v15["override_ranges"], v16["override_ranges"]
    assert new["value"] == old["value"] | V16_RANGES
    assert new["source"] == old["source"]
    assert new["note"].startswith(old["note"] + " ")
    added = new["note"].removeprefix(old["note"] + " ")
    for tag in V16_RANGES:
        assert tag in added, tag
    assert "spec 2026-11-14" in added


@pytest.mark.parametrize(
    ("name", "value", "rule"),
    [
        ("sbc_material_share", "-0.01", "sbc_material_share: must be from 0% to 100%"),
        ("sbc_material_share", "1.01", "sbc_material_share: must be from 0% to 100%"),
        ("sbc_material_share", "nan", "sbc_material_share: must be from 0% to 100%"),
        ("sbc_basis_tax_share", "-0.01", "sbc_basis_tax_share: must be from 0% to 100%"),
        ("sbc_basis_tax_share", "1.01", "sbc_basis_tax_share: must be from 0% to 100%"),
        ("sbc_basis_tax_share", "nan", "sbc_basis_tax_share: must be from 0% to 100%"),
        ("sbc_basis_gap_multiple", "0.0", "sbc_basis_gap_multiple: must be above 0"),
        ("sbc_basis_gap_multiple", "-1.0", "sbc_basis_gap_multiple: must be above 0"),
        ("sbc_basis_gap_multiple", "nan", "sbc_basis_gap_multiple: must be above 0"),
        ("sbc_basis_gap_multiple", "inf", "sbc_basis_gap_multiple: must be above 0"),
        ("share_count_gap_band", "[1.0, 1.3]", "share_count_gap_band: " + BAND_RULE),
        ("share_count_gap_band", "[0.7, 1.0]", "share_count_gap_band: " + BAND_RULE),
        ("share_count_gap_band", "[1.3, 0.7]", "share_count_gap_band: " + BAND_RULE),
        ("share_count_gap_band", "[nan, 1.3]", "share_count_gap_band: " + BAND_RULE),
        ("share_count_gap_band", "[0.7, inf]", "share_count_gap_band: " + BAND_RULE),
    ],
)
def test_a_v13_value_outside_its_range_is_refused(
    tmp_path: Path, name: str, value: str, rule: str
) -> None:
    """None is a setting, so the file is the only way in; ``load_policy`` checks all four. A NaN
    or an infinity is outside every range."""
    with pytest.raises(ValueError, match=f"^{re.escape(rule)}$"):
        load_policy(_packaged_with(tmp_path, name, value))


@pytest.mark.parametrize(
    ("name", "value", "read"),
    [
        ("sbc_material_share", "0.0", 0.0),
        ("sbc_material_share", "1.0", 1.0),
        ("sbc_basis_tax_share", "0.0", 0.0),
        ("sbc_basis_tax_share", "1.0", 1.0),
        ("sbc_basis_gap_multiple", "0.001", 0.001),
        ("share_count_gap_band", "[0.999, 1.001]", (0.999, 1.001)),
    ],
)
def test_the_v13_values_at_their_ends_load(
    tmp_path: Path, name: str, value: str, read: object
) -> None:
    assert getattr(load_policy(_packaged_with(tmp_path, name, value)), name) == read


@pytest.mark.parametrize("value", ["0.20", "0.09", "1.01", "nan"])
def test_a_cap_outside_its_range_is_refused(tmp_path: Path, value: str) -> None:
    """The cap is no setting, so the file is the only way in. It stays above 20%, the highest
    required return a setting allows, so the capped return is always above r."""
    rule = "return_without_goodwill_cap: must be above 20% and at most 100%"
    with pytest.raises(ValueError, match=f"^{re.escape(rule)}$"):
        load_policy(_packaged_with(tmp_path, "return_without_goodwill_cap", value))


@pytest.mark.parametrize("value", ["0.201", "1.0"])
def test_a_cap_at_either_end_loads(tmp_path: Path, value: str) -> None:
    policy = load_policy(_packaged_with(tmp_path, "return_without_goodwill_cap", value))
    assert policy.return_without_goodwill_cap == float(value)


@pytest.mark.parametrize(
    ("name", "value", "rule"),
    [
        ("inflation_max", "0.0", "inflation_max: must be above 0 and below 1"),
        ("inflation_max", "-0.05", "inflation_max: must be above 0 and below 1"),
        ("inflation_max", "1.0", "inflation_max: must be above 0 and below 1"),
        ("inflation_max", "nan", "inflation_max: must be above 0 and below 1"),
        ("fx_stale_days", "0", "fx_stale_days: must be at least 1 day"),
    ],
)
def test_a_v11_value_outside_its_range_is_refused(
    tmp_path: Path, name: str, value: str, rule: str
) -> None:
    """Neither is a setting, so the file is the only way in; ``load_policy`` checks both."""
    with pytest.raises(ValueError, match=f"^{re.escape(rule)}$"):
        load_policy(_packaged_with(tmp_path, name, value))


def _history_years(tmp_path: Path, years: int) -> Path:
    """A copy of the packaged file with ``refresh.fx_history_years`` set to ``years``."""
    text = _packaged_bytes().decode()
    old = "\nfx_history_years = 3\n"
    assert text.count(old) == 1
    copy = tmp_path / "policy.toml"
    copy.write_text(text.replace(old, f"\nfx_history_years = {years}\n"))
    return copy


def test_a_rate_history_shorter_than_a_year_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"^refresh\.fx_history_years: must be at least 1 year$"):
        load_policy(_history_years(tmp_path, 0))


def test_the_v11_values_at_their_ends_load(tmp_path: Path) -> None:
    assert load_policy(_packaged_with(tmp_path, "inflation_max", "0.001")).inflation_max == 0.001
    assert load_policy(_packaged_with(tmp_path, "inflation_max", "0.999")).inflation_max == 0.999
    assert load_policy(_packaged_with(tmp_path, "fx_stale_days", "1")).fx_stale_days == 1
    assert load_policy(_history_years(tmp_path, 1)).refresh.fx_history_years == 1


@pytest.mark.parametrize(
    ("name", "rule"),
    [
        ("step_series_gap_max", "step_series_gap_max: must be from 0 to 50 points"),
        ("split_implied_count_tolerance", "split_implied_count_tolerance: must be from 0% to 50%"),
    ],
)
@pytest.mark.parametrize("value", ["-0.01", "0.51"])
def test_a_v10_value_outside_its_range_is_refused(
    tmp_path: Path, name: str, rule: str, value: str
) -> None:
    """Neither is a setting, so the file is the only way in; ``load_policy`` checks both."""
    with pytest.raises(ValueError, match=f"^{re.escape(rule)}$"):
        load_policy(_packaged_with(tmp_path, name, value))


@pytest.mark.parametrize("name", sorted(V10_VALUES))
@pytest.mark.parametrize("value", ["0.0", "0.5"])
def test_a_v10_value_at_either_end_loads(tmp_path: Path, name: str, value: str) -> None:
    assert getattr(load_policy(_packaged_with(tmp_path, name, value)), name) == float(value)


def test_a_driver_range_that_does_not_ascend_is_refused(tmp_path: Path) -> None:
    text = _packaged_bytes().decode()
    old = "tax_rate = [0.0, 0.50]"
    assert text.count(old) == 1
    copy = tmp_path / "policy.toml"
    copy.write_text(text.replace(old, "tax_rate = [0.50, 0.0]"))
    with pytest.raises(
        ValueError, match=r"\[values\.secondary_driver_ranges\] is malformed .*tax_rate"
    ):
        load_policy(copy)


@pytest.mark.parametrize("pair", ["[0.60, 0.60]", "[0.60, -0.20]"])
def test_an_override_range_that_does_not_ascend_is_refused(tmp_path: Path, pair: str) -> None:
    """A range's low must be below its high."""
    text = _packaged_bytes().decode()
    old = '"growth.belief" = [-0.20, 0.60]'
    assert text.count(old) == 1
    copy = tmp_path / "policy.toml"
    copy.write_text(text.replace(old, f'"growth.belief" = {pair}'))
    with pytest.raises(
        ValueError, match=r"\[values\.override_ranges\] is malformed .*growth\.belief"
    ):
        load_policy(copy)


def test_v7_is_v6_with_the_two_values_added() -> None:
    """Every v6 value loads unchanged from v7; v7 adds the growth routes' own sales-to-capital
    bound and the loss ramp bound, neither a setting (spec 2026-11-06 section 11)."""
    v6 = _file_values("fairband-policy-v6.toml")
    v7 = _file_values("fairband-policy-v7.toml")
    assert v6.keys() <= v7.keys()
    assert v7.keys() - v6.keys() == {"own_sales_to_capital_min_share", "loss_ramp_margin_bound"}
    assert {k: v7[k] for k in v6} == v6
    assert v7["own_sales_to_capital_min_share"]["value"] == 0.5
    assert v7["loss_ramp_margin_bound"]["value"] == -1.0
    assert not {s.name for s in SETTINGS} & (v7.keys() - v6.keys())


def test_v6_is_v5_with_the_two_values_swapped() -> None:
    """Every v5 value loads unchanged from v6, save the edges and the Wide cap, which v6 derives;
    v6 adds the Wide spread and the repricing horizon (spec 2026-11-04 8.3)."""
    v5 = _file_values("fairband-policy-v5.toml")
    v6 = _file_values("fairband-policy-v6.toml")
    assert v5.keys() - v6.keys() == {"designation_edges", "wide_terminal_roic_cap"}
    assert v6.keys() - v5.keys() == {"wide_terminal_roic_spread", "repricing_horizon_years"}
    kept = v5.keys() & v6.keys()
    assert {k: v6[k] for k in kept} == {k: v5[k] for k in kept}
    assert v6["wide_terminal_roic_spread"]["value"] == 0.04
    assert v6["repricing_horizon_years"]["value"] == 3
    assert v5["designation_edges"]["value"] == list(load_policy().designation_edges)
    assert v5["wide_terminal_roic_cap"]["value"] == load_policy().wide_terminal_roic_cap


def test_v5_is_v4_with_the_new_values() -> None:
    """Every v4 value loads unchanged from v5, save the universe's six industries and admission
    list and the refresh's pace and hold; v5 adds the ten values of the designation and the
    routes."""
    v4 = _file_values("fairband-policy-v4.toml")
    v5 = _file_values("fairband-policy-v5.toml")
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


def test_v15_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v15`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v15.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V15_SHA256


def test_v14_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v14`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v14.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V14_SHA256


def test_v13_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v13`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v13.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V13_SHA256


def test_v12_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v12`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v12.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V12_SHA256


def test_v11_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v11`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v11.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V11_SHA256


def test_v10_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v10`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v10.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V10_SHA256


def test_v9_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v9`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v9.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V9_SHA256


def test_v8_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v8`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v8.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V8_SHA256


def test_v7_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v7`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v7.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V7_SHA256


def test_v6_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v6`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v6.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V6_SHA256


def test_v5_file_is_unchanged() -> None:
    data = resources.files("fairband.policy").joinpath("fairband-policy-v5.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V5_SHA256


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
