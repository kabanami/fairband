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
import tarfile
from collections.abc import Callable
from contextlib import closing
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any, get_args

import anyio
import httpx
from mcp import Client

from fairband.config import MissingKey
from fairband.engine.overrides import BRIDGE_ORDER, LABELS, NO_GUIDANCE, TAGS, anchor_misfit
from fairband.launch.command import TEST_PROMPT
from fairband.launch.settings import DEFAULTS
from fairband.mcp.client import NOT_RUNNING, FairbandClient
from fairband.mcp.server import TOOL_NAMES, build_server
from fairband.policy import load_policy
from fairband.refresh.passthrough import BUSY, NO_GF_KEY
from fairband.refresh.rates import NO_RATE
from fairband.refresh.reviews import OFF_ROUTE
from fairband.reports.charts import BAND_TITLE
from fairband.reports.check import (
    FAILURES,
    HEADINGS,
    STRUCTURE,
    parse_cite,
    quantities,
    structure_refusal,
)
from fairband.reports.refs import KILL_FORM, NUMBER_FORM, NUMBERS, day_words
from fairband.reports.render import resting_words
from fairband.reports.tables import QUARTERS, TABLES, Kind
from fairband.store.currency import check_currency
from fairband.store.db import connect, migrate
from fairband.store.research import _require_figure
from fairband.store.secondary import cannot_fix
from fairband.store.settings import effective_policy
from fairband.web.app import _NO_WORKER as NO_WORKER
from fairband.web.identity import IDENTIFY_FIRST
from fairband.web.reviews_api import (
    DEPENDS_ON_A_FIGURE,
    FIXED_NUMBERS,
    GUIDANCE_REF,
    NEEDS_A_FIGURE,
    REDERIVE,
)
from fairband.web.vendor_api import NO_FMP_KEY

PLAYBOOK = Path(__file__).parent.parent / "playbook" / "fairband-research"
SKILL = PLAYBOOK / "SKILL.md"
TOOLS = PLAYBOOK / "reference" / "tools.md"
CITATIONS = PLAYBOOK / "reference" / "citations.md"
TEMPLATE = PLAYBOOK / "reference" / "report-template.md"
REGISTER = PLAYBOOK / "reference" / "register.md"
# The brand book, inside the design system's archive (CLAUDE.md: read it without unpacking).
DESIGN_SYSTEM = (
    Path(__file__).parent.parent / "docs" / "design-system" / "fairband-design-system_4.tar.gz"
)
BRAND_BOOK = "fairband-design-system/docs/brand-book.md"
# The section a `kill:` cite passes in alone (spec 2026-11-15 8.2), as the check names it.
KILL_SECTION = HEADINGS[10]

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
    "kill",
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
    # a fixed number in `derive` (spec 2026-11-15 7.1)
    f"{FIXED_NUMBERS}, not <what was written>",
    NEEDS_A_FIGURE,
    DEPENDS_ON_A_FIGURE,
    REDERIVE,  # the controller's ruling 8
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
# The two mode names, which a report writes as given ("The words a report writes").
MODES = ("full report", "valuation review")
# A bracket in section 8's text, "the" before its words left out.
BRACKET = re.compile(r"\((?:the )?([^()]*)\)")
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
    " capital-spending guidance, decide the runway return and cite both figures; where the charge"
    " starts at the five-year marginal return, read the same return at a constant margin"
    " (`intermediates/runway_return/constant_margin`) and decide whether new capital earned the"
    " margin's gain; when `return-without-goodwill` fires, decide whether the growth ahead is built"
    " or bought; and whether the higher case stood (step 10)"
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
    judged = [j["judgment"] for j in example["judgments"]]
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
    # the fallback in its two forms, the standard one and the parts (method 15.1; B-138)
    opening = _flat(_read(SKILL)).split("## The secondary valuation ", 1)[1][:700]
    assert opening.startswith(
        "The fallback, and only the fallback: a value a share by a discounted cash flow, from"
        " drivers you set (the standard form) or from free cash flows you build part by part (the"
        " parts form), made where neither the route nor your review values the company."
    )
    assert "Make none there, and read no DCF beside the route's value." in opening
    intro = _flat(_frontmatter(_read(SKILL))[1].split("## Before you start", 1)[0])
    assert (
        "Only where neither the route nor your review values the company does the secondary"
        " valuation stand in: a discounted cash flow from drivers you set, or from free cash flows"
        " you build part by part."
    ) in intro
    assert "standard discounted cash flow" not in _flat(_read(SKILL)).replace(
        "with `drivers`, the standard discounted cash flow, as the fallback", ""
    )
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


def test_every_item_is_refreshed_before_it_is_read(tmp_path: Path) -> None:
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
    # a start refused for another reason than a running refresh, by the refusals the server gives
    # (web/app.py `start_refresh`, the worker's, the run's and `effective_policy`'s; B-138), each
    # sentence read from the code: without a key or a worker the agent reads the stored snapshot;
    # under a stored setting the policy refuses, every read of the policy, `company` among them,
    # answers the same sentence (409, `settings_api.effective`), so the agent waits (the review)
    no_key = str(MissingKey("fmp")).split(": ", 1)[0]
    with closing(connect(tmp_path / "f.db")) as conn:
        migrate(conn)
        conn.execute("INSERT INTO settings VALUES ('gone_value', '1', '2026-11-15T00:00:00+00:00')")
        conn.commit()
        try:
            effective_policy(conn)
            stale = ""
        except ValueError as exc:
            stale = str(exc)
    assert stale.startswith("settings: gone_value: "), stale
    head, tail = stale.split(": ", 1)[0], stale.rsplit("; ", 1)[1]
    for words in (
        (
            f'When it is refused with "{no_key}: ..." (400), a server with no FMP key, which runs a'
            f' revalue only, or "{NO_WORKER}" (503), no refresh can start until the user acts.'
        ),
        (
            "Tell the user, go on with the stored snapshot, and write the price's date in section 9"
            " of the report. Skip the wait below and read `company(symbol)`."
        ),
        (
            f'When it is refused with "{head}: ...; {tail}" (400), a stored setting the policy file'
            " no longer accepts, every read of the policy answers the same sentence (409),"
            " `company` among them."
        ),
        (
            "Tell the user, and wait until they reset the setting, as for a server that is not"
            " running. Then start the refresh again."
        ),
    ):
        assert words in three, words
    assert "When it is refused for another reason" not in three
    entry = _tool_entry("refresh_start")
    for words in (f'"{no_key}: ..." (400)', f'"{head}: ...; {tail}" (400)', f'"{NO_WORKER}" (503)'):
        assert words in entry, words
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
    # in section 8 a term stands only in a bracket that names one term, a longer bracketed term's
    # part counting as bracketed ("runway" in "(the runway return)") and a term in any other
    # bracket as bare (B-138); each term is named in brackets once at most
    assert _bare_terms("its inputs (the mechanical value), its return (the runway return)") == []
    assert _bare_terms("the value rests on growth (its moat is wide)") == ["moat"]
    valuation = sections["Valuation"].lower()
    assert _bare_terms(valuation) == []
    named = [m[1] for m in BRACKET.finditer(valuation)]
    for term in TERMS:
        count = sum(1 for n in named if re.fullmatch(_term(term), n))
        assert count <= 1, term
        if term in ("belief", "runway return", "mechanical value", "reviewed value"):
            assert count == 1, term
    # outside section 8 no term of the table appears: the shape, the other sections, the
    # decisions, the kill criteria and the news items; the mode names stand as given, so
    # "valuation review" holds no "review" while "the review" does (B-138)
    assert _terms_in("This valuation review reuses the full report of 3 Oct 2026.") == []
    assert _terms_in("The review moved the value.") == ["review"]
    others = [text for heading, text in sections.items() if heading != "Valuation"]
    for text in [shape, *others, *decisions, *shown]:
        assert _terms_in(text) == [], text[:80]
    # the mechanical value is the value with no override at all, an earlier report's included,
    # and the reviewed value the value under every applied one (the final review of plan 5)
    for path in (REGISTER, TEMPLATE):
        assert "this report's changes" not in _flat(_read(path)), path.name


