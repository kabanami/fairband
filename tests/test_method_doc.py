"""``docs/method.md`` against the engine: the sections that name the engine's terms name all of
them."""

from pathlib import Path
from typing import get_args

import pytest

from fairband.engine.mature_growth import _fade
from fairband.engine.overrides import OverrideTag, anchor_misfit
from fairband.engine.secondary import SECONDARY_METHOD
from fairband.policy import load_policy
from fairband.reports.check import FAILURES
from fairband.store.guidance import METRICS
from fairband.web.reviews_api import FIXED_NUMBERS, NEEDS_A_FIGURE

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


def test_a_finding_and_a_guidance_record_name_their_currency() -> None:
    """Spec 2026-11-15 9.1, 9.2: 16.2 says a finding and a guidance record may name the currency
    of a money figure, with the form's and the figure's refusals, none meaning the reporting
    currency, and that every read answers it; 14.9 lists the currency among the record's fields
    and its refusals, and says a record in another currency than its actual takes no step."""
    fourteen = _section(14)
    guidance = fourteen[fourteen.index("### 14.9") :]
    for words in (
        "its currency, where it names one (16.2)",
        '"a guidance record needs its source", then a currency\'s two (16.2)',
        (
            "Nor is there a step on a record whose stored currency (16.2) is not that actual's, the"
            " currency of that year's statement (a year whose statement names none takes the year"
            " before's), since its midpoint over an actual in another currency is no growth (spec"
            " 2026-11-15 9.2); a record that names no currency steps as before."
        ),
    ):
        assert words in guidance, words
    sixteen = _section(16)
    references = sixteen[sixteen.index("### 16.2") : sixteen.index("### 16.3")]
    for words in (
        (
            "A finding and a guidance record may name the currency the company states a money"
            " figure in (spec 2026-11-15 9.1): a finding of unit currency or per-share, a guidance"
            " record of `revenue`, `net_income`, `free_cash_flow`, `capex` or `eps`."
        ),
        (
            'The code is three capital letters, checked for its form and not against a list, "a'
            ' currency is three capital letters, not <what was written>", and goes with a money'
            ' figure alone, "a currency goes with a money figure"; it is stored as given, also'
            " when it is the reporting currency."
        ),
        (
            "A record that names none is in the reporting currency, as every record before it:"
            " the currency of the company's latest snapshot as its money reads, USD where the"
            " company has no snapshot."
        ),
        (
            "Every read of a finding or a guidance record (`findings`, `guidance`, the drawer's"
            " research read) answers `currency`: the stored code, else the reporting currency;"
            " none for a figure that is not money."
        ),
    ):
        assert words in references, words


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


