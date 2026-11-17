"""The company page's Research tab: the layout rules of a report's section (the Research tab's
design, 7.4 and 4; Review Focus 1). company_research_text.js runs in node after the bundle and
app.js (``support.page``): the tests hand ``researchText``'s functions a section's heading and
parts and read the rows and the cards they give, which hold the blocks the design system's reader
gives (``Fairband.reportText.read``) and the named blocks ``researchText.named`` makes of them.

The sections are synthetic: the report of ``support.research_answers``, in the template's shapes,
and the odd shapes made here. No rule drops a block: the blocks laid out are the blocks read, but
the Summary's stance line, and the two columns' opening words, which become their labels."""

import re
from typing import Any

import pytest
from support import research_answers as answers
from support.page import NODE, STATIC, node

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (STATIC / "company_research_text.js",)
STANCE = answers.STANCE
SUMMARY = "Summary"
BUSINESS = "The business"
FINANCIAL = "Financial performance and health"
DEBATE = "The bull case and the bear case"
JUDGMENTS = "Key judgments"
GROUPS = ["growth", "cash_flow", "solvency", "returns", "capital_allocation", "quality"]
# The headings whose named blocks stay in the text, in their place: the three with a rule of their
# own and the six whose cards draw records.
OWN = (
    SUMMARY,
    FINANCIAL,
    DEBATE,
    "The last earnings call",
    "Valuation",
    "Price and multiples",
    "Recent news",
    "Risks and kill criteria",
    JUDGMENTS,
)
CITE = {"cite": "TWD 291.4 billion", "ref": "segment:LFOX/product/Lenses/2025"}
CELL_44 = "Sensor sales to car suppliers rose all year."
CELL_45 = "Sensor sales to car suppliers rose in a year."
NAME_90 = (
    "Revenue by product and by region, in each reporting currency, over the three fiscal years:"
)
NAME_91 = (
    "Revenue by product and by region, in every reporting currency, over the three fiscal years:"
)
FIVE_COLUMNS = "| | 2022 | 2023 | 2024 | 2025 |\n|---|---|---|---|---|\n| Lenses | 1 | 2 | 3 | 4 |"

# A named list and a named table of three short columns between two paragraphs.
CARDS = [
    (
        "Lanternfield makes lenses.\n\nWhat drives revenue:\n\n- Volume.\n- Price.\n\nRevenue by "
        "product:\n\n| | Fiscal 2024 | Fiscal 2025 |\n|---|---|---|\n| Lenses | TWD 268.1 billion | "
    ),
    CITE,
    " |\n\nThe gross margin rose.",
]
# Three named tables: five columns, a cell of 45 characters, and a cell of 44.
WIDE = [
    (
        f"Lanternfield makes lenses.\n\nRevenue by year:\n\n{FIVE_COLUMNS}\n\nThe customers:\n\n"
        f"| Customer | Share |\n|---|---|\n| {CELL_45} | most |\n\nThe suppliers:\n\n"
        f"| Supplier | Share |\n|---|---|\n| {CELL_44} | most |\n\nThe end."
    ),
]
ONLY_NAMED = ["What drives revenue:\n\n- Volume.\n- Price.\n\nThe customers:\n\n- Carmakers."]
# A plain paragraph, then six led by a bold word: four groups named, growth twice, and a lead word
# that names none.
ONCE = [
    (
        "Profit kept pace with sales.\n\n**Growth.** Revenue rose.\n\n**Growth.** Margins rose too.\n\n"
        "**Cash flow.** Cash rose.\n\n**Outlook.** Demand holds.\n\n**Solvency.** No debt.\n\n"
        "**Returns.** Above the hurdle."
    )
]
FOUR = [
    (
        "**Growth.** Revenue rose.\n\n**Cash flow follows.** Cash rose.\n\n**Returns on capital.** "
        "Above the hurdle.\n\n**Quality scores.** Both strong."
    )
]
THREE = [
    (
        f"**Growth.** Revenue rose.\n\n**Cash flow.** Cash rose.\n\nA plain paragraph.\n\n"
        f"{FIVE_COLUMNS}\n\n**Returns.** Above the hurdle."
    )
]
TWICE = [
    (
        "**Growth.** Revenue rose.\n\n**Growth.** Margins rose.\n\n**Cash flow.** Cash rose.\n\n"
        "**Solvency.** No debt."
    )
]
BULL_BEAR = [
    "The bull case: customers stay, and ",
    CITE,
    " came from lenses.\n\n**The bear case.** rivals cut prices.",
]
THIRD = [*BULL_BEAR, "\n\nBoth sides agree on demand."]
BULLS = ["The bull case: customers stay.\n\nThe bull case: rivals fall behind."]
NO_RULE = [
    f"The judgments follow.\n\nThe record:\n\n- Phase stands.\n- Moat changed.\n\n{FIVE_COLUMNS}"
]
ONE_TABLE = ["| Customer | Share |\n|---|---|\n| Carmakers | most |"]
ONE_WIDE = [FIVE_COLUMNS]
ENDS = ["The company sells to a few makers.\n\nThe customers:\n\n- Carmakers.\n- Phone makers."]
COLON = ["The company sells to:"]
COLON_TEXT = ["The company sells to:\n\nCarmakers and phone makers."]
NAMES = [
    (
        f"{NAME_90}\n- Lenses.\n\n{NAME_91}\n- Lenses.\n\nThe sales\nby product:\n- Lenses.\n\n"
        "**Reasons for:**\n- Cars.\n\nRevenue of "
    ),
    CITE,
    " by product:\n| Lenses | ",
    CITE,
    " |",
]

