"""The rule that drafts the moat table (spec 2026-11-19 8.2), as it ran on 2026-11-19.

Each test reads the class ``draft_classes`` gives one company among four larger peers of its
industry (``_class``), so it is no leader unless a test makes it one. ``facts`` is the Wide default:
ten return years at 25%, a steady gross margin, $60 billion of revenue, Mature Stable, in an
industry of five. A return year is written in percent on a capital of 1,000, so each edge reads
exactly: 2.9 is NOPAT 29 on 1,000."""

from dataclasses import replace
from typing import Any

from fairband.policy import Moat
from fairband.policy.moat_rule import (
    CYCLICAL,
    MoatFacts,
    ReturnYear,
    draft_classes,
    gross_margins,
)

_STEADY = (0.5,) * 10
_UNSTEADY = (0.39, *(0.5,) * 9)  # one margin below 80% of the median, 0.4
# Ten fiscal revenues, the newest 1.1 ** 9 times the tenth newest: 10.0% a year.
_GROWTH = (1e9, *(1.5e9,) * 8, 2.357947691e9)


def _years(*percents: float) -> tuple[ReturnYear, ...]:
    return tuple(ReturnYear(nopat=p * 10, capital=1000.0) for p in percents)


def _ten(percent: float) -> tuple[ReturnYear, ...]:
    return _years(*(percent,) * 10)


def facts(symbol: str = "WIDE", **changes: Any) -> MoatFacts:
    wide = MoatFacts(
        symbol=symbol,
        industry="Widgets",
        sector="Industrials",
        phase="Mature Stable",
        years=_ten(25),
        revenue_usd=60e9,
        fiscal_revenues=(),
        gross_margins=_STEADY,
    )
    return replace(wide, **changes)


def _class(company: MoatFacts) -> Moat:
    """The company's class beside four peers of its industry and sector at $1 trillion each."""
    peers = [
        facts(f"PEER{k}", industry=company.industry, sector=company.sector, revenue_usd=1e12)
        for k in range(4)
    ]
    return draft_classes([company, *peers])[company.symbol]


def test_too_few_years_or_a_young_phase_is_narrow() -> None:
    assert _class(facts()) == "Wide"
    assert _class(facts(years=_years(*(1,) * 9))) == "Narrow"
    assert _class(facts(years=_years(*(25,) * 9))) == "Narrow"
    for phase in ("Start-up", "Young Growth", "High Growth"):
        assert _class(facts(phase=phase, years=_ten(1))) == "Narrow"
        assert _class(facts(phase=phase)) == "Narrow"


def test_none_needs_both_below_three_percent() -> None:
    assert _class(facts(years=_ten(2.9))) == "None"
    # a ten-year total of 3.0%, a median of 2.9%
    assert _class(facts(years=_years(*(3.1,) * 5, *(2.9,) * 5))) == "Narrow"
    # a ten-year total of 2.9%, a median of 3.0%
    assert _class(facts(years=_years(*(2.8,) * 5, *(3.0,) * 5))) == "Narrow"
    # None in any phase but the young ones, whatever the marks
    assert _class(facts(phase="Mature Growth", years=_ten(2.9))) == "None"
    assert _class(facts(phase=None, years=_ten(2.9))) == "None"


def test_decline_is_none_or_narrow() -> None:
    assert _class(facts(phase="Decline", years=_ten(1))) == "None"
    assert _class(facts(phase="Decline")) == "Narrow"


def test_the_scale_route() -> None:
    scale = facts(years=_ten(15))  # below the return route: size and steady
    assert _class(scale) == "Wide"
    assert _class(replace(scale, gross_margins=_UNSTEADY)) == "Narrow"  # size alone
    assert _class(replace(scale, revenue_usd=50e9)) == "Wide"
    assert _class(replace(scale, revenue_usd=49.9e9)) == "Narrow"
    assert _class(replace(scale, revenue_usd=None)) == "Narrow"
    grower = replace(scale, revenue_usd=12e9, fiscal_revenues=_GROWTH)  # growth and steady
    assert _class(grower) == "Wide"
    assert _class(replace(grower, revenue_usd=11.9e9)) == "Narrow"
    nine_nine = (1e9, *(1.5e9,) * 8, 1.099**9 * 1e9)
    assert _class(replace(grower, fiscal_revenues=nine_nine)) == "Narrow"
    # size and growth, without the steady margin
    assert _class(replace(grower, revenue_usd=60e9, gross_margins=_UNSTEADY)) == "Wide"


