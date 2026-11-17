"""The report reader renders a section's text as the agent wrote it (spec 2026-11-06 Tier 2, 13.1
"The text's shape" and 18.4): a blank line between paragraphs, bullet and numbered lists, a table
whose ``|---|`` row sets its header, ``**bold**``, and the cites with their footnote numbers inline
in any of them. The bundle runs in node with a stub React (``render.mjs``), so the test
reads the HTML ``ReportReader`` builds.

And the bundle's reader of a section's text in its two steps (spec 2026-11-17 research tab, 6
and 9): ``Fairband.reportText.read`` gives the blocks, ``Fairband.reportText.draw`` one block's
element, the two ``ReportReader`` calls, so a page that lays the blocks out itself draws what the
reader draws. The harness (``page.mjs``) calls them and the tests read what they give
(``support.page``)."""

import json
import re
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from support.page import elements, node

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("render.mjs")
BUNDLE = (
    Path(str(resources.files("fairband.web").joinpath("static", "design-system", "components")))
    / "bundle.js"
)

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PARTS = [
    "Stance: hold.\n\nThe price of ",
    {"cite": "$173.19", "ref": "snapshot:1/price"},
    " is below the buy level.\n\nReasons for:\n\n1. Licensing renewed.\n2. Cars grew ",
    {"cite": "51.7%", "ref": "table:QCOM/growth/revenue_growth/2026"},
    ".\n\n",
    "| | The quarter | A year before |\n|---|---|---|\n| Revenue | ",
    {"cite": "$10.44 billion", "ref": "fact:QCOM/revenue/2026Q4"},
    " | $11.27 billion |\n\n",
    (
        "**The verdict.** The call confirmed the thesis. A lone * stays. A price | value sentence"
        " stays prose."
    ),
]
FOOTNOTES = {"snapshot:1/price": 1, "table:QCOM/growth/revenue_growth/2026": 2}
BULLETS = [
    "Risks:\n\n- **Licensing.** A renewal could fail.\n- Cars may slow.\n\n",
    "3. The third reason.\n4. The fourth.\n\n",
    "**Revenue of ",
    {"cite": "$10.44 billion", "ref": "fact:QCOM/revenue/2026Q4"},
    " fell.** Growth ** slowed.\nThe next line joins.\n\n",
    "By quarter:\n| | Revenue |\n| :--- | ---: |\n| The quarter | ",
    {"cite": "$10.44 billion", "ref": "fact:QCOM/revenue/2026Q4"},
    " |\n\n| alone",
]
BULLETS_FOOTNOTES = {"fact:QCOM/revenue/2026Q4": 3}
PROSE = '<p class="fb-report__prose body">'


def _section(parts: list[Any], footnotes: dict[str, int]) -> str:
    """The HTML of one published section holding ``parts``, from its heading's end."""
    assert NODE is not None
    props = {
        "state": "published",
        "revision": "revision 1",
        "sections": [{"heading": "Summary", "parts": parts}],
        "footnotes": footnotes,
        "appendixes": False,
    }
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE)],
        input=json.dumps(props),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    html = done.stdout
    return html[html.index("</h4>") + len("</h4>") : html.rindex("</section>")]


def _between(html: str, start: str, end: str) -> str:
    """The text after the first ``start``, to the first ``end`` after it."""
    at = html.index(start) + len(start)
    return html[at : html.index(end, at)]


def _blocks(html: str) -> list[str]:
    """The section's blocks in order, by their class."""
    return re.findall(r'<(?:p|ul|ol|div) class="fb-report__(\w+)', html)


def test_the_text_renders_as_blocks() -> None:
    """The brief's fixture: three paragraphs, the numbered list, the table and a last paragraph."""
    html = _section(PARTS, FOOTNOTES)
    assert _blocks(html) == ["prose", "prose", "prose", "list", "scroll", "prose"]
    before = html[: html.index("<ol")]
    assert before.count("<p") == 3
    assert before.count(PROSE) == 3
    # the numbered list: two items, the second holding the cite and its footnote number
    numbered = _between(html, '<ol class="fb-report__list body" start="1">', "</ol>")
    items = re.findall(r"<li>(.*?)</li>", numbered)
    assert items[0] == "Licensing renewed."
    assert len(items) == 2 and numbered.count("<li>") == 2
    assert '<span class="fb-cite' in items[1]
    assert '<sup class="fb-cite__n">[2]</sup>' in items[1]
    assert items[1].startswith("Cars grew ")
    # the table: the header row in thead, the cite inside a body cell, no separator as text
    assert html.count('<table class="fb-report__table">') == 1
    assert '<div class="fb-report__scroll"><table class="fb-report__table"><thead><tr>' in html
    head = _between(html, "<thead>", "</thead>")
    assert re.findall(r'<th class="label">(.*?)</th>', head) == ["", "The quarter", "A year before"]
    body = _between(html, "<tbody>", "</tbody>")
    cells = re.findall(r'<td class="body">(.*?)</td>', body)
    assert len(cells) == 3 and cells[0] == "Revenue" and cells[2] == "$11.27 billion"
    assert cells[1].startswith('<span class="fb-cite figure-sm" title="traces to fact:QCOM/')
    assert "|---|" not in html and "---" not in html and "|" not in cells[1]
    # the last paragraph: the bold lead, the lone *, and a | in a sentence, which stays prose
    last = re.findall(re.escape(PROSE) + r"(.*?)</p>", html)[-1]
    assert last.startswith("<strong>The verdict.</strong> The call confirmed the thesis.")
    assert "A lone * stays." in last
    assert "A price | value sentence stays prose." in last
    assert "**" not in html
    # the price's cite in the second paragraph keeps its underline's class and its number
    second = re.findall(re.escape(PROSE) + r"(.*?)</p>", html)[1]
    assert second == (
        'The price of <span class="fb-cite figure-sm" title="traces to snapshot:1/price">'
        '$173.19</span><sup class="fb-cite__n">[1]</sup> is below the buy level.'
    )