# Every fixture with its heading and the report's stance: the report's twelve sections, and the
# shapes made here.
FIXTURES: list[tuple[str, list[Any], str]] = [
    *((s["heading"], s["parts"], STANCE) for s in answers.SECTIONS),
    (SUMMARY, ["Stance: trim.\nThe price ran ahead.\n\nReasons for:\n- A.\n- B."], "trim"),
    (SUMMARY, ["Stance: trim, for now.\n\nThe price ran ahead."], "trim"),
    (BUSINESS, CARDS, STANCE),
    (BUSINESS, WIDE, STANCE),
    (BUSINESS, ONLY_NAMED, STANCE),
    ("A heading the rules do not know", CARDS, STANCE),
    (FINANCIAL, ONCE, STANCE),
    (FINANCIAL, FOUR, STANCE),
    (FINANCIAL, THREE, STANCE),
    (FINANCIAL, TWICE, STANCE),
    (DEBATE, BULL_BEAR, STANCE),
    (DEBATE, THIRD, STANCE),
    (DEBATE, BULLS, STANCE),
    (JUDGMENTS, NO_RULE, STANCE),
    (BUSINESS, ONE_TABLE, STANCE),
    (BUSINESS, ONE_WIDE, STANCE),
    ("Industry and competition", ENDS, STANCE),
    ("The thesis", COLON_TEXT, STANCE),
]


def _lay(heading: str, parts: list[Any], stance: str = STANCE) -> Any:
    """``researchText.lay``'s rows and cards of the section."""
    return node("researchText.lay", [heading, parts, stance], *SCRIPTS)


def _read(parts: list[Any]) -> Any:
    """The section's blocks as the design system's reader gives them."""
    return node("Fairband.reportText.read", [parts])


def _named(parts: list[Any]) -> Any:
    """The section's blocks with its named blocks made (``researchText.named``)."""
    return node("researchText.named", [_read(parts)], *SCRIPTS)


def _p(text: str) -> dict[str, Any]:
    """A paragraph of one line of plain text, as the reader gives it."""
    return {"kind": "p", "items": [[text]]}


def _run(*blocks: Any) -> dict[str, Any]:
    return {"kind": "run", "blocks": list(blocks)}


def _wide(block: Any) -> dict[str, Any]:
    return {"kind": "wide", "block": block}


def _pair(group: str, block: Any) -> dict[str, Any]:
    return {"kind": "pair", "group": group, "block": block}


def _flat(rows: list[Any]) -> list[Any]:
    """Every block the rows hold, in their order: a run's and the columns' blocks, a wide row's
    and a pair's block, each side's block; a groups row holds none."""
    out: list[Any] = []
    for row in rows:
        if row["kind"] in ("run", "columns"):
            out += row["blocks"]
        elif row["kind"] in ("wide", "pair"):
            out.append(row["block"])
        elif row["kind"] == "sides":
            out += [side["block"] for side in row["sides"]]
    return out


# ------------------------------------------------------------------ the Summary


