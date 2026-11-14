"""The drawer's Charge group on a Mature Growth or Mature Stable row (spec 2026-11-09 6.2, 6.3 and
12; method 4.8): the return each year pays at, the growth the charge pays for beside the earnings
growth, and the newest year's marginal return, in plain words. The page's own script runs in node
after the bundle (``page.mjs``), and the test reads what ``chargeRows`` makes of a row's
intermediates: MGCO's and MSCO's from their goldens, and hand-built ones for the other forms."""

import json
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

RETURNS = "Return by year"
GROWTH = "Growth the charge pays for"
NEWEST = "Newest year's marginal return"


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


def _rows(im: dict[str, Any]) -> list[list[Any]]:
    """``chargeRows(im)`` as app.js returns it: [label, text, numeric] rows."""
    rows: list[list[Any]] = _call("chargeRows", im)
    return rows


def _texts(node: Any) -> list[str]:
    """The text of an element tree, in order: its strings and its children's."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [text for child in node for text in _texts(child)]
    if isinstance(node, dict):
        return _texts(node.get("props", {}).get("children", []))
    return []


def _golden(symbol: str) -> dict[str, Any]:
    im: dict[str, Any] = json.loads((GOLDEN / f"{symbol}.json").read_text())["intermediates"]
    return im


def _returns(r: float, t: float, n: int, k: int) -> list[float]:
    """Method 4.8's return by year: ``r`` through year ``k``, then in a straight line to ``t``,
    which year ``n`` takes; with ``k`` at ``n`` - 1 or more, ``r`` to year ``n`` - 1."""
    if k >= n - 1:
        return [r] * (n - 1) + [t]
    return [r] * k + [r + (t - r) * (y - k) / (n - k) for y in range(k + 1, n)] + [t]


Pair = tuple[float | None, float | None]


def _growth_row(
    revenue: Pair,
    earnings: tuple[float, float] = (0.25, 0.20),
    runway: int = 10,
    hold: int = 6,
    one_year: float | None = 0.21,
    used: str = "marginal",
    charge_off: bool = False,
    found: Pair | None = None,
    source: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """A Mature Growth row's intermediates: earnings growth ``earnings`` in years 2 and 3 and 6%
    after, the revenue steps ``revenue`` the charge read (``None`` takes that year's earnings
    growth), a 20% runway return held through ``hold`` and faded to 13% in year ``runway``, the
    terminal growth 3%. With ``source``, the charge records the consensus's steps as ``found`` and
    each year's source (spec 2026-11-14 6.3); without, it is a result stored before them."""
    paid = [e if g is None else g for g, e in zip(revenue, earnings, strict=True)]
    later = [0.06] * (runway - 3)
    recorded = (
        {}
        if source is None
        else {
            "revenue_steps_found": list(found or (None, None)),
            "revenue_step_source": list(source),
        }
    )
    return {
        "path_steps": list(earnings),
        "growth_rates": [*earnings, *later],
        "runway_return": {"used": used, "one_year": one_year},
        "charge_off": charge_off,
        "charge": {
            "growth_by_year": [*paid, *later, 0.03],
            "return_by_year": _returns(0.20, 0.13, runway, hold),
            "hold_years": hold,
            "revenue_steps": list(revenue),
            **recorded,
        },
    }


def test_mgco_holds_its_return_then_fades_on_its_earnings_growth() -> None:
    """MGCO's golden: a 43.1% runway return held through year 6 and faded to 13.0% in year 20, its
    20-year runway; no revenue consensus, so the charge pays for the earnings growth, 12.0% then
    10.0%; the newest year's marginal return 45.7%."""
    assert _rows(_golden("MGCO")) == [
        [RETURNS, "43.1% through year 6, then to 13.0% in year 20", False],
        [
            GROWTH,
            "12.0% then 10.0%, the earnings growth: years 2 and 3 have no revenue consensus",
            False,
        ],
        [NEWEST, "45.7%", True],
    ]


def test_msco_fades_from_year_1_on_the_terminal_growth() -> None:
    """MSCO's golden: no year grows above the terminal growth, so the return fades from year 1,
    18.0% there, to 13.0% in year 20; the path grows at the terminal growth, 3.0%, every year; the
    newest year's marginal return 18.3%."""
    assert _rows(_golden("MSCO")) == [
        [RETURNS, "from 18.0% in year 1 to 13.0% in year 20", False],
        [GROWTH, "3.0% a year, the terminal growth", False],
        [NEWEST, "18.3%", True],
    ]


def test_a_refused_mature_row_draws_its_charge_under_its_phase_s_route() -> None:
    """A Mature Growth row refused "value not positive under the reinvestment charge" has no route
    but keeps its charge, the row whose cash years go below zero: the section takes the route's
    name from the phase and draws the Charge group."""
    result = {"route": None, "phase": {"phase": "Mature Growth"}, "intermediates": _golden("MGCO")}
    assert _texts(_call("matureRoute", result)) == [
        "Mature growth route",
        "Charge",
        RETURNS,
        "43.1% through year 6, then to 13.0% in year 20",
        GROWTH,
        "12.0% then 10.0%, the earnings growth: years 2 and 3 have no revenue consensus",
        NEWEST,
        "45.7%",
    ]


