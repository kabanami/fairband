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

MGCO re-captured under 1.0 on 2026-11-09 for the payout floor's removal (spec 2026-11-09 section
6.1), before the routes pass the charge's hold and revenue steps: a year whose growth outruns its
return now pays out less than nothing. The row's own charge, at its 43.1% return, has no such
year, so its value (133.37 a share), levels and designation are unchanged; the sensitivities that
charge growth above their return move. At the 9% return, equal to r, the value is year-1 earnings
over r on any path whose charge pays for its earnings growth, as MGCO's does with no consensus
revenue (once the routes pass the revenue steps, below, a path with them adds its uncharged
margin change, method 5.8), 65.56 a share (68.14 under 0.9), so no belief reaches the price and
`implied_by_roic` `0.09` is null (14.19%); the five-year runway's implied growth is 47.21%
(46.57%); and `value-spread` reads its range from 65.56, a spread of 103.4% (95.7%).

MGCO and MSCO re-captured under 1.0 on 2026-11-09 for one cause: `runway_return` in the
intermediates gains `one_year`, the newest year's marginal return, shown and never used (spec
2026-11-09 section 6.3): 45.75% on MGCO, 18.25% on MSCO. Every figure is unchanged; only the key
is new.

MGCO and MSCO re-captured under 1.0 on 2026-11-09 for the charge's shape (spec 2026-11-09
sections 6.1 to 6.3): the two mature routes now pass the hold K and the revenue steps, and the
intermediates gain `charge` (`growth_by_year`, `return_by_year`, `hold_years`, `revenue_steps`).
MGCO has no consensus revenue, so its charge pays for its earnings growth (`revenue_steps` null);
its hold is 6, the last year whose next growth is above the 6.3% belief, so its 43.1% return holds
through year 6 and fades to 13% in year 20. Its value is 127.68 a share (133.37), so its
designation at $150 is above (near), and its levels, the 10- and 20-year runway values, the three
return keys above r, every implied growth but the five-year runway's (the row's own 8.64%, 7.84%)
and the expected return move with it; the five-year runway, whose path the hold covers to year 4,
and the `0.09` key keep their figures. `value-spread` reads 65.56 to 127.68, 94.8% (103.4%).
MSCO's hold is 0, so its three-year 18.25% fades from year 1 to 13% in year 20: its value is 43.85
a share (44.71), and its levels and expected return move with it; its designation stays near.

MSCO re-captured under 1.0 on 2026-11-09 for one new key: its intermediates carry `charge_off`
(false) beside `charge`, as Mature Growth's do, so the drawer reads whether the runway years went
uncharged from the row rather than from the measure's word (method 4.8). Its figures are
unchanged; the other five goldens are untouched.

FXCO captured under 1.1 on 2026-11-10 (spec 2026-11-10 section 7 and 11.2), the seventh golden:
a company in another currency, `fx_inputs()`, the Mature Growth company at a tenth of its size
(100 m shares) reporting in SEK at 8.0 SEK per USD on 2026-10-31 with an inflation differential of
2%, quoting USD 50.00 for a market cap of USD 5,000 m. Its route reads a price of 400.00 and a
market cap of 40,000 m in SEK on the policy's rates restated by the differential (r 11.18%, g_T
5.06%, the inflation addition 4.04%); its value is 837.14 SEK a share, USD 104.64 at 8.0, so at USD
50.00 it is well-below (0.478 × the value), its levels the policy's on the USD value. Its
intermediates add `currency`, `fx_rate`, `fx_date`, `value_in_currency` and
`inflation_differential`, and its inputs `fx_rate` (SEK per USD) and the RULE input
`inflation_differential`; every other money input is in SEK. The six USD goldens are unchanged by
method 1.1, bit for bit: a USD row carries none of these.

Run from the repository root:

```
PYTHONPATH=tests:tests/engine uv run python - <<'PY'
import json; from test_golden import FIXTURES, GOLDEN, TODAY, golden_dict, load_policy, universe_deciles, value_company
for symbol, inputs in FIXTURES.items():
    result = value_company(inputs(), universe_deciles(), load_policy(), TODAY)
    (GOLDEN / f"{symbol}.json").write_text(json.dumps(golden_dict(result), indent=1, sort_keys=True) + "\n")
PY
```
