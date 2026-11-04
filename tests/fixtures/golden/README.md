# Golden results

The six engine fixtures' result dicts (`tests/support/engine_companies.py`), valued under the
packaged policy at its defaults on 2026-10-31, with `policy_version`, `method_version` and
`settings_hash` removed. `tests/engine/test_golden.py` compares the engine against them.
The policy name a RULE input cites in its provenance is masked as well: its `source`
`policy fairband-policy-v5` is stored as `policy`.

Captured from method 0.7, policy v5, on 2026-11-04; regenerate only when the method changes on purpose.

Run from the repository root:

```
PYTHONPATH=tests:tests/engine uv run python - <<'PY'
import json; from test_golden import FIXTURES, GOLDEN, TODAY, golden_dict, load_policy, universe_deciles, value_company
for symbol, inputs in FIXTURES.items():
    result = value_company(inputs(), universe_deciles(), load_policy(), TODAY)
    (GOLDEN / f"{symbol}.json").write_text(json.dumps(golden_dict(result), indent=1, sort_keys=True) + "\n")
PY
```
