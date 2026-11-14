"""The drawer's figures from the intermediates the research round adds. In "Intermediate results"
(spec 2026-11-13 11 and 11a, 7.2): ``margin_history``'s medians as percentages, as
``median_margin`` reads, its counts of years whole, and no heading for an empty record;
``trailing_end`` as its ISO date, as ``fx_date`` reads; ``sbc_ttm`` as a total in the row's
currency at any size, nil included, as ``ntm_net_income`` reads; and from plan 2 (12, 13 and 9a)
``minority_interest`` as a total, ``balance_sheet``'s period, and the anchor's sum of the
window's periods and its annual correction's figures a share, its fiscal year whole. Each label
is the intermediate's key, as every other label of the section is. In the route sections (15):
the minority interest beside debt and cash on the revenue-growth bridge, the Decline floor and
distress and the Start-up requirement and cash floor, only above zero, the words beside it
naming it; the balance sheet's period under those rows; and on Mature Growth the line that says
year 1 is corrected by the annual consensus, and by how much. No route section prints a raw key
or tag. The page's own script runs in node after the bundle (``page.mjs``), and the tests read
what ``intermediates`` and the route sections return."""

import json
import re
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

NODE = shutil.which("node")
HARNESS = Path(__file__).with_name("page.mjs")
STATIC = Path(str(resources.files("fairband.web").joinpath("static")))
BUNDLE = STATIC / "design-system" / "components" / "bundle.js"
APP = STATIC / "app.js"
GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

MARGINS = {
    "operating": {"median": 0.2325, "years": 10},
    "net": {"median": 0.174375, "years": 10},
}


def _call(helper: str, *args: Any) -> Any:
    """What app.js's ``helper`` returns on ``args``, through JSON."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(HARNESS), str(BUNDLE), str(APP), helper],
        input=json.dumps(list(args)),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


def _texts(node: Any) -> list[str]:
    """The text of an element tree, in order: its strings and its children's."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [text for child in node for text in _texts(child)]
    if isinstance(node, dict):
        return _texts(node.get("props", {}).get("children", []))
    return []


def _after(texts: list[str], label: str) -> str:
    """The text that follows ``label``: a figure after its name."""
    return texts[texts.index(label) + 1]


def _shown(im: dict[str, Any]) -> list[str]:
    return _texts(_call("intermediates", im))


def test_the_ten_year_median_margins_read_as_percentages() -> None:
    """Each median prints as ``median_margin`` prints the same figure, a percentage to one
    decimal; each count of years whole; the record under its key's heading."""
    texts = _shown({"median_margin": 0.2325, "margin_history": MARGINS})
    assert "margin_history" in texts  # the group's heading
    assert _after(texts, "operating.median") == _after(texts, "median_margin")
    assert _after(texts, "operating.median").endswith("%")
    assert _after(texts, "net.median") == "17.4%"
    assert _after(texts, "operating.years") == "10"
    assert _after(texts, "net.years") == "10"
    # MSCO's golden: the route's own median and the record's operating one read alike, 20.0%
    msco = json.loads((GOLDEN / "MSCO.json").read_text())["intermediates"]
    stable = _shown(msco)
    assert _after(stable, "operating.median") == _after(stable, "median_margin") == "20.0%"


def test_an_empty_margin_record_has_no_heading() -> None:
    """SUCO has no fiscal year with a revenue above zero, so its record is empty: the drawer shows
    no group for it, heading or rows."""
    suco = json.loads((GOLDEN / "SUCO.json").read_text())["intermediates"]
    assert suco["margin_history"] == {}
    texts = _shown(suco)
    assert "margin_history" not in texts
    assert "burn_cover_years" in texts  # the rest of the section stands


def test_the_trailing_end_and_the_stock_pay_read_as_their_neighbours() -> None:
    """``trailing_end`` is an ISO date, as ``fx_date``; ``sbc_ttm`` a total in the row's currency,
    as ``ntm_net_income``, at any size: MGCO's $400 m, FXCO's SEK 320 m, and a stock pay of nil
    or below a million, which the rule for an unnamed total at a million or more would leave a
    bare decimal."""
    mgco = json.loads((GOLDEN / "MGCO.json").read_text())["intermediates"]
    usd = _shown(mgco)
    assert _after(usd, "trailing_end") == "2026-09-30"
    assert _after(usd, "sbc_ttm") == "$400,000,000"
    assert _after(usd, "ntm_net_income").startswith("$")
    fxco = json.loads((GOLDEN / "FXCO.json").read_text())["intermediates"]
    sek = _shown(fxco)
    assert _after(sek, "sbc_ttm") == "SEK 320,000,000"
    assert _after(sek, "fx_date") == "2026-10-31"
    assert _after(_shown(mgco | {"sbc_ttm": 0.0}), "sbc_ttm") == "$0"
    assert _after(_shown(mgco | {"sbc_ttm": 500_000.0}), "sbc_ttm") == "$500,000"
    assert _after(_shown(fxco | {"sbc_ttm": 0.0}), "sbc_ttm") == "SEK 0"