def test_the_tables_carry_their_columns_past_the_last_fiscal_year() -> None:
    """Spec 2026-11-15 6.1 to 6.3 and 6.5: 16.5 states the columns, the three tables' trailing
    cells and the growth table's estimate cells; 16.2 the periods of a ``table:`` ref, their
    words, and the check reading ``2026E`` as the year."""
    sixteen = _section(16)
    tables = sixteen[sixteen.index("### 16.5") : sixteen.index("### 16.6")]
    for words in (
        (
            "computed by the server from the stored statements, the engine's readings and the"
            " stored consensus"
        ),
        "A cell that is one stored line cites it as `fact:`, a consensus figure as `estimate:`",
        (
            "A table carries its columns, and each row one cell under each column, in order, the"
            " cell's period the column's"
        ),
        "the `/financial-tables` read serves each table with its `columns`",
        (
            'the trailing twelve months, its period `ttm` and its label "12 months to" and the'
            ' trailing period\'s end as the references write a day ("12 months to 30 Sep 2026")'
        ),
        (
            "an estimate, its period the consensus year and `E` (`2026E`) and its label the year"
            ' and "estimate" ("2026 estimate")'
        ),
        (
            "Three tables, growth, cash flow and capital allocation, gain one trailing column after"
            " the fiscal years"
        ),
        (
            "It stands when the trailing figures (4.2) are on file, are sums of stored periods and"
            " not the last fiscal year standing in, and end after the newest fiscal year's period"
            " end; otherwise the table has no trailing column."
        ),
        "each citing `fact:<symbol>/<line>/ttm`",
        "each citing itself, `table:<symbol>/<table>/<row>/ttm`",
        (
            "the sum of the stored periods (16.9) a year earlier: as many as the trailing figures"
            " sum, each ending 80 to 100 days after the one before (170 to 195 for half-years,"
            " 4.2), and the trailing figures' first likewise after the last of them;"
        ),
        (
            'where those are not all stored it holds no figure, noted "fewer than two years of'
            ' periods on file"'
        ),
        'The gross margin holds none, noted "not measured over the trailing twelve months"',
        (
            'The share count change holds none under the same note, and acquisitions none, "not on'
            ' file"'
        ),
        "Returns, solvency and quality keep their fiscal columns alone",
        "The growth table alone gains estimate columns, after the trailing column",
        (
            "the consensus fiscal years after the newest fiscal year on file that hold a revenue or"
            " an EPS, in order, three at most, each read as its `estimate:` ref reads it (16.2)"
        ),
        "citing `estimate:<symbol>/<year>/revenue` and `estimate:<symbol>/<year>/eps`",
        (
            "the newest fiscal year's reported revenue for the year after it and the year before's"
            " consensus revenue for a later one"
        ),
        "cites itself, `table:<symbol>/growth/revenue_growth/<year>E`",
        (
            "Every estimate cell of the EPS is noted \"on the analysts' own basis, which can leave"
            " out items the reported EPS includes\": the analysts' EPS often leaves out stock pay"
            " or other items the reported diluted EPS includes. The revenue's estimate cells carry"
            " no note: the revenue consensus is on the reported basis."
        ),
        'The gross, operating and net margins hold none, noted "no estimate for this line"',
        (
            "A consensus year already reported, or one with neither a revenue nor an EPS, gives no"
            " column, and no other table gains one"
        ),
    ):
        assert words in tables, words
    references = sixteen[sixteen.index("### 16.2") : sixteen.index("### 16.3")]
    for words in (
        (
            "| `table:<symbol>/<table>/<row>/<period>` | a cell of the financial tables (16.5) by"
            " its column's period: a fiscal year (`2025`), `ttm` for the trailing twelve months,"
            " or a consensus year and `E` for an estimate (`2026E`)"
        ),
        '"the growth table, revenue growth, the trailing twelve months"',
        '"the growth table, revenue growth, fiscal 2026, the analysts\' estimate"',
        "so a cite of an estimate column no longer on file reads the same",
        "The check reads `2026E`, and `FY2026E`, as the year, `2026`",
        (
            "a cite of an estimate cell may give either, on the `estimate:` ref and on a `table:`"
            " ref alike, and no cite is refused for the letter"
        ),
    ):
        assert words in references, words


def test_the_quarters_table_stands_beside_the_six() -> None:
    """Spec 2026-11-15 6.4 and 6.5: 16.5 states the quarters table, its columns, its rows and
    their refs, the margin's empty cells, the table with no column and a half-year filer's; 16.2
    the quarter period of a ``table:`` ref and its words."""
    sixteen = _section(16)
    tables = sixteen[sixteen.index("### 16.5") : sixteen.index("### 16.6")]
    for words in (
        (
            "The quarters table of the report's section 5 stands beside the six, not among them"
            " (spec 2026-11-15 6.4): the newest eight stored periods in the reporting currency"
            " (16.9), oldest first"
        ),
        (
            "each a column of its own kind, a quarter, its period the stored period's label"
            ' (`2026-Q3`) and its label the fiscal period and the fiscal year ("Q3 2026")'
        ),
        (
            "Its rows are the revenue and the EPS, each the stored period's line, citing"
            " `fact:<symbol>/revenue/<period>` and `fact:<symbol>/eps_diluted/<period>`"
        ),
        (
            "the operating margin, the period's operating income over its revenue, citing itself,"
            " `table:<symbol>/quarters/operating_margin/<period>`"
        ),
        (
            "the margin holds no figure where either line is missing or the revenue is at or"
            " below zero"
        ),
        "A company with no stored period has the table with no column.",
        "A half-yearly reporter's columns are its half-years, under the store's own period names",
        (
            "The `/financial-tables` read serves the table beside the six, under `quarters`, and"
            " the six alone under `tables`."
        ),
    ):
        assert words in tables, words
    references = sixteen[sixteen.index("### 16.2") : sixteen.index("### 16.3")]
    for words in (
        (
            "or a consensus year and `E` for an estimate (`2026E`); on the quarters table, a stored"
            " period's label (`2026-Q3`); a period the table has no column for is `unresolved"
            " reference`"
        ),
        "a year, `ttm`, a year and `E` (`2026E`) or a stored period's label (`2026-Q3`)",
        '"the quarters table, operating margin, Q3 of fiscal 2026"',
    ):
        assert words in references, words


