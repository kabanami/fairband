# Playbook: the Latest Price and the Report's Words Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every run reads the company at the latest price, and every report is written in phrases a reader who has never seen Fairband follows, the method's own terms kept out of the text or given once in brackets.

**Architecture:** Three changes to the playbook (`playbook/fairband-research/`) and its pins in `tests/test_playbook.py`: step 3 opens with a scoped refresh of the company on every item, not only an expired one (B-126); the register's "Plain meanings to reuse" becomes "The words a report writes", a rule and a table of the method's terms with the phrase the report writes instead, and the template's example and summary shape are rewritten in those phrases (B-134); step 12 reads the report once as its reader before it is submitted (B-134). No engine, method, policy, page or server change. The live skill is a symlink into the repository's playbook directory, so the merge to main is the deployment.

**Tech Stack:** Markdown (the skill and its references), pytest (the pins).

**Spec:** `docs/superpowers/specs/2026-11-06-tier-2-agents-design.md`, amended 2026-11-09 for plan 5: section 13.1 (the paragraph "The words"), section 14 (step 3, step 12 and the rules paragraph) and the decision log's last row. Backlog items B-126 and B-134. B-135 (a words warning at publish) is deferred by the founder's ruling and is not in this plan.

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`. The suite is green at the base (2,128 tests).
- The commit message is one plain sentence in the imperative, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01K4pNFGMWqnrPuvG88Nf31f`.
- Never print, log, store or commit a key; never commit vendor data; test fixtures are synthetic. The live database (`~/.local/share/fairband`), the keys file and the live server on port 8470 are off limits: no request of any kind. Never push.
- Nothing under `src/` changes. `docs/method.md` and the Methodology page do not change. The spec is already amended; a task that finds the spec and the playbook in conflict stops and reports it.
- The playbook is read by an agent and its reports by a person. Its text is plain English in the register's own rules (`playbook/fairband-research/reference/register.md`: the answer first, short sentences, no idiom, no first person). A sentence this plan pins is used verbatim, line breaks aside; the pins flatten whitespace (`_flat`).
- The template's full submission example keeps every cite and every ref as they are: only the plain strings change, and every plain string still holds no quantity (`test_the_template_example_passes_the_structural_checks_and_the_token_rule`).
- A test pins a sentence or a shape of the text, in the style of `tests/test_playbook.py` (`_steps`, `_flat`, `_tool_entry`, `_example`), never a line number.

## Review Focus

1. A scoped refresh refused because another refresh is running: the agent waits for that one on `refresh_status()` and then starts its own; it never goes on with the stale snapshot. Pinned in Task 1.
2. A scoped refresh that ends `failed` or `cancelled`: the agent tells the user, goes on with the stored snapshot, and section 9 names the price's date, so a reader sees how old the price is. Pinned in Task 1.
3. An `expiry` item is refreshed once, in step 3, not twice: step 2's old instruction to refresh it first is gone. Pinned in Task 1.
4. The judgments' decisions follow the words rule too, since the page shows them: no name of Fairband's parts, and a method term only in brackets. Pinned in Task 2.
5. The reader test sits before `report_submit` in step 12, so a report fixed after a rejection is read again before it goes back. Pinned in Task 3.

---

### Task 1: The latest price (B-126)