def test_the_stance_line_leaves_only_when_it_is_exact() -> None:
    """Rule 1 and section 4: the Summary's first line leaves where it is exactly ``Stance:
    <word>.`` and the word is the report's stance, which the bar states, the paragraph it opens
    staying; any other line stays, and so does the line under another heading."""
    after = "The price ran ahead of the business."
    alone = {"rows": [_run(_p(after))], "cards": []}
    assert _lay(SUMMARY, [f"Stance: trim.\n\n{after}"], "trim") == alone
    assert _lay(SUMMARY, [f"Stance: trim.\n{after}"], "trim") == alone
    for parts, stance in (
        ([f"Stance: trim.\n\n{after}"], "hold"),
        ([f"Stance: trim, for now.\n\n{after}"], "trim"),
        ([f"{after}\n\nStance: trim."], "trim"),
        ([after], "trim"),
    ):
        assert _lay(SUMMARY, parts, stance) == {"rows": [_run(*_read(parts))], "cards": []}
    kept = [f"Stance: trim.\n\n{after}"]
    assert _lay("The thesis", kept, "trim") == {"rows": [_run(*_read(kept))], "cards": []}


def test_the_summary_s_named_lists_stand_side_by_side() -> None:
    """Rule 1: two or more named lists in a row stand side by side, under the text before them,
    with what follows them under them; one named list stays in the text."""
    named = _named(answers.SUMMARY)  # the stance line, three paragraphs, three lists, a sentence
    laid = _lay(SUMMARY, answers.SUMMARY)
    assert laid == {
        "rows": [_run(*named[1:4]), {"kind": "columns", "blocks": named[4:7]}, _run(*named[7:])],
        "cards": [],
    }
    assert [b["name"] for b in named[4:7]] == [
        ["Reasons for"],
        ["Main risks"],
        ["What would change the view"],
    ]
    assert [b["body"]["kind"] for b in named[4:7]] == ["ol", "ol", "ul"]
    one = ["The price sits close to the value.\n\nReasons for:\n\n1. Cars.\n\nThe window ends."]
    assert _lay(SUMMARY, one) == {"rows": [_run(*_named(one))], "cards": []}


# ------------------------------------------------------------------ the cards


def test_a_named_list_and_a_narrow_named_table_become_cards() -> None:
    """Rule 2: under The business, Industry and competition, The thesis and a heading the rules do
    not know, a named list and a named table that is not wide leave the text for the cards, each
    with its name; a named table of five columns, or with a cell above 44 characters, stays as a
    wide row, and one with a cell of 44 is a card. The nine headings with a rule or a card of
    their own keep the named blocks in the text."""
    named = _named(CARDS)
    for heading in (BUSINESS, "Industry and competition", "The thesis", "Notes on the moat"):
        assert _lay(heading, CARDS) == {
            "rows": [_run(named[0], named[3])],
            "cards": [named[1], named[2]],
        }, heading
    assert [b["name"] for b in named[1:3]] == [["What drives revenue"], ["Revenue by product"]]
    assert _lay(JUDGMENTS, CARDS) == {"rows": [_run(*named)], "cards": []}

    assert (len(CELL_44), len(CELL_45)) == (44, 45)
    wide = _named(WIDE)
    assert [b["kind"] for b in wide] == ["p", "named", "named", "named", "p"]
    assert _lay(BUSINESS, WIDE) == {
        "rows": [_run(wide[0]), _wide(wide[1]), _wide(wide[2]), _run(wide[4])],
        "cards": [wide[3]],
    }
    measured = [
        (node("researchText.isWide", [b], *SCRIPTS), node("researchText.isLong", [b], *SCRIPTS))
        for b in (wide[1], wide[2], wide[3], wide[2]["body"], wide[0])
    ]
    assert measured == [(True, False), (True, True), (False, False), (True, True), (False, False)]


def test_a_section_that_is_only_named_blocks_keeps_them_in_place() -> None:
    """With no text for the cards to stand beside, the named blocks stay in the text."""
    assert _lay(BUSINESS, ONLY_NAMED) == {"rows": [_run(*_named(ONLY_NAMED))], "cards": []}


# ------------------------------------------------------------------ the financial section


def test_the_financial_pairs() -> None:
    """Rule 3: each paragraph led by a group's bold word stands beside its group's charts, in the
    tables' order."""
    named = _named(answers.FINANCIAL)
    assert _lay(FINANCIAL, answers.FINANCIAL) == {
        "rows": [_pair(key, block) for key, block in zip(GROUPS, named, strict=True)],
        "cards": [],
    }


