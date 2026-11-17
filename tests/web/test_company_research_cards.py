"""The company page's Research tab, its cards and its charts (the Research tab's design, 7.4 rules
1, 3, 4 and 6 to 10, 7.5, 7.6, 7.9 and 8.2; Review Focus 2, 3 and 4): the value card on each form
of the read's ``call``, the changes card, the kill criteria, the news sources, the judgments,
each heading's cards, a financial paragraph beside its group's charts, the earnings call's charts
by quarter, and the series read once a report after it lands, each read with the request header,
one of another report dropped. The tab's scripts run in node after the bundle and app.js
(``support.page``), and the tests read the trees its builders return; ``research.mjs`` drives
the tab with the series' answers landing when a step lets them.

The answer is ``support.research_answers``' LFOX: report 31, a hold resting on review 6, and its
series. Every company, figure and sentence is invented."""

import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support import page_answers
from support import research_answers as answers
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (
    STATIC / "charts.js",
    STATIC / "company.js",
    STATIC / "report_parts.js",
    STATIC / "company_research_text.js",
    STATIC / "company_research.js",
)
DRIVER = Path(__file__).parent / "research.mjs"
METER = ("low", "high", "price", "fairValue", "buyLevel", "trimLevel", "designation", "gap")
SMALL = 120
GROUPS = ["growth", "cash_flow", "solvency", "returns", "capital_allocation", "quality"]
TABLES = answers.COMPANY + "/financial-tables"
HEADER = {"X-Fairband-Request": "1"}
HEADINGS = [s["heading"] for s in answers.SECTIONS]

# A report's call on its snapshot alone: the mechanical value, its levels and a price 1.9 times it.
MECHANICAL: dict[str, Any] = {
    "value": 186.0,
    "basis": "mechanical",
    "note": None,
    "levels": {"buy": 148.8, "fairLow": 167.4, "fairHigh": 204.6, "trim": 279.0},
    "priceToValue": 1.9,
    "designation": "well-above",
    "price": 353.4,
    "priceDate": "2026-11-10",
    "dataDate": "2026-11-10",
    "validUntil": "2027-02-12",
    "mechanicalValue": 186.0,
    "refusal": None,
}


def _research(helper: str, *args: Any) -> Any:
    """What ``research.<helper>`` returns on ``args``, the tab's scripts loaded after app.js."""
    return node("research." + helper, list(args), *SCRIPTS)


def _charts_of(helper: str, *args: Any) -> Any:
    return node("reportCharts." + helper, list(args), *SCRIPTS)