def test_the_revenue_steps_stand_beside_the_earnings_growth() -> None:
    rows = _rows(_growth_row((0.15, 0.10)))
    assert rows[:2] == [
        [RETURNS, "20.0% through year 6, then to 13.0% in year 10", False],
        [GROWTH, "15.0% then 10.0% on revenue, against earnings of 25.0% then 20.0%", False],
    ]


def test_a_missing_revenue_step_takes_its_years_earnings_growth() -> None:
    year_2 = (
        "25.0% then 10.0%, against earnings of 25.0% then 20.0%: year 2 has no revenue consensus"
        " and takes its earnings growth, year 3 is on revenue"
    )
    year_3 = (
        "15.0% then 20.0%, against earnings of 25.0% then 20.0%: year 2 is on revenue, year 3 has"
        " no revenue consensus and takes its earnings growth"
    )
    assert _rows(_growth_row((None, 0.10)))[1] == [GROWTH, year_2, False]
    assert _rows(_growth_row((0.15, None)))[1] == [GROWTH, year_3, False]


AGAINST = ", against earnings of 25.0% then 20.0%"
NO_CONSENSUS = " has no revenue consensus and takes its earnings growth"


@pytest.mark.parametrize(
    ("revenue", "found", "source", "line"),
    [
        # the consensus's steps, read: as a result stored before the source reads
        (
            (0.15, 0.10),
            (0.15, 0.10),
            ("consensus", "consensus"),
            f"15.0% then 10.0% on revenue{AGAINST}",
        ),
        # an agent's step in place of the consensus's 9.0%
        (
            (0.18, 0.10),
            (0.09, 0.10),
            ("agent", "consensus"),
            f"18.0% then 10.0%{AGAINST}: year 2 is on revenue from an override, year 3 is on revenue",
        ),
        # an agent's step where the consensus gives none
        (
            (0.15, 0.12),
            (0.15, None),
            ("consensus", "agent"),
            f"15.0% then 12.0%{AGAINST}: year 2 is on revenue, year 3 is on revenue from an override",
        ),
        (
            (None, 0.12),
            (None, None),
            ("none", "agent"),
            f"25.0% then 12.0%{AGAINST}: year 2{NO_CONSENSUS}, year 3 is on revenue from an override",
        ),
        (
            (0.18, 0.12),
            (0.09, 0.10),
            ("agent", "agent"),
            f"18.0% then 12.0% on revenue from overrides{AGAINST}",
        ),
        # no revenue consensus: the earnings growth, as a result stored before the source reads
        (
            (None, 0.10),
            (None, 0.10),
            ("none", "consensus"),
            f"25.0% then 10.0%{AGAINST}: year 2{NO_CONSENSUS}, year 3 is on revenue",
        ),
        (
            (None, None),
            (None, None),
            ("none", "none"),
            "25.0% then 20.0%, the earnings growth: years 2 and 3 have no revenue consensus",
        ),
    ],
)
def test_each_year_says_where_the_growth_the_charge_pays_for_comes_from(
    revenue: Pair, found: Pair, source: tuple[str, str], line: str
) -> None:
    """Spec 2026-11-14 6.3: the charge records each year's source, and its line says which growth
    the charge paid for: the consensus revenue step, an agent's revenue step, an override, or the
    earnings growth where the consensus gives no revenue step. The steps the charge read alone
    cannot tell an agent's step from the consensus's."""
    rows = _rows(_growth_row(revenue, found=found, source=source))
    assert rows[1] == [GROWTH, line, False]


@pytest.mark.parametrize("revenue", [(0.15, 0.10), (None, 0.10), (0.15, None), (None, None)])
def test_a_result_stored_before_the_source_reads_as_the_steps_the_charge_read(
    revenue: Pair,
) -> None:
    """A result stored before spec 2026-11-14 has the steps the charge read alone: a step there is
    the consensus's, none the earnings growth, as a result with those sources reads."""
    source = tuple("none" if step is None else "consensus" for step in revenue)
    recorded = _growth_row(revenue, found=revenue, source=(source[0], source[1]))
    assert _rows(_growth_row(revenue)) == _rows(recorded)


THIN = " has too few analysts on file for a revenue consensus as high as "


@pytest.mark.parametrize(
    ("revenue", "found", "source", "line"),
    [
        (
            (0.15, None),
            (0.15, 0.61),
            ("consensus", "thin"),
            (
                f"15.0% then 20.0%{AGAINST}: year 2 is on revenue, year 3{THIN}61.0% and takes"
                " its earnings growth"
            ),
        ),
        (
            (None, None),
            (3.105, None),
            ("thin", "none"),
            (
                f"25.0% then 20.0%{AGAINST}: year 2{THIN}310.5% and takes its earnings growth,"
                f" year 3{NO_CONSENSUS}"
            ),
        ),
    ],
)
def test_a_thin_revenue_step_takes_its_years_earnings_growth(
    revenue: Pair, found: Pair, source: tuple[str, str], line: str
) -> None:
    """Spec 2026-11-14 6.2, as narrowed: a consensus revenue step above 50% on fewer revenue
    analysts than the analyst minimum, or no count, is not read, and the charge pays for the
    year's earnings growth. The line says the year has a revenue consensus, unlike a year with
    none, gives its step as found, and names the two limits in words, as the drawer holds
    neither figure: too few analysts, for a step that high. The figures are spec 6's: BIPC's step
    of 310.5% on one analyst, FRO's of 61.0% on two."""
    rows = _rows(_growth_row(revenue, found=found, source=source))
    assert rows[1] == [GROWTH, line, False]
    assert "thin" not in line and "_" not in line


