"""``docs/method.md`` against the engine: the sections that name the engine's terms name all of
them."""

import re
from importlib import resources
from pathlib import Path
from typing import get_args

import pytest

from fairband.engine import METHOD_VERSION
from fairband.engine.mature_growth import _fade
from fairband.engine.overrides import OverrideTag, anchor_misfit
from fairband.engine.review import REVIEW_METHOD
from fairband.engine.secondary import SECONDARY_METHOD
from fairband.policy import load_policy
from fairband.policy.moat_rule import CYCLICAL
from fairband.refresh.fetch import PAGE_ENDPOINTS
from fairband.reports.check import FAILURES
from fairband.store.guidance import METRICS
from fairband.web.reviews_api import DEPENDS_ON_A_FIGURE, FIXED_NUMBERS, NEEDS_A_FIGURE, REDERIVE

METHOD = Path(__file__).parent.parent / "docs" / "method.md"


def _section(number: int) -> str:
    """The text under the heading ``## <number>.``, to the next top-level heading."""
    text = METHOD.read_text(encoding="utf-8")
    start = text.index(f"\n## {number}. ")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def test_section_10_counts_the_page_s_answers_and_leaves_the_investor_relations_tab_s() -> None:
    """B-252: the full refresh's sentence counts the FMP answers only the company page shows
    (``fetch.PAGE_ENDPOINTS``) and the calls a company costs, and says a refresh fetches none of
    the Investor relations tab's three, which a reader's opening of the tab or an agent's tool
    fetches. 16.8 says the same of the filing list."""
    full = next(x for x in _section(10).splitlines() if x.startswith("- **Full refresh**"))
    assert len(PAGE_ENDPOINTS) == 14
    for words in (
        (
            "a full or scoped refresh fetches for each company fourteen FMP answers that only the"
            " company page shows and the method does not read (`fetch.PAGE_ENDPOINTS`, spec"
            " 2026-11-16 company page, 10.1, and spec 2026-11-17 financials tab, 8.1): twenty-nine"
            " calls a company, on either plan."
        ),
        "None is required, and none gives a fact or an observation.",
        (
            "A refresh fetches none of the Investor relations tab's answers (B-252; the founder,"
            " 2026-11-18 and 2026-11-25: a reader opens a few companies, and a refresh paid for"
            " all of them): a company's list of earnings calls (`transcript-dates`), its filings"
            " of the 365 days to the day (`sec-filings`) and a call's transcript are fetched as a"
            " reader opens the tab, or as an agent's tool asks, through the pass-throughs, each"
            " kept under its key and reused inside the reuse window; the tab reads a call's"
            " stored words whatever their age, draws a list on file at once and asks for a newer"
            " one where it is older than the window. The copies the refreshes before stored stay"
            " and are still shown."
        ),
        (
            "On a key whose plan is Premium (section 2) the pass-throughs ask neither the list of"
            " earnings calls nor a transcript, since FMP serves them on Ultimate alone, and what"
            " the store holds of the two from a time on Ultimate stays and is still shown."
        ),
    ):
        assert words in full, words
    for gone in ("sixteen FMP answers", "thirty calls a company", "newest call on the stored"):
        assert gone not in full, gone
    filings = _section(16)[_section(16).index("### 16.8") : _section(16).index("### 16.9")]
    assert "Of the three, a refresh fetches the filing list alone" not in filings
    assert (
        "A refresh fetches none of the three (section 10): only a request does, an agent's or the"
        " Investor relations tab's, whose first window is the filing list's default, the 365 days"
        " to the day, so on one day each reuses the other's copy."
    ) in filings


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
    rulings = next(
        x
        for x in rows
        if x.startswith(
            "| 1.5, policy v16 | 2026-11-15 | The runway return's rulings (founder 2026-11-15"
        )
    )
    assert rows[rows.index(rulings) + 1].startswith("| 1.6, policy v16 |")
    assert "The method is unchanged at 1.5: no mechanical value moves." in rulings
    assert "the moat's terminal rule reads it in place of the measure on every row" in rulings
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
    assert "`runway_return` gains `constant_margin`" in rulings
    # the cap is a setting; the other calls stand, and no cap bounds a return on capital near zero
    value = next(x for x in four.splitlines() if "| `return_without_goodwill_cap` | yes |" in x)
    assert "a setting since the founder's ruling of 2026-11-15" in value
    assert "`return_without_goodwill_cap` (25%), becomes a setting" in rulings
    assert "A return far above 100% on capital near zero stands with no cap" in rulings
    # B-8's last part: the chart and its table do not print a ROIC on capital at or below zero
    sixteen = _section(16)
    assert (
        "a ROIC year on average invested capital at or below zero written as its note"
    ) in sixteen
    assert "as the page's ROIC chart leaves that year out and names it under the chart" in sixteen
    assert "the report page's ROIC chart leaves a year on average invested capital" in rulings
    assert "an agent set at r, which sets the terminal return at r too (14.4)" in four


def test_the_adr_ratio_is_found_from_the_two_counts() -> None:
    """Spec 2026-11-19 6.2, method 1.6: 4.2 states the rule with its limits, FMP's ADR flag its
    guard; section 2 reads no ratio from GuruFocus; 5.12 and 7.1 make the input an estimate from the
    counts on the rows the rule found a ratio on; the note and the refusal lose "ADR ratio", the
    refusal row naming the old ending; 11 has the 1.6 row last."""
    four = _section(4)
    for words in (
        (
            "when FMP flags the company as an ADR (the ADR flag of section 2), the quote gives its "
            "count and a diluted count is on file. A row without the flag reads its counts as the "
            "split rule alone reads them."
        ),
        "No vendor on file states the ratio, so the rule finds it from the counts.",
        (
            "For a count c that differs from the count A it is judged against, the multiple m is "
            "A ÷ c, then A ÷ (c × the pending splits' ratio)."
        ),
        "A multiple between the two gives no candidate.",
        (
            "the diluted count against the quote's count; then, when the diluted count does not "
            "differ, each trailing period"
        ),
        (
            "oldest first, the newest against the quote's count and each older one against the "
            "diluted count. A period that differs and fits no whole number is passed over"
        ),
        (
            "\"share basis unclear: the newest period's count <c> against the quote's <Q>\", the "
            "counts in millions to one decimal, every figure as stored."
        ),
        "With a ratio found, a count fits a factor f of 1, ρ and 1 ÷ ρ, tried in that order",
        "1,450.8 m (the ratio 10)",
        'a count a third of the quote\'s reads "a third (the ratio 3)"',
        (
            "No whole number is too large to be a ratio: a count held in thousands reads as a "
            "ratio of 1,000."
        ),
        "so ρ is always the whole number, 3 where a vendor would state 0.3333",
    ):
        assert words in four, words
    for gone in ("the ADR ratio 10", "whatever FMP's ADR flag", "ADSs to one share"):
        assert gone not in four, gone
    two = _section(2)
    # section 2 names no GuruFocus call that runs (spec 2026-11-19 8.10) and no depositary ratio
    assert "No call goes to GuruFocus" in two and "depositary" not in two
    five = _section(5)
    assert "`adr_ratio` (unit `ratio`, an estimate under the method `counts-ratio`" in five
    assert "absent on every other row, an ADR whose counts agree among them included" in five
    seven = _section(7)
    assert "no vendor on file states it" in seven
    assert "GuruFocus's depositary receipt ratio" not in seven
    eight = _section(8)
    basis = next(x for x in eight.splitlines() if x.startswith("| `basis-scaled` |"))
    assert "by the ratio or its inverse" in basis
    assert "a flagged ADR the rule found a ratio on" in basis and "ADR ratio" not in basis
    refusal = next(x for x in _section(9).splitlines() if x.startswith("| share basis unclear"))
    assert refusal.startswith(
        "| share basis unclear: the newest period's count <c> against the quote's <Q> (a snapshot "
        'valued before method 1.6 may carry the ending " (the ADR ratio <ρ>)") | 4.2 |'
    )
    row = next(x for x in _section(11).splitlines() if x.startswith("| 1.6, policy v16 |"))
    assert row.startswith(
        "| 1.6, policy v16 | 2026-11-19 | The ADR ratio from FMP's two share counts (spec "
        "2026-11-19 6.2"
    )
    for words in (
        "No vendor's ratio is read",
        "FMP's ADR flag guards the rule",
        "On refresh 68, valued in memory on 2026-11-19, no value moved",
    ):
        assert words in row, words