def test_the_export_lists_its_references_last_and_carries_the_columns() -> None:
    """Spec 2026-11-15 6.5 and 9: 16.6 states the export's order, the references after Appendix
    B; the chart tables' columns under their labels and the "Period" corner; section 5's quarters
    table; and the statistics rows named as the year-end table's columns."""
    sixteen = _section(16)
    export = sixteen[sixteen.index("### 16.6") : sixteen.index("### 16.7")]
    for words in (
        (
            "so no ref appears in the text; then Appendix A as tables and Appendix B as a list;"
            ' and last, under "References", a line `[^n]: <ref> — <source>` for each ref'
        ),
        "GitHub-flavoured Markdown renders footnote definitions at the end of the document",
        "The page keeps its order, the references after the last section.",
        (
            "A financial table's twin has a column for each of the table's columns (16.5), under"
            ' its label ("2025", "12 months to 30 Sep 2026", "2026 estimate", "Q3 2026"), and its'
            ' header\'s first cell reads "Fiscal year" where every column is a fiscal year and'
            ' "Period" where one is not'
        ),
        (
            "over the last five fiscal years, then on growth, cash flow and capital allocation the"
            " trailing twelve months and on growth the estimate years"
        ),
        (
            'in The last earnings call one table, "By quarter", before its text: the quarters'
            " table of 16.5, its rows the revenue, the operating margin and the EPS, under"
            ' "Period", with no rows where no period is stored, a valuation review\'s as a full'
            " report's"
        ),
        (
            "each row named as the year-end table's column and the page's chart, \"Trailing P/E\""
            ' and "Forward P/E"'
        ),
    ):
        assert words in export, words
    assert 'after the last section, under "References"' not in export


def test_the_page_draws_the_bars_past_the_fiscal_year_and_by_quarter() -> None:
    """Spec 2026-11-15 6.5 and 6.6: 16.6 states that the page reads the quarters table beside the
    six and draws section 5's three charts by quarter, the trailing and the estimate bars and the
    line under a chart that has one, which names the EPS estimates' basis where their cells carry
    it, as the export's line under the growth table does (the whole-branch review's I2); that the
    axis prints every bar's tick up to seven bars and every other one on more, none within a
    stride of the last bar's or of the trailing twelve months', which print always, as the
    first's does (its I3); that a chart table's cell is empty where the table holds no figure,
    which a trailing or an estimate cell may not measure; and that a chart table with no rows
    reads "No data on file." in the export, as on the page (its M8)."""
    sixteen = _section(16)
    export = sixteen[sixteen.index("### 16.6") : sixteen.index("### 16.7")]
    for words in (
        "a day as the references write it, and an empty cell where the table holds no figure.",
        (
            "the page reads the series itself: the six tables and the quarters table beside them,"
            " the readings the sections cite"
        ),
        (
            'in The last earnings call three charts by quarter under "By quarter", the revenue, the'
            " operating margin and the EPS, each by its row's name, each bar's tick its quarter and"
            ' the last two digits of its year ("Q3 26"), and where no period is stored the three'
            ' with "No data on file.";'
        ),
        (
            "A bar chart draws a bar for each column of its table that holds a figure, the table"
            " twin naming each by the column's label"
        ),
        (
            "and its axis prints every bar's tick up to seven bars and every other one on more,"
            " none within a stride of the last bar's or of the trailing twelve months', which"
            " print always, as the first's does (eight quarters print the first, third, fifth and"
            " eighth ticks; nine bars ending in the trailing twelve months' and three estimates"
            " the first, third, sixth and ninth):"
        ),
        (
            "the fiscal years', each ticked by its year, then the trailing twelve months' filled"
            ' in grey and ticked "to date", then the estimates\' as outlines, each ticked by its'
            ' period ("2026E"), the value printed over the last bar that is not an estimate'
        ),
        (
            '"Grey: the 12 months to 30 Sep 2026. Outlined: analysts\' estimates.", the first'
            " sentence alone without an outlined bar and the second alone without a grey one,"
            " the second followed by the drawn estimates' note, after a comma, where their cells"
            " carry one, the EPS's: \"Outlined: analysts' estimates, on the analysts' own basis,"
            ' which can leave out items the reported EPS includes."'
        ),
        (
            "Under the growth table's twin, where an estimate cell of its EPS holds a figure, the"
            " export prints one plain line after the rows, \"EPS estimates are on the analysts'"
            ' own basis, which can leave out items the reported EPS includes."; no other twin'
            " has a line."
        ),
        (
            'A twin with no rows reads "No data on file." in the export, as its chart does on the'
            " page."
        ),
        "The annual charts never hold a quarter.",
    ):
        assert words in export, words
    assert "an empty cell where none is on file" not in export
    assert "a bar marked by its quarter" not in export and 'marked "to date"' not in export
    assert "the first's, the last's and the trailing twelve months' always" not in export


