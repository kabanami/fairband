"""The settings catalogue, the overlay and the range checks (spec 2026-11-04 8.2 to 8.4, 8.9)."""

import hashlib
import math
import re
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from fairband.policy import load_policy
from fairband.policy.settings import (
    EMPTY_SETTINGS_HASH,
    SETTINGS,
    apply_overlay,
    check,
    default_of,
    exchange_symbol,
    setting,
    settings_hash,
    value_of,
)


def test_forty_settings_in_the_spec_order() -> None:
    # spec 2026-11-04 8.2's forty, and the cap on the return without goodwill (the founder's
    # ruling of 2026-11-15, B-170), which follows the Wide spread; less GuruFocus's reuse window,
    # which policy v18 drops (spec 2026-11-19 8.9), so the FMP window is the last
    assert len(SETTINGS) == 40
    assert [s.name for s in SETTINGS[:3]] == ["required_return", "terminal_growth", "runway_years"]
    assert SETTINGS[-1].name == "refresh.reuse_hours"
    assert {s.group for s in SETTINGS} == {"valuation", "flags", "validity", "universe", "refresh"}
    with pytest.raises(KeyError):
        setting("refresh.gf_reuse_days")


def test_the_groups_run_in_the_spec_order_and_each_name_once() -> None:
    order = ("valuation", "flags", "validity", "universe", "refresh")
    groups = [s.group for s in SETTINGS]
    assert groups == sorted(groups, key=order.index)
    assert [groups.count(g) for g in order] == [20, 9, 2, 5, 4]
    assert len({s.name for s in SETTINGS}) == 40


def test_the_catalogue_rows_read_as_the_spec_tables() -> None:
    r = setting("required_return")
    assert (r.label, r.unit, r.effect, r.range_text, r.hashed) == (
        "Hurdle rate r",
        "fraction",
        "revalue",
        "4% to 20%, above g_T",
        True,
    )
    aging = setting("aging_fraction")
    assert (aging.effect, aging.hashed, aging.range_text) == ("at once", False, "10% to 95%")
    hold = setting("refresh.rate_limit_hold_s")
    assert (hold.label, hold.unit, hold.effect, hold.range_text) == (
        "Hold after a 429",
        "seconds",
        "run",
        "1 to 3,600, finite",
    )
    bands = setting("universe.cap_bands")
    assert (bands.unit, bands.effect, bands.range_text) == (
        "cap_bands",
        "full",
        "descending; the lowest equals the size floor",
    )
    assert all(s.description.endswith(".") and len(s.description.split()) <= 25 for s in SETTINGS)
    # spec 2026-11-06 6.1: past year 3 a thin year ends a Decline row's consensus, unflagged
    analysts = setting("analyst_min")
    assert (analysts.effect, analysts.hashed) == ("revalue", True)
    assert "past year 3 it ends a Decline row's consensus" in analysts.description
    # spec 2026-11-14 6.2: a revenue step landing on a thin year is not read on Mature Growth
    assert "Mature Growth skips its revenue step above 50%" in analysts.description
    with pytest.raises(KeyError):
        setting("designation_edges")


def test_the_cap_on_the_return_without_goodwill_is_a_setting() -> None:
    """The founder's ruling of 2026-11-15 (B-170): the cap of method 4.6 rule 5 is the user's to
    move, in the valuation group right after the Wide spread, read at a revalue and hashed."""
    cap = setting("return_without_goodwill_cap")
    assert (cap.group, cap.label, cap.unit, cap.effect, cap.range_text, cap.hashed) == (
        "valuation",
        "Cap on the return without goodwill",
        "fraction",
        "revalue",
        "above 20%, up to 100%",
        True,
    )
    names = [s.name for s in SETTINGS]
    assert names.index(cap.name) == names.index("wide_terminal_roic_spread") + 1
    base = load_policy()
    assert default_of(cap.name, base) == value_of(cap.name, base) == 0.25
    moved = apply_overlay(base, {"return_without_goodwill_cap": 0.30})
    assert moved.return_without_goodwill_cap == 0.30 and moved.version == base.version
    assert moved.settings_hash == settings_hash({"return_without_goodwill_cap": 0.30})
    assert moved.settings_hash != base.settings_hash