def test_method_1_7_takes_no_gap() -> None:
    """Spec 2026-11-19 7.2 to 7.4, method 1.7: 4.1 has the two new values with their sources and
    not the non-recurring flag's share; 5.11 reads reason 1 by the warning's test; 5.12 and 6.5
    cite the street EPS on Mature Stable; 6.1 says the refusal carries the warning; section 8 has
    the spec's row for the warning, the twelve quality warnings with it in the place of
    ``large-nri``, and neither removed code; 11 has the 1.7 row before 1.8's. Spec 7.1, the gap
    taken out of the mechanical routes: 5.9 has the clean figures equal the reported ones but
    under an agent's gap; 6.1 takes E less an agent's gap alone; no route cites GuruFocus's EPS
    (5.12, 5a.14, 6a.10); 13 has the Words table's entry; 14.2 and 14.4 make the whole gap the
    agent's and the engine's reading 0.0; and the 1.7 row says so. The policy the head names, and
    the versions 4.1 keeps, are policy v18's (``test_policy_v18_drops_three_values``)."""
    text = METHOD.read_text(encoding="utf-8")
    four = _section(4)
    one_time = next(x for x in four.splitlines() if "| `one_time_items_share` | yes |" in x)
    assert (
        "the founder, 2026-11-19: of four thresholds tested on 392 Mature Stable rows" in one_time
    )
    mark = next(x for x in four.splitlines() if "| `warning_mark_min` | no |" in x)
    assert "the founder, 2026-11-19: three warnings or more" in mark
    # the final review of plan 2, Minor 2: a valued row whose counting review refuses is marked
    assert (
        "a mechanical value with 3 quality warnings or more and no reviewed value is marked"
    ) in mark
    # its Minor 1: the warning's compare, and reason 1's, allow for binary floating point
    constants = four[four.index("### 4.1a") : four.index("### 4.2")]
    assert (
        "the 1e-12 under `one_time_items_share` within which the warning `one-time-items` and the "
        "first reason of `sbc-basis-uncertain` read a share as at the threshold, so a gap of "
        "exactly 20% fires whatever binary floating point makes of it (section 8)."
    ) in constants
    assert "`nri_flag_share`" not in four
    five = _section(5)
    assert (
        "Reason 1: the test reads `includes-sbc` on a material stock pay where GAAP trailing EPS "
        "and the street's differ by `one_time_items_share` (20%) or more"
    ) in five
    stable = _section(6)
    assert "street trailing EPS" in stable[stable.index("### 6.5") :]
    assert "carries the warning `one-time-items` where its test holds" in stable
    eight = _section(8)
    row = next(x for x in eight.splitlines() if x.startswith("| `one-time-items` |"))
    # spec 7.2's row word for word, its formula's bars escaped so the table keeps three cells
    assert row == (
        '| `one-time-items` | yes | a Mature Stable row, valued or refused "no positive trailing '
        'earnings", whose GAAP trailing diluted EPS and street trailing EPS (5.12) differ by '
        "`one_time_items_share` (20%) of the GAAP figure's size or more: \\|GAAP − street\\| ÷ "
        "\\|GAAP\\| at the threshold less 1e-12 or more (4.1a), so a gap of exactly 20% fires "
        "whatever binary floating point makes of it; "
        "silent without a street figure, with a GAAP EPS of zero, and under an agent's "
        '`earnings.nri_gap`, which decides the items. Word "One-time items". The sentence names '
        "the two figures and the share: \"GAAP trailing EPS is $4.10 and the analysts' is $5.20, "
        "apart by 26.8% of GAAP EPS, at or above 20.0%. The trailing earnings may hold one-time "
        "items, which the mechanical value keeps; a review takes them out through "
        '`earnings.nri_gap`." |'
    )
    assert "They are `one-time-items`, `value-spread`," in eight
    outside_history = text.replace(_section(11), "")
    for gone in ("large-nri", "consensus-basis-unknown", "nri_flag_share"):
        assert gone not in outside_history, gone
    rows = [x for x in _section(11).splitlines() if x.startswith("| 1.")]
    row17 = next(x for x in rows if x.startswith("| 1.7, policy v17 |"))
    assert rows[rows.index(row17) + 1].startswith("| 1.8, policy v17 |")
    for words in ("`one-time-items`", "`large-nri`", "`consensus-basis-unknown`", "policy v17"):
        assert words in row17, words
    # spec 7.1: the mechanical routes take no gap
    clean = five[five.index("### 5.9") : five.index("### 5.10")]
    assert (
        "Clean trailing EPS = GAAP trailing diluted EPS − an agent's non-recurring gap "
        "(`earnings.nri_gap`, 14.4), nil without one."
    ) in clean
    assert (
        "on a mechanical row the clean figures, the clean EPS and the clean P/E, equal the "
        "reported ones, and EPV rests on the reported EPS; they differ under an agent's gap alone"
    ) in clean
    assert (
        "E = trailing net income − an agent's non-recurring gap × diluted shares; the mechanical "
        "route takes no gap (spec 2026-11-19 7.1)."
    ) in stable
    assert "GuruFocus EPS" not in outside_history and "the gap found" not in outside_history
    assert (
        "| Non-recurring gap | The one-time items in the trailing earnings a share, after tax, "
        "which an agent sets in a review; a net charge is negative |"
    ) in _section(13)
    fourteen = _section(14)
    gap_row = next(x for x in fourteen.splitlines() if x.startswith("| `earnings.nri_gap` |"))
    assert "the whole gap is the agent's, since the engine finds none" in gap_row
    reads = fourteen[fourteen.index("### 14.4") : fourteen.index("### 14.5")]
    for words in (
        "`earnings.nri_gap` is the non-recurring gap, the agent's whole figure",
        "which reads trailing GAAP EPS less the agent's figure, so an override of 0.0",
        (
            "nil on a Mature Growth or Mature Stable result without one (on a refusal, the route "
            "its phase takes) and none on any other route: the engine finds none, so a bridge's "
            "old value is 0.00"
        ),
    ):
        assert words in reads, words
    for words in ("no non-recurring gap", "`gf_eps_ttm`", "drops (14.6)", "values move"):
        assert words in row17, words
    # the final review of plan 2, T9-c: CLS's 36 is the one override of any kind that drops
    assert "PLTR's 20, lasting, stays, and no other override drops;" in row17


def test_the_overview_marks_a_value_with_no_reviewed_value() -> None:
    """The final review of plan 2, Minor 2: the mark waits on no reviewed value, not on no
    review, since a valued row whose counting review refuses is marked (method 8); the overview
    says so in its line on the flags."""
    overview = (METHOD.parent / "method-overview.md").read_text(encoding="utf-8")
    assert (
        "the screen marks a mechanical value with three or more and no reviewed value."
    ) in " ".join(overview.split())


def test_the_method_reads_no_gurufocus_key_ratios() -> None:
    """Spec 2026-11-19 7.1: the ``keyratios`` call goes, and with it the rules written for its two
    figures. Section 2 says no call goes to GuruFocus since spec 2026-11-19 8.10, its stored
    answers unread; the split rule and the listed-share basis (4.2), 7.1 and the currency's table
    (7.4) name no GuruFocus EPS, 7.4 bringing the street actuals alone into the currency; 1.7's row
    names the call and its stored answers, unread."""
    text = METHOD.read_text(encoding="utf-8")
    outside_history = text.replace(_section(11), "")
    for gone in (
        "keyratios",
        "gf-ratio",
        "GuruFocus's EPS",
        "GuruFocus's two EPS",
        "GuruFocus's trailing EPS",
        "GuruFocus states its EPS",
    ):
        assert gone not in outside_history, gone
    two = _section(2)
    assert "No call goes to GuruFocus (spec 2026-11-19 8.10)" in two
    assert "still runs" not in two and "`summary`" not in two
    seven = _section(7)
    assert "Assembly brings the street actuals into the currency" in seven
    assert "the mean of the trailing periods' period-end rates" not in seven
    row17 = next(x for x in _section(11).splitlines() if x.startswith("| 1.7, policy v17 |"))
    for words in ("`keyratios`", "`gf-ratio`", "unread", "`summary`"):
        assert words in row17, words