def test_the_report_is_read_as_its_reader_before_it_is_submitted() -> None:
    """Spec 14 step 12 (plan 5, B-134): before `report_submit`, the agent reads the report once as
    its reader, someone who has never seen Fairband; it rewrites every sentence that needs the
    Methodology page to follow, by the register's "The words a report writes"; and it reads the
    summary alone, which must stand on its own."""
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


def test_the_agent_reads_the_overrides_the_route_no_longer_reads() -> None:
    """Spec 2026-11-14 8: the system drops an override the row's route no longer reads, at a
    refresh that moves the phase and when a `phase` override is added, replaced or dropped, with
    the reason as the server words it; a company with no phase keeps its overrides. The answers of
    `override_add` and `override_drop` name such drops under `dropped`, which the agent reads
    after each of the three writes of a `phase` override, a first one included (Task 6's review,
    fix round 1)."""
    skill = _flat(_read(SKILL))
    reason = OFF_ROUTE.format(route="<route>")
    assert reason == "the <route> route does not read the input"
    for words in (
        "An override the row's route does not read drops too.",
        (
            "When a refresh moves the phase, or you add, replace or drop a `phase` override, the"
            f' system drops each override only the old route read: "{reason}"'
        ),
        "A company the refresh leaves with no phase keeps its overrides.",
        "After you add, replace or drop a `phase` override, read `dropped` in the answer",
        "An applied override answers `{override, review, bridge, dropped}`",
    ):
        assert words in skill, words
    assert "you drop or replace a `phase` override" not in skill
    for name in ("override_add", "override_drop"):
        entry = _tool_entry(name)
        assert "`{override, review, bridge, dropped}`" in entry, name
        assert "`{id, tag, reason}`" in entry or "as `override_add`'s" in entry, name
    assert "(a `phase` override, new or replacing another, can move the route)" in _tool_entry(
        "override_add"
    )


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


def test_the_agent_weighs_the_marginal_return_against_the_return_at_a_constant_margin() -> None:
    """The founder's ruling of 2026-11-15 (theme 2 of the research round): the engine keeps the
    five-year marginal return and records the same return at a constant margin; step 8 tells the
    agent to read both where the marginal is the measure, what a margin gain that took no new
    capital looks like, and where the marginal stands."""
    eight = _flat(_steps(_frontmatter(_read(SKILL))[1])[8])
    for words in (
        "On Mature Growth and Mature Stable, one reading of the return has no flag.",
        (
            "(`intermediates/runway_return/used` is `marginal`), read "
            "`intermediates/runway_return/constant_margin` beside it"
        ),
        "so a margin that rose on sales the company already had reads as a return on new capital",
        (
            "Costs cut, or prices at a cycle's peak, do not repeat on new capital: set "
            "`return.runway` at the constant-margin figure, or between the two, with the evidence"
        ),
        (
            "A mix that moved to a line with a higher margin, where the new capital went, is a return "
            "on that capital: the marginal stands"
        ),
        "Decide it in the `roic` judgment, and cite both figures.",
        "on a Wide row a figure below the Wide cap lowers the terminal return too",
    ):
        assert words in eight, words
    # the references name the figure, and the inputs' table says what the override also sets
    assert (
        "`runway_return/constant_margin`, the five-year marginal return at a constant margin"
        in (_flat(_read(CITATIONS)))
    )
    assert "cite both, `/runway_return/marginal` and `/runway_return/constant_margin`" in _flat(
        _read(TEMPLATE)
    )
    assert (
        "on a Wide row it also sets the terminal return, at most the Wide cap and never below the "
        "hurdle rate"
    ) in _flat(_read(SKILL))


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
                # a thin revenue step is not read (spec 2026-11-14 6.2)
                (
                    "The engine does not read a revenue step above `thin_revenue_step_max` "
                    "(50%) whose year has fewer than `analyst_min` revenue analysts "
                    "(`policy()`), or no count"
                ),
                "A step at or below 50% is read on any count",
                (
                    "that year's charge pays for its earnings step, so a `path.step_2` or "
                    "`path.step_3` moves it"
                ),
                "`charge/revenue_step_source` says `thin`",
                "your `revenue.step_2` or `revenue.step_3` still stands over the rule",
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
                # an EPS from a net income record backs the anchor too (spec 2026-11-14 9)
                "clear EPS or net income guidance record",
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
                # as amended at the build: the basis date, the earlier of the two dates
                "whose figures had not seen the split",
                "both its quote's date and the day its statements were fetched are on or after",
                "carries the figures of the one it repriced",
                "a refresh on the split's day before the US close has not seen it",
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
    assert "made on a snapshot fetched before the split" not in split
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
        # the override is the return in force on every row, so the Wide terminal return follows
        # it (method 4.7 and 14.4, the founder's ruling of 2026-11-15)
        (
            "On every row your `return.runway` is the return in force: on a Wide row the terminal "
            "return follows it, at most the Wide cap and never below the hurdle rate"
        ),
        "So a return you set below the Wide cap lowers the terminal return too.",
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
        # a record's money is in the currency the company states it in (spec 2026-11-15 9.6)
        "is in the currency the company states it in",
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
        # the whole-branch review's deferred minor 19: a euro record of a US company takes no `$`
        (
            "and every figure of a company that reports in US dollars but a record it states in"
            " another currency."
        ),
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


