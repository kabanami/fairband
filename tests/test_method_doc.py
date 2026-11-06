"""``docs/method.md`` against the engine: the sections that name the engine's terms name all of
them."""

from pathlib import Path
from typing import get_args

from fairband.engine.overrides import OverrideTag

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
