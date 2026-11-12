"""The policy's JSON shapes: the values the Methodology page cites (spec 2026-11-04 7.4), the
Settings form (8.7) and the universe's growth deciles (7.4).

Each value is served in the JSON form of ``fairband.policy.settings.value_of``: a number, a list
for a pair or a tuple, a table by moat. A setting is ``changed`` when the user's overlay holds it,
that is when the user set it away from its default. A value a changed setting carries along (the
Mid band's floor, under a changed size floor) is served as the effective policy has it but does
not read changed: resetting it would change nothing. A derived value is changed when it differs
from the file's.

Besides the forty settings, the page cites nine values that are not settings, read from the file
only, among them the foreign filers' two bounds (the inflation bound and the stale-rate bound, spec
2026-11-10 9), and the two the policy derives (the designation edges and the Wide moat's terminal
return cap). The policy's tables (the base rates, the ratings, the default probabilities, the
patterns, the industries) are never served, and nothing in the policy is a key.
"""

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from fairband.engine.classifier import GROWTH_WORDS, Deciles
from fairband.policy import Policy
from fairband.policy.settings import SETTINGS, default_of, value_of

# The cited values that are not settings, with their unit. A score shows as a plain number, as a
# count does.
READ_ONLY: dict[str, str] = {
    "moat_wide_min": "count",
    "moat_narrow_min": "count",
    "peer_margin_min_years": "years",
    "z_distress": "count",
    "z_safe": "count",
    "f_score_low": "count",
    "implied_margin_bounds": "fraction",
    "inflation_max": "fraction",
    "fx_stale_days": "days",
    "return_without_goodwill_cap": "fraction",
}
# The derived values, with their unit and the source line the file no longer holds.
DERIVED: dict[str, tuple[str, str]] = {
    "designation_edges": (
        "times",
        (
            "derived (spec 2026-11-04 8.3): 1 − the Narrow margin of safety, the fair band's low "
            "and high, the trim multiple; stocks method v1.7 Step 10"
        ),
    ),
    "wide_terminal_roic_cap": (
        "fraction",
        "derived (spec 2026-11-04 8.3): r + the Wide-moat terminal spread; design.md 6.6",
    ),
}


def policy_json(policy: Policy, base: Policy, overlay: Mapping[str, Any]) -> dict[str, Any]:
    """The values the page cites from ``policy``, the effective one, by name; ``base`` is the
    file's policy, which holds the defaults and the source lines."""
    values: dict[str, dict[str, Any]] = {}
    for s in SETTINGS:
        values[s.name] = _cited(
            value_of(s.name, policy), s.unit, _source(base, s.name), True, s.name in overlay
        )
    for name, unit in READ_ONLY.items():
        values[name] = _cited(
            _plain(getattr(policy, name)), unit, _source(base, name), False, False
        )
    for name, (unit, source) in DERIVED.items():
        value = _plain(getattr(policy, name))
        values[name] = _cited(value, unit, source, False, value != _plain(getattr(base, name)))
    return {
        "version": policy.version,
        "settingsHash": policy.settings_hash,
        "changed": _changed(overlay),
        "values": values,
    }


def settings_json(
    policy: Policy,
    base: Policy,
    overlay: Mapping[str, Any],
    changed_at: Mapping[str, datetime],
    valued_under: Mapping[str, Any],
) -> dict[str, Any]:
    """The Settings form: the settings in their groups, each with its default from ``base``, its
    value in ``policy``, when it last changed, and what the page shows of it; the current policy
    version and settings hash; and ``valued_under``, what the screen's figures were valued under."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for s in SETTINGS:
        at = changed_at.get(s.name)
        groups.setdefault(s.group, []).append(
            {
                "name": s.name,
                "label": s.label,
                "description": s.description,
                "unit": s.unit,
                "default": default_of(s.name, base),
                "value": value_of(s.name, policy),
                "range": s.range_text,
                "effect": s.effect,
                "source": _source(base, s.name),
                "changed": s.name in overlay,
                "changedAt": None if at is None else at.isoformat(),
            }
        )
    return {
        "groups": [{"name": name, "settings": rows} for name, rows in groups.items()],
        "current": {"policyVersion": policy.version, "settingsHash": policy.settings_hash},
        "valuedUnder": dict(valued_under),
    }


def deciles_json(deciles: Deciles) -> dict[str, Any]:
    """The universe's nine revenue-growth decile edges, the deciles each growth word covers (the
    classifier's word i covers deciles 2i + 1 and 2i + 2), highest first, and the number of
    companies the edges were read from."""
    words = {word: [2 * i + 1, 2 * i + 2] for i, word in enumerate(GROWTH_WORDS)}
    return {
        "edges": list(deciles.growth_edges),
        "words": dict(reversed(words.items())),
        "n": deciles.n_growth,
    }


def _cited(value: Any, unit: str, source: str, setting: bool, changed: bool) -> dict[str, Any]:
    return {"value": value, "unit": unit, "source": source, "setting": setting, "changed": changed}


def _source(base: Policy, name: str) -> str:
    """The file's source line for the name; a universe or refresh setting cites its table's."""
    group, _, field = name.rpartition(".")
    return str(base.raw["values"][group or field]["source"])


def _changed(overlay: Mapping[str, Any]) -> int:
    return sum(1 for s in SETTINGS if s.name in overlay)


def _plain(value: Any) -> Any:
    """The value as JSON reads it back: a tuple becomes a list."""
    return json.loads(json.dumps(value, allow_nan=False))
