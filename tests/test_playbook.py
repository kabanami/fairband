"""The playbook (spec 2026-11-06 Tier 2, 14), the skill an agent host installs, against the server
it describes: it names every MCP tool with the arguments the server takes, in the server's order;
it runs spec 14's thirteen steps in order with the tools each names; it quotes the refusals the
agent meets as the server words them; its citation reference names the check's six failures and
the ref forms; its submission example, twelve sections for an invented company the route values,
passes the structural checks and the token rule; and it makes the secondary valuation only where
neither the route nor the review values the company, with no DCF beside the route's value (the
founder's rule of 2026-11-08, spec 14 steps 10 and 11 as amended for plan 3)."""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import anyio
import httpx
from mcp import Client

from fairband.engine.overrides import BRIDGE_ORDER, LABELS, NO_GUIDANCE, TAGS, anchor_misfit
from fairband.mcp.client import NOT_RUNNING, FairbandClient
from fairband.mcp.server import TOOL_NAMES, build_server
from fairband.policy import load_policy
from fairband.refresh.passthrough import BUSY, NO_GF_KEY
from fairband.refresh.rates import NO_RATE
from fairband.reports.check import (
    ALWAYS_JUDGED,
    FAILURES,
    HEADINGS,
    STRUCTURE,
    parse_cite,
    quantities,
    structure_refusal,
)
from fairband.store.secondary import cannot_fix
from fairband.web.identity import IDENTIFY_FIRST
from fairband.web.reviews_api import GUIDANCE_REF
from fairband.web.vendor_api import NO_FMP_KEY

PLAYBOOK = Path(__file__).parent.parent / "playbook" / "fairband-research"
SKILL = PLAYBOOK / "SKILL.md"
TOOLS = PLAYBOOK / "reference" / "tools.md"
CITATIONS = PLAYBOOK / "reference" / "citations.md"
TEMPLATE = PLAYBOOK / "reference" / "report-template.md"
REGISTER = PLAYBOOK / "reference" / "register.md"

# Spec 14's thirteen steps, each with the tools it names; steps 9 and 11 name none.
STEPS: dict[int, tuple[str, ...]] = {
    1: ("identify",),
    2: ("inbox_list", "inbox_claim", "inbox_post"),
    3: (
        "company",
        "financials",
        "quarters",
        "financial_tables",
        "estimates",
        "peers",
        "price_history",
        "multiples_history",
        "report",
        "notes",
        "findings",
        "guidance",
        "overrides",
        "reviews",
        "secondary",
        "kill_criteria",
        "policy",
        "methodology",
        "refresh_start",
        "refresh_status",
    ),
    4: ("filing_report", "filing_search", "filings", "transcript", "segments", "finding_add"),
    5: ("transcript_dates", "transcript", "quarters", "finding_add", "guidance_add", "derive"),
    6: ("news", "news_item_add"),
    7: ("financial_tables", "finding_add"),
    8: ("company", "methodology"),
    9: (),
    10: ("override_add", "override_drop", "secondary_valuation", "dcf", "sensitivity", "derive"),
    11: (),
    12: ("report_submit",),
    13: ("inbox_complete",),
}
REF_FORMS = (
    "snapshot",
    "review",
    "secondary",
    "sensitivity",
    "guidance",
    "multiple",
    "fact",
    "table",
    "estimate",
    "close",
    "peer",
    "finding",
    "derived",
    "filing",
    "response",
    "policy",
)
# The refusals an agent cannot fix, which spare a report the secondary valuation (spec
# 2026-11-10 7.6), as the server words them with their placeholders.
CANNOT_FIX = (
    "no diluted share count",
    "reporting currency unknown",
    NO_RATE.format(code="<code>"),
    "no inflation projection for <code>",
    "<code>: expected inflation <π>% above the 10% bound",
    "share basis unclear",
)
# The refusal the engine gave a foreign filer before method 1.1, which the playbook names no more.
OLD_FOREIGN_FILER = "currency and share-unit handling not built yet"
# The listed-share basis's refusal whole, as assembly words it (``refresh.inputs_splits``), with its
# placeholders: the counts in millions to one decimal, and the ratio.
BASIS_UNCLEAR = (
    "share basis unclear: the newest period's count <c> against the quote's <Q> (the ADR ratio <ρ>)"
)
# The refusals the agent meets, as the server words them; the playbook quotes each verbatim.
REFUSALS = (
    IDENTIFY_FIRST,
    NOT_RUNNING,
    NO_GUIDANCE,
    anchor_misfit("earnings.ntm"),
    anchor_misfit("revenue.ntm"),
    GUIDANCE_REF,
    *CANNOT_FIX,
    BASIS_UNCLEAR,
    NO_FMP_KEY,
    NO_GF_KEY,
    BUSY,
    "the report needs a secondary valuation on snapshot <id>",
    "the route values <symbol>: the secondary valuation is the fallback where it refuses",
    (
        "the review values <symbol>: the secondary valuation is the fallback where neither the route"
        " nor the review values the company"
    ),
    "guidance record <id> is superseded by record <id>",
    "the store moved since snapshot <id>: run a revalue",
    "settings changed: run a revalue",
    "the path needs its own evidence item",
    "an axis holds one to five values",
    "the two tags differ",
)
# The forms the example cites at least once: the history, the grid, the guidance.
EXAMPLE_FORMS = ("multiple", "sensitivity", "guidance")
# Step 11's order of the values: the review, else the snapshot, else on a refused row the secondary.
VALUE_ORDER = (
    "Take the reviewed value when the current review has one. Else take the snapshot's value. On a"
    " refused row with no reviewed value, take the secondary valuation's."
)
# Step 11 on a review that refused on a valued snapshot: the mechanical value stands meanwhile.
REFUSED_REVIEW = (
    "When the current review refused on a valued snapshot, the snapshot's value stands: fix or drop"
    " the override whose bridge line refused before you choose the stance. No stance rests on a"
    " refused review."
)
# Step 11 on a refused row with nothing to weigh the price against (the final review of plan 3).
THESIS_ALONE = (
    "On a refused row with no reviewed value and no possible secondary valuation (a refusal you"
    " cannot fix: no diluted share count, the reporting currency's or the share basis's), the stance"
    " rests on the thesis alone, and the report says so in section 8."
)
# Step 3 on a secondary valuation made before the route or an override valued the company.
HISTORY = (
    "On a company the route or the review values, a secondary valuation on file is history: neither"
    " cite it nor weigh it."
)
# Where FMP's figure is read: the secondary valuation's scope (the coordinator, final wave).
DCF_SCOPE = (
    "only where neither the route nor the review values the company, as a cross-check on the"
    " secondary valuation"
)
# The phrases of the rule before plan 3: a secondary valuation on every report, the second view;
# and "no DCF of any kind", which the growth routes' own revenue DCFs contradict.
STALE = (
    "on every report",
    "every report values",
    "second view",
    "third opinion",
    "two values",
    "dcf of any kind",
    "where the route refuses or no route fits",
    "on a refused row only",
)
# The names of Fairband's parts, which a report never writes (register, "The words a report writes").
NEVER = (
    "the engine",
    "the classifier",
    "the route",
    "the snapshot",
    "the check",
    "a flag",
    "the bridge",
    "a tag",
    "an id",
)
# Method terms the register's table must map to a plain phrase, section 8's own among them.
TERMS = (
    "belief",
    "implied growth",
    "mechanical value",
    "reviewed value",
    "override",
    "review",
    "bridge",
    "buy level",
    "margin of safety",
    "fair band",
    "trim level",
    "designation",
    "phase",
    "Dickinson stage",
    "moat",
    "runway",
    "runway return",
    "held rate",
    "target margin",
    "margin the price needs",
    "sales-to-capital",
    "decline rate",
    "liquidation floor",
    "distress-weighted value",
    "price-implied requirement",
    "hurdle rate",
    "consensus",
    "snapshot",
    "validity window",
    "secondary valuation",
    "sensitivity grid",
    "kill criterion",
    "return by year",
    "value outside the business",
)
# The phases each route values, as the overrides table names them; "every route" names all six.
ROUTE_PHASES: dict[str, tuple[str, ...]] = {
    "mature-growth": ("Mature Growth",),
    "mature-stable": ("Mature Stable",),
    "revenue-growth": ("High Growth", "Young Growth"),
    "decline": ("Decline",),
    "start-up": ("Start-up",),
}
PHASES = tuple(phase for phases in ROUTE_PHASES.values() for phase in phases)
# The return judgment under heavy capital spending (spec 2026-11-09 12).
ROIC_JUDGMENT = (
    "the return on invested capital and the runway return; when `heavy-capex` fires, read the"
    " newest year's marginal return (`intermediates/runway_return/one_year`) and the"
    " capital-spending guidance, decide the runway return and cite both figures; when"
    " `return-without-goodwill` fires, decide whether the growth ahead is built or bought; and"
    " whether the higher case stood (step 10)"
)
# The judgments that record a growth, a margin or a return, each tested for a higher figure.
HIGHER_CASE_JUDGMENTS = ("`belief`", "`roic`", "`target_margin`")
# The intermediates the engine round 2 adds, by their paths under `intermediates/`.
NEW_INTERMEDIATES = (
    "charge/return_by_year/<n>",
    "charge/growth_by_year/<n>",
    "charge/hold_years",
    "runway_return/one_year",
    "outside_value_per_share",
)
# Each stock-pay note's entry under a guided anchor (the controller's ruling on the whole-branch
# review of the research round's plan 1, its Minor 2): the note is silent, the inputs moot.
GUIDED_STOCK_PAY = (
    "Under an applied `earnings.ntm` the note does not show, and neither stock-pay input is needed"
)
# Terms the example's Summary writes as their phrase, never by name.
SUMMARY_FREE = (
    "belief",
    "reviewed value",
    "mechanical value",
    "buy level",
    "trim level",
    "fair band",
    "margin of safety",
    "runway",
    "override",
    "snapshot",
    "engine",
)


