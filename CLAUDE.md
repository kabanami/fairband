# Fairband

A local valuation screen for a value investor. Python 3.13, uv, FastAPI.
Package in `src/fairband/`; tests in `tests/`, mirroring the package.

## Read first

- Method as built: `docs/method.md`. The single statement of the classifier, the routes, the
  flags and the refusals the engine runs. Where it and any other document disagree, it
  describes what runs. Change it in the same commit as any change to the engine, the
  classifier, the universe rule or a policy value. The Methodology page
  (`src/fairband/web/static/methodology.html`) changes in the same commit, and a change of
  method version re-reads its examples' figures.
- Design: `docs/legacy/design.md`. The original design and the reasons behind the method;
  where `docs/method.md` and the specs are silent, it applies.
- Spec: `docs/superpowers/specs/2026-10-31-mechanical-screen-design.md`. The mechanical
  screen; where it and a legacy document disagree, the spec wins.
- Plan: `docs/superpowers/plans/2026-10-31-mechanical-screen.md`. The task order and the
  global constraints every task follows.
- Backlog: `docs/backlog.md`. The running list of work not started; Now is ordered. At the end
  of each plan, the ledger's deferred minors and parked findings move there before the workspace
  is deleted.
- Brand book: `fairband-design-system/docs/brand-book.md` inside the archive
  `docs/design-system/fairband-design-system_4.tar.gz`. Read it without unpacking:
  `tar -xzOf docs/design-system/fairband-design-system_4.tar.gz fairband-design-system/docs/brand-book.md`
  Its rules on provenance, the dates and the validity window cover Fairband's own figures and
  writes: the value, the levels, an input, an override, a record. A cite on every number is
  the rule of an agent's report alone (`docs/method.md` 16). Vendor reference data on a page
  (a company's statistics, prices, estimates, news) is shown plain: no cite, no chip and no
  vendor's name on a figure or a block, and one data date for the page or the block. An owner's
  moat class is saved without a reason (the founder, 2026-11-19). Motion is allowed in three
  places and no other (the founder, 2026-11-23): the refresh layer's fade, the run bar's fill and
  the highlight of a changed figure. The two fades run under the system's reduced-motion setting
  too.

## Keys and data

- Never print, log, store or commit a key: not in a URL that is logged or stored, a log line,
  the database, an error message or a test fixture.
- Never commit vendor data. Test fixtures are synthetic or hand-trimmed. The one exception is
  the README's screenshots in `docs/images/`: they show the page as it runs, real companies and
  their figures included (the founder, 2026-11-18). Do not remove them or redraw them on
  invented companies.
- Keys live in `~/.config/fairband/keys.toml`, outside the repository.
- Data lives in `~/.local/share/fairband`.

## Checks

Use `uv run` for every command; dependencies are locked in `uv.lock`. Run before every commit:

```
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
```

A commit of documents alone (Markdown files and files under `docs/`; nothing under `src/` or
`tests/`, no `pyproject.toml` and no `uv.lock`) runs this shorter check in its place, the tests
that read a document (the founder, 2026-11-18):

```
uv run ruff check . && uv run ruff format --check . && uv run pytest -q tests/test_method_doc.py tests/test_playbook.py tests/reports/test_render.py tests/web/test_design_tokens.py tests/policy/test_moat.py
```

## Commits

- The message is one plain sentence in the imperative; see `git log` for the style.
- Every commit ends with a `Co-Authored-By: Claude <model> <noreply@anthropic.com>` line
  naming the Claude model that wrote the change.