def test_the_lines_above_the_sections_and_appendix_a_s_dates_are_in_the_reader_s_words() -> None:
    """Spec 2026-11-15 7: 16.6 states the export's two opening lines and its line on a reused full
    report in the reader's words, the page's line under the title by the same rule, Appendix A's
    dates in words and its sentence for no secondary valuation without "the route"; and, since
    those lines name no record, the Snapshot part that opens Appendix A on the page and in the
    export alike, which names the snapshot the report rests on (the whole-branch review's I1)."""
    sixteen = _section(16)
    export = sixteen[sixteen.index("### 16.6") : sixteen.index("### 16.7")]
    for words in (
        (
            "Appendix A: the snapshot the report rests on, with the reporting currency its money"
            " figures are in (section 7; USD for a row with no rate), in one line that opens it,"
            " the page's and the export's alike but for the export's thousands separator from"
            ' $1,000 up ("$1,507.85" where the page writes "$1507.85"): its id, its data date, its'
            " price date, the end"
            " of its window, its price and its value a share, and last, on a company in another"
            ' currency, the currency ("Snapshot 412 · data 4 Nov 2026 · priced 4 Nov 2026 · valid'
            ' until 27 Jan 2027 · price $150.00 · value $128.00 · in SEK"), a dash for a date or a'
            " figure the snapshot has none of, and a refused snapshot's refusal after the line;"
        ),
        (
            "The Markdown export opens with a line naming the company, the mode, the date, the"
            ' actor and the revision ("GOOG · full report · 9 Nov 2026 · claude-opus-5-5 ·'
            ' revision 1"), then a line naming the stance and what the report rests on'
        ),
        (
            '"On the data of" and the snapshot\'s data date, then "priced that day" where the'
            ' price date is the same day, "priced" and the price date where it is another and'
            ' nothing where the snapshot has none, then "valid until" and the date'
        ),
        '("Stance: hold. On the data of 4 Nov 2026, priced that day, valid until 27 Jan 2027.")',
        (
            "a valuation review's next line names the full report it reuses by its date, \"Reuses"
            ' the full report of 3 Nov 2026." ("Reuses an earlier full report." where that'
            " report's record is not on file, so a stored report always renders), or says \"No"
            ' full report to reuse."'
        ),
        (
            "The page's line under the title follows the same rule, its parts joined by"
            ' "·", the full report a valuation review reuses last ("On the data of 4 Nov 2026 ·'
            ' priced that day · valid until 27 Jan 2027 · reuses the full report of 3 Nov 2026"),'
            " that part left out where the reused report's record is not on file, where the"
            ' export writes "Reuses an earlier full report.", and names no record: the'
            " snapshot's and the review's ids are in Appendix A."
        ),
        (
            "The export writes Appendix A's dates in words, as the references write a day: the"
            ' Snapshot line\'s, the Inputs table\'s "As of" and the guidance\'s "Call". A date'
            " input's note, the next earnings date, is in words too."
        ),
        (
            '"No secondary valuation: Fairband\'s own valuation gives the company a value" where'
            ' the snapshot has a value, "No secondary valuation: the review gives the company a'
            ' value" where the report\'s review has one, or "No secondary valuation: " followed'
            " by the snapshot's refusal in its own words"
        ),
        '"No secondary valuation: no diluted share count"',
    ):
        assert words in export, words
    for gone in (
        "then the stance and the snapshot with its price date",
        "no secondary valuation: the route values the company",
        "no secondary valuation: the review values the company",
        "Reuses full report",
    ):
        assert gone not in export, gone


