"""The playbook (spec 2026-11-06 Tier 2, 14), the skill an agent host installs, against the server
it describes: it names every MCP tool with the arguments the server takes, in the server's order;
it runs spec 14's thirteen steps in order with the tools each names; it quotes the refusals the
agent meets as the server words them; its citation reference names the check's six failures and
the ref forms; and its submission example, twelve sections for an invented company, passes the
structural checks, the secondary valuation's among them, and the token rule."""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import anyio
import httpx
from mcp import Client

from fairband.engine.overrides import NO_GUIDANCE
from fairband.engine.route import FOREIGN_FILER
from fairband.mcp.client import NOT_RUNNING, FairbandClient
from fairband.mcp.server import TOOL_NAMES, build_server
from fairband.policy import load_policy
from fairband.refresh.passthrough import BUSY, NO_GF_KEY
from fairband.reports.check import (
    ALWAYS_JUDGED,
    FAILURES,
    HEADINGS,
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
    GUIDANCE_REF,
    FOREIGN_FILER,
    NO_FMP_KEY,
    NO_GF_KEY,
    BUSY,
    "the report needs a secondary valuation on snapshot <id>",
    "guidance record <id> is superseded by record <id>",
    "the store moved since snapshot <id>: run a revalue",
    "settings changed: run a revalue",
    "the path needs its own evidence item",
    "an axis holds one to five values",
    "the two tags differ",
)
# The forms the example cites at least once: the second view, the history, the grid, the guidance.
EXAMPLE_FORMS = ("secondary", "multiple", "sensitivity", "guidance")


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
        secondary_on_snapshot=True,
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
    assert set(EXAMPLE_FORMS) <= forms, set(EXAMPLE_FORMS) - forms
    for judgment in example["judgments"]:  # a record: no bull, no bear, no figure
        assert set(judgment) <= {"judgment", "decision", "override_id"}, judgment
        assert quantities(judgment["decision"]) == [], judgment["judgment"]


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
