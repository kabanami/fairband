"""The report page's ROIC chart on a year whose average invested capital is at or below zero
(B-8, the founder's ruling of 2026-11-15; method 16.6): the year's figure has the wrong sign and
no meaning, so the chart leaves it out and a line under it names the years and why. charts.js
runs in node after the bundle and app.js (``page.mjs``), and the test reads what its
``roicPoints`` makes of the returns table's two rows."""

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
NOTE = "average invested capital is at or below zero"

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _call(helper: str, *args: Any) -> Any:
    """What charts.js's ``helper`` returns on ``args``, through JSON."""
    assert NODE is not None
    done = subprocess.run(
        [
            NODE,
            str(HARNESS),
            str(BUNDLE),
            str(STATIC / "app.js"),
            helper,
            str(STATIC / "charts.js"),
        ],
        input=json.dumps(list(args)),
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return json.loads(done.stdout)


def _row(values: list[float | None], notes: dict[str, str] | None = None) -> dict[str, Any]:
    """A table row over fiscal 2021 to 2025, each cell as the financial tables' read serves it."""
    cells = [
        {"period": str(2021 + k), "value": v, "unit": "percent", "ref": None, "note": None}
        for k, v in enumerate(values)
    ]
    for cell in cells:
        cell["note"] = (notes or {}).get(cell["period"])
    return {"name": "row", "unit": "percent", "cells": cells}


HURDLE = _row([0.09] * 5)


def test_a_year_on_capital_at_or_below_zero_is_left_out_and_named() -> None:
    roic = _row([0.20, 0.25, 0.30, -37.4, -71.1], {"2024": NOTE, "2025": NOTE})
    drawn = _call("reportCharts.roicPoints", roic, HURDLE)
    assert [p["period"] for p in drawn["series"]] == ["2021", "2022", "2023"]
    assert drawn["series"][0] == {"period": "2021", "roic": pytest.approx(20.0), "wacc": 9.0}
    assert drawn["left"] == (
        "Fiscal 2024 and 2025 are not drawn: average invested capital is at or below zero."
    )


def test_one_year_left_out_reads_in_the_singular() -> None:
    roic = _row([0.20, 0.25, 0.30, 0.31, -71.1], {"2025": NOTE})
    drawn = _call("reportCharts.roicPoints", roic, HURDLE)
    assert len(drawn["series"]) == 4
    assert drawn["left"] == (
        "Fiscal 2025 is not drawn: average invested capital is at or below zero."
    )


def test_a_row_without_such_a_year_draws_every_point_and_says_nothing() -> None:
    drawn = _call("reportCharts.roicPoints", _row([0.20, None, 0.30, 0.31, 0.32]), HURDLE)
    assert [p["period"] for p in drawn["series"]] == ["2021", "2023", "2024", "2025"]  # a gap
    assert drawn["left"] is None
    assert _call("reportCharts.roicPoints", None, HURDLE) == {"series": [], "left": None}


def test_three_years_left_out_are_listed_with_commas() -> None:
    notes = {"2023": NOTE, "2024": NOTE, "2025": NOTE}
    drawn = _call("reportCharts.roicPoints", _row([0.2, 0.2, -5.0, -6.0, -7.0], notes), HURDLE)
    assert drawn["left"] == (
        "Fiscal 2023, 2024 and 2025 are not drawn: average invested capital is at or below zero."
    )