def test_a_group_is_named_once_and_an_unknown_lead_word_is_text() -> None:
    """The first paragraph that names a group takes it; a second, a paragraph whose lead word names
    no group and a plain paragraph stand as text in their place; the groups no paragraph names
    follow."""
    named = _named(ONCE)
    assert _lay(FINANCIAL, ONCE) == {
        "rows": [
            _run(named[0]),
            _pair("growth", named[1]),
            _run(named[2]),
            _pair("cash_flow", named[3]),
            _run(named[4]),
            _pair("solvency", named[5]),
            _pair("returns", named[6]),
            {"kind": "groups", "groups": ["capital_allocation", "quality"]},
        ],
        "cards": [],
    }


def test_a_group_no_paragraph_names_follows() -> None:
    """Four groups named by lead words of more than one word: four pairs, then one row of the two
    groups no paragraph names."""
    named = _named(FOUR)
    assert _lay(FINANCIAL, FOUR) == {
        "rows": [
            _pair("growth", named[0]),
            _pair("cash_flow", named[1]),
            _pair("returns", named[2]),
            _pair("quality", named[3]),
            {"kind": "groups", "groups": ["solvency", "capital_allocation"]},
        ],
        "cards": [],
    }


def test_fewer_than_four_lead_words_put_every_chart_first() -> None:
    """Where fewer than four paragraphs name a group, every chart stands first, by group, and the
    blocks follow in their order, a wide table in its own row: three lead words; four paragraphs
    that name three groups, one twice; none."""
    every = {"kind": "groups", "groups": GROUPS}
    named = _named(THREE)
    assert _lay(FINANCIAL, THREE) == {
        "rows": [every, _run(*named[:3]), _wide(named[3]), _run(named[4])],
        "cards": [],
    }
    assert _lay(FINANCIAL, TWICE) == {"rows": [every, _run(*_named(TWICE))], "cards": []}
    plain = ["Revenue rose.\n\nCash rose."]
    assert _lay(FINANCIAL, plain) == {"rows": [every, _run(*_read(plain))], "cards": []}


def test_the_lead_word_s_matching() -> None:
    """The lead word without its full stop and without regard to case: one that starts with
    "growth", "cash" or "return", or holds "solvency", "balance", "capital allocation" or
    "quality", in the groups' order; any other, none."""
    expected = {
        "Balance sheet": "solvency",
        "solvency": "solvency",
        "Returns on capital": "returns",
        "Cash flow follows": "cash_flow",
        "Growth": "growth",
        "growth": "growth",
        "GROWTH.": "growth",
        "Quality scores": "quality",
        "Capital allocation": "capital_allocation",
        "Outlook": None,
    }
    found = {lead: node("researchText.group", [lead], *SCRIPTS) for lead in expected}
    assert found == expected


# ------------------------------------------------------------------ the two columns


def test_the_two_columns() -> None:
    """Rule 5: a section of exactly two paragraphs that open "The bull case" and "The bear case"
    stands in two columns, each under those words, which leave the paragraph's start, its first
    letter then upper case and its other pieces kept; three paragraphs, or two bull cases, stand
    as text."""
    assert _lay(DEBATE, BULL_BEAR) == {
        "rows": [
            {
                "kind": "sides",
                "sides": [
                    {
                        "label": "The bull case",
                        "block": {
                            "kind": "p",
                            "items": [["Customers stay, and ", CITE, " came from lenses."]],
                        },
                    },
                    {"label": "The bear case", "block": _p("Rivals cut prices.")},
                ],
            }
        ],
        "cards": [],
    }
    [row] = _lay(DEBATE, answers.BULL_BEAR)["rows"]
    assert [side["label"] for side in row["sides"]] == ["The bull case", "The bear case"]
    assert row["sides"][1]["block"]["items"][0][0].startswith("Two rivals now sell")
    for parts in (THIRD, BULLS):
        assert _lay(DEBATE, parts) == {"rows": [_run(*_read(parts))], "cards": []}


# ------------------------------------------------------------------ the fallback