def test_appendix_a_shows_an_override_scaled_at_a_split_with_both_figures() -> None:
    """Spec 2026-11-15 8: 16.6 states that Appendix A shows an override the review applied at a
    split with the review's pair in force, both on the new basis, and the words of the scaling, the
    export after the new figure in brackets and the page under the record, read from the stored
    review, a step that refused included; one with no bridge line or in a review written before
    the scaling, its stored pair (the Task 7 review's ruling). 14.6's sentence on the note points
    to it."""
    sixteen = _section(16)
    export = sixteen[sixteen.index("### 16.6") : sixteen.index("### 16.7")]
    for words in (
        (
            "the overrides inside the review with their reasons and evidence, each with its old"
            " and new figures as stored, but one the review applied at a figure other than the one"
            " entered, because a split fell between (14.6), with the review's pair in force, its"
            " bridge line's old and new, both on the new share basis, and the words the scaling"
            " added to its JUDGMENT entry's note, \"entered as $30.00 a share before the 2-for-1"
            ' split of 27 Jan 2027"'
        ),
        "a reading of $60 cut to $30 before a 2-for-1 split shows $30.00 and $15.00 with the words",
        "never $60.00 and $15.00",
        "the export writing the words after the new figure in brackets and the page under the record",
        (
            "both read from the stored review, never from the splits on file when the report is"
            " read; a step that refused was applied at the figure in force and met its refusal"
            " there, so its override shows the pair in force and the words too, while an override"
            " with no bridge line, in the empty bridge of a failed fetch, valuation or review, or"
            " one in a review written before the scaling existed, shows its figures as stored"
            " (spec 2026-11-15 8)"
        ),
    ):
        assert words in export, words
    assert "an override whose step refused, or one in a review written before" not in export
    fourteen = _section(14)
    follows = fourteen[fourteen.index("### 14.6") : fourteen.index("### 14.7")]
    assert (
        "A report's Appendix A shows such an override with the review's pair in force and these"
        " words (16.6)."
    ) in follows