def test_bullets_bold_leads_and_cites_in_cells() -> None:
    """Review focus 4: a list item with a bold lead, a cite with its footnote number in a table
    cell, held with it in one span (spec 2026-11-15 9), and the same cite in a paragraph without
    one, a bold run across a cite, an unpaired ``**``, a numbered list's own start, a paragraph's
    lines joined with a space, a table under a paragraph line with no blank line, and a line that
    opens with ``|`` and holds no second one, which stays prose."""
    html = _section(BULLETS, BULLETS_FOOTNOTES)
    assert _blocks(html) == ["prose", "list", "list", "prose", "prose", "scroll", "prose"]
    bullets = _between(html, '<ul class="fb-report__list body">', "</ul>")
    assert re.findall(r"<li>(.*?)</li>", bullets) == [
        "<strong>Licensing.</strong> A renewal could fail.",
        "Cars may slow.",
    ]
    numbered = _between(html, '<ol class="fb-report__list body" start="3">', "</ol>")
    assert re.findall(r"<li>(.*?)</li>", numbered) == ["The third reason.", "The fourth."]
    cite = (
        '<span class="fb-cite figure-sm" title="traces to fact:QCOM/revenue/2026Q4">'
        '$10.44 billion</span><sup class="fb-cite__n">[3]</sup>'
    )
    paragraphs = re.findall(re.escape(PROSE) + r"(.*?)</p>", html)
    assert paragraphs[0] == "Risks:"
    assert paragraphs[1] == (
        f"<strong>Revenue of {cite} fell.</strong> Growth ** slowed. The next line joins."
    )
    assert paragraphs[2] == "By quarter:"
    assert paragraphs[3] == "| alone"
    assert re.findall(r'<th class="label">(.*?)</th>', html) == ["", "Revenue"]
    # in a cell the cite and its number sit in one span that does not wrap (spec 2026-11-15 9)
    assert re.findall(r'<td class="body">(.*?)</td>', html) == [
        "The quarter",
        f'<span class="fb-cite__pair">{cite}</span>',
    ]
    assert ":---" not in html


def _reader_blocks(parts: list[Any], footnotes: dict[str, int]) -> list[Any]:
    """The elements ``ReportReader`` draws for one published section holding ``parts``, after its
    heading and its charts, as the harness gives the tree."""
    props = {
        "state": "published",
        "revision": "revision 1",
        "sections": [{"heading": "Summary", "parts": parts}],
        "footnotes": footnotes,
        "appendixes": False,
    }
    tree = node("Fairband.ReportReader", [props])
    [section] = [e for e in elements(tree) if e.get("type") == "section"]
    heading, charts, drawn = section["props"]["children"]
    assert heading["type"] == "h4" and charts is None
    return list(drawn)


@pytest.mark.parametrize(
    ("parts", "footnotes", "kinds"),
    [
        (PARTS, FOOTNOTES, ["p", "p", "p", "ol", "table", "p"]),
        (BULLETS, BULLETS_FOOTNOTES, ["p", "ul", "ol", "p", "p", "table", "p"]),
    ],
)
def test_read_and_draw_give_what_the_reader_drew(
    parts: list[Any], footnotes: dict[str, int], kinds: list[str]
) -> None:
    """Each fixture's section, read into blocks with ``reportText.read`` and each block drawn with
    ``reportText.draw`` under its index as its key, is the tree ``ReportReader`` draws for it."""
    blocks = node("Fairband.reportText.read", [parts])
    assert [block["kind"] for block in blocks] == kinds
    drawn = [
        node("Fairband.reportText.draw", [block, footnotes, k]) for k, block in enumerate(blocks)
    ]
    assert drawn == _reader_blocks(parts, footnotes)


def test_read_gives_the_blocks_kinds() -> None:
    """A paragraph, a bullet list, a numbered list from 3 and a table read as four blocks in the
    shape the reader builds: a paragraph's lines, a list's items, the numbered list's start, the
    table's one head row and its rows of cells, each a list of pieces, a text or a cite."""
    cite = {"cite": "$10.44 billion", "ref": "fact:QCOM/revenue/2026Q4"}
    parts = [
        "A paragraph.\n\n- One.\n- Two.\n\n3. Third.\n4. Fourth.\n\n",
        "| Line | Figure |\n|---|---|\n| Revenue | ",
        cite,
        " |",
    ]
    blocks = node("Fairband.reportText.read", [parts])
    assert [block["kind"] for block in blocks] == ["p", "ul", "ol", "table"]
    paragraph, bullets, numbered, table = blocks
    assert paragraph["items"] == [["A paragraph."]]
    assert bullets["items"] == [["One."], ["Two."]]
    assert numbered["start"] == 3
    assert numbered["items"] == [["Third."], ["Fourth."]]
    assert table["head"] == [[["Line"], ["Figure"]]]
    assert table["items"] == [[["Revenue"], [cite]]]
