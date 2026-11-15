"""``docs/method.md`` against the engine: the sections that name the engine's terms name all of
them."""

from pathlib import Path
from typing import get_args

from fairband.engine.overrides import OverrideTag, anchor_misfit
from fairband.engine.secondary import SECONDARY_METHOD
from fairband.policy import load_policy
from fairband.reports.check import FAILURES
from fairband.store.guidance import METRICS

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


def test_a_thin_revenue_step_is_not_read() -> None:
    """Spec 2026-11-14 6.2, method 1.5: 5.3 states the rule, the count it reads and a missing
    count, what an earnings step override then moves, the agent's step over the rule and the
    Decline route's like rule; 4.8 and 5.12 name the source `thin`; 6.4's cross-check follows; 14.4
    says what an earnings step override moves and that the reading stays the step found; 11 has the
    1.5 row after the 1.4 one."""
    five = _section(5)
    bullet = next(x for x in five.splitlines() if x.startswith("- a consensus revenue step above"))
    for words in (
        # the size test (spec 2026-11-14 6.2, as narrowed on 2026-11-15)
        "a consensus revenue step above `thin_revenue_step_max` (50%) whose landing year has",
        "fewer than `analyst_min` (5) revenue analysts, or no count, is thin and not read",
        "A step at or below 50% is read on any count",
        "The count is FMP's revenue analyst count of the landing year alone",
        "so an earnings step override moves the charge of that year",
        "an agent's `revenue.step_2` or `revenue.step_3` still stands over the rule",
        "The Decline route leaves out a consensus year on too few revenue analysts",
    ):
        assert words in bullet, words
    assert "So does a thin one, a consensus revenue step above `thin_revenue_step_max`" in (
        _section(4)
    )
    value = next(x for x in _section(4).splitlines() if "`thin_revenue_step_max` | no |" in x)
    assert "spec 2026-11-14 6.2" in value
    assert "`consensus`, `agent`, `thin` (5.3) or `none`" in five
    assert "`consensus`, `agent`, `thin` (the consensus's step left out as thin" in _section(4)
    assert "leaves a thin step out as the route does (5.3)" in _section(6)
    fourteen = _section(14)
    assert "A thin consensus revenue step (5.3) does not stand" in fourteen
    assert "On a thin year the reading is still the step found" in fourteen
    # a sensitivity grid marks the growth the charge read (14.8)
    assert "On a thin year (5.3) the pair marked is the earnings step's, not the step" in fourteen
    rows = [x for x in _section(11).splitlines() if x.startswith("| 1.")]
    thin = next(
        k
        for k, x in enumerate(rows)
        if x.startswith("| 1.5, policy v16 | 2026-11-15 | A thin revenue step is not read")
    )
    assert rows[thin - 1].startswith("| 1.4, policy v16 |")
    assert "above `thin_revenue_step_max` (50%)" in rows[thin]
    assert "Policy v16 gains one value for the rule, `thin_revenue_step_max` (50%)" in rows[thin]