def test_method_1_8_reads_the_moat_table() -> None:
    """Spec 2026-11-19 8.5, 8.2 and 12, method 1.8: the head names the method; section 2 lists the
    moat table and no GuruFocus row; 4.9 is spec 8.5's text; 4.9a states the rule as it ran, its
    cyclical list the rule's 27 names; 5.1, 6b.1 and section 9 place the guard "no moat class";
    5.12 has the input's three forms and no route cites the moat score, and 5a.14, 6a.10 and 6b.6
    cite it after their RULE inputs; section 12 names the founder's table as the source; 11 has
    the 1.8 row under policy v17, before policy v18's, and neither says a GuruFocus call runs."""
    text = METHOD.read_text(encoding="utf-8")
    assert (
        "| Method version | `fairband-mechanical/1.10` (`fairband.engine.METHOD_VERSION`) |" in text
    )
    two = _section(2)
    assert "GuruFocus `summary` |" not in two
    assert "| Moat class | the packaged moat table `moat-classes-v1.toml`" in two
    assert "stay in the database, and the method reads none of them." in two
    four = _section(4)
    nine = four[four.index("### 4.9 ") : four.index("### 4.9a")]
    assert (
        "The moat class is the company's row in the moat table (`moat_classes`): Wide, Narrow or "
        "None. The table is Fairband's own."
    ) in nine
    assert (
        'A company with no row is refused, "no moat class" (5.1): one that entered the universe '
        "after the file was cut. The owner's class, an agent's verdict or the file's next version "
        "lifts the refusal. The moat enters in three places:"
    ) in nine
    assert "Moat Score" not in nine
    rule = four[four.index("### 4.9a") : four.index("### 4.10")]
    for words in (
        (
            "The rule writes the first class of a company in the moat table (4.9). The engine does "
            "not run it"
        ),
        "none with fewer than ten such years, or when either end is not above zero",
        "a tie in revenue ranks by symbol, A first",
        "It is steady with ten margins, none below 80% of their median.",
        (
            "A company on the cyclical list that meets rule 5 is Narrow; rule 3 comes first, so the "
            "list never lifts a None."
        ),
        "Semiconductors are left out on purpose",
        "Size is revenue, never market value",
        "`Chemicals - Specialty` is not on the list",
    ):
        assert words in rule, words
    listed = rule[rule.index("- Housing and construction:") : rule.index("Semiconductors")]
    assert set(re.findall(r"`([^`]+)`", listed)) == CYCLICAL and len(CYCLICAL) == 27
    assert "Oil & Gas Energy" not in rule
    five = _section(5)
    guards = five[five.index("### 5.1") : five.index("### 5.2")]
    assert (
        "The last guard before a route is the moat class (4.9): a company with no row in the moat "
        'table is refused "no moat class". A Start-up row meets it right before its route (6b)'
    ) in guards
    assert "Every other row is refused without trailing figures, then meets the guard." in guards
    inputs = five[five.index("### 5.12") : five.index("### 5.13")]
    for row in (
        (
            "| the file's | RULE, kind rule | \"moat table fairband-moat-v1\", the file's version "
            '| the entry\'s date | "Wide" |'
        ),
        (
            '| the owner\'s | JUDGMENT, kind judgment | "owner" | the day of the write | "Wide", or '
            '"Wide: <reason>" |'
        ),
        (
            '| an agent\'s | JUDGMENT, kind judgment | "agent claude-opus-5-5", the principal and '
            'the actor | the day of the write | "Wide: <reason>" |'
        ),
    ):
        assert row in inputs, row
    outside_history = text.replace(_section(11), "")
    assert "moat score;" not in outside_history and "no moat score" not in outside_history
    start_up = text[text.index("### 6b.1") : text.index("### 6b.2")]
    assert 'a Start-up row with no row is refused "no moat class"' in start_up
    assert "| no moat class | 4.9, 5.1 |" in _section(9)
    sources = _section(12)
    assert "the gate tests, the moat table |" not in sources
    assert "`docs/gurufocus-removal.md` 6.4" in sources
    rows = [x for x in _section(11).splitlines() if x.startswith("| 1.")]
    row = next(x for x in rows if x.startswith("| 1.8, policy v17 |"))
    assert row.startswith("| 1.8, policy v17 | 2026-11-21 | The moat table (spec 2026-11-19 8")
    for words in ('"no moat class"', "`moat_score`", "`moat_classes`", "unread", "74 corrections"):
        assert words in row, words
    # the acceptance's counts on refresh 68's data, each with its denominator (spec 2026-11-19 10),
    # as the 1.7 row gives plan 2's; the class triples read again on the acceptance's copy
    for words in (
        (
            "161, 1,155 and 47 over its 1,363 valued rows, where the Moat Score as the policy read "
            "it gave 145, 1,132 and 86"
        ),
        (
            "285 of the 1,488 companies with a class under both change it: 108 None to Narrow, 67 "
            "Narrow to Wide, 57 Narrow to None, 52 Wide to Narrow and 1 Wide to None"
        ),
        "1.7 refused 45 more before it read a class, and 25 are refused before either reads one",
        (
            "Of the 1,344 valued rows, 165 values move, 108 up and 57 down, 54 of them up and 12 "
            "down by 20% or more; 233 buy levels move, every valued row whose class changed"
        ),
        'No row crosses between valued and refused, and none is refused "no moat class".',
        (
            "Of the 28 reviews, one moves: CRM's, from $213.35 to $175.15, its mechanical value "
            "falling from $235.84 to $187.30 under Narrow."
        ),
        "TTMI's, NVO's and RELX's stay",
    ):
        assert words in row, words
    assert "plan 3's readout counts them" not in row
    # the 1.8 rows describe what ships, one version under policy v18: no GuruFocus call runs, and
    # the override of the tag is refused for the agent's verdict (the final review, I2 and M4)
    assert (
        "Assembly no longer reads GuruFocus's `summary`, and the call itself leaves with policy "
        "v18 (section 2)."
    ) in row
    assert (
        "An override of `moat.class` is refused: an agent records its verdict with `moat_set`, and "
        "a report needs that verdict on its snapshot (14.2, 14.3, 16.3)."
    ) in row
    for each in (x for x in rows if x.startswith("| 1.8, ")):
        assert "the fetch still asks" not in each and "runs until it goes" not in each
    # section 2 says nothing unchanged from nothing; 4.9a's margin skips a statement with no
    # revenue too; the routes' DATA lists hold no RULE or JUDGMENT input (the final review, M5 to
    # M7)
    assert "The retry counts and the run's 429 path are unchanged." not in two
    assert (
        "a statement without a gross profit or a revenue, or with a revenue of zero, gives no "
        "margin"
    ) in rule
    for start, end in (
        ("### 5a.14", "### 5a.15"),
        ("### 6a.10", "### 6a.11"),
        ("### 6b.6", "### 6b.7"),
    ):
        part = text[text.index(start) : text.index(end)]
        assert "`adr_ratio`, `fx_rate` and `inflation_differential` as 5.12;" in part, start
        assert "and `moat_class` as 5.12" not in part, start
        assert part.count(" The input `moat_class` as 5.12 cites it.") == 1, start
        rules = part.index(" RULE: ")
        assert part.index(" The input `moat_class` as 5.12 cites it.") > rules, start