def test_the_return_route() -> None:
    small = facts(revenue_usd=1e9, years=_ten(21))
    assert _class(small) == "Wide"
    assert _class(replace(small, years=_ten(20))) == "Narrow"
    assert _class(replace(small, years=_years(*(22,) * 5, *(20,) * 5))) == "Narrow"  # 21%, 20%
    assert _class(replace(small, years=_years(*(19,) * 5, *(21,) * 5))) == "Narrow"  # 20%, 21%
    assert _class(replace(small, gross_margins=_UNSTEADY)) == "Narrow"


def test_the_conditions() -> None:
    assert _class(facts(years=_years(-5, -5, *(25,) * 8))) == "Narrow"  # two loss years
    assert _class(facts(years=_years(-5, *(25,) * 9))) == "Wide"  # one, before the last five
    assert _class(facts(years=_years(*(25,) * 9, -5))) == "Narrow"  # one in the last five
    assert _class(facts(years=_years(*(25,) * 5, 0, *(25,) * 4))) == "Narrow"  # nil is a loss
    assert _class(facts(years=_ten(9.5))) == "Wide"
    assert _class(facts(years=_ten(9.0))) == "Narrow"
    assert _class(facts(years=_years(*(10,) * 5, *(9,) * 5))) == "Narrow"  # 9.5%, 9.0%
    assert _class(facts(years=_years(*(8.5,) * 5, *(9.5,) * 5))) == "Narrow"  # 9.0%, 9.5%


def test_a_year_without_capital() -> None:
    # NOPAT 50 on a capital of −100 would read −50%: a profit with no capital is above any bar.
    free = facts(revenue_usd=1e9, years=tuple(ReturnYear(50.0, -100.0) for _ in range(10)))
    assert _class(free) == "Wide"  # the return route, at $1 billion
    recent = facts(revenue_usd=1e9, years=(*_ten(25)[:5], *(ReturnYear(50.0, 0.0),) * 5))
    assert _class(recent) == "Wide"
    # A loss of 50 on −100 would read +50%: a loss with no capital is below any bar.
    lossy = facts(years=tuple(ReturnYear(-50.0, -100.0) for _ in range(10)))
    assert _class(lossy) == "None"


def test_the_list() -> None:
    assert _class(facts(industry="Steel")) == "Narrow"
    assert _class(facts(industry="Steel", years=_ten(1))) == "None"
    assert _class(facts(industry="Chemicals")) == "Narrow"
    assert _class(facts(industry="Chemicals - Specialty")) == "Wide"
    assert _class(facts(industry="steel")) == "Wide"  # names compare exactly
    assert CYCLICAL == {
        "Residential Construction",
        "Engineering & Construction",
        "Construction Materials",
        "Real Estate - Services",
        "Auto - Dealerships",
        "Auto - Manufacturers",
        "Auto - Recreational Vehicles",
        "Oil & Gas Drilling",
        "Oil & Gas Exploration & Production",
        "Oil & Gas Integrated",
        "Oil & Gas Refining & Marketing",
        "Oil & Gas Equipment & Services",
        "Oil & Gas Midstream",
        "Coal",
        "Steel",
        "Copper",
        "Gold",
        "Other Precious Metals",
        "Industrial Materials",
        "Chemicals",
        "Agricultural Inputs",
        "Paper, Lumber & Forest Products",
        "Airlines, Airports & Air Services",
        "Marine Shipping",
        "Aluminum",
        "Silver",
        "Uranium",
    }
    assert len(CYCLICAL) == 27 and "Oil & Gas Energy" not in CYCLICAL


def _ranked(symbol: str, industry: str, sector: str, revenue: float | None) -> MoatFacts:
    """A company at 15% whose one other mark is its steady margin: Wide as a leader, else
    Narrow."""
    return facts(symbol, industry=industry, sector=sector, revenue_usd=revenue, years=_ten(15))