def test_the_one_time_items_share_is_a_setting_in_the_place_of_the_non_recurring_flag_s() -> None:
    """Spec 2026-11-19 7.4: ``one_time_items_share`` stands where ``nri_flag_share`` stood, the
    flags group's second, with the Settings page's label and sentence of the spec's words, its
    range 1% to 50%, read at a revalue and hashed; ``nri_flag_share`` is no setting, and
    ``warning_mark_min`` none either."""
    s = setting("one_time_items_share")
    sentence = (
        "A Mature Stable row whose GAAP and street trailing EPS differ by this share of GAAP EPS "
        "or more is warned of one-time items."
    )
    assert (s.group, s.label, s.description, s.unit, s.effect, s.range_text, s.hashed) == (
        "flags",
        "One-time items, share of EPS",
        sentence,
        "fraction",
        "revalue",
        "1% to 50%",
        True,
    )
    names = [s.name for s in SETTINGS]
    assert names.index("one_time_items_share") == names.index("analyst_min") + 1
    for gone in ("nri_flag_share", "warning_mark_min"):
        with pytest.raises(KeyError):
            setting(gone)
    base = load_policy()
    assert default_of("one_time_items_share", base) == value_of("one_time_items_share", base)
    moved = apply_overlay(base, {"one_time_items_share": 0.25})
    assert moved.one_time_items_share == 0.25
    assert (
        moved.settings_hash == settings_hash({"one_time_items_share": 0.25}) != base.settings_hash
    )


def test_every_setting_names_a_value_of_the_file() -> None:
    p = load_policy()
    for s in SETTINGS:
        assert default_of(s.name, p) is not None, s.name


def test_hash_covers_valuation_flags_and_the_fallback_only() -> None:
    assert settings_hash({}) == EMPTY_SETTINGS_HASH
    assert settings_hash({"aging_fraction": 0.5}) == EMPTY_SETTINGS_HASH
    assert settings_hash({"refresh.workers": 4}) == EMPTY_SETTINGS_HASH
    assert settings_hash({"validity_fallback_days": 60}) != EMPTY_SETTINGS_HASH
    assert settings_hash({"required_return": 0.1}) == settings_hash(
        {"required_return": 0.1, "refresh.workers": 4}
    )
    hashed = {s.name for s in SETTINGS if s.hashed}
    valuing = {s.name for s in SETTINGS if s.group in ("valuation", "flags")} - THRESHOLDS
    assert hashed == valuing | {"validity_fallback_days"}


# The three thresholds, which set a row's levels and word and move no value (spec 2026-11-23
# thresholds, 5.3).
THRESHOLDS = {"margin_of_safety", "fair_band", "trim_multiple"}


def test_a_threshold_takes_effect_at_once_and_is_not_hashed() -> None:
    """Spec 2026-11-23 thresholds, 5.3: the margin of safety, the fair band and the trim multiple
    move no value, so a change of one shows at once and leaves the settings hash as it was: no
    row then reads as valued under other settings."""
    for name in THRESHOLDS:
        assert (setting(name).effect, setting(name).hashed) == ("at once", False), name
    assert settings_hash({"trim_multiple": 1.2, "fair_band": [0.95, 1.05]}) == EMPTY_SETTINGS_HASH
    assert settings_hash({"required_return": 0.1, "trim_multiple": 1.2}) == settings_hash(
        {"required_return": 0.1}
    )
    changed = apply_overlay(load_policy(), {"trim_multiple": 1.2})
    assert (changed.trim_multiple, changed.settings_hash) == (1.2, EMPTY_SETTINGS_HASH)
    safety = setting("margin_of_safety")
    assert safety.description == (
        "The discount to the value that sets the buy level; a price under a row's buy level "
        "reads Well below."
    )


def test_the_bands_low_is_above_every_class_s_buy_level() -> None:
    """Spec 2026-11-23 thresholds, 5.2: the first edge is each row's own, 1 − the margin of its
    class, so the band's low must be above the highest of them, the Wide row's: at a Wide margin
    of 20% a low of 0.81 is taken and one of 0.80 or 0.75 refused, though both are above the
    Narrow row's 0.70."""
    wide = {"None": 0.40, "Narrow": 0.30, "Wide": 0.20}
    apply_overlay(load_policy(), {"margin_of_safety": wide, "fair_band": [0.81, 1.10]})
    rule = "margin_of_safety, fair_band: the band's low must be above 1 − the Wide margin of safety"
    for low in (0.80, 0.75):
        with pytest.raises(ValueError, match=f"^{re.escape(rule)}$"):
            apply_overlay(load_policy(), {"margin_of_safety": wide, "fair_band": [low, 1.10]})


def test_the_empty_overlay_hashes_the_literal_of_the_migration() -> None:
    assert EMPTY_SETTINGS_HASH == hashlib.sha256(b"{}").hexdigest()
    assert EMPTY_SETTINGS_HASH == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


