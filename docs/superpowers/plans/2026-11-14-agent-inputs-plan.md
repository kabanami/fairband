# The Inputs An Agent Could Not Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the six changes of the agent-inputs spec: the input `shares.committed`, the input `earnings.ntm_nri`, the inputs `revenue.step_2` and `revenue.step_3`, the scaling of an override at a split, the drop of an override its row's route no longer reads, a guidance record in net income, and, as commits of its own under method 1.5, the rule that a thin consensus revenue step is not read. Then two scratch revalues, the founder's reading of the rule's readout, one live revalue and its readout.

**Architecture:** Four tags join `engine/overrides.py` with their ranges in policy v16. The route's context gains the count without the committed shares, and the anchor and Mature Stable's two gaps read it. The anchor gains one keyword for the one-time amount. The charge reads an agent's revenue step through `route_mature_growth._judged`, and its intermediates keep the steps as read and as found. The split's scaling and the route drop live in `refresh/reviews.py`, at the one place where the store's overrides become the engine's and beside the other drop tests, and the web's recompute calls both. Guidance gains a metric in `store/guidance.py`. The thin rule is one test in `anchor.path_steps`.

**Tech Stack:** Python 3.13, uv, pytest, mypy, ruff; FastAPI; `app.js` run under node by the drawer tests; the playbook's Markdown.

**Spec:** `docs/superpowers/specs/2026-11-14-agent-inputs-design.md`. Read it before any task; where this plan and the spec differ, the spec governs and the difference is a finding to report.

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- `docs/method.md` changes in the same commit as the engine, the classifier, the universe rule or a policy value it describes; the Methodology page (`src/fairband/web/static/methodology.html`) with it. Where documents disagree, `docs/method.md` describes what runs.
- Policy `fairband-policy-v16`; `fairband-policy-v15.toml` stays byte-identical. The method version stays `fairband-mechanical/1.4` in Tasks 1 to 7 and becomes `fairband-mechanical/1.5` in Task 8 alone. No new setting, no database migration.
- Never print, log, store or commit a key; never commit vendor data; test fixtures are synthetic or hand-trimmed.
- Commit messages: one plain sentence in the imperative, ending with `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- Every dispatched subagent, reviewers included, runs on Opus 5.5 at xhigh (the founder's standing instruction of 2026-11-10).
- The goldens (`tests/fixtures/golden/`): in Tasks 1 to 7 no value, level, designation, refusal or flag of any golden moves; a golden changes only by gaining new intermediates. In Task 8 a golden's figure moves only where its fixture holds a thin revenue step, and the README paragraph names each such move. Each re-capture adds a paragraph to `tests/fixtures/golden/README.md` naming its cause.
- No vendor call and no touch of `~/.local/share/fairband` before Task 10, and none there without the founder's word.
- Work in a git worktree (superpowers:using-git-worktrees), not in the main checkout.
- Task 8 (the thin rule) is its own commits and no other task's code depends on it, so the founder can leave it out of the merge after reading its readout (spec 6.2).

## Review Focus

- A company in another currency: `earnings.ntm_nri` is an amount a share in the reporting currency and its range is read at the rate; `shares.committed` is a count and no rate touches it. Tests in Tasks 2 and 3.
- A price refresh after the revalue: the committed shares, the one-time amount and an agent's revenue step survive the reprice, and the implied growth is solved on the count in force. Tests in Tasks 2, 3 and 4.
- Two new inputs on one row: `shares.committed` with `shares.diluted`, and `earnings.ntm_nri` with `earnings.cycle_gap` and `value.outside` (the AMZN case), in the bridge's order, the deltas summing to the reviewed value. Tests in Tasks 2 and 3.
- An override made on a snapshot whose data date is before a split and whose price date is after it (a price refresh came between): the scaling reads the data date. Test in Task 5.
- A `phase` override that is itself dropped at the same recompute as the overrides only its route read: the route test reads the route after that drop. Test in Task 6.

---

### Task 1: Policy v16

**Files:**
- Create: `src/fairband/policy/fairband-policy-v16.toml` (a copy of v15 with the four ranges)
- Modify: `src/fairband/policy/__init__.py` (`_POLICY_FILE`, the docstring's version lines)
- Modify: `docs/method.md` 4.1 (the override ranges; "loads v16 only"), 11 (a row "1.4, policy v16", written whole now)
- Test: `tests/policy/test_policy.py`, and every test that pins `fairband-policy-v15` as the packaged policy (grep; commit `869fc1c` shows which tests a policy version moves)

**Interfaces:**
- Produces: `load_policy().version == "fairband-policy-v16"`; `Policy.override_ranges` gains `"shares.committed": (0.0, 1e12)`, `"earnings.ntm_nri": (-100.0, 100.0)`, `"revenue.step_2": (-0.80, 3.00)`, `"revenue.step_3": (-0.80, 3.00)`. No new `Policy` field.

- [ ] **Step 1: Write the failing tests** in `tests/policy/test_policy.py`, in the form of the v15 pair: `V15_SHA256` (the sha256 of the v15 file as it stands) with `test_v15_is_byte_identical_under_its_hash`; `test_v16_is_the_packaged_policy` (the version and the four pairs above); `test_v16_is_v15_with_the_four_ranges` (every v15 value loads unchanged from v16 but `override_ranges`, whose value equals v15's with the four pairs added and whose note names each new tag). The tests that read v15 as the packaged policy read the v15 file instead.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/policy/test_policy.py -k "v16 or v15"`
Expected: FAIL (the packaged policy is v15).

