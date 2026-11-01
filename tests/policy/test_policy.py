import hashlib
import re
from importlib import resources
from pathlib import Path

import pytest

from fairband.policy import BaseRateClass, load_policy


def _packaged_bytes() -> bytes:
    return resources.files("fairband.policy").joinpath("fairband-policy-v1.toml").read_bytes()


def test_values_match_design() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v1" and len(p.hash) == 64
    assert p.required_return == 0.09 and p.terminal_growth == 0.03
    assert p.runway_years == {"None": 5, "Narrow": 10, "Wide": 20}
    assert p.margin_of_safety == {"None": 0.45, "Narrow": 0.35, "Wide": 0.25}
    assert p.fair_band == (0.85, 1.15) and p.trim_multiple == 1.5
    assert p.wide_terminal_roic_cap == 0.13
    assert p.moat_wide_min == 8 and p.moat_narrow_min == 4
    assert len(p.base_rates) == 11
    assert p.base_rates[0] == BaseRateClass(325, 0.085, "$0-325 Mn")
    assert p.base_rates[-1].median == 0.033 and p.inflation_addition == 0.02
    assert p.analyst_min == 5 and p.universe.cap_floor_usd == 2_000_000_000
    assert p.refresh.reuse_hours == 24 and p.refresh.gf_reuse_days == 7 and p.refresh.workers == 4


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