def test_the_runway_returns_rulings_of_2026_11_15() -> None:
    """The founder's rulings of 2026-11-15 on the runway return (B-8, B-170): 4.7 and 14.4 say an
    agent's ``return.runway`` sets the terminal return by the moat's rule on every row, 4.6's
    edge follows, and 11 has the row after the thin rule's, the method unchanged at 1.5."""
    four = _section(4)
    assert (
        "Under an agent's `return.runway` (14.4) the override is the return in force, and the "
        "rule reads it in place of the measure on every row"
    ) in four
    assert "and the Wide moat's terminal return reads the override (4.7, 14.4)" in four
    assert "the Wide moat's terminal return stays on the measure" not in four
    fourteen = _section(14)
    bullet = next(
        x for x in fourteen.splitlines() if x.startswith("- `return.runway` replaces the runway")
    )
    for words in (
        (
            "The override is the return in force, so the moat's terminal rule (4.7) reads it in "
            "place of the measure, on every row"
        ),
        (
            "So the terminal return never stands above an agent's start at or above r, while a "
            "start below r, which the range allows, still fades up to r"
        ),
        "the same terminal return",
        (
            "on Mature Growth the value under the override alone is the row's own return "
            "sensitivity at the same figure (5.8; the Mature Stable route has no return sensitivity)"
        ),
    ):
        assert words in bullet, words
    assert "the terminal return stays at r" not in bullet
    rows = [x for x in _section(11).splitlines() if x.startswith("| 1.")]
    assert rows[-1].startswith(
        "| 1.5, policy v16 | 2026-11-15 | The runway return's rulings (founder 2026-11-15"
    )
    assert "The method is unchanged at 1.5: no mechanical value moves." in rows[-1]
    assert "the moat's terminal rule reads it in place of the measure on every row" in rows[-1]
    # the marginal return at a constant margin: recorded, shown and never used (4.6)
    paragraph = next(
        x for x in four.splitlines() if x.startswith("The row records one more figure, shown and")
    )
    for words in (
        "the five-year marginal return at a constant margin (`runway_return.constant_margin`)",
        (
            "the newest kept year's NOPAT over that fiscal year's revenue, times the revenue added "
            "over the average capital added across the marginal span"
        ),
        "so a margin that rose on the revenue already there reads as a return on new capital",
        "It holds no figure with fewer than six kept years",
        "The engine keeps the marginal (founder 2026-11-15)",
    ):
        assert words in paragraph, words
    assert "`runway_return` gains `constant_margin`" in rows[-1]
    # the cap is a setting; the other calls stand, and no cap bounds a return on capital near zero
    value = next(x for x in four.splitlines() if "| `return_without_goodwill_cap` | yes |" in x)
    assert "a setting since the founder's ruling of 2026-11-15" in value
    assert "`return_without_goodwill_cap` (25%), becomes a setting" in rows[-1]
    assert "A return far above 100% on capital near zero stands with no cap" in rows[-1]
    # B-8's last part: the chart and its table do not print a ROIC on capital at or below zero
    sixteen = _section(16)
    assert (
        "a ROIC year on average invested capital at or below zero written as its note"
    ) in sixteen
    assert "as the page's ROIC chart leaves that year out and names it under the chart" in sixteen
    assert "the report page's ROIC chart leaves a year on average invested capital" in rows[-1]
    assert "an agent set at r, which sets the terminal return at r too (14.4)" in four


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
    """Spec 2026-11-14 7, as amended at the build: 14.6 states the rule on the two snapshots' basis
    dates, the earlier of the price date and the data date of the snapshot that assembled the
    figures, its three residuals (the third, statements and splits fetched on different days, from
    the whole-branch review), what the row says and what stays; 14.4's JUDGMENT entry and 14.8's
    reading point to it; section 8 names the note, not counted, and where it stands among the
    review's flags; and 11's row states the basis date and cites every section that states the
    rule."""
    fourteen = _section(14)
    follows = fourteen[fourteen.index("### 14.6") : fourteen.index("### 14.7")]
    for words in (
        "divided by ρ, and one in shares (`shares.diluted`, `shares.committed`) multiplied by it",
        (
            "that the figures of the snapshot reviewed saw and the figures of the snapshot the"
            " override was made on did not"
        ),
        (
            "A snapshot's figures saw a split dated at or before its basis date: the earlier of the"
            " price date and the data date of the snapshot that assembled them, the snapshot"
            " itself, or, for a snapshot a price refresh made, the company's latest earlier"
            " snapshot that a full or scoped refresh or a revalue made, else the snapshot's own two"
            " dates."
        ),
        "a refresh on a split's day before the US close, whose quote is the day before's, has not",
        "Three cases escape the basis date",
        (
            "the statements can be read from an answer fetched on one day and the splits from an"
            " answer fetched on another, when a fetch stopped on a 429 after the statements and a"
            " full refresh inside the reuse window fetched again only the calls that failed"
            " (section 2), or when the vendor lists a split a day late, while the basis date reads"
            " the statements' data date, so it can say the figures saw a split they did not, or"
            " the reverse."
        ),
        "The stored override keeps the figure entered.",
        '"entered as $30.00 a share before the 2-for-1 split of 27 Jan 2027"',
        "`override-split-scaled`",
        "The drop tests read the figure the override corrected, never scaled",
    ):
        assert words in follows, words
    assert "after the data date of the snapshot the override was made on" not in follows
    assert "the reason as the note, and after a split the figure as entered (14.6)" in fourteen
    assert "each on that snapshot's share basis after a split as the review reads it (14.6)" in (
        fourteen
    )
    row = next(x for x in _section(8).splitlines() if x.startswith("| `override-split-scaled`"))
    assert row.startswith("| `override-split-scaled` | no |")
    assert '"Override scaled at a split"' in row
    assert "seeing the splits dated at or before its basis date" in row
    # a reprice re-reads a flag that can land after the note (the whole-branch review)
    assert (
        "at the recompute it comes after the review's other flags, `fx-stale` last; a price"
        " refresh keeps it with the review, and a flag the reprice re-reads,"
        " `long-runway-high-growth` or `below-net-cash` (section 10), can land after it"
    ) in row
    assert "last among the review's flags but `fx-stale`" not in row
    row = next(x for x in _section(11).splitlines() if x.startswith("| 1.4, policy v16 |"))
    assert (
        "a snapshot's figures seeing the splits dated at or before its basis date, the earlier of"
        " the price date and the data date of the snapshot that assembled them"
    ) in row
    assert "after the data date of the snapshot it was made on" not in row
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


