# Golden results

The six engine fixtures' result dicts (`tests/support/engine_companies.py`), valued under the
packaged policy at its defaults on 2026-10-31, with `policy_version`, `method_version` and
`settings_hash` removed. `tests/engine/test_golden.py` compares the engine against them.
The policy name a RULE input cites in its provenance is masked as well: its `source`
`policy fairband-policy-v5` is stored as `policy`.

Captured from method 0.7, policy v5, on 2026-11-04, and still the baseline at the start of
method 0.9; regenerate only when the method changes on purpose.

Re-captured under 0.9 on 2026-11-06 for the classifier (spec 2026-11-06 section 8), for two
causes: every phase block gains the established test's two counts, `positive_years_last_five` and
`positive_years_on_file`; and DCCO loses `margin-direction-disagrees` from its flags and its
checks, since Stable points to no phase (spec 8.3). The figures of every golden are unchanged by
this re-capture: values, levels, designations, intermediates, inputs and refusals are as captured
from 0.7.

HGCO and YGCO re-captured under 0.9 on 2026-11-06 for the growth routes (spec 2026-11-06 section
7), for one cause: two records gain a key, `margin_path.ramp` ("margin") and
`sales_to_capital.own_below_bound` (false). Neither rule applies to them, their trailing margin
being −9% and their own sales-to-capital above half the peers' median, so their figures are
unchanged.

DCCO re-captured under 0.9 on 2026-11-06: the fade and the flat terminal (spec 2026-11-06 section
6). The decline rate fades from −4% to zero by year 10 and the terminal is flat on year 10's
revenue, so every run-off figure moves: the value is 4.9533 a share (4.3180 under 0.8), the
designation at $3.00 is "well-below", the run-off is worth more than $3.00 at every decline rate
the scan reads so there is no implied decline rate, the expected return grows at the path's own
rates, and `runoff_path` gains `consensus_years` (3: the fixture's consensus ends at base + 2).

Run from the repository root:

```
PYTHONPATH=tests:tests/engine uv run python - <<'PY'
import json; from test_golden import FIXTURES, GOLDEN, TODAY, golden_dict, load_policy, universe_deciles, value_company
for symbol, inputs in FIXTURES.items():
    result = value_company(inputs(), universe_deciles(), load_policy(), TODAY)
    (GOLDEN / f"{symbol}.json").write_text(json.dumps(golden_dict(result), indent=1, sort_keys=True) + "\n")
PY
```