# The newest balance sheet's period, as the three firm-value routes record it (spec 12.2), and the
# caption the route sections give it.
SHEET = {"period_end": "2026-09-30", "label": "fiscal 2026 Q3", "quarterly": True}
CAPTION = "Balance sheet of fiscal 2026 Q3."
NO_SHEET: list[tuple[tuple[str, ...], dict[str, Any]]] = [
    ((), {"balance_sheet": None}),  # no balance sheet on file
    (("balance_sheet",), {}),  # a result stored before method 1.4
]
NO_MINORITY: list[tuple[tuple[str, ...], dict[str, Any]]] = [
    ((), {"minority_interest": 0.0}),  # none on the sheet, the most common case
    (("minority_interest",), {}),  # a result stored before method 1.4
]

# Year 1 corrected by the annual consensus of fiscal 2027 (spec 9a, as amended): its annual EPS
# of 6.00 against its four quarters' 6.16, three of them in the window, −0.12 a share.
GAP = {
    "analysts": 12,
    "correction": -0.12,
    "eps": 6.0,
    "fiscal_year": 2027,
    "share": 0.75,
    "year_sum": 6.16,
}
CORRECTED = "Year 1 from the periods, corrected by the annual consensus of fiscal 2027: "


def _result(symbol: str, drop: tuple[str, ...] = (), **entries: Any) -> dict[str, Any]:
    """A golden's result whose intermediates lose the keys in ``drop`` and take ``entries``."""
    result: dict[str, Any] = json.loads((GOLDEN / f"{symbol}.json").read_text())
    im = {k: v for k, v in result["intermediates"].items() if k not in drop}
    result["intermediates"] = im | entries
    return result


def _annual_anchor(gap: dict[str, Any] | None, raw: float) -> dict[str, Any]:
    """MGCO's anchor, the window's periods summing to its 5.90, corrected by ``gap``, the annual
    consensus of the last fiscal year the window reaches, to ``raw``; with no ``gap``, the
    periods' sum. Built by hand, so the drawer's tests stand with or without the engine's annual
    source (spec 9a)."""
    return {
        "annual": gap,
        "ntm_eps": raw,
        "ntm_eps_raw": raw,
        "periods_sum": 5.9,
        "sbc_adjustment_per_share": 0.0,
        "source": "periods" if gap is None else "annual",
    }


def _section(helper: str, result: dict[str, Any]) -> list[str]:
    """The text of the route section ``helper`` draws for ``result``."""
    return _texts(_call(helper, result))


def _in_order(texts: list[str], *labels: str) -> None:
    """Each label is in ``texts``, each after the one before it."""
    at = [texts.index(label) for label in labels]
    assert at == sorted(at), labels


def test_the_minority_interest_prints_as_a_total() -> None:
    """``minority_interest`` is a total in the row's currency, as ``sbc_ttm`` is, at any size and
    at nil, which the rule for an unnamed total at a million or more would leave "0.00"."""
    hgco = _result("HGCO")["intermediates"]
    assert _after(_shown(hgco | {"minority_interest": 500e6}), "minority_interest") == (
        "$500,000,000"
    )
    assert _after(_shown(hgco), "minority_interest") == "$0"  # HGCO's own, nil
    assert _after(_shown(hgco | {"minority_interest": 250_000.0}), "minority_interest") == (
        "$250,000"
    )
    fxco = json.loads((GOLDEN / "FXCO.json").read_text())["intermediates"]
    assert _after(_shown(fxco | {"minority_interest": 0.0}), "minority_interest") == "SEK 0"


def test_the_balance_sheet_entry_prints_its_period() -> None:
    """``balance_sheet`` is a group under its key, as every record is: the label as stored, the
    period end as its ISO date, whether it is a quarter's as a word; a result with no sheet shows
    an em dash under the key."""
    texts = _shown(_result("HGCO", balance_sheet=SHEET)["intermediates"])
    assert "balance_sheet" in texts  # the group's heading
    assert _after(texts, "label") == "fiscal 2026 Q3"
    assert _after(texts, "period_end") == "2026-09-30"
    assert _after(texts, "quarterly") == "true"
    empty = _shown(_result("HGCO", balance_sheet=None)["intermediates"])
    assert _after(empty, "balance_sheet") == "—"