def test_the_skill_names_every_tool() -> None:
    text = SKILL.read_text(encoding="utf-8") + TOOLS.read_text(encoding="utf-8")
    for name in TOOL_NAMES:
        assert re.search(rf"`{name}\(", text), name
    listed = _signatures(TOOLS.read_text(encoding="utf-8"))
    assert list(listed) == list(TOOL_NAMES)  # the server's order, each once
    assert listed == _served()  # each with the arguments the server takes, ? on the optional


def test_the_skill_has_the_frontmatter_and_the_thirteen_steps() -> None:
    front, body = _frontmatter(SKILL.read_text(encoding="utf-8"))
    assert front["name"] == "fairband-research"
    description = front["description"]
    assert 0 < len(description) <= 1024  # the Agent Skills limit
    assert description.endswith(".") and ". " not in description  # one sentence
    steps = _steps(body)
    assert list(steps) == list(STEPS)
    for number, tools in STEPS.items():
        for tool in tools:
            assert re.search(rf"`{tool}[`(]", steps[number]), (number, tool)
    for reference in (TOOLS, CITATIONS, TEMPLATE, REGISTER):
        assert f"reference/{reference.name}" in body, reference.name


def test_the_skill_quotes_the_refusals_as_the_server_words_them() -> None:
    text = " ".join(" ".join(f.read_text(encoding="utf-8").split()) for f in (SKILL, TOOLS))
    for sentence in REFUSALS:
        assert sentence in text, sentence


def test_the_citation_reference_names_the_six_failures() -> None:
    text = CITATIONS.read_text(encoding="utf-8")
    for failure in FAILURES:
        assert f"`{failure}`" in text, failure
    for form in REF_FORMS:
        assert f"`{form}:" in text, form


def test_the_template_example_passes_the_structural_checks_and_the_token_rule() -> None:
    example = _example(TEMPLATE.read_text(encoding="utf-8"))
    assert set(example) <= {argument.rstrip("?") for argument in _served()["report_submit"]}
    assert example["mode"] == "full report"
    headings = [s["heading"] for s in example["sections"]]
    assert len(headings) == 12 and headings == list(HEADINGS)
    judged = [j["judgment"] for j in example["judgments"]]
    assert set(ALWAYS_JUDGED) <= set(judged) and len(judged) == len(set(judged))
    refusal = structure_refusal(
        example["mode"],
        example["stance"],
        headings,
        judged,
        "mature-growth",  # the example's company, Example Corp, is a Mature Growth company
        load_policy(),
        secondary_on_snapshot=True,  # a valued snapshot needs none: the route values the company
        snapshot_id=412,
    )
    assert refusal is None, refusal
    forms = set()
    for section in example["sections"]:
        for part in section["parts"]:
            if isinstance(part, str):
                assert quantities(part) == [], part
            else:  # one number, or the word of a word ref
                text = part["cite"]
                assert parse_cite(text) is not None or not re.search(r"\d", text), part
                forms.add(part["ref"].partition(":")[0])
                # where the route values the company: no secondary valuation, no DCF of any kind
                assert not part["ref"].startswith("secondary:"), part
                assert not part["ref"].endswith("/dcf"), part
    assert set(EXAMPLE_FORMS) <= forms, set(EXAMPLE_FORMS) - forms
    for judgment in example["judgments"]:  # a record: no bull, no bear, no figure
        assert set(judgment) <= {"judgment", "decision", "override_id"}, judgment
        assert quantities(judgment["decision"]) == [], judgment["judgment"]


def test_the_secondary_valuation_is_the_fallback_only() -> None:
    """The founder's rule of 2026-11-08, as ruled on the final review of plan 3: the secondary
    valuation is made where neither the route nor the review values the company, and only there;
    no DCF weighs on the stance where either does, and FMP's figure is read in the same scope;
    a secondary valuation on file on a company the route or the review values is history; a refused
    row with nothing to weigh the price against rests the stance on the thesis."""
    steps = {n: _flat(text) for n, text in _steps(_frontmatter(_read(SKILL))[1]).items()}
    assert HISTORY in steps[3]
    lead = "Where the route or your review values the company, make no secondary valuation and read"
    assert f"{lead} no DCF beside the route's value." in steps[10]
    rule = steps[10].find(
        "Where neither the route nor your review values the company, and only there"
    )
    assert 0 <= rule < steps[10].find("`secondary_valuation`")
    no_dcf = "No DCF weighs on the stance where the route or your review values the company"
    assert no_dcf in steps[11]
    assert VALUE_ORDER in steps[11]
    assert THESIS_ALONE in steps[11]
    assert steps[11].index(VALUE_ORDER) < steps[11].index(THESIS_ALONE)
    assert REFUSED_REVIEW in steps[11]  # a refused review is the agent's to fix (ruling 2026-11-08)
    opening = _flat(_read(SKILL)).split("## The secondary valuation ", 1)[1][:600]
    assert opening.startswith(
        "The fallback, and only the fallback: a value a share by the standard discounted cash flow,"
        " made where neither the route nor your review values the company."
    )
    assert "Make none there, and read no DCF beside the route's value." in opening
    assert _tool_entry("secondary_valuation").startswith(
        "- `secondary_valuation(symbol, reason, evidence, drivers?, parts?, debt?, cash?)`: the"
        " fallback where neither the route nor your review values the company:"
    )
    for exemption in CANNOT_FIX:  # the refusals an agent cannot fix, in the server's words
        assert exemption in _tool_entry("secondary_valuation"), exemption
        assert exemption in steps[10], exemption
        assert cannot_fix(exemption.replace("<code>", "SEK").replace("<π>", "12.1")), exemption
    # FMP's figure takes the secondary valuation's scope, in step 10 and in the tool list
    assert DCF_SCOPE in steps[10]
    assert DCF_SCOPE in _tool_entry("dcf").lower()
    assert STRUCTURE[-1] in _flat(_read(CITATIONS))  # the structural check as the check names it
    for path in sorted(PLAYBOOK.rglob("*.md")):
        text = _flat(_read(path)).lower()
        for phrase in STALE:
            assert phrase not in text, (path.name, phrase)
        assert OLD_FOREIGN_FILER not in text, path.name  # the server refuses no foreign filer


def test_the_references_say_what_the_server_and_the_reader_do() -> None:
    """The final review of plan 3: the check reads a list's number and a table's separator row as
    marks (method 16.3); the screen's rows follow the reviewed value where it is filled, the
    engine's value kept as ``mechanical`` (spec 18.1); and the report template states the whole
    subset of the text the reader renders (spec 13.1, 18.4)."""
    citations = _flat(_read(CITATIONS))
    assert (
        "a list's number at a line's start with a space after it on the same line, `1. `, `12. ` or"
        " `12) `, and a table's separator row, `|---|---|`: marks, not quantities (a number alone on"
        " its line, `12.`, is a quantity);"
    ) in citations
    for mark in ("1. ", "12) "):  # the check agrees: a mark at a line's start, no quantity
        assert quantities(f"Reasons:\n{mark}Licensing renewed.") == []
    assert quantities("|---|---|\n") == []
    assert quantities("Reasons:\n12.\n") != []
    assert (
        "A row's `fairValue`, band, levels, price ÷ value and designation follow the reviewed value"
        " where `reviewed` is filled; `mechanical` is the engine's value."
    ) in _tool_entry("screen")
    template = _flat(_read(TEMPLATE))
    for words in (
        "a blank line between paragraphs",
        "`- ` bullets (not `* `) or `1. ` numbers",
        "with no blank line needed before it",
        "a header row, a `|---|` separator row",
        "`**bold**`",
        "No heading marks, no links, no nested lists, no images: anything else shows as plain text.",
    ):
        assert words in template, words