def test_apply_overlay_changes_the_value_and_the_derived_edges() -> None:
    p = apply_overlay(
        load_policy(),
        {"required_return": 0.1, "fair_band": [0.85, 1.2], "universe.cap_floor_usd": 5e9},
    )
    assert p.required_return == 0.1 and p.wide_terminal_roic_cap == pytest.approx(0.14)
    assert p.designation_edges == pytest.approx((0.70, 0.85, 1.2, 1.35))
    assert p.universe.cap_floor_usd == 5e9
    # the band enters no hash (spec 2026-11-23 thresholds, 5.3): the hash is the hurdle rate's
    assert p.version == "fairband-policy-v19" and p.settings_hash == settings_hash(
        {"required_return": 0.1}
    )


def test_the_empty_overlay_is_the_file() -> None:
    base = load_policy()
    assert apply_overlay(base, {}) == base


def test_apply_overlay_skips_a_name_that_is_no_setting() -> None:
    """A stored value of a removed setting is skipped (spec 2026-11-19 5 point 4, 7.4)."""
    p = apply_overlay(load_policy(), {"gone_value": 1, "fade_years": 3})
    assert p.fade_years == 3 and p.settings_hash == settings_hash({"fade_years": 3})
    assert settings_hash({"gone_value": 1}) == EMPTY_SETTINGS_HASH


@pytest.mark.parametrize(
    ("removed", "stored"), [("nri_flag_share", 0.05), ("refresh.gf_reuse_days", 3)]
)
def test_an_overlay_holding_a_removed_setting_reads_as_without_it(
    removed: str, stored: object
) -> None:
    """Policy v17 drops ``nri_flag_share`` (spec 2026-11-19 7.4, Review Focus 2) and policy v18
    ``refresh.gf_reuse_days`` by the same path (8.9): a stored value of either changes nothing
    and hashes as the overlay without it."""
    p = apply_overlay(load_policy(), {removed: stored, "fade_years": 3})
    assert p == apply_overlay(load_policy(), {"fade_years": 3})
    assert p.settings_hash == settings_hash({"fade_years": 3})
    assert settings_hash({removed: stored}) == EMPTY_SETTINGS_HASH


def test_apply_overlay_converts_as_the_loader_does() -> None:
    p = apply_overlay(
        load_policy(),
        {
            "runway_years": {"None": 6, "Narrow": 12, "Wide": 25},
            "margin_of_safety": {"None": 0.5, "Narrow": 0.3, "Wide": 0.2},
            "roic_sensitivity": [0.2, 0.1],
            "burn_cover_flag_years": 1,
            "universe.cap_bands": [[3e11, "Mega"], [2e10, "Large"], [2e9, "Mid"]],
            "universe.exchanges": ["NYSE"],
            "refresh.workers": 4,
            "refresh.rate_limit_hold_s": 30,
        },
    )
    assert p.runway_years == {"None": 6, "Narrow": 12, "Wide": 25}
    assert p.margin_of_safety == {"None": 0.5, "Narrow": 0.3, "Wide": 0.2}
    assert p.designation_edges[0] == pytest.approx(0.7)
    assert p.roic_sensitivity == (0.2, 0.1)
    assert p.burn_cover_flag_years == 1.0 and isinstance(p.burn_cover_flag_years, float)
    assert p.universe.cap_bands == ((3e11, "Mega"), (2e10, "Large"), (2e9, "Mid"))
    assert p.universe.exchanges == ("NYSE",) and p.universe.cap_floor_usd == 2e9
    assert p.refresh.workers == 4 and p.refresh.rate_limit_hold_s == 30.0
    assert p.refresh.reuse_hours == 24  # untouched


def test_a_new_size_floor_carries_the_lowest_band() -> None:
    """The lowest band equals the size floor (8.9), so a floor changed alone moves it."""
    p = apply_overlay(load_policy(), {"universe.cap_floor_usd": 5e9})
    assert p.universe.cap_bands == ((2e11, "Mega"), (1e10, "Large"), (5e9, "Mid"))