def test_a_heading_with_no_rule_and_an_empty_section() -> None:
    """Under the six headings whose cards draw records, not the text's blocks, the blocks stand in
    their order, text in runs and a wide table in its own row; a section with no parts has no
    row."""
    named = _named(NO_RULE)
    for heading in OWN[3:]:
        assert _lay(heading, NO_RULE) == {
            "rows": [_run(named[0], named[1]), _wide(named[2])],
            "cards": [],
        }, heading
    for heading in (SUMMARY, BUSINESS, DEBATE, JUDGMENTS):
        assert _lay(heading, []) == {"rows": [], "cards": []}, heading


def test_odd_sections() -> None:
    """A section that is one table; a named list that ends a section; a line that ends in a colon
    with nothing after it, or a paragraph; and the name's line: one line of 90 characters or
    fewer, read as ``plain`` reads it, the cites by their text and ``**`` left out."""
    assert _lay(BUSINESS, ONE_TABLE) == {"rows": [_run(*_read(ONE_TABLE))], "cards": []}
    assert _lay(BUSINESS, ONE_WIDE) == {"rows": [_wide(_read(ONE_WIDE)[0])], "cards": []}
    named = _named(ENDS)
    assert _lay("Industry and competition", ENDS) == {"rows": [_run(named[0])], "cards": [named[1]]}
    for parts in (COLON, COLON_TEXT):
        assert _lay(BUSINESS, parts) == {"rows": [_run(*_read(parts))], "cards": []}

    assert (len(NAME_90), len(NAME_91)) == (90, 91)
    blocks = _named(NAMES)
    assert [b["kind"] for b in blocks] == ["named", "p", "ul", "p", "ul", "named", "named"]
    assert blocks[0]["name"] == [NAME_90[:-1]]
    assert blocks[5]["name"] == ["**Reasons for**"]
    assert blocks[6]["name"] == ["Revenue of ", CITE, " by product"]
    assert blocks[6]["body"]["kind"] == "table"
    line = ["**Revenue** of ", CITE, " rose."]
    assert node("researchText.plain", [line], *SCRIPTS) == "Revenue of TWD 291.4 billion rose."


# ------------------------------------------------------------------ no block dropped

_OPENING = re.compile(r"\**the (bull|bear) case\**[:.]?\**\s*", re.IGNORECASE)


def _opened(side: Any, block: Any) -> bool:
    """Whether ``side``'s block is ``block``, a paragraph, with its opening words off, the first
    letter of what follows upper case, under the label those words name."""
    got, was = side["block"]["items"], block["items"]
    first, start = got[0][0], was[0][0]
    words, rest = start[: len(start) - len(first)], start[len(start) - len(first) :]
    opening = _OPENING.fullmatch(words)
    return (
        opening is not None
        and side["label"] == f"The {opening[1].lower()} case"
        and (got[1:], got[0][1:]) == (was[1:], was[0][1:])
        and first == rest[:1].upper() + rest[1:]
    )


@pytest.mark.parametrize(
    ("heading", "parts", "stance"),
    FIXTURES,
    ids=[f"{n}-{heading}" for n, (heading, _, _) in enumerate(FIXTURES, 1)],
)
def test_no_rule_drops_a_block(heading: str, parts: list[Any], stance: str) -> None:
    """The blocks the rows and the cards hold, each once, are the named blocks of the parts, but
    the Summary's stance line: the rows' in their order, and the cards' in theirs, each taken out
    of its place; a side's paragraph is the paragraph its opening words left."""
    expected = _named(parts)
    first = expected[0]["items"] if expected and expected[0]["kind"] == "p" else None
    if heading == SUMMARY and first and first[0] == [f"Stance: {stance}."]:
        expected = ([{"kind": "p", "items": first[1:]}] if first[1:] else []) + expected[1:]
    laid = _lay(heading, parts, stance)
    rows, cards = _flat(laid["rows"]), laid["cards"]
    sides = [side for row in laid["rows"] if row["kind"] == "sides" for side in row["sides"]]
    in_rows = in_cards = 0
    for was in expected:
        if in_cards < len(cards) and cards[in_cards] == was:
            in_cards += 1
            continue
        assert in_rows < len(rows), was
        block = rows[in_rows]
        side = next((s for s in sides if s["block"] is block), None)
        assert block == was or (side is not None and _opened(side, was)), (block, was)
        in_rows += 1
    assert (in_rows, in_cards) == (len(rows), len(cards))