def test_a_hold_to_the_year_before_the_last_is_the_shape_as_built() -> None:
    """With the hold at N − 1 or more (a short runway cut mid-fade) only year N takes the terminal
    return."""
    assert _rows(_growth_row((0.15, 0.10), runway=5, hold=4))[0] == [
        RETURNS,
        "20.0% through year 4, then 13.0% in year 5",
        False,
    ]


def test_a_one_year_runway_has_the_terminal_return_alone() -> None:
    im = _growth_row((0.15, 0.10))
    im["charge"]["return_by_year"] = [0.13]
    im["charge"]["hold_years"] = 0
    assert _rows(im)[0] == [RETURNS, "13.0% in year 1", False]


def test_a_return_that_does_not_move_reads_every_year() -> None:
    """A runway return that rounds to the terminal return, a Narrow row floored at r for one, is
    one figure in every year: no fade to the same figure."""
    im = _growth_row((0.15, 0.10))
    im["charge"]["return_by_year"] = [0.09] * 10
    assert _rows(im)[0] == [RETURNS, "9.0% in every year", False]


def test_a_charge_off_charges_the_last_year_alone() -> None:
    """Method 4.6 rule 4: with the runway charge off, years 1 to N − 1 are not charged and year N
    and the terminal charge at the terminal return."""
    im = _growth_row((0.15, 0.10), used="off", charge_off=True)
    im["charge"]["return_by_year"] = [0.13] * 10
    assert _rows(im)[0] == [RETURNS, "no charge in years 1 to 9, then 13.0% in year 10", False]


def test_an_override_charges_a_row_whose_measure_was_off() -> None:
    """A ``return.runway`` override charges every year (method 14.2) though the measure still
    reads "off": the row's ``charge_off`` decides, not the measure. An override below the Wide
    cap starts the return under the terminal return, so it rises to it: "then to", not "fading"."""
    im = _growth_row((0.15, 0.10), runway=20, used="off")
    im["charge"]["return_by_year"] = _returns(0.11, 0.13, 20, 6)
    assert _rows(im)[0] == [RETURNS, "11.0% through year 6, then to 13.0% in year 20", False]


def _lifted_row(
    measure: float | None, marginal_usable: bool = True, capital_free: bool = False
) -> dict[str, Any]:
    """A row whose measure with goodwill, 6.2% on the five-year marginal or 4.1% on the
    three-year, is below the hurdle rate, with ``measure`` on capital without goodwill."""
    im = _growth_row((0.15, 0.10), one_year=None, used="without-goodwill")
    im["runway_return"] |= {
        "marginal": 0.062,
        "marginal_usable": marginal_usable,
        "three_year": 0.041,
        "without_goodwill": {
            "marginal": measure,
            "marginal_usable": measure is not None,
            "three_year": None,
            "measure": measure,
            "capital_free": capital_free,
        },
    }
    return im


def test_a_return_read_without_goodwill_shows_both_measures() -> None:
    """Method 4.6 rule 5: the measure below the hurdle rate, then the same measure on capital
    without goodwill and intangibles, under the return by year, which shows the start."""
    with_goodwill, without = "Return with goodwill", "Return without goodwill"
    assert _rows(_lifted_row(0.527))[2:] == [
        [with_goodwill, "6.2%, below the hurdle rate", True],
        [without, "52.7%", True],
    ]
    assert _rows(_lifted_row(0.223, marginal_usable=False))[2:] == [
        [with_goodwill, "4.1%, below the hurdle rate", True],
        [without, "22.3%", True],
    ]
    assert _rows(_lifted_row(None, capital_free=True))[2:] == [
        [with_goodwill, "6.2%, below the hurdle rate", True],
        [without, "no capital without goodwill", False],
    ]


def test_a_row_on_another_measure_shows_no_goodwill_rows() -> None:
    """The measures without goodwill are recorded on every row (MGCO's golden holds them) and
    drawn only where the charge read them."""
    assert [row[0] for row in _rows(_golden("MGCO"))] == [RETURNS, GROWTH, NEWEST]
    floored = _lifted_row(0.05)
    floored["runway_return"]["used"] = "floor"
    assert [row[0] for row in _rows(floored)] == [RETURNS, GROWTH]


def test_no_newest_year_figure_leaves_its_row_out() -> None:
    rows = _rows(_growth_row((0.15, 0.10), one_year=None))
    assert [row[0] for row in rows] == [RETURNS, GROWTH]