@pytest.mark.parametrize(
    ("overlay", "rule"),
    [
        ({"required_return": 0.02}, "required_return: must be from 4% to 20%"),
        ({"terminal_growth": 0.1}, "required_return, terminal_growth: g_T must be below r"),
        (
            {"runway_years": {"None": 3, "Narrow": 10, "Wide": 20}},
            "runway_years: each must be from 4 to 30 years",
        ),
        (
            {"runway_years": {"None": 12, "Narrow": 10, "Wide": 20}},
            "runway_years: None, Narrow, Wide must not decrease",
        ),
        ({"fair_band": [0.9, 1.6]}, "fair_band: the high must be from 1.01 to 1.50"),
        (
            {"trim_multiple": 1.1},
            "fair_band, trim_multiple: the trim multiple must be above the band's high",
        ),
        (
            {"high_growth_years": 7, "fade_years": 5},
            "fade_years, high_growth_years: together at most 10",
        ),
        (
            {"industry_peer_max": 2},
            "peer_min, industry_peer_max: the industry peers must be at least the fewest peers",
        ),
        (
            {"refresh.rate_limit_hold_s": float("inf")},
            "refresh.rate_limit_hold_s: must be from 1 to 3600",
        ),
        (
            {"universe.cap_bands": [[2e11, "Mega"], [1e10, "Large"], [3e9, "Mid"]]},
            "universe.cap_floor_usd, universe.cap_bands: the lowest band must equal the size floor",
        ),
        (
            {"universe.manual_admissions": ["v", "bad symbol"]},
            "universe.manual_admissions: 'bad symbol' is not a symbol",
        ),
    ],
)
def test_ranges_and_rules_name_the_setting(overlay: dict[str, Any], rule: str) -> None:
    with pytest.raises(ValueError, match=re.escape(rule)):
        apply_overlay(load_policy(), overlay)


MOATS = ("None", "Narrow", "Wide")


def _by_moat(*values: float) -> dict[str, float]:
    return dict(zip(MOATS, values, strict=True))


