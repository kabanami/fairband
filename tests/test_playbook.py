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

from fairband.engine.overrides import NO_GUIDANCE, anchor_misfit
from fairband.engine.route import FOREIGN_FILER
from fairband.mcp.client import NOT_RUNNING, FairbandClient
from fairband.mcp.server import TOOL_NAMES, build_server
from fairband.policy import load_policy
from fairband.refresh.passthrough import BUSY, NO_GF_KEY
from fairband.reports.check import (
    ALWAYS_JUDGED,
    FAILURES,
    HEADINGS,
    STRUCTURE,
    parse_cite,
    quantities,
    structure_refusal,
)
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
    4: ("transcript", "segments", "finding_add"),
    5: ("transcript_dates", "transcript", "finding_add", "guidance_add", "derive"),
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
    "response",
    "policy",
)
# The refusals the agent meets, as the server words them; the playbook quotes each verbatim.
REFUSALS = (
    IDENTIFY_FIRST,
    NOT_RUNNING,
    NO_GUIDANCE,
    anchor_misfit("earnings.ntm"),
    anchor_misfit("revenue.ntm"),
    GUIDANCE_REF,
    FOREIGN_FILER,
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
    "On a refused row with no reviewed value and no possible secondary valuation (a foreign filer, no"
    " diluted share count), the stance rests on the thesis alone, and the report says so in section"
    " 8."
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
    for exemption in ("foreign filer", "no diluted share count"):  # step 10's two exemptions
        assert exemption in _tool_entry("secondary_valuation"), exemption
    # FMP's figure takes the secondary valuation's scope, in step 10 and in the tool list
    assert DCF_SCOPE in steps[10]
    assert DCF_SCOPE in _tool_entry("dcf").lower()
    assert STRUCTURE[-1] in _flat(_read(CITATIONS))  # the structural check as the check names it
    for path in sorted(PLAYBOOK.rglob("*.md")):
        text = _flat(_read(path)).lower()
        for phrase in STALE:
            assert phrase not in text, (path.name, phrase)


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
    assert "Tell the user, go on with the stored snapshot" in three
    assert "write the price's date in section 9 of the report" in three
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
    """The Markdown table in ``text`` whose header row is ``header``, cell for cell: its first
    column to its second, from the row after the separator to the first line that does not start
    with ``|``."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if _cells(line) == list(header))
    rows = {}
    for line in lines[start + 1 :]:
        if not line.startswith("|"):
            break
        cells = _cells(line)
        if not set(cells[0]) <= {"-", ":"}:  # the separator row left out
            rows[cells[0]] = cells[1]
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
