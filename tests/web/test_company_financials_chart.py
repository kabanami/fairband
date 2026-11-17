"""The Financials tab's chart (the Financials tab's design, 7.4, 7.5, 7.6, 7.7 and 7.9; Review
Focus 2, 3 and 4): the line a tab opens on, a row's press, a pick's series at a period, the
periods the chart stands on, the plot's scale and ticks, its bars and its line, the head, the box
under the pointer or the keys, the periods' labels on a narrow plot, and a pick that is off; and
the chart of several lines, a plot a unit, their bars side by side in their colours, the labels,
the box of several and a plot with no mark. company.js, company_chart.js, company_financials.js
and company_financials_chart.js run in node after the bundle and app.js (``support.page``), and
the tests read what the chart's functions return and the trees its builders draw;
``financials.mjs`` drives a row's press; the layout node cannot run is read from the page's CSS.

The answer is made here, ``ANSWER``, in US dollars: eleven fiscal years, 2016 to 2026, of an
income statement whose revenue rises from 215,639 to 478,834 million, with a loss in 2020; eight
quarters of its revenue alone; a cash flow line below zero every year; a revenue by product that
ends three years before the statements; and ratios by fiscal year, among them two margins, one
from 24.5% to 33.0%, and a multiple with gaps."""

import copy
import json
import math
import re
import subprocess
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
from support import page_answers as answers
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (
    STATIC / "company.js",
    STATIC / "company_chart.js",
    STATIC / "company_financials.js",
    STATIC / "company_financials_chart.js",
)
DRIVER = Path(__file__).parent / "financials.mjs"
DASH = "—"
CHAR = 6.6  # a monospaced 11px label's character
KEYS_WORDS = "The left and right arrow keys read each period."

YEARS = [str(year) for year in range(2016, 2027)]


def _columns(labels: list[str], currency: str = "USD") -> list[dict[str, Any]]:
    """A column a fiscal year, each ending on 30 September, in ``currency``."""
    return [{"label": y, "end": f"{y}-09-30", "currency": currency} for y in labels]


def _row(key: str, label: str, unit: str, values: list[Any], **more: str) -> dict[str, Any]:
    """A line as the read gives it, named on the chart as in the table unless told."""
    return (
        {"key": key, "label": label, "name": label, "kind": "line", "unit": unit}
        | {"values": values}
        | more
    )


def _head(label: str) -> dict[str, Any]:
    return {"key": None, "label": label, "name": None, "kind": "head", "unit": None, "values": None}


def _table(columns: list[dict[str, Any]], *rows: dict[str, Any]) -> dict[str, Any]:
    return {"columns": columns, "rows": list(rows)}


EMPTY: dict[str, Any] = {"columns": [], "rows": []}

REVENUE = [
    215_639e6,
    228_500e6,
    249_100e6,
    262_300e6,
    281_700e6,
    318_400e6,
    352_900e6,
    371_200e6,
    391_035e6,
    433_600e6,
    478_834e6,
]
MARGIN = [0.245, 0.252, 0.261, 0.270, 0.268, 0.281, 0.294, 0.305, 0.312, 0.321, 0.33]
OPERATING = [0.278, 0.267, 0.27, 0.251, 0.241, 0.298, 0.303, 0.298, 0.315, 0.32, 0.325]
NET = [45.6e9, 48.4e9, 59.5e9, 55.3e9, -2.1e9, 61.0e9, 72.4e9, 70.9e9, 93_736e6, 88.3e9, 101.2e9]
REPURCHASED = [-29.7e9, -32.9e9, -72.7e9, -66.9e9, -71.5e9, -85.5e9, -89.4e9, -77.6e9, -94.9e9,
               -90.2e9, -88.1e9]  # fmt: skip
EPS = [2.08, 2.30, 2.98, 2.97, -0.12, 3.28, 4.04, 3.90, 4.42, 5.10, 5.87]
SHARES = [21.9e9, 21.0e9, 20.0e9, 18.6e9, 17.5e9, 16.7e9, 16.3e9, 15.8e9, 15.4e9, 15.0e9, 14.7e9]
PE = [13.6, None, 18.9, None, 35.3, 28.9, None, 27.5, 37.9, 34.1, 33.2]

QUARTERS = [
    {"label": f"Q{q} {y}", "end": end, "currency": "USD"}
    for (q, y, end) in (
        (1, 2025, "2024-12-28"),
        (2, 2025, "2025-03-29"),
        (3, 2025, "2025-06-28"),
        (4, 2025, "2025-09-27"),
        (1, 2026, "2025-12-27"),
        (2, 2026, "2026-03-28"),
        (3, 2026, "2026-06-27"),
        (4, 2026, "2026-09-26"),
    )
]

INCOME = _table(
    _columns(YEARS),
    _row("revenue", "Revenue", "money", REVENUE, kind="total"),
    _row("grossProfit", "Gross profit", "money", [v * 0.4 for v in REVENUE], kind="total"),
    _row("netIncome", "Net income", "money", NET, kind="total"),
    _row("eps", "EPS", "perShare", EPS),
    _row("weightedAverageShsOut", "Shares, basic", "shares", SHARES),
)
INCOME_QUARTERS = _table(
    QUARTERS,
    _row(
        "revenue",
        "Revenue",
        "money",
        [124.3e9, 95.4e9, 94.0e9, 102.5e9, 140.1e9, 110.0e9, 109.6e9, 121.2e9],
        kind="total",
    ),
)
BALANCE = _table(
    _columns(YEARS),
    _head("ASSETS"),
    _row("cashAndCashEquivalents", "Cash", "money", [20e9 + i * 1e9 for i in range(11)]),
)
CASHFLOW = _table(
    _columns(YEARS), _row("commonStockRepurchased", "Stock repurchased", "money", REPURCHASED)
)
PRODUCT = _table(
    _columns(YEARS[:8]),
    _row("Anvils", "Anvils", "money", [140e9 + i * 5e9 for i in range(8)], name="Revenue: Anvils"),
    _row(
        "Rockets", "Rockets", "money", [60e9 + i * 2e9 for i in range(8)], name="Revenue: Rockets"
    ),
)
RATIOS = _table(
    _columns(YEARS),
    _head("MARGINS"),
    _row("grossProfitMargin", "Gross", "percent", MARGIN, name="Gross margin"),
    _row("operatingProfitMargin", "Operating", "percent", OPERATING, name="Operating margin"),
    _head("VALUATION"),
    _row("priceToEarningsRatio", "P/E", "multiple", PE),
    _head("LEVERAGE"),
    _row("debtToEquityRatio", "Debt to equity", "ratio", [1.2 + i * 0.1 for i in range(11)]),
    _head("EFFICIENCY"),
    _row("daysOfSalesOutstanding", "Days of sales outstanding", "days", [30 + i for i in range(11)]),
    _head("PER SHARE"),
    _row("revenuePerShare", "Revenue", "perShare", [9.8 + i for i in range(11)],
         name="Revenue a share"),
)  # fmt: skip


def _answer(
    income: dict[str, Any] = INCOME,
    quarters: dict[str, Any] = INCOME_QUARTERS,
    *,
    balance: dict[str, Any] = BALANCE,
    cashflow: dict[str, Any] = CASHFLOW,
    product: dict[str, Any] = PRODUCT,
    region: dict[str, Any] = EMPTY,
    ratios: dict[str, Any] = RATIOS,
    currency: str = "USD",
) -> dict[str, Any]:
    """The tab's answer with the tables given, ACME's."""
    return {
        "symbol": "ACME",
        "dataDate": "2026-11-14",
        "quote": {"price": None, "change": None, "changePercent": None, "day": None},
        "currency": currency,
        "cadence": "quarterly",
        "statements": {
            "income": {"annual": income, "quarter": quarters},
            "balance": {"annual": balance, "quarter": EMPTY},
            "cashflow": {"annual": cashflow, "quarter": EMPTY},
        },
        "segments": {"product": product, "region": region},
        "ratios": ratios,
    }


ANSWER = _answer()


def _pick(kind: str, key: str, table: str | None = None, slot: int = 0) -> dict[str, Any]:
    return {"kind": kind, "table": table, "key": key, "slot": slot}


REVENUE_PICK = _pick("income", "revenue")
MARGIN_PICK = _pick("ratios", "grossProfitMargin")
NET_PICK = _pick("income", "netIncome", slot=1)
OPERATING_PICK = _pick("ratios", "operatingProfitMargin", slot=2)
THREE = [REVENUE_PICK, NET_PICK, OPERATING_PICK]  # two units: money and percent
TAKE = "Take off the chart"
NONE_DRAWN = (
    "These lines have figures by fiscal year only. Choose Annual, or press a line in the table."
)


def _chart(helper: str, *args: Any) -> Any:
    """What ``companyFinancialsChart.<helper>`` returns on ``args``, the four scripts loaded after
    app.js, as the page loads them."""
    return node("companyFinancialsChart." + helper, list(args), *SCRIPTS)