def test_the_bridge_takes_off_the_minority_interest_between_debt_and_cash() -> None:
    """A revenue-growth row with a minority interest of $500 m: equity = firm value − debt −
    minority interest + cash (method 5a.9), so its row sits between "Less debt" and "Plus
    cash"."""
    texts = _section("revenueRoute", _result("HGCO", minority_interest=500e6))
    _in_order(texts, "Less debt", "Less minority interest", "Plus cash", "Equity")
    assert _after(texts, "Less minority interest") == "$500,000,000"
    assert _after(texts, "Less debt") == "$1,000,000,000"  # HGCO's


@pytest.mark.parametrize(("drop", "entries"), NO_MINORITY)
def test_a_bridge_without_a_minority_interest_reads_as_before(
    drop: tuple[str, ...], entries: dict[str, Any]
) -> None:
    texts = _section("revenueRoute", _result("HGCO", drop, **entries))
    assert "Less minority interest" not in texts
    assert texts[texts.index("Less debt") + 2] == "Plus cash"


def test_the_bridge_names_its_balance_sheet() -> None:
    """The caption under the bridge's rows names the sheet debt, cash and the minority interest
    were read from, from ``balance_sheet``'s label: a quarter's, or HGCO's fiscal year."""
    texts = _section("revenueRoute", _result("HGCO", balance_sheet=SHEET))
    _in_order(texts, "Value a share", CAPTION, "At the price")
    assert "Balance sheet of fiscal 2025." in _section("revenueRoute", _result("HGCO"))


@pytest.mark.parametrize(("drop", "entries"), NO_SHEET)
def test_a_bridge_without_a_balance_sheet_has_no_caption(
    drop: tuple[str, ...], entries: dict[str, Any]
) -> None:
    texts = _section("revenueRoute", _result("HGCO", drop, **entries))
    assert not [t for t in texts if t.startswith("Balance sheet")]
    assert "Value a share" in texts  # the bridge stands


def test_the_floor_and_distress_take_off_the_minority_interest() -> None:
    """A Decline row with a minority interest of $50 m: its row between "Less debt" and "Plus
    cash"; the floor a share is NCAV less the minority interest (method 6a.6), and its row says
    so; the distress-sale value is the fraction of the firm value plus cash less debt and the
    minority interest (6a.7), and its words name it. DCCO's distress fraction is 60%."""
    texts = _section("declineRoute", _result("DCCO", minority_interest=50e6, balance_sheet=SHEET))
    _in_order(texts, "Less debt", "Less minority interest", "Plus cash", "Shares")
    assert _after(texts, "Less minority interest") == "$50,000,000"
    assert "NCAV a share" not in texts
    assert "NCAV less minority interest, a share" in texts
    assert " (60.0% of firm value + cash − debt − minority interest)" in texts
    _in_order(
        texts, "Distress-sale value a share", CAPTION, "value = floored × (1 − π) + distress × π"
    )


@pytest.mark.parametrize(("drop", "entries"), NO_MINORITY)
def test_a_floor_without_a_minority_interest_reads_as_before(
    drop: tuple[str, ...], entries: dict[str, Any]
) -> None:
    texts = _section("declineRoute", _result("DCCO", drop, **entries))
    assert "Less minority interest" not in texts
    assert texts[texts.index("Less debt") + 2] == "Plus cash"
    assert "NCAV a share" in texts
    assert " (60.0% of firm value + cash − debt)" in texts
    assert "Balance sheet of fiscal 2025." in texts  # DCCO's own sheet


@pytest.mark.parametrize(("drop", "entries"), NO_SHEET)
def test_a_floor_without_a_balance_sheet_has_no_caption(
    drop: tuple[str, ...], entries: dict[str, Any]
) -> None:
    texts = _section("declineRoute", _result("DCCO", drop, **entries))
    assert not [t for t in texts if t.startswith("Balance sheet")]