def test_a_reviewed_rows_flags_follow_the_review() -> None:
    """Spec 2026-11-13 8a: where a review fills the screen's row, the row's flags and count are the
    review's, a secondary valuation's row keeping the snapshot's; the company's ``review`` record
    carries the review's own flags; and the template's share-count sentence says the screen shows
    the review's flags, so a warning the count does not settle stays there."""
    assert (
        "Where `reviewed` is a review's value, the row's `flags` and `flagCount` are the review's"
        " flags too; where it is a secondary valuation's, they stay the snapshot's, since a"
        " secondary valuation has none."
    ) in _tool_entry("screen")
    company = _tool_entry("company")
    for words in (
        (
            "`review`: the current review on the latest snapshot, or on one a price refresh"
            " repriced, `null` without one;"
        ),
        (
            "its `flags` are the review's own, each with its `code`, `word` and `sentence`, as the"
            " screen's row shows them"
        ),
        "on a refused review `flags` is `null`. The `result`'s flags stay the snapshot's.",
    ):
        assert words in company, words
    template = _flat(_read(TEMPLATE))
    assert (
        "Where `share-count-gap` stays because the market cap leaves a class out, say why the count"
        " stands; the screen's row shows the review's flags, so the warning stays there too."
    ) in template


def test_the_note_has_one_form() -> None:
    """Spec 2026-11-06 Tier 2, 8 (plan 4): the note is the request in the user's own words, on one
    line; the skill gives the counter-example, a note with process commentary."""
    skill = _flat(_read(SKILL))
    sentence = (
        "the request in the user's own words, on one line, with no commentary and without adding"
        " the mode"
    )
    assert sentence in skill
    assert sentence in _tool_entry("inbox_post")
    assert "asked in chat on 2026-11-08 (the second run)" in skill  # the counter-example


def test_every_item_is_refreshed_before_it_is_read() -> None:
    """Spec 14 step 3 (plan 5, B-126): a scoped refresh of the company opens step 3 on every
    item, so the report reads the latest price; before plan 5 only an expired company was
    refreshed, and QCOM's report 2 of 8 Nov 2026 read the close of 4 Nov. The snapshot's refresh
    id, not the run's status, proves the company was refreshed: a scoped run whose fetch of the
    company fails still ends `done` (the final review of plan 5)."""
    _, body = _frontmatter(_read(SKILL))
    steps = _steps(body)
    three = _flat(steps[3])
    assert "Every item: refresh the company before you read it" in three
    assert 'Call `refresh_start("scoped", [symbol])` and keep the `refreshId` it answers' in three
    assert "call `refresh_status()` until that one ends, then start yours" in three
    wait = "Call `refresh_status()` until its `refresh` is `null`"
    check = "When its `snapshot.refreshId` is not the id you kept, the company was not refreshed"
    assert wait in three and check in three and three.index(wait) < three.index(check)
    assert "`last` is the one you started" not in three  # the old test of success is gone
    # the tool list names both fields as the server answers them (web/app.py, web/rows.py)
    assert '`{"refreshId": <id>}`' in _tool_entry("refresh_start")
    assert "`snapshot.refreshId`" in _tool_entry("company")
    assert "Tell the user, go on with the stored snapshot" in three
    assert "write the price's date in section 9 of the report" in three
    # a split's remedy is this refresh, every call made again (the whole-branch review of plan 2)
    assert "When a stock split has taken effect, this scoped refresh is the remedy" in three
    assert "(every call, whatever was fetched that day)" in three
    skill = _flat(_read(SKILL))
    assert (
        "Start a refresh only in three cases: the scoped refresh of the company at the start of"
        " step 3"
    ) in skill
    assert "`valid_until` before today" not in skill  # the old condition is gone
    # step 2 no longer refreshes
    assert "Refresh it first, at the start of step 3" not in _flat(steps[2])


def test_the_report_writes_the_plain_phrase_not_the_term() -> None:
    """Spec 13.1 "The words" and 14 (plan 5, B-134): the register maps each method term to the
    phrase the report writes; the term appears once, in brackets, in section 8 only; the names of
    Fairband's parts never appear; the template's example and summary shape are written so."""
    register = _read(REGISTER)
    assert "## The words a report writes" in register
    flat = _flat(register)
    assert "Write what a figure is, not what Fairband calls it" in flat
    assert "in brackets after the phrase, in section 8 only" in flat
    for word in NEVER:
        assert f'"{word}"' in flat, word  # each named in the never-list
    rows = _table_rows(register, ("Term", "Write instead"))
    for term in TERMS:
        assert term in rows, term
        assert rows[term] and not rows[term].startswith("the engine"), term
    assert "every term explained the first time" not in _flat(_read(SKILL))
    assert "the method's terms as `reference/register.md` writes them" in _flat(_read(SKILL))
    # the old 9.2 bullet, which told the agent to write the term
    assert "Name the input in words" not in flat
    # the template: the shape, the example's text and the judgments
    template = _read(TEMPLATE)
    shape = _shape(template)
    example = _example(template)
    sections = {
        s["heading"]: " ".join(p for p in s["parts"] if isinstance(p, str))
        for s in example["sections"]
    }
    decisions = [j["decision"] for j in example["judgments"]]
    # the page shows the kill criteria and the news items as well
    shown = [k["text"] for k in example["kill_criteria"]] + [
        n[key] for n in example["news_items"] for key in ("headline", "text")
    ]
    for text in [shape, *sections.values(), *decisions, *shown]:
        for word in (*NEVER, "snapshot", "bridge"):  # their phrase stands alone, in section 8 too
            assert not _has(word, text), (word, text[:80])
    for term in SUMMARY_FREE:
        assert not _has(term, sections["Summary"]), term
        assert not _has(term, shape), term
    # in section 8 a term stands only in brackets, a longer bracketed term's part counting as
    # bracketed ("runway" in "(the runway return)"), and is named in brackets once at most
    valuation = sections["Valuation"].lower()
    brackets = [
        (m.start(), m.end(), m[1]) for m in re.finditer(r"\((?:the )?([^()]*)\)", valuation)
    ]
    for term in TERMS:
        found = [m.span() for m in re.finditer(rf"\b{_term(term)}\b", valuation)]
        bare = [s for s in found if not any(a < s[0] and s[1] < b for a, b, _ in brackets)]
        assert bare == [], term
        named = [n for _, _, n in brackets if re.fullmatch(_term(term), n)]
        assert len(named) <= 1, term
        if term in ("belief", "runway return", "mechanical value", "reviewed value"):
            assert len(named) == 1, term
    # outside section 8 no term of the table appears: the shape, the other sections, the
    # decisions, the kill criteria and the news items
    others = [text for heading, text in sections.items() if heading != "Valuation"]
    for text in [shape, *others, *decisions, *shown]:
        for term in TERMS:
            assert not _has(term, text), (term, text[:80])
    # the mechanical value is the value with no override at all, an earlier report's included,
    # and the reviewed value the value under every applied one (the final review of plan 5)
    for path in (REGISTER, TEMPLATE):
        assert "this report's changes" not in _flat(_read(path)), path.name


def test_the_report_is_read_as_its_reader_before_it_is_submitted() -> None:
    """Spec 14 step 12 (plan 5, B-134): the agent reads the report once as someone who has never
    seen Fairband, before `report_submit`, so a report fixed after a rejection is read again."""
    _, body = _frontmatter(_read(SKILL))
    twelve = _flat(_steps(body)[12])
    sentence = "read the report once as its reader: someone who has never seen Fairband"
    assert sentence in twelve
    assert "Rewrite every sentence that needs the Methodology page to follow" in twelve
    assert '"The words a report writes"' in twelve
    assert "the summary alone: it must stand on its own" in twelve
    assert twelve.index(sentence) < twelve.index("Submit with `report_submit`")