# One value outside each setting's range (spec 8.2) and one breaking each rule (8.9), with the
# sentence the API serves.
OUTSIDE: list[tuple[dict[str, Any], str]] = [
    ({"required_return": 0.21}, "required_return: must be from 4% to 20%"),
    ({"terminal_growth": -0.01}, "terminal_growth: must be from 0% to 5%"),
    (
        {"required_return": 0.04, "terminal_growth": 0.04},
        "required_return, terminal_growth: g_T must be below r",
    ),
    ({"runway_years": _by_moat(5, 10, 31)}, "runway_years: each must be from 4 to 30 years"),
    (
        {"margin_of_safety": _by_moat(0.71, 0.35, 0.25)},
        "margin_of_safety: each must be from 5% to 70%",
    ),
    (
        {"margin_of_safety": _by_moat(0.45, 0.35, 0.04)},
        "margin_of_safety: each must be from 5% to 70%",
    ),
    (
        {"margin_of_safety": _by_moat(0.30, 0.35, 0.25)},
        "margin_of_safety: None, Narrow, Wide must not increase",
    ),
    ({"fair_band": [0.49, 1.15]}, "fair_band: the low must be from 0.50 to 0.99"),
    ({"fair_band": [1.0, 1.15]}, "fair_band: the low must be from 0.50 to 0.99"),
    ({"fair_band": [0.85, 1.0]}, "fair_band: the high must be from 1.01 to 1.50"),
    # Every class's edges ascend: e1 = 1 − its margin of safety below e2 = the band's low, so the
    # low is above the highest e1, the Wide row's (0.80 at the defaults).
    (
        {"fair_band": [0.6, 1.15]},
        "margin_of_safety, fair_band: the band's low must be above 1 − the Wide margin of safety",
    ),
    (
        {"fair_band": [0.80, 1.15]},
        "margin_of_safety, fair_band: the band's low must be above 1 − the Wide margin of safety",
    ),
    (
        {"margin_of_safety": _by_moat(0.45, 0.30, 0.10)},
        "margin_of_safety, fair_band: the band's low must be above 1 − the Wide margin of safety",
    ),
    ({"trim_multiple": 3.01}, "trim_multiple: must be up to 3.0"),
    (
        {"trim_multiple": 1.10},
        "fair_band, trim_multiple: the trim multiple must be above the band's high",
    ),
    ({"wide_terminal_roic_spread": 0.11}, "wide_terminal_roic_spread: must be from 0 to 10 points"),
    (
        {"wide_terminal_roic_spread": -0.01},
        "wide_terminal_roic_spread: must be from 0 to 10 points",
    ),
    (
        {"return_without_goodwill_cap": 0.20},
        "return_without_goodwill_cap: must be above 20% and at most 100%",
    ),
    (
        {"return_without_goodwill_cap": 1.01},
        "return_without_goodwill_cap: must be above 20% and at most 100%",
    ),
    ({"inflation_addition": 0.051}, "inflation_addition: must be from 0 to 5 points"),
    ({"repricing_horizon_years": 0}, "repricing_horizon_years: must be from 1 to 10 years"),
    ({"repricing_horizon_years": 11}, "repricing_horizon_years: must be from 1 to 10 years"),
    ({"roic_sensitivity": [0.51, 0.09]}, "roic_sensitivity: each must be from 1% to 50%"),
    ({"roic_sensitivity": [0.15, 0.005]}, "roic_sensitivity: each must be from 1% to 50%"),
    ({"roic_sensitivity": [0.09, 0.09]}, "roic_sensitivity: the high must be above the low"),
    ({"fade_years": 0}, "fade_years: must be from 1 to 9"),
    ({"fade_years": 10}, "fade_years: must be from 1 to 9"),
    ({"high_growth_years": 2}, "high_growth_years: must be from 3 to 9"),
    ({"high_growth_years": 10, "fade_years": 1}, "high_growth_years: must be from 3 to 9"),
    ({"high_growth_years": 6}, "fade_years, high_growth_years: together at most 10"),
    ({"margin_convergence_year": 11}, "margin_convergence_year: must be from 1 to 10"),
    ({"margin_convergence_year": 0}, "margin_convergence_year: must be from 1 to 10"),
    ({"peer_min": 0}, "peer_min: must be from 1 to 10"),
    ({"peer_min": 11, "industry_peer_max": 20}, "peer_min: must be from 1 to 10"),
    ({"industry_peer_max": 51}, "industry_peer_max: must be from 1 to 50"),
    (
        {"peer_min": 5, "industry_peer_max": 4},
        "peer_min, industry_peer_max: the industry peers must be at least the fewest peers",
    ),
    ({"runoff_years": 4}, "runoff_years: must be from 5 to 20"),
    ({"runoff_years": 21}, "runoff_years: must be from 5 to 20"),
    ({"runoff_recovery": 1.01}, "runoff_recovery: must be from 0% to 100%"),
    ({"distress_sale_fraction": -0.1}, "distress_sale_fraction: must be from 0% to 100%"),
    ({"burn_cover_flag_years": 0.4}, "burn_cover_flag_years: must be from 0.5 to 5"),
    ({"burn_cover_flag_years": 5.5}, "burn_cover_flag_years: must be from 0.5 to 5"),
    ({"analyst_min": 0}, "analyst_min: must be from 1 to 20"),
    ({"analyst_min": 21}, "analyst_min: must be from 1 to 20"),
    ({"one_time_items_share": 0.005}, "one_time_items_share: must be from 1% to 50%"),
    ({"one_time_items_share": 0.51}, "one_time_items_share: must be from 1% to 50%"),
    ({"value_spread_flag": 1.01}, "value_spread_flag: must be from 5% to 100%"),
    ({"long_runway_growth_flag": 0.31}, "long_runway_growth_flag: must be from 1% to 30%"),
    ({"margin_flag_ratio": 1.0}, "margin_flag_ratio: must be from 1.1 to 3.0"),
    ({"margin_flag_above_high": 0.6}, "margin_flag_above_high: must be from 1% to 50%"),
    ({"margin_flag_min_years": 2}, "margin_flag_min_years: must be from 3 to 10"),
    ({"capex_ocf_flag": 0.05}, "capex_ocf_flag: must be from 10% to 100%"),
    ({"equity_raise_share": 0.2}, "equity_raise_share: must be from 0.1% to 10%"),
    ({"equity_raise_share": 0.0009}, "equity_raise_share: must be from 0.1% to 10%"),
    ({"validity_fallback_days": 29}, "validity_fallback_days: must be from 30 to 365"),
    ({"validity_fallback_days": 366}, "validity_fallback_days: must be from 30 to 365"),
    ({"aging_fraction": 0.96}, "aging_fraction: must be from 10% to 95%"),
    ({"aging_fraction": 0.09}, "aging_fraction: must be from 10% to 95%"),
    (
        {"universe.exchanges": []},
        "universe.exchanges: must be a non-empty subset of NYSE, NASDAQ, AMEX",
    ),
    (
        {"universe.exchanges": ["NYSE", "OTC"]},
        "universe.exchanges: must be a non-empty subset of NYSE, NASDAQ, AMEX",
    ),
    (
        {"universe.exchanges": ["NYSE", "NYSE"]},
        "universe.exchanges: must be a non-empty subset of NYSE, NASDAQ, AMEX",
    ),
    ({"universe.cap_floor_usd": 9e7}, "universe.cap_floor_usd: must be from $100 m to $50 bn"),
    ({"universe.cap_floor_usd": 6e10}, "universe.cap_floor_usd: must be from $100 m to $50 bn"),
    (
        {"universe.cap_bands": [[1e10, "Mega"], [2e11, "Large"], [2e9, "Mid"]]},
        "universe.cap_bands: the floors must descend",
    ),
    (
        {"universe.cap_bands": [[2e11, "Mega"], [2e9, "Mid"]]},
        "universe.cap_bands: must be the Mega, Large and Mid floors",
    ),
    (
        {"universe.cap_bands": [[2e11, "Huge"], [1e10, "Large"], [2e9, "Mid"]]},
        "universe.cap_bands: must be the Mega, Large and Mid floors",
    ),
    (
        {
            "universe.cap_floor_usd": 3e9,
            "universe.cap_bands": [[2e11, "Mega"], [1e10, "Large"], [2e9, "Mid"]],
        },
        "universe.cap_floor_usd, universe.cap_bands: the lowest band must equal the size floor",
    ),
    (
        {"universe.manual_exclusions": ["TOOLONGSYMBOL"]},
        "universe.manual_exclusions: 'TOOLONGSYMBOL' is not a symbol",
    ),
    ({"universe.manual_exclusions": [""]}, "universe.manual_exclusions: '' is not a symbol"),
    (
        {"universe.manual_admissions": ["BRK B"]},
        "universe.manual_admissions: 'BRK B' is not a symbol",
    ),
    ({"refresh.workers": 0}, "refresh.workers: must be from 1 to 64"),
    ({"refresh.workers": 65}, "refresh.workers: must be from 1 to 64"),
    ({"refresh.fmp_calls_per_minute": 9}, "refresh.fmp_calls_per_minute: must be from 10 to 10000"),
    (
        {"refresh.fmp_calls_per_minute": 10001},
        "refresh.fmp_calls_per_minute: must be from 10 to 10000",
    ),
    ({"refresh.rate_limit_hold_s": 0.5}, "refresh.rate_limit_hold_s: must be from 1 to 3600"),
    (
        {"refresh.rate_limit_hold_s": float("nan")},
        "refresh.rate_limit_hold_s: must be from 1 to 3600",
    ),
    ({"refresh.reuse_hours": 721}, "refresh.reuse_hours: must be from 0 to 720"),
    ({"refresh.reuse_hours": -1}, "refresh.reuse_hours: must be from 0 to 720"),
]