**Files:**
- Modify: `playbook/fairband-research/SKILL.md` (step 2's `expiry` paragraph, "An item of origin `expiry` …"; step 3's opening, "First, the window. …" to "The snapshot id is new."; the rules' bullet "Start a refresh only in three cases …")
- Test: `tests/test_playbook.py` (`STEPS[3]`, a new test)

**Interfaces:**
- Consumes: the MCP tools `refresh_start(kind, symbols?)` and `refresh_status()` as `reference/tools.md` lists them (unchanged); `refresh_status()` answers `{refresh, last}`, `refresh` the running one or `null`, `last` the last run's record with its `status`, one of `done`, `failed` or `cancelled`.
- Produces: step 3's refresh paragraph, which Task 2 and Task 3 leave as it is.

- [ ] **Step 1: Write the failing pins**

In `tests/test_playbook.py`, add `"refresh_start", "refresh_status"` to `STEPS[3]` (the test `test_the_skill_has_the_frontmatter_and_the_thirteen_steps` then requires step 3 to name both), and add:

```python
def test_every_item_is_refreshed_before_it_is_read() -> None:
    """Spec 14 step 3 (plan 5, B-126): a scoped refresh of the company opens step 3 on every
    item, so the report reads the latest price; before plan 5 only an expired company was
    refreshed, and QCOM's report 2 of 8 Nov 2026 read the close of 4 Nov."""
    _, body = _frontmatter(_read(SKILL))
    steps = _steps(body)
    three = _flat(steps[3])
    assert "Every item: refresh the company before you read it" in three
    assert 'Call `refresh_start("scoped", [symbol])`' in three
    assert "call `refresh_status()` until that one ends, then start yours" in three
    assert "When `last` ends with a `status` other than `done`" in three
    assert "section 9 names the price's date" in three
    skill = _flat(_read(SKILL))
    assert "Start a refresh only in three cases: the scoped refresh of the company at the start of step 3" in skill
    assert "`valid_until` before today" not in skill  # the old condition is gone
    assert "Refresh it first, at the start of step 3" not in _flat(steps[2])  # step 2 no longer refreshes
```

- [ ] **Step 2: Run the pins to see them fail**

Run: `uv run pytest tests/test_playbook.py -q -k "refreshed or thirteen"`
Expected: FAIL on `"Every item: refresh the company before you read it" in three`.

- [ ] **Step 3: Rewrite step 3's opening in `SKILL.md`**

Replace the paragraph "First, the window. …" and its three bullets with this text, verbatim:

```
First, the refresh. Every item: refresh the company before you read it, so the report rests on
the latest price and the row's price, price ÷ value and designation are current when the report
publishes. The stored price is the last refresh's close, which may be days old.

- Call `refresh_start("scoped", [symbol])`. When it is refused because a refresh is running, call
  `refresh_status()` until that one ends, then start yours.
- Call `refresh_status()` until its `refresh` is `null`: no refresh is running, and `last` is the
  one you started.
- When `last` ends with a `status` other than `done`, tell the user, and go on with the stored
  snapshot; section 9 names the price's date.
- Read `company(symbol)`. The snapshot id is the one the report cites; its `price_date` is the
  latest close.

A scoped refresh fetches the company's price and statements again and values it. It takes about
a minute.
```

In step 2, replace "An item of origin `expiry` is a company whose validity window has ended: its snapshot is stale. Refresh it first, at the start of step 3." with "An item of origin `expiry` is a company whose validity window has ended. Step 3's refresh renews it, as it renews every company's."

In the rules, replace the refresh bullet with: "Start a refresh only in three cases: the scoped refresh of the company at the start of step 3; a revalue when a refusal asks for one; or when the user asks."

- [ ] **Step 4: Run the playbook tests**

Run: `uv run pytest tests/test_playbook.py -q`
Expected: PASS, every test.

- [ ] **Step 5: Commit**

```bash
git add playbook/fairband-research/SKILL.md tests/test_playbook.py
git commit -m "Refresh the company at the start of step 3 on every item so the report reads the latest price"
```

---

### Task 2: The words a report writes (B-134, the file and the template)

**Files:**
- Modify: `playbook/fairband-research/reference/register.md` (the 9.2 bullets "Keep codes out of the reader part …" and "Explain each term the first time …"; "The voice" bullet "Write in the third person for what the engine does …"; the section "Plain meanings to reuse", which this task replaces)
- Modify: `playbook/fairband-research/SKILL.md` (the rules' bullet "Write in the register of design.md 9.2 …")
- Modify: `playbook/fairband-research/reference/report-template.md` (the summary page's shape block under "## The summary page"; the full submission example's plain strings in the sections Summary, Industry and competition, Valuation, Price and multiples and Key judgments, and the judgments' decisions; the sentence "The reviewed value is the engine's value under this report's overrides. The buy level is that value less a margin of safety." goes)
- Test: `tests/test_playbook.py` (a new test and two helpers)

**Interfaces:**
- Consumes: nothing from Task 1 beyond its text standing.
- Produces: the register's section heading `## The words a report writes` and its table, which Task 3's reader test names.

- [ ] **Step 1: Write the failing pins**

In `tests/test_playbook.py`:

```python
# The names of Fairband's parts, which a report never writes (register, "The words a report writes").
NEVER = ("the engine", "the classifier", "the route", "the snapshot", "check flag", "the bridge", "a tag", "an id")
# Method terms the register's table must map to a plain phrase.
TERMS = (
    "belief", "mechanical value", "reviewed value", "override", "review", "bridge", "buy level",
    "margin of safety", "fair band", "trim level", "designation", "phase", "moat", "runway",
    "runway return", "held rate", "target margin", "sales-to-capital", "hurdle rate", "consensus",
    "snapshot", "validity window", "secondary valuation", "sensitivity grid", "kill criterion",
)
# Terms the example's Summary writes as their phrase, never by name.
SUMMARY_FREE = ("belief", "reviewed value", "mechanical value", "buy level", "trim level", "fair band", "margin of safety", "runway", "override", "snapshot", "engine")


def test_the_report_writes_the_plain_phrase_not_the_term() -> None:
    """Spec 13.1 "The words" and 14 (plan 5, B-134): the register maps each method term to the
    phrase the report writes; the term appears once, in brackets, in section 8 only; the names of
    Fairband's parts never appear; the template's example and summary shape are written so."""
    register = _read(REGISTER)
    assert "## The words a report writes" in register
    flat = _flat(register)
    assert "Write what a figure is, not what Fairband calls it" in flat
    assert "in brackets after the phrase, in section 8 only" in flat
    for word in NEVER:
        assert f'"{word}"' in flat, word  # each named in the never-list
    rows = _table_rows(register[register.index("## The words a report writes") :])
    for term in TERMS:
        assert term in rows, term
        assert rows[term] and not rows[term].startswith("the engine"), term
    assert "every term explained the first time" not in _flat(_read(SKILL))
    assert "the method's terms as `reference/register.md` writes them" in _flat(_read(SKILL))
    assert "Name the input in words" not in flat  # the old 9.2 bullet, which told the agent to write the term
    # the template: the shape, the example's text and the judgments
    template = _read(TEMPLATE)
    shape = _shape(template)
    example = _example(template)
    sections = {s["heading"]: " ".join(p for p in s["parts"] if isinstance(p, str)) for s in example["sections"]}
    texts = [shape, *sections.values(), *(j["decision"] for j in example["judgments"])]
    for text in texts:
        low = text.lower()
        for word in NEVER:
            assert word not in low, (word, text[:80])
    for term in SUMMARY_FREE:
        assert term not in sections["Summary"].lower(), term
        assert term not in shape.lower(), term
    for term in ("belief", "runway return", "mechanical value", "reviewed value"):
        bare = [m.start() for m in re.finditer(re.escape(term), sections["Valuation"])]
        bracketed = [m.start() + 5 for m in re.finditer(rf"\(the {re.escape(term)}\)", sections["Valuation"])]
        assert bare == bracketed and len(bare) <= 1, term  # once, and only in brackets
    for decision in (j["decision"] for j in example["judgments"]):
        assert "belief" not in decision or "(the belief)" in decision, decision
```

And the two helpers, next to `_example`:

```python
def _table_rows(text: str) -> dict[str, str]:
    """The first Markdown table in ``text``: its first column to its second, the header and the
    separator left out."""
    rows = {}
    for line in text.splitlines():
        if line.startswith("| ") and not line.startswith("|---") and "| Term" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] and not set(cells[0]) <= {"-", ":"}:
                rows[cells[0]] = cells[1]
    return rows


def _shape(text: str) -> str:
    """The summary page's shape: the fenced block after ``## The summary page``."""
    after = text[text.index("## The summary page") :]
    return re.search(r"^```\n(.*?)^```", after, re.MULTILINE | re.DOTALL)[1]
```

- [ ] **Step 2: Run the pin to see it fail**

Run: `uv run pytest tests/test_playbook.py -q -k plain_phrase`
Expected: FAIL on `"## The words a report writes" in register`.

- [ ] **Step 3: Rewrite the register**

Replace the section "## Plain meanings to reuse" (its heading, its sentence and its table, to the paragraph on possible, plausible and probable, which stays) with "## The words a report writes", opening with this text, verbatim:

```
The report is read by people who have never seen Fairband and will not read its method. Write
what a figure is, not what Fairband calls it. Fairband's own terms, the left column below, never
carry a sentence: "The belief is 5.3%" tells such a reader nothing. Write the right column, and
give the term once, in brackets after the phrase, in section 8 only, where the reader needs it to
find the figure in Appendix A or on the Methodology page. Outside section 8 the term does not
appear. The names of Fairband's parts never appear in a report: not "the engine", "the
classifier", "the route", "the snapshot", "check flag", "the bridge", "a tag" or "an id". Write
"Fairband" for the product and say what the thing did: "Fairband puts the company in its Mature
Growth stage", "the data on file as of 4 Nov 2026".
```

Then the table, `| Term | Write instead |`, one row for each term of the old table and for each of `TERMS`, the phrase a reader follows with no method behind it and holding no other term of the table. Four rows set the style; the implementer writes the rest to match:

| Term | Write instead |
|---|---|
| belief | the growth rate the value assumes after the analysts' forecast years |
| mechanical value | the value a share before this report's changes to the inputs |
| reviewed value | the value a share under this report's changes to the inputs |
| snapshot | the data on file as of a date, the date written out |

Edit the 9.2 bullets: "Keep codes out of the reader part: no tag (`growth.belief`), no ref, no id, no snake_case input name. Name the input in words: "the belief"." becomes "Keep codes out of the reader part: no tag (`growth.belief`), no ref, no id, no snake_case input name. Name the input by what it is, as the table below writes it." and "Explain each term the first time it appears, in brackets or in a short clause." becomes "Write the method's terms as the table below writes them: the phrase in the text, the term once in brackets in section 8 only." In "The voice", "Write in the third person for what the engine does: "The engine recomputes the value after each override."" becomes "Write in the third person for what Fairband does: "Fairband recomputes the value after each change to an input.""

In `SKILL.md`'s rules, the bullet "Write in the register of design.md 9.2 (`reference/register.md`): the answer first; short sentences, one idea each; every term explained the first time; rounded numbers." becomes "Write in the register of design.md 9.2 (`reference/register.md`): the answer first; short sentences, one idea each; rounded numbers; the method's terms as `reference/register.md` writes them, the plain phrase in the text and the term once in brackets in section 8 only."

- [ ] **Step 4: Rewrite the template's shape and example**

In `report-template.md`, rewrite the summary page's shape block and the example's plain strings in the register's phrases, keeping every cite and ref as it is. The Summary names no method term (`SUMMARY_FREE`): the value is "the value this report puts on the company", the buy level "the price at which the discount is wide enough to buy", the fair band "prices close to the value", the phase "its stage"; the sentence "The reviewed value is the engine's value under this report's overrides. The buy level is that value less a margin of safety." goes. The Valuation section writes "Fairband puts the company in its Mature Growth stage", "no warning was raised" for the check flag, "the value before this report's changes (the mechanical value)", "two changes to the inputs moved it to", "the growth rate the value assumes after the analysts' years (the belief)", and "the return the company earns on the money it reinvests in the coming years (the runway return)"; each of those four terms appears once in the section, in brackets. Price and multiples drops "the engine's" and "the snapshot's". Key judgments and the judgments' decisions write "the growth rate assumed after the analysts' years rose to the rate the longer contracts support (the belief)" and "the return on reinvested money Fairband measured stands". Elsewhere in the file, the instructions to the agent keep the terms: they are read by the agent, not the reader.

- [ ] **Step 5: Run the playbook tests**

Run: `uv run pytest tests/test_playbook.py -q`
Expected: PASS, every test, `test_the_template_example_passes_the_structural_checks_and_the_token_rule` included.

- [ ] **Step 6: Commit**

```bash
git add playbook/fairband-research/reference/register.md playbook/fairband-research/reference/report-template.md playbook/fairband-research/SKILL.md tests/test_playbook.py
git commit -m "Write the report in plain phrases, the method's terms once in brackets in the valuation section only and Fairband's parts never named"
```

---

### Task 3: The reader test (B-134, step 12)

**Files:**
- Modify: `playbook/fairband-research/SKILL.md` (step 12, "The report", between "Give the judgments as the record of your decisions …" and "Submit with `report_submit`.")
- Test: `tests/test_playbook.py` (a new test)

**Interfaces:**
- Consumes: the register's section `## The words a report writes` (Task 2).
- Produces: nothing later tasks use.

- [ ] **Step 1: Write the failing pin**

```python
def test_the_report_is_read_as_its_reader_before_it_is_submitted() -> None:
    """Spec 14 step 12 (plan 5, B-134): the agent reads the report once as someone who has never
    seen Fairband, before `report_submit`, so a report fixed after a rejection is read again."""
    _, body = _frontmatter(_read(SKILL))
    twelve = _flat(_steps(body)[12])
    sentence = "read the report once as its reader: someone who has never seen Fairband"
    assert sentence in twelve
    assert "Rewrite every sentence that needs the Methodology page to follow" in twelve
    assert '"The words a report writes"' in twelve
    assert "the summary alone: it must stand on its own" in twelve
    assert twelve.index(sentence) < twelve.index("Submit with `report_submit`")
```

- [ ] **Step 2: Run the pin to see it fail**

Run: `uv run pytest tests/test_playbook.py -q -k its_reader`
Expected: FAIL on `sentence in twelve`.

- [ ] **Step 3: Add the paragraph to step 12**

After "Give the judgments as the record of your decisions, each `{judgment, decision, override_id?}`." and before "Submit with `report_submit`.", insert, verbatim:

```
Before you submit, read the report once as its reader: someone who has never seen Fairband, will
not read its method, and wants to know what the company is worth and why. Rewrite every sentence
that needs the Methodology page to follow, by `reference/register.md`, "The words a report
writes". Then read the summary alone: it must stand on its own, since many readers stop there.
```

- [ ] **Step 4: Run the playbook tests**

Run: `uv run pytest tests/test_playbook.py -q`
Expected: PASS, every test.

- [ ] **Step 5: Commit**

```bash
git add playbook/fairband-research/SKILL.md tests/test_playbook.py
git commit -m "Read the report once as a reader who has never seen Fairband before it is submitted"
```

---

### Task 4: The finish (the controller's steps, not a subagent's)

- [ ] **Step 1: Final whole-branch review** (superpowers:requesting-code-review) on the most capable model, one fix wave, a clean re-review. The reviewer reads the template's example as the reader the rule describes and checks each of the register's phrases against `docs/method.md` 13.
- [ ] **Step 2: Merge to main and push**, per the founder's standing instruction: `git merge --ff-only`, the full check on main, push, remove the worktree and the branch. No server restart: the live skill is a symlink into the repository's playbook directory.
- [ ] **Step 3: The spec and the backlog.** The spec's status line gains "(merged 2026-11-09, …)" for plan 5. B-126 and B-134 move to Done with their commits; the plan's deferred minors and parked findings move in as one row.
- [ ] **Step 4: Memory** and the message to the founder, with the rulings made during the build and what the next two company runs should show: a report that opens with the latest price and reads without the method.