def test_the_overrides_table_names_the_twenty_five_inputs() -> None:
    """Spec 2026-11-09 8 and 12 (the engine round 2, plan 1), spec 2026-11-13 7.2 and 13 and spec
    2026-11-14 4, 5 and 6.1: the skill's overrides table names the twenty-five inputs the engine
    takes, each once, with the routes that read it; the two revenue steps are Mature Growth's,
    the revenue growth the charge pays for in place of the consensus's, period-tied only, and a
    guidance record gives one as the growth of its midpoint over the revenue consensus; the share
    count is period-tied only and moves the next twelve months' net income with it, so the agent
    reads the consensus EPS's share basis first; the committed shares, shares neither the count
    nor the analysts' EPS holds yet, are period-tied only, from the filing that commits them,
    dilute the value a share by x ÷ (n + x) and bring their cash through another input; the
    one-time item in the NTM consensus is a figure a share after tax, period-tied only, off the
    NTM EPS, on the evidence of the filing's other-income line and the analysts' basis, and moot
    under `earnings.ntm`; the value outside the business is after tax, and its gains come out of
    the earnings through the non-recurring gap on Mature Stable and the one-time item on Mature
    Growth, so nothing counts twice; the stock pay is a total from the filing's cash flow
    statement, period-tied, or lasting at 0 alone (spec 2026-11-13 7.3), and the stock-pay basis
    rests on the release's definition of its adjusted EPS; the minority interest is a total,
    period-tied only, for a market value or a redeemable stake the line leaves out, from the
    filing's note on non-controlling or redeemable interests; the bridge's lines run in the
    engine's order, the revenue steps' after the consensus steps', the minority interest's after
    cash, the committed shares' after the count's and the one-time item's before the cycle gap's;
    the passage no longer says that a raised count barely moves a Mature Growth value; the tool
    list counts the twenty-five, names the two revenue steps, and says that the write's refusal of
    a lasting nil stores nothing."""
    skill = _read(SKILL)
    table = _table(skill, ("Tag", "Routes that read it", "The input", "Takes, the ends included"))
    tags: list[str] = []
    for first, (routes, _, _) in table.items():
        named = re.findall(r"`([\w.]+)`", first)
        tags += named
        phases = set(PHASES) if routes == "every route" else {p for p in PHASES if p in routes}
        for tag in named:
            assert phases == {p for r in TAGS[tag].routes for p in ROUTE_PHASES[r]}, tag
    assert len(tags) == len(set(tags)) == 25 and set(tags) == set(TAGS)
    revenue = _flat(" ".join(table["`revenue.step_2`, `revenue.step_3`"]))
    for words in (
        "the revenue growth of year two or year three that the charge pays for",
        "in place of the analysts' revenue step",
        "the analysts' step as found",
        "−0.80 to 3.00; period-tied only",
    ):
        assert words in revenue, words
    # a revenue step from a guidance record: the growth of its midpoint over the revenue consensus
    assert (
        "`revenue.step_2`, `revenue.step_3` (Mature Growth): a full-year revenue guidance for the"
        " base year plus one, or plus two. `new` is the `derive` `growth` of the record's midpoint"
        " over the consensus for the year before, its `estimate:` revenue."
    ) in _flat(skill)
    shares = _flat(" ".join(table["`shares.diluted`"]))
    for words in (
        "period-tied only",
        "NTM net income",
        "read the consensus EPS's own share basis first",
    ):
        assert words in shares, words
    committed = _flat(" ".join(table["`shares.committed`"]))
    for words in (
        "neither the diluted count nor the analysts' EPS holds yet",
        "x ÷ (n + x)",
        "the filing that commits them",
        "`balance.cash` or `value.outside`",
        "above 0 shares; period-tied only",
    ):
        assert words in committed, words
    one_time = _flat(" ".join(table["`earnings.ntm_nri`"]))
    for words in (
        "a one-time item a share that the analysts' NTM EPS carries and that does not recur",
        "after tax",
        "comes off the NTM EPS",
        "a negative figure, a one-time loss, raises it",
        "the filing's other-income line and the analysts' basis",
        "Under `earnings.ntm` it moves nothing",
        "−100 to 100 dollars a share; period-tied only",
    ):
        assert words in one_time, words
    # a raised count no longer reads as barely moving a Mature Growth value (spec 2026-11-14 4)
    for words in (
        "the value a share moves only through the stock compensation a share",
        "a raised count does not dilute the value",
    ):
        assert words not in _flat(skill), words
    outside = _flat(" ".join(table["`value.outside`"]))
    for words in (
        "after tax",
        "−1,000 to 1,000 dollars a share",
        "`earnings.nri_gap`",
        "twice",
        "`earnings.ntm_nri`",
    ):
        assert words in outside, words
    pay = _flat(" ".join(table["`earnings.sbc`"]))
    for words in (
        "a total",
        "cash flow statement",
        "0 dollars or more, period-tied; lasting at 0 only, for a company that pays no stock",
    ):
        assert words in pay, words
    basis = _flat(" ".join(table["`earnings.sbc_basis`"]))
    for words in ("`includes` or `excludes`", "definition of its adjusted EPS", "the release"):
        assert words in basis, words
    minority = _flat(" ".join(table["`balance.minority`"]))
    for words in (
        "a total",
        "a market value",
        "a redeemable stake that the line leaves out",
        "the filing's note on non-controlling or redeemable interests",
        "0 dollars or more; period-tied only",
    ):
        assert words in minority, words
    # the charge divides by the runway return, so the range excludes 0 (the final review's fix);
    # policy v13 takes it to 5.00, so the engine's own measure fits (spec 2026-11-13 10)
    assert table["`return.runway`"][2] == "above 0 to 5.00"
    # the outside figure is a share on the count in force, a new count's when one is set
    assert "with `shares.diluted` also set, divide the asset's worth by the new count" in _flat(
        skill
    )
    order = ", ".join(LABELS[tag] for tag in BRIDGE_ORDER)
    assert f"The lines run in the method's order: {order}." in _flat(skill)
    assert order.endswith(
        "moat, debt, cash, minority interest, diluted shares, committed shares, outside the business"
    )
    entry = _tool_entry("override_add")
    for words in (
        "twenty-five",
        "`shares.diluted`",
        "`shares.committed`",
        "`earnings.ntm_nri`",
        "`revenue.step_2`",
        "`revenue.step_3`",
        "`value.outside`",
        "`balance.minority`",
        # the write's own refusal of a lasting nil answers the sentence alone (spec 2026-11-13 7.3)
        (
            "A lasting `earnings.sbc` of 0 on a row whose trailing stock pay is above zero is"
            " refused with the sentence alone, and nothing is stored."
        ),
    ):
        assert words in entry, words


def test_the_agent_reads_the_stock_pay_on_mature_growth() -> None:
    """Spec 2026-11-13 7.2: in every Mature Growth report the agent reads the company's own
    definition of its adjusted EPS in the release, says in section 8 whether it leaves out stock
    pay, and sets `earnings.sbc_basis` with that passage as evidence where the row reads
    otherwise; where `stock-pay-missing` shows, it reads the trailing stock pay from the filings'
    cash flow statements and sets `earnings.sbc`, period-tied."""
    eight = _flat(_steps(_frontmatter(_read(SKILL))[1])[8])
    for words in (
        "On Mature Growth, two steps on the stock pay, in every report",
        "the company's own definition of its adjusted EPS in the earnings release",
        "Section 8 says whether it leaves out stock pay",
        "set `earnings.sbc_basis`, `includes` or `excludes`, with that passage as evidence",
        # under a guided NTM EPS neither input moves the value, but the basis is still stated
        (
            "Under an applied `earnings.ntm` section 8 still states the basis, and the report sets"
            " neither stock-pay input"
        ),
        "Where `stock-pay-missing` shows, read the trailing stock pay in the cash flow statements",
        "set `earnings.sbc`, their total in the reporting currency, period-tied",
    ):
        assert words in eight, words


def test_the_agent_sets_a_lasting_nil_for_a_company_that_pays_no_stock() -> None:
    """Spec 2026-11-13 7.3: where the filings show nil too, the agent sets a lasting
    `earnings.sbc` of 0 with the filing as evidence, once; the system drops it when the stored
    trailing stock pay is above zero; the rules refuse a lasting figure but 0, and the server a
    lasting 0 on a row whose trailing stock pay is above zero, where the period-tied nil is the
    one to set; section 8 says so."""
    skill = _flat(_read(SKILL))
    eight = _flat(_steps(_frontmatter(_read(SKILL))[1])[8])
    for words in (
        (
            "Where the filings show nil too, the company pays no stock: set a lasting"
            " `earnings.sbc` of 0 with the filing as evidence, and section 8 says so."
        ),
        "It holds across periods, so a later report does not set it again",
        "the system drops it once the stored trailing stock pay is above zero",
        "where the row's trailing stock pay (`intermediates/sbc_ttm`) is above zero",
        "set the filings' nil period-tied",
    ):
        assert words in eight, words
    for words in (
        # the rules' list: a lasting stock pay takes 0 alone
        (
            "a lasting override of a balance tag (debt, cash or the minority interest) or of the"
            ' share count, or a lasting stock pay at any figure but 0: "a lasting earnings.sbc'
            ' takes 0 only: a figure is period-tied".'
        ),
        # the write's check after the rules, which stores nothing
        (
            "After them, it refuses a lasting `earnings.sbc` of 0 where the snapshot's trailing"
            " stock pay is above zero, \"a lasting earnings.sbc of 0 is refused: the snapshot's"
            ' trailing stock pay is above zero", and stores nothing'
        ),
        # the lifetimes
        (
            "A lasting `earnings.sbc` of 0 holds across periods, and the system drops it once the"
            ' stored trailing stock pay is above zero: "the store holds a trailing stock pay above'
            ' zero".'
        ),
    ):
        assert words in skill, words