def test_policy_v18_drops_three_values() -> None:
    """Spec 2026-11-19 8.9, policy v18 under method 1.8: the head names policy v18; 4.1 reads every
    value from the v18 file, keeps v1 to v17 while the engine loads v18, and holds no row for the
    Moat Score's two thresholds or GuruFocus's reuse window, nor names GuruFocus's observation
    dates in the rate history's source; section 2 names no GuruFocus call and no reuse window of
    7 days, since the call went (spec 2026-11-19 8.10); 11 has the v18 row last, after the 1.8 row
    under v17, saying no value moves."""
    text = METHOD.read_text(encoding="utf-8")
    assert (
        "| Policy version | `fairband-policy-v19` (`src/fairband/policy/fairband-policy-v19.toml`) |"
    ) in text
    assert (
        "| Method version | `fairband-mechanical/1.10` (`fairband.engine.METHOD_VERSION`) |" in text
    )
    four = _section(4)
    assert "Every value comes from `fairband-policy-v19.toml`" in four
    assert (
        "Policies v1 to v18 stay in the package unchanged, because the snapshots valued under them "
        "cite their hashes. The engine loads v19 only."
    ) in four
    outside_history = text.replace(_section(11), "")
    for gone in ("`moat_wide_min`", "`moat_narrow_min`", "`refresh.gf_reuse_days`"):
        assert gone not in outside_history, gone
    assert "Reuse window, GuruFocus" not in four and "Moat: score" not in four
    depth = next(x for x in four.splitlines() if "| `refresh.fx_history_years` | no |" in x)
    assert (
        "spec 2026-11-10 9: the trailing periods' ends lie within 15 months, and three years "
        "leaves room; no source gives the number |"
    ) in depth
    assert "GuruFocus" not in depth
    assert "No call goes to GuruFocus" in _section(2) and "7 days" not in _section(2)
    rows = [x for x in _section(11).splitlines() if x.startswith("| 1.")]
    row = next(x for x in rows if x.startswith("| 1.8, policy v18 |"))
    assert row.startswith(
        "| 1.8, policy v18 | 2026-11-21 | The policy drops the Moat Score's two thresholds and "
        "GuruFocus's reuse window. "
    )
    assert row.endswith(" The method is unchanged at 1.8: no value moves. |")
    for words in (
        "`moat_wide_min` and `moat_narrow_min`, unread since method 1.8",
        "the setting `refresh.gf_reuse_days` (spec 2026-11-19 8.9; 4.1)",
        "A stored value of the setting is skipped, and deleted at the next save or reset",
        (
            "GuruFocus's `summary` call leaves with it, with its client and its key: Fairband makes "
            "no GuruFocus call (spec 2026-11-19 8.10; section 2)."
        ),
    ):
        assert words in row, words
    assert rows[rows.index(row) - 1].startswith("| 1.8, policy v17 |")


def test_policy_v19_sets_the_three_thresholds() -> None:
    """Spec 2026-11-23 thresholds, 3 and 5.1: section 4.1 gives the three values policy v19 sets,
    each with the figure it had before and its source, 4.10 the band's and the trim's defaults,
    and the version table a row for policy v19 under method 1.8 that says no value moves."""
    four = _section(4)
    for words in (
        "| Margin of safety: None 40%, Narrow 30%, Wide 20% (policy v19; 45%, 35% and 25% before) |",
        "| Fair band 0.90 to 1.10 × value (policy v19; 0.85 to 1.15 before) | `fair_band` | yes |",
        "| Trim at 1.35 × value (policy v19; 1.5 before) | `trim_multiple` | yes |",
        "Morningstar's Equity Research Methodology (September 2022, Exhibit 4)",
    ):
        assert words in four, words
    levels = four[four.index("### 4.10") : four.index("### 4.11")]
    assert "(0.90 and 1.10 at the defaults)" in levels and "(1.35 at the defaults)" in levels
    assert "0.85 and 1.15 at the defaults" not in levels
    policy = load_policy()
    assert policy.margin_of_safety == {"None": 0.40, "Narrow": 0.30, "Wide": 0.20}
    assert (policy.fair_band, policy.trim_multiple) == ((0.90, 1.10), 1.35)
    rows = [x for x in _section(11).splitlines() if x.startswith("| 1.")]
    row = next(x for x in rows if x.startswith("| 1.8, policy v19 |"))
    assert row.startswith("| 1.8, policy v19 | 2026-11-23 | The thresholds (spec 2026-11-23")
    for words in ("20%, 30% and 40% from Wide to None", "0.90 to 1.10", "1.35 (1.5)"):
        assert words in row, words
    assert "The method is unchanged at 1.8: no value moves." in row


def test_method_1_9_gives_the_first_edge_by_moat_class() -> None:
    """Spec 2026-11-23 thresholds, 5.2 and 5.3: 4.10 gives the first edge as the row's own buy
    level over its value, with the three classes' figures, and says no result holds the margin of
    safety; the routes' lists of RULE inputs no longer name it; the version table has the 1.9 row;
    and the Methodology page's table of words names the buy level, with no edge of one class."""
    text = METHOD.read_text(encoding="utf-8")
    four = _section(4)
    levels = four[four.index("### 4.10") : four.index("### 4.11")]
    for words in (
        "e1 = 1 − the margin of safety of the row's moat class, its buy level over its value",
        (
            "(0.80, 0.90, 1.10, 1.35 for a Wide row at the defaults; a Narrow row's e1 is 0.70 and"
            " a None row's 0.60)"
        ),
        "No result holds the margin of safety among its inputs (method 1.9)",
    ):
        assert words in levels, words
    assert "e1 = 1 − the Narrow margin of safety, e2" not in levels
    policy = load_policy()
    assert policy.edges_for("Wide") == pytest.approx((0.80, 0.90, 1.10, 1.35))
    assert (policy.edges_for("Narrow")[0], policy.edges_for("None")[0]) == pytest.approx((0.7, 0.6))
    assert "g_T, the margin of safety, the terminal return" not in text
    assert "`f_score_low`, the margin of safety, and" not in text
    rows = [x for x in _section(11).splitlines() if x.startswith("| 1.9, policy v19 |")]
    assert rows[-1].startswith("| 1.9, policy v19 | 2026-11-23 | The row's own first edge (spec")
    for words in (
        "0.80 for a Wide row, 0.70 for a Narrow row and 0.60 for a None row at the defaults",
        "No route writes the RULE input `margin_of_safety` any more",
        "No value a share and no level moves.",
    ):
        assert words in rows[-1], words
    page = resources.files("fairband.web").joinpath("static", "methodology.html").read_text("utf-8")
    assert "designation_edges" not in page
    assert '<td class="figure fb-num">under the buy level</td>' in page
    assert "The first edge is the company's own buy level" in page


def test_the_levels_and_the_word_follow_the_settings_in_force() -> None:
    """Spec 2026-11-23 thresholds, 5.3 and 5.4: 4.1 keeps the three thresholds out of the settings
    hash, 4.10 says every reader reads the levels and the word on the settings in force and that
    a published report's card keeps its record's stored levels, section 10 says a change of a
    threshold needs no revalue, 14.5 reads a reviewed row's levels the same way, and the
    Methodology page says a change shows at once and re-reads its examples under 1.9."""
    four = _section(4)
    assert (
        "Nor do the three thresholds, `margin_of_safety`, `fair_band` and `trim_multiple`, though "
        "they are valuation settings (spec 2026-11-23 thresholds, 5.3)"
    ) in four
    assert "the fair band's low must be above 1 − the Wide margin of safety" in four
    levels = four[four.index("### 4.10") : four.index("### 4.11")]
    for words in (
        "every reader reads them again on the settings in force",
        "from the record's stored value and its moat class",
        "A published report's value card is a record",
    ):
        assert words in levels, words
    assert "The levels are computed once at valuation and shown as figures" not in levels
    ten = _section(10)
    assert (
        "A change of the margin of safety, the fair band or the trim multiple needs no revalue "
        "(spec 2026-11-23 thresholds, 5.3)"
    ) in ten
    reviews = _section(14)
    assert (
        "its fair band and its buy and trim levels read on the settings in force (4.10)" in reviews
    )
    assert "the designation read at the latest snapshot's price on the edges of the" in reviews
    assert "on the effective policy's edges" not in reviews
    html = resources.files("fairband.web").joinpath("static", "methodology.html").read_text("utf-8")
    page = " ".join(html.split())
    assert (
        "A change of the margin of safety, the fair band or the trim multiple shows on every row "
        "at once. None of the three moves a value."
    ) in page
    assert "Method 1.9 (23 Nov 2026" in page and "so the figures stand under 1.9" in page


def test_a_price_refresh_stores_the_levels_of_the_settings_in_force() -> None:
    """The whole-branch review of the thresholds plan, 2026-11-23: a threshold is in no settings
    hash, so a price refresh reprices a row valued before a change of one, and it writes the levels
    of the policy in force beside the word read on them (`engine.route.reprice`). 4.10 and section
    10 say so, and 4.10 names the agents' tools that list records, which give stored figures."""
    four = _section(4)
    levels = four[four.index("### 4.10") : four.index("### 4.11")]
    for words in (
        (
            "The levels are computed at valuation and again at each price refresh, on the policy "
            "then in force (section 10)"
        ),
        (
            "the agents' `screen` and `company` tools and a cited level (16.3) show the levels of "
            "the settings in force"
        ),
        (
            "the tools that list records (`reviews`, `secondary`, `review_log`) give each record's "
            "stored figures"
        ),
    ):
        assert words in levels, words
    ten = _section(10)
    assert (
        "the value and the validity window stay, and the levels are written again on the value "
        "under the policy in force"
    ) in ten
    assert "the value, the levels and the validity window stay" not in ten
    assert "the next price refresh stores them on each repriced snapshot and review" in ten