def test_an_override_the_route_no_longer_reads_drops() -> None:
    """Spec 2026-11-14 8 (Task 6's review, fix round 1): 14.3's rule 3 says the route is checked
    again at every recompute, the route moving when a `phase` override is added, replaced or
    dropped, a first one included, or the classifier moves the phase; 14.6 states the drop, its
    reason, its place among the tests and the unclassified row; and 11's row cites both."""
    fourteen = _section(14)
    rules = fourteen[fourteen.index("### 14.3") : fourteen.index("### 14.4")]
    follows = fourteen[fourteen.index("### 14.6") : fourteen.index("### 14.7")]
    assert (
        "an applied override whose tag the row's route no longer reads, once a `phase` override is"
        " added, replaced or dropped or the classifier moves the phase, is dropped by the system,"
        ' "the <route> route does not read the input" (14.6)'
    ) in rules
    for words in (
        'the reason "the <route> route does not read the input"',
        (
            "The row's route is the route of its applied `phase` override, else of its mechanical"
            " phase."
        ),
        "the route's test runs before the other overrides' tests",
        (
            "So a phase that moves, at a refresh or when an agent adds, replaces or drops a"
            " `phase` override, takes with it each override only the old route read"
        ),
        (
            "An unclassified row, with no `phase` override and no mechanical phase, has no route"
            " and keeps every override"
        ),
    ):
        assert words in follows, words
    assert "when an agent drops or replaces a `phase` override" not in follows
    row = next(x for x in _section(11).splitlines() if x.startswith("| 1.4, policy v16 |"))
    assert "while an unclassified row keeps its overrides (14.3, 14.6)" in row