@pytest.mark.parametrize(("overlay", "rule"), OUTSIDE)
def test_every_range_and_rule_names_its_setting(overlay: dict[str, Any], rule: str) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(rule)}$"):
        apply_overlay(load_policy(), overlay)


def test_every_setting_has_a_range_check() -> None:
    # A rule between two settings names both, joined by a comma (B-75).
    named = {name for _, rule in OUTSIDE for name in rule.split(":")[0].split(", ")}
    assert named == {s.name for s in SETTINGS}


# Each range's ends are inside it (8.2: ranges are inclusive).
INSIDE: list[dict[str, Any]] = [
    {"required_return": 0.04},
    {"required_return": 0.20, "terminal_growth": 0.05},
    {"terminal_growth": 0.0},
    {"runway_years": _by_moat(4, 4, 4)},
    {"runway_years": _by_moat(30, 30, 30)},
    {"margin_of_safety": _by_moat(0.05, 0.05, 0.05), "fair_band": [0.96, 1.15]},
    {"margin_of_safety": _by_moat(0.70, 0.70, 0.70)},
    {"fair_band": [0.50, 1.01], "margin_of_safety": _by_moat(0.70, 0.55, 0.51)},
    {"fair_band": [0.81, 1.15]},  # just above the Wide row's e1 = 0.80
    {"margin_of_safety": _by_moat(0.45, 0.30, 0.11)},  # Wide e1 = 0.89, just below the band's 0.90
    {"fair_band": [0.99, 1.50], "trim_multiple": 3.0},
    {"wide_terminal_roic_spread": 0.0},
    {"wide_terminal_roic_spread": 0.10},
    {"return_without_goodwill_cap": 0.21},
    {"return_without_goodwill_cap": 1.0},
    {"inflation_addition": 0.0},
    {"inflation_addition": 0.05},
    {"repricing_horizon_years": 1},
    {"repricing_horizon_years": 10},
    {"roic_sensitivity": [0.50, 0.01]},
    {"fade_years": 1, "high_growth_years": 9},
    {"fade_years": 7, "high_growth_years": 3},
    {"margin_convergence_year": 1},
    {"margin_convergence_year": 10},
    {"peer_min": 1, "industry_peer_max": 1},
    {"peer_min": 10, "industry_peer_max": 50},
    {"runoff_years": 5, "runoff_recovery": 0.0, "distress_sale_fraction": 1.0},
    {"runoff_years": 20, "runoff_recovery": 1.0, "distress_sale_fraction": 0.0},
    {"burn_cover_flag_years": 0.5},
    {"burn_cover_flag_years": 5},
    {
        "analyst_min": 1,
        "one_time_items_share": 0.01,
        "value_spread_flag": 0.05,
        "long_runway_growth_flag": 0.01,
        "margin_flag_ratio": 1.1,
        "margin_flag_above_high": 0.01,
        "margin_flag_min_years": 3,
        "capex_ocf_flag": 0.10,
        "equity_raise_share": 0.001,
    },
    {
        "analyst_min": 20,
        "one_time_items_share": 0.50,
        "value_spread_flag": 1.0,
        "long_runway_growth_flag": 0.30,
        "margin_flag_ratio": 3.0,
        "margin_flag_above_high": 0.50,
        "margin_flag_min_years": 10,
        "capex_ocf_flag": 1.0,
        "equity_raise_share": 0.10,
    },
    {"validity_fallback_days": 30, "aging_fraction": 0.10},
    {"validity_fallback_days": 365, "aging_fraction": 0.95},
    {"universe.exchanges": ["AMEX", "NYSE", "NASDAQ"], "universe.manual_exclusions": ["BRK.B"]},
    {"universe.cap_floor_usd": 1e8, "universe.manual_admissions": []},
    {
        "universe.cap_floor_usd": 5e10,
        "universe.cap_bands": [[2e11, "Mega"], [1e11, "Large"], [5e10, "Mid"]],
        "universe.manual_admissions": ["ABCDEFGHIJ", "BF-B"],
    },
    {
        "refresh.workers": 1,
        "refresh.fmp_calls_per_minute": 10,
        "refresh.rate_limit_hold_s": 1,
        "refresh.reuse_hours": 0,
    },
    {
        "refresh.workers": 64,
        "refresh.fmp_calls_per_minute": 10000,
        "refresh.rate_limit_hold_s": 3600,
        "refresh.reuse_hours": 720,
    },
]