def test_a_review_is_made_held_and_read_again() -> None:
    """Spec 2026-11-23 held reviewed value, 5.1 to 5.5 and 5.11: 14.6 says a review is made by a
    deliberate act, held, and read again by a refresh; what a carried copy keeps and what moves;
    the plain move; and the facts a refresh stores. Section 10 says each refresh carries the held
    review. 14.7's log tells the kinds apart, the review method is ``fairband-review/2``, and the
    versions table has its row."""
    reviews = _section(14)
    held = reviews[reviews.index("### 14.6") : reviews.index("### 14.7")]
    for words in (
        "### 14.6 A review is made, held and read again",
        "A review a refresh writes is a reading and never the held review",
        "an agent adds, replaces or drops an override",
        "writes the moat class",
        "the held review is carried onto each new snapshot",
        "the price refresh's own three tests",
        "takes the plain move",
        "`held_as_made`",
        "changes neither the held value nor the facts stored for it",
        "the last good reading stands",
        "a state no write of the API makes",
    ):
        assert words in held, words
    assert "A review follows its company's snapshots." not in reviews
    made = reviews[reviews.index("### 14.5") : reviews.index("### 14.6")]
    assert "`fairband-review/2`" in made and "`fairband-review/1`" not in made
    log = reviews[reviews.index("### 14.7") : reviews.index("### 14.8")]
    assert "its kind, `made`, `held` or `reading`" in log
    ten = _section(10)
    assert "The review the company holds is carried onto the repriced snapshot (14.6)" in ten
    assert "The company's current review reprices with its snapshot" not in ten
    assert "reads each held review again (14.6)" in ten
    [row] = [x for x in _section(11).splitlines() if x.startswith("| 1.9, `fairband-review/2`")]
    assert row.startswith("| 1.9, `fairband-review/2`, policy v19 | 2026-11-23 | The held")
    assert "No mechanical value moves" in row
    assert REVIEW_METHOD == "fairband-review/2"


def test_review_again_is_the_third_act() -> None:
    """Spec 2026-11-23 held reviewed value, 5.6: 14.6 names Review again as the third act that
    makes a review, an agent's (``review_again``) or the owner's, says it runs the recompute of an
    override's write with its refusals, and that with no override applied it clears the held
    review."""
    reviews = _section(14)
    held = reviews[reviews.index("### 14.6") : reviews.index("### 14.7")]
    for words in (
        "Three acts make one",
        "makes the review again with no change of an input",
        "the agents' `review_again` tool",
        '"review made again on snapshot <id>"',
        '"review cleared: no override applies"',
        '"no review for <symbol>"',
    ):
        assert words in held, words
    assert "Two acts make one" not in held


def test_a_report_and_a_reading_need_a_review_no_refresh_read_again() -> None:
    """Spec 2026-11-23 held reviewed value, 5.8: section 16's check takes a ``review:`` cite of
    the review the company holds, or of a copy of it, and refuses one once a refresh that values
    read the review again; 14.8 refuses a sensitivity reading in the same state."""
    text = METHOD.read_text(encoding="utf-8")
    refusal = '"the review was made before the latest refresh: make it again"'
    cite = next(x for x in text.splitlines() if x.startswith("- `wrong snapshot`:"))
    for words in (
        "A `review:` cite must be of the review the company holds (14.6)",
        "the made review or a copy of it",
        refusal,
        "A price refresh does not count",
    ):
        assert words in cite, words
    readings = _section(14)
    reading = readings[readings.index("### 14.8") : readings.index("### 14.9")]
    assert refusal in reading and "under a held review that a refresh read again" in reading


def test_a_secondary_valuation_holds_its_row() -> None:
    """Spec 2026-11-23 held reviewed value, 5.9: section 15 says the newest secondary valuation
    made where the route refused fills its row until a newer one or a made review that values the
    company, how it expires, and that it has no reading and no Review again."""
    secondary = _section(15)
    for words in (
        "It holds the row (spec 2026-11-23 held reviewed value, 5.9)",
        "until an agent makes a newer one or a made review values the company",
        '"The route now values the company, at $X."',
        "It has no reading and no Review again",
        "fills no row",
    ):
        assert words in secondary, words


def test_the_method_states_no_expiry_rule() -> None:
    """Spec 2026-11-25 owner's inbox, 8 and 9: the expiry rule left, so the document states it
    nowhere; 14.6 says Fairband posts no item for an expired value, and the glossary's work item
    is posted by the owner or an agent, its states the five a stored row can hold."""
    text = METHOD.read_text(encoding="utf-8")
    assert "expiry rule" not in text
    assert "Fairband posts no work item for an expired value" in text
    assert "posted by the owner or an agent; pending, claimed, done, declined or dropped" in text


def test_the_page_s_line_and_the_research_tab_s_list() -> None:
    """Spec 2026-11-23 held reviewed value, 5.7: 14.6 says what the page adds for a value
    expired early, that Review again is its button, that the Research tab lists no reading and
    that a bridge's first line says the day of its mechanical value."""
    reviews = _section(14)
    held = reviews[reviews.index("### 14.6") : reviews.index("### 14.7")]
    for words in (
        "one line under the value's levels",
        "the page's Review again button",
        "The Research tab's reviews list no reading",
        '"Mechanical value of 8 Nov 2026"',
    ):
        assert words in held, words


def test_the_overview_says_a_reviewed_value_holds() -> None:
    """Spec 2026-11-23 held reviewed value, 5.11: the overview's part on what an agent can change
    says the reviewed value holds until the next review, and points at 14.6."""
    overview = " ".join((METHOD.parent / "method-overview.md").read_text(encoding="utf-8").split())
    assert (
        "A reviewed value holds until the next review: a refresh reads the review again and does "
        "not change it"
    ) in overview
    assert "reads Expired early, with its reasons" in overview
    assert "(method 4.9, 14, 14.1 to 14.6, 15)" in overview


def test_the_rules_the_whole_branch_review_added() -> None:
    """The whole-branch review and the acceptance of the held reviewed value, 2026-11-23: the
    held review shows whatever snapshot its copy stands on; a failed reading still marks the
    review read again; the facts are stored in a savepoint; a report is refused whole on a
    review a refresh read again; and the Reviewed cell carries the mark."""
    text = METHOD.read_text(encoding="utf-8")
    reviews = _section(14)
    held = reviews[reviews.index("### 14.6") : reviews.index("### 14.7")]
    for words in (
        "whatever snapshot its newest copy stands on",
        "The refresh still stores that it read the review again, and the newer period it found",
        "each run in a savepoint of the snapshot's transaction",
        "The Reviewed cell of the screen's row carries Expired's glyph",
    ):
        assert words in held, words
    cite = next(x for x in text.splitlines() if x.startswith("- `wrong snapshot`:"))
    assert "is refused whole, 409, with the same sentence, cite or no cite" in cite


def test_a_held_value_s_state_and_its_sentences() -> None:
    """Spec 2026-11-23 held reviewed value, 5.3 and 5.7: 14.6 gives the three reasons with their
    sentences, says which stay and which can end, and what the row and the detail carry; 4.10
    says a reviewed row reads its held review's window and state."""
    reviews = _section(14)
    held = reviews[reviews.index("### 14.6") : reviews.index("### 14.7")]
    for words in (
        "expired early while one of three reasons holds",
        '"The company has reported a newer period (to 26 Dec 2026)."',
        (
            '"Override 36 (non-recurring gap) no longer applies: the input the override '
            'corrected changed."'
        ),
        '"Computed again on today\'s data, the review gives $229.25 (+204%)."',
        '"Computed again, the review gives no value: <the refusal>."',
        "it follows a changed band at once",
        "with the field `expiredEarly`",
        "What the price needs (4.11) is not served for a review whose copy took the plain move",
    ):
        assert words in held, words
    four = _section(4)
    levels = four[four.index("### 4.10") : four.index("### 4.11")]
    assert (
        "A row a review fills reads the window and the state of the review the company holds"
        in levels
    )
    assert "is expired early while a reason of 14.6 holds" in levels