def test_a_net_income_guidance_backs_the_ntm_eps_over_the_count_the_eps_is_per() -> None:
    """Spec 2026-11-14 9, as changed on the review of Task 7: a guidance record may hold
    `net_income`, the net income that belongs to the shareholders, as the EPS does; a total with a
    minority's share is recorded verbatim with nothing added, backs no anchor, and the report says
    so; a company that guides net income alone backs `earnings.ntm` with that record, and `new` is
    the `derive` ratio of its midpoint over the count the company's EPS is per: the reported count
    on most rows, an applied `shares.diluted` that corrects the count of the same shares, the
    reported count where it adds an Up-C's units ($100M over 100M Class A shares is $1.00, not
    $0.25 over 400M), never a count that holds committed shares; the server checks the record,
    not the figure. The tools reference lists the metric, the citations reference reads its
    figures as totals, and the template's section 8 cites the division."""
    skill = _flat(_read(SKILL))
    guidance = skill[skill.index("## Guidance ") : skill.index("## Overrides ")]
    for words in (
        (
            "`metric`: `revenue`, `eps`, `net_income`, `operating_margin`, `free_cash_flow`,"
            " `capex`, `revenue_growth` or `eps_growth`."
        ),
        "`net_income` is the net income that belongs to the company's shareholders, as its EPS is.",
        (
            "Where a company guides a total that includes a minority's share, record it with the"
            " sentence verbatim and nothing added: that record does not back `earnings.ntm`, and"
            " the report says so where it cites the record."
        ),
        "For a fiscal-year revenue, EPS or net income record on the `gaap` basis",
        (
            "A company that guides net income alone backs `earnings.ntm` with that record, a"
            " `gaap` one for the base year. `new` is then the `derive` `ratio` of the record's"
            " midpoint over the count the company's EPS is per, the count its shareholders' net"
            " income is shared among. On most rows that is the reported count,"
            " `snapshot:<id>/inputs/shares_diluted`. Where an applied `shares.diluted` corrects"
            " the count of the same shares (the vendor's figure was wrong or stale, or it left out"
            " a class of common stock that shares the earnings), divide by that figure, cited"
            " through its bridge line, `review:<id>/bridge/<n>/new`. Where it adds an Up-C's"
            " units, whose share of the earnings is a minority's, divide by the reported count:"
            " the EPS is a Class A share's. With 100M Class A shares and 300M units, a guided"
            " Class A net income of $100M gives $100M ÷ 100M = $1.00 a share, not"
            " $100M ÷ 400M = $0.25. Never divide by a count that holds committed shares"
            " (`shares.committed`). The server checks the record, not the figure."
        ),
    ):
        assert words in guidance, words
    # the earlier rule, which had the agent add a note to the verbatim sentence
    assert "say so in the record's `text`" not in guidance
    table = _table(
        _read(SKILL), ("Tag", "Routes that read it", "The input", "Takes, the ends included")
    )
    ntm = _flat(" ".join(table["`earnings.ntm`"]))
    assert (
        "from a clear full-year EPS guidance, or a net income one over the count the company's EPS"
        ' is per (see "Guidance")'
    ) in ntm
    assert "(`eps` or `net_income` for `earnings.ntm`, `revenue` for `revenue.ntm`)" in skill
    entry = _tool_entry("guidance_add")
    assert "for a fiscal-year revenue, EPS or net income figure on the `gaap` basis" in entry
    tools = _flat(_read(TOOLS))
    assert (
        "the `metric` is `revenue`, `eps`, `net_income`, `operating_margin`, `free_cash_flow`,"
        " `capex`, `revenue_growth` or `eps_growth`"
    ) in tools
    citations = _table(_read(CITATIONS), ("Ref", "The stored value", "Unit"))
    guided = _flat(" ".join(citations["`guidance:<id>/low`, `/high`, `/midpoint`, `/step`"]))
    for words in (
        "a `gaap` fiscal-year revenue, EPS or net income record",
        "currency for revenue, net income, free cash flow and capex",
    ):
        assert words in guided, words
    # section 8 shows the division, so the reader sees how the guided total became the EPS
    assert (
        "Where the NTM EPS came from a net income record, the sentence cites the division too,"
        " `derived:<id>`."
    ) in _flat(_read(TEMPLATE))


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
    # the quarter's figures, its operating margin a cell of the quarters table (spec 2026-11-15
    # 6.4), and the free cash flow's derivation (the fix round of Task 6)
    for words in (
        "The quarter's figures still come from `quarters`.",
        (
            "The operating margin is the quarters table's cell,"
            " `table:<symbol>/quarters/operating_margin/2026-Q3`, which `financial_tables` gives"
            " under `quarters`."
        ),
        (  # the table may hold no such cell (spec 2026-11-15 6.4; the Task 9 review)
            "Where the table has no such cell (no stored period, the quarter not yet stored, or a"
            " line missing), the operating margin is the `derive` `ratio` of the quarter's"
            " operating income to its revenue."
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
    # the final review's C.4: a cell is at its sheet's scale; since spec 2026-11-15 7.5 it is
    # scaled by a fixed number before it meets a figure in full units, never recorded as a finding
    for text in (four, citations):
        for words in (
            "A filing cell holds the number at its sheet's scale, so scale the cell first",
            (
                "before it meets a figure in full units (a `fact:` or a `table:` figure), or a cell"
                " of a sheet with another scale"
            ),
            (
                "the `derive` `product` of the cell and its sheet's scale, `number:1000000` for"
                " `$ in Millions`"
            ),
            "never record it as a finding in full units to compute with it",
            # the whole-branch review's deferred minor 20: a row the title scales apart
            (
                'A row the title scales apart takes its own scale: in a sheet "in Millions, except'
                ' Per Share data" a figure a share is in full units, and a count of shares may be in'
                " thousands, as the title says."
            ),
        ):
            assert words in text, words
        assert "do not `derive` a cell with a figure in full units" not in text
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


def test_the_playbook_says_what_the_tables_the_charts_and_the_export_show() -> None:
    """Spec 2026-11-15 6, 7, 8 and 12 (the report reader's plan, Task 9): the template says what
    section 4's charts draw after the fiscal years, and that section 5 draws the quarters beside
    the agent's table of the quarter, which the agent still writes; the quarter's operating margin
    is a cell of the quarters table; the `table:` row names the periods a cell takes and what each
    cell is; the `financial_tables` entry names the columns, their kinds and the quarters; the
    playbook quotes Appendix A's sentences for no secondary valuation and the export's opening
    lines as the server writes them; and the split note says what Appendix A shows of an override
    a split rescaled."""
    template = _flat(_read(TEMPLATE))
    charts = template.split("### The charts", 1)[1].split("## The summary page", 1)[0]
    # section 9's first chart, as the export titles it
    band = BAND_TITLE[0].lower() + BAND_TITLE[1:]
    for words in (
        "in section 5 the revenue, the operating margin and the EPS by quarter",
        f"in section 9 {band} and the P/E history with its average lines",
        "Section 4's charts show the fiscal years, then, for the lines that have them,",
        "the twelve months to the newest stored period in grey",
        "the analysts' estimate years as outlined bars",
        # the EPS estimates' basis (the whole-branch review's I2)
        (
            "The EPS estimates are on the analysts' own basis, which can leave out items the"
            " reported EPS includes, such as stock pay: where a step from a reported EPS to an"
            " estimate matters to what you write, say which basis each figure is on."
        ),
        (
            "Section 5's charts do not replace your table of the quarter against the expectations:"
            " write that table still."
        ),
    ):
        assert words in charts, words
    # the quarter's operating margin is a cell to cite, in the template's section 5 and in step 5,
    # which keeps the `derive` for a quarter the table holds no cell of
    steps = {n: _flat(text) for n, text in _steps(_frontmatter(_read(SKILL))[1]).items()}
    for text in (template, steps[5]):
        assert "`table:<symbol>/quarters/operating_margin/" in text
    # a cite's period may be an estimate year, in the cite's keys and in the template's example
    assert (
        "the period the text claims, a fiscal year (`2025` or `FY2025`), a quarter (`2026-Q2`),"
        " `ttm` or an estimate year (`2026E`)."
    ) in _flat(_read(CITATIONS))
    assert "With the period it claims, a fiscal year, a quarter, `ttm` or an estimate year" in (
        template
    )
    # the periods a `table:` ref takes, what each cell is, and the cite of an estimate cell
    citations = _read(CITATIONS)
    cell = _table(citations, ("Ref", "The stored value", "Unit"))[
        "`table:<symbol>/<table>/<row>/<period>`"
    ][0]
    for words in (
        "a fiscal year (`2025`), that year's figure",
        "`ttm`, the trailing twelve months' figure",
        "a year and `E` (`2026E`), the analysts' estimate for that year",
        "on the table `quarters`, a stored period (`2026-Q3`), that period's figure",
        "Cite an estimate cell of revenue or EPS by the `estimate:` ref the read gives.",
        "may give its period as `2026E` or `2026`",
    ):
        assert words in cell, words
    assert "`FY2025` reads as `2025`, and `2026E` as `2026`." in _flat(citations)
    # the read: each table's columns with their kinds, and the quarters beside the six
    tables = _tool_entry("financial_tables")
    assert "five-year" not in tables
    for words in (
        "under `tables`",
        f"under `{QUARTERS}`",
        "`columns`, each `{period, kind, label}`",
        "`{period, value, unit, ref, note}`",
        "`ttm`",
        "`2026E`",
        "`2026-Q3`",
        "`estimate:` ref",
    ):
        assert words in tables, words
    for name in TABLES:
        assert f"`{name}`" in tables, name
    for kind in get_args(Kind):
        assert f"kind `{kind}`" in tables, kind
    # Appendix A's sentence for no secondary valuation, as the server writes it (spec 7)
    route = "No secondary valuation: Fairband's own valuation gives the company a value"
    review = "No secondary valuation: the review gives the company a value"
    for text in (steps[12], template):
        for sentence in (route, review):
            assert f'Appendix A says "{sentence}"' in text, sentence
    for path in sorted(PLAYBOOK.rglob("*.md")):
        text = _flat(_read(path)).lower()
        for old in (
            "secondary valuation: the route values",
            "secondary valuation: the review values",
        ):
            assert old not in text, (path.name, old)
    # the export's opening lines and its order, in the server's words (spec 7 and 9)
    summary = template.split("## The summary page", 1)[1].split("```", 1)[0]
    rests = resting_words(date(2026, 11, 4), date(2026, 11, 4), date(2027, 1, 27))
    reused = f"Reuses the full report of {day_words(date(2026, 11, 3))}."
    for words in (
        "the date in words",
        f'Its second reads "Stance: hold. {rests}"',
        f'"{reused}"',
        "the sections, Appendix A, Appendix B and, last, the references",
    ):
        assert words in summary, words
    assert "the snapshot and its price date" not in template
    # an override a split rescaled: Appendix A shows the figures in force and the scaling's words
    check = "Check the figure in force against the new basis before you publish."
    shown = (
        "Appendix A shows such an override's old and new figures in force, both on the new basis,"
        " with the note's words: \"entered as $30.00 a share before the 2-for-1 split of 27 Jan"
        ' 2027".'
    )
    assert 0 <= steps[8].index(check) < steps[8].index(shown)


def test_the_playbook_s_phrases_state_the_method_as_it_runs() -> None:
    """Spec 2026-11-15 10 (B-138): the register's hurdle rate is one rate for every company,
    restated for a company in another currency (method 4.1, 7.5); the belief is the rate growth
    eases down to over five years and holds to the runway's end, as the overrides table says
    (5.4, 5.5); the validity window says what stays valid and that the value ages after two-thirds
    of it (4.10); an override's reason may use the record words, which Appendix A shows; "stage"
    names the phase alone, and the Dickinson stage is a second reading of the life cycle (3.7)."""
    register = _read(REGISTER)
    rows = _table_rows(register, ("Term", "Write instead"))
    assert rows["hurdle rate"] == (
        "the yearly return investors require of any company's shares: one rate for every company,"
        " restated in the currency of a company that does not report in US dollars; future cash is"
        " discounted to today at this rate"
    )
    # the fade's length is a setting and the runway cuts the path (method 4.1, 4.8, 5.5)
    assert rows["belief"] == (
        "the growth rate the value assumes after the analysts' forecast years: where the analysts'"
        " last year grows faster, growth eases down toward this rate in equal steps, over five"
        " years at the defaults, then holds at it until it settles to the long-run rate; where"
        " growth settles to the long-run rate sooner, the easing stops there"
    )
    # the fallback and the aging share are settings, and a known report date on or before the
    # data's date gives the fallback too (method 4.1, 4.10)
    assert rows["validity window"] == (
        "the time the value stays valid on the data on file: until the company's next earnings"
        " report when one is due after the data's date, else for a fixed time after that date; past"
        " a share of that time the value is aging, and past its end it has expired. At the"
        " defaults the fixed time is about three months and the share two-thirds"
    )
    assert rows["Dickinson stage"].startswith(
        "a second reading of the company's life cycle, one of Introduction, Growth, Mature,"
        " Shake-out or Decline, from whether the last fiscal year's cash from operations,"
    )
    assert rows["phase"].startswith("the company's stage in its life cycle:")
    flat = _flat(register)
    for words in (
        (
            "They are for your records, your tool calls and Appendix A. An override's reason may"
            " use them too, since Fairband shows it verbatim in Appendix A."
        ),
        (
            'The word "stage" names the phase alone: "Fairband puts the company in its Mature'
            ' Growth stage". Write the Dickinson stage as the second reading of the life cycle, so'
            " a reader does not take it for a second stage."
        ),
    ):
        assert words in flat, words
    table = _table(
        _read(SKILL), ("Tag", "Routes that read it", "The input", "Takes, the ends included")
    )
    assert table["`growth.belief`"][1] == (
        "the belief: the growth of each year from 4 to the runway's end, save where the year-3"
        " growth is higher: then years 4 to 3 + `fade_years` (4 to 8 at the defaults) fade from it"
        " down to the belief in equal steps, and a runway that ends sooner ends the path mid-fade"
    )
    assert "before the fade to the long-run rate" not in _read(SKILL)


def test_step_5_reads_a_margin_s_change_in_points_and_the_cells_no_consensus_fills() -> None:
    """The reviews of the report reader's plan (Task 10), as the controller ruled: the store holds
    no consensus for the quarter's operating margin or free cash flow, so their consensus and
    surprise cells stay empty, and a company's own figure never stands under the analysts'
    average; a quarter the company guided on the actual's basis is set against the guided midpoint
    in one sentence after the table, named as the company's guidance, and a figure guided on
    another basis is not; the margin's change is a `difference` of two margins cited in points,
    not a `growth`, which is a relative change."""
    five = _flat(_steps(_frontmatter(_read(SKILL))[1])[5])
    for words in (
        (
            "The store holds no consensus for the operating margin or the free cash flow, so their"
            " consensus and surprise cells stay empty: a company's own figure never stands under the"
            " analysts' average."
        ),
        (
            "Where the company guided the quarter on the actual's basis, a `gaap` record, one"
            " sentence after the table sets the actual against the record's midpoint"
            " (`guidance:<id>/midpoint`) and names it the company's guidance."
        ),
        (
            "A figure guided on another basis, an adjusted margin against the reported one, is not"
            " set against the actual."
        ),
        (
            "The operating margin's change, on the year or against a guided margin, is a"
            " `difference` of two margins, cited in points (`1.5 percentage points`): a `growth` of"
            " one margin over another is a relative change, not a margin's change."
        ),
    ):
        assert words in five, words
    assert "Their consensus cell holds a guidance record's midpoint" not in five


def test_the_template_s_words_state_what_each_figure_is() -> None:
    """Spec 2026-11-15 10 (B-138): the forward P/E, the price over the NTM EPS (method 5.9), sits
    beside the belief and does not rest on it; the Driver column names the inputs by terms whose
    phrases the register gives; the clean P/E is glossed in words a reader follows (5.9); section
    9 gives the price's date where step 3's refresh did not refresh the company; the Dickinson
    stage is a second reading of the life cycle, not a stage (3.7)."""
    template = _flat(_read(TEMPLATE))
    assert "the growth rate it rests on" not in template
    assert (
        "| Mature Growth | the forward P/E, and beside it the growth rate the value assumes after"
        " the analysts' forecast years, the belief (`snapshot:<id>/inputs/belief`), and the PEG,"
        " the forward P/E over that rate |"
    ) in template
    rows = _table_rows(_read(REGISTER), ("Term", "Write instead"))
    drivers = template.split('"The words a report writes"): ', 1)[1].split(" |", 1)[0]
    named = [name.removeprefix("the ") for name in re.split(r", | or ", drivers)]
    assert named == [
        "consensus",
        "belief",
        "held rate",
        "target margin",
        "runway return",
        "sales-to-capital",
        "moat",
    ]
    for name in named:
        assert name in rows, name
    assert "the method's earnings" not in template
    assert (
        "the clean P/E (the price over the trailing earnings a share without one-time items)"
    ) in template
    nine = template.split("### Section 9", 1)[1].split("### The charts", 1)[0]
    assert (
        "Where step 3's refresh did not refresh the company, give the price's date beside it, the"
        " snapshot's `price_date` written as `4 Nov 2026`: the price is that day's close."
    ) in nine
    assert (
        "the Dickinson stage (a second reading of the life cycle, Introduction, Growth, Mature,"
        " Shake-out or Decline, from the signs of the last fiscal year's three cash flows)"
    ) in template
    assert "the life-cycle stage, Introduction" not in template


def test_the_template_example_holds_together() -> None:
    """Spec 2026-11-15 10 (B-138): the example's figures agree with each other. The bridge's
    lines add up from the value before the changes to the inputs to the value after them; the
    price sits against the value as the growth the price needs sits against the belief, before the
    belief's change and after it (method 5.7: at the implied growth the value equals the price);
    the levels are the value's at the moat's margin of safety and the fair band (4.10); the grid
    holds the value in force. Its Valuation names the Dickinson stage with its cite, in short
    sentences; it gives "thesis" and the three words of likelihood their meaning at first use;
    its Driver cells are the register's phrases; the Summary says what is valid until when."""
    template = _read(TEMPLATE)
    example = _example(template)
    written = {s["heading"]: _written(s["parts"]) for s in example["sections"]}
    cites = {
        part["ref"]: part["cite"]
        for section in example["sections"]
        for part in section["parts"]
        if not isinstance(part, str)
    }

    def number(ref: str) -> float:
        parsed = parse_cite(cites[ref])
        assert parsed is not None, ref
        return parsed[0]

    price, mechanical, value = (
        number(r) for r in ("snapshot:412/price", "snapshot:412/value", "review:89/value")
    )
    lines = sorted(
        int(m[1]) for ref in cites if (m := re.fullmatch(r"review:89/bridge/(\d+)/delta", ref))
    )
    assert abs(mechanical + sum(number(f"review:89/bridge/{n}/delta") for n in lines) - value) < 1
    belief = next(n for n in lines if f"review:89/bridge/{n}/old" in cites)
    old, new = number(f"review:89/bridge/{belief}/old"), number(f"review:89/bridge/{belief}/new")
    before = mechanical + sum(number(f"review:89/bridge/{n}/delta") for n in lines if n < belief)
    implied = number(next(ref for ref in cites if ref.endswith("/intermediates/implied_growth")))
    assert (price < before) == (implied < old), (price, before, implied, old)
    assert (price < value) == (implied < new), (price, value, implied, new)
    policy = load_policy()
    safety = policy.margin_of_safety[cites["snapshot:412/inputs/moat_class"]]
    low, high = policy.fair_band
    for level, factor in (("buy", 1 - safety), ("fair_low", low), ("fair_high", high)):
        assert abs(number(f"review:89/levels/{level}") - value * factor) < 1, level
    cells = [number(ref) for ref in cites if re.fullmatch(r"sensitivity:\d+/\d+/\d+", ref)]
    assert min(cells) < value < max(cells)
    # the Valuation names the Dickinson stage and cites it, in short sentences of one bracket each
    valuation = written["Valuation"]
    assert any(ref.endswith("/phase/dickinson") for ref in cites)
    assert "(the Dickinson stage)" in valuation
    assert "The price needs growth of" not in valuation
    for sentence in re.split(r"(?<=\.)\s+(?=[A-Z])", valuation):
        assert len(sentence.split()) <= 30 and sentence.count("(") <= 1, sentence
    # the thesis and the three words of likelihood, each with its meaning at first use
    summary = written["Summary"]
    assert summary.startswith(
        "Stance: hold.\n\nThe thesis, the report's own view of the business: customers stay"
    )
    call = written["The last earnings call"]
    for words in (
        "The multi-year contracts are probable, more likely than not on the evidence:",
        "The price list is plausible, believable on the evidence but not yet likely:",
        "Payroll is possible, since nothing rules it out, and moves no figure.",
    ):
        assert words in call, words
    # each Driver cell is the register's phrase for the input it would move
    phrases = _table_rows(_read(REGISTER), ("Term", "Write instead")).values()
    heads = [re.split(r"[:;,]", phrase)[0] for phrase in phrases]
    claims = call.split("| Claim | Evidence | Driver | Test |", 1)[1].split("\n\n", 1)[0]
    drivers = [_cells(line)[2] for line in claims.strip().splitlines()[1:]]
    assert len(drivers) == 3
    for driver in drivers:
        assert any(driver.lower().startswith(head) for head in heads), driver
    # what is valid until when, in the Summary and its shape
    valid = "The value is valid until 27 Jan 2027, the date of the next earnings report."
    assert summary.endswith(valid)
    shape = _shape(template)
    assert shape.strip().endswith(valid)
    assert _flat(shape.split("Reasons for:", 1)[0]) == _flat(summary.split("Reasons for:", 1)[0])
    # the forward P/E sits beside the growth assumed, and the hurdle rate is every company's
    nine = written["Price and multiples"]
    beside = (
        "The value assumes growth of 9.0% a year after the analysts' forecast years, and the"
        " forward P/E is read beside that rate."
    )
    assert beside in nine and "rests on growth" not in nine and "Beside it," not in nine
    # the reviews of Task 10: the hold's reason against a price below the value, the stage named,
    # and one phrase for the belief in the judgments as in the Valuation
    assert (
        "The price is below the value, but not far enough below it to buy: rivals sell close"
        " substitutes, so the discount a buyer asks for is wide, and churn under the new prices is"
        " not yet known."
    ) in written["The thesis"]
    assert "fair for now" not in written["The thesis"]
    assert "nothing in the figures puts the Mature Growth stage in doubt" in valuation
    decisions = [j["decision"] for j in example["judgments"]] + [written["Key judgments"]]
    for text in decisions:
        assert "the analysts' years" not in text, text
    assert (
        "The growth rate assumed after the analysts' forecast years rose"
        in (written["Key judgments"])
    )
    # the quarter's table has the four lines: the margin and the free cash flow with their
    # consensus and surprise cells empty, the margin's change on the year a difference in points
    table = call.split("| | The quarter |", 1)[1].split("\n\n", 1)[0]
    rows_of = {cells[0]: cells[1:] for cells in map(_cells, table.splitlines()[2:])}
    assert list(rows_of) == ["Revenue", "EPS", "Operating margin", "Free cash flow"]
    for line in ("Operating margin", "Free cash flow"):
        assert rows_of[line][2:] == ["", ""], line
    for period in ("2026-Q4", "2025-Q4"):
        assert f"table:EXMP/quarters/operating_margin/{period}" in cites, period
    change = next(
        part
        for section in example["sections"]
        if section["heading"] == "The last earnings call"
        for part in section["parts"]
        if not isinstance(part, str) and part["cite"].endswith("percentage points")
    )
    margins = [number(f"table:EXMP/quarters/operating_margin/{p}") for p in ("2026-Q4", "2025-Q4")]
    assert abs(number(change["ref"]) - (margins[0] - margins[1])) < 0.05
    assert "The operating margin rose 2.1 percentage points on the year." in call
    # the sentence on the EPS guidance in the register: no method term, no bracket for
    # another kind of company (the re-review of Task 10; method 14.9, SKILL.md's Guidance)
    assert (
        "The valuation takes the EPS guidance. Fiscal 2027 holds the next four quarters, so"
        " its midpoint replaces the analysts' average estimate as the earnings the value"
        " starts from."
    ) in call
    assert "base year" not in call and "half-years" not in call
    hurdle = "the yearly return of 9.0% that investors require of any company's shares."
    assert hurdle in written["Industry and competition"]


def test_the_skill_s_lines_fit_the_page() -> None:
    """The reviews of the report reader's plan (Task 10): every line of `SKILL.md` but the
    frontmatter's and a table's row, and every line of `reference/tools.md` but a table's row, is
    at most 100 characters, as the rest of the prose is wrapped; the note on `split-pending` held
    one of 146, and the `company` entry and `report_submit`'s signature in the tool list ones of
    114 and 105."""
    _, body = _frontmatter(_read(SKILL))
    for text in (body, _read(TOOLS)):
        long = [line for line in text.splitlines() if len(line) > 100 and not line.startswith("|")]
        assert long == [], long


def test_a_hold_says_why_the_price_calls_for_neither_buying_nor_trimming() -> None:
    """The re-review of Task 10: a hold's price can stand below or above the range of prices
    close to the value, so the template and step 9 ask a hold why the price calls for neither
    buying nor trimming, as step 11 reads the price against the buy and the trim levels."""
    nine = _flat(_steps(_frontmatter(_read(SKILL))[1])[9])
    template = _flat(_read(TEMPLATE))
    assert (
        "- a hold says why the price calls for neither buying nor trimming, and what the view waits"
        " for;"
    ) in nine
    assert (
        "A hold says why the price calls for neither buying nor trimming, and what the view waits"
        " for."
    ) in template
    for text in (nine, template):
        assert "why the price is fair" not in text


def test_a_fixed_number_is_arithmetic_never_a_figure_you_chose() -> None:
    """Spec 2026-11-15 7.5 and the controller's ruling 1 on Task 1: the `derive` entry gives the
    form `number:<n>`, the server's list, its two refusals in the server's words and the unit
    table; step 10 and the citations give the same recipes (a complement, an average, a change of
    sign, a filing cell scaled before it meets a figure in full units, a PEG as two ratios) and the
    rule that a fixed number is arithmetic, never a figure the agent chose; the cycle gap's half
    takes `number:2`; the template computes the PEG it once said was not available; and no file
    teaches a percent times 100 as points."""
    assert NUMBERS == {*range(13), 52, 100, 365, *(10**k for k in range(3, 13))}
    assert (NUMBER_FORM, KILL_FORM) == ("number", "kill")
    rule = (
        "A fixed number is a number of arithmetic, never a figure you chose: the server takes no"
        " other, and a multiple, a rate or a threshold you assume is not arithmetic."
    )
    derive = _tool_entry("derive")
    for words in (
        (
            "One operand may be a fixed number, `number:<n>` where a ref goes, `<n>` in digits"
            " alone, with no sign, separator, point or exponent: the whole numbers 0 to 12, then"
            " 52, 100, 365, 1000 and each further power of ten up to 1,000,000,000,000."
        ),
        f'"{FIXED_NUMBERS}, not <what was written>"',
        f'and so are two numbers in one derivation, "{NEEDS_A_FIGURE}"',
        # the whole-branch review's C1: a number in the tree, and the tree moves with a figure
        (
            "A derivation with a number anywhere in it, its own operands or those of a `derived:`"
            " operand, must move with a stored figure: one that keeps its value whatever its"
            " figures are, a figure times `number:0`, a number over a figure over itself, a figure"
            f' plus a number less the same figure, is refused, "{DEPENDS_ON_A_FIGURE}".'
        ),
        (  # the controller's ruling 8: an earlier derivation whose figures changed
            "Where it rests on an earlier derivation whose figures changed since, or are no"
            " longer on file, the words go on,"
            f' "{REDERIVE}": derive that one again from its refs.'
        ),
        "A refusal stores none of the call's derivations.",
        "| `sum`, `difference`, `product` with a number | the stored figure's unit |",
        "| `ratio` of a figure over a number | the figure's unit |",
        "| `ratio` of a number over a figure | none |",
        "| `growth`, `cagr` | percent |",
        (
            "A fixed number is a number of arithmetic, never a figure you chose: the recipes are in"
            " `SKILL.md`, step 10."
        ),
        "`growth` and `cagr` have no value from a base at or below zero.",
        (
            'A `kill:` ref is refused, "unresolved reference: kill:<id>": a threshold you chose'
            " enters no arithmetic."
        ),
    ):
        assert words in derive, words
    assert "one of them a fixed number, `number:<n>`" in _flat(_read(TOOLS))  # the record
    recipes = (
        "- a complement: the `difference` of `number:1` and a rate, such as 1 less the tax rate;",
        (
            "- an average: the `sum` of the figures (chained `sum` calls for more than two), then"
            " the `ratio` of that `derived:` id and their count, `number:2` for two;"
        ),
        "- a change of sign: the `difference` of `number:0` and the figure;",
        (
            "- a filing cell before it meets a figure in full units: the `product` of the cell and"
            " its sheet's scale, `number:1000000` for `$ in Millions`, a figure with no unit, as the"
            " cell has none;"
        ),
        (
            "- a PEG: the `ratio` of the P/E and the growth rate, a figure with no unit that is a"
            " hundred times the PEG, since the rate is a fraction; then the `ratio` of that"
            " `derived:` id and `number:100`."
        ),
    )
    ten = _flat(_steps(_frontmatter(_read(SKILL))[1])[10])
    arithmetic = _flat(_read(CITATIONS).split("## Your own arithmetic", 1)[1].split("\n## ")[0])
    scaled_apart = (  # the whole-branch review's deferred minor 20
        "as the cell has none; a row the title scales apart takes its own scale (a figure a share in"
        ' a sheet "in Millions, except Per Share data" is in full units, and a count of shares may'
        " be in thousands);"
    )
    for text in (ten, arithmetic):
        for words in (rule, *recipes, scaled_apart):
            assert words in text, words
    assert (
        "A derivation with a number anywhere in it, its own operands or those of a `derived:`"
        " operand, must move with a stored figure. One that keeps its value whatever its figures"
        " are is a number you chose passed off as a sourced one, and is refused,"
        f' "{DEPENDS_ON_A_FIGURE}": a figure times `number:0`, a number over a figure over itself, a'
        " figure plus a number less the same figure. A figure that is nought moves nothing, so a"
        " derivation of it with a number is refused in the same words: cite the figure itself."
    ) in arithmetic
    # a figure a filing states is still cited from its cell (spec 7.5's third bullet)
    assert (
        "A figure a filing states is still cited from its cell: a finding in full units is not the"
        " way to compute with it."
    ) in arithmetic
    # the cycle gap's half takes the fixed number; the workaround of a figure over itself goes
    skill = _flat(_read(SKILL))
    assert "Half is the `derive` `ratio` of the full gap and `number:2`." in skill
    assert "`derive` takes no constant" not in skill
    # the template's PEG, the two ratios, where it once said PEG was not available
    template = _flat(_read(TEMPLATE))
    nine = template.split("### Section 9", 1)[1].split("### The charts", 1)[0]
    for words in (
        (
            "The PEG is the forward P/E over the growth rate beside it, by two `derive` calls: the"
            " `ratio` of the forward P/E, `snapshot:<id>/intermediates/multiples/pe_forward`, and"
            " the growth rate, a figure with no unit that is a hundred times the PEG, since the rate"
            " is a fraction; then the `ratio` of that `derived:` id and `number:100`."
        ),
        "Cite the second, at the decimals you write (`3.75`).",
    ):
        assert words in nine, words
    # the controller's ruling 1: a percent times 100 stays a percent, so no file teaches it
    for path in sorted(PLAYBOOK.rglob("*.md")):
        text = _flat(_read(path))
        for old in ("PEG is not available yet", "takes refs only", "percent as points"):
            assert old not in text, (path.name, old)


def test_a_threshold_you_choose_goes_on_its_kill_criterion() -> None:
    """Spec 2026-11-15 8.3 and Task 3's review: a threshold the agent chooses goes on the kill
    criterion with `kill_criterion_add` before the report is written, is cited by `kill:<id>` in
    "Risks and kill criteria" alone, enters no arithmetic and is left out of the report's
    `killCriteria`, where it would be dropped without a word; a criterion of a report not
    published is retired; an event tied to a stored figure is still the better criterion where
    one serves. The citations' passage, the failures table, the skill's step 9 and rules, the
    template's section 11 row and its example say so, and the tools list the threshold."""
    citations = _flat(_read(CITATIONS))
    passage = citations.split("## A threshold you choose", 1)[1].split(" ## ", 1)[0]
    for words in (
        "A threshold you choose is not a fact, so it is never a finding",
        (
            "A reader can follow such a line to its source, so it is the better criterion where one"
            " serves."
        ),
        "Put the threshold on the kill criterion.",
        "`kill_criterion_add(symbol, text, threshold, unit, currency?)` before you write the report",
        (
            "Cite it as `kill:<id>` in Risks and kill criteria (section 11 of a full report, the"
            " ninth of a valuation review), and only there"
        ),
        "`derive` refuses it, so it enters no arithmetic",
        '"kill criterion <id>, a threshold the author chose"',
        "Leave the criterion out of the report's `kill_criteria`",
        "a threshold put there is dropped without a word",
        'retire the criterion with `kill_criterion_set(id, "retired", reason)`',
    ):
        assert words in passage, words
    assert KILL_SECTION == "Risks and kill criteria"
    failures = _table(_read(CITATIONS), ("`what`", "It means", "What to do"))
    assert (  # the whole-branch review's deferred minor 21: the stored figure first (spec 8.3)
        "Never record a threshold you chose as a finding: tie the event to a cited figure where one"
        " serves, else put it on its kill criterion and cite `kill:<id>` in Risks and kill"
        " criteria, or state it in words"
    ) in failures["`a number with no reference`"][1]
    unresolved = failures["`unresolved reference`"]
    for words in (
        '"number:100 is an operand of derive: cite the derivation"',
        f'"kill:12 is the author\'s own threshold: cite it in {KILL_SECTION}"',
    ):
        assert words in unresolved[1], words
    steps = {n: _flat(text) for n, text in _steps(_frontmatter(_read(SKILL))[1]).items()}
    for words in (
        (
            "Where the line is one you choose, record the criterion with its threshold before you"
            " write the report: `kill_criterion_add(symbol, text, threshold, unit, currency?)`"
        ),
        "Section 11 cites the threshold as `kill:<id>`, and only there; it enters no arithmetic.",
        "Leave such a criterion out of the report's `kill_criteria`",
        'If the report is not published, retire it with `kill_criterion_set(id, "retired", reason)`.',
    ):
        assert words in steps[9], words
    rules = _flat(_read(SKILL).split("## The rules", 1)[1].split("## Guidance", 1)[0])
    assert (
        "- A threshold you choose is never a finding: tie the event to a stored figure, cited,"
        " where one serves, else put it on its kill criterion and cite it as `kill:<id>` in section"
        " 11 alone (step 9), or state it in words (`reference/citations.md`)."
    ) in rules
    template = _read(TEMPLATE)
    row = _flat(_table(template, ("#", "Heading", "Mode", "What it holds"))["11"][2])
    assert (
        "Else record your threshold on the kill criterion with `kill_criterion_add` before you"
        " write the report, cite it here alone as `kill:<id>`, and leave that criterion out of"
        " `kill_criteria`"
    ) in row
    assert (
        "a criterion with a threshold you chose is recorded with `kill_criterion_add` before the"
        " report and left out of this list"
    ) in _flat(template)
    # the example cites one threshold, in section 11 alone, and its own list holds text alone
    example = _example(template)
    kills = [
        (section["heading"], part)
        for section in example["sections"]
        for part in section["parts"]
        if not isinstance(part, str) and part["ref"].startswith(f"{KILL_FORM}:")
    ]
    assert len(kills) == 1 and kills[0][0] == KILL_SECTION, kills
    assert "period" not in kills[0][1]  # a threshold has no period
    assert all(set(criterion) == {"text"} for criterion in example["kill_criteria"])
    # the tools: the add with its threshold, the read, the move's 409 and the report's list
    threshold = _refused(lambda: _require_figure(1.0, None, None, "a kill criterion's threshold"))
    add = _tool_entry("kill_criterion_add")
    for words in (
        "`threshold` and `unit` together, the unit one of a finding's",
        "cite the threshold as `kill:<id>` in Risks and kill criteria alone",
        "leave the criterion out of the report's `kill_criteria`",
        f'"{threshold}"',
    ):
        assert words in add, words
    assert "cited as `kill:<id>` in Risks and kill criteria alone" in _tool_entry("kill_criteria")
    already = '"kill criterion <id> is already <state>" (409)'
    assert already in _tool_entry("kill_criterion_set")
    tools = _flat(_read(TOOLS))
    assert "a superseded guidance record, a kill criterion moved to the state it is in)" in tools
    assert "text alone, so a threshold there is dropped without a word" in tools
    for path in sorted(PLAYBOOK.rglob("*.md")):
        text = _flat(_read(path))
        for old in ("a later piece of Fairband", "a question for the founder"):
            assert old not in text, (path.name, old)


def test_a_money_figure_is_recorded_in_the_currency_the_company_states() -> None:
    """Spec 2026-11-15 9.6: one rule in the three places that state it, step 3, the citations and
    the tools: a money figure is recorded in the currency the company states it in, with
    `currency` when that is not the reporting currency; `$` for a US-dollar figure and the code
    before a bare cite otherwise; converted with `product` and the rate before it sets an input or
    meets a statement, a derivation of it keeping its currency until then (the whole-branch
    review's I1); a third currency enters no arithmetic. The words "in the reporting currency
    as the company states it" go; the guidance step says a record in another currency takes none;
    the tools quote the currency's two refusals as the store words them."""
    rule = (
        "in the currency the company states it in",
        "when that is not the reporting currency",
        "`$` where it is in US dollars, and its code in the plain text before a bare cite otherwise",
        "the `derive` `product` of a US-dollar figure and `snapshot:<id>/inputs/fx_rate`",
        "a third currency, neither the reporting currency nor the US dollar",
        "enters no arithmetic with the company's figures",
    )
    three = _flat(_steps(_frontmatter(_read(SKILL))[1])[3])
    citations = _flat(_read(CITATIONS))
    tools = _flat(_read(TOOLS))
    for text in (three, citations, tools):
        for words in rule:
            assert words in text, words
    assert (
        "A money figure you record (a finding's value, a guidance record's low and high, a kill"
        " criterion's threshold) is in the currency the company states it in."
    ) in three
    # the check's own rule for a record, as the server words its detail
    assert (
        '"finding:812 reads TWD 1,000,000,000: write the number without $ and name TWD before it"'
    ) in citations
    # the whole-branch review's I1: a derivation of a record keeps its currency until its product
    # with the rate, so the agent converts first or keeps to figures in that currency
    assert (
        "Until then `derive` keeps it out of money arithmetic, and every derivation of it too: its"
        " quarter, its average with another, the record times `number:1`, each keeps its currency"
        " until its `product` with the rate. So convert it first, or keep to figures in its own"
        " currency."
    ) in three
    for words in (
        (
            "A derivation of it keeps its currency until that product, its quarter or its average"
            " among them, so convert first, or keep to figures in its own currency."
        ),
        (
            "stays out of money arithmetic until you convert it, and so does every derivation of"
            " it: its quarter (a `ratio` over `number:4`), its average with another record, the"
            " record times `number:1`, each keeps its currency until its `product` with the rate."
        ),
        (
            "convert so first, before you set an input from the record or set it against a"
            " statement, or keep to figures in its own currency."
        ),
    ):
        assert words in citations, words
    assert (
        "stays out of money arithmetic until you convert it, and so does every derivation of it,"
        " its quarter or its average among them"
    ) in _tool_entry("derive")
    assert "convert first, or keep to figures in its own currency." in _tool_entry("derive")
    guidance = _flat(_read(SKILL).split("## Guidance", 1)[1].split("## Overrides", 1)[0])
    for words in (
        "`guidance_add(symbol, metric, period, low, high, basis, as_of, text, source, currency?)`",
        (
            "Money in full, in the currency the company states it in, with `currency` when that is"
            " not the reporting currency (step 3)"
        ),
        # the whole-branch review's Minor 3 and deferred minor 18: the record names the currency,
        # and the growth is over the year before's line, the actual's
        (
            "Nor does a record that names a currency other than that of the year before's"
            " statement: convert its midpoint (step 3) and `derive` the `growth` of that over the"
            " year before's `fact:` line."
        ),
    ):
        assert words in guidance, words
    assert (
        "A record that names a currency other than that of the year before's statement has no step."
    ) in _tool_entry("guidance")
    for path in sorted(PLAYBOOK.rglob("*.md")):
        text = _flat(_read(path))
        for old in ("whose `currency` is not that of", "over the year's `fact:` line"):
            assert old not in text, (path.name, old)
    code = _refused(lambda: check_currency("usd", "currency")).split(", not ", 1)[0]
    money = _refused(lambda: check_currency("USD", "percent"))
    for words in (f'"{code}, not <what was written>"', f'"{money}"'):
        assert words in tools, words
    for name in ("finding_add", "guidance_add", "kill_criterion_add"):
        assert "`currency`" in _tool_entry(name), name
    for name in ("findings", "guidance", "kill_criteria"):
        assert "`currency`" in _tool_entry(name), name
    for path in sorted(PLAYBOOK.rglob("*.md")):
        text = _flat(_read(path))
        for old in (
            "in the reporting currency as the company states it",
            "in the reporting currency, as the company states them",
            "money in the company's reporting currency, as its statements are",
            "money in full in the reporting currency, as the statements are",
        ):
            assert old not in text, (path.name, old)


def test_the_playbook_reads_a_split_s_newest_year_a_late_close_and_a_kept_filing() -> None:
    """Spec 2026-11-15 10 and 11: the `segments` entry names `newestYear`, and step 4 sends the
    agent to the 10-K's segment note where a split's newest year is null or before the newest
    fiscal year (the whole-branch review's deferred minor 25), as the tool entry and the
    template's section 2 row do; step 5 and the template's section 5 state no move where the next
    trading day's close is not on file yet; the filing report is reused whatever its age, not for
    thirty days; and the reads that answer a company with no snapshot 404 say so (B-103 clause
    6)."""
    assert "`newestYear`, the newest fiscal year among its rows" in _tool_entry("segments")
    steps = {n: _flat(text) for n, text in _steps(_frontmatter(_read(SKILL))[1]).items()}
    assert (
        "Where a split's `newestYear` is null or is before the company's newest fiscal year"
        " (`financials`), the split is missing or ends early: read the 10-K's segment note instead,"
        " found with `filing_search` in the newest `FY` report and read with `filing_report`, and"
        " cite its cells."
    ) in steps[4]
    assert (
        "where a split's `newestYear` is null or is before the company's newest fiscal year, read"
        " the 10-K's segment note"
    ) in _tool_entry("segments")
    assert (
        "the 10-K's segment note where a split's `newestYear` is null or is before the newest"
        " fiscal year"
    ) in _flat(_read(TEMPLATE))
    late = (
        "Where no close is on file for the trading day after the call, state no move and say that"
        " the close is not on file yet."
    )
    assert late in steps[5]
    template = _flat(_read(TEMPLATE))
    section_5 = template.split("### Section 5", 1)[1].split("### Section 7", 1)[0]
    assert (
        "where no close is on file for that day yet, no move, and say that the close is not on file"
        " yet."
    ) in section_5
    tools = _flat(_read(TOOLS))
    assert "thirty days" not in tools
    assert (
        "A filing report, once stored, is reused whatever its age, since a filing does not change"
        " once filed"
    ) in tools
    assert "Its newest stored copy is reused without a limit" in _tool_entry("filing_report")
    assert (
        "404 a record that does not exist (and, to `company`, `estimates`, `price_history` and"
        ' `peers`, a company with no snapshot: "no snapshot for <symbol>")'
    ) in tools


def test_the_playbook_s_debt_rows_are_settled() -> None:
    """Spec 2026-11-15 12.2 and 12.3: the register's "Means" on snapshot, news item and work item
    are the brand book's words, the judgment row the register's own; the sales class is explained
    at its first use; a figure from a secondary analysis names that source and the report says
    the filing was not read; the skill reads a filing on the company's investor site where
    sec.gov refuses; the review log's stance is the one in force when the review was written."""
    with tarfile.open(DESIGN_SYSTEM, "r:gz") as archive:
        member = archive.extractfile(BRAND_BOOK)
        assert member is not None
        book = _table(member.read().decode("utf-8"), ("Use", "Not", "Means"))
    register = _table(_read(REGISTER), ("Use", "Not", "Means"))
    for term in ("snapshot", "news item", "work item"):
        assert register[term][1] == book[term][1], term
    assert register["judgment"][1].startswith("the record of one input decision")  # kept, filed
    # the sales class, explained in the paragraph of its first use
    body = _frontmatter(_read(SKILL))[1]
    first = next(p for p in body.split("\n\n") if "sales class" in p)
    assert (
        "The sales class is the size band of the company's trailing revenue in US dollars, one of"
        " the Base Rate Book's eleven; its 90th percentile is the yearly sales growth over five"
        " years that only one company in ten of that size beat."
    ) in _flat(first)
    finding = _flat(_read(CITATIONS).split("## A figure from outside Fairband", 1)[1])
    assert (
        "A figure you take from a secondary analysis (a broker's note, an article, a data site that"
        " quotes the filing) names that source in its finding, not the filing it quotes, and the"
        " report says that the filing itself was not read."
    ) in finding.split(" ## ", 1)[0]
    four = _flat(_steps(body)[4])
    assert (
        "Where sec.gov refuses the fetch, read the filing's text on the company's investor site."
    ) in four
    assert (
        "`stance`, the stance of the company's newest report when the review was written: a review"
        " your overrides write carries the stance of the report before yours, and one written"
        " before a company's first report carries none (`null`)."
    ) in _tool_entry("review_log")


def test_a_launch_test_answers_and_a_named_item_is_claimed_where_it_is_pending() -> None:
    """Spec 2026-11-16 agent launch, 11 and 7.4: before the steps, a part answers the first prompt
    of the Settings page's Test (``TEST_PROMPT``) with the sentence that the skill is loaded and one
    on whether the Fairband tools are connected, read from `identify` among the agent's tools, and
    does nothing else; in step 2 a request that names a work item, as a launched session's first
    prompt does (the default ``claude.prompt``), claims that item where it is pending, reading its
    state first since a claim by id takes an item over; it stops on an item claimed by any session
    but this one, unless the user asks for a takeover, since two sessions may share one model
    identifier; and it stops on an item done, declined, dropped or not in the list, claiming no
    other in its place."""
    front, body = _frontmatter(_read(SKILL))
    command = f"/{front['name']} "
    assert TEST_PROMPT.startswith(command)
    assert body.index("## A launch test") < body.index("## The steps")
    test = _flat(body.split("## A launch test", 1)[1].split("\n## ", 1)[0])
    request = TEST_PROMPT.removeprefix(command)
    assert (
        f"When the request is `{request}`, it is a test of the window that opened this session, not"
        " a request for research."
    ) in test
    assert (
        "Do not identify, do not claim an item, call no tool that writes, and do no research."
    ) in test
    assert 'Answer with the sentence "The Fairband research skill is loaded." and then one' in test
    assert (
        "one sentence that says whether the Fairband tools are connected, which you can tell from"
        " seeing `identify` among your tools."
    ) in test
    assert test.endswith("Then stop.")
    # step 2: the item a launched session's first prompt names, claimed only where it is pending
    two = _steps(body)[2]
    named = DEFAULTS["claude.prompt"].replace("{item}", "12").removeprefix(command)
    assert named == "work item 12"
    title, _, text = two.partition("\n")
    assert title == "Take the work item"
    paragraphs = [_flat(p) for p in text.strip().split("\n\n")]
    assert (
        "Do not take over an item that another agent has claimed unless the user asks."
    ) in paragraphs[0]  # the step's rule of today, kept
    assert paragraphs[1] == (
        f"When the request names a work item, as `{named}`, claim that item with `inbox_claim(12)`"
        " where it is pending. Read its state in the list first: a claim by id takes over a claimed"
        " item. Where it is already claimed, by any session but this one, say so and stop, unless"
        " the user asks you to take it over. Where it is done, declined, dropped or not in the"
        " list, say so and stop: do not claim another item in its place."
    )
    assert "another agent has claimed it" not in paragraphs[1]
    assert "naming a claimed item takes it over" in _tool_entry("inbox_claim")


def _refused(call: Callable[[], object]) -> str:
    """The sentence ``call`` is refused with, a ``ValueError``'s."""
    try:
        call()
    except ValueError as exc:
        return str(exc)
    raise AssertionError("not refused")


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
    """The tools ``reference/tools.md`` lists, one entry each, ``- `name(argument, optional?)` ``,
    a signature on one line or wrapped over the next, as ``report_submit``'s is."""
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


def _written(parts: list[Any]) -> str:
    """A section's text as the reader sees it, each cite written in."""
    return "".join(part if isinstance(part, str) else part["cite"] for part in parts)


def _terms_in(text: str) -> list[str]:
    """The terms of ``TERMS`` that ``text`` holds, the two mode names left out: they stand as
    given, so "valuation review" holds no "review", while "the review" does."""
    plain = text.lower()
    for mode in MODES:
        plain = re.sub(rf"\b{_term(mode)}\b", " ", plain)
    return [term for term in TERMS if _has(term, plain)]


def _bare_terms(text: str) -> list[str]:
    """The terms of ``TERMS`` that section 8's ``text`` holds outside the brackets that name one:
    a bracket that holds exactly one term, "the" before it allowed. A term inside such a bracket
    is bracketed, "runway" in "(the runway return)" too; a term inside any other bracket is bare,
    "moat" in "(its moat is wide)"."""
    lower = text.lower()
    brackets = [
        m.span()
        for m in BRACKET.finditer(lower)
        if any(re.fullmatch(_term(term), m[1]) for term in TERMS)
    ]
    return [
        term
        for term in TERMS
        if any(
            not any(a < m.start() and m.end() < b for a, b in brackets)
            for m in re.finditer(rf"\b{_term(term)}\b", lower)
        )
    ]


def _shape(text: str) -> str:
    """The summary page's shape: the fenced block after ``## The summary page``."""
    after = text[text.index("## The summary page") :]
    return re.search(r"^```\n(.*?)^```", after, re.MULTILINE | re.DOTALL)[1]