def _start_up(market_cap: float, minority: float | None, **entries: Any) -> dict[str, Any]:
    """SUCO (cash 300, debt 0, 100 shares) at ``market_cap``, its market-cap input read at it so
    the cap did not move with the price, with a minority interest of ``minority``, ``None`` for
    a result stored before method 1.4, which counts it nil: the enterprise value at the price
    market cap + debt + minority interest − cash (method 6b.2), the cash floor (cash − debt −
    minority interest) ÷ shares (6b.4), and ``below-net-cash`` where the enterprise value is at
    or below zero. At SUCO's own market cap of 2,000 and no minority interest, SUCO's figures."""
    held = 0.0 if minority is None else minority
    result = _result("SUCO", ("minority_interest",) if minority is None else (), **entries)
    im = result["intermediates"]
    im["market_cap"] = market_cap
    if minority is not None:
        im["minority_interest"] = minority
    im["requirement"] = im["requirement"] | {"ev_price": market_cap + 0.0 + held - 300.0}
    im["cash_floor"] = (300.0 - 0.0 - held) / 100.0
    for i in result["inputs"]:
        if i["name"] == "market_cap":
            i["value"] = market_cap
    if im["requirement"]["ev_price"] <= 0:
        flag = {"code": "below-net-cash", "word": "Below net cash", "sentence": ""}
        result["flags"] = [*result["flags"], flag]
    return result


NET_CASH = "The price is covered by net cash: the market cap is at or below the cash less the debt"


def test_the_start_up_names_the_minority_interest() -> None:
    """Method 6b's example: a minority interest of 100 at a market cap of 250 gives EV_price
    250 + 0 + 100 − 300 = 50 and a cash floor of (300 − 100) ÷ 100 = $2.00; at a market cap of
    150, EV_price is −50 and the price is covered. The enterprise value says what it adds; the
    cash floor takes the minority interest off between "Less debt" and "Shares"; the caption
    of a covered price names it."""
    texts = _section("startUpRoute", _start_up(250.0, 100.0, balance_sheet=SHEET))
    assert _after(texts, "Enterprise value at the price") == "$50"
    assert texts[texts.index("Enterprise value at the price") + 2] == (
        " (market cap + debt + minority interest − cash)"
    )
    assert _after(texts, "Net cash a share") == "$2.00"
    _in_order(texts, "Cash", "Less debt", "Less minority interest", "Shares", CAPTION, "Burn cover")
    assert _after(texts, "Less minority interest") == "$100"
    assert not [t for t in texts if t.startswith("The price is covered")]
    covered = _section("startUpRoute", _start_up(150.0, 100.0))
    assert _after(covered, "Enterprise value at the price") == "−$50"
    assert covered[covered.index("Enterprise value at the price") + 2] == (
        " (market cap + debt + minority interest − cash; net cash covers the price)"
    )
    assert NET_CASH + " and the minority interest" in covered
    assert "Balance sheet of fiscal 2025." in covered  # SUCO's own sheet


@pytest.mark.parametrize("minority", [0.0, None])
def test_a_start_up_without_a_minority_interest_reads_as_before(minority: float | None) -> None:
    """SUCO as captured, market cap 2,000: EV_price 2,000 + 0 − 300 = 1,700, no words beside it,
    a cash floor of 300 ÷ 100 = $3.00; at a market cap of 200, EV_price −100 and the price
    covered, in today's words."""
    texts = _section("startUpRoute", _start_up(2000.0, minority))
    assert _after(texts, "Enterprise value at the price") == "$1,700"
    assert texts[texts.index("Enterprise value at the price") + 2] == "Target margin"
    assert _after(texts, "Net cash a share") == "$3.00"
    assert "Less minority interest" not in texts
    assert texts[texts.index("Less debt") + 2] == "Shares"
    covered = _section("startUpRoute", _start_up(200.0, minority))
    assert _after(covered, "Enterprise value at the price") == "−$100"
    assert covered[covered.index("Enterprise value at the price") + 2] == (
        " (net cash covers the price)"
    )
    assert NET_CASH in covered
    assert "Less minority interest" not in covered


@pytest.mark.parametrize(("drop", "entries"), NO_SHEET)
def test_a_start_up_without_a_balance_sheet_has_no_caption(
    drop: tuple[str, ...], entries: dict[str, Any]
) -> None:
    texts = _section("startUpRoute", _result("SUCO", drop, **entries))
    assert not [t for t in texts if t.startswith("Balance sheet")]