- [ ] **Step 3: Create the policy file and point the loader at it.** Copy v15 byte for byte, add the header line `# v16: …` in the form of v15's, set the version, add the four pairs to `[values.override_ranges.value]` and one sentence to that table's `note` naming each tag and "spec 2026-11-14".

- [ ] **Step 4: Update the version pins and the documents.** `docs/method.md` 4.1: the ranges' row and "v1 to v15 stay … loads v16 only". Section 11: a row "1.4, policy v16", dated 2026-11-14, with one sentence for each change of Tasks 2 to 7 (the committed shares; the one-time item; the two revenue inputs; the scaling at a split; the route drop; guidance in net income), and that the method is unchanged at 1.4. Later tasks build what the row says; a task whose build departs from its sentence changes the sentence.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Name policy v16, whose override ranges gain the committed shares, the one-time item and the two revenue steps"
```

---

### Task 2: Committed shares (spec 4)

**Files:**
- Modify: `src/fairband/engine/overrides.py` (`OverrideTag`, `BRIDGE_ORDER`, `TAGS`, `LABELS`, `current_reading`, the docstring's count), `src/fairband/engine/route.py` (`_shares`, the context's build, `_share_count`), `src/fairband/engine/route_steps.py` (`Context`, `StartUpContext`, an entry helper), `src/fairband/engine/route_mature_growth.py` (`_anchor_and_path`, `_stock_pay_notes`, the intermediates), `src/fairband/engine/route_mature_stable.py` (the two gaps), `src/fairband/engine/route_revenue_growth.py` (its call of `ntm_anchor`)
- Modify: `docs/method.md` 5.2, 5.12, 5.13, 6.1, 6.4, 14.2 to 14.5; the Methodology page's count of inputs; `playbook/fairband-research/SKILL.md` (the overrides table, the share-count passage) and `reference/tools.md`, `reference/report-template.md`
- Test: `tests/engine/test_overrides.py`, `tests/engine/test_route.py`, `tests/engine/test_review.py`, `tests/engine/test_currency.py`, `tests/web/test_reviews_api.py`, `tests/test_playbook.py`, `tests/test_method_doc.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Consumes: the range of Task 1.
- Produces:
  - The tag `shares.committed`: routes Mature Growth, Mature Stable, revenue-growth, Decline and Start-up; unit `shares`; period-tied only; the lower end of its range excluded (`low_open`); label "committed shares"; in `BRIDGE_ORDER` right after `shares.diluted`; no `INPUT_OF` entry.
  - `Context.shares` and `StartUpContext.shares` stay the count in force: the diluted count (an agent's `shares.diluted` in its place) plus the committed shares. Both contexts gain `consensus_shares: float`, the count in force less the committed shares.
  - The anchor is called with `consensus_shares` at both call sites, so NTM net income and the stock pay a share stand on it; `_stock_pay_notes` and `step_series_flag` read it too. Mature Stable's two gaps a share become totals on it. Every division of a value among the owners stays on `shares`.
  - `route_steps.committed_entry(c) -> dict[str, Any]`: `{"shares_committed": x}` under the override, else empty; each route puts it beside `shares`.
  - `current_reading(result, "shares.diluted")` is `shares` less `shares_committed`; `current_reading(result, "shares.committed")` is `None`.

- [ ] **Step 1: Write the failing tests.**

  - `tests/engine/test_overrides.py`: the tag's rules, in the form of `test_the_minority_interest_tag_s_rules`: a period-tied 60e6 applies on each of the five routes; 0 and a negative count are refused ("shares.committed takes above 0 shares" in the module's words); lasting is refused "shares.committed is period-tied only"; its place in the bridge and its label.
  - `tests/engine/test_route.py`, on `mature_growth_inputs()` (a count of 1,000 m, an NTM EPS of $5.90): under `shares.committed` at 60 m the value a share is the fixture's × 1,000 ÷ 1,060; `intermediates["ntm_net_income"]` stays 5,900 m; `intermediates["shares"]` is 1,060 m and `["shares_committed"]` 60 m; the stock-pay adjustment, the basis and the two consensus DATA entries equal the fixture's. With `shares.diluted` at 1,100 m as well: NTM net income 6,490 m, the count in force 1,160 m, the value a share the fixture's × 1,100 ÷ 1,160. On a fixture whose basis reads `excludes-sbc`, the adjustment a share is unchanged by the committed shares.
  - On `mature_stable_inputs()`: the value a share is the fixture's × n ÷ (n + x), and the normalized earnings are unchanged.
  - On `high_growth_inputs()` (100 m shares), `decline_inputs()` and `start_up_inputs()`: `shares.committed` at 10% of the count gives the result of `shares.diluted` at 110% of it, in value, levels and every intermediate but `shares_committed` and the JUDGMENT entries.
  - The cross-check of a Mature Stable row falls by the same share as a Mature Growth value.
  - The price refresh (Review Focus): after `result_from_json(result_to_json(r))` and `reprice`, the Mature Growth result under the override equals a fresh valuation at the new price; its implied growth is solved on the count in force.
  - `tests/engine/test_review.py` (Review Focus): `shares.diluted` and `shares.committed` together bridge in that order and the deltas sum to the reviewed value; `current_reading` of `shares.diluted` on the review's result is the count without the committed shares.
  - `tests/engine/test_currency.py` (Review Focus): on the SEK company the count is not scaled by the rate and the refusal names shares, not a currency.
  - `tests/web/test_reviews_api.py`: through the API on AAPL, a period-tied post applies, lowers the reviewed value by the share above and shows "committed shares" in the bridge.
  - `tests/test_playbook.py` and `tests/test_method_doc.py`: twenty-two tags, and the words where the tests pin them.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_overrides.py tests/engine/test_route.py -k "committed"`
Expected: FAIL (`shares.committed` is not a tag).

- [ ] **Step 3: Implement.** `_shares` returns the two counts; the contexts carry both. Change no division of a value among the owners. Move the count of the inputs to twenty-two where it is pinned.

- [ ] **Step 4: Re-capture the goldens** only if an intermediate's shape changed (no entry is written without the override, so none should); if any golden changes, say why in the README.

- [ ] **Step 5: Update the documents and the playbook.** `docs/method.md`: 5.2 and 6.1 (the count the consensus is on), 5.12 and 5.13 (the intermediates; the worked line for a raised count), 6.4, 14.2 (the row), 14.3 (the lifetime rule's list, the count), 14.4 (a bullet for the input; `shares.diluted`'s bullet says what it is for and points to the new input for dilution), 14.5 (the order and label). The playbook: shares not yet issued go through `shares.committed` on every route, with the filing that commits them as evidence, and cash the issue brings through `balance.cash` or `value.outside`; a class or units the count leaves out go through `shares.diluted`. The sentences that say a raised count barely moves a Mature Growth value go.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Let an agent state committed shares with shares.committed, which dilute a value on every route and leave Mature Growth's earnings on the consensus's count"
```