def test_no_page_or_ref_calls_the_ratio_the_ordinary_shares_an_ads_stands_for() -> None:
    """Spec 2026-11-19 6.2: the counts cannot say which way a depositary's ratio runs, so 7.4's line
    under the drawer's head names no ratio, the Research tab's being the same line; 16.2 and 16.6
    give the ref's words; and 16.6's sentence on a refusal the agent cannot fix quotes the refusal
    as method 1.6 words it."""
    seven = _section(7)
    for words in (
        "the ADR ratio as a plain number",
        "and the Research tab the same line under its bar",
        '"Reports in TWD; an ADR: every per-share figure is per ADS; valued at TWD 32.96 per USD"',
        "the line names no ratio, with one on file or none",
        '("Reports in ARS; an ADR: every per-share figure is per ADS")',
        "the whole number found between FMP's stored share count and the quote's (4.2)",
    ):
        assert words in seven, words
    sixteen = _section(16)
    assert (
        "the ADR ratio, `adr_ratio`, the ratio between FMP's stored share count and the quote's"
    ) in sixteen
    assert (
        "the input `adr_ratio` \"the ratio between FMP's stored share count and the quote's\""
    ) in sixteen
    assert (
        "\"No secondary valuation: share basis unclear: the newest period's count 259.5 m against"
        " the quote's 194.9 m\""
    ) in sixteen
    for text in (seven, sixteen):
        for gone in ("ordinary shares per ADS", "one ADS is", "(the ADR ratio 10)"):
            assert gone not in text, gone


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
            " before's, and the oldest years with none the first currency named after them), since"
            " its midpoint over an actual in another currency is no growth (spec 2026-11-15 9.2); a"
            " record that names no currency steps as before."
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
            " company has no snapshot; in a report's Appendix A, the currency of the report's own"
            " snapshot (16.6)."
        ),
        (
            "Every read of a finding or a guidance record (`findings`, `guidance`, the research"
            " read `GET /api/companies/{symbol}/research`, and for a guidance record a report's"
            " Appendix A) answers `currency`: the stored code, else the reporting currency; none"
            " for a figure that is not money."
        ),
        (
            "The Research tab's Appendix A writes a guidance record's money figure in that"
            ' currency, `$` for USD and the code before the number otherwise ("SEK 2,100,000,000")'
            " (16.6; spec 2026-11-15 9.5), and its Records view a guidance record's and a"
            " finding's alike (spec 2026-11-17 research tab, 7.10); an agent reads the findings"
            " through `findings`."
        ),
    ):
        assert words in references, words


def test_appendix_a_writes_each_guidance_record_in_its_currency() -> None:
    """Spec 2026-11-15 9.5: 16.6 states that Appendix A's guidance on file carries each record's
    currency, the report's own snapshot's for one that names none, which the page writes with each
    figure and the export's table in a Currency column after the midpoint, its numbers bare, the
    cell empty for a percent."""
    sixteen = _section(16)
    export = sixteen[sixteen.index("### 16.6") : sixteen.index("### 16.7")]
    assert (
        "the guidance on file, the company's guidance records written by the report's time, newest"
        " first, each with its metric, period, low, high, midpoint, the currency of its money"
        " (16.2: the stored code, else the reporting currency of the report's own snapshot; none"
        " for a percent), basis and call's date, current or superseded as of the report, and the"
        " overrides inside the review that cite it; the page writes each money figure in its"
        ' record\'s currency, `$` for USD and the code before the number otherwise ("SEK 42.00"),'
        " and the export's table keeps its figures bare, as before, and names the currency in a"
        ' column of its own after the midpoint, "Currency", the code for a money metric and empty'
        " for a percent (spec 2026-11-15 9.5);"
    ) in export


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
    axis prints as many ticks as its plot's width holds, one to 70px for the bars, 64px for the
    price against the band and 56px for the ROIC chart, seven at most and two at least, the P/E
    charts keeping their own count (the Research tab's design, 7.9), none within a stride of the
    last bar's or of the trailing twelve months', which print always, as the first's does (its
    I3); that a chart table's cell is empty where the table holds no figure,
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
            "in Financial performance and health each chart by its row's name, buybacks and"
            " dividends one measure, their sum, and a group no paragraph names a block of its own"
            ' under its table\'s title ("Growth and profitability"), a group a paragraph names'
            " under none, since the paragraph's lead word names it"
        ),
        (
            "in The last earnings call three charts by quarter in the section's first row, under"
            ' the export\'s title for them, "By quarter", the revenue, the operating margin and the'
            " EPS, each by its row's name, each bar's tick its quarter and the last two digits of"
            ' its year ("Q3 26"), and where no period is stored the three with "No data on'
            ' file.";'
        ),
        (
            "A bar chart draws a bar for each column of its table that holds a figure, the"
            " tooltip naming each by the column's label"
        ),
        (
            "and its axis prints as many ticks as its plot's width holds, one to 70 px of plot,"
            " seven at most and two at least (spec 2026-11-17 research tab, 7.9; the price against"
            " the band's axis holds one to 64 px and the ROIC chart's one to 56 px, and the P/E"
            " charts keep their own count), every k-th where the bars outnumber them, k the bars"
            " over the ticks held rounded up, none within a stride of the last bar's or of the"
            " trailing twelve months', which print always, as the first's does (on a chart about"
            " 550 px wide, as the report page drew them, six bars print every tick, eight quarters"
            " the first, third, fifth and eighth, and nine bars ending in the trailing twelve"
            " months' and three estimates the first, third, sixth and ninth; at 320 px six bars"
            " ending in the trailing twelve months' print the first, third and sixth, and at"
            " 334 px eight quarters the first, fourth and eighth):"
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
    report in the reader's words, the Research tab's bar and value card by the same rule (spec
    2026-11-17 research tab, 7.2 and 7.5), Appendix A's dates in words and its sentence for no
    secondary valuation without "the route"; and, since
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
            "The company page's Research tab says the same in the same words, in two places"
            " (spec 2026-11-17 research tab, 7.2 and 7.5): the bar's line names the stance, the"
            ' mode, the revision, the date and the writer, then "valid until" and the date and,'
            ' for a valuation review, "reuses the full report of" and that report\'s date, the'
            " last left out where the reused report's record is not on file, where the export"
            ' writes "Reuses an earlier full report."; and the head of the report\'s value card'
            ' reads "on the data of 4 Nov 2026, priced that day", or "priced" and the price date'
            " where it is another. Neither names a record: the snapshot's and the review's ids"
            " are in Appendix A."
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
        # the check reads the snapshots in order and names the first that is not the latest
        "the detail names, of the snapshots that fail, the one with the lowest id.",
    ):
        assert words in check, words
    assert "the detail names, of those snapshots, the one with the lowest id" not in check
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
        # the controller's ruling 1 on Task 1: 100 serves the PEG, a ratio with no unit; a
        # percent times 100 keeps its unit, so it is never points
        (
            "They serve a complement (1), a change of sign (0), an average or an annual rate (2 to"
            " 12, 52, 365), the PEG (100: the ratio of a P/E to a growth rate, a fraction, has no"
            " unit and is a hundred times the PEG, so its ratio to 100 is the PEG; a percent times"
            " 100 stays a percent, so it is never cited as points) and a unit scale (a power of"
            " ten)."
        ),
    ):
        assert words in derivations, words
    assert "a percent as points (100)" not in derivations
    assert FIXED_NUMBERS in derivations
    assert NEEDS_A_FIGURE in derivations