def test_the_annual_correction_prints_its_year_whole_and_its_figures_a_share() -> None:
    """The anchor's sum of the window's periods and the correction's EPS figures are figures a
    share, as ``ntm_eps`` beside them: fiscal 2027's annual EPS, its quarters' sum and the
    correction, 5.90 − 0.12 = 5.78; the fiscal year a whole year, not "2,027"; the analysts a
    count; the window's share of the year a plain number."""
    texts = _shown(_result("MGCO", anchor=_annual_anchor(GAP, 5.78))["intermediates"])
    assert _after(texts, "ntm_eps") == "$5.78"
    assert _after(texts, "periods_sum") == "$5.90"
    assert _after(texts, "annual.fiscal_year") == "2027"
    assert _after(texts, "annual.analysts") == "12"
    assert _after(texts, "annual.eps") == "$6.00"
    assert _after(texts, "annual.year_sum") == "$6.16"
    assert _after(texts, "annual.correction") == "−$0.12"
    assert _after(texts, "annual.share") == "0.75"
    assert not [t for t in texts if "2,027" in t]
    whole = _result("MGCO", anchor=_annual_anchor(GAP | {"share": 1.0}, 5.78))
    assert _after(_shown(whole["intermediates"]), "annual.share") == "1"
    # on the window's periods: the sum a share, no correction
    periods = _shown(_result("MGCO", anchor=_annual_anchor(None, 5.9))["intermediates"])
    assert _after(periods, "periods_sum") == "$5.90"
    assert _after(periods, "annual") == "—"
    # a row in another currency: each figure a share in it
    sek = _shown(_result("FXCO", anchor=_annual_anchor(GAP, 5.78))["intermediates"])
    assert _after(sek, "annual.correction") == "−SEK 0.12"


@pytest.mark.parametrize(
    ("symbol", "correction", "line"),
    [
        ("MGCO", -0.10, f"{CORRECTED}−$0.10 a share."),
        ("MGCO", 0.12, f"{CORRECTED}+$0.12 a share."),
        ("FXCO", 0.12, f"{CORRECTED}+SEK 0.12 a share."),  # in the row's currency
    ],
)
def test_a_mature_growth_row_corrected_by_the_annual_consensus_says_so(
    symbol: str, correction: float, line: str
) -> None:
    """Spec 9a, as amended: on a thin window year 1 is the periods' sum corrected by the annual
    consensus of the last fiscal year the window reaches, and the Mature Growth section says by
    how much a share, the sign shown, in the row's currency; above the Charge group."""
    gap = GAP | {"correction": correction}
    texts = _section("matureRoute", _result(symbol, anchor=_annual_anchor(gap, 5.9 + correction)))
    _in_order(texts, "Mature growth route", line, "Charge")


@pytest.mark.parametrize(
    "result",
    [
        _result("MGCO", anchor=_annual_anchor(None, 5.9)),  # the window's periods
        _result("MGCO", anchor=_annual_anchor(None, 5.9) | {"source": "annual"}),  # no correction
        _result(  # an anchor stored before method 1.4
            "MGCO", anchor={"ntm_eps": 5.9, "ntm_eps_raw": 5.9, "sbc_adjustment_per_share": 0.0}
        ),
        _result("MSCO"),  # Mature Stable, no anchor
    ],
)
def test_a_mature_row_off_the_annual_correction_has_no_anchor_line(
    result: dict[str, Any],
) -> None:
    texts = _section("matureRoute", result)
    assert not [t for t in texts if t.startswith("Year 1")]
    assert "Charge" in texts


# A word joined by underscores, as a key is: no text of a route section holds one.
RAW_KEY = re.compile(r"\b[a-z0-9]+(?:_[a-z0-9]+)+\b")


FILLED = {"minority_interest": 50e6, "balance_sheet": SHEET}


@pytest.mark.parametrize(
    ("symbol", "helper", "entries", "drawn"),
    [
        ("HGCO", "revenueRoute", FILLED, ["Less minority interest", CAPTION]),
        ("YGCO", "revenueRoute", FILLED, ["Less minority interest", CAPTION]),
        (
            "MGCO",
            "matureRoute",
            {"anchor": _annual_anchor(GAP, 5.78)},
            [f"{CORRECTED}−$0.12 a share."],
        ),
        ("DCCO", "declineRoute", FILLED, ["Less minority interest", CAPTION]),
        ("SUCO", "startUpRoute", FILLED, ["Less minority interest", CAPTION]),
    ],
)
def test_no_route_section_prints_a_raw_key_or_tag(
    symbol: str, helper: str, entries: dict[str, Any], drawn: list[str]
) -> None:
    """In place of a look by eye: each route's section, drawn for its golden with the new entries
    filled (a minority interest above zero and a quarter's sheet on the three firm-value routes,
    the annual source on Mature Growth), draws them, and holds no key of the intermediates, no
    word joined by underscores and none of the row's flag codes."""
    result = _result(symbol, **entries)
    texts = _section(helper, result)
    for text in drawn:
        assert text in texts, text
    for key in ("minority_interest", "balance_sheet", "periods_sum", "fiscal_year", "year_sum"):
        assert not [t for t in texts if key in t], key
    assert not [t for t in texts if RAW_KEY.search(t)]
    assert not set(texts) & set(result["intermediates"])
    codes = {f["code"] for f in result["flags"]}
    assert not [t for t in texts for code in codes if code in t]