def test_the_belief_is_the_rate_the_path_fades_to_over_the_fade_years() -> None:
    """The reviews of the report reader's plan (Task 10): 5.4 says what the belief is in 5.5's
    terms, the rate the path fades down to and then holds, not "the growth for years 4 to N, before
    the fade"; 5.5 writes the fade over F = `fade_years`, the setting the engine reads (4.1, 4.8),
    with the defaults' worked sentence; the glossary's Belief and Fade and the sources' row say the
    same. The formula is the engine's (`mature_growth._fade`), here on a fade of three years."""
    five = _section(5)
    four = five.split("### 5.4 The belief\n\n", 1)[1].split("\n\n", 1)[0]
    assert four.startswith(
        "The growth rate the earnings path settles at after the consensus years (5.5): where the"
        " year-3 growth is higher, years 4 to 3 + F fade down to it, F the fade years"
        " (`fade_years`), and every later year to the runway's end N grows at it. It is the"
        " Base Rate Book median ten-year net-income growth for the company's sales class"
        " plus 2 points."
    ), four
    path = five.split("### 5.5 The growth path\n\n", 1)[1].split("\n### ", 1)[0]
    for words in (
        (
            "With belief b, year-3 growth g_3 and F = `fade_years` (5 at the defaults; 4.1): if"
            " g_3 > b, years 4 to 3 + F fade in F equal steps,"
        ),
        "g_t = b + (g_3 − b) × (3 + F − t) ÷ F, for t = 4 … 3 + F,",
        (
            "so g_{3+F} = b, and years 4 + F to N grow at b. At the defaults years 4 to 8 fade and"
            " g_8 = b."
        ),
        (
            "If g_3 ≤ b, years 4 to N grow at b. The runway cuts the path. At the defaults, with"
            " N = 5 the path ends at g_5 mid-fade."
        ),
    ):
        assert words in path, words
    assert load_policy().fade_years == 5
    g3, belief, years = 0.20, 0.05, 3
    formula = tuple(belief + (g3 - belief) * (3 + years - t) / years for t in range(4, 4 + years))
    assert _fade(g3, belief, years) == pytest.approx(formula)
    glossary = _section(13)
    for row in (
        (
            "| Belief | The growth rate the value assumes after the analysts' forecast years: where"
            " year 3's growth is higher, growth eases down to it over the fade, then holds at it"
            " as far as the runway reaches; the base-rate median plus 2 points |"
        ),
        (
            "| Fade | The equal steps from the year-3 consensus growth down to the belief, one a"
            " year over the fade years, a setting, five at the defaults |"
        ),
    ):
        assert row in glossary, row
    assert "| The fade in equal steps, five at the defaults |" in _section(12)
    text = METHOD.read_text(encoding="utf-8")
    for old in ("years 4 to 8 fade in five equal steps", "The growth for years 4 to N, before"):
        assert old not in text, old


def test_section_16_names_the_six_failures() -> None:
    section = _section(16)
    for failure in FAILURES:
        assert f"`{failure}`" in section, failure
    for form in ("snapshot", "review", "secondary", "fact", "table", "estimate", "close", "peer"):
        assert f"`{form}:" in section, form
    for form in ("finding", "guidance", "derived", "sensitivity", "response", "policy"):
        assert f"`{form}:" in section, form
    assert "`stance_words`" in section


def test_a_fixed_number_is_an_operand_of_derive_alone() -> None:
    """Spec 2026-11-15 7.1 to 7.4: 16.2 names the operand form `number:`, an operand of `derive`
    alone, and a derivation resting on every snapshot of its operands; 16.3 the number cite's
    refusal and the snapshot test of every operand; 16.4 the list, the two refusals, the unit
    table, the references' words and growth from a base at or below zero."""
    sixteen = _section(16)
    references = sixteen[sixteen.index("### 16.2") : sixteen.index("### 16.3")]
    for words in (
        (
            "a `derived:` ref on every snapshot its operands rest on, through nested derivations"
            " (spec 2026-11-15 7.4)"
        ),
        (
            "`number:<n>` is no reference a report cites: it is an operand of `derive` alone"
            " (16.4), a fixed number of the server's list written in digits alone, with no unit,"
            " resting on no snapshot (spec 2026-11-15 7.3)"
        ),
    ):
        assert words in references, words
    check = sixteen[sixteen.index("### 16.3") : sixteen.index("### 16.4")]
    for words in (
        (
            "A `number:` cite names nothing, a fixed number being an operand of `derive` alone"
            ' (16.4); the detail says so, "number:100 is an operand of derive: cite the'
            ' derivation".'
        ),
        (
            "A `derived:` cite is tested on every snapshot its operands rest on, through nested"
            " derivations (spec 2026-11-15 7.4), so a derivation whose second operand, or an"
            " operand of an operand, rests on an older snapshot fails"
        ),
    ):
        assert words in check, words
    derivations = sixteen[sixteen.index("### 16.4") : sixteen.index("### 16.5")]
    for words in (
        (
            "A division by zero, a growth or a cagr from a base at or below zero, a cagr over a"
            " negative ratio and a result that is not finite have no value."
        ),
        "a derivation stored before the rule keeps its value",
        "it rests on every snapshot its operands rest on, through nested derivations",
        (
            "the whole numbers 0 to 12, then 52, 100, 365, 1000 and each further power of ten up"
            " to 1,000,000,000,000"
        ),
        (
            '"a fixed number is one of 0 to 12, 52, 100, 365 or a power of ten up to'
            ' 1,000,000,000,000, not <what was written>"'
        ),
        'two numbers in one derivation, "a derivation needs a stored figure"',
        "| `sum`, `difference`, `product` with a number | the stored figure's unit |",
        "| `ratio` of a figure over a number | the figure's unit |",
        "| `ratio` of a number over a figure | none |",
        "| `growth`, `cagr` | percent, as ever |",
        (
            'writes the number without its prefix, with separators: "derivation 1602: the'
            ' product of filing:95122/… and 1,000,000"'
        ),
    ):
        assert words in derivations, words
    assert FIXED_NUMBERS in derivations
    assert NEEDS_A_FIGURE in derivations