@pytest.mark.parametrize("overlay", INSIDE)
def test_the_ends_of_each_range_are_inside(overlay: dict[str, Any]) -> None:
    apply_overlay(load_policy(), overlay)


@pytest.mark.parametrize(
    ("overlay", "rule"),
    [
        ({"required_return": "9%"}, "required_return: '9%' is not a number"),
        ({"required_return": True}, "required_return: True is not a number"),
        ({"refresh.workers": 4.5}, "refresh.workers: 4.5 is not a whole number"),
        ({"fair_band": [0.85]}, "fair_band: [0.85] is not a pair of numbers"),
        (
            {"runway_years": {"None": 5, "Narrow": 10}},
            "runway_years: {'None': 5, 'Narrow': 10} is not a table of None, Narrow and Wide",
        ),
        (
            {"universe.cap_bands": [[1, "Mega"], 2]},
            "universe.cap_bands: [[1, 'Mega'], 2] is not a list of [floor, label] pairs",
        ),
        ({"universe.manual_admissions": "V"}, "universe.manual_admissions: 'V' is not a list"),
    ],
)
def test_a_value_of_the_wrong_type_names_the_setting(overlay: dict[str, Any], rule: str) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(rule)}$"):
        apply_overlay(load_policy(), overlay)


def test_symbols_are_upper_cased_on_apply() -> None:
    p = apply_overlay(load_policy(), {"universe.manual_admissions": ["v", "ma"]})
    assert p.universe.manual_admissions == ("V", "MA")


def test_load_policy_checks_the_file_too(tmp_path: Path) -> None:
    text = resources.files("fairband.policy").joinpath("fairband-policy-v18.toml").read_text()
    old = "[values.required_return]\nvalue = 0.09\n"
    assert text.count(old) == 1
    copy = tmp_path / "policy.toml"
    copy.write_text(text.replace(old, "[values.required_return]\nvalue = 0.02\n"))
    with pytest.raises(ValueError, match=re.escape("required_return: must be from 4% to 20%")):
        load_policy(copy)


