"""``docs/method.md`` against the engine: the sections that name the engine's terms name all of
them."""

from pathlib import Path
from typing import get_args

from fairband.engine.overrides import OverrideTag
from fairband.engine.secondary import SECONDARY_METHOD
from fairband.policy import load_policy
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
    # rule 2 counts the tags in words
    assert len(get_args(OverrideTag)) == 23
    assert "A tag that is not one of the twenty-three:" in section


def test_the_one_time_item_comes_off_year_1_in_its_order() -> None:
    """Spec 2026-11-14 5: 5.2 states the order of the three subtractions and the form under a
    guided EPS, which does not read the one-time amount; 14.4 gives the input its bullet, and 11's
    row cites every section that states the rule."""
    five = _section(5)
    assert "    NTM EPS = raw − adjustment − one-time amount − cycle gap\n" in five
    assert "    NTM EPS = guided EPS − cycle gap\n" in five
    fourteen = _section(14)
    bullet = next(x for x in fourteen.splitlines() if x.startswith("- `earnings.ntm_nri`"))
    for words in (
        "the `ntm_eps` and `ntm_net_income` DATA entries stay on the consensus as found",
        "a bridge line of zero",
        "a cross-check does not read it",
    ):
        assert words in bullet, words
    row = next(x for x in _section(11).splitlines() if x.startswith("| 1.4, policy v16 |"))
    assert "(5.2, 5.12, 14.2 to 14.5)" in row


def test_the_share_count_gap_reads_the_count_without_the_committed_shares() -> None:
    """Spec 2026-11-14 4 and the controller's ruling on Task 2: the note reads the diluted count
    without an agent's committed shares, which the market cap cannot hold yet."""
    row = next(line for line in _section(8).splitlines() if line.startswith("| `share-count-gap`"))
    assert (
        "it leaves out an agent's committed shares (`shares.committed`, 14.4), since the market "
        "cap holds no share not yet issued"
    ) in row


def test_every_value_a_share_divides_by_the_count_in_force() -> None:
    """Spec 2026-11-14 4 (Task 2's review, fix round 1): the sections that define a value a share
    divide by the count in force, the diluted count plus any committed shares, as the routes do;
    none divides by the diluted shares alone. (The stock pay a share of 5.2 stays on the diluted
    shares: the count the consensus is on.)"""
    text = METHOD.read_text(encoding="utf-8")
    for line in (
        (
            "The value a share is the total ÷ the count in force: the diluted share count (4.2), "
            "plus any committed shares (14.4)."
        ),
        "    value a share = equity ÷ the count in force\n",
        (
            "    going-concern value a share = (firm value − debt − minority interest + cash) ÷ the "
            "count in force\n"
        ),
        "    floor a share = (NCAV − minority interest) ÷ the count in force\n",
        (
            "    distress-sale value a share = max(0, distress proceeds − debt − minority interest)"
            " ÷ the count in force\n"
        ),
        "    cash floor = (cash − debt − minority interest) ÷ the count in force\n",
        (
            "| NCAV | Graham's net current asset value: total current assets less total "
            "liabilities; less the minority interest and over the count in force,"
        ),
        (
            "| Cash floor | A Start-up row's net cash a share, (cash − debt − minority interest) ÷ "
            "the count in force,"
        ),
    ):
        assert line in text, line
    for old in (
        "The value a share is the total ÷ the diluted share count.",
        "value a share = equity ÷ diluted shares",
        "+ cash) ÷ diluted shares",
        "(NCAV − minority interest) ÷ diluted shares",
        "debt − minority interest) ÷ diluted shares",
        "over the diluted shares",
    ):
        assert old not in text, old


def test_section_15_names_the_bounds_and_the_two_versions() -> None:
    section = _section(15)
    bounds = ("secondary_parts_max", "secondary_years_min", "secondary_years_max")
    for name in (*bounds, "secondary_driver_ranges"):
        assert f"`{name}`" in section, name
    assert f"`{SECONDARY_METHOD}`" in section
    assert "`fairband-secondary/1`" in section  # a plan 1 record reads as it was
    for name in load_policy().secondary_driver_ranges:
        assert f'"{name} is ' in section, name  # each driver's refusal sentence
    # spec 2026-11-13 3: no minority interest in the secondary valuation; the debt carries one
    assert "The secondary valuation subtracts no minority interest" in section


def test_section_16_names_the_six_failures() -> None:
    section = _section(16)
    for failure in FAILURES:
        assert f"`{failure}`" in section, failure
    for form in ("snapshot", "review", "secondary", "fact", "table", "estimate", "close", "peer"):
        assert f"`{form}:" in section, form
    for form in ("finding", "guidance", "derived", "sensitivity", "response", "policy"):
        assert f"`{form}:" in section, form
    assert "`stance_words`" in section
