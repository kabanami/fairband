"""The industry on the screen (B-32; the founder, 2026-11-22): FMP's industry, the level under the
sector, as a column, as a group of the Filters menu and as a chip. The whole screen holds over a
hundred industries, so the menu lists those of the chosen sectors alone, and a sector unticked
takes its chosen industries along. The column, the group, the chip and the menu's section are
``fairband:`` patches of the vendored bundle; the narrowing and the menu's list are the page's.

The bundle and the page's script run in node (``support.page``); the menu opens on a press, which
the stub's state never sees, so its section is read in the bundle's source."""

from typing import Any

import pytest
from support.page import BUNDLE, NODE, elements, node, text

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _row(ticker: str, sector: str | None, industry: str | None) -> dict[str, Any]:
    """A valued screen row of ``sector`` and ``industry``."""
    return {
        "ticker": ticker,
        "name": f"{ticker} Co",
        "phase": 5,
        "price": 100.0,
        "sector": sector,
        "industry": industry,
        "capBand": "mid",
        "watchlists": [],
        "reviewed": None,
        "freshness": "current",
        "designation": "near",
        "agentStance": None,
    }


CHIP = _row("CHIP", "Technology", "Semiconductors")
SOFT = _row("SOFT", "Technology", "Software - Application")
SEMI = _row("SEMI", "Technology", "Semiconductors")
WELL = _row("WELL", "Energy", "Oil & Gas Drilling")
BARE = _row("BARE", None, None)  # a row the universe gives no sector and no industry
ROWS = [CHIP, SOFT, SEMI, WELL, BARE]


def _filters(**chosen: Any) -> dict[str, Any]:
    return node("Fairband.EMPTY_FILTERS", []) | chosen


def _tickers(rows: list[dict[str, Any]]) -> list[str]:
    return [row["ticker"] for row in rows]


def test_the_industry_column_follows_the_sector_s() -> None:
    """The catalog's Industry column stands after Sector and draws the row's industry as a word,
    an em dash for none."""
    keys = node("Fairband.COLUMN_KEYS", [])
    assert keys[keys.index("sector") + 1] == "industry"
    tree = node(
        "Fairband.ScreenTable",
        [{"rows": [CHIP, BARE], "chooser": False, "columns": ["ticker", "industry", "price"]}],
    )
    heads = [e for e in elements(tree) if e.get("type") == "th"]
    assert [(h["props"]["data-key"], text(h)) for h in heads][1] == ("industry", "Industry")
    cells = [e for e in elements(tree) if e.get("type") == "td"]
    words = [text(c) for c in cells if c["props"].get("className") == "body"]
    assert words == ["Semiconductors", "—"]


def test_the_empty_filters_hold_an_industry_group() -> None:
    assert node("Fairband.EMPTY_FILTERS", [])["industry"] == []


def test_the_menu_lists_the_industries_of_the_chosen_sectors() -> None:
    """None before a sector is chosen; then the names on the rows of the chosen sectors, each
    once, sorted; a row without an industry adds none."""
    assert node("industriesOf", [ROWS, []]) == []
    assert node("industriesOf", [ROWS, ["Technology"]]) == [
        "Semiconductors",
        "Software - Application",
    ]
    assert node("industriesOf", [ROWS, ["Technology", "Energy"]]) == [
        "Oil & Gas Drilling",
        "Semiconductors",
        "Software - Application",
    ]
    assert node("industriesOf", [[BARE | {"sector": "Energy"}], ["Energy"]]) == []


def test_a_chosen_industry_narrows_the_rows() -> None:
    """An empty group narrows nothing; a chosen industry keeps its rows alone, with the sector's
    filter and with the FIND text; a row without an industry matches none."""
    assert _tickers(node("narrow", [ROWS, "", _filters()])) == _tickers(ROWS)
    semis = _filters(sector=["Technology"], industry=["Semiconductors"])
    assert _tickers(node("narrow", [ROWS, "", semis])) == ["CHIP", "SEMI"]
    assert _tickers(node("narrow", [ROWS, "se", semis])) == ["SEMI"]
    two = _filters(
        sector=["Technology", "Energy"], industry=["Semiconductors", "Oil & Gas Drilling"]
    )
    assert _tickers(node("narrow", [ROWS, "", two])) == ["CHIP", "SEMI", "WELL"]


def test_a_sector_unticked_takes_its_industries_along() -> None:
    """The filters the page keeps hold the chosen industries the menu still lists: with Energy
    unticked, its chosen industry goes and Technology's stays; with no sector left, none stays.
    Filters that lose nothing come back as they are."""
    two = _filters(
        sector=["Technology", "Energy"], industry=["Semiconductors", "Oil & Gas Drilling"]
    )
    assert node("listedFilters", [two, ROWS]) == two
    assert node("listedFilters", [two | {"sector": ["Technology"]}, ROWS]) == two | {
        "sector": ["Technology"],
        "industry": ["Semiconductors"],
    }
    assert node("listedFilters", [two | {"sector": []}, ROWS]) == two | {
        "sector": [],
        "industry": [],
    }


def _chips(filters: dict[str, Any]) -> list[str]:
    tree = node("Fairband.ScreenTable", [{"rows": [], "filters": filters}])
    return [
        text(e)
        for e in elements(tree)
        if e.get("type") == "button" and "fb-screen__chip" in e["props"].get("className", "")
    ]


def test_the_industry_chip_follows_the_sector_s() -> None:
    """One or two chosen industries read by name, more by their count, after the sector's chip."""
    one = _filters(sector=["Technology"], industry=["Semiconductors"])
    assert _chips(one) == ["Technology", "Semiconductors"]
    two = one | {"industry": ["Semiconductors", "Software - Application"]}
    assert _chips(two) == ["Technology", "Semiconductors + Software - Application"]
    three = one | {"industry": ["Semiconductors", "Software - Application", "Solar"]}
    assert _chips(three) == ["Technology", "3 industries"]


def test_the_menu_has_an_industry_section_after_the_sector_s() -> None:
    """INDUSTRY stands between SECTOR and WATCHLISTS: a checkbox for each industry the page hands
    the table, or one line that asks for a sector while it hands none. A table handed no
    ``industries`` draws no section. Clear takes the group with the others."""
    bundle = BUNDLE.read_text(encoding="utf-8")
    groups = "['designation', 'stance', 'phase', 'cap', 'sector', 'industry', 'watchlist']"
    assert f"var FILTER_GROUPS = {groups};" in bundle
    menu = bundle[bundle.index("'SECTOR'),") : bundle.index("'WATCHLISTS'),")]
    for line in (
        "p.industries ? h('hr') : null,",
        "h('span', { className: 'fb-menu__h label' }, 'INDUSTRY'),",
        "return checkRow(name, listOf(filters, 'industry').indexOf(name) !== -1,",
        "function () { toggleIn('industry', name); },",
        "h('span', { className: 'fb-menu__hint caption' },",
        "'Choose a sector to list its industries.')",
    ):
        assert line in menu, line
    assert bundle.count("sector: [], industry: [],") == 2  # the empty filters and Clear's
    styles = (BUNDLE.parent / "bundle.css").read_text(encoding="utf-8")
    assert ".fb-menu__hint {" in styles


def test_the_page_hands_the_table_the_industries_and_keeps_the_listed_filters() -> None:
    script = (BUNDLE.parent.parent.parent / "app.js").read_text(encoding="utf-8")
    assert "industries: industriesOf(state.rows, state.filters.sector)," in script
    assert "state.filters = listedFilters(filters, state.rows || []);" in script
    assert "within(filters.industry, r.industry) &&" in script