def test_a_derivation_with_a_number_depends_on_a_stored_figure() -> None:
    """The whole-branch review's C1 (the controller's rulings 6 and 8): 16.4 names the third
    refusal in the server's words, with its words for a tree that rests on a changed derivation;
    the tree read from the stored rows, the leaves and their groups, the evaluation and the
    scaling, a move from a value to a value beyond the float rounding, the nested derivation taken
    as a constant, a derivation with no value and a tree with no number left untested, the
    recipes, the edge beside a large number, and what the rule cannot refuse."""
    derivations = _section(16)
    derivations = derivations[derivations.index("### 16.4") : derivations.index("### 16.5")]
    for words in (
        (
            "Three refusals, each a 400 that stores none of the call's derivations, as an"
            " unresolved reference does"
        ),
        (
            'and a derivation with a fixed number whose value depends on no stored figure, "a'
            " derivation with a fixed number must depend on a stored figure: this one has the same"
            ' value whatever its figures are" (below).'
        ),
        (
            "A fixed number serves arithmetic on a stored figure and never stands for a number the"
            " agent chose (spec 2026-11-15 4), so a derivation with a number anywhere in its tree"
            " must depend on a stored figure"
        ),
        (
            "The tree is the derivation's two operands and, for a `derived:` operand, the operands"
            " of its stored derivation, nested ones too, as the snapshots it rests on are read"
            " (16.2); a call's derivations are stored one by one, so a later one of the call may"
            " name an earlier one, and its tree is read alike."
        ),
        (
            "The tree's leaves are its operands that are neither a number nor a derivation, stored"
            " figures each resolved now, and leaves that resolve to one value are one group, so the"
            " same ref twice, or two refs of one figure (the price and its input, a `fact:` line"
            " and its `table:` cell), count once."
        ),
        # the controller's ruling 8: R1, a move beyond the float rounding; R2, from a value to a
        # value; R3, an earlier derivation whose figures changed is a constant
        (
            "The tree is evaluated from its leaves by `derive`'s own arithmetic, not from the"
            " nested derivations' stored values, then again with each group's value × 1.5 in turn;"
            " the derivation depends on a stored figure where, for one group at least, the result"
            " moves: it has a value both times, and the two differ by more than a billionth (1e-9)"
            " of the larger of 1 and the unscaled result's size and by more than four times the"
            " float rounding the two can carry, a bound on each value's rounding carried through"
            " each operation, so a sum that rounds past 2^53 does not move."
        ),
        (
            "A value that turns into none under the scaling, a growth over a base that crosses zero"
            " or an overflow, is no move, and a tree with no value is refused."
        ),
        (
            "A nested derivation whose own leaves do not all resolve now, or whose tree no longer"
            " gives its stored value (a figure restated since), is a constant at its stored value"
            " and is never scaled."
        ),
        (
            "A derivation that holds a number and depends on no stored figure is refused,"
            f' "{DEPENDS_ON_A_FIGURE}"; where an earlier derivation of its tree is such a constant,'
            f' "{REDERIVE}", and that one, derived again from its refs, reads its figures as they'
            " are now."
        ),
        (
            "A derivation with no value is not tested, being no figure a report cites (16.3) nor an"
            " operand of another, so a ratio over `number:0` is stored with none, as before; and"
            " neither is a tree with no number, so a figure over itself, plus itself or less itself"
            " computes as before."
        ),
        (
            "Each recipe of the playbook moves with its figure: a complement, an average, a change"
            " of sign, a cell scaled by a power of ten, the PEG, the cycle gap's half, one plus a"
            " growth."
        ),
        # the scoped re-review of the fix wave: a figure of nought moves nothing
        (
            "A figure that is nought moves nothing, so a derivation with a number whose only figure"
            " is nought is refused in the same words: the figure itself is cited."
        ),
        (
            "A number beside a figure a billion times smaller is refused too, the figure moving the"
            " result by less than the billionth (the price plus `number:1000000000000`)."
        ),
        # the controller's rulings 8 and 10: what is left, in one plain sentence
        (
            "The rule refuses a constant, and it cannot refuse a figure built to sit near one, one"
            " made by stored figures that cancel among themselves, or a stored figure scaled by"
            " numbers chosen to land on a figure (a price of $150 times `number:2` over `number:3`"
            " is $100); the references list shows each cited derivation."
        ),
    ):
        assert words in derivations, words
    for old in (
        "Two refusals, each a 400",
        "is one leaf at its stored value",
        "no value where it had one, or the reverse",
    ):
        assert old not in derivations, old


def test_a_report_is_stored_on_the_earliest_snapshot_its_cites_rest_on() -> None:
    """The whole-branch review's deferred minor 2: 16.1 stores a report on the earliest snapshot
    its cites rest on, a derivation's every operand's counted, as 16.2 says a `derived:` ref
    rests on every snapshot its operands rest on."""
    sixteen = _section(16)
    report = sixteen[sixteen.index("### 16.1") : sixteen.index("### 16.2")]
    assert (
        "A published one is stored as the company's next revision (from 1) on the earliest"
        " snapshot its cites rest on, every operand's of a derivation among them (16.2), the"
        " latest where they rest on none, with the review"
    ) in report


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
            "Every read of a criterion (`kill_criteria`, the research read) answers its"
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
    two rules with their examples, a derivation carrying its record's currency until it is
    converted (the whole-branch review's I1)."""
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
            "So the server checks the `$` rule (16.3) for a record alone, and keeps out of money"
            " arithmetic (16.4) a record in another currency and a derivation of one until it is"
            " converted."
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
        # the whole-branch review's I1 (the controller's ruling 7): a derivation carries its
        # record's currency where it is an operand, until it is converted
        (
            "Such a record is kept out of money arithmetic until it is converted, and so is a"
            " derivation of it (spec 2026-11-15 4): an operand is foreign in a currency where it is"
            " a record in that currency, or a `derived:` operand whose stored derivation has an"
            " operand foreign in it, read through the stored rows as the tree is (above), but for"
            " three derivations, foreign in nothing: the `product` of an operand foreign in US"
            " dollars and a `snapshot:<id>/inputs/fx_rate` ref, the reporting currency per US"
            " dollar, which converted it (a `ratio` over the rate, or the rate's product with an"
            " operand in another currency, converts nothing and keeps its mark); a `growth` or a"
            " `cagr`, a percent having no currency; and a `ratio` of two operands foreign in the"
            " same currency, which cancels it."
        ),
        "A derivation is still stored with no currency; the mark is read where it is an operand.",
        (
            "Two rules: a derivation has no value, and no unit, where one operand is foreign in a"
            " currency and the other is a money figure (currency or per-share), or an operand"
            " foreign in another currency, that is not foreign in that same currency; and a"
            " derivation with an operand foreign in a currency never has a money unit: where the"
            " unit rules above give currency or per-share, it has none, since a stored derivation"
            " has no currency and a money unit on it would read as the reporting currency, so a"
            " US-dollar record times `number:1` has no unit."
        ),
        (
            "An operand foreign in a currency combines as before with one that has no unit and is"
            " foreign in nothing: the rate, a number, a filing cell, a converted figure."
        ),
        (
            "A derivation of it keeps its currency: its quarter, its `ratio` over `number:4`, or"
            " the average of two US-dollar records has no value with the TWD revenue until it is"
            " converted; times the rate it is in TWD and combines with anything; its `growth` over"
            " a US-dollar record is a percent; and the ratio of two such averages, the currency"
            " cancelled, combines with anything."
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
            "Nor has it one with the price, the value a share, the levels, a close or a grid's"
            " cells, which are in US dollars (16.3) but whose currency the resolver does not know"
            " (spec 2026-11-15 14)."
        ),
        (
            "A derivation with no unit is cited at the cite's own precision (16.3), its currency"
            " written in the text."
        ),
    ):
        assert words in derivations, words
    for old in (
        "by two rules: a derivation has no value",
        "since a derivation carries no currency",
        # the controller's ruling 9: a ratio over the rate converts nothing
        "a `product` or a `ratio` with a `snapshot:<id>/inputs/fx_rate` ref",
    ):
        assert old not in derivations, old


def test_a_filing_report_is_kept_and_a_revenue_split_names_its_newest_year() -> None:
    """Spec 2026-11-15 10 and 11: 16.8 says a filing report is reused at any age and nothing is
    deleted, the filing list and the list of reports keeping `reuse_hours`, and that each part of
    the `segments` answer names its newest year."""
    sixteen = _section(16)
    filings = sixteen[sixteen.index("### 16.8") : sixteen.index("### 16.9")]
    for words in (
        (
            "and reused as every pass-through is: the newest response to the same call observed"
            " within the kind's window, a filing report's at any age, never one stored with an"
            " error."
        ),
        (
            "`filings` stores FMP's `sec-filings-search/symbol` under the endpoint `sec-filings`,"
            " page 0 of 1,000 rows, the call being the symbol, `from`, `to` and the page size,"
            " reused for `reuse_hours`."
        ),
        (
            "`filing-reports` stores `financial-reports-dates` under `filing-report-dates`, every"
            " report on file, reused for `reuse_hours`."
        ),
        (
            "`filing-report` stores `financial-reports-json` under `filing-report`, the report of a"
            " fiscal `year` and a `period` (`FY`, `Q1` to `Q4`), reused whatever its age, with no"
            " window (spec 2026-11-15 10): a filing does not change once filed, and a `filing:` ref"
            " names its stored copy by the response id, so a second copy would only split the"
            " cites of one filing over two ids."
        ),
        (
            "Nothing is deleted: every stored copy keeps its payload, so a published report's"
            " references keep resolving."
        ),
        (
            "`segments` answers its two calls whole, `product` and `geographic`, each with"
            " `newestYear`, the largest `fiscalYear` among its payload's rows that hold an integer"
            " there (a JSON `2025.0` is no integer), null where none does or the payload is not a"
            " list (spec 2026-11-15 11): FMP's revenue by region can end years before its revenue"
            " by product (QCOM's ended at fiscal 2023), and the payload names no newest year."
        ),
    ):
        assert words in filings, words
    assert "720 hours" not in filings and "thirty days" not in filings
    assert "hold a whole number there" not in filings