def test_the_citations_name_the_newest_sheet_and_the_minority_interest() -> None:
    """Spec 2026-11-13 12.2 and 13: on the three firm-value routes the citations name the input
    `minority_interest`, the line as the newest balance sheet presents it, the intermediate of
    the same name, the figure the route subtracts, and the sheet's period beside debt and cash."""
    row = _table(_read(CITATIONS), ("Ref", "The stored value", "Unit"))
    inputs = _flat(row["`snapshot:<id>/inputs/<name>`"][0])
    for words in (
        "On High Growth, Young Growth, Decline and Start-up, `debt` and `cash`",
        "are the newest balance sheet's, a quarter's or a fiscal year's",
        "`minority_interest` is that sheet's minority interest as it presents it",
    ):
        assert words in inputs, words
    intermediates = _flat(row["`snapshot:<id>/intermediates/<path>`"][0])
    for words in (
        "`minority_interest`, the minority interest the route subtracted",
        "`balance_sheet/label` and `balance_sheet/period_end`",
    ):
        assert words in intermediates, words


def test_the_citations_name_the_anchor_s_source() -> None:
    """Spec 2026-11-13 9a, as amended: on Mature Growth the citations name what the analysts' NTM
    EPS read, the window's periods or their sum corrected by the annual consensus of the last
    fiscal year the window reaches, the periods' sum, and each figure of the correction."""
    row = _table(_read(CITATIONS), ("Ref", "The stored value", "Unit"))
    intermediates = _flat(row["`snapshot:<id>/intermediates/<path>`"][0])
    for words in (
        "On Mature Growth, `anchor/source`, what the analysts' NTM EPS read",
        "`periods`, the sum of the NTM window's EPS means",
        "`annual`, that sum corrected by the annual consensus of the last fiscal year the window",
        "`anchor/periods_sum`",
        "`anchor/annual/fiscal_year`",
        "`anchor/annual/eps`",
        "`anchor/annual/analysts`",
        "`anchor/annual/year_sum`",
        "`anchor/annual/share`",
        "`anchor/annual/correction`",
    ):
        assert words in intermediates, words
    assert "`anchor/annual/<n>/" not in intermediates  # the first form's list of years


def test_the_register_s_floor_takes_the_minority_interest_off() -> None:
    """Spec 2026-11-13 13: the liquidation floor is the common owners' claim, so the plain words a
    report writes for it take off the share of the subsidiaries that outside owners hold."""
    rows = _table_rows(_read(REGISTER), ("Term", "Write instead"))
    assert rows["liquidation floor"].startswith(
        "the company's current assets less all its liabilities and less the share of its "
        "subsidiaries that outside owners hold, a share;"
    )


def test_the_cycle_formula_reads_the_ten_year_median_net_margin() -> None:
    """Spec 2026-11-13 11: the cycle formula changes one term, the mid-cycle net margin, now the
    snapshot's ten-year median net margin in place of the middle of the growth table's five
    years; a shorter history is named with its count; a consensus that leaves out the amortization
    of bought intangibles against a history as reported is evidence for half; the ruling of
    2026-11-11 stands otherwise, and a gap on file keeps its figure until its review is made
    again. Step 7 reads the ten-year median operating margin on every route; the template and the
    citations name the new paths."""
    flat = _flat(_read(SKILL))
    start = flat.index("The cycle gap's figure.")
    formula = flat[start : flat.index("The share count and the value outside the business:")]
    for words in (
        "full gap = NTM EPS − NTM EPS ÷ (NTM net margin ÷ mid-cycle net margin)",
        (
            "The mid-cycle net margin is the ten-year median net margin,"
            " `snapshot:<id>/intermediates/margin_history/net/median`"
        ),
        "A history of fewer than ten years is named with its count",
        "`snapshot:<id>/intermediates/margin_history/net/years`",
        (
            "leaves out the amortization of bought intangibles while the history is as reported,"
            " the full gap cuts for accounting as well as for the cycle"
        ),
        "that is evidence for half",
        "Take the full gap.",
        "Take half of it only where a filing or a transcript shows a lasting cause",
        "Never take less than half.",
        "An `earnings.cycle_gap` on file keeps its figure until its review is made again",
        "Never set the gap from a trailing margin or from an operating margin.",
    ):
        assert words in formula, words
    for old in ("growth/net_margin", "middle one of the five", "no tool gives a median"):
        assert old not in flat, old
    seven = _flat(_steps(_frontmatter(_read(SKILL))[1])[7])
    for words in (
        "On every route the snapshot's intermediates hold the ten-year median operating margin",
        "`margin_history/operating/median`",
        "`margin_history/operating/years`",
        "never a median you computed",
        "Where fewer than ten years stand behind it, name the count",
    ):
        assert words in seven, words
    template = _flat(_read(TEMPLATE))
    assert "`snapshot:<id>/intermediates/margin_history/net/median`" in template
    assert "the net margin of the middle year" not in template
    row = _table(_read(CITATIONS), ("Ref", "The stored value", "Unit"))
    cell = row["`snapshot:<id>/intermediates/<path>`"][0]
    for path in ("operating/median", "net/median", "operating/years", "net/years"):
        assert f"`margin_history/{path}`" in cell, path


def test_the_agent_judges_the_runway_return_and_reads_the_notes() -> None:
    """Spec 2026-11-09 6.3, 7, 9 and 12 (the engine round 2, plan 1): the return judgment reads
    the newest year's marginal return and the capital-spending guidance when `heavy-capex` fires;
    step 8 says what each flag that asks for a decision asks; the citations name the new
    intermediates; section 8's detail names the charge, the value outside the business and the
    share count, each with what it cites."""
    skill = _read(SKILL)
    judgments = _table(skill, ("Judgment", "On", "What it records"))
    assert judgments["`roic`"] == ["Mature Growth, Mature Stable", ROIC_JUDGMENT]
    eight = _steps(_frontmatter(skill)[1])[8]
    flags = {
        code: _flat(text)
        for code, text in re.findall(
            r"^- `([\w-]+)`: (.*?)(?=^- |^$|\Z)", eight, re.MULTILINE | re.DOTALL
        )
    }
    for code, words in (
        ("heavy-capex", ("`roic`", "`return.runway`", "stops after the spending share")),
        (
            "growth-above-return",
            (
                "the owner funds the growth",
                # a wrong revenue step has its own inputs (spec 2026-11-14 6.1)
                "On Mature Growth years two and three pay for the analysts' revenue growth",
                "rests on few analysts or outruns the business's record",
                "set `revenue.step_2` or `revenue.step_3` from a guidance record or a filing",
                "`return.runway` is not the lever for a wrong revenue step",
            ),
        ),
        (
            "consensus-basis-unknown",
            (
                "`large-nri`",
                "`earnings.nri_gap`",
                "only while no `earnings.sbc_basis` is applied",
                # a one-time item the consensus carries (spec 2026-11-14 5)
                "`earnings.ntm_nri`",
                "the filing's other-income line",
                "`earnings.ntm`",
                "guidance record",
                "exposure",
            ),
        ),
        ("step-series-disagree", ("both series", "`path.step_2`", "`path.step_3`")),
        (
            "thin-ntm",
            (
                "`analyst_min`",
                # the anchor on a thin window (spec 2026-11-13 9a, as amended): the note means a
                # thin period is left as it is, and names why
                "and is left as it is",
                "the engine corrects year 1 by that year's annual consensus",
                "read the anchor's source at `snapshot:<id>/intermediates/anchor/source`",
                "the period's fiscal year is partly reported, which is never corrected",
                "not every period of that year has an estimate",
                "how many of the window's periods are left thin, the smallest count and its period",
                "the annual estimates of the fiscal years the window spans",
                "their analyst counts",
                "guidance",
                "clear EPS guidance record",
                "`earnings.ntm`",
                "once it applies",
                "states the exposure",
            ),
        ),
        (
            "stock-pay-missing",
            (
                "cash flow statements",
                "`earnings.sbc`",
                "period-tied",
                "lasting at 0 where they show nil too",
                "once `earnings.sbc`",
                GUIDED_STOCK_PAY,
            ),
        ),
        (
            "sbc-basis-uncertain",
            (
                "definition of its adjusted EPS",
                "the release",
                "`earnings.sbc_basis`",
                "once `earnings.sbc_basis`",
                GUIDED_STOCK_PAY,
            ),
        ),
        (
            "share-count-gap",
            (
                "both figures",
                "`share_count_gap_band`",
                "a share class or units that convert to shares",
                "the market cap may leave a class out",
                "cover page",
                "note on the share classes",
                "`shares.diluted`",
                "reconciles the two",
            ),
        ),
        (
            # the sheet-shift note (spec 2026-11-13 12.5): the quarter's filing decides the figure
            "sheet-shift",
            (
                "a quarter's",
                "the newest annual sheet's",
                "the balance sheet in the filing of that quarter",
                "`balance.debt`",
                "`balance.cash`",
                "`balance.minority`",
                "the sentence it decides does not show",
                "lease liabilities",
                "needs no input",
                "the report says so",
            ),
        ),
        (
            "split-pending",
            (
                "no net-income mean",
                # spec 2026-11-14 7: the system scales an override made before the split
                "`earnings.cycle_gap`",
                "`shares.committed`",
                "apply on the new basis",
                "keeps the figure you entered",
                "`override-split-scaled`",
                "the figure in force",
                "the input the override corrected changed",
            ),
        ),
    ):
        assert code in flags, code
        for word in words:
            assert word in flags[code], (code, word)
    # the runway return is decided on the two mature routes alone (the Task 8 review)
    heavy = flags["heavy-capex"]
    assert heavy.startswith("on Mature Growth and Mature Stable"), heavy
    # the split note's first sentence says when it fires (the whole-branch review of plan 2)
    split = flags["split-pending"]
    assert split.startswith(
        "a split falls after the oldest period of the trailing figures and on or before the"
        " quote's date."
    ), split
    assert "drop and re-make them on the new basis" not in split
    # a mature row with the charge off or the return unavailable still takes the judgment; only
    # the other routes have no runway return to decide (the Task 8 fix round 2, method 14.4)
    for words in (
        (
            "On a mature row whose charge is off or whose return is unavailable, the sentence"
            " stops after the spending share until a `return.runway` override sets the start, and"
            " the judgment still stands"
        ),
        "an off charge leaves the runway years uncharged",
        "an unavailable return charges every year at the terminal return",
        (
            "On the other routes the sentence stops after the spending share, and there is no"
            " runway return to decide."
        ),
    ):
        assert words in heavy, words
    assert "the return is unavailable, the sentence stops after the spending share: there" not in (
        heavy
    )
    row = _table(_read(CITATIONS), ("Ref", "The stored value", "Unit"))
    cell = row["`snapshot:<id>/intermediates/<path>`"][0]
    for path in NEW_INTERMEDIATES:
        assert f"`{path}`" in cell, path
    template = _read(TEMPLATE)
    valuation = _flat(template[template.index("### Section 8") : template.index("### Section 9")])
    for words in (
        "**The charge**",
        "`snapshot:<id>/intermediates/charge/return_by_year/<n>`",
        "`/charge/growth_by_year/<n>`",
        "**The value outside the business**",
        "**The share count**, where an override set one or `share-count-gap` stays",
        "`review:<id>/bridge/<n>/new`",
        "`earnings.nri_gap`",
        "NTM net income",
        "why it is not added",
        # what step 8 asks section 8 to say (the whole-branch review of the research round's
        # plan 1, its Minor 4): a class the count leaves out, and why a share-count warning stays
        "a share class or units that convert to shares that the count leaves out",
        "Where `share-count-gap` stays because the market cap leaves a class out",
        # shares not yet issued, through their own input (spec 2026-11-14 4)
        "`shares.committed`, with the filing that commits them",
        "x ÷ (n + x)",
        # the stock pay's basis with its passage, and a nil the filings confirm, set lasting
        "**The stock pay**, on Mature Growth",
        "whether the company's adjusted EPS leaves out stock pay",
        "the passage cited as a finding",
        "Under an applied `earnings.ntm` still state the basis, and set neither stock-pay input",
        (
            "where the filings show nil too, say so, with the filing cited: the company pays no"
            " stock, and a lasting `earnings.sbc` of 0 records it."
        ),
        # the exposure under a thin NTM consensus
        "**The thin NTM consensus**, where `thin-ntm` shows",
        "the thin periods and their share of the NTM EPS",
    ):
        assert words in valuation, words