def test_a_kill_criterion_holds_a_threshold_cited_in_its_section_alone() -> None:
    """Spec 2026-11-15 8.1, 8.2: 16.2 names the form `kill:`, the threshold's record with its
    refusals and its words in the references; 16.3 the section rule, an unresolved reference
    elsewhere with its detail, and no arithmetic; 16.4 the one ref of 16.2 `derive` refuses."""
    sixteen = _section(16)
    references = sixteen[sixteen.index("### 16.2") : sixteen.index("### 16.3")]
    for words in (
        (
            "| `kill:<id>` | a kill criterion's threshold, the number the author chose for it,"
            " whatever the criterion's state; a criterion with no threshold names nothing |"
            " the threshold's |"
        ),
        (
            "A kill criterion may hold one threshold, a number the author chose (spec 2026-11-15"
            " 8.1): the number, its unit, one of a finding's, and for a money figure its currency,"
            " by the rule of a finding's above."
        ),
        (
            "The number and the unit come together, \"a kill criterion's threshold and unit come"
            ' together", and the number is finite, "a kill criterion\'s threshold is a finite'
            " number\"; the criterion's text stays its statement and is never checked."
        ),
        "a report's own kill criteria (16.1) are text alone",
        (
            "`kill:<id>` resolves to the threshold with its unit, and a money threshold with its"
            " currency as a finding's figure does, of no period and resting on no snapshot,"
            " whatever the criterion's state, so a published report's references keep their words"
            " once the criterion is triggered or retired; the references list says whose number it"
            ' is, "kill criterion 12, a threshold the author chose".'
        ),
        (
            "Every read of a criterion (`kill_criteria`, the drawer's research read) answers its"
            " `threshold`, its `unit` and its `currency`, as a finding's."
        ),
    ):
        assert words in references, words
    check = sixteen[sixteen.index("### 16.3") : sixteen.index("### 16.4")]
    for words in (
        (
            'A `kill:` cite, a number the author chose (16.2), passes in one section alone, "Risks'
            ' and kill criteria", known by its heading: section 11 of a full report, the ninth of'
            " a valuation review."
        ),
        (
            "There it is checked as a `finding:` cite is; anywhere else it is `unresolved"
            " reference`, \"kill:12 is the author's own threshold: cite it in Risks and kill"
            ' criteria", so a chosen number enters no other section (spec 2026-11-15 8.2).'
        ),
        (
            'Nor does it enter arithmetic: `derive` takes no `kill:` operand, "unresolved'
            ' reference: kill:12", as for a ref that names no number.'
        ),
    ):
        assert words in check, words
    derivations = sixteen[sixteen.index("### 16.4") : sixteen.index("### 16.5")]
    words = (
        "over two refs of 16.2 resolved for the company, a table cell included, but `kill:`, a"
        ' number the author chose, which is the 400 "unresolved reference: kill:12" (16.3).'
    )
    assert words in derivations