def test_the_log_s_stance_and_the_tables_three_notes() -> None:
    """Spec 2026-11-15 12.1 clause 9 and 12.2: 14.7 says the log's stance is the one in force
    when the review was written, none before a company's first report; 16.5 names the aggregate
    ROIC's "over <n> years" beside the two notes that mark a figure that would mislead."""
    fourteen = _section(14)
    log = fourteen[fourteen.index("### 14.7") : fourteen.index("### 14.8")]
    assert (
        "The stance is the one in force when the review was written, the stance of the company's"
        " newest report at that time: a review an agent's override writes before its report is"
        " published carries the stance of the report before it, and a company's reviews before"
        " its first report carry none (spec 2026-11-15 12.2)."
    ) in log
    sixteen = _section(16)
    tables = sixteen[sixteen.index("### 16.5") : sixteen.index("### 16.6")]
    assert (
        "Among the cells' notes, three mark a figure that would mislead: the interest coverage"
        ' holds no figure on a stored interest expense of zero, "the interest expense on file is'
        " zero\"; a year's ROIC on average invested capital at or below zero keeps the engine's"
        ' figure, "average invested capital is at or below zero", a figure with the wrong sign or'
        " none and no meaning (4.5); and the ten-year aggregate ROIC in the newest year's cell,"
        ' where it stands on fewer than ten kept years, says how many, "over <n> years" (4.5;'
        " spec 2026-11-15 12.1)."
    ) in tables
    assert "two mark a figure that would mislead" not in tables


def test_method_1_10_reads_the_forward_pe_on_the_analysts_eps() -> None:
    """The founder's decision of 2026-11-24, method 1.10: the head names the method; 5.2 says
    which figure each reading of the anchor takes; 5.9 defines the forward P/E on the analysts'
    EPS as they state it and the forward P/E after stock pay, Mature Growth's alone; 5a.10 and
    5a.14 give the revenue-growth route the first and not the second; 14.4 says the stock-pay
    inputs move the second alone; 16.7 says the log holds the first and how its earlier rows were
    restated; 11 has the 1.10 row; and the Methodology page's examples stand under 1.10."""
    assert METHOD_VERSION == "fairband-mechanical/1.10"
    five = _section(5)
    anchor = five[five.index("### 5.2") : five.index("### 5.3")]
    assert (
        "The unit-error check, the forward P/E after stock pay of 5.9 and the `ntm_eps` and"
        " `ntm_net_income` DATA entries read raw − adjustment, the consensus as found; the forward"
        " P/E of 5.9 reads the raw figure, the analysts' EPS as they state it (method 1.10)."
    ) in anchor
    # the check still reads the figure after stock pay (the whole-branch review's finding 4)
    assert (
        "So the forward P/E of a row the check passes can read under the bound, where the"
        " adjustment alone lifts the figure after stock pay to the bound or above it"
    ) in anchor
    multiples = five[five.index("### 5.9") : five.index("### 5.10")]
    for words in (
        "- Trailing P/E reported and clean; a P/E exists only for a positive EPS.",
        (
            "- The forward P/E = price ÷ the analysts' NTM EPS as they state it, the anchor's raw"
            " figure (5.2), with no stock-pay adjustment (method 1.10; the founder's decision of"
            " 2026-11-24)"
        ),
        "The forward P/E after stock pay = price ÷ (raw − adjustment)",
        "where the adjustment is nil it equals the forward P/E",
        "It is Mature Growth's alone, and it follows the adjustment in force",
        # whatever moves the adjustment in a review moves it (the whole-branch review's finding 2)
        (
            "in a review whatever sets the adjustment there, an agent's `earnings.sbc_basis` and"
            " `earnings.sbc`, its `shares.diluted`, and an `earnings.nri_gap` that changes the"
            " test's reading (14.4)"
        ),
        "So the Screen and the multiples log (16.7) carry the forward P/E",
        (
            "The intermediates' `eps` holds the two EPS figures as `forward` and"
            " `forward_after_sbc`, and `multiples` the two P/Es as `pe_forward` and"
            " `pe_forward_after_sbc`"
        ),
    ):
        assert words in multiples, words
    assert "forward P/E on NTM EPS" not in multiples
    growth = _section_5a()
    moves = growth[growth.index("### 5a.10") : growth.index("### 5a.11")]
    for words in (
        (
            "the forward P/E on the analysts' NTM EPS as they state it, the raw figure of the"
            " cross-check's anchor (5.2)"
        ),
        'where it refuses "no positive forward anchor" on a raw figure above zero',
        "no forward P/E after stock pay, since no agent's input sets the basis on this route",
    ):
        assert words in moves, words
    assert "the forward P/E on the anchor's NTM EPS (5.2) when the anchor stands" not in moves
    recorded = growth[growth.index("### 5a.14") : growth.index("### 5a.15")]
    assert (
        "The forward EPS of `eps`, and the forward P/E of `multiples` on it, read the raw figure"
        " of the anchor of 5.2, and the cross-check's `growth_route` the anchor itself, on either"
        " source"
    ) in recorded
    assert "`forward_after_sbc` and `pe_forward_after_sbc` are null on this route" in recorded
    reviews = _section(14)
    reads = reviews[reviews.index("### 14.4") : reviews.index("### 14.5")]
    for words in (
        (
            "Neither stock-pay input moves the forward P/E, which reads the raw figure; the"
            " forward P/E after stock pay follows the adjustment in force (5.9)."
        ),
        (
            "the anchor's basis and stock pay, and the forward P/E after stock pay (5.9), still"
            " follow them"
        ),
        "and the two forward P/Es of 5.9 do not read the guided figure",
        (
            "the unit-error check, the forward P/E after stock pay and the `ntm_eps` and"
            " `ntm_net_income` DATA entries stay on the consensus as found, and the forward P/E"
            " on the raw figure"
        ),
    ):
        assert words in reads, words
    assert "the forward P/E on the consensus as found, still follow them" not in reads
    sixteen = _section(16)
    history = sixteen[sixteen.index("### 16.7") : sixteen.index("### 16.8")]
    for words in (
        "The log holds the forward P/E alone, never the forward P/E after stock pay.",
        "`012_forward_pe_as_stated.sql`",
        "× (raw − adjustment) ÷ raw",
        "so every point of the series is on one basis",
    ):
        assert words in history, words
    [row] = [x for x in _section(11).splitlines() if x.startswith("| 1.10, policy v19 |")]
    assert row.startswith(
        "| 1.10, policy v19 | 2026-11-24 | The forward P/E on the analysts' EPS as they state it"
    )
    for words in (
        "on UBER's row",
        "the forward P/E after stock pay",
        "`forward_after_sbc`",
        "`pe_forward_after_sbc`",
        "No value a share, no level and no word moves",
        # a held review keeps its method's figures (the whole-branch review's finding 3)
        "A held review made before 1.10 is carried as made (14.6)",
        "until the review is made again",
    ):
        assert words in row, words
    # the row gives Fairband's own figures and no vendor's EPS (the review's finding 11)
    assert "$4.06" not in row and "$3.20" not in row
    html = resources.files("fairband.web").joinpath("static", "methodology.html").read_text("utf-8")
    page = " ".join(html.split())
    assert "Method 1.10 (24 Nov 2026" in page and "so the figures stand under 1.10" in page
    assert "no example prints a P/E" in page and "P/E" not in html[html.index("<article") :]


def _section_5a() -> str:
    """The text under the heading ``## 5a.``, to the next top-level heading."""
    text = METHOD.read_text(encoding="utf-8")
    start = text.index("\n## 5a. ")
    return text[start : text.index("\n## ", start + 1)]