def test_the_agent_judges_the_return_without_goodwill() -> None:
    """Method 4.6 rule 5 and 14.4 (the founder's ruling of 2026-11-12): the engine starts the
    charge at the return without goodwill where the measure is below the hurdle rate, and the
    agent decides whether the growth ahead is built or bought, with the door back."""
    skill = _read(SKILL)
    eight = _flat(_steps(_frontmatter(skill)[1])[8])
    for words in (
        (
            "- `return-without-goodwill`: the measured return on new capital was below the hurdle "
            "rate, and the charge starts at the return on capital without goodwill and intangibles"
        ),
        "(`policy()`, `return_without_goodwill_cap`)",
        "That reading is right only where the growth ahead is built, not bought.",
        # the hurdle rate is the row's own: restated on a company in another currency, where
        # `policy()` answers the US dollar rate (the review of 2026-11-12)
        (
            "set `return.runway` at the row's hurdle rate, the `required_return` input of "
            "`company`, which is restated on a company in another currency"
        ),
        "That takes the terminal return's part back too.",
        "Decide it in the `roic` judgment.",
        "`intermediates/runway_return/without_goodwill/measure`",
        # the engine keeps the floor where purchases carried the capital's growth, and records it
        (
            "Where purchases carried the growth of the capital "
            "(`intermediates/runway_return/without_goodwill/bought`), the engine keeps the floor "
            "(`return-floored`)"
        ),
        # only a row the engine started at the return without goodwill lets the override set the
        # terminal return; a floored row and one above the hurdle rate keep theirs (method 14.4)
        (
            "On a floored row the override raises the start, and the terminal return stays at the "
            "hurdle rate"
        ),
        "the terminal return stays on the measure",
        # on a row started at the return without goodwill neither the earnings nor the return
        # carry the purchases' cost, which the older ruling on amortization relied on
        (
            "On a row whose charge starts at the return without goodwill, the return leaves that "
            "cost out too"
        ),
    ):
        assert words in eight, words
    assert "bought intangibles" not in _read(TEMPLATE)  # the line holds licences too
    template = _read(TEMPLATE)
    valuation = _flat(template[template.index("### Section 8") : template.index("### Section 9")])
    for words in (
        "the note `return-without-goodwill`",
        "`/runway_return/without_goodwill/measure`",
        "why the growth ahead is the business's own",
        # a business with no capital of its own without them has no such figure to cite; the
        # start is the runway return's value, since year 1 of a row with no hold has faded
        "Where the business has no capital of its own without them, that figure is null",
        "cite the start alone, `/runway_return/value`",
    ):
        assert words in valuation, words
    assert "cite the start alone, `/charge/return_by_year/0`" not in valuation
    row = _table(_read(CITATIONS), ("Ref", "The stored value", "Unit"))
    cell = row["`snapshot:<id>/intermediates/<path>`"][0]
    assert "`runway_return/without_goodwill/measure`" in cell


def test_the_agent_tests_the_higher_case_of_each_input() -> None:
    """The founder's ruling of 2026-11-12, on the low-values investigation: the reviews lowered
    21 values of 28 and raised 3, and no agent raised a growth input in 29 reports. Step 10 tests
    each growth, margin and return input in both directions; the judgment says whether the higher
    case stood; section 8 records each test."""
    skill = _read(SKILL)
    ten = _flat(_steps(_frontmatter(skill)[1])[10])
    for words in (
        "Test each input in both directions.",
        "write the strongest case for a higher figure of each of these",
        (
            "- the growth: the belief on Mature Growth, the held rate on High Growth and Young "
            "Growth, the decline rate on Decline;"
        ),
        "- the margin: the target margin on High Growth, Young Growth and Start-up;",
        (
            "- the return on new capital: the runway return on Mature Growth and Mature Stable, the "
            "sales-to-capital on High Growth and Young Growth."
        ),
        "The case is evidence, not hope",
        "Accept it or reject it, with the reason.",
        "Reject it where it rests on a forecast or a story alone.",
        "Test the lower case with the same care.",
    ):
        assert words in ten, words
    judgments = _table(skill, ("Judgment", "On", "What it records"))
    for kind in HIGHER_CASE_JUDGMENTS:
        assert judgments[kind][1].endswith("whether the higher case stood (step 10)"), kind
    for kind in ("`phase`", "`moat`"):
        assert "higher case" not in judgments[kind][1], kind
    template = _read(TEMPLATE)
    valuation = _flat(template[template.index("### Section 8") : template.index("### Section 9")])
    assert (
        "- **The higher case.** For the growth, the margin and the return on new capital, as "
        "the company's route reads them: the strongest evidence for a higher figure, and why it "
        "stood or did not"
    ) in valuation


def test_the_report_leads_with_what_the_price_needs() -> None:
    """Method 4.11 (the founder's ruling of 2026-11-12): where the price is well above the
    value, the detail carries what the price needs, and the report leads with it."""
    skill = _read(SKILL)
    eight = _flat(_steps(_frontmatter(skill)[1])[8])
    for words in (
        "Where the price is well above the value, the answer of `company` carries `priceNeeds`",
        "A value far below the price says only that the method cannot reach the price.",
        "So judge the need itself",
        # section 8 leads with it; the Summary says it after the value (the template's order)
        "section 8 leads with it and the Summary says it after the value",
    ):
        assert words in eight, words
    assert "`priceNeeds`" in _tool_entry("company")
    template = _read(TEMPLATE)
    valuation = _flat(template[template.index("### Section 8") : template.index("### Section 9")])
    assert valuation.index("- **What the price needs**") < valuation.index("- **The phase.**")
    for words in (
        # each route stores the figure under its own path (the review of 2026-11-12)
        "on Mature Growth, High Growth and Young Growth `snapshot:<id>/intermediates/implied_growth`",
        "on Mature Stable `/growth_route/implied_growth`",
        "on Decline `/implied_decline_rate`",
        "`/implied_margin`",
        "Where no rate reaches the price, say so in words and cite no figure.",
        # a row charged at the hurdle rate: on Mature Growth the growth at the 15% return, named
        # as that case; Mature Stable stores no such figure, so it says it in words
        "on Mature Growth give the growth the price needs at a 15% return, `/implied_by_roic/0.15`",
        "On Mature Stable no such figure is stored: say it in words.",
    ):
        assert words in valuation, words
    summary = _flat(
        template[template.index("## The summary page") : template.index("## A cited part")]
    )
    assert (
        "Where the price is well above the value, the paragraph on the price says what the "
        "price needs"
    ) in summary


