"""The sensitivity reading's routes (spec 2026-11-06 Tier 2, 13.8 and 16; ``method.md`` 14.8).

``POST /api/companies/{symbol}/sensitivities`` takes ``{rowTag, rowValues, colTag, colValues}``
from an agent and answers 201 with the stored reading: the route's value a share on the
company's latest snapshot under its applied overrides, with the two inputs set to each pair of
the values given (``engine.sensitivity``). The owner's post answers 403, "a sensitivity reading
is an agent's write". The refusals, in this order: an axis with no value or more than five, 400
"an axis holds one to five values"; the same input on both axes, 400 "the two tags differ"; no
snapshot, 404; ``require_current``'s 409s ("settings changed: run a revalue" and its two
siblings); then each value as an override of it would be refused by the input's own rules
(``overrides.check_input``: a locked input, a tag that is not an input, a route that does not
read it, a value outside its words or its range), 400 with the rule's sentence, judged on the
route the row takes (``reviews_api.judged_route``: an applied ``phase`` override counts, and with
the phase on one axis the other input is judged on the route of each of its phases); last, the
store moved since the snapshot, 409 (``reviews_api.built_inputs``). The evidence rules and the
lifetime do not apply: a reading changes no input. Nothing is overridden and no review is
recomputed.

The reading is stored with the snapshot, the current review's id (``null`` without an applied
override), the writer, the policy version and the settings hash, with a ``sensitivity`` ledger
row resting on the snapshot, its summary "<row tag> by <column tag>, a grid of <n> rows and <m>
columns". The answer and ``GET /api/sensitivities/{id}`` (404 without it) carry its fields
camelCase, the pair in force as ``current``, ``[i, j]`` counted from 1 as the ref
``sensitivity:<id>/<i>/<j>`` counts the row and the column, ``null`` when no pair is in force;
and the words the report's Markdown writes the reading's table in (``charts.reading_axes``), which
the report page draws its grid with (spec 18.4): ``title``, "Sensitivity 7: the belief by the
runway return", ``rowLabel`` and ``colLabel``, each input's label, and ``rowWords`` and
``colWords``, each value as a cite of it reads.
"""

import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import datetime
from typing import Any, cast

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, FiniteFloat
from pydantic.alias_generators import to_camel

from fairband.engine.overrides import OverrideTag, check_input
from fairband.engine.sensitivity import axes_refusal, sensitivity_grid
from fairband.policy import Policy
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.reports.charts import reading_axes
from fairband.store.db import transaction
from fairband.store.ledger import record
from fairband.store.overrides import OverrideRow, applied_overrides, as_override
from fairband.store.reviews import latest_review
from fairband.store.sensitivities import insert_sensitivity, sensitivity_row
from fairband.store.snapshots import SnapshotRow
from fairband.web.agents_api import WriterOf, record_json
from fairband.web.reviews_api import (
    agents_only,
    built_inputs,
    counted,
    judged_route,
    require_current,
    snapshot_of,
)
from fairband.web.settings_api import effective

READINGS_WRITE = "a sensitivity reading is an agent's write"


class SensitivityPost(BaseModel):
    """The two axes, each an input's tag and its values; the keys camelCase."""

    model_config = ConfigDict(alias_generator=to_camel)

    row_tag: str
    row_values: list[FiniteFloat | str]
    col_tag: str
    col_values: list[FiniteFloat | str]


def add_sensitivity_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    tax: TaxTable,
    clock: Callable[[], datetime],
) -> None:
    """Register the sensitivity routes; ``policy`` is the file's, which the user's settings
    overlay, and ``tax`` the table the inputs are built with."""

    @app.post("/api/companies/{symbol}/sensitivities", status_code=201)
    def post_sensitivity(symbol: str, body: SensitivityPost, writer: WriterOf) -> dict[str, Any]:
        """Read the route's value at each pair of the two axes' values and store the grid."""
        agents_only(writer, READINGS_WRITE)
        refusal = axes_refusal(body.row_tag, body.row_values, body.col_tag, body.col_values)
        if refusal is not None:
            raise HTTPException(400, refusal)
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            symbol = exchange_symbol(symbol)
            snapshot = snapshot_of(conn, symbol)
            current = effective(conn, policy)
            require_current(current, snapshot)
            applied = applied_overrides(conn, symbol)
            refused = _refusal(body, applied, snapshot, current)
            if refused is not None:
                raise HTTPException(400, refused)
            inputs, deciles = built_inputs(conn, snapshot, current, tax, at.date())
            grid = sensitivity_grid(
                inputs,
                deciles,
                current,
                at.date(),
                {o.tag: o for o in map(as_override, applied)},
                cast(OverrideTag, body.row_tag),
                body.row_values,
                cast(OverrideTag, body.col_tag),
                body.col_values,
            )
            review = latest_review(conn, symbol)
            sensitivity_id = insert_sensitivity(
                conn,
                symbol,
                snapshot.id,
                None if review is None else review.id,
                body.row_tag,
                body.col_tag,
                grid,
                current.version,
                current.settings_hash,
                writer,
                at,
            )
            rows = counted(len(grid.rows), "row")
            cols = counted(len(grid.cols), "column")
            record(
                conn,
                writer,
                at,
                "sensitivity",
                symbol,
                "sensitivities",
                sensitivity_id,
                snapshot_id=snapshot.id,
                summary=f"{body.row_tag} by {body.col_tag}, a grid of {rows} and {cols}",
            )
            return _read(conn, sensitivity_id)

    @app.get("/api/sensitivities/{sensitivity_id}")
    def sensitivity(sensitivity_id: int) -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            return _read(conn, sensitivity_id)


def _read(conn: sqlite3.Connection, sensitivity_id: int) -> dict[str, Any]:
    """The reading as the API sends it; 404 without it."""
    found = sensitivity_row(conn, sensitivity_id)
    if found is None:
        raise HTTPException(404, f"no sensitivity {sensitivity_id}")
    axes = reading_axes(found)
    return record_json(found) | {
        "title": axes.title,
        "rowLabel": axes.row_label,
        "colLabel": axes.col_label,
        "rowWords": list(axes.rows),
        "colWords": list(axes.cols),
    }


def _refusal(
    body: SensitivityPost, applied: Sequence[OverrideRow], snapshot: SnapshotRow, policy: Policy
) -> str | None:
    """The sentence of the first input rule a value of the two axes breaks, the row's values
    first, each on the route the row takes (module docstring); ``None`` when every value passes."""
    axes = ((body.row_tag, body.row_values), (body.col_tag, body.col_values))
    phases: Sequence[float | str | None] = next(
        (values for tag, values in axes if tag == "phase"), [None]
    )
    for tag, values in axes:
        for value in values:
            for phase in [value] if tag == "phase" else phases:
                route = judged_route(tag, applied, snapshot, phase)
                if isinstance(route, tuple):  # an unclassified row: the refusal's sentence
                    return route[1]
                state, message = check_input(tag, value, route, policy)
                if state != "applied":
                    return message
    return None
