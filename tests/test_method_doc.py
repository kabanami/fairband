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
    assert len(get_args(OverrideTag)) == 25
    assert "A tag that is not one of the twenty-five:" in section


def test_an_agent_s_revenue_step_is_the_one_the_charge_pays_for() -> None:
    """Spec 2026-11-14 6.1 and 6.3: 4.8 and 5.3 say the charge reads an agent's revenue step in
    place of the consensus's, while an earnings step override still moves only the fallback; 4.8
    and 5.12 name the `charge` entry's three keys; 5.11's flag says "revenue growth" for an agent's
    step too; 6.4's cross-check takes none; 14.4 gives the two inputs their bullet, with the
    reading, the steps found; and 11's row cites every section that states the rule."""
    four = _section(4)
    for words in (
        "an agent's revenue step (`revenue.step_2`, `revenue.step_3`, 14.4) in its place",
        "`revenue_steps_found`",
        "`revenue_step_source`",
    ):
        assert words in four, words
    five = _section(5)
    for words in (
        (
            "an earnings step override (`path.step_2`, `path.step_3`) moves that fallback and never"
            " a revenue step the consensus gives"
        ),
        (
            "an agent's `revenue.step_2` or `revenue.step_3` (14.4) replaces the consensus revenue"
            " step"
        ),
        (
            "the owner funds the growth.\" where the year's h is a revenue step, the consensus's or"
            " an agent's"
        ),
        "`revenue_steps_found`",
        "`revenue_step_source`",
    ):
        assert words in five, words
    six = _section(6)
    assert "reads the consensus revenue steps as found and no agent's" in six
    fourteen = _section(14)
    bullet = next(x for x in fourteen.splitlines() if x.startswith("- `revenue.step_2`"))
    for words in (
        "the consensus revenue step as found",
        "`path.step_2` and `path.step_3` still move the earnings steps",
        "a cross-check does not read them",
        "Period-tied only",
    ):
        assert words in bullet, words
    assert "the revenue steps, the consensus's as found (`charge.revenue_steps_found`" in fourteen
    row = next(x for x in _section(11).splitlines() if x.startswith("| 1.4, policy v16 |"))
    assert "(4.8, 5.3, 5.11, 5.12, 6.4, 14.2 to 14.5, 14.9)" in row


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
    # the reading of the NTM earnings adds the cycle gap back and not the item (the review of
    # Task 3): the item is moot under a guided EPS, so a grid on `earnings.ntm` marks the cell
    # in force
    assert (
        "the NTM EPS, the Mature Growth anchor as stored with any cycle gap added back and not the"
        " one-time item (`ntm_nri`), the figure an `earnings.ntm` override stands in for to give"
        " the same result, since a guided EPS stands in for the consensus with its items;"
    ) in fourteen
    assert "the one-time item it took off (`ntm_nri`" not in fourteen


def test_an_override_made_before_a_split_applies_on_the_new_basis() -> None:
    """Spec 2026-11-14 7: 14.6 states the rule on the two data dates, what the row says and what
    stays; 14.4's JUDGMENT entry and 14.8's reading point to it; section 8 names the note, not
    counted; and 11's row cites every section that states the rule."""
    fourteen = _section(14)
    follows = fourteen[fourteen.index("### 14.6") : fourteen.index("### 14.7")]
    for words in (
        "divided by ρ, and one in shares (`shares.diluted`, `shares.committed`) multiplied by it",
        (
            "the product of the ratios of the splits dated after the data date of the snapshot the"
            " override was made on, and at or before the data date of the snapshot reviewed"
        ),
        "the price date does not, since a price refresh fetches no split",
        "The stored override keeps the figure entered.",
        '"entered as $30.00 a share before the 2-for-1 split of 27 Jan 2027"',
        "`override-split-scaled`",
        "The drop tests read the figure the override corrected, never scaled",
    ):
        assert words in follows, words
    assert "the reason as the note, and after a split the figure as entered (14.6)" in fourteen
    assert "each on that snapshot's share basis after a split as the review reads it (14.6)" in (
        fourteen
    )
    row = next(x for x in _section(8).splitlines() if x.startswith("| `override-split-scaled`"))
    assert row.startswith("| `override-split-scaled` | no |")
    assert '"Override scaled at a split"' in row
    row = next(x for x in _section(11).splitlines() if x.startswith("| 1.4, policy v16 |"))
    assert "carrying the note `override-split-scaled` (section 8, 14.4, 14.6, 14.8)" in row


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