def test_the_skill_reads_a_foreign_filer() -> None:
    """Spec 2026-11-10 10: step 3 reads a foreign filer (every figure in the reporting currency but
    the price, the value and the levels; per ADS on an ADR; the rate's ref for any arithmetic
    across the two currencies, through `derive`; the override ranges and the guidance in the
    currency); step 8 reads `basis-scaled` and `fx-stale`; the overrides' ranges in dollars are in
    the currency; a part's free cash flow is in the currency; the citations' format rows name the
    currency; the tools name the company read's fields and the secondary valuation's currency."""
    skill = _read(SKILL)
    steps = {n: _flat(text) for n, text in _steps(_frontmatter(skill)[1]).items()}
    for words in (
        "A foreign filer reports in another currency than the US dollar",
        "`currency`",
        "`adrRatio`",
        "`fxRate`",
        "every per-share figure is per ADS",
        "`snapshot:<id>/inputs/fx_rate`",
        "through `derive`",
        "the override ranges in dollars are in the reporting currency",
        "a guidance record's figures are in the reporting currency",
    ):
        assert words in steps[3], words
    eight = _steps(_frontmatter(skill)[1])[8]
    flags = {
        code: _flat(text)
        for code, text in re.findall(
            r"^- `([\w-]+)`: (.*?)(?=^- |^$|\Z)", eight, re.MULTILINE | re.DOTALL
        )
    }
    assert "Thirteen flags ask for a decision of yours." in steps[8]
    for code, words in (
        ("basis-scaled", ("the ADR ratio", "read as stored", "section 8")),
        ("fx-stale", ("the rate", "price date", '`refresh_start("price")`')),
    ):
        assert code in flags, code
        for word in words:
            assert word in flags[code], (code, word)
    flat = _flat(skill)
    assert (
        "On a company in another currency every range in dollars is in the reporting currency,"
        " each end × the snapshot's rate"
    ) in flat
    assert "`fcff` is the free cash flow to the firm in the reporting currency" in flat
    citations = _flat(_read(CITATIONS))
    for words in (
        "`$` for a figure in US dollars only",
        "put the code before the number in the plain part",
        "or its sign for €, £ and ¥",
    ):
        assert words in citations, words
    company = _tool_entry("company")
    for words in ("`currency`", "`isAdr`", "`adrRatio`", "`fxRate`", "`fxDate`"):
        assert words in company, words
    secondary = _tool_entry("secondary_valuation")
    assert (
        "On a company in another currency pass the path, the debt and the cash in the reporting"
        " currency; the value a share comes back in US dollars."
    ) in secondary
    derive = _tool_entry("derive")
    assert "`snapshot:<id>/inputs/fx_rate`" in derive


def test_nothing_counts_twice_route_by_route() -> None:
    """The Task 8 review of the engine round 2, plan 1 (the controller's ruling, 2026-11-10): the
    skill says route by route how an asset outside the business whose gains run through the
    earnings is added once. On Mature Stable `earnings.nri_gap` strips the gains from the trailing
    earnings; High Growth, Young Growth and Decline read operating income, which the gains never
    enter. On Mature Growth (spec 2026-11-14 5) the agent reads the filing's other-income line
    against the analysts' basis, and where the consensus carries the gains sets
    `earnings.ntm_nri` to them, a share and after tax, then adds the asset; where it excludes
    them the asset is added alone; `earnings.nri_gap` reaches the basis test alone; under
    `earnings.ntm` the item moves nothing; where the agent cannot tell, the asset is left out and
    named in section 8. Mature Stable's rule stands. The template's section 8 says the same."""
    skill = _flat(_read(SKILL))
    for words in (
        "Mature Stable: strip the gains from the trailing earnings through `earnings.nri_gap`",
        (
            "High Growth, Young Growth and Decline: the value reads operating income, which the"
            " gains never enter"
        ),
        (
            "Mature Growth: the value rests on the analysts' consensus for the next twelve months."
            " Read the filing's other-income line against the analysts' basis"
        ),
        (
            "Where the consensus carries the asset's gains, set `earnings.ntm_nri` to them, a share"
            " and after tax, then add the asset through `value.outside`. Where it excludes them,"
            " add the asset alone."
        ),
        (
            "`earnings.nri_gap` does not take them out: it reaches only the test of the anchor's"
            " stock-compensation basis, and only while no `earnings.sbc_basis` is applied"
        ),
        "Under an applied `earnings.ntm` the guidance stands in for the consensus with its items",
        (
            "Where you cannot tell whether the consensus carries the gains, leave the asset out of"
            " `value.outside`"
        ),
        # the cycle formula reads the NTM EPS without the item, so the item is not cut twice
        (
            "Where `earnings.ntm_nri` takes a one-time item out of the NTM EPS, measure the gap on"
            " the figure less the item in the same way"
        ),
        # an asset a growth or Decline route counts already (5a.9; 6a.6 only where the floor
        # sets the value; the fix rounds 2 and 3)
        (
            "unless it already sits in cash and short-term investments, or, on a Decline row whose"
            " value the floor sets (`ncav-floor`), in the current assets the floor reads, which the"
            " route counts already; then it is not outside the business and is not added"
        ),
    ):
        assert words in skill, words
    template = _read(TEMPLATE)
    valuation = _flat(template[template.index("### Section 8") : template.index("### Section 9")])
    assert (
        "On High Growth, Young Growth and Decline, an asset already in cash and short-term"
        " investments, or, on a Decline row whose value the floor sets (`ncav-floor`), in the"
        " current assets the floor reads, is counted by the route already: it is not outside the"
        " business and is not added."
    ) in valuation
    for words in (
        (
            "on Mature Growth the analysts' consensus excludes them, or `earnings.ntm_nri` took"
            " them out of the NTM EPS, cited as its bridge line"
        ),
        (
            "On Mature Growth where you could not tell whether the consensus carries the asset's"
            " gains, no override adds it"
        ),
    ):
        assert words in valuation, words
    # the rule before the review, which told the agent to strip the gains on every route
    assert "strip them through `earnings.nri_gap` in the same review" not in skill
    # the rule before the one-time item, which left a Mature Growth asset out (spec 2026-11-14 5)
    assert "no input strips an asset's gains from it" not in skill
    assert "Add the asset only when the consensus excludes its gains." not in skill


def test_the_agent_reads_fairband_before_it_goes_outside() -> None:
    """Spec 2026-11-11, 8: the filing report, the filing list and the quarters come from Fairband;
    the host's tools read only what Fairband does not hold; a subagent is briefed after the check."""
    skill = _read(SKILL)
    steps = _steps(_frontmatter(skill)[1])
    four, five = _flat(steps[4]), _flat(steps[5])
    for words in (
        "Read Fairband first",
        "`filing_report(symbol)` lists the reports FMP holds",
        "the row's ref plus `/<col>`",
        "the sheet's title names the scale",
        "the scale word stands outside the cite",
        '{kind: "filing", ref: "response:<responseId>", note}',
        "an 8-K's exhibits",
        "by its `finalLink`",
    ):
        assert words in four, words
    assert "`quarters(symbol)`" in five and "`fact:`" in five
    assert (
        "record each quarter's figure as a finding from the 10-Q or the press release" not in five
    )
    assert "`split-pending` or `basis-scaled`" in five
    # the quarter's figures and their two derivations (the fix round of Task 6)
    for words in (
        "The quarter's figures still come from `quarters`.",
        (
            "The operating margin is the `derive` `ratio` of the quarter's operating income to its"
            " revenue."
        ),
        (
            "The free cash flow is the `derive` `sum` of its cash from operations and its capital"
            " spending"
        ),
    ):
        assert words in five, words
    template = _flat(_read(TEMPLATE))
    assert (
        "When the vendor has no transcript, say so first, and build the parts from the press"
        " release. The quarter's figures still come from `quarters`."
    ) in template
    assert "the quarter's finding" not in template  # the example cites the stored quarters
    rules = _flat(skill[skill.index("## The rules") : skill.index("## Guidance")])
    assert "Before you brief a subagent to fetch a figure, check what Fairband holds" in rules
    tools = _flat(_read(TOOLS))
    for words in (
        "at most 100 rows",
        "at most 30,000 characters of the answer's list as it is printed",
        "2,000 characters",
        "a page of 20,000 characters",
        "at most 20 hits",
        "the newest eight",
    ):
        assert words in tools, words
    assert "compact JSON" not in tools  # the budget is measured as the answer is printed
    # the sheet list pages as a sheet's rows do (the final review's A.2)
    sheets = _tool_entry("filing_report")
    assert "at most 100 sheets" in sheets and "`nextRow`" in sheets
    citations = _read(CITATIONS)
    assert "`fact:<symbol>/<line>/<year, quarter or ttm>`" in citations
    assert "`filing:<id>/<sheet>/<row>/<col>`" in citations