def test_a_guidance_record_holds_net_income_and_backs_the_ntm_eps() -> None:
    """Spec 2026-11-14 9, as changed on the review of Task 7: 14.2's row names a net income
    guidance over the count the company's EPS is per; 14.9 lists every metric the store takes,
    `net_income` a total stepped from the year before's net income line, and says the agent
    derives the NTM EPS from it over that count: the reported count on most rows, an applied
    `shares.diluted` that corrects the count of the same shares, the reported count where it adds
    an Up-C's units, never a count that holds committed shares; 14.3 quotes the anchor's refusal
    as the engine words it and says the check reads the record, not the figure; 14.6's drop reads
    either record; 16.2 reads its figures as totals; and 11's row cites every section that states
    the rule."""
    fourteen = _section(14)
    inputs = fourteen[fourteen.index("### 14.2") : fourteen.index("### 14.3")]
    rules = fourteen[fourteen.index("### 14.3") : fourteen.index("### 14.4")]
    follows = fourteen[fourteen.index("### 14.6") : fourteen.index("### 14.7")]
    guidance = fourteen[fourteen.index("### 14.9") :]
    assert (
        "from a clear full-year EPS guidance, or a net income one over the count the company's EPS"
        " is per (14.9)"
    ) in inputs
    assert f"the metric, one of {', '.join(f'`{m}`' for m in METRICS[:-1])} and" in guidance
    assert f'"metric is one of {", ".join(METRICS[:-1])} or {METRICS[-1]}"' in guidance
    for words in (
        "`net_income` a total in the reporting currency",
        "for a fiscal-year `revenue`, `eps` or `net_income` record on the `gaap` basis the step",
        "`fact:<symbol>/net_income/<year>`",
        "A company that guides net income alone backs it with that record",
        (
            "the record's midpoint over the count the company's EPS is per, the count the"
            " shareholders' net income is shared among. On most rows that is the reported diluted"
            " count, `snapshot:<id>/inputs/shares_diluted`."
        ),
        (
            "Where an applied `shares.diluted` corrects the count of the same shares (the vendor's"
            " figure was wrong or stale, or it left out a class of common stock that shares the"
            " earnings), it is that figure, cited through its bridge line."
        ),
        (
            "Where an applied `shares.diluted` adds the units of an Up-C, whose share of the"
            " earnings is a minority's (14.4), it is the reported count, since the EPS is a"
            " Class A share's. It never holds committed shares."
        ),
    ):
        assert words in guidance, words
    assert "the count the consensus is on" not in guidance
    assert f'"{anchor_misfit("earnings.ntm")}"' in rules
    assert "`eps` or `net_income` for `earnings.ntm` and `revenue` for `revenue.ntm`" in rules
    assert "The check reads the record, not the override's figure against it" in rules
    assert "an `eps` or a `net_income` record for `earnings.ntm`" in follows
    assert "currency for revenue, net income, free cash flow and capex" in _section(16)
    row = next(x for x in _section(11).splitlines() if x.startswith("| 1.4, policy v16 |"))
    assert (
        "the agent dividing a net income's midpoint by the count the company's EPS is per, the"
        " guided-year drop reading either (14.2, 14.3, 14.6, 14.9, 16.2)"
    ) in row


def test_a_sensitivity_marks_a_revenue_step_at_the_growth_the_charge_read() -> None:
    """14.8: a revenue step with no applied override is marked at the growth the charge read for
    its year, while the engine's reading of 14.4 stays the step found."""
    fourteen = _section(14)
    reading = fourteen[fourteen.index("### 14.8") : fourteen.index("### 14.9")]
    for words in (
        (
            "with no applied override is marked at the growth the Mature Growth charge read for its"
            " year, h_2 or h_3 of `charge.growth_by_year` (4.8)"
        ),
        (
            "else the earnings step as resolved, since an override at that figure gives the result"
            " in force"
        ),
        "the engine's reading of 14.4 stays the step found",
    ):
        assert words in reading, words


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
    # the count is the snapshot's, so an agent's two share inputs do not reach it (the
    # whole-branch review of spec 2026-11-14)
    assert (
        "So the secondary valuation divides by the snapshot's reported diluted count, and neither"
        " an agent's `shares.diluted` nor its `shares.committed` (14.2) reaches it."
    ) in section


def test_section_16_names_the_six_failures() -> None:
    section = _section(16)
    for failure in FAILURES:
        assert f"`{failure}`" in section, failure
    for form in ("snapshot", "review", "secondary", "fact", "table", "estimate", "close", "peer"):
        assert f"`{form}:" in section, form
    for form in ("finding", "guidance", "derived", "sensitivity", "response", "policy"):
        assert f"`{form}:" in section, form
    assert "`stance_words`" in section
