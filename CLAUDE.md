# Fairband

A local valuation screen for a value investor. Python 3.13, uv, FastAPI.
Package in `src/fairband/`; tests in `tests/`, mirroring the package.

## Read first

- Method as built: `docs/method.md`. The single statement of the classifier, the routes, the
  flags and the refusals the engine runs. Where it and any other document disagree, it
  describes what runs. Change it in the same commit as any change to the engine, the
  classifier, the universe rule or a policy value.
- Design: `docs/legacy/design.md`. The original design and the reasons behind the method;
  where `docs/method.md` and the specs are silent, it applies.
- Spec: `docs/superpowers/specs/2026-10-31-mechanical-screen-design.md`. The mechanical
  screen; where it and a legacy document disagree, the spec wins.
- Plan: `docs/superpowers/plans/2026-10-31-mechanical-screen.md`. The task order and the
  global constraints every task follows.
- Brand book: `fairband-design-system/docs/brand-book.md` inside the archive
  `docs/design-system/fairband-design-system_4.tar.gz`. Read it without unpacking:
  `tar -xzOf docs/design-system/fairband-design-system_4.tar.gz fairband-design-system/docs/brand-book.md`

## Keys and data

- Never print, log, store or commit a key: not in a URL that is logged or stored, a log line,
  the database, an error message or a test fixture.
- Never commit vendor data. Test fixtures are synthetic or hand-trimmed.
- Keys live in `~/.config/fairband/keys.toml`, outside the repository.
- Data lives in `~/.local/share/fairband`.

## Checks

Use `uv run` for every command; dependencies are locked in `uv.lock`. Run before every commit:

```
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
```

## Commits

- The message is one plain sentence in the imperative; see `git log` for the style.
- Every commit ends with a `Co-Authored-By: Claude <model> <noreply@anthropic.com>` line
  naming the Claude model that wrote the change.
