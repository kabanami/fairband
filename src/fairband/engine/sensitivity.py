"""A sensitivity reading of the route (spec 2026-11-06 Tier 2, 13.8; ``method.md`` 14.8): how
much of the route's value is assumption, as a grid the agent cites and does not compute.

``sensitivity_grid`` runs ``route.value_company`` on a company's inputs under the applied
overrides with two inputs of ``overrides.TAGS`` set to each pair of the values given: the cell
at row value ``r`` and column value ``c`` is the value a share under ``applied | {row_tag: r,
col_tag: c}``, an applied override on either input giving way to the pair's value, and ``None``
where the result has no value (a refusal). Nothing is overridden: the pair is read, never
stored as an override, and the review does not move.

Each axis holds one to five values (``AXIS_MAX``) of its own input, and the two inputs differ
(``axes_refusal``). The values are not checked against the input's rules here: the caller
checks each as an override of it would be (``overrides.check_input``).

``current`` is the pair in force: the row and the column whose values are the readings the
engine runs on, each the applied override's value when its input has one, else the engine's
own reading of the input on the result under the applied overrides
(``overrides.current_reading``; with none applied, the mechanical result), a number within
1e-12 and a word equal; the first such pair, ``None`` when no pair is it. The row and the column
are counted from 1, as the ref ``sensitivity:<id>/<i>/<j>`` counts them, so the stored pair, the
API's ``current`` and the ref name a cell the same way.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import Override, Overrides, OverrideTag, current_reading
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy

AXIS_MAX = 5  # the values an axis holds at most: a grid of five by five
AXIS_SIZE = "an axis holds one to five values"
DISTINCT_TAGS = "the two tags differ"
# How near a value is to the reading in force to mark its pair.
_IN_FORCE = 1e-12
# The note on a pair's input in a cell's result, which is never stored.
_READING = "a sensitivity reading"

type Value = float | str


@dataclass(frozen=True)
class SensitivityGrid:
    """The row input's values, the column input's, the value a share at each pair (a row of
    cells for each row value, ``None`` where the engine values none) and the pair in force,
    counted from 1 (module docstring)."""

    rows: tuple[Value, ...]
    cols: tuple[Value, ...]
    cells: tuple[tuple[float | None, ...], ...]
    current: tuple[int, int] | None


def axes_refusal(
    row_tag: str, row_values: Sequence[Value], col_tag: str, col_values: Sequence[Value]
) -> str | None:
    """Why the two axes make no grid, or ``None``: an axis with no value or more than
    ``AXIS_MAX``, or one input on both."""
    if not all(1 <= len(values) <= AXIS_MAX for values in (row_values, col_values)):
        return AXIS_SIZE
    if row_tag == col_tag:
        return DISTINCT_TAGS
    return None


def sensitivity_grid(
    inputs: CompanyInputs,
    deciles: Deciles | None,
    policy: Policy,
    today: date,
    applied: Overrides,
    row_tag: OverrideTag,
    row_values: Sequence[Value],
    col_tag: OverrideTag,
    col_values: Sequence[Value],
) -> SensitivityGrid:
    """The grid of ``row_tag`` at ``row_values`` by ``col_tag`` at ``col_values`` under the
    ``applied`` overrides by tag (module docstring); ``ValueError`` with ``axes_refusal``'s
    sentence for axes that make no grid."""
    refusal = axes_refusal(row_tag, row_values, col_tag, col_values)
    if refusal is not None:
        raise ValueError(refusal)
    at = datetime.combine(today, time(), UTC)

    def cell(r: Value, c: Value) -> float | None:
        pair = {
            row_tag: Override(None, row_tag, r, "agent", None, at, _READING),
            col_tag: Override(None, col_tag, c, "agent", None, at, _READING),
        }
        return value_company(inputs, deciles, policy, today, {**applied, **pair}).value

    cells = tuple(tuple(cell(r, c) for c in col_values) for r in row_values)
    in_force = value_company(inputs, deciles, policy, today, applied)
    row = _matching(row_values, _reading(applied, in_force, row_tag))
    col = _matching(col_values, _reading(applied, in_force, col_tag))
    current = None if row is None or col is None else (row, col)
    return SensitivityGrid(tuple(row_values), tuple(col_values), cells, current)


def _reading(applied: Overrides, in_force: ValuationResult, tag: OverrideTag) -> Value | None:
    """The reading of ``tag``'s input the engine runs on: the applied override's value, else its
    own reading on ``in_force``, the result under the applied overrides."""
    found = applied.get(tag)
    return current_reading(in_force, tag) if found is None else found.value


def _matching(values: Sequence[Value], reading: Value | None) -> int | None:
    """The first of ``values`` that is ``reading``, counted from 1: a number within 1e-12, a word
    equal; ``None`` when none is."""
    for k, value in enumerate(values, 1):
        if isinstance(value, str) or isinstance(reading, str):
            if value == reading:
                return k
        elif reading is not None and abs(value - reading) <= _IN_FORCE:
            return k
    return None
