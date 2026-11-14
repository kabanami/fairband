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

MGCO, MSCO and FXCO re-captured under 1.2 on 2026-11-12 for new keys only (method 4.6 rule 5):
`runway_return` gains `without_goodwill`, the runway measures on capital without goodwill and
intangibles (MGCO and FXCO: a usable five-year marginal of 52.7%; MSCO: the three-year, 22.3%),
and each kept year of `roic.by_year` gains `average_goodwill_and_intangibles`. The record holds
`bought` too, false on all three: whether purchases carried the capital's growth, under which
the charge reads none of the measures. Each fixture's measure is above r, so no charge reads
the new measures and every figure is unchanged. The four other goldens carry neither record and
are untouched.

All seven re-captured under 1.3 on 2026-11-13 for one new key (spec 2026-11-13 11a; method
14.6): the intermediates gain `trailing_end`, the trailing period end as an ISO date, the period a
period-tied override corrects, so the drop of such an override follows the period and not the
day the statements were fetched. Every fixture's trailing figures end on 2026-09-30, SUCO's
refusal included. No other key or figure of any golden moves.

MGCO and FXCO re-captured under 1.3 on 2026-11-14 for one new key (spec 2026-11-13 7.2; method
14.4): the Mature Growth intermediates gain `sbc_ttm`, the trailing stock pay the anchor read,
which an agent's `earnings.sbc` replaces and which `overrides.current_reading` reads as the
figure such an override corrects. With no override it is the stored figure: 400 m on MGCO, 320 m
SEK on FXCO. No other key or figure of either golden moves; the five goldens on other routes carry
no such key and are untouched.

All seven re-captured under 1.3 on 2026-11-14 for one new key (spec 2026-11-13 11; method,
section 8): the intermediates gain `margin_history`, the ten-year median operating margin on
`margin-flag`'s window and the ten-year median net margin on the same rule, each with its count
of years, on every result whose series is not empty, a refusal too. The fixtures' series carry no
net income, so no golden has a net margin: MGCO and FXCO 23.25% over 10 years (the last ten of
eleven, a ratio, so FXCO's rate does not enter), MSCO 20% over 10, HGCO −19.5% and YGCO −15.5%
over 8, DCCO 8% over 5, and SUCO, with no revenue above zero, an empty record. The note
`thin-ntm` (spec 2026-11-13 9) fires on none: every fixture's NTM quarters have 20 analysts. No
other key or figure of any golden moves.

HGCO, YGCO, DCCO and SUCO re-captured under 1.4 on 2026-11-14 for one cause, the newest balance
sheet (spec 2026-11-13 12.2; method 4.2): the three firm-value routes read debt, cash and the
liquidation floor from the newest balance sheet on file, a quarter's or a fiscal year's, and cite
it with its period. Each fixture's newest sheet is its newest fiscal year's, fiscal 2025, so no
figure moves. The `debt` and `cash` inputs cite the source `balance_sheet` ("FMP
balance-sheet-statement") in place of the statements, with the note "the balance sheet of fiscal
2025"; the intermediates gain `balance_sheet` beside `debt` and `cash` (period end 2025-12-31,
label "fiscal 2025", not quarterly); and DCCO's inputs gain the floor's two lines under their own
names after `cash`, `floor_current_assets` (300 m) and `floor_total_liabilities` (500 m), cited to
the sheet with the same note, while `total_current_assets` and `total_liabilities` stay fiscal
2025's for Z″ and F. MGCO, MSCO and FXCO read no balance sheet and are untouched.

HGCO, YGCO, DCCO and SUCO re-captured under 1.4 on 2026-11-14 for two causes. The first is the
minority interest (spec 2026-11-13 13; method 5a.9, 6a.5 to 6a.7, 6b.2, 6b.4): the three
firm-value routes subtract the newest balance sheet's minority interest at book, nil where the
sheet does not present it or holds it at or below zero. No fixture's sheet presents one, so no
value, level, designation, flag or refusal moves. The inputs gain `minority_interest` right after
`cash`, empty (the line as the sheet presents it), cited to the sheet (`balance_sheet`, "FMP
balance-sheet-statement") with the note "the balance sheet of fiscal 2025"; the intermediates gain
`minority_interest`, 0.0, the figure in force. The second is the date of the sheet's citation,
which the builders now set as assembly sets it, as of the sheet's period end (method 4.2): the
paragraph above left `balance_sheet` as of the fixtures' data date, 2026-10-30, a citation
assembly never gives, and the four builders now cite it as of 2025-12-31, the end of fiscal 2025.
So `debt`, `cash`, the new entry and DCCO's `floor_current_assets` and `floor_total_liabilities`
are as of 2025-12-31; no figure depends on the date. MGCO, MSCO and FXCO read no balance sheet and
are untouched.

MGCO and FXCO re-captured under 1.4 on 2026-11-14 for three new keys, the NTM anchor on a thin
window (spec 2026-11-13 9a; method 5.2): the Mature Growth `anchor` entry gains `source`, what
the raw NTM EPS read, `periods_sum`, the sum of the window's EPS means, and `annual`, each fiscal
year the annual figure weighs, null on the periods' source. Each fixture's NTM quarters have 20
analysts, so the window is not thin: the source is `periods`, the sum is the raw figure (5.90 on
MGCO, 47.20 SEK on FXCO) and the DATA entries still cite the quarterly consensus. No other key or
figure of either golden moves; the five goldens on other routes carry no `anchor` entry and are
untouched.

MGCO and FXCO re-captured under 1.4 on 2026-11-14 for the anchor rule's second form (spec
2026-11-13 9a, as amended): on the annual source `annual` is now one record, the correction by
the annual consensus of the last fiscal year the window reaches (`fiscal_year`, `eps`,
`analysts`, `year_sum`, `share`, `correction`), in place of a list of fiscal years with their
weights. Neither fixture's window is thin, so `annual` stays null and both files are unchanged
byte for byte.

MGCO, MSCO and FXCO re-captured under 1.4 on 2026-11-14 for two new keys of the `charge` entry,
the revenue steps an agent may set (spec 2026-11-14 6.1 and 6.3; method 4.8 and 5.12):
`revenue_steps_found`, the consensus revenue steps as found, and `revenue_step_source`, where
each step the charge read came from, `consensus`, `agent` or `none`; `revenue_steps` stays the
steps the charge read, the key a price refresh rebuilds from. None of the three fixtures has a
consensus revenue step (MSCO's own charge reads none), so each gains `[null, null]` and
`["none", "none"]`. No other key or figure moves; HGCO, YGCO, DCCO and SUCO carry no `charge`
entry and are untouched.

Run from the repository root:

```
PYTHONPATH=tests:tests/engine uv run python - <<'PY'
import json; from test_golden import FIXTURES, GOLDEN, TODAY, golden_dict, load_policy, universe_deciles, value_company
for symbol, inputs in FIXTURES.items():
    result = value_company(inputs(), universe_deciles(), load_policy(), TODAY)
    (GOLDEN / f"{symbol}.json").write_text(json.dumps(golden_dict(result), indent=1, sort_keys=True) + "\n")
PY
```