def test_the_group_and_the_rank() -> None:
    companies = [
        # Gears holds five companies with a revenue, EGEAR among them with nine years: the first
        # two by revenue lead, TIEA before TIEB on their tie.
        _ranked("AGEAR", "Gears", "Industrials", 5e9),
        _ranked("TIEB", "Gears", "Industrials", 4e9),
        _ranked("TIEA", "Gears", "Industrials", 4e9),
        _ranked("DGEAR", "Gears", "Industrials", 3e9),
        replace(_ranked("EGEAR", "Gears", "Industrials", 2e9), years=_ten(15)[:9]),
        # Pumps holds four with a revenue and one without; with Valves, the sector's other small
        # industry, they rank together, Gears' larger companies apart: VALVE, then APUMP.
        _ranked("APUMP", "Pumps", "Industrials", 0.9e9),
        _ranked("BPUMP", "Pumps", "Industrials", 0.8e9),
        _ranked("CPUMP", "Pumps", "Industrials", 0.7e9),
        _ranked("DPUMP", "Pumps", "Industrials", 0.6e9),
        _ranked("NOREV", "Pumps", "Industrials", None),
        _ranked("VALVE", "Valves", "Industrials", 0.95e9),
        # Another sector's small industries rank apart: LONE leads a group of one.
        _ranked("LONE", "Water", "Utilities", 0.1e9),
    ]
    assert draft_classes(companies) == {
        "AGEAR": "Wide",
        "TIEB": "Narrow",
        "TIEA": "Wide",
        "DGEAR": "Narrow",
        "EGEAR": "Narrow",
        "APUMP": "Wide",
        "BPUMP": "Narrow",
        "CPUMP": "Narrow",
        "DPUMP": "Narrow",
        "NOREV": "Narrow",
        "VALVE": "Wide",
        "LONE": "Wide",
    }


def _statement(year: int, **lines: Any) -> dict[str, Any]:
    return {"date": f"{year}-12-31", "symbol": "WIDE", "period": "FY", **lines}


def test_growth_and_the_margins() -> None:
    grower = facts(years=_ten(15), revenue_usd=12e9, fiscal_revenues=_GROWTH)
    assert _class(grower) == "Wide"
    # a revenue of None or 0 is no year of the ten; the tenth newest, not the oldest, is read
    assert _class(replace(grower, fiscal_revenues=(5e9, None, 0.0, *_GROWTH, 0.0))) == "Wide"
    assert _class(replace(grower, fiscal_revenues=(None, *_GROWTH[1:]))) == "Narrow"  # nine
    assert _class(replace(grower, fiscal_revenues=(-1e9, *_GROWTH[1:]))) == "Narrow"
    assert _class(replace(grower, fiscal_revenues=(*_GROWTH[:-1], -2e9))) == "Narrow"

    # twelve statements out of date order: the last ten by date
    twelve = [_statement(y, revenue=100.0, grossProfit=float(y - 1970)) for y in range(2014, 2026)]
    assert gross_margins(twelve[::-1]) == tuple((y - 1970) / 100 for y in range(2016, 2026))
    # one of the last ten without a gross profit: nine margins, none taken from before them
    holed = [_statement(2020, revenue=100.0) if s["date"] == "2020-12-31" else s for s in twelve]
    assert gross_margins(holed) == tuple((y - 1970) / 100 for y in range(2016, 2026) if y != 2020)
    odd = [
        _statement(2022, revenue=100, grossProfit=50),  # whole numbers count
        _statement(2023, revenue=0.0, grossProfit=50.0),  # no revenue
        _statement(2024, revenue=100.0, grossProfit="50"),  # not a number
        _statement(2025, revenue=100.0, grossProfit=None),
    ]
    assert gross_margins(odd) == (0.5,)
    assert gross_margins([]) == () and gross_margins({"revenue": 1.0}) == ()
    assert gross_margins(None) == () and gross_margins("[]") == ()

    # steady: ten margins, none below 80% of their median
    edge = facts(years=_ten(15), gross_margins=(0.4, *(0.5,) * 9))
    assert _class(edge) == "Wide"
    assert _class(replace(edge, gross_margins=_UNSTEADY)) == "Narrow"
    assert _class(replace(edge, gross_margins=(0.5,) * 9)) == "Narrow"
