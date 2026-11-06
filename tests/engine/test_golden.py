"""The six engine fixtures under the packaged policy at its defaults, against the result dicts
captured from method 0.7 and policy v5 before the settings build (spec 2026-11-04, 2 and 11).
The version fields are masked, and so is the policy name a RULE input cites in its provenance:
the dict's figures are what must not move."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from support.engine_companies import (
    decline_inputs,
    high_growth_inputs,
    mature_growth_inputs,
    mature_stable_inputs,
    start_up_inputs,
    universe_deciles,
    young_growth_inputs,
)

from fairband.engine.route import value_company
from fairband.engine.types import ValuationResult, result_to_json
from fairband.policy import load_policy

TODAY = date(2026, 10, 31)
GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden"
MASKED = ("policy_version", "method_version", "settings_hash")
FIXTURES = {
    "MGCO": mature_growth_inputs,
    "MSCO": mature_stable_inputs,
    "HGCO": high_growth_inputs,
    "YGCO": young_growth_inputs,
    "DCCO": decline_inputs,
    "SUCO": start_up_inputs,
}  # the fixtures' own symbols (tests/support/engine_companies.py)


def golden_dict(result: ValuationResult) -> dict[str, Any]:
    d: dict[str, Any] = json.loads(result_to_json(result))
    for key in MASKED:
        d.pop(key, None)
    for tagged in d["inputs"]:
        if tagged["provenance"]["source"].startswith("policy "):
            tagged["provenance"]["source"] = "policy"
    return d


@pytest.mark.parametrize("symbol", sorted(FIXTURES))
def test_defaults_match_the_golden(symbol: str) -> None:
    result = value_company(FIXTURES[symbol](), universe_deciles(), load_policy(), TODAY)
    assert golden_dict(result) == json.loads((GOLDEN / f"{symbol}.json").read_text())