@pytest.mark.parametrize("multiple", [1.0, 0.5, math.nan, math.inf])
def test_a_sheet_shift_multiple_at_or_below_one_is_refused(multiple: float) -> None:
    """Spec 2026-11-13 12.5: the multiple is no setting, so only the file sets it; at 1 or below
    every minority interest that moved at all would show, so the check refuses it, and a NaN or
    an infinity with it."""
    with pytest.raises(ValueError, match="^sheet_shift_multiple: must be above 1$"):
        check(replace(load_policy(), sheet_shift_multiple=multiple))


def test_a_sheet_shift_multiple_above_one_is_accepted() -> None:
    check(replace(load_policy(), sheet_shift_multiple=1.5))


@pytest.mark.parametrize("size", [-0.01, math.nan, math.inf])
def test_a_thin_revenue_step_max_below_zero_is_refused(size: float) -> None:
    """Spec 2026-11-14 6.2, as narrowed: the size is no setting, so only the file sets it; below 0%
    a thin falling step would go unread, and a NaN or an infinity would turn the rule off, so the
    check refuses each."""
    with pytest.raises(ValueError, match="^thin_revenue_step_max: must be 0% or more$"):
        check(replace(load_policy(), thin_revenue_step_max=size))


def test_a_thin_revenue_step_max_of_0_percent_or_more_is_accepted() -> None:
    check(replace(load_policy(), thin_revenue_step_max=0.0))
    check(replace(load_policy(), thin_revenue_step_max=3.0))


@pytest.mark.parametrize(
    ("name", "default"),
    [
        ("required_return", 0.09),
        ("runway_years", {"None": 5, "Narrow": 10, "Wide": 20}),
        ("margin_of_safety", {"None": 0.40, "Narrow": 0.30, "Wide": 0.20}),
        ("fair_band", [0.90, 1.10]),
        ("wide_terminal_roic_spread", 0.04),
        ("return_without_goodwill_cap", 0.25),
        ("repricing_horizon_years", 3),
        ("margin_flag_min_years", 6),
        ("validity_fallback_days", 91),
        ("aging_fraction", 0.6667),
        ("universe.exchanges", ["NYSE", "NASDAQ", "AMEX"]),
        ("universe.cap_floor_usd", 2e9),
        ("universe.cap_bands", [[2e11, "Mega"], [1e10, "Large"], [2e9, "Mid"]]),
        ("universe.manual_admissions", ["V", "MA", "GPN"]),
        ("universe.manual_exclusions", []),
        ("refresh.workers", 16),
        ("refresh.rate_limit_hold_s", 60),
        ("refresh.reuse_hours", 24),
    ],
)
def test_default_of_is_the_files_value_as_json(name: str, default: Any) -> None:
    assert default_of(name, load_policy()) == default


def test_default_of_reads_the_file_under_an_overlay() -> None:
    custom = apply_overlay(load_policy(), {"required_return": 0.1, "refresh.workers": 4})
    assert default_of("required_return", custom) == 0.09
    assert default_of("refresh.workers", custom) == 16
    copy = default_of("universe.manual_admissions", custom)
    copy.append("X")
    assert default_of("universe.manual_admissions", custom) == ["V", "MA", "GPN"]


def test_default_of_an_unknown_name_raises() -> None:
    with pytest.raises(KeyError):
        default_of("designation_edges", load_policy())


def test_value_of_is_the_policys_value_as_json() -> None:
    """At the defaults every setting's value is its default; under an overlay the policy's value,
    as the API serves it and the overlay stores it."""
    p = load_policy()
    assert all(value_of(s.name, p) == default_of(s.name, p) for s in SETTINGS)
    custom = apply_overlay(p, {"fair_band": [0.9, 1.2], "universe.cap_floor_usd": 3e9})
    assert value_of("fair_band", custom) == [0.9, 1.2]
    assert value_of("runway_years", custom) == {"None": 5, "Narrow": 10, "Wide": 20}
    assert value_of("universe.cap_bands", custom) == [[2e11, "Mega"], [1e10, "Large"], [3e9, "Mid"]]
    with pytest.raises(KeyError):
        value_of("designation_edges", p)


def test_exchange_symbol() -> None:
    assert exchange_symbol("brk.b") == "BRK.B"
    for text in ("bad symbol", "", "TOOLONGSYMBOL", "BRK/B"):
        with pytest.raises(ValueError, match=f"^{re.escape(repr(text))} is not a symbol$"):
            exchange_symbol(text)
