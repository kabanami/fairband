"""The sensitivity reading of the route (spec 2026-11-06 Tier 2, 13.8; ``method.md`` 14.8): the
engine under the applied overrides with two inputs set to each pair of the values given, a cell
``None`` where the engine values none, and the pair in force counted from 1, as the ref
``sensitivity:<id>/<i>/<j>`` counts it."""

from collections.abc import Mapping
from datetime import UTC, date, datetime

import pytest

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import Override, OverrideTag, current_reading
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.sensitivity import (
    AXIS_MAX,
    AXIS_SIZE,
    DISTINCT_TAGS,
    SensitivityGrid,
    axes_refusal,
    sensitivity_grid,
)
from fairband.policy import Policy

TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)  # the time the applied overrides are made
BELIEFS, RUNWAYS = (0.05, 0.08), (0.10, 0.20)


def _applied(values: Mapping[OverrideTag, float | str]) -> dict[OverrideTag, Override]:
    return {
        tag: Override(1, tag, value, "agent", "claude-opus-5-5", NOW, "guidance raised")
        for tag, value in values.items()
    }


def _engine(
    inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
    values: Mapping[OverrideTag, float | str],
) -> float | None:
    return value_company(inputs, deciles, policy, TODAY, _applied(values)).value


def test_the_grid_is_the_engine_under_each_pair(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    grid = sensitivity_grid(
        mg_inputs, deciles, policy, TODAY, {}, "growth.belief", BELIEFS, "return.runway", RUNWAYS
    )
    assert (grid.rows, grid.cols) == (BELIEFS, RUNWAYS)
    assert grid.cells == tuple(
        tuple(
            _engine(mg_inputs, deciles, policy, {"growth.belief": b, "return.runway": c})
            for c in RUNWAYS
        )
        for b in BELIEFS
    )
    assert all(isinstance(cell, float) for row in grid.cells for cell in row)
    assert grid.current is None  # MGCO's belief is 6.3%, its runway return 43.1%

    mechanical = value_company(mg_inputs, deciles, policy, TODAY)
    belief = current_reading(mechanical, "growth.belief")
    runway = current_reading(mechanical, "return.runway")
    assert isinstance(belief, float) and isinstance(runway, float)
    found = sensitivity_grid(
        mg_inputs,
        deciles,
        policy,
        TODAY,
        {},
        "growth.belief",
        (belief, 0.08),
        "return.runway",
        (0.10, runway),
    )
    assert found.current == (1, 2)  # row 1, column 2: the engine's own readings
    assert found.cells[0][1] == mechanical.value  # an override at the reading moves nothing


def test_the_grid_runs_under_the_applied_overrides(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A moat override stays under every cell; an applied override on an axis's input gives way
    to the pair's value and marks the pair in force."""
    applied = {"moat.class": "Narrow", "growth.belief": 0.05, "return.runway": 0.20}
    grid = sensitivity_grid(
        mg_inputs,
        deciles,
        policy,
        TODAY,
        _applied(applied),
        "growth.belief",
        BELIEFS,
        "return.runway",
        RUNWAYS,
    )
    assert grid.cells == tuple(
        tuple(
            _engine(
                mg_inputs,
                deciles,
                policy,
                {"moat.class": "Narrow", "growth.belief": b, "return.runway": c},
            )
            for c in RUNWAYS
        )
        for b in BELIEFS
    )
    assert grid.current == (1, 2)  # the applied belief of 5% and runway return of 20%
    assert grid.cells[0][1] == _engine(mg_inputs, deciles, policy, applied)


def test_a_one_time_item_marks_the_ntm_cell_in_force(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-14 5, as changed on the review of Task 3: on MGCO, an NTM EPS of $5.90, under
    an applied one-time item of $0.59 the reviewed value rests on year 1 at $5.31. A guided EPS
    stands in for the consensus with its items, so the item is moot under it: the EPS that gives
    the reviewed value is $5.31, and the grid marks that cell, whose value is the reviewed one;
    the cell at $5.90 is the mechanical value."""
    applied = _applied({"earnings.ntm_nri": 0.59})
    reviewed = value_company(mg_inputs, deciles, policy, TODAY, applied)
    mechanical = value_company(mg_inputs, deciles, policy, TODAY)
    belief = current_reading(reviewed, "growth.belief")
    assert isinstance(belief, float) and reviewed.value is not None
    grid = sensitivity_grid(
        mg_inputs,
        deciles,
        policy,
        TODAY,
        applied,
        "earnings.ntm",
        (5.31, 5.90),
        "growth.belief",
        (belief,),
    )
    assert grid.current == (1, 1)
    assert grid.cells[0][0] == pytest.approx(reviewed.value)
    assert grid.cells[1][0] == pytest.approx(mechanical.value)


def test_a_word_input_marks_its_pair(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    grid = sensitivity_grid(
        mg_inputs,
        deciles,
        policy,
        TODAY,
        {},
        "moat.class",
        ("None", "Narrow", "Wide"),
        "growth.belief",
        (0.063,),
    )
    assert grid.current == (3, 1)  # MGCO is Wide, its belief 6.3%
    assert grid.cells[1] == (
        _engine(mg_inputs, deciles, policy, {"moat.class": "Narrow", "growth.belief": 0.063}),
    )


@pytest.mark.parametrize("off,marked", [(0.0, True), (1e-13, True), (-1e-13, True), (1e-11, False)])
def test_the_pair_in_force_matches_within_1e_12(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy, off: float, marked: bool
) -> None:
    grid = sensitivity_grid(
        mg_inputs,
        deciles,
        policy,
        TODAY,
        {},
        "growth.belief",
        (0.063 + off,),
        "moat.class",
        ("Wide",),
    )
    assert grid.current == ((1, 1) if marked else None)


def test_a_refused_cell_is_null(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """HGCO holds 15% from year four at a 20% target margin: a held rate of −20% at an 8% margin
    leaves no positive value under the reinvestment charge."""
    holds, margins = (-0.20, 0.15), (0.08, 0.20)
    grid = sensitivity_grid(
        high_growth_inputs, deciles, policy, TODAY, {}, "path.hold", holds, "margin.target", margins
    )
    refused = value_company(
        high_growth_inputs,
        deciles,
        policy,
        TODAY,
        _applied({"path.hold": -0.20, "margin.target": 0.08}),
    )
    assert (refused.value, refused.refusal) == (
        None,
        "value not positive under the reinvestment charge",
    )
    assert grid.cells[0][0] is None
    for i, j in ((0, 1), (1, 0), (1, 1)):
        values: dict[OverrideTag, float | str] = {
            "path.hold": holds[i],
            "margin.target": margins[j],
        }
        cell = grid.cells[i][j]
        assert cell is not None and cell == _engine(high_growth_inputs, deciles, policy, values)
    mechanical = value_company(high_growth_inputs, deciles, policy, TODAY)
    assert grid.current == (2, 2) and grid.cells[1][1] == mechanical.value


@pytest.mark.parametrize(
    "row_tag,rows,col_tag,cols,refusal",
    [
        ("growth.belief", (), "return.runway", (0.1,), AXIS_SIZE),
        ("growth.belief", (0.1,), "return.runway", (0.1,) * (AXIS_MAX + 1), AXIS_SIZE),
        ("growth.belief", (0.1,), "growth.belief", (0.2,), DISTINCT_TAGS),
        ("growth.belief", (0.1,) * AXIS_MAX, "return.runway", (0.1,) * AXIS_MAX, None),
    ],
)
def test_an_axis_holds_one_to_five_values_of_its_own_tag(
    mg_inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
    row_tag: OverrideTag,
    rows: tuple[float, ...],
    col_tag: OverrideTag,
    cols: tuple[float, ...],
    refusal: str | None,
) -> None:
    assert axes_refusal(row_tag, rows, col_tag, cols) == refusal
    if refusal is None:
        grid = sensitivity_grid(mg_inputs, deciles, policy, TODAY, {}, row_tag, rows, col_tag, cols)
        assert isinstance(grid, SensitivityGrid) and len(grid.cells) == AXIS_MAX
        return
    with pytest.raises(ValueError, match=refusal):
        sensitivity_grid(mg_inputs, deciles, policy, TODAY, {}, row_tag, rows, col_tag, cols)


def test_the_messages_are_the_server_s() -> None:
    assert (AXIS_MAX, AXIS_SIZE, DISTINCT_TAGS) == (
        5,
        "an axis holds one to five values",
        "the two tags differ",
    )