def test_a_record_s_currency_is_read_by_the_resolver_derive_and_the_check() -> None:
    """Spec 2026-11-15 9.3, 9.4: 16.2 says a resolved record's money figure carries its currency
    and every other ref none; 16.3 the `$` rule the server checks for a record, the detail with
    the code, and the playbook's for every other ref; 16.4 a record in another currency and its
    two rules with their examples."""
    sixteen = _section(16)
    references = sixteen[sixteen.index("### 16.2") : sixteen.index("### 16.3")]
    for words in (
        (
            "Each resolves to a value (a number, a word, or none where the record holds no"
            " figure), a unit, a period and the snapshot it rests on, and a record's money figure"
            " to its currency too (below)."
        ),
        (
            "The resolver reads it alike (spec 2026-11-15 9.3): a `finding:` and a `guidance:`"
            " low, high or midpoint of a money figure resolve with that currency, the reporting"
            " currency read once for all the refs of a report or of a `derive` call; a guidance"
            " step, a percent, resolves with none."
        ),
        (
            "The resolver knows the currency of a record alone: every ref of another form resolves"
            " with none, a `fact:`, an `estimate:` or a snapshot's figure of a company in another"
            " currency among them, as before (spec 2026-11-15 3, 14)."
        ),
        (
            "So the server checks the `$` rule (16.3) and keeps a record in another currency out"
            " of money arithmetic (16.4) for a record alone."
        ),
    ):
        assert words in references, words
    check = sixteen[sixteen.index("### 16.3") : sixteen.index("### 16.4")]
    for words in (
        (
            "A word cited against a number, or a word that is not the ref's, is also `wrong"
            " unit`, and so is a `$` on a record's money figure in another currency than USD"
            " (below)."
        ),
        "A figure in another currency than USD (section 7) takes no new rounding (spec 2026-11-10",
        (
            "`$` is for a figure in US dollars: the price, the value a share, the levels, a close,"
            " a grid's cells, a record's figure in US dollars."
        ),
        (
            "A figure of a company in another currency, a statement line, an input in the"
            " currency, a finding's, a guidance record's or a threshold's figure in the currency,"
            " an override's figure, a secondary valuation's total, is cited with no `$`"
        ),
        (
            "The server checks the rule for a record's money figure, whose currency the resolver"
            " knows (16.2; spec 2026-11-15 9.4): a `$` on a `finding:`, a `guidance:` or a `kill:`"
            " cite passes only where the record's currency is USD, a US-dollar record of a company"
            " in another currency among them, and on a record in any other currency is `wrong"
            ' unit`, "finding:812 reads TWD 1,000,000,000: write the number without $ and name TWD'
            ' before it"; every wrong-unit detail of such a figure writes it with its code where'
            ' `$` would stand, "SEK 12.50".'
        ),
        (
            "For every other ref the rule stays the playbook's: a `$` on a `fact:`, an `estimate:`"
            " or a snapshot's figure of a company in another currency still passes, and a detail"
            " still writes `$` on it (spec 2026-11-15 14)."
        ),
    ):
        assert words in check, words
    derivations = sixteen[sixteen.index("### 16.4") : sixteen.index("### 16.5")]
    for words in (
        (
            "A record in another currency (spec 2026-11-15 9.3) is a `finding:`, or a `guidance:`"
            " low, high or midpoint, whose currency (16.2) is not the company's reporting"
            " currency, in either direction: a US-dollar finding of a company that reports in TWD,"
            " a euro finding of one that reports in US dollars."
        ),
        (
            "A record that names the reporting currency, or names none, is not one, and derives as"
            " before."
        ),
        (
            "Such a record is kept out of money arithmetic until it is converted, by two rules: a"
            " derivation has no value, and no unit, where one operand is such a record and the"
            " other is a money figure (currency or per-share) that is not a record in that same"
            " currency; and a derivation with such an operand never has a money unit: where the"
            " unit rules above give currency or per-share, it has none, since a derivation carries"
            " no currency and a money unit on it would read as the reporting currency, so a"
            " US-dollar record times `number:1` has no unit."
        ),
        (
            "So a US-dollar finding of a TWD reporter with another US-dollar record gives a growth"
            " (a percent), a ratio (a multiple), or a sum or a difference with a value and no"
            " unit; times the rate, `snapshot:<id>/inputs/fx_rate` (TWD per US dollar, a figure"
            " with no unit), it is the figure in TWD, with no unit, which then combines with"
            " anything; and with a `fact:` revenue in TWD, or with a finding in the reporting"
            " currency, it has no value."
        ),
        (
            "Nor has it one with the price or a close, which are in US dollars but whose currency"
            " the resolver does not know (spec 2026-11-15 14)."
        ),
    ):
        assert words in derivations, words