def test_a_filing_cell_is_cited_by_the_ref_the_answer_gives() -> None:
    """The reviews of the filings access plan: a cell's ref is copied from its row's `rowRef`,
    never built by hand, since a sheet name with a slash is written `~1` inside a ref; the worked
    cite keeps the scale word outside the cite; the tool list says what each filing read answers
    and how a half-yearly reporter's periods are labelled."""
    never = "Never build a `filing:` ref by hand"
    steps = {n: _flat(text) for n, text in _steps(_frontmatter(_read(SKILL))[1]).items()}
    four = steps[4]
    assert never in four
    citations = _flat(_read(CITATIONS))
    assert never in citations
    for text in (four, citations):  # a hand-built ref may resolve, to the wrong sheet or none
        assert "may resolve to nothing" in text
        assert "resolves to nothing" not in text.replace("may resolve to nothing", "")
    assert "A `filing:` cite takes no `period`" in four  # a cite given one fails wrong period
    # another listed company's report is read but not cited; what FMP holds no report for is not
    assert "a figure from it is a finding" in four
    assert "a filing FMP holds no report for" in four
    # the year and the period come from the list; no 10-Q for a US filer's fourth quarter
    assert "files no 10-Q for its fourth quarter" in steps[5]
    assert "files no 10-Q for its fourth quarter" in _tool_entry("filing_report")
    assert '`filings(symbol, "6-K")`' in steps[5]  # a foreign filer's press release
    assert "it holds the 10-K again" in _tool_entry("filing_report")  # FMP's `Q4` entry, B-169
    assert "read it whole with `row` and `col`" in _tool_entry("filing_report")
    assert "search a longer text" in _tool_entry("filing_search")  # `more` has no page
    # B-169: a note's row of thousands of cells is cut, and a hit's numbers are, each with a count
    for words in (
        "100 at most and 10,000 characters of them as printed",
        "`cellCount`, the count of all its cells",
        "A cell past the cut is read with `row` and `col`, or found by `filing_search`",
    ):
        assert words in _tool_entry("filing_report"), words
    assert "with `numberCount`, the count of all" in _tool_entry("filing_search")
    # the fix's review: a cell past a cut has its column named, and a column's words are cut
    assert "`column` (the words of the cell's column, or `null`)" in _tool_entry("filing_report")
    assert "A column's words are cut at 200 characters" in _tool_entry("filing_report")
    assert "`column` the words of that cell's column, or `null`" in _tool_entry("filing_search")
    # the final review's B.5: a cell's column is a period or a member, read before it is cited
    for text in (four, citations):
        for words in (
            "A sheet's columns are periods or members",
            "read the column's words (the sheet's `columns`, or the hit's `column`) before you cite",
            "name that period in the sentence",
        ):
            assert words in text, words
    assert "`columns`" in _tool_entry("filing_report")
    assert "`{col, value, column}`" in _tool_entry("filing_search")
    # the final review's C.4: a cell is at its sheet's scale, so it is not derived with full units
    for text in (four, citations):
        for words in (
            "A filing cell holds the number at its sheet's scale",
            "do not `derive` a cell with a figure in full units",
            "nor two cells of sheets with different scales",
        ):
            assert words in text, words
    search = _tool_entry("filing_search")
    assert "`33,165` finds the number cell `33165`" in search  # C.3
    assert "read the sheet the hits name" not in search  # C.9: a further match may sit elsewhere
    # C.7: the newest four add to the trailing figures only when those sum four quarters
    quarters = _tool_entry("quarters")
    assert "the newest four add to the trailing figures" not in quarters
    for words in ("the sum of four quarters", "the fiscal-year fallback", "the newest two add"):
        assert words in quarters, words
    assert (
        '{"cite": "$12.5", "ref": "filing:<id>/Leases - Additional Informatio/2/0"}, " million'
    ) in citations
    tools = _flat(_read(TOOLS))
    assert "Seven vendor reads" not in tools  # the count before the filing reads
    for words in ("`nextRow`", "`nextOffset`", "`more`", "`truncated`", "the past 365 days"):
        assert words in tools, words
    assert "`Q2` and `Q4`" in _tool_entry("quarters")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """The text with every run of whitespace one space, so a phrase may cross a line break."""
    return " ".join(text.split())


def _tool_entry(name: str) -> str:
    """The tool's entry in ``reference/tools.md``, from its ``- `name(`` line to the next entry or
    heading, flattened."""
    pattern = rf"^- `{name}\(.*?(?=^- `|^#|\Z)"
    entry = re.search(pattern, _read(TOOLS), re.MULTILINE | re.DOTALL)
    assert entry is not None, name
    return _flat(entry[0])


@cache
def _served() -> dict[str, list[str]]:
    """Each tool the server registers with its arguments, an optional one marked ``?``."""
    with httpx.Client(base_url="http://127.0.0.1:1") as http:  # listing calls nothing
        server = build_server(FairbandClient(http))

        async def listed() -> list[Any]:
            async with Client(server) as session:
                return (await session.list_tools()).tools

        tools = anyio.run(listed)
    served = {}
    for tool in tools:
        required = set(tool.input_schema.get("required", []))
        names = tool.input_schema.get("properties", {})
        served[tool.name] = [n if n in required else f"{n}?" for n in names]
    return served


def _signatures(text: str) -> dict[str, list[str]]:
    """The tools ``reference/tools.md`` lists, one a line, ``- `name(argument, optional?)` ``."""
    found: dict[str, list[str]] = {}
    for name, arguments in re.findall(r"^- `(\w+)\(([^)]*)\)`", text, re.MULTILINE):
        assert name not in found, f"{name} is listed twice"
        found[name] = [a.strip() for a in arguments.split(",")] if arguments.strip() else []
    return found


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    """The skill's frontmatter as ``key: value`` lines, and the body after it."""
    assert text.startswith("---\n")
    head, _, body = text[4:].partition("\n---\n")
    front = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        front[key.strip()] = value.strip()
    return front, body


def _steps(body: str) -> dict[int, str]:
    """Each step under its heading ``### <n>. ...``, to the next heading of its level or above."""
    found = {}
    for match in re.finditer(r"^### (\d+)\. (.*?)(?=^#{1,3} |\Z)", body, re.MULTILINE | re.DOTALL):
        found[int(match[1])] = match[2]
    return found


def _example(text: str) -> dict[str, Any]:
    """The template's full submission example: of its ``json`` blocks, the one with sections."""
    blocks = re.findall(r"^```json\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    submissions = [b for b in map(json.loads, blocks) if "sections" in b]
    assert len(submissions) == 1
    found: dict[str, Any] = submissions[0]
    return found


def _table_rows(text: str, header: tuple[str, str]) -> dict[str, str]:
    """The Markdown table in ``text`` whose header row is ``header``: its first column to its
    second."""
    return {first: rest[0] for first, rest in _table(text, header).items()}


def _table(text: str, header: tuple[str, ...]) -> dict[str, list[str]]:
    """The Markdown table in ``text`` whose header row is ``header``, cell for cell: each row's
    first cell to its other cells, from the row after the separator to the first line that does
    not start with ``|``."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if _cells(line) == list(header))
    rows = {}
    for line in lines[start + 1 :]:
        if not line.startswith("|"):
            break
        cells = _cells(line)
        if not set(cells[0]) <= {"-", ":"}:  # the separator row left out
            rows[cells[0]] = cells[1:]
    return rows


def _cells(line: str) -> list[str]:
    """A Markdown table line's cells, stripped."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _has(word: str, text: str) -> bool:
    """Whether ``word`` is in ``text`` as a whole word or phrase, case ignored, its plural
    included: "overrides" holds "override", and "kill criteria" "kill criterion"; "an id" is not
    in "an idea", nor "review" in "reviewed"."""
    return re.search(rf"\b{_term(word)}\b", text.lower()) is not None


def _term(word: str) -> str:
    """The pattern of ``word`` in lower case with its plural: an ending ``s`` or ``es``, or
    "criteria" for "criterion"."""
    pattern = re.escape(word.lower())
    if pattern.endswith("criterion"):
        return f"{pattern[: -len('on')]}(?:on|a)"
    return f"{pattern}(?:e?s)?"


def _shape(text: str) -> str:
    """The summary page's shape: the fenced block after ``## The summary page``."""
    after = text[text.index("## The summary page") :]
    return re.search(r"^```\n(.*?)^```", after, re.MULTILINE | re.DOTALL)[1]