def _tab(helper: str, *args: Any) -> Any:
    """What ``companyFinancials.<helper>`` returns on ``args``."""
    return node("companyFinancials." + helper, list(args), *SCRIPTS)


def _drawn(
    picks: list[dict[str, Any]], answer: dict[str, Any] = ANSWER, period: str = "annual"
) -> list[dict[str, Any]]:
    """The series of ``picks`` at ``period`` that draw."""
    found: list[dict[str, Any]] = _chart("series", answer, picks, period)
    return [s for s in found if s["off"] is None]


def _geometry(
    picks: list[dict[str, Any]],
    width: float = 1200,
    answer: dict[str, Any] = ANSWER,
    period: str = "annual",
) -> Any:
    return _chart("geometry", _drawn(picks, answer, period), width, answer["currency"])


def _block(
    picks: list[dict[str, Any]],
    answer: dict[str, Any] = ANSWER,
    period: str = "annual",
    scale: str = "m",
    at: int | None = None,
    width: float = 1200,
) -> Any:
    """The chart's block, with no handlers (none is called while it is drawn)."""
    return _chart("block", answer, picks, period, scale, at, width, None)


def _drive(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The trace of ``steps`` (``financials.mjs``), with no store."""
    assert NODE is not None
    scripts = (BUNDLE, STATIC / "app.js", *SCRIPTS)
    done = subprocess.run(
        [NODE, str(DRIVER), *(str(script) for script in scripts)],
        input=json.dumps({"store": None, "steps": steps}),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    trace: list[dict[str, Any]] = json.loads(done.stdout)
    return trace


def _typed(tree: Any, kind: str) -> list[dict[str, Any]]:
    return [e for e in elements(tree) if e.get("type") == kind]


def _classes(e: dict[str, Any]) -> set[str]:
    return set(str(e["props"].get("className") or "").split())


def _numbers(tree: Any) -> list[float]:
    """Every number in a tree of geometry, its paths' too."""
    if isinstance(tree, dict):
        return [n for value in tree.values() for n in _numbers(value)]
    if isinstance(tree, list):
        return [n for value in tree for n in _numbers(value)]
    if isinstance(tree, bool):
        return []
    if isinstance(tree, int | float):
        return [float(tree)]
    if isinstance(tree, str) and ("NaN" in tree or "Infinity" in tree):
        return [math.nan]
    if isinstance(tree, str) and re.fullmatch(r"[MLVHQZ\d.\s-]+", tree):
        return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", tree)]
    return []


def _finite(g: Any) -> bool:
    numbers = _numbers(g)
    return bool(numbers) and all(math.isfinite(n) for n in numbers)


def _points(path: str) -> list[tuple[str, float, float]]:
    """Each command of a path of moves and lines: its letter, its x and its y."""
    return [(c, float(x), float(y)) for c, x, y in re.findall(r"([ML])(-?[\d.]+) (-?[\d.]+)", path)]


def _ticks(plot: dict[str, Any]) -> list[str]:
    """The texts of a plot's ticks from its foot up."""
    return [tick["text"] for tick in sorted(plot["ticks"], key=lambda t: -t["y"]) if tick["text"]]


def _labels(tree: Any) -> list[tuple[str, ...]]:
    """The chart's labels, each the words of its spans after its swatch: its name and its figure
    or the words that say why it is off."""
    found = []
    for label in classed(tree, "app-fin__label"):
        spans = [
            k for k in label["props"]["children"] if isinstance(k, dict) and k["type"] == "span"
        ]
        found.append(tuple(text(k) for k in spans if "app-fin__key" not in _classes(k)))
    return found


# --------------------------------------------------------------------------- picking a line


def test_the_tab_opens_on_revenue_and_falls_back() -> None:
    """A company's tab opens on its income statement's Revenue alone; with no Revenue line on
    the first line of the annual income table; with no statement on the first line of the first
    table that has one, segments then ratios; with no line anywhere on none, and the tab draws
    no chart and does not throw. A pick alone on the chart takes slot 0."""
    assert _tab("first", ANSWER) == REVENUE_PICK
    no_revenue = _answer(_table(INCOME["columns"], *INCOME["rows"][1:]))
    assert _tab("first", no_revenue) == _pick("income", "grossProfit")
    headed = _answer(EMPTY, EMPTY, balance=BALANCE, cashflow=EMPTY)
    assert _tab("first", headed) == _pick("balance", "cashAndCashEquivalents")
    segments = _answer(EMPTY, EMPTY, balance=EMPTY, cashflow=EMPTY)
    assert _tab("first", segments) == _pick("segments", "Anvils", "product")
    ratios = _answer(EMPTY, EMPTY, balance=EMPTY, cashflow=EMPTY, product=EMPTY)
    assert _tab("first", ratios) == MARGIN_PICK
    bare = answers.profile_only_financials()
    assert _tab("first", bare) is None
    line = {"kind": "ratios", "table": None, "key": "priceToEarningsRatio"}
    assert _tab("alone", line) == [line | {"slot": 0}]
    assert _tab("alone", _pick("income", "eps", slot=2)) == [_pick("income", "eps")]

    trace = _drive([{"do": "mount", "answer": ANSWER}, {"do": "mount", "answer": bare}])
    assert [step["threw"] for step in trace] == [False, False]
    assert [step["picks"] for step in trace] == [[REVENUE_PICK], None]
    assert [step["on"] for step in trace] == [["Revenue"], []]
    tree = _tab("block", bare, {"kind": "income", "period": "annual", "scale": "m"}, [], None)
    [place] = classed(tree, "app-fin__chart")
    assert list(elements(place["props"]["children"])) == []


def test_a_press_on_a_row_charts_it_alone() -> None:
    """A click on a row, or Enter or Space while it has the focus, charts its line alone at
    slot 0; the row carries is-on and aria-selected true, every other row neither; another key
    does nothing. The line stays on the chart as the reader changes sub-tab and period, and it
    is dropped when another company's answer lands. A section head takes no press."""
    trace = _drive(
        [
            {"do": "mount", "answer": ANSWER},
            {"do": "row", "text": "Gross profit"},
            {"do": "row", "text": "Net income", "key": "Enter"},
            {"do": "row", "text": "EPS", "key": " "},
            {"do": "row", "text": "Revenue", "key": "a"},
            {"do": "press", "class": "app-fin__tab", "text": "Ratios"},
            {"do": "row", "text": "Gross"},
            {"do": "press", "class": "app-fin__tab", "text": "Segments"},
            {"do": "row", "text": "Rockets"},
            {"do": "press", "class": "app-fin__tab", "text": "Income statement"},
            {"do": "press", "class": "app-fin__period", "text": "Quarterly"},
            {"do": "mount", "answer": ANSWER | {"symbol": "BETA"}},
        ]
    )
    assert [step["threw"] for step in trace] == [False] * 12
    assert [step["picks"] for step in trace] == [
        [REVENUE_PICK],
        [_pick("income", "grossProfit")],
        [_pick("income", "netIncome")],
        [_pick("income", "eps")],
        [_pick("income", "eps")],
        [_pick("income", "eps")],
        [MARGIN_PICK],
        [MARGIN_PICK],
        [_pick("segments", "Rockets", "product")],
        [_pick("segments", "Rockets", "product")],
        [_pick("segments", "Rockets", "product")],
        [REVENUE_PICK],
    ]
    assert [step["on"] for step in trace] == [
        ["Revenue"],
        ["Gross profit"],
        ["Net income"],
        ["EPS"],
        ["EPS"],
        [],
        ["Gross"],
        [],
        ["Rockets"],
        [],
        [],
        ["Revenue"],
    ]
    assert [step["prevented"] for step in trace[2:5]] == [True, True, False]

    view = {"kind": "income", "period": "annual", "scale": "m"}
    tree = _tab("block", ANSWER, view, [_pick("income", "netIncome")], None)
    [table] = classed(tree, "app-fin__table")
    lines = [r for r in _typed(table, "tr")[1:]]
    assert [r["props"]["aria-selected"] for r in lines] == [
        "false",
        "false",
        "true",
        "false",
        "false",
    ]
    assert [r["props"]["tabIndex"] for r in lines] == [0] * 5
    assert _classes(lines[2]) == {"is-total", "is-on", "is-s0"}
    assert [_classes(r) for r in lines if r is not lines[2]] == [
        {"is-total"},
        {"is-total"},
        set(),
        set(),
    ]
    [chart] = [e for e in elements(classed(tree, "app-fin__chart")[0]["props"]["children"])]
    assert chart["props"] == {
        "answer": ANSWER,
        "picks": [_pick("income", "netIncome")],
        "period": "annual",
        "scale": "m",
        "children": [],
    }
    [balance] = classed(
        _tab("block", ANSWER, view | {"kind": "balance"}, [], None), "app-fin__table"
    )
    head = classed(balance, "is-head")[0]
    assert "tabIndex" not in head["props"] and "aria-selected" not in head["props"]
    script = _static_file("company_financials.js")
    for words in ("onKeyDown", "'Enter'", "' '", "preventDefault"):
        assert words in script, words


# --------------------------------------------------------------------------------- the series


def test_an_amount_is_bars_and_a_rate_is_a_line() -> None:
    """A pick's series at a period: its pick, its slot, its name on the chart, its unit and its
    form by the unit, money, per share and a share count as bars and every other unit as a line;
    its table's columns, and its figure a column's label with the column's currency."""
    picks = [
        REVENUE_PICK,
        _pick("income", "eps", slot=1),
        _pick("income", "weightedAverageShsOut", slot=2),
        _pick("ratios", "revenuePerShare", slot=3),
        MARGIN_PICK,
        _pick("ratios", "priceToEarningsRatio"),
        _pick("ratios", "debtToEquityRatio"),
        _pick("ratios", "daysOfSalesOutstanding"),
    ]
    found = _chart("series", ANSWER, picks, "annual")
    assert [(s["name"], s["unit"], s["form"]) for s in found] == [
        ("Revenue", "money", "bars"),
        ("EPS", "perShare", "bars"),
        ("Shares, basic", "shares", "bars"),
        ("Revenue a share", "perShare", "bars"),
        ("Gross margin", "percent", "line"),
        ("P/E", "multiple", "line"),
        ("Debt to equity", "ratio", "line"),
        ("Days of sales outstanding", "days", "line"),
    ]
    assert [s["pick"] for s in found] == picks
    assert [s["slot"] for s in found] == [0, 1, 2, 3, 0, 0, 0, 0]
    assert {s["off"] for s in found} == {None}
    revenue = found[0]
    assert revenue["columns"] == INCOME["columns"]
    assert revenue["at"]["2024"] == {"value": 391_035e6, "currency": "USD"}
    assert len(revenue["at"]) == 11
    quarter = _chart("series", ANSWER, [REVENUE_PICK], "quarter")[0]
    assert quarter["columns"] == QUARTERS
    assert quarter["off"] is None
    assert quarter["at"]["Q4 2026"] == {"value": 121.2e9, "currency": "USD"}
    product = _chart("series", ANSWER, [_pick("segments", "Rockets", "product")], "annual")[0]
    assert product["name"] == "Revenue: Rockets"
    assert list(product["at"]) == YEARS[:8]


def test_the_periods_are_the_union_of_the_lines_in_order_of_their_end() -> None:
    """The chart stands on every period a drawn line's table holds, known by its label, in order
    of the day each ends, whatever the order of the lines; a line that ends three years early or
    misses a year draws no mark there. A plot's unit in words."""
    early = {"columns": _columns(["2017", "2019"])}
    late = {"columns": _columns(["2016", "2018", "2019", "2020"])}
    assert [p["label"] for p in _chart("periods", [early, late])] == YEARS[:5]
    assert _chart("periods", [late, early]) == _chart("periods", [early, late])
    assert _chart("periods", [early])[0] == {"label": "2017", "end": "2017-09-30"}
    halves = {
        "columns": [
            {"label": "H2 2025", "end": "2025-12-31", "currency": "GBP"},
            {"label": "H1 2025", "end": "2025-06-30", "currency": "GBP"},
        ]
    }
    assert [p["label"] for p in _chart("periods", [halves])] == ["H1 2025", "H2 2025"]
    g = _geometry([_pick("segments", "Anvils", "product")])
    assert [p["label"] for p in g["periods"]] == YEARS[:8]
    assert [bar["i"] for bar in g["plots"][0]["series"][0]["bars"]] == list(range(8))
    for args, words in (
        (("money", "USD", "m"), "USD, millions"),
        (("money", "TWD", "b"), "TWD, billions"),
        (("perShare", "EUR", "b"), "EUR a share"),
        (("shares", "USD", "m"), "millions of shares"),
        (("shares", "USD", "b"), "billions of shares"),
        (("percent", "USD", "b"), "percent"),
        (("multiple", "USD", "m"), "multiple"),
        (("ratio", "USD", "m"), "ratio"),
        (("days", "USD", "m"), "days"),
    ):
        assert _chart("unitWords", *args) == words, args


# --------------------------------------------------------------------------------- the scales


def test_the_bar_plot_s_scale_holds_zero_and_its_ticks_are_compact() -> None:
    """Revenue: eleven bars, one a period, on a scale from 0 in four clean steps, the ticks bare
    and compact from the baseline up, the zero line in border and the others in chart-grid; no
    bar wider than 44px nor than 72% of its period's width. One plot: 160px, 18px above it, 22px
    under it for the periods' labels."""
    g = _geometry([REVENUE_PICK])
    [plot] = g["plots"]
    assert (g["width"], g["height"], plot["top"], plot["height"]) == (1200, 200, 18, 160)
    assert _ticks(plot) == ["0B", "200B", "400B", "600B"]
    [zero] = [tick for tick in plot["ticks"] if tick["zero"]]
    assert zero["text"] == "0B"
    assert zero["y"] == pytest.approx(plot["top"] + plot["height"], abs=0.5)
    [series] = plot["series"]
    assert [bar["i"] for bar in series["bars"]] == list(range(11))
    assert max(bar["width"] for bar in series["bars"]) == 44
    assert all(
        bar["y"] + bar["height"] == pytest.approx(zero["y"], abs=0.6) for bar in series["bars"]
    )
    narrow = _geometry([REVENUE_PICK], 400)["plots"][0]["series"][0]["bars"]
    band = (400 - 6 - 58) / 11
    assert max(bar["width"] for bar in narrow) == pytest.approx(band * 0.72)
    for picks, ticks in (
        ([_pick("income", "eps")], ["−2", "0", "2", "4", "6"]),
        ([_pick("income", "weightedAverageShsOut")], ["0B", "10B", "20B", "30B"]),
        ([_pick("segments", "Rockets", "product")], ["0B", "20B", "40B", "60B", "80B"]),
        ([_pick("ratios", "daysOfSalesOutstanding")], ["30", "35", "40"]),
        ([_pick("ratios", "debtToEquityRatio")], ["1.0", "1.5", "2.0", "2.5"]),
        ([_pick("ratios", "priceToEarningsRatio")], ["10x", "20x", "30x", "40x"]),
    ):
        assert _ticks(_geometry(picks)["plots"][0]) == ticks, picks
    small = _answer(
        _table(_columns(YEARS[:3]), _row("revenue", "Revenue", "money", [12e6, 31e6, 48e6]))
    )
    assert _ticks(_geometry([REVENUE_PICK], answer=small)["plots"][0]) == [
        "0M",
        "20M",
        "40M",
        "60M",
    ]
    taiwan = _answer(
        _table(
            _columns(YEARS[:3], "TWD"),
            _row("revenue", "Revenue", "money", [1.6e12, 2.2e12, 2.9e12]),
        ),
        currency="TWD",
    )
    assert _ticks(_geometry([REVENUE_PICK], answer=taiwan)["plots"][0]) == ["0T", "1T", "2T", "3T"]


def test_the_line_plot_s_scale_fits_its_figures() -> None:
    """The margin: a 2px line through its eleven figures on a scale that fits them, 20% to 35%,
    with no zero line, and an end marker on the newest figure."""
    g = _geometry([MARGIN_PICK])
    [plot] = g["plots"]
    assert _ticks(plot) == ["20%", "25%", "30%", "35%"]
    assert not any(tick["zero"] for tick in plot["ticks"])
    [series] = plot["series"]
    assert series["bars"] == []
    points = _points(series["path"])
    assert [letter for letter, _, _ in points] == ["M"] + ["L"] * 10
    assert [x for _, x, _ in points] == pytest.approx(g["xs"], abs=0.005)  # a path's 2 decimals
    ys = [y for _, _, y in points]
    assert ys[0] == max(ys) and ys[-1] == min(ys)  # the lowest margin first, the highest last
    assert series["dots"] == []
    assert series["end"]["i"] == 10
    assert (series["end"]["x"], series["end"]["y"]) == pytest.approx(
        (points[-1][1], points[-1][2]), abs=0.005
    )
    crossing = _answer(
        ratios=_table(
            _columns(YEARS[:4]),
            _row("netProfitMargin", "Net", "percent", [-0.04, 0.02, 0.07, 0.11], name="Net margin"),
        )
    )
    plot = _geometry([_pick("ratios", "netProfitMargin")], answer=crossing)["plots"][0]
    assert _ticks(plot) == ["−5%", "0%", "5%", "10%", "15%"]
    assert [tick["text"] for tick in plot["ticks"] if tick["zero"]] == ["0%"]


def test_a_figure_below_zero_hangs_from_the_baseline_in_the_negative_colour() -> None:
    """A lone line's bar below zero hangs from the baseline down and carries is-neg, which wears
    chart-neg-3; the scale holds zero and the figure, its ticks below zero led by a minus. A line
    below zero every year draws every bar so, the baseline at the plot's top."""
    g = _geometry([_pick("income", "netIncome")])
    [plot] = g["plots"]
    [zero] = [tick for tick in plot["ticks"] if tick["zero"]]
    bars = plot["series"][0]["bars"]
    assert [bar["neg"] for bar in bars] == [False] * 4 + [True] + [False] * 6
    loss = bars[4]
    assert loss["y"] == pytest.approx(zero["y"], abs=0.6)
    assert loss["height"] > 0
    assert all(
        bar["y"] + bar["height"] == pytest.approx(zero["y"], abs=0.6)
        for bar in bars
        if not bar["neg"]
    )
    assert _ticks(plot) == ["−50B", "0B", "50B", "100B", "150B"]
    tree = _block([_pick("income", "netIncome")])
    marks = classed(tree, "app-fin__col")
    assert [_classes(m) for m in marks].count({"app-fin__col", "is-s0", "is-neg"}) == 1
    assert [_classes(m) for m in marks].count({"app-fin__col", "is-s0"}) == 10
    repurchased = _geometry([_pick("cashflow", "commonStockRepurchased")])["plots"][0]
    assert all(bar["neg"] for bar in repurchased["series"][0]["bars"])
    assert _ticks(repurchased) == ["−100B", "−50B", "0B"]
    [zero] = [tick for tick in repurchased["ticks"] if tick["zero"]]
    assert zero["y"] == pytest.approx(repurchased["top"], abs=0.5)


def test_no_mark_for_a_gap_a_zero_amount_or_another_currency() -> None:
    """A period with no figure, an amount of exactly 0 and an amount in another currency than
    the tab's draw no mark, and no scale is built from such a figure; a line breaks at a gap,
    and a lone figure between gaps draws a dot."""
    gaps = _answer(
        _table(_columns(YEARS[:4]), _row("revenue", "Revenue", "money", [5e9, None, 0, 7e9]))
    )
    bars = _geometry([REVENUE_PICK], answer=gaps)["plots"][0]["series"][0]["bars"]
    assert [bar["i"] for bar in bars] == [0, 3]
    columns = _columns(YEARS[:4])
    columns[0]["currency"] = "EUR"
    euros = _answer(_table(columns, _row("revenue", "Revenue", "money", [25_129e6, 5e9, 6e9, 7e9])))
    plot = _geometry([REVENUE_PICK], answer=euros)["plots"][0]
    assert [bar["i"] for bar in plot["series"][0]["bars"]] == [1, 2, 3]
    assert _ticks(plot) == ["0B", "2B", "4B", "6B", "8B"]  # 25,129 million is not on the scale
    eps = _answer(_table(columns, _row("eps", "EPS", "perShare", [9.5, 1.1, 0, 1.4])))
    plot = _geometry([_pick("income", "eps")], answer=eps)["plots"][0]
    assert [bar["i"] for bar in plot["series"][0]["bars"]] == [1, 3]  # no bar at 0 either
    assert _ticks(plot) == ["0.0", "0.5", "1.0", "1.5"]
    shares = _answer(
        _table(columns, _row("weightedAverageShsOut", "Shares", "shares", [9e9, 1e9, 0, 1.2e9]))
    )
    plot = _geometry([_pick("income", "weightedAverageShsOut")], answer=shares)["plots"][0]
    assert [bar["i"] for bar in plot["series"][0]["bars"]] == [0, 1, 3]  # a count in any currency
    ratios = _answer(
        ratios=_table(_columns(YEARS), _row("priceToEarningsRatio", "P/E", "multiple", PE))
    )
    pe = _geometry([_pick("ratios", "priceToEarningsRatio")], answer=ratios)
    series = pe["plots"][0]["series"][0]
    points = _points(series["path"])
    assert [letter for letter, _, _ in points] == ["M", "L", "M", "L", "L", "L"]
    xs = [pe["xs"][i] for i in (4, 5, 7, 8, 9, 10)]
    assert [x for _, x, _ in points] == pytest.approx(xs, abs=0.005)
    assert [dot["i"] for dot in series["dots"]] == [0, 2]
    assert series["end"]["i"] == 10
    zeros = _answer(
        ratios=_table(
            _columns(YEARS[:4]),
            _row("priceToEarningsRatio", "P/E", "multiple", [12.0, 0, 14.0, 15.0]),
        )
    )
    series = _geometry([_pick("ratios", "priceToEarningsRatio")], answer=zeros)["plots"][0][
        "series"
    ][0]
    assert [dot["i"] for dot in series["dots"]] == [0]  # a multiple of exactly 0 is a dash
    nothing = _answer(_table(columns[:1], _row("revenue", "Revenue", "money", [25_129e6])))
    plot = _geometry([REVENUE_PICK], answer=nothing)["plots"][0]
    assert plot["series"][0]["bars"] == []
    assert len(plot["ticks"]) == 1 and plot["ticks"][0]["zero"]  # its frame, the baseline
    tree = _block([REVENUE_PICK], answer=nothing)
    assert len(_typed(tree, "svg")) == 1


def test_a_flat_or_single_series_divides_by_nothing() -> None:
    """Every figure equal, as a line and as bars, and one figure only: the scale is widened by a
    step where it would be flat, and every number of the geometry is finite. One figure draws
    one bar, or one marker."""
    flat_line = _answer(
        ratios=_table(
            _columns(YEARS),
            _row("grossProfitMargin", "Gross", "percent", [0.2] * 11, name="Gross margin"),
        )
    )
    g = _geometry([MARGIN_PICK], answer=flat_line)
    assert _finite(g)
    assert _ticks(g["plots"][0]) == ["15%", "20%", "25%"]
    assert len(_points(g["plots"][0]["series"][0]["path"])) == 11
    flat_bars = _answer(_table(_columns(YEARS), _row("revenue", "Revenue", "money", [5e9] * 11)))
    g = _geometry([REVENUE_PICK], answer=flat_bars)
    assert _finite(g)
    assert len(g["plots"][0]["series"][0]["bars"]) == 11
    one = _answer(
        _table(_columns(YEARS[-1:]), _row("revenue", "Revenue", "money", [478_834e6])),
        ratios=_table(
            _columns(YEARS[-1:]),
            _row("grossProfitMargin", "Gross", "percent", [0.33], name="Gross margin"),
        ),
    )
    g = _geometry([REVENUE_PICK], answer=one)
    assert _finite(g)
    assert len(g["plots"][0]["series"][0]["bars"]) == 1
    assert g["xs"] == [6 + (1200 - 6 - 58) / 2]
    g = _geometry([MARGIN_PICK], answer=one)
    assert _finite(g)
    [series] = g["plots"][0]["series"]
    assert (series["path"], series["dots"], series["end"]["i"]) == ("", [], 0)
    tree = _block([MARGIN_PICK], answer=one)
    assert len([e for e in _typed(tree, "circle")]) == 1
    zero = _answer(
        ratios=_table(
            _columns(YEARS[:3]),
            _row(
                "operatingProfitMargin", "Operating", "percent", [0, 0, 0], name="Operating margin"
            ),
        )
    )
    assert _finite(_geometry([_pick("ratios", "operatingProfitMargin")], answer=zero))


# ----------------------------------------------------------------------------------- the head


def test_the_head_of_one_line() -> None:
    """One line: its name, its newest figure in figure-lg at its table's decimals and in the
    unit chosen, and the caption of the newest period and the plot's unit; the newest period is
    the union's, and a line with no figure there reads a dash. No legend."""

    def head(tree: Any) -> list[str]:
        [found] = classed(tree, "app-fin__chead")
        return [text(part) for part in found["props"]["children"]]

    assert head(_block([REVENUE_PICK])) == ["Revenue", "478,834", "2026, USD, millions"]
    assert head(_block([REVENUE_PICK], scale="b")) == ["Revenue", "478.83", "2026, USD, billions"]
    [figure] = classed(_block([REVENUE_PICK]), "figure-lg")
    assert text(figure) == "478,834"
    assert head(_block([MARGIN_PICK])) == ["Gross margin", "33.0%", "2026, percent"]
    assert head(_block([_pick("income", "eps")], scale="b")) == ["EPS", "5.87", "2026, USD a share"]
    assert head(_block([_pick("income", "weightedAverageShsOut")])) == [
        "Shares, basic",
        "14,700",
        "2026, millions of shares",
    ]
    assert head(_block([REVENUE_PICK], period="quarter")) == [
        "Revenue",
        "121,200",
        "Q4 2026, USD, millions",
    ]
    small = _answer(
        _table(_columns(YEARS[:3]), _row("revenue", "Revenue", "money", [12e6, 31e6, 48.25e6]))
    )
    assert head(_block([REVENUE_PICK], answer=small)) == ["Revenue", "48.3", "2018, USD, millions"]
    gap = _answer(
        _table(_columns(YEARS[:3]), _row("revenue", "Revenue", "money", [12e9, 31e9, None]))
    )
    assert head(_block([REVENUE_PICK], answer=gap))[1] == DASH
    assert classed(_block([REVENUE_PICK]), "app-fin__legend") == []


# ------------------------------------------------------------------------------ hover and keys


def test_the_hover_box_and_the_keys() -> None:
    """The box of a period: its label and its figure, the figure in another currency led by its
    code; none for a period with no figure. Picked by the pointer or the keys, the box stands
    over its mark and the other bars fade; on a line a crosshair and a marker on its point. The
    plot takes the focus; the arrows move a period, from the newest where none is picked."""
    g = _geometry([REVENUE_PICK])
    found = _chart("box", g, 8, "m")
    assert found["text"] == "2024 · 391,035"
    assert found["x"] == pytest.approx(g["xs"][8])
    assert found["y"] == pytest.approx(g["plots"][0]["series"][0]["bars"][8]["y"])
    assert 0 <= found["left"] <= g["width"]
    assert _chart("box", g, 8, "b")["text"] == "2024 · 391.04"
    assert _chart("box", g, None, "m") is None
    assert _chart("box", g, 11, "m") is None
    columns = _columns(YEARS[:4])
    columns[0]["currency"] = "EUR"
    euros = _answer(
        _table(columns, _row("revenue", "Revenue", "money", [25_129e6, None, 6e9, 7e9]))
    )
    g = _geometry([REVENUE_PICK], answer=euros)
    assert _chart("box", g, 0, "m")["text"] == "2016 · EUR 25,129"
    assert _chart("box", g, 1, "m") is None
    assert _chart("box", _geometry([MARGIN_PICK]), 4, "m")["text"] == "2020 · 26.8%"

    tree = _block([REVENUE_PICK], at=8)
    [tip] = classed(tree, "app-fin__tip")
    assert text(tip) == "2024 · 391,035"
    assert "figure-sm" in _classes(tip)
    bars = classed(tree, "app-fin__col")
    assert ["is-dim" in _classes(bar) for bar in bars] == [True] * 8 + [False] + [True] * 2
    assert classed(tree, "app-fin__cross") == []
    assert classed(_block([REVENUE_PICK]), "app-fin__tip") == []
    assert classed(_block([REVENUE_PICK]), "is-dim") == []
    assert classed(_block([REVENUE_PICK], at=11), "app-fin__tip") == []
    line = _block([MARGIN_PICK], at=4)
    [cross] = classed(line, "app-fin__cross")
    g = _geometry([MARGIN_PICK])
    assert cross["props"]["x1"] == cross["props"]["x2"] == pytest.approx(g["xs"][4])
    [mark] = classed(line, "app-fin__mark")
    assert mark["props"]["r"] == 5

    for at, key, found in ((None, "ArrowLeft", 10), (None, "ArrowRight", 10), (4, "ArrowLeft", 3),
                           (4, "Home", 0), (4, "End", 10), (4, "Escape", None)):  # fmt: skip
        assert node("companyChart.keyed", [at, key, 11], *SCRIPTS) == found, (at, key)
    g = _geometry([REVENUE_PICK])
    for x, i in ((0, 0), (g["xs"][3], 3), (g["xs"][3] + g["band"] * 0.45, 3), (5_000, 10)):
        assert _chart("nearest", g, x) == i, x
    [plot] = classed(_block([REVENUE_PICK]), "app-fin__plot")
    assert plot["props"]["tabIndex"] == 0
    assert plot["props"]["role"] == "group"
    assert plot["props"]["aria-label"] == f"Revenue in USD, millions, 2016 to 2026. {KEYS_WORDS}"
    [svg] = _typed(plot, "svg")
    assert svg["props"]["aria-hidden"] == "true"
    script = _static_file("company_financials_chart.js")
    start = script.index("  function plot(")
    body = script[start : script.index("\n  }\n", start)]
    for handler in (
        "onKeyDown",
        "onBlur",
        "onMouseMove",
        "onMouseLeave",
        "preventDefault",
        "keyed",
    ):
        assert handler in body, handler


def test_the_periods_labels_thin_on_a_narrow_plot() -> None:
    """The periods' labels stand under the plot, a label a period where there is room; on a
    narrow plot every second or every third is left out, counted from the newest back, so the
    newest stays and no two stand closer than a label's width."""
    g = _geometry([REVENUE_PICK], 1200)
    assert [label["text"] for label in g["labels"]] == YEARS
    assert [label["x"] for label in g["labels"]] == pytest.approx(g["xs"])
    for width in (300, 360):
        g = _geometry([REVENUE_PICK], width)
        labels = g["labels"]
        assert 1 < len(labels) < 11
        assert labels[-1]["text"] == "2026"
        for a, b in pairwise(labels):
            assert b["x"] - a["x"] >= len(b["text"]) * CHAR
            assert (b["i"] - a["i"]) in (2, 3)
        assert all(0 <= label["x"] <= g["width"] for label in labels)
    quarters = _geometry([REVENUE_PICK], 340, period="quarter")["labels"]
    assert quarters[-1]["text"] == "Q4 2026"
    for a, b in pairwise(quarters):
        assert b["x"] - a["x"] >= len(b["text"]) * CHAR
    tree = _block([REVENUE_PICK], width=300)
    assert [text(t) for t in classed(tree, "app-fin__when")] == [
        label["text"] for label in _geometry([REVENUE_PICK], 300)["labels"]
    ]


# ------------------------------------------------------------------------------- off the chart


def test_a_pick_that_is_off_draws_no_plot() -> None:
    """Under Quarterly a ratio or a segment is off, by year only, and a statement's line the
    quarterly table lacks is off, no figures by quarter; an off line draws nothing, and where the
    one pick is off the chart holds the head of its line, its name and why it is off, and the
    sentence in the plot's place. The same lines by fiscal year draw."""
    found = _chart(
        "series",
        ANSWER,
        [
            MARGIN_PICK,
            _pick("segments", "Anvils", "product"),
            _pick("income", "grossProfit"),
            REVENUE_PICK,
        ],
        "quarter",
    )
    assert [s["off"] for s in found] == [
        "by year only",
        "by year only",
        "no figures by quarter",
        None,
    ]
    assert [s["name"] for s in found] == [
        "Gross margin",
        "Revenue: Anvils",
        "Gross profit",
        "Revenue",
    ]
    assert _drawn([MARGIN_PICK], period="quarter") == []
    assert _chart("geometry", [], 1200, "USD") is None
    assert _chart("series", ANSWER, [_pick("income", "nothing")], "annual") == []
    # a line only its quarterly table holds stands by fiscal year with no figure: a frame alone
    newer = copy.deepcopy(INCOME_QUARTERS)
    newer["rows"].append(_row("otherIncome", "Other income", "money", [None] * 7 + [1.5e9]))
    late = _answer(INCOME, newer)
    [line] = _chart("series", late, [_pick("income", "otherIncome")], "annual")
    assert (line["off"], line["columns"], line["at"]) == (None, INCOME["columns"], {})
    assert line["name"] == "Other income"
    tree = _block([_pick("income", "otherIncome")], answer=late)
    assert [text(e) for e in classed(tree, "app-fin__chead")[0]["props"]["children"]][1] == DASH
    assert classed(tree, "app-fin__col") == [] and len(classed(tree, "app-fin__zero")) == 1
    for pick, name, why in (
        (MARGIN_PICK, "Gross margin", "by year only"),
        (_pick("income", "grossProfit"), "Gross profit", "no figures by quarter"),
    ):
        for tree in (
            _block([pick], period="quarter"),
            _chart("view", {"answer": ANSWER, "picks": [pick], "period": "quarter", "scale": "m"}),
        ):
            [head] = classed(tree, "app-fin__chead")
            assert [text(part) for part in head["props"]["children"] if part] == [name, why]
            assert _typed(tree, "svg") == [] and classed(tree, "app-fin__legend") == []
            assert [text(b) for b in classed(tree, "app-fin__blank")] == [NONE_DRAWN]
        assert _typed(
            _chart("view", {"answer": ANSWER, "picks": [pick], "period": "annual", "scale": "m"}),
            "svg",
        )
    assert _chart("view", {"answer": ANSWER, "picks": [], "period": "annual", "scale": "m"}) is None
    opened = _chart(
        "view", {"answer": ANSWER, "picks": [REVENUE_PICK], "period": "annual", "scale": "m"}
    )
    [svg] = _typed(opened, "svg")
    assert svg["props"]["viewBox"] == "0 0 900 200"  # the width drawn before one is measured


# ---------------------------------------------------------------------------- marks and the page


def test_the_marks_follow_the_design_system() -> None:
    """Every mark carries its slot's class, is-s0 for a lone line, which the CSS paints chart-1;
    a line 2px with round joins and caps; its end marker 10px across, ringed in surface-raised;
    the grid solid; the ticks and the labels in text that wears no colour of a series. Nothing
    is a table."""
    bars = _block([REVENUE_PICK])
    assert {frozenset(_classes(bar)) for bar in classed(bars, "app-fin__col")} == {
        frozenset({"app-fin__col", "is-s0"})
    }
    assert all(bar["type"] == "path" for bar in classed(bars, "app-fin__col"))
    line = _block([MARGIN_PICK])
    [path] = classed(line, "app-fin__line")
    assert _classes(path) == {"app-fin__line", "is-s0"}
    [end] = classed(line, "app-fin__end")
    assert _classes(end) == {"app-fin__end", "is-s0"}
    assert end["props"]["r"] == 5
    gaps = _block([_pick("ratios", "priceToEarningsRatio")])
    assert {frozenset(_classes(dot)) for dot in classed(gaps, "app-fin__dot")} == {
        frozenset({"app-fin__dot", "is-s0"})
    }
    for tree in (bars, line):
        assert all("strokeDasharray" not in e["props"] for e in elements(tree))
        assert all(
            "fill" not in t["props"] and "style" not in t["props"] for t in _typed(tree, "text")
        )
        assert _typed(tree, "table") == []
        assert len(classed(tree, "app-fin__zero")) + len(classed(tree, "app-fin__grid")) == len(
            classed(tree, "app-fin__tick")
        )
    html = _static_file("index.html")
    rules = {
        selector.strip(): " ".join(body.split())
        for selector, body in re.findall(r"\n  (\.app-fin(?![a-z])[^{]*)\{([^}]*)\}", html)
    }
    assert "--fin-series: var(--chart-1);" in rules[".app-fin .is-s0"]
    assert (
        "fill: var(--fin-series);"
        in rules[".app-fin__col, .app-fin__dot, .app-fin__end, .app-fin__mark"]
    )
    assert "stroke: var(--fin-series);" in rules[".app-fin__line"]
    assert "stroke-width: 2;" in rules[".app-fin__line"]
    assert "fill: var(--chart-neg-3);" in rules[".app-fin__col.is-neg"]
    assert "opacity: 0.45;" in rules[".app-fin__col.is-dim"]
    assert "display: flex;" in rules[".app-fin__bar"]  # the controls row's, and none of the marks'
    assert not [s for s in rules if "app-fin__bar" in s and s != ".app-fin__bar"]
    assert "stroke: var(--surface-raised);" in rules[".app-fin__end, .app-fin__mark"]
    assert "stroke: var(--chart-grid);" in rules[".app-fin__grid"]
    assert "stroke: var(--border);" in rules[".app-fin__zero, .app-fin__cross"]
    assert "fill: var(--ink-faint);" in rules[".app-fin__plot text"]
    assert "font-family: var(--font-mono);" in rules[".app-fin__plot text"]
    assert "position: absolute;" in rules[".app-fin__tip"]
    assert "pointer-events: none;" in rules[".app-fin__tip"]
    assert "outline: 2px solid var(--focus-ring);" in rules[".app-fin__plot:focus-visible"]
    assert "display: none;" in rules[".app-fin__chart:empty"]
    assert (
        "box-shadow: inset 2px 0 0 var(--fin-series);"
        in rules[".app-fin__table tbody tr.is-on th:first-child"]
    )
    assert (
        "background: var(--surface-selected);"
        in rules[".app-fin__table tbody tr.is-on th, .app-fin__table tbody tr.is-on td"]
    )
    # a focused row ringed by its cells, the names' sticky column covering a ring on the row
    ring = "inset 0 2px 0 var(--focus-ring), inset 0 -2px 0 var(--focus-ring);"
    focus = ".app-fin__table tbody tr:focus-visible"
    assert "outline: none;" in rules[focus]
    assert ring in rules[f"{focus} > th, {focus} > td"]
    assert "inset 2px 0 0 var(--focus-ring)" in rules[f"{focus} > th:first-child"]
    assert "inset -2px 0 0 var(--focus-ring)" in rules[f"{focus} > td:last-child"]
    order = list(rules)
    assert order.index(f"{focus} > th:first-child") > order.index(
        ".app-fin__table tbody tr.is-on th:first-child"
    )
    assert all("transition" not in body and "animation" not in body for body in rules.values())
    colours = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", " ".join(rules.values()))
    assert colours == []


# --------------------------------------------------------------------------- several lines


def test_one_plot_a_unit_in_pick_order() -> None:
    """Revenue, net income and the operating margin: the lines of one unit share a plot and a
    scale, and each other unit takes a plot of its own under it, in the order the units were
    first picked, the lines of a plot in their order; every plot stands on the same periods,
    whose labels stand once, under the last. With two or more lines each plot states its unit
    at its top left; with one, the head does."""
    g = _geometry(THREE)
    assert [p["unit"] for p in g["plots"]] == ["money", "percent"]
    assert [p["form"] for p in g["plots"]] == ["bars", "line"]
    assert [p["height"] for p in g["plots"]] == [120, 120]
    assert [p["top"] for p in g["plots"]] == [18, 18 + 120 + 8 + 18]
    assert g["height"] == 18 + 120 + 8 + 18 + 120 + 22
    money, percent = g["plots"]
    assert [s["name"] for s in money["series"]] == ["Revenue", "Net income"]
    assert sum(len(s["bars"]) for s in money["series"]) == 22
    [margin] = percent["series"]
    assert margin["bars"] == [] and len(_points(margin["path"])) == 11
    assert _finite(g)
    tree = _block(THREE)
    assert len(_typed(tree, "svg")) == 1
    measures = classed(tree, "app-fin__measure")
    assert [text(t) for t in measures] == ["USD, millions", "percent"]
    assert [t["props"]["y"] for t in measures] == [p["top"] - 6 for p in g["plots"]]
    assert {t["props"]["x"] for t in measures} == {g["left"]}
    billions = _block(THREE, scale="b")
    assert [text(t) for t in classed(billions, "app-fin__measure")] == ["USD, billions", "percent"]
    whens = classed(tree, "app-fin__when")
    assert len(whens) == 11 and {t["props"]["y"] for t in whens} == {g["height"] - 6}
    turned = _geometry([OPERATING_PICK, REVENUE_PICK | {"slot": 1}, NET_PICK | {"slot": 0}])
    assert [p["unit"] for p in turned["plots"]] == ["percent", "money"]
    assert [s["name"] for s in turned["plots"][1]["series"]] == ["Revenue", "Net income"]
    assert classed(_block([REVENUE_PICK]), "app-fin__measure") == []


def test_the_plots_heights_and_steps() -> None:
    """A plot is 160px high alone, 120px each of two, 100px each of three and 90px each of four,
    every plot 18px under the room above it and 8px over the next; a plot of 160px has four
    clean steps, one under 150px three."""
    years = YEARS[:4]
    answer = _answer(
        _table(_columns(years), _row("revenue", "Revenue", "money", [40e9, 80e9, 120e9, 160e9])),
        ratios=_table(
            _columns(years),
            _row("grossProfitMargin", "Gross", "percent", [0.3, 0.32, 0.31, 0.33],
                 name="Gross margin"),
            _row("priceToEarningsRatio", "P/E", "multiple", [20.0, 22.0, 25.0, 24.0]),
            _row("debtToEquityRatio", "Debt to equity", "ratio", [1.2, 1.3, 1.1, 1.0]),
        ),
    )  # fmt: skip
    picks = [
        REVENUE_PICK,
        MARGIN_PICK | {"slot": 1},
        _pick("ratios", "priceToEarningsRatio", slot=2),
        _pick("ratios", "debtToEquityRatio", slot=3),
    ]
    for n, height, ticks in (
        (1, 160, ["0B", "50B", "100B", "150B", "200B"]),
        (2, 120, ["0B", "100B", "200B"]),
        (3, 100, ["0B", "100B", "200B"]),
        (4, 90, ["0B", "100B", "200B"]),
    ):
        g = _geometry(picks[:n], answer=answer)
        assert [p["height"] for p in g["plots"]] == [height] * n, n
        assert _ticks(g["plots"][0]) == ticks, n
        assert g["height"] == 18 + n * height + (n - 1) * (8 + 18) + 22, n
        assert _finite(g), n
    four = _geometry(picks, answer=answer)
    assert [p["unit"] for p in four["plots"]] == ["money", "percent", "multiple", "ratio"]
    assert len(classed(_block(picks, answer=answer), "app-fin__measure")) == 4


def test_bars_of_one_period_stand_side_by_side_in_their_colours() -> None:
    """Two to four bars of a period stand side by side about its middle, in the lines' order,
    each at most 28px wide and 2px apart, each in its line's colour above zero and below: with
    two or more lines no bar takes the negative colour."""
    picks = [REVENUE_PICK, NET_PICK]
    g = _geometry(picks)
    revenue, net = g["plots"][0]["series"]
    for i in range(11):
        a, b = revenue["bars"][i], net["bars"][i]
        assert (a["i"], b["i"]) == (i, i)
        assert a["width"] == b["width"] == 28
        assert b["x"] - (a["x"] + a["width"]) == pytest.approx(2)
        assert (a["x"] + b["x"] + b["width"]) / 2 == pytest.approx(g["xs"][i])
    loss = net["bars"][4]
    assert loss["neg"] is False
    [zero] = [tick for tick in g["plots"][0]["ticks"] if tick["zero"]]
    assert loss["y"] == pytest.approx(zero["y"], abs=0.6) and loss["height"] > 0
    tree = _block(picks)
    marks = [_classes(m) for m in classed(tree, "app-fin__col")]
    assert marks == [{"app-fin__col", "is-s0"}] * 11 + [{"app-fin__col", "is-s1"}] * 11

    band = (400 - 6 - 58) / 11
    narrow = _geometry(picks, 400)["plots"][0]["series"]
    widths = [bar["width"] for s in narrow for bar in s["bars"]]
    assert widths == pytest.approx([(band * 0.72 - 2) / 2] * 22)
    four = [
        REVENUE_PICK,
        _pick("income", "grossProfit", slot=1),
        NET_PICK | {"slot": 2},
        _pick("segments", "Anvils", "product", slot=3),
    ]
    g = _geometry(four, 400)
    [plot] = g["plots"]
    width = (band * 0.72 - 6) / 4
    first = [s["bars"][0] for s in plot["series"]]
    assert [bar["width"] for bar in first] == pytest.approx([width] * 4)
    for a, b in pairwise(first):
        assert b["x"] - (a["x"] + a["width"]) == pytest.approx(2)
    assert (first[0]["x"] + first[-1]["x"] + width) / 2 == pytest.approx(g["xs"][0])
    newest = [bar for s in plot["series"] for bar in s["bars"] if bar["i"] == 10]
    assert [bar["x"] for bar in newest] == pytest.approx(  # the segment ends early: a gap
        [g["xs"][10] - (4 * width + 6) / 2 + q * (width + 2) for q in range(3)]
    )
    marks = [_classes(m) for m in classed(_block(four, width=400), "app-fin__col")]
    assert [m - {"app-fin__col"} for m in marks] == (
        [{"is-s0"}] * 11 + [{"is-s1"}] * 11 + [{"is-s2"}] * 11 + [{"is-s3"}] * 8
    )


def test_the_periods_are_the_union_whatever_the_order() -> None:
    """A statement's line over 2016 to 2026 and a segment's over 2017 and 2023 to 2025: the chart
    stands on the eleven periods whichever is picked first; the segment draws its four marks and
    none where it has no figure, and its label reads a dash for 2026, the newest period."""
    late = _table(
        _columns(["2017", "2023", "2024", "2025"]),
        _row("Anvils", "Anvils", "money", [150e9, 170e9, 175e9, 180e9], name="Revenue: Anvils"),
    )
    answer = _answer(product=late)
    segment = _pick("segments", "Anvils", "product")
    for picks in ([REVENUE_PICK, segment | {"slot": 1}], [segment, REVENUE_PICK | {"slot": 1}]):
        g = _geometry(picks, answer=answer)
        assert [p["label"] for p in g["periods"]] == YEARS
        [plot] = g["plots"]
        [anvils] = [s for s in plot["series"] if s["name"] == "Revenue: Anvils"]
        assert [bar["i"] for bar in anvils["bars"]] == [1, 7, 8, 9]
        assert [i for i, top in enumerate(anvils["tops"]) if top is not None] == [1, 7, 8, 9]
        tree = _block(picks, answer=answer)
        labels = dict(_labels(tree))
        assert (labels["Revenue: Anvils"], labels["Revenue"]) == (DASH, "478,834")
        assert [text(c) for c in classed(tree, "app-fin__unit")] == ["figures for 2026"]


def test_the_labels_of_several_lines() -> None:
    """Two or more lines: the head is a label a line, in their order, each its swatch, a square
    for bars and a round dot for a line, its name, its figure at the newest period as its table
    writes it in the unit chosen, another currency's led by its code, and a x that takes it off;
    then the caption of the newest period. The labels are the legend: none with one line. No
    text wears a series colour; the swatch does."""
    tree = _block(THREE)
    assert _labels(tree) == [
        ("Revenue", "478,834"),
        ("Net income", "101,200"),
        ("Operating margin", "32.5%"),
    ]
    labels = classed(tree, "app-fin__label")
    assert [_classes(label) for label in labels] == [
        {"control", "app-fin__label", f"is-s{n}"} for n in range(3)
    ]
    assert [label["type"] for label in labels] == ["li"] * 3
    [legend] = classed(tree, "app-fin__legend")
    assert legend["type"] == "ul"
    assert [_classes(k) for k in classed(tree, "app-fin__key")] == [
        {"app-fin__key"},
        {"app-fin__key"},
        {"app-fin__key", "app-fin__key--round"},
    ]
    figures = [e for label in labels for e in elements(label) if "figure-sm" in _classes(e)]
    assert [text(f) for f in figures] == ["478,834", "101,200", "32.5%"]
    xs = classed(tree, "app-fin__x")
    assert [
        (x["type"], x["props"]["type"], x["props"]["aria-label"], x["props"]["title"], text(x))
        for x in xs
    ] == [("button", "button", TAKE, TAKE, "×")] * 3
    assert [text(c) for c in classed(tree, "app-fin__unit")] == ["figures for 2026"]
    assert classed(tree, "figure-lg") == [] and classed(tree, "heading") == []
    assert _labels(_block(THREE, scale="b"))[:2] == [
        ("Revenue", "478.83"),
        ("Net income", "101.20"),
    ]
    columns = _columns(YEARS[-2:])
    columns[-1]["currency"] = "EUR"
    euros = _answer(
        product=_table(
            columns, _row("Anvils", "Anvils", "money", [20e9, 25_129e6], name="Revenue: Anvils")
        )
    )
    picks = [REVENUE_PICK, _pick("segments", "Anvils", "product", slot=1)]
    assert dict(_labels(_block(picks, answer=euros)))["Revenue: Anvils"] == "EUR 25,129"

    css = {
        selector.strip(): " ".join(body.split())
        for selector, body in re.findall(
            r"\n  (\.app-fin(?![a-z])[^{]*)\{([^}]*)\}", _static_file("index.html")
        )
    }
    assert "list-style: none;" in css[".app-fin__legend"]
    assert "color: var(--ink);" in css[".app-fin__label"]
    assert "color: var(--ink-faint);" in css[".app-fin__label.is-off"]
    assert "opacity: 0.4;" in css[".app-fin__label.is-off .app-fin__key"]
    assert "font-family: var(--font-sans);" in css[".app-fin__plot .app-fin__measure"]


def test_by_quarter_a_ratio_is_off_and_draws_nothing() -> None:
    """Under Quarterly a ratio stays among the labels, faded, by year only in its figure's place,
    and draws nothing: one plot, the statement's line's; a statement's line the quarterly table
    lacks reads no figures by quarter. Where no line can draw there is no plot: the sentence
    stands in its place under the labels, and no caption of a period."""
    picks = [REVENUE_PICK, MARGIN_PICK | {"slot": 1}, _pick("income", "grossProfit", slot=2)]
    tree = _block(picks, period="quarter")
    assert _labels(tree) == [
        ("Revenue", "121,200"),
        ("Gross margin", "by year only"),
        ("Gross profit", "no figures by quarter"),
    ]
    labels = classed(tree, "app-fin__label")
    assert ["is-off" in _classes(label) for label in labels] == [False, True, True]
    [why] = [e for e in elements(labels[1]) if text(e) == "by year only" and e is not labels[1]]
    assert _classes(why) == {"caption"}
    assert len(classed(tree, "app-fin__x")) == 3
    assert [text(c) for c in classed(tree, "app-fin__unit")] == ["figures for Q4 2026"]
    g = _geometry(picks, period="quarter")
    assert [p["unit"] for p in g["plots"]] == ["money"]
    assert len(_typed(tree, "svg")) == 1 and classed(tree, "app-fin__blank") == []
    assert [text(t) for t in classed(tree, "app-fin__measure")] == ["USD, millions"]

    ratios = [MARGIN_PICK, _pick("ratios", "priceToEarningsRatio", slot=1)]
    tree = _block(ratios, period="quarter")
    assert _typed(tree, "svg") == [] and classed(tree, "app-fin__plot") == []
    [blank] = classed(tree, "app-fin__blank")
    assert (blank["type"], text(blank)) == ("p", NONE_DRAWN)
    assert "app-fin__none" not in _classes(blank)
    assert _labels(tree) == [("Gross margin", "by year only"), ("P/E", "by year only")]
    assert classed(tree, "app-fin__unit") == []
    order = [id(e) for e in elements(tree)]
    assert order.index(id(classed(tree, "app-fin__legend")[0])) < order.index(id(blank))


def test_the_box_of_several_lines() -> None:
    """Two or more lines drawn: the box of a period holds the period, then a row a line drawn,
    plot by plot, each its swatch, its name and its figure as its table writes it, another
    currency's led by its code; it stands beside the period on the side with room, at the first
    plot's top; none where no line has a figure. A crosshair runs from the first plot's top to
    the last plot's bottom where a line plot is drawn, each line's point takes a marker, and the
    other periods' bars fade; with bars alone, no crosshair."""
    g = _geometry(THREE)
    found = _chart("box", g, 8, "m")
    assert found["label"] == "2024"
    assert [(r["name"], r["text"]) for r in found["rows"]] == [
        ("Revenue", "391,035"),
        ("Net income", "93,736"),
        ("Operating margin", "31.5%"),
    ]
    assert [(r["slot"], r["form"]) for r in found["rows"]] == [
        (0, "bars"),
        (1, "bars"),
        (2, "line"),
    ]
    assert found["y"] == g["plots"][0]["top"]
    beside = g["band"] / 2 + 4
    assert (found["left"], found["right"]) == (pytest.approx(g["xs"][8] + beside), None)
    newest = _chart("box", g, 10, "m")  # no room at its right: at its left, against it
    assert (newest["left"], newest["right"]) == (None, pytest.approx(1200 - g["xs"][10] + beside))
    narrow = _geometry(THREE, 300)  # room on neither side: against the chart's right edge
    middle = _chart("box", narrow, 5, "m")
    assert middle["right"] is None and 0 <= middle["left"] < narrow["xs"][5]
    assert _chart("box", g, 8, "b")["rows"][0]["text"] == "391.04"
    assert _chart("box", g, 11, "m") is None

    columns = _columns(YEARS[:4])
    columns[0]["currency"] = "EUR"
    euros = _answer(
        _table(
            columns,
            _row("revenue", "Revenue", "money", [25_129e6, 5e9, None, 7e9]),
            _row("netIncome", "Net income", "money", [3e9, 1e9, None, 2e9]),
        ),
        ratios=_table(
            _columns(YEARS[:4]),
            _row("operatingProfitMargin", "Operating", "percent", [0.278, 0.267, None, 0.251],
                 name="Operating margin"),
        ),
    )  # fmt: skip
    g = _geometry(THREE, answer=euros)
    assert [(r["name"], r["text"]) for r in _chart("box", g, 0, "m")["rows"]] == [
        ("Revenue", "EUR 25,129"),
        ("Net income", "EUR 3,000"),
        ("Operating margin", "27.8%"),
    ]
    assert _chart("box", g, 2, "m") is None

    tree = _block(THREE, at=8)
    g = _geometry(THREE)
    [tip] = classed(tree, "app-fin__tip")
    assert _classes(tip) == {"app-fin__tip", "app-fin__tip--rows"}
    assert set(tip["props"]["style"]) == {"left", "top"}
    assert tip["props"]["style"]["top"] == "18px"
    [late] = classed(_block(THREE, at=10), "app-fin__tip")
    assert set(late["props"]["style"]) == {"right", "top"}
    assert [text(e) for e in classed(tip, "app-fin__tipwhen")] == ["2024"]
    rows = classed(tip, "app-fin__tiprow")
    assert [_classes(r) for r in rows] == [{"app-fin__tiprow", f"is-s{n}"} for n in range(3)]
    assert [text(r) for r in rows] == [
        "Revenue391,035",
        "Net income93,736",
        "Operating margin31.5%",
    ]
    assert [len(classed(r, "app-fin__key")) for r in rows] == [1, 1, 1]
    assert _classes(classed(rows[2], "app-fin__key")[0]) == {"app-fin__key", "app-fin__key--round"}
    [cross] = classed(tree, "app-fin__cross")
    last = g["plots"][-1]
    assert (cross["props"]["y1"], cross["props"]["y2"]) == (18, last["top"] + last["height"])
    assert cross["props"]["x1"] == cross["props"]["x2"] == pytest.approx(g["xs"][8])
    [mark] = classed(tree, "app-fin__mark")
    assert _classes(mark) == {"app-fin__mark", "is-s2"}
    assert mark["props"]["cy"] == pytest.approx(last["series"][0]["tops"][8])
    bars = classed(tree, "app-fin__col")
    assert ["is-dim" in _classes(bar) for bar in bars] == ([True] * 8 + [False] + [True] * 2) * 2
    two = _block([REVENUE_PICK, NET_PICK], at=8)
    assert classed(two, "app-fin__cross") == [] and len(classed(two, "app-fin__tip")) == 1
    lines = _block([MARGIN_PICK, OPERATING_PICK | {"slot": 1}], at=8)
    assert len(classed(lines, "app-fin__mark")) == 2 and len(classed(lines, "app-fin__cross")) == 1
    css = {
        selector.strip(): " ".join(body.split())
        for selector, body in re.findall(
            r"\n  (\.app-fin(?![a-z])[^{]*)\{([^}]*)\}", _static_file("index.html")
        )
    }
    assert "transform: none;" in css[".app-fin__tip--rows"]


def test_a_plot_whose_every_figure_is_in_another_currency() -> None:
    """A per-share line whose every figure is in another currency than the tab's, beside revenue:
    its plot draws its frame, its baseline alone, and its unit, and no mark, on a scale built
    from no figure and finite; its label and the box write its figures with their code."""
    euros = copy.deepcopy(RATIOS)
    euros["columns"] = _columns(YEARS, "EUR")
    answer = _answer(ratios=euros)
    picks = [REVENUE_PICK, _pick("ratios", "revenuePerShare", slot=1)]
    g = _geometry(picks, answer=answer)
    assert _finite(g)
    money, per = g["plots"]
    assert (per["unit"], per["series"][0]["bars"]) == ("perShare", [])
    assert [(t["zero"], t["text"]) for t in per["ticks"]] == [(True, None)]
    assert per["ticks"][0]["y"] == pytest.approx(per["top"] + per["height"], abs=0.5)
    assert len(money["series"][0]["bars"]) == 11
    tree = _block(picks, answer=answer)
    assert [text(t) for t in classed(tree, "app-fin__measure")] == ["USD, millions", "USD a share"]
    assert len(classed(tree, "app-fin__zero")) == 2  # each plot's baseline
    assert dict(_labels(tree))["Revenue a share"] == "EUR 19.80"
    assert _chart("box", g, 8, "m")["rows"][1]["text"] == "EUR 17.80"


def test_the_chart_borrows_its_rules() -> None:
    """One rule each: the chart writes its ticks with the price chart's own helpers, and a figure
    draws a mark only where the table's own formatter does not write it as a dash."""
    script = _static_file("company_financials_chart.js")
    for copied in ("function decimals(", "function bare(", "NIL"):
        assert copied not in script, copied
    assert "K.decimals(" in script and "K.bare(" in script
    start = script.index("  function figured(")
    assert "F.figure(" in script[start : script.index("\n  }\n", start)]
    price = (STATIC / "company.js", STATIC / "company_chart.js")
    assert node("companyChart.bare", [-1234.56, 1], *price) == "−1234.6"
    assert node("companyChart.bare", [-0.004, 2], *price) == "0.00"
    assert node("companyChart.decimals", [0.05], *price) == 2


MARKS = {"app-fin__col", "app-fin__line", "app-fin__dot", "app-fin__end", "app-fin__mark"}
SLOTS = {"is-s0", "is-s1", "is-s2", "is-s3"}
SHARED = SLOTS | {"heading", "caption", "figure-sm", "control"}  # the slots and the type styles


def test_the_chart_s_classes_are_its_own() -> None:
    """No element of a drawn tab, its chart in its place, carries both the controls row's class
    and a mark's, so no rule of one can reach the other; no element the tab's own builders draw
    outside the chart carries a mark's class or any other of the chart's own. The two share only
    the lines' colour slots, which the rows on the chart and their marks both wear, and the design
    system's type styles; neither script names a class of the other's own, wherever it names it."""
    view = {"kind": "income", "period": "annual", "scale": "m"}
    for change, picks in (
        ({}, [REVENUE_PICK]),
        ({}, [_pick("income", "netIncome")]),
        ({"kind": "ratios"}, [MARGIN_PICK]),
        ({"kind": "segments"}, [_pick("segments", "Anvils", "product")]),
        ({}, [*THREE, _pick("income", "eps", slot=3)]),
        ({"kind": "ratios"}, THREE),
    ):
        tab = _tab("block", ANSWER, view | change, picks, None)
        own = {name for e in elements(tab) for name in _classes(e)}
        chart = _block(picks, at=3)
        drawn = {name for e in elements(chart) for name in _classes(e)}
        assert drawn & MARKS, picks
        assert own & MARKS == set(), picks
        assert own & drawn <= SHARED, (picks, own & drawn)
        [place] = classed(tab, "app-fin__chart")
        place["props"]["children"] = [chart]  # the chart drawn in its place
        [row] = classed(tab, "app-fin__bar")
        assert row["type"] == "div" and _classes(row) == {"app-fin__bar"}
        assert all("app-fin__bar" not in _classes(e) for e in elements(tab) if _classes(e) & MARKS)
    names = re.compile(r"app-fin__[a-z]+")  # every name, the second of a string's too
    tab_names = set(names.findall(_static_file("company_financials.js")))
    chart_names = set(names.findall(_static_file("company_financials_chart.js")))
    assert MARKS <= chart_names
    assert {"app-fin__add", "app-fin__swatch", "app-fin__bar"} <= tab_names
    assert {"app-fin__label", "app-fin__key", "app-fin__x", "app-fin__tiprow"} <= chart_names
    assert tab_names & chart_names == set(), tab_names & chart_names
    assert names.findall("'control app-fin__tab'") == ["app-fin__tab"]  # after another class


def test_the_chart_s_script_follows_the_tab_s() -> None:
    """The chart's script loads right after the tab's, which draws it in its chart's place."""
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert (
        scripts.index("company_financials_chart.js") == scripts.index("company_financials.js") + 1
    )