def _drive(steps: list[dict[str, Any]], replies: dict[str, Any] | None = None) -> Any:
    """The trace of ``steps`` with the fetch's ``replies`` (``research.mjs``)."""
    assert NODE is not None
    scripts = (BUNDLE, STATIC / "app.js", *SCRIPTS)
    done = subprocess.run(
        [NODE, str(DRIVER), *(str(script) for script in scripts)],
        input=json.dumps({"store": {}, "answers": replies or {}, "steps": steps}),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert done.stderr == "", done.stderr
    return json.loads(done.stdout)


def _mount(answer: dict[str, Any] | None = None, do: str = "mount") -> dict[str, Any]:
    return {
        "do": do,
        "answer": answer if answer is not None else answers.answer(),
        "detail": page_answers.detail(),
    }


def _one(tree: Any, name: str) -> dict[str, Any]:
    [found] = classed(tree, name)
    return found


def _texts(tree: Any) -> list[str]:
    return [text(e) for e in elements(tree)]


def _meter(tree: Any) -> list[dict[str, Any]]:
    """The props of each BandMeter in a tree its builder returned: the element that carries a
    ``fairValue``."""
    return [e["props"] for e in elements(tree) if "fairValue" in e["props"]]


def _clean(tree: Any) -> None:
    """No text the tree holds is a figure that failed."""
    for word in ("NaN", "null", "undefined"):
        assert word not in text(tree), word


def _rule(selector: str) -> str:
    """The declarations of the page's one rule whose line opens with ``selector``, on one line."""
    css = _static_file("index.html")
    ends = [m.end() for m in re.finditer(r"(?m)^[ \t]*" + re.escape(selector), css)]
    assert len(ends) == 1, selector
    return " ".join(css[ends[0] : css.index("}", ends[0])].split())


def test_a_card_s_name_reads_as_the_label_and_a_level_takes_its_zone_s_colour() -> None:
    """A named block's name in a card is the label's size, not the card's text's: its rule
    outranks the card's prose rule. A level's key takes its zone's token."""
    name = _rule(".app-research .app-research__name > .fb-report__prose {")
    assert "font: inherit;" in name
    card = ".app-research__card .fb-report__prose, .app-research__card .fb-report__list {"
    assert "font-size: 14px;" in _rule(card)
    for level, zone in (("buy", "buy"), ("fair", "fair"), ("trim", "trim")):
        key = _rule(f".app-research__level--{level}::before {{")
        assert key == f"background: var(--zone-{zone});"


# ---------------------------------------------------------------------------- the value card


def test_the_value_card() -> None:
    """The report's call: its head on the data of the snapshot, priced that day; the value a
    share by formatMoney and its kind; the design system's meter on the value, its four levels,
    the snapshot's price, the read's word and the gap in the page's words, with no scale and
    under no hero; the three levels in words; the caption's two sentences, today's figures from
    the company's detail."""
    tree = _research("valueCard", MECHANICAL, page_answers.detail())
    head = _one(tree, "app-research__head")
    assert [text(e) for e in head["props"]["children"]] == [
        "The report's call",
        "on the data of 10 Nov 2026, priced that day",
    ]
    value = _one(tree, "app-research__value")
    assert _texts(value)[1:] == ["Value a share", "$186.00mechanical", "$186.00", "mechanical"]
    [meter] = _meter(tree)
    assert {key: meter[key] for key in METER} == {
        "low": 167.4,
        "high": 204.6,
        "price": 353.4,
        "fairValue": 186.0,
        "buyLevel": 148.8,
        "trimLevel": 279.0,
        "designation": "well-above",
        "gap": "1.90 × the mechanical value",
    }
    assert (meter["showScale"], meter["hero"]) == (False, False)
    assert [text(e) for e in classed(tree, "app-research__level")] == [
        "buy below $148.80",
        "close to the value $167.40 to $204.60",
        "trim above $279.00",
    ]
    assert text(_one(tree, "app-research__foot")) == (
        "Valid until 12 Feb 2027. Today the mechanical value is $196.50 and the price $182.40."
    )
    _clean(tree)


def test_priced_that_day_and_priced_on_another() -> None:
    def head(call: dict[str, Any]) -> str:
        found = _research("valueCard", call, page_answers.detail())
        return text(_one(found, "app-research__headnote"))

    assert head(MECHANICAL) == "on the data of 10 Nov 2026, priced that day"
    assert head(MECHANICAL | {"priceDate": "2026-11-09"}) == (
        "on the data of 10 Nov 2026, priced 9 Nov 2026"
    )


def test_a_reviewed_value_names_the_mechanical_one() -> None:
    """A value a review gives is `reviewed`, the gap over the reviewed value, and the caption's
    third sentence names the snapshot's mechanical value; none where the snapshot has none."""
    call = answers.CALL | {"mechanicalValue": 451.42}
    tree = _research("valueCard", call, page_answers.detail())
    assert text(_one(tree, "app-research__kind")) == "reviewed"
    [meter] = _meter(tree)
    assert meter["gap"] == "0.97 × the reviewed value"
    assert (meter["fairValue"], meter["price"], meter["designation"]) == (182.0, 176.8, "near")
    assert text(_one(tree, "app-research__foot")) == (
        "Valid until 12 Feb 2027. Today the mechanical value is $196.50 and the price $182.40. "
        "The mechanical value was $451.42."
    )
    refused = _research("valueCard", answers.CALL | {"mechanicalValue": None}, None)
    assert text(_one(refused, "app-research__foot")) == "Valid until 12 Feb 2027."
    mechanical = _research("valueCard", MECHANICAL, page_answers.detail())
    assert "The mechanical value was" not in text(mechanical)


def test_a_secondary_valuation_s_card() -> None:
    call = answers.CALL | {
        "value": 114.65,
        "note": "secondary valuation",
        "levels": {"buy": 85.99, "fairLow": 97.45, "fairHigh": 131.85, "trim": 171.98},
        "priceToValue": 176.8 / 114.65,
        "designation": "well-above",
        "mechanicalValue": None,
    }
    tree = _research("valueCard", call, page_answers.detail())
    assert text(_one(tree, "app-research__kind")) == "reviewed, secondary valuation"
    [meter] = _meter(tree)
    assert meter["gap"] == "1.54 × the secondary valuation"
    assert meter["fairValue"] == 114.65
    assert "The mechanical value was" not in text(tree)


NO_VALUE: dict[str, Any] = MECHANICAL | {
    "value": None,
    "basis": None,
    "levels": None,
    "priceToValue": None,
    "designation": None,
    "mechanicalValue": None,
    "refusal": "fewer than three fiscal years of statements on file",
}


def test_no_value_draws_the_refusal_and_no_meter() -> None:
    tree = _research("valueCard", NO_VALUE, page_answers.detail())
    assert text(_one(tree, "app-refusal")) == NO_VALUE["refusal"]
    assert _meter(tree) == []
    assert classed(tree, "app-research__value") == []
    assert classed(tree, "app-research__levels") == []
    _clean(tree)
    _clean(_research("valueCard", NO_VALUE | {"refusal": None}, None))


def test_a_call_with_no_price_draws_the_value_and_no_meter() -> None:
    call = answers.CALL | {"price": None, "priceDate": None, "priceToValue": None}
    call["designation"] = None
    tree = _research("valueCard", call, page_answers.detail())
    assert text(_one(tree, "app-research__headnote")) == "on the data of 10 Nov 2026"
    assert _texts(_one(tree, "app-research__figure"))[1:] == ["$182.00", "reviewed"]
    assert _meter(tree) == []
    _clean(tree)
    no_levels = _research("valueCard", MECHANICAL | {"levels": None}, page_answers.detail())
    assert _meter(no_levels) == [] and classed(no_levels, "app-research__levels") == []
    _clean(no_levels)


def test_today_s_value_is_the_detail_s() -> None:
    """The caption's today: the review's value, `reviewed`, where the company's detail carries a
    review with a value; else the snapshot's, `mechanical`; left out with no value or no price."""

    def foot(detail: dict[str, Any] | None) -> str:
        return text(_one(_research("valueCard", MECHANICAL, detail), "app-research__foot"))

    assert foot(page_answers.reviewed_detail()) == (
        "Valid until 12 Feb 2027. Today the reviewed value is $182.00 and the price $182.40."
    )
    unvalued = page_answers.reviewed_detail()
    unvalued["review"] = unvalued["review"] | {"value": None}
    assert "Today the mechanical value is $196.50" in foot(unvalued)
    assert foot(page_answers.refused_detail()) == "Valid until 12 Feb 2027."
    unpriced = page_answers.detail()
    unpriced["result"]["price"] = None
    assert foot(unpriced) == "Valid until 12 Feb 2027."


# -------------------------------------------------------------------------- the changes card


def _bridged(lines: list[dict[str, Any]], units: dict[int, str]) -> dict[str, Any]:
    report: dict[str, Any] = answers.answer()["report"]
    a = report["appendixA"]
    a["bridge"]["lines"] = lines
    a["overrides"] = [
        a["overrides"][0] | {"id": override, "unit": unit} for override, unit in units.items()
    ]
    return report


def test_the_changes_card() -> None:
    """A report with no review changes no input; one on a review draws a line a change, in the
    bridge's order: its label, its figures before and after in its unit (P.inputFigure), and its
    effect on the value a share, signed, to cents, or its refusal."""
    unreviewed = answers.answer()["report"] | {"reviewId": None}
    unreviewed["appendixA"]["bridge"] = None
    none = _research("changesCard", unreviewed)
    assert [text(e) for e in _one(none, "app-research__head")["props"]["children"]] == [
        "Changes to Fairband's inputs",
        "none",
    ]
    assert "The report changes no input, so its value is the mechanical value." in _texts(none)
    assert classed(none, "app-research__rec") == []

    lines = [
        {"tag": "growth.belief", "overrideId": 21, "old": 0.256, "new": 0.198, "delta": -56.55}
        | {"refusal": None, "label": "belief"},
        {"tag": "moat.class", "overrideId": 12, "old": "Wide", "new": "Narrow", "delta": -14.5}
        | {"refusal": None, "label": "moat"},
        {"tag": "value.outside", "overrideId": 23, "old": 0.0, "new": 3.04, "delta": 3.04}
        | {"refusal": None, "label": "value outside the business"},
    ]
    units = {21: "ratio", 12: "class", 23: "USD a share"}
    three = _research("changesCard", _bridged(lines, units))
    assert text(_one(three, "app-research__headnote")) == "3"
    recs = classed(three, "app-research__rec")
    assert [text(_one(r, "app-research__label")) for r in recs] == [
        "belief",
        "moat",
        "value outside the business",
    ]
    assert [text(_one(r, "app-research__change")) for r in recs] == [
        "25.6% → 19.8%",
        "Wide → Narrow",
        "$0.00 → $3.04",
    ]
    assert text(_one(recs[0], "app-research__change")) == (
        node("inputFigure", [0.256, "ratio"]) + " → " + node("inputFigure", [0.198, "ratio"])
    )
    assert [text(_one(r, "app-research__effect")) for r in recs] == [
        "−$56.55 a share",
        "−$14.50 a share",
        "+$3.04 a share",
    ]
    refusal = "the route refuses a return on new capital below the hurdle"
    failed = {"tag": "return.runway", "overrideId": 24, "old": 0.5, "new": 0.05, "delta": None}
    failed |= {"refusal": refusal, "label": "runway return"}
    four = _research("changesCard", _bridged([*lines, failed], units | {24: "ratio"}))
    last = classed(four, "app-research__rec")[-1]
    assert text(_one(last, "app-research__change")) == "50.0% → 5.0%"
    assert classed(last, "app-research__effect") == []
    assert text(_one(last, "app-refusal")) == refusal
    assert "The report changes no input" not in text(four)
    _clean(four)


# ------------------------------------------------------------------------ the records' cards


def test_the_kill_criteria_card() -> None:
    """Kill criteria with how many are open of all; each with its state, the day of that state,
    its text and its state's reason; under them the sentence that a state outlives the report."""
    tree = _research("killCard", answers.CRITERIA)
    assert [text(e) for e in _one(tree, "app-research__head")["props"]["children"]] == [
        "Kill criteria",
        "2 open of 3",
    ]
    recs = classed(tree, "app-research__rec")
    assert [text(_one(r, "app-research__stamp")) for r in recs] == ["open", "open", "triggered"]
    assert [text(_one(r, "app-research__since")) for r in recs] == [
        "since 11 Nov 2026",
        "since 2 Oct 2026",
        "since 11 Nov 2026",
    ]
    triggered = recs[2]
    assert "A rival matches the newest lens grade." in _texts(triggered)
    assert text(_one(triggered, "app-research__reason")) == (
        "A rival launched a lens of the same grade on 28 Oct 2026."
    )
    assert classed(recs[0], "app-research__reason") == []
    assert text(_one(tree, "app-research__foot")) == (
        "A criterion keeps its state after the report: an agent marks it when the event happens."
    )
    assert _research("killCard", []) is None


def test_the_news_card() -> None:
    """The sources on file with their count, newest first: each its date, its address's host
    without www., and its headline, a link only where the address is a web address."""
    items = copy.deepcopy(answers.NEWS_ITEMS[:2])
    items += [
        {**items[0], "id": 90, "date": "2026-11-05", "headline": "A plant opened"}
        | {"source": "https://www.press.example/plant"},
        {**items[0], "id": 91, "date": "2026-10-30", "headline": "A filing"}
        | {"source": "ftp://files.example/filing"},
        {**items[0], "id": 92, "date": "2026-10-29", "headline": "A script"}
        | {"source": "javascript:alert(1)"},
    ]
    tree = _research("newsCard", items)
    assert [text(e) for e in _one(tree, "app-research__head")["props"]["children"]] == [
        "The sources on file",
        "5",
    ]
    recs = classed(tree, "app-research__rec")
    assert [text(_one(r, "app-research__headline")) for r in recs] == [
        "A plant opened",
        "A new supply contract with a car supplier",
        "A filing",
        "A script",
        "A rival launched a lens of the same grade",
    ]
    assert [text(_one(r, "app-research__date")) for r in recs] == [
        "5 Nov 2026",
        "3 Nov 2026",
        "30 Oct 2026",
        "29 Oct 2026",
        "28 Oct 2026",
    ]
    assert [[text(e) for e in classed(r, "app-research__host")] for r in recs] == [
        ["press.example"],
        ["lanternfield.example"],
        [],
        [],
        [],
    ]
    links = [_one(r, "app-research__headline") for r in recs]
    assert [(e["type"], e["props"].get("href")) for e in links] == [
        ("a", "https://www.press.example/plant"),
        ("a", "https://lanternfield.example/contract"),
        ("span", None),
        ("span", None),
        ("span", None),
    ]
    assert links[0]["props"]["rel"] == "noopener"
    assert _research("newsCard", []) is None


def test_the_judgment_cards() -> None:
    """One card a judgment in a row: its name, `stands`, or `changed` where it names an
    override, and its decision."""
    report = answers.answer()["report"]
    report["judgments"].append(
        {**report["judgments"][0], "id": 105, "judgment": "target_margin"}
        | {"decision": "The peers' margin stands.", "overrideId": None}
    )
    row = _research("judgmentCards", report)
    assert "app-research__judged" in row["props"]["className"]
    cards = classed(row, "app-research__card")
    assert [text(_one(c, "app-research__judgment")) for c in cards] == [
        "Phase",
        "Moat",
        "Belief",
        "Return on new capital",
        "Target margin",
    ]
    assert [text(_one(c, "app-research__stamp")) for c in cards] == [
        "stands",
        "changed",
        "stands",
        "stands",
        "stands",
    ]
    assert "app-research__stamp--on" in _one(cards[1], "app-research__stamp")["props"]["className"]
    assert text(_one(cards[1], "app-research__decision")) == (
        "Narrow: two rivals now sell lenses of the same grade."
    )
    assert _research("judgmentCards", report | {"judgments": []}) is None


# ---------------------------------------------------------------------- the cards by heading


def _with_reading() -> dict[str, Any]:
    """The answer whose report cites sensitivity reading 9."""
    answer = answers.answer()
    references = answer["report"]["references"]
    references.append(
        {"n": len(references) + 1, "ref": answers.READING_REF, "source": "sensitivity 9"}
    )
    return answer


def _panel(tree: Any, index: int) -> dict[str, Any]:
    """The panel of the section at ``index`` in the drawn tab."""
    [found] = [e for e in elements(tree) if e["props"].get("id") == f"research-s{index + 1}"]
    return found


def _column(panel: dict[str, Any]) -> list[dict[str, Any]]:
    """The cards in a panel's column, in order."""
    cards: list[dict[str, Any]] = _one(panel, "app-research__cards")["props"]["children"][0]
    return cards


def _titles(tree: Any) -> list[str]:
    return [text(e) for e in classed(tree, "fb-c__title")]


def test_the_cards_of_each_heading() -> None:
    """Summary: the value card beside its first run. Valuation: each grid, then the changes card.
    Price and multiples: the band, the trailing and the forward P/E. Recent news: the sources on
    file. Risks and kill criteria: the kill criteria. Key judgments: its cards in a row under the
    text, no column."""
    mounted, landed = _drive([_mount(_with_reading()), {"do": "wait"}], answers.series_replies())
    tree = landed["tree"]
    summary = _panel(tree, HEADINGS.index("Summary"))
    split = _one(summary, "app-research__split")
    assert "app-research__run" in split["props"]["children"][0]["props"]["className"]
    [call] = _column(summary)
    assert "app-research__call" in call["props"]["className"]
    assert "The report's call" in text(call)

    valuation = _column(_panel(tree, HEADINGS.index("Valuation")))
    assert [_titles(card) for card in valuation] == [[answers.READING["title"]], []]
    assert "app-research__changes" in valuation[1]["props"]["className"]
    prices = _column(_panel(tree, HEADINGS.index("Price and multiples")))
    assert [_titles(card) for card in prices] == [
        ["The price against the band by quarter"],
        ["Trailing P/E"],
        ["Forward P/E"],
    ]
    [news] = _column(_panel(tree, HEADINGS.index("Recent news")))
    assert "The sources on file" in text(news)
    [kill] = _column(_panel(tree, HEADINGS.index("Risks and kill criteria")))
    assert "2 open of 2" in text(kill)

    judgments = _panel(tree, HEADINGS.index("Key judgments"))
    assert classed(judgments, "app-research__cards") == []
    rows = _one(judgments, "app-research__body")["props"]["children"][0]
    assert "app-research__run" in rows[0]["props"]["className"]
    assert "app-research__judged" in rows[-1]["props"]["className"]
    assert len(classed(rows[-1], "app-research__card")) == 4
    assert classed(tree, "app-chart") == []  # no chart on a raised panel of its own

    # before the series land, the grids wait and the changes card stands alone
    before = _column(_panel(mounted["tree"], HEADINGS.index("Valuation")))
    assert [_titles(card) for card in before] == [[]]
    price = _panel(mounted["tree"], HEADINGS.index("Price and multiples"))
    assert classed(price, "app-research__cards") == []


# ----------------------------------------------------------------------- the charts in the text


def _section(index: int, landed: dict[str, Any], parts: list[Any] | None = None) -> Any:
    report = answers.answer()["report"]
    section = report["sections"][index]
    if parts is not None:
        section = section | {"parts": parts}
    return _research("section", section, index, report, {}, landed)


def _rows(tree: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = _one(tree, "app-research__body")["props"]["children"][0]
    return rows


def _laid_count(index: int) -> int:
    """The blocks ``lay`` gives a section: a run's and a columns row's blocks, a wide row's and a
    pair's one, a sides row's one a side, a card one; none in a row of charts alone."""
    section = answers.SECTIONS[index]
    laid = node(
        "researchText.lay",
        [section["heading"], section["parts"], answers.STANCE],
        STATIC / "company_research_text.js",
    )
    count = len(laid["cards"])
    for row in laid["rows"]:
        if row["kind"] in ("run", "columns"):
            count += len(row["blocks"])
        elif row["kind"] == "sides":
            count += len(row["sides"])
        elif row["kind"] in ("wide", "pair"):
            count += 1
    return int(count)


def _drawn_blocks(tree: Any) -> int:
    """The blocks the reader drew in a panel, a named block's body among them but not its name."""
    names = {id(e) for name in classed(tree, "app-research__name") for e in elements(name)}
    kinds = ("fb-report__prose", "fb-report__list", "fb-report__scroll")
    return len(
        [
            e
            for e in elements(tree)
            if id(e) not in names
            and any(k in str(e["props"].get("className") or "").split() for k in kinds)
        ]
    )


def test_a_pair_holds_its_group_s_charts_and_the_call_its_quarters() -> None:
    """Rule 3: a pair is its paragraph at the reading width beside its group's charts, drawn
    smaller; a group no paragraph names stands in a row of its own, the charts alone at their
    own height. Rule 4: the call opens with its three charts by quarter, drawn smaller. A refused
    read draws its sentence once, in the place of the first charts. Every section's text is
    drawn while no series has landed."""
    tables = {"body": answers.TABLES}
    small = _charts_of("groupCharts", tables, SMALL)
    financial = HEADINGS.index("Financial performance and health")
    rows = _rows(_section(financial, {"tables": tables}))
    assert [r["props"]["className"] for r in rows] == ["app-research__pair"] * 6
    for row, key in zip(rows, GROUPS, strict=True):
        run, charts = row["props"]["children"]
        assert "app-research__run" in run["props"]["className"]
        assert charts["props"]["className"] == "app-research__minis"
        assert charts["props"]["children"] == [small[key]]

    parts = [
        p.replace("**Quality.**", "**Scores.**") if isinstance(p, str) else p
        for p in answers.FINANCIAL
    ]
    rows = _rows(_section(financial, {"tables": tables}, parts))
    assert [r["props"]["className"] for r in rows] == [
        *["app-research__pair"] * 5,
        "app-research__run",
        "app-research__minis app-research__minis--all",
    ]
    whole = _charts_of("groupCharts", tables)
    assert rows[-1]["props"]["children"] == [whole["quality"]]

    refused = {"error": "no financial statements for LFOX"}
    rows = _rows(_section(financial, {"tables": refused}))
    sentence = "The financial tables did not load: no financial statements for LFOX."
    assert [text(r["props"]["children"][1]) for r in rows] == [sentence] + [""] * 5

    earnings = HEADINGS.index("The last earnings call")
    first, *rest = _rows(_section(earnings, {"tables": tables}))
    assert first["props"]["className"] == "app-research__minis"
    assert first["props"]["children"] == [_charts_of("quarterCharts", tables, SMALL)]
    assert rest == _rows(_section(earnings, {}))

    [mounted] = _drive([_mount()])
    for index in range(len(HEADINGS)):
        panel = _panel(mounted["tree"], index)
        assert _drawn_blocks(panel) == _laid_count(index), HEADINGS[index]
    assert _titles(mounted["tree"]) == []  # no chart before its series lands
    pairs = classed(mounted["tree"], "app-research__pair")
    assert len(pairs) == 6
    assert all(p["props"]["children"][1]["props"]["children"] == [None] for p in pairs)


# ------------------------------------------------------------------------------- the series


def _report_19() -> dict[str, Any]:
    answer = answers.answer()
    answer["report"] |= {"id": 19, "revision": 1, "stance": "trim"}
    return answer


def _urls(step: dict[str, Any]) -> list[str]:
    return sorted(url for _, url in step["fetched"])


def test_the_series_are_read_once_an_answer_with_the_request_header() -> None:
    """After the report lands, its series are read, each on its own with the request header: the
    financial tables, the multiples history, five years of closes, the band's history and each
    sensitivity reading the references name; each landing draws the page again. The tab drawn
    again with the same answer reads none; a new answer of the same report, as after a refresh
    ends or a note is taken, reads them all again."""
    press = {"do": "press", "class": "app-research__marks", "text": "Footnote marks"}
    steps = [_mount(_with_reading()), {"do": "wait"}, press]
    steps += [_mount(_with_reading(), "land"), {"do": "wait"}, press]
    mounted, waited, pressed, again, settled, redrawn = _drive(steps, answers.series_replies())
    assert _urls(mounted) == sorted(answers.SERIES)
    assert mounted["headers"] == [HEADER] * len(answers.SERIES)
    assert waited["redrawn"] == 5 and waited["fetched"] == []
    assert pressed["fetched"] == []
    assert _urls(again) == sorted(answers.SERIES)
    assert again["headers"] == [HEADER] * len(answers.SERIES)
    assert settled["redrawn"] == 5 and settled["fetched"] == []
    assert redrawn["fetched"] == []


def test_the_charts_drawn_stay_until_the_new_answer_s_series_land() -> None:
    """A new answer of the report shown keeps the charts the first run drew until its own series
    land, each taking the old one's place: here the second run's tables, which carry no quarters,
    leave the earnings call without its row of charts."""
    older = {k: v for k, v in answers.TABLES.items() if k != "quarters"}
    replies = {
        TABLES: [
            {"status": 200, "body": answers.TABLES},
            {"status": 200, "body": older, "held": True},
        ]
    }
    steps = [_mount(), {"do": "wait"}, _mount(answers.answer(), "land")]
    _, first, again, second = _drive([*steps, {"do": "release", "url": TABLES}], replies)
    assert len(_titles(first["tree"])) == 12 + 3
    assert [url for _, url in again["fetched"]].count(TABLES) == 1
    assert again["tree"] == first["tree"]
    assert len(_titles(second["tree"])) == 12
    earnings = _panel(second["tree"], HEADINGS.index("The last earnings call"))
    assert classed(earnings, "app-research__minis") == []


def test_a_failed_read_is_read_again_with_the_next_answer() -> None:
    """A series the server refused draws its sentence until a new answer of the report lands and
    its own read of that series lands: the sentence gives way to the charts."""
    replies = {
        TABLES: [
            {"status": 404, "body": {"detail": "no financial statements for LFOX"}},
            {"status": 200, "body": answers.TABLES, "held": True},
        ]
    }
    steps = [_mount(), {"do": "wait"}, _mount(answers.answer(), "land")]
    _, failed, again, landed = _drive([*steps, {"do": "release", "url": TABLES}], replies)
    sentence = "The financial tables did not load: no financial statements for LFOX."
    assert sentence in [text(e) for e in classed(failed["tree"], "app-report__error")]
    assert _titles(failed["tree"]) == []
    assert again["tree"] == failed["tree"]
    assert classed(landed["tree"], "app-report__error") == []
    assert len(_titles(landed["tree"])) == 12 + 3


def test_a_late_series_of_an_older_run_is_dropped() -> None:
    """The first run's financial tables, landing after a new answer of the same report started a
    second run, change nothing drawn and draw nothing again; the second run's draw the charts."""
    replies = {TABLES: {"status": 200, "body": answers.TABLES, "held": True}}
    steps = [_mount(), _mount(answers.answer(), "land"), {"do": "wait"}]
    steps += [{"do": "release", "url": TABLES}, {"do": "release", "url": TABLES}]
    _, again, waited, late, own = _drive(steps, replies)
    assert [url for _, url in again["fetched"]].count(TABLES) == 1
    assert _titles(waited["tree"]) == []
    assert late["redrawn"] == 0
    assert late["tree"] == waited["tree"]
    assert own["redrawn"] == 1
    assert len(_titles(own["tree"])) == 12 + 3


def test_a_refused_series_draws_the_server_s_sentence_in_the_charts_place() -> None:
    """Review Focus 4: the financial tables refused draw the server's sentence once in the
    financial section and as the earnings call's first row; the multiples history refused, with
    no sentence of its own, the status in its place beside the band; a sensitivity reading gone
    its sentence before the changes card. The text stands whole."""
    replies = answers.series_replies()
    replies[TABLES] = {"status": 404, "body": {"detail": "no financial statements for LFOX"}}
    replies[answers.COMPANY + "/multiples-history"] = {"status": 502, "body": None}
    replies[f"/api/sensitivities/{answers.READING_ID}"] = {
        "status": 404,
        "body": {"detail": "no sensitivity 9"},
    }
    _, landed = _drive([_mount(_with_reading()), {"do": "wait"}], replies)
    tree = landed["tree"]
    financial = _panel(tree, HEADINGS.index("Financial performance and health"))
    errors = [text(e) for e in classed(financial, "app-report__error")]
    assert errors == ["The financial tables did not load: no financial statements for LFOX."]
    earnings = _panel(tree, HEADINGS.index("The last earnings call"))
    first = _rows(earnings)[0]
    assert text(first) == "The figures by quarter did not load: no financial statements for LFOX."
    prices = _column(_panel(tree, HEADINGS.index("Price and multiples")))
    assert [text(card) for card in prices][1] == (
        "The P/E history did not load: the server answered 502."
    )
    assert _titles(prices[0]) == ["The price against the band by quarter"]
    valuation = _column(_panel(tree, HEADINGS.index("Valuation")))
    assert text(valuation[0]) == "A sensitivity reading did not load: no sensitivity 9."
    assert "app-research__changes" in valuation[1]["props"]["className"]
    for index in range(len(HEADINGS)):
        assert _drawn_blocks(_panel(tree, index)) == _laid_count(index), HEADINGS[index]


def test_a_series_of_another_report_is_dropped() -> None:
    """Report 31's financial tables, landing after report 19 is shown, change nothing drawn;
    report 19's own, landing after, draw its charts."""
    replies = {TABLES: {"status": 200, "body": answers.TABLES, "held": True}}
    steps = [
        _mount(),
        _mount(_report_19(), "land"),
        {"do": "wait"},
        {"do": "release", "url": TABLES},
        {"do": "release", "url": TABLES},
    ]
    _, shown, waited, late, own = _drive(steps, replies)
    assert [url for _, url in shown["fetched"]].count(TABLES) == 1  # report 19's own read
    assert late["redrawn"] == 1
    assert late["tree"] == waited["tree"]
    assert _titles(waited["tree"]) == []
    assert own["redrawn"] == 1
    assert len(_titles(own["tree"])) == 12 + 3  # the six groups' charts and the quarters'