---

### Task 3: A one-time item in the NTM consensus (spec 5)

**Files:**
- Modify: `src/fairband/engine/overrides.py` (the tag's entries, `current_reading`), `src/fairband/engine/anchor.py` (`ntm_anchor`, `Anchor`), `src/fairband/engine/route_steps.py` (an entry helper), `src/fairband/engine/route_mature_growth.py` (`_anchor_and_path`, the intermediates)
- Modify: `docs/method.md` 5.2, 5.12, 14.2 to 14.5; the Methodology page's count; the playbook ("Nothing counts twice", the overrides table, the `consensus-basis-unknown` entry), `reference/report-template.md`
- Test: `tests/engine/test_anchor.py`, `tests/engine/test_overrides.py`, `tests/engine/test_route.py`, `tests/engine/test_review.py`, `tests/engine/test_currency.py`, `tests/refresh/test_reviews_follow.py`, `tests/test_playbook.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: `Context.consensus_shares` (Task 2); the range of Task 1.
- Produces:
  - The tag `earnings.ntm_nri`: Mature Growth alone; unit `USD a share`; period-tied only; label "one-time item in the NTM consensus"; in `BRIDGE_ORDER` right before `earnings.cycle_gap`; no `INPUT_OF` entry.
  - `ntm_anchor(..., one_time: float | None = None)`: with no `guided_eps`, `ntm_eps` is the consensus less the stock-pay adjustment, less `one_time`, less `cycle_gap`; with a `guided_eps` the amount is not read. `Anchor.ntm_eps_found` and the unit-error check are unchanged.
  - `_anchor_and_path` passes it only for the route's own anchor (`own`).
  - `intermediates["ntm_nri"]` under the override. `current_reading(result, "earnings.ntm_nri")` is 0.0 on a Mature Growth result and `None` elsewhere; the reading of `earnings.ntm` adds `ntm_nri` back with the cycle gap.

- [ ] **Step 1: Write the failing tests.** `tests/engine/test_anchor.py`, on the module's `ntm()` (four quarters at 2.5, a raw sum of 10.0) with a street EPS of 4.2 (no stock-pay adjustment):

```python
def test_a_one_time_amount_comes_off_year_1(policy: Policy) -> None:
    """Spec 2026-11-14 5: 10.00 less 0.50 is 9.50; a one-time loss of 0.50 a share raises year
    1 to 10.50; a cycle gap of 1.00 comes off too; under a guided EPS the amount is not read."""
    args = (ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy)
    assert ntm_anchor(*args, one_time=0.5).ntm_eps == pytest.approx(9.5)
    assert ntm_anchor(*args, one_time=-0.5).ntm_eps == pytest.approx(10.5)
    both = ntm_anchor(*args, one_time=0.5, cycle_gap=1.0)
    assert both.ntm_eps == pytest.approx(8.5) and both.ntm_net_income == pytest.approx(85.0)
    assert both.ntm_eps_found == pytest.approx(10.0)
    guided = ntm_anchor(*args, one_time=0.5, guided_eps=9.0)
    assert guided.ntm_eps == pytest.approx(9.0)
    wiped = ntm_anchor(*args, one_time=10.0)
    assert wiped.refusal == "no positive forward anchor"
```

  - `tests/engine/test_overrides.py`: the tag's rules (Mature Growth alone; −100 and 100 apply, −100.01 is refused; lasting is refused; its place and label).
  - `tests/engine/test_route.py`, on `mature_growth_inputs()` (NTM EPS $5.90): under the input at $0.59 the value a share is the fixture's × 5.31 ÷ 5.90, `intermediates["ntm_nri"]` is 0.59, and the DATA entries `ntm_eps` and `ntm_net_income` equal the fixture's; a Mature Stable row's cross-check does not read it; a price refresh rebuilds the same value (Review Focus).
  - `tests/engine/test_review.py` (Review Focus, the AMZN case): `earnings.ntm_nri`, `earnings.cycle_gap` and `value.outside` together bridge in the order of `BRIDGE_ORDER` and the deltas sum; under an applied `earnings.ntm` the one-time line's delta is 0; `current_reading` of `earnings.ntm` on that result adds the amount back.
  - `tests/engine/test_currency.py` (Review Focus): on the SEK company the range is read at the rate and the unit reads `SEK a share`.
  - `tests/refresh/test_reviews_follow.py`: the override stays applied on the same period and drops with `NEWER` a quarter later.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_anchor.py tests/engine/test_overrides.py -k "one_time or ntm_nri"`
Expected: FAIL (unexpected keyword `one_time`).

- [ ] **Step 3: Implement.** Move the count of the inputs to twenty-three.

- [ ] **Step 4: Update the documents and the playbook.** `docs/method.md` 5.2 (the order of the three subtractions; under a guided EPS), 5.12, 14.2, 14.3, 14.4 (a bullet: what it corrects, that the entries stay on the consensus as found, that it is moot under `earnings.ntm`), 14.5. The playbook's "Nothing counts twice" on Mature Growth as spec 5 states it, the `consensus-basis-unknown` entry, the overrides table (the evidence: the filing's other-income line and the analysts' basis), and the report template's line that no override adds the asset.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Let an agent take a one-time amount a share off the NTM consensus with earnings.ntm_nri"
```

---

### Task 4: The two revenue inputs (spec 6.1, 6.3)

**Files:**
- Modify: `src/fairband/engine/overrides.py` (the two tags' entries, `current_reading`), `src/fairband/engine/route_mature_growth.py` (`_judged`, `charge_entry`, `_rebuilt`, `_on_revenue`), `src/fairband/reports/refs.py` (words for the entry's new keys)
- Modify: `docs/method.md` 4.8, 5.3, 5.11, 5.12, 14.2 to 14.5; the Methodology page's count; the playbook's overrides table and its text on the steps
- Test: `tests/engine/test_overrides.py`, `tests/engine/test_route.py`, `tests/engine/test_review.py`, `tests/refresh/test_reviews_follow.py`, `tests/reports/test_refs.py`, `tests/test_playbook.py`, `tests/test_method_doc.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Consumes: the ranges of Task 1.
- Produces:
  - The tags `revenue.step_2` and `revenue.step_3`: Mature Growth alone; unit `ratio`; period-tied only; labels "revenue step 2" and "revenue step 3"; in `BRIDGE_ORDER` right after `path.step_3`; no `INPUT_OF` entry.
  - `_judged` replaces a revenue step of the path with the agent's; a cross-check keeps the steps as found.
  - `intermediates["charge"]` holds `revenue_steps` (the steps the charge read, the rebuild key), `revenue_steps_found` (the consensus's, as found) and `revenue_step_source` (a list of two among `"consensus"`, `"agent"`, `"none"`). Task 8 adds `"thin"`.
  - `current_reading(result, "revenue.step_2")` is `charge.revenue_steps_found[0]`, `step_3` the second; `None` off Mature Growth.

- [ ] **Step 1: Write the failing tests.** `tests/engine/test_route.py`, on `mature_growth_inputs()` with a revenue consensus on its annual rows, each on 10 revenue analysts: fiscal 2027 $25,000 m, fiscal 2028 $27,500 m (+10%), fiscal 2029 $29,700 m (+8%):

  - with no override, `charge.revenue_steps == [0.10, 0.08]` (to the test's precision), `revenue_steps_found` the same and `revenue_step_source == ["consensus", "consensus"]`;
  - under `revenue.step_3` at 0.05: `revenue_steps == [0.10, 0.05]`, `revenue_steps_found == [0.10, 0.08]`, the source `["consensus", "agent"]`, `charge.growth_by_year`'s second entry 0.05, and the value above the result without the override (the charge pays for less growth);
  - on the fixture as it is (no revenue consensus): the source is `["none", "none"]`, and `revenue.step_2` at 0.04 makes the charge pay for 4% in year 2 where it paid for the earnings step;
  - a Mature Stable row's cross-check is unchanged by the override;
  - a price refresh rebuilds the same value from the stored `charge` (Review Focus);
  - `growth-above-return` says "revenue growth" for a year whose growth is an agent's revenue step.

  `tests/engine/test_overrides.py`: the two tags' rules (Mature Growth alone; −0.80 and 3.00 apply, 3.01 is refused; lasting is refused; places and labels) and the readings. `tests/engine/test_review.py`: `path.step_3` and `revenue.step_3` together bridge in order, the deltas sum, and the earnings-step override no longer moves the charge of that year. `tests/refresh/test_reviews_follow.py`: the override stays while the consensus revenue step stands, and drops with `CHANGED` when it moves. `tests/reports/test_refs.py`: the words of the three paths.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_route.py tests/engine/test_overrides.py -k "revenue_step"`
Expected: FAIL (`revenue.step_2` is not a tag; no `revenue_steps_found`).

- [ ] **Step 3: Implement.** Move the count of the inputs to twenty-five.

- [ ] **Step 4: Re-capture the goldens that carry a `charge` entry** for its two new keys, with the README paragraph. No figure moves.

- [ ] **Step 5: Update the documents and the playbook.** `docs/method.md` 4.8 and 5.3 (the charge reads an agent's revenue step; an earnings-step override still moves only the fallback), 5.11 (the flag's words), 5.12 (the entry's keys), 14.2 to 14.5. The playbook: where a revenue step rests on few analysts or outruns the business's record, the agent sets `revenue.step_2` or `revenue.step_3` from guidance or a filing; `return.runway` is not the lever for a wrong revenue step.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Let an agent correct a consensus revenue step on Mature Growth with revenue.step_2 and revenue.step_3"
```

---

### Task 5: Overrides at a split (spec 7)

**Files:**
- Modify: `src/fairband/engine/overrides.py` (`Override.rescaled`), `src/fairband/engine/route_steps.py` (`_judgment`), `src/fairband/engine/review.py` (the note on the review's result), `src/fairband/refresh/reviews.py` (`engine_overrides`, `write_review`), `src/fairband/web/sensitivity_api.py` (its use of `as_override`)
- Modify: `docs/method.md` 8 (the note's row), 14.4 or 14.6 (the rule); the playbook's split passage; the Methodology page where it states what a refresh does to an override
- Test: `tests/refresh/test_reviews_follow.py`, `tests/engine/test_review.py`, `tests/web/test_reviews_api.py`, `tests/web/test_sensitivity_api.py`, `tests/test_playbook.py`, `tests/web/test_methodology.py`

**Interfaces:**
- Produces:
  - The engine's `Override` gains a last field with a default, `rescaled: str | None = None`: the words of the scaling, "entered as $30.00 a share before the 2-for-1 split of 27 Jan 2027" (a count reads "entered as 60.0M shares before …"; two splits are named in order).
  - `reviews.engine_overrides(conn: sqlite3.Connection, symbol: str, rows: Sequence[OverrideRow], data_date: date) -> list[Override]`: each row as the engine's override; a row whose tag's unit is `USD a share` has its value divided by ρ and one whose unit is `shares` multiplied by ρ, with `rescaled` set, where ρ is the product of the ratios of the company's splits dated after the data date of the snapshot the row was made on and at or before `data_date`; ρ of 1 leaves the row as it is. `write_review` and the sensitivity reading build their overrides through it, with the data date of the snapshot they value.
  - The JUDGMENT entry's note ends with the `rescaled` words. `review_company` adds the note flag `override-split-scaled`, "Override scaled at a split", to the review's result when an applied override carries them: "A split took effect after these inputs were entered, so each applies on the new basis: earnings.ntm, value.outside." (the tags in the bridge's order).

- [ ] **Step 1: Write the failing tests** in `tests/refresh/test_reviews_follow.py`, in the form of its stock-pay follow tests, on MGCO with a split stored through the module's own means for a `splits` answer:

  - a lasting `value.outside` of $10.00 made on a snapshot whose data date is 10 Jan 2027; a 2-for-1 split dated 27 Jan 2027; the next snapshot's data date 1 Feb 2027: the review's bridge line shows a new value of 5.00, its JUDGMENT entry's value is 5.00 and its note ends "entered as $10.00 a share before the 2-for-1 split of 27 Jan 2027", the result's flags hold `override-split-scaled` naming `value.outside`, and the stored override still holds 10.00;
  - a period-tied `shares.committed` of 60 m made before the split applies at 120 m;
  - an override made on a snapshot whose data date is 1 Feb 2027 is not scaled and carries no words;
  - the Review Focus case: an override made on a snapshot whose data date is 10 Jan 2027 and whose price date is 28 Jan 2027 is scaled;
  - a 2-for-1 and then a 3-for-1 after the override divide it by 6;
  - a tag in a ratio or a total (`growth.belief`, `balance.cash`) is never scaled.

  `tests/web/test_reviews_api.py` and `tests/web/test_sensitivity_api.py`: the recompute after a post and a sensitivity reading apply the same scaled figure.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/refresh/test_reviews_follow.py -k "split"`
Expected: FAIL (`engine_overrides` is not defined).

- [ ] **Step 3: Implement.** Read the splits with `inputs_splits.splits_for` and each made-on snapshot's data date from the store. A period-tied override's drop tests are unchanged.

- [ ] **Step 4: Update the documents and the playbook.** `docs/method.md`: the rule where section 14 states how a review follows its snapshot, and the note's row in section 8 (not counted). The playbook's passage that tells the agent to drop and re-make per-share overrides after a split becomes: the system applies them on the new basis and names them; the agent checks the figure in force. The Methodology page: one sentence.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Apply an override in dollars a share or in shares on the new basis after a split, and name it on the review"
```

---

### Task 6: An override the route no longer reads (spec 8)

**Files:**
- Modify: `src/fairband/refresh/reviews.py` (`OFF_ROUTE`, `_follow`, a shared helper), `src/fairband/web/reviews_api.py` (`recompute`, the answer)
- Modify: `docs/method.md` 14.3 and 14.6; the playbook's lifetimes passage and its tools reference for `override_add` and `override_drop`
- Test: `tests/refresh/test_reviews_follow.py`, `tests/web/test_reviews_api.py`, `tests/test_playbook.py`

**Interfaces:**
- Produces:
  - `reviews.off_route(route: Route | None, rows: Sequence[OverrideRow]) -> list[OverrideRow]`: the rows whose tag is not `phase` and whose `TAGS` entry does not hold `route`; empty when `route` is `None`.
  - The drop reason is f"the {route's name} route does not read the input", the route named as `check_input` names it.
  - `_follow`: the `phase` override's own drop tests run first; the row's route is then the route of the surviving `phase` override, else of the mechanical phase; the rows `off_route` names drop with the reason and a SYSTEM ledger row; the other drop tests run on the rest.
  - The web's `recompute` drops the rows `off_route` names, in the same transaction, before it writes the review; the answers of `POST …/overrides` and `DELETE /api/overrides/{id}` gain `dropped`, a list of `{"id", "tag", "reason"}`, empty when none.

- [ ] **Step 1: Write the failing tests.** `tests/refresh/test_reviews_follow.py`:

  - MGCO with a lasting `return.runway` and a lasting `growth.belief`; the next snapshot's mechanical phase is Decline: the two drop with "the Decline route does not read the input" where a route's name is what `check_input` prints, each with its ledger row, and a `moat.class`, which Decline reads, stays if the tag table says so (take the tags from `TAGS`, not from this sentence);
  - a period-tied `earnings.sbc` on a row that moved to Mature Stable drops with the route's reason, not with `CHANGED`;
  - the Review Focus case: a period-tied `phase` override that drops for a newer period, and a lasting override only its route read: both drop at the same follow, the second with the route's reason;
  - an unclassified row keeps every override.

  `tests/web/test_reviews_api.py`: on a row with a `phase` override of Mature Growth and an `earnings.cycle_gap`, the `DELETE` of the `phase` override answers with `dropped` naming the cycle gap when the mechanical route does not read it, and the review that the answer carries holds neither; a post that replaces the `phase` override does the same; a post that changes no route answers `"dropped": []`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/refresh/test_reviews_follow.py tests/web/test_reviews_api.py -k "route"`
Expected: FAIL (`off_route` is not defined; no `dropped` key).

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Update the documents and the playbook.** `docs/method.md` 14.3 (the route is checked again at every recompute) and 14.6 (the drop, its place before the other tests, the unclassified row). The playbook: after a `phase` override is dropped or replaced, read `dropped` in the answer; the tools reference gains the key.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Drop an applied override whose row's route no longer reads it, at a refresh and at the web's recompute"
```

---

### Task 7: Guidance in net income (spec 9)

**Files:**
- Modify: `src/fairband/store/guidance.py` (`METRICS`, `UNITS`, `STEPPED`, `anchor_year`), `src/fairband/web/guidance_api.py` (`_BASE_LINES`), `src/fairband/engine/overrides.py` (`ANCHOR_METRICS`, `anchor_misfit`), `src/fairband/web/reviews_api.py` (`_require_anchor_record` if it names one metric)
- Modify: `docs/method.md` 14.3 and 14.9; the playbook's guidance passage and its entry for `earnings.ntm`; `reference/tools.md` (`guidance_add`)
- Test: `tests/store/test_guidance.py`, `tests/web/test_guidance_api.py`, `tests/web/test_reviews_api.py`, `tests/refresh/test_reviews_follow.py`, `tests/reports/test_refs.py`, `tests/test_playbook.py`

**Interfaces:**
- Produces: `"net_income"` in `METRICS`, unit `currency`, stepped against the prior fiscal year's net income; `ANCHOR_METRICS: dict[str, frozenset[str]]` with `"earnings.ntm": {"eps", "net_income"}` and `"revenue.ntm": {"revenue"}`; `anchor_year(tag, row)` accepts a metric in the tag's set; `anchor_misfit("earnings.ntm")` reads "… needs a gaap guidance record of eps or net_income for a fiscal year" in the form of today's sentence.

- [ ] **Step 1: Write the failing tests.** A `net_income` record is stored and read back with its step (the midpoint over the prior year's net income, less 1); `guidance:<id>/midpoint` resolves with its unit; a metric outside the list is still refused, the sentence naming `net_income` in the list; an `earnings.ntm` post citing a `gaap` fiscal-year `net_income` record is accepted, one citing a `revenue` record is refused with the new misfit sentence, and one citing an `adjusted` `net_income` record is refused; a lasting `earnings.ntm` resting on a `net_income` record of fiscal 2027 drops with `PASSED` when the base year is 2028.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/store/test_guidance.py tests/web/test_guidance_api.py -k "net_income"`
Expected: FAIL ("metric is one of …").

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Update the documents and the playbook.** `docs/method.md` 14.9 (the metric; the anchor's two metrics) and 14.3. The playbook: a company that guides net income alone backs `earnings.ntm` with that record; `new` is the `derive` ratio of the record's midpoint over the count the consensus is on, `snapshot:<id>/inputs/shares_diluted`, and never over a count that holds committed shares.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Let a guidance record hold net income, and an NTM EPS rest on it"
```

---

### Task 8: A thin revenue step is not read (spec 6.2), method 1.5

This task's commits stand alone (Global Constraints).

**Files:**
- Modify: `src/fairband/engine/anchor.py` (`path_steps`, `Path`), `src/fairband/engine/route_mature_growth.py` (the source of each step), `src/fairband/engine/__init__.py` (`METHOD_VERSION`)
- Modify: `docs/method.md` 4.8, 5.3, 6.4, 11 (the 1.5 row); the Methodology page where it states what the charge pays for
- Test: `tests/engine/test_anchor.py`, `tests/engine/test_route.py`, `tests/engine/test_review.py`, every test that pins `mechanical/1.4`, `tests/engine/test_golden.py`

**Interfaces:**
- Consumes: `charge.revenue_step_source` (Task 4).
- Produces: `path_steps` reads a revenue step only when its landing year's `analysts_revenue` is `policy.analyst_min` or more; else that step is `None` in `Path.revenue_steps`. `Path` gains `revenue_found: tuple[float | None, float | None]`, the steps as the consensus gives them, and `revenue_thin: tuple[bool, bool]`. The charge's entry writes `revenue_steps_found` from the first and the source `"thin"` from the second. `METHOD_VERSION == "fairband-mechanical/1.5"`.

- [ ] **Step 1: Write the failing tests.** `tests/engine/test_anchor.py`, on the module's `_annual` helper (base 2027; revenue 100, 110, 121; counts as given):

```python
def test_a_thin_revenue_step_is_not_read(policy: Policy) -> None:
    """Spec 2026-11-14 6.2: a revenue step whose landing year has fewer than 5 revenue analysts,
    or no count, is not read; the steps as found are kept beside it."""
    years = _annual(2027, eps=(2.0, 2.2, 2.4), revenue=(100.0, 110.0, 121.0))
    thin = [years[0], years[1], replace(years[2], analysts_revenue=4)]
    path = path_steps(thin, 2027, policy)
    assert path.revenue_steps == (pytest.approx(0.10), None)
    assert path.revenue_found == (pytest.approx(0.10), pytest.approx(0.10))
    assert path.revenue_thin == (False, True)
    at_five = [years[0], years[1], replace(years[2], analysts_revenue=5)]
    assert path_steps(at_five, 2027, policy).revenue_steps[1] == pytest.approx(0.10)
    no_count = [years[0], replace(years[1], analysts_revenue=None), years[2]]
    assert path_steps(no_count, 2027, policy).revenue_steps == (None, pytest.approx(0.10))
```

  `tests/engine/test_route.py`, on Task 4's fixture with fiscal 2029 on 4 revenue analysts: `charge.revenue_steps == [0.10, None]`, the source `["consensus", "thin"]`, and year 3's growth in the charge is the earnings step, 10%; an applied `path.step_3` moves it; an applied `revenue.step_3` wins over the rule and reads "agent"; a Mature Stable row's cross-check follows the rule. `tests/engine/test_review.py`: `revenue.step_3` on a thin year bridges from the earnings step's value.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_anchor.py -k "thin_revenue"`
Expected: FAIL (no attribute `revenue_found`).

- [ ] **Step 3: Implement**, and set `METHOD_VERSION`. Every test that pins the old version string moves.

- [ ] **Step 4: Re-capture the goldens** and list in the README each golden whose figure moved and the thin step that moved it; a golden with no thin step keeps every figure.

- [ ] **Step 5: Update the documents.** `docs/method.md` 4.8 and 5.3 (the rule, the count read, a missing count, the Decline route's like rule), 6.4, and section 11's row "1.5, policy v16". The Methodology page's sentence on the growth the charge pays for.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Read a consensus revenue step only on five revenue analysts or more, the charge taking the earnings step otherwise, as method 1.5"
```

---

### Task 9: The drawer and the whole-branch review

**Files:**
- Modify: `src/fairband/web/static/app.js` (`paidFor` and the Mature Growth section's lines for years 2 and 3; the count's rows on each route; the formats of the new keys in "Intermediate results")
- Test: `tests/web/test_drawer_intermediates.py`, `tests/web/test_app.py`

- [ ] **Step 1: Write the failing tests** on the node harness: for each value of `revenue_step_source` the charge's line of that year says which growth it paid for (the consensus revenue step; an agent's revenue step; the earnings step because the revenue step rests on fewer than five analysts; the earnings step because there is no revenue consensus), in the page's register, and a result with no source (stored before this plan) reads as today; a result with `shares_committed` shows "Committed shares" beside the count on each route's section and one without it shows no such row; `ntm_nri` shows as a figure a share; no raw key shows.

- [ ] **Step 2: Implement**, with the anchor of Task 8 in lines of its own so the page stands without it.

- [ ] **Step 3: Request the whole-branch review** (superpowers:requesting-code-review) against the spec and this plan's Review Focus; fix what it finds test-first; park what it rules minor in `docs/backlog.md` as one row.

- [ ] **Step 4: Run the four checks, then commit** the drawer in one commit and each review fix in its own.

---

### Task 10: The scratch revalues, the founder's reading, the live step and the readout (spec 13)

Nothing in this task runs without the founder's word. Ask once, with this list: a copy of the live store, two revalues on copies, the merge and the push, the backup, the server's restart, one revalue on the live store. No vendor call.

- [ ] **Step 1: The scratch revalues.** Copy the live database twice with SQLite's backup. Revalue one copy with the branch's code as it is at the commit before Task 8's, and the other with the branch's head.

- [ ] **Step 2: The readout** (spec 13). Without Task 8: every row and every review identical to the live refresh. With it: the Mature Growth rows whose revenue step is not read, by the analysts' count; the value's moves (the median, the share within 5% and within 10%, the ten largest each way); ACM, FRO, HESM and BIPC; the rows that newly value or newly refuse; the cross-checks that moved; each review whose value moved.

- [ ] **Step 3: The Methodology page's examples**, if method 1.5 is to merge: re-read the six on the scratch copy's rows and change each figure that moved, with the dating paragraph and its pins. Run the four checks and commit.

- [ ] **Step 4: The founder's reading.** Give the founder the readout of the thin rule in everyday words, with one company's figures step by step, and ask whether it merges. If not: revert Task 8's commits and the examples' commit, take its row out of `docs/method.md` 11 and its lines out of the drawer, run the four checks.

- [ ] **Step 5: The live step.** Merge to main and push; back up the live database; stop the server by its process ids; run one revalue by the command line; start the server from main. The live revalue must be identical to the scratch copy that matches what merged.

- [ ] **Step 6: The readout**, written into the spec's decision log, and the backlog: B-145, B-146, B-148, B-151, B-98 and B-179 to Done with their commits; B-150 keeps its date; the review's parked minors as one row. Commit, remove the worktree and the workspace, and tell the founder that every research session must restart its MCP process.

---

## Self-review notes

- Spec coverage: 10 (v16) is Task 1; 4 is Task 2; 5 is Task 3; 6.1 and 6.3 are Task 4; 7 is Task 5; 8 is Task 6; 9 is Task 7; 6.2 and method 1.5 are Task 8; 11 is spread over the tasks' document steps and Task 9; 12's tests are in the tasks that own the code; 13 is Task 10.
- The order: Task 2 before Task 3, which stands on the count the consensus is on; Task 4 before Task 8, which adds one source to its entry; Tasks 5, 6 and 7 need Task 1 alone. Task 8 comes last among the engine tasks so that its commits can be left out.
- The count of inputs moves three times, to twenty-two, twenty-three and twenty-five, each in the task that adds the tags.
