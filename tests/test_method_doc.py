"""``docs/method.md`` against the engine: the sections that name the engine's terms name all of
them."""

from pathlib import Path
from typing import get_args

from fairband.engine.overrides import OverrideTag
from fairband.reports.check import FAILURES

METHOD = Path(__file__).parent.parent / "docs" / "method.md"


def _section(number: int) -> str:
    """The text under the heading ``## <number>.``, to the next top-level heading."""
    text = METHOD.read_text(encoding="utf-8")
    start = text.index(f"\n## {number}. ")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_section_14_names_every_override_tag() -> None:
    section = _section(14)
    for tag in get_args(OverrideTag):
        assert f"`{tag}`" in section, tag
    assert "`override_ranges`" in section
    assert "`override_primary_evidence_above_p90`" in section


def test_section_15_names_the_three_bounds() -> None:
    section = _section(15)
    for name in ("secondary_parts_max", "secondary_years_min", "secondary_years_max"):
        assert f"`{name}`" in section, name
    assert "fairband-secondary/1" in section


def test_section_16_names_the_six_failures() -> None:
    section = _section(16)
    for failure in FAILURES:
        assert f"`{failure}`" in section, failure
    for form in ("snapshot", "review", "secondary", "fact", "table", "estimate", "close", "peer"):
        assert f"`{form}:" in section, form
    for form in ("finding", "derived", "response", "policy"):
        assert f"`{form}:" in section, form
    assert "`stance_words`" in section
