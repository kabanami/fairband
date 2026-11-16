# The Research Button Opens Claude Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A click on Request research posts the work item and opens a terminal window in which Claude Code starts with the research skill and the item's id; the Agents section of Settings holds what the launch needs, in one file; a failure says which stage failed and why.

**Architecture:** The values are a file, `launch.json` in the config folder, read at each use. `POST /api/launches` stores a launch, then runs the window command with five plain words added, with no shell. In the window a packaged script runs under `bash -l` and starts `fairband launch <port> <id>`, which asks the server for the agent's words, starts Claude Code as its child and reports `started`, `ended` or `failed`. The page reads the launch every 2 seconds and draws one line for each state.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, httpx; plain JavaScript with React from the design-system bundle; pytest, with node for the page's own scripts (`tests/web/page.mjs`, `tests/support/page.py`).

**Spec:** `docs/superpowers/specs/2026-11-16-agent-launch-design.md`. Read it with your task: this plan argues from it, and where the two differ the spec wins.

**A map of the code as it stands:**

- `src/fairband/web/app.py`: `create_app(settings, policy, conn_factory, worker, clock, tax, passthrough, fetch_logo)`; its `lifespan` marks interrupted refreshes; `company()` is the detail read; the module docstring states D11. `Settings.config_dir` is the config folder.
- `src/fairband/web/identity.py`: `writer_of(request)` gives a `Writer`; `writer.principal` is `"owner"` or `"agent"`. `agents_api.py` uses it as the dependency `WriterOf`.
- `src/fairband/store/inbox.py`: `WorkItem` (`id`, `symbol`, `mode`, `state`, `claimed_by`), `work_item(conn, id)` (raises `KeyError` for none), states `pending`, `claimed`, `done`, `declined`, `dropped`.
- `src/fairband/web/research_api.py`, `agent_records`: builds the detail read's `item` (`id`, `state`, `mode`, `claimedBy`, `createdAt`).
- `src/fairband/store/db.py`: `connect`, `transaction(conn, immediate=True)`, `migrate`; a migration is `src/fairband/store/migrations/NNN_name.sql`. `src/fairband/store/_codec.py`: `dump_stamp`, `load_stamp`.
- `src/fairband/__main__.py`: `_build_parser`, `_COMMANDS`, `_serve` (passes `args.port` to uvicorn only), `_mcp`.
- `src/fairband/mcp/client.py`: an `httpx.Client` on `127.0.0.1:<port>` with `trust_env=False`; the request header is `web.app.REQUEST_HEADER`.
- `src/fairband/web/static/app.js`: `requestResearch(ask, item, redraw, after)`, `RequestMenu`, `postRequest`, `requested(item)`, `asking(symbol)`, `api.post`, `getJson`, and `window.FairbandPage` (the helpers other scripts and the node tests read). `report.js` calls `P.requestResearch(state.request, d.item, render, load)` twice. `settings.js` owns `#settings`; its `View` draws one `<form>`; `P.onShow.settings` loads it.
- Tests: `tests/support/web_app.py` (`client`, `db_path`, `policy`), `tests/support/web.py` (`HOST`, `HEADER`, `NOW`, `_settings`, `_static_file`), `tests/support/page.py` (`node(helper, args, *scripts)`); a test directory has a `conftest.py` and no `__init__.py`.

## Global Constraints

- No file under `src/fairband/engine/`, `src/fairband/policy/`, `src/fairband/refresh/` or `src/fairband/vendors/` changes. `docs/method.md` and the Methodology page do not change. No value, level, flag or settings hash moves.
- Nothing writes the `settings` table or reaches `store.settings.read_overlay`.
- One migration, `src/fairband/store/migrations/009_launches.sql`, written whole in Task 2 and not edited after it: a migration is recorded with its checksum.
- **No shell, anywhere.** A program starts from a list of arguments (`subprocess` with `shell=False`); no `os.system`, no `shell=True`, no string handed to a shell.
- **No test opens a window, starts an agent or uses the network.** The window command's runner, the program finder and the launcher's program start are doubles. An app built without an opener opens nothing (Task 5).
- Every sentence a person reads is copied from this plan's tables, which copy the spec's. A changed word is a spec change.
- A plain word matches `[A-Za-z0-9_./:@+-]+`. `CLAIM_WAIT_S = 90`. `WINDOW_LIMIT_S = 15`. The page reads a launch every 2 seconds and stops 600 seconds after it was made.
- Work in a worktree, not in the main checkout: the live server on port 8470 serves the page files of the main checkout as they are on disk.
- Never print, log, store or commit a key. The launcher reads no key and opens no database.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- A commit message is one plain sentence in the imperative, then a blank line, then these two lines in this order, the second naming the model that wrote the change:
  `Claude-Session: https://claude.ai/code/session_01K4pNFGb6uWekaVUA4NgJbB`
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Review Focus

Five conditions the spec implies and a hurried build would miss. Each has its test in the task that owns the code.

1. **A file caught half written.** An agent or an editor is writing `launch.json` while the server reads it: the text is cut short, or empty. The read answers `fileError`, launching is off, no route answers 500, and the next read of the whole file is right (Tasks 1, 4).
2. **A save over a file that changed underneath.** The form loaded, then an agent changed `claude.model` in the file, then the founder saves a new `claude.effort`. The save sends its changed names alone and lays them over the file as it is now, so the model the agent wrote stays (Task 4).
3. **The window command's error output is not UTF-8.** `wsl.exe` and `wt.exe` write UTF-16 with a NUL after each letter. The failure's sentence is readable: NULs dropped, undecodable bytes replaced, the first line that holds text, at most 200 characters (Task 3).
4. **Two clicks at once.** Two `POST /api/launches` for one item arrive together. One window opens; the second answers 409. The check and the insert are one `BEGIN IMMEDIATE` transaction (Task 5).
5. **An agent claims the item before the launch is posted.** A session that already runs claims the oldest pending item in the moment between the two posts. `POST /api/launches` answers 409 "item 12 is claimed by …"; the page shows no error for it, reads the company again and draws the claim (Tasks 5, 8).

---

### Task 1: The launch file (spec 7.1, 7.2)

**Files:**
- Create: `src/fairband/launch/__init__.py`, `src/fairband/launch/settings.py`
- Test: `tests/launch/conftest.py` (empty but for a docstring), `tests/launch/test_settings.py`

**Interfaces:**
- Produces, in `src/fairband/launch/settings.py`:

```python
FILE_NAME = "launch.json"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
MODES = ("acceptEdits", "auto", "dontAsk", "manual", "plan")  # bypassPermissions is not offered
NAMES = ("window_command", "claude.command", "claude.prompt", "claude.model", "claude.effort",
         "claude.permission_mode", "claude.folder")            # the file's order and the form's
DEFAULTS: dict[str, str]   # "" but: claude.command "claude"; claude.prompt
                           # "/fairband-research work item {item}"; claude.folder "~/fairband-research"

@dataclass(frozen=True)
class LaunchFile:
    values: dict[str, str]   # every name of NAMES; the defaults where `error` is set
    error: str | None        # the fileError sentence; None for a usable file and for no file

    @property
    def ready(self) -> bool: ...   # no error and a window command that is not empty

def check_value(name: str, value: str) -> str | None: ...
    # the rule `value` breaks, as the words after "<name>: "; None when it breaks none
def read_launch_file(config_dir: Path) -> LaunchFile: ...          # never raises
def write_launch_file(config_dir: Path, changes: Mapping[str, str]) -> LaunchFile: ...
    # lays `changes` over the file as it is now (over the defaults where it is unusable), checks
    # every name, and writes the whole file; ValueError("<name>: <rule>") and nothing written
def suggested_window_command(environ: Mapping[str, str],
                             which: Callable[[str], str | None]) -> str | None: ...
```

- The file is one JSON object: `window_command`, and an object `claude` with `command`, `prompt`, `model`, `effort`, `permission_mode`, `folder`. A dotted name `claude.model` is `claude` then `model`. A save writes every name in `NAMES`' order, two spaces of indent, a newline at the end, through a temporary file in the same folder and `os.replace`; it makes the config folder where it is missing.
- The rules, each the words after `<name>: `:

| Name | Rule broken | Words |
|---|---|---|
| `window_command` | `shlex.split` raises | ``does not split into words: <the error's text>`` |
| `claude.command` | no word | `holds no word` |
| `claude.command` | first word starts with `-` | `starts with -` |
| `claude.prompt` | a line break | `is not one line` |
| `claude.prompt` | over 500 characters | `is longer than 500 characters` |
| `claude.prompt` | no `{item}` | `does not hold {item}` |
| `claude.prompt` | a `{name}` other than item, symbol, mode | ``holds {<name>}; a name in braces is item, symbol or mode`` |
| `claude.model` | white space | `holds white space` |
| `claude.model` | starts with `-` | `starts with -` |
| `claude.model` | over 100 characters | `is longer than 100 characters` |
| `claude.effort` | not empty, not in `EFFORTS` | ``is `<value>`; it is one of low, medium, high, xhigh, max`` |
| `claude.permission_mode` | not empty, not in `MODES` | ``is `<value>`; it is one of acceptEdits, auto, dontAsk, manual, plan`` |
| `claude.folder` | not absolute once `~` is the home | `is not an absolute path` |

- The `fileError` sentences: ``launch.json is not valid JSON (line <n>)``; ``launch.json: the file holds no object``; ``launch.json: `<name>` is not a name of this file`` (the dotted name; `claude` that is not an object reads ``launch.json: `claude` is not an object``); ``launch.json: `<name>` is not text``; ``launch.json: `<name>` <rule>``.
- `suggested_window_command`: `wt.exe -w 0 new-tab --title {title} wsl.exe -d <WSL_DISTRO_NAME> -e` where `environ` holds a plain-word `WSL_DISTRO_NAME` and `which("wt.exe")` finds it; else `None`.

- [ ] **Step 1: Write the failing tests.** No file: every default, no error, not ready. The example of spec 7.2 reads back name for name and is ready. A name left out has its default. Each row of the rules table through `check_value` and through a file that holds it (the sentence with `launch.json: ` before it). Each `fileError` sentence: text cut short at half its length, an empty file, a list, an unknown top name, an unknown name under `claude`, `claude` as text, a number as a value. `write_launch_file`: writes every name in order with the example's layout; makes the folder; lays a change over the file as it is now and keeps a name another writer changed since; over an unusable file starts from the defaults; a refused change raises `ValueError("claude.effort: is `extreme`; it is one of low, medium, high, xhigh, max")` and leaves the file's bytes as they were; no temporary file is left in either case. The suggested line with `WSL_DISTRO_NAME=Ubuntu` and `wt.exe` found; `None` without the name, with a name that is not a plain word, and with `wt.exe` not found. Review Focus 1.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/launch/test_settings.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 2: Migration 009 and the launch record (spec 8)

**Files:**
- Create: `src/fairband/store/migrations/009_launches.sql`, `src/fairband/store/launches.py`
- Test: `tests/store/test_launches.py`; modify `tests/store/test_db.py` and `tests/web/test_app.py` (each list `[1, 2, 3, 4, 5, 6, 7, 8]` of applied versions gains `9`)

**Interfaces:**
- Produces, the migration, whole:

```sql
-- A window opened from the research button, and what its launcher reported (spec 2026-11-16).
CREATE TABLE launches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER REFERENCES work_items(id),  -- NULL: a test from Settings
    agent TEXT NOT NULL,                        -- 'claude'
    state TEXT NOT NULL,                        -- opening, opened, started, ended, failed
    stage TEXT,                                 -- of a failure: window, agent
    detail TEXT,                                -- a failure's sentence
    exit_code INTEGER,                          -- of an agent that ended
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX launches_item ON launches (item_id, id);
```

- Produces, in `src/fairband/store/launches.py`:

```python
CLAIM_WAIT_S = 90
State = Literal["opening", "opened", "started", "ended", "failed"]
Stage = Literal["window", "agent"]
STOPPED = "the server stopped while the window command ran"

class WrongMove(ValueError): ...   # "a launch that is <from> does not become <to>"
class InFlight(ValueError): ...    # "a window for this request opened <n> seconds ago"

@dataclass(frozen=True)
class LaunchRow:
    id: int; item_id: int | None; agent: str; state: State; stage: Stage | None
    detail: str | None; exit_code: int | None; created_at: datetime; updated_at: datetime

def overdue(row: LaunchRow, item_state: str | None, now: datetime) -> bool: ...
def insert_launch(conn, item_id: int | None, agent: str, at: datetime) -> LaunchRow: ...
    # state opening; InFlight where the item's newest launch is opening, opened or started and
    # not overdue, read with the item as pending: the caller holds the write lock and has
    # checked that the item is pending (Task 5)
def launch(conn, launch_id: int) -> LaunchRow: ...              # KeyError(launch_id) for none
def newest_launch(conn, item_id: int) -> LaunchRow | None: ...
def move_launch(conn, launch_id: int, to: State, at: datetime, *, stage: Stage | None = None,
                detail: str | None = None, exit_code: int | None = None) -> LaunchRow: ...
def opened(conn, launch_id: int, at: datetime) -> LaunchRow: ...
    # opening -> opened; a launch the launcher already moved on stays as it is, and is answered
def fail_opening(conn, at: datetime) -> int: ...   # every `opening` to failed, window, STOPPED
```

- The moves: `opening` to `opened`, `started` or `failed`; `opened` to `started` or `failed`; `started` to `ended`. `move_launch` raises `WrongMove` for any other.
- `overdue`: an item's launch is overdue when it is `opened` or `started`, `item_state == "pending"` and `now - created_at >= 90 s`. A test (`item_id is None`, `item_state is None`) is overdue when it is `opened` and 90 seconds old, never once started.

- [ ] **Step 1: Write the failing tests.** The migration on a store at 008 that holds a work item: the item reads as before, `launches` is empty, `schema_versions` gains 009. Each allowed move and each refused one with its sentence. `opened` after the launcher's `started` leaves `started`. Overdue at 90 seconds and not at 89; never for a claimed, done or dropped item; a test overdue at `opened` and not at `started`. `insert_launch` refuses with `InFlight` and the seconds, and allows a second after `failed`, after `ended` and after an overdue launch; a test never blocks an item nor another test. `newest_launch` is the highest id. `fail_opening` moves `opening` alone and answers the count. Review Focus: a launch that is `started` when the server restarts stays `started` and still takes `ended`.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/store/test_launches.py tests/store/test_db.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 3: The words of a launch (spec 6.1, 6.3)

**Files:**
- Create: `src/fairband/launch/command.py`, `src/fairband/launch/launcher.sh`
- Test: `tests/launch/test_command.py`

**Interfaces:**
- Consumes: `launch.settings.LaunchFile`; `store.inbox.WorkItem`.
- Produces, in `src/fairband/launch/command.py`:

```python
WINDOW_LIMIT_S = 15
TEST_PROMPT = "/fairband-research launch test"

class WindowFailed(Exception): ...   # str(exc) is the failure's sentence

@dataclass(frozen=True)
class Opener:
    run: Callable[[Sequence[str]], subprocess.CompletedProcess[bytes]]
    which: Callable[[str], str | None]
    python: str                # sys.executable
    launcher: str              # the packaged launcher.sh's path
    environ: Mapping[str, str]

def system_opener() -> Opener: ...
    # run: subprocess.run(words, shell=False, stdin=DEVNULL, capture_output=True,
    # timeout=WINDOW_LIMIT_S); which: shutil.which; python: sys.executable; launcher: the path of
    # importlib.resources.files("fairband.launch") / "launcher.sh"; environ: os.environ
def is_plain(word: str) -> bool: ...
def window_words(window_command: str, title: str, opener: Opener, port: int,
                 launch_id: int) -> list[str]: ...
def open_window(words: Sequence[str], opener: Opener) -> None: ...   # WindowFailed
def agent_words(values: Mapping[str, str], item: WorkItem | None) -> list[str]: ...
def title_of(item: WorkItem | None) -> str: ...   # "Fairband-<SYMBOL>", "Fairband-test"
```

- `launcher.sh` is one line and a comment: `exec "$1" -m fairband launch "$2" "$3"`.
- `window_words`: the words of `shlex.split(window_command)` with `{title}` replaced in each, then `bash`, `-l`, `opener.launcher`, `opener.python`, `str(port)`, `str(launch_id)`. It raises `WindowFailed` before anything runs where the title or one of the last four words is not plain: ``` `<word>` cannot cross the window: it holds a character other than letters, digits and _ . / : @ + - ```.
- `open_window`, the failures' sentences:

| What happened | Sentence |
|---|---|
| `opener.which(words[0])` is `None`, or `run` raises `FileNotFoundError` | ``` `<words[0]>` was not found ``` |
| `run` raises another `OSError` | `the window command could not start: <the error's text>` |
| `run` raises `subprocess.TimeoutExpired` | `the window command did not end in 15 seconds` |
| exit code not 0 | `the window command ended with exit code <n>: <line>`, and without `: <line>` where the error output holds no text |

- `<line>`: the error output with every NUL byte dropped, decoded as UTF-8 with replacement, its first line that holds text, cut to 200 characters.
- `agent_words`: `shlex.split(values["claude.command"])`, then `--model <m>`, `--effort <e>`, `--permission-mode <p>` for each that is not empty, in that order, then one last word: `claude.prompt` with `{item}`, `{symbol}` and `{mode}` replaced from `item`, or `TEST_PROMPT` for a test.

- [ ] **Step 1: Write the failing tests.** `is_plain` on a path, a symbol with a dot and one with a dash, and on a space, a quote, a semicolon, `$` and an empty word. `window_words` for the line of spec 6.1 with item AAPL, port 8470 and launch 17: the exact list, in order. A launcher path with a space, a Python path with a space: `WindowFailed` with the sentence and no call to `run`. `open_window` passes the words to `run` as a list and never a string; each row of the table, with a double that raises or answers; error output written as UTF-16 with NULs (`"The system cannot find the file\r\n".encode("utf-16-le")`) reads as that line (Review Focus 3); 500 characters are cut to 200. `agent_words` for item 12 of QCOM in mode `full report`: with every field set the list of spec 6.3; with model alone, effort alone, mode alone and none; the prompt is one word with all three names replaced; a command of two words keeps both before the options; a test's last word. `launcher.sh` holds no shell name on its first line and the one `exec`.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/launch/test_command.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 4: The settings routes and `launchReady` (spec 7.3, 9)

**Files:**
- Create: `src/fairband/web/launch_api.py`
- Modify: `src/fairband/web/app.py` (register the routes; the detail read's `launchReady`; `create_app` gains `opener: Opener | None = None` and `port: int | None = None`)
- Test: `tests/web/test_launch_settings_api.py`; modify `tests/web/test_app.py` (the detail read's key set gains `launchReady`)

**Interfaces:**
- Consumes: Task 1's module; Task 3's `Opener`; `web.identity.writer_of`.
- Produces, in `src/fairband/web/launch_api.py`: `add_launch_settings_routes(app, config_dir: Path, opener: Opener | None) -> None`.
- `GET /api/launch-settings` answers:

```json
{"ready": false, "fileError": null, "suggested": "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e",
 "fields": [{"name": "window_command", "label": "Window command", "value": "", "default": "",
             "help": "…", "choices": null}, …]}
```

  one entry of `fields` for each of `NAMES`, in order; `choices` is `EFFORTS` or `MODES` for those two and `null` for the rest; `suggested` is `null` without an opener or where Task 1's function gives none. The labels are spec 7.1's Field column.
- `PUT /api/launch-settings` with `{"changes": {"claude.effort": "xhigh"}}` answers the form again. A name not in `NAMES` is a 400, ``<name>: is not a name of the Agents section``; a value that is not text a 400, ``<name>: is not text``; a broken rule a 400 with `write_launch_file`'s sentence. Where the window command is not empty and an opener is given, its first word must be one `opener.which` finds, else 400 ``window_command: `<word>` was not found on the server's path``. A request with the agent's principal header is a 403, `the Agents section is the owner's`.
- The detail read gains `"launchReady": read_launch_file(settings.config_dir).ready`.

- [ ] **Step 1: Write the failing tests.** The read with no file. A save, then the read and the file's bytes. Each refusal with its status and sentence, and the file unchanged after it. An agent's write is a 403 and writes nothing. A write without `X-Fairband-Request` is a 403. A file that is not JSON: the read answers 200 with `fileError` and the defaults, `ready` false; a save then writes a good file and clears the error (Review Focus 1). The form loaded, the file's `claude.model` changed on disk, a save of `claude.effort`: both hold (Review Focus 2). `suggested` with a double opener under WSL, and `null` without one. `launchReady` false with no file, true once a window command is saved, false again for an unusable file. The `settings` table holds no row after any of it, and `GET /api/settings` answers the same `settingsHash` as before.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_launch_settings_api.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 5: The launch routes (spec 6, 8, 9, 12)

**Files:**
- Modify: `src/fairband/web/launch_api.py`, `src/fairband/web/app.py` (register; the lifespan's `fail_opening`; the module docstring's D11 paragraph names the launch routes), `src/fairband/web/research_api.py` (`item.launch`), `src/fairband/__main__.py` (`_serve` passes `opener=system_opener()` and `port=args.port`)
- Test: `tests/web/test_launch_api.py`; modify `tests/web/test_research_api.py` or `tests/web/test_app.py` where the detail read's `item` is pinned

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces: `add_launch_routes(app, conn_factory, config_dir, opener, port, clock) -> None` and `launch_json(row: LaunchRow, item: WorkItem | None, now: datetime) -> dict[str, Any]` in `launch_api.py`.
- A launch as the API sends it:

```json
{"id": 17, "itemId": 12, "test": false, "agent": "claude", "state": "opened", "stage": null,
 "detail": null, "exitCode": null, "createdAt": "…", "updatedAt": "…", "ageSeconds": 4,
 "overdue": false, "itemState": "pending", "claimedBy": null}
```

- `POST /api/launches` with `{"itemId": 12}` or `{"test": true}`: 201 with the launch as the window command left it, `opened`, or `failed` with stage `window` and the sentence. The check of the item, the in-flight check and the insert are one `transaction(conn, immediate=True)`; the window command runs after that transaction commits, and its result is a second write.
- `GET /api/launches/{id}`: the launch. `GET /api/launches/{id}/command`: `{"argv": [...], "folder": "<absolute>"}`, the folder with `~` made the home. `POST /api/launches/{id}/status` with `{"state": "started" | "ended" | "failed", "detail": "…", "exitCode": 0}`: the launch after the move; `failed` is stage `agent`.
- The refusals:

| Route | When | Status | Sentence |
|---|---|---|---|
| `POST /api/launches` | the agent's principal | 403 | `a launch is the owner's` |
| | the app has no opener or no port | 503 | `this server opens no window` |
| | the file is unusable | 400 | the `fileError` sentence |
| | the window command is empty | 400 | `launching is not set up: see Settings, Agents` |
| | neither an item nor a test, or both | 400 | `a launch names an item or a test` |
| | no such item | 404 | `no work item <id>` |
| | the item is claimed | 409 | `item <id> is claimed by <actor>` |
| | the item is done, declined or dropped | 409 | `item <id> is <state>` |
| | a launch in flight | 409 | `a window for this request opened <n> seconds ago` |
| any launch route | no such launch | 404 | `no launch <id>` |
| `GET …/command` | the launch is past `opened` | 409 | `launch <id> is <state>` |
| | its item is no longer pending | 409 | the item's sentence above |
| `POST …/status` | the agent's principal | 403 | `a launch is the owner's` |
| | a move the record refuses | 409 | `a launch that is <from> does not become <to>` |
| | a state other than the three | 400 | `a launcher reports started, ended or failed` |

- The detail read's `item` gains `"launch"`: `launch_json` of `newest_launch(conn, item.id)`, or `null`.
- The lifespan calls `fail_opening(conn, clock())` beside `mark_interrupted` and logs the count.

- [ ] **Step 1: Write the failing tests.** With a double opener that records its words: a launch for a pending item answers 201 `opened`, and the words run are Task 3's for the saved window command, the app's port and the launch's id. The opener's `which` finds nothing: 201 `failed`, stage `window`, the sentence, and `run` not called. Each row of the refusals table. Two posts for one item: one row in `launches`, the second a 409 (Review Focus 4); a second is taken after the first failed. A post for an item an agent claimed meanwhile is the 409 of the table and runs nothing (Review Focus 5). A test launch has no item and runs with title `Fairband-test`. The command read: the argv of Task 3 and the folder made absolute; taken while `opening` and while `opened`; refused after `started`; refused once the item is claimed. Status: `started`, then `ended` with an exit code; `failed` with a sentence; a report on a launch still `opening`; each refused move; an agent's principal. The read's `overdue` at 90 seconds on the app's clock, `ageSeconds`, `itemState` and `claimedBy`. A write without `X-Fairband-Request` is a 403; the reads need none. An app built with no opener answers 503 and runs nothing. A launch left `opening` is `failed` after the app starts. The detail read's `item.launch` is the item's newest launch, and `null` with none. `serve` hands the app an opener and the port of `--port` (the test replaces `cli.system_opener` and `uvicorn.run`, as `tests/web/test_logo_api.py` replaces `cli.fetch_logo`).
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_launch_api.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 6: The launcher (spec 6.2)

**Files:**
- Create: `src/fairband/launch/run.py`
- Modify: `src/fairband/__main__.py` (the subcommand `launch`)
- Test: `tests/launch/test_run.py`; modify `tests/test_package.py` or add `tests/test_cli_launch.py` for the parser

**Interfaces:**
- Consumes: Task 5's two launcher routes; `web.app.REQUEST_HEADER`.
- Produces, in `src/fairband/launch/run.py`:

```python
def run_launcher(port: int, launch_id: int, *, http: httpx.Client | None = None,
                 start: Callable[[Sequence[str], str], subprocess.Popen[bytes]] | None = None,
                 out: TextIO = sys.stdout, hold: Callable[[], None] | None = None) -> int: ...
```

  `http` defaults to a client on `http://127.0.0.1:<port>` with `trust_env=False` and the request header on every call; `start(argv, folder)` defaults to `subprocess.Popen(argv, cwd=folder)`; `hold` defaults to waiting for Enter. It answers 0 after an agent that ran, whatever the agent's own exit code, and 1 after a failure.
- `fairband launch <port> <launch_id>`: both whole numbers; its help says the launcher's script calls it. It opens no database and reads no key. It sets the `httpx` and `httpcore` loggers to WARNING before its first call, so the window shows the launcher's own sentences and no log line.
- The order: read the command; make the folder with its parents; start the agent; report `started`; ignore SIGINT while it waits, and restore it after; report `ended` with the exit code.
- The failures. Each is written to `out`, then `Press Enter to close this window.`, then `hold()`:

| What happened | Written | Reported |
|---|---|---|
| the server does not answer | `no Fairband server answered on port <port>` | nothing |
| the command read is refused | the server's sentence | nothing |
| the folder cannot be made | `the folder <path> cannot be made: <the error's text>` | `failed`, the same sentence |
| the program is not found | ``` `<argv[0]>` was not found on the path of a login shell ``` | `failed`, the same sentence |
| the program cannot start | ``` `<argv[0]>` could not start: <the error's text> ``` | `failed`, the same sentence |

- A report that the server refuses or does not answer is written to `out` and does not stop the agent.

- [ ] **Step 1: Write the failing tests**, with `httpx.MockTransport` for the server and a double for `start`. The calls in order, each with the request header and no principal header: the command read, `started`, `ended` with exit code 3; the folder made under `tmp_path`; `start` called with the argv as a list and the folder; the answer 0. Each row of the table: what is written, what is reported, that `hold` ran, the answer 1, and that `start` did not run for the first three. A refused `started` report leaves the agent running to its end. SIGINT's handler is the default again after the call. The parser takes `launch 8470 17` and refuses a word that is no number. After the command ran, the `httpx` logger's level is WARNING. No name of `fairband.store` or `fairband.config.load_keys` is imported by `launch/run.py`.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/launch/test_run.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 7: The Agents section of the Settings page (spec 7.3, 7.4)

**Files:**
- Create: `src/fairband/web/static/agents.js`
- Modify: `src/fairband/web/static/app.js` (the one helper `following`, which the request button of Task 8 shares), `src/fairband/web/static/settings.js` (draw the section under the form; load it in `P.onShow.settings`), `src/fairband/web/static/index.html` (the script before `settings.js`; the section's styles)
- Test: `tests/web/test_agents_page.py`

**Interfaces:**
- Consumes: Task 4's and Task 5's routes; `FairbandPage.api`, `FairbandPage.getJson`.
- Produces `window.FairbandPage.agents`, in `agents.js`:

```js
load(redraw)        // GET /api/launch-settings into the section's state, then redraw()
section(redraw)     // the section's element, drawn by settings.js under its form
edits(form, draft)  // the names whose draft differs from the form's value, with their values
testLine(launch)    // the line of spec 7.4 for a test's launch: { text, failed }
```

- Produces `window.FairbandPage.following(launch)`, in `app.js`: whether the page reads the launch again. Task 8 uses it too.

- The section: a heading `Agents`; `fileError` at its head with `Correct the file, or save here to write it again.`; a row for each field with its label, its control and its help (a `<select>` with an empty first choice for the two fields with `choices`, a text field for the rest); **Use the Windows Terminal line**, shown only where `suggested` is not `null`, which fills the window command's draft and saves nothing; **Save**, off with no edit, which sends `edits` alone as `changes`; a refused save's sentence beside the field its first word names; **Test**, off while an edit is unsaved or launching is not ready, which posts `{test: true}` and follows the launch.
- `testLine`, by state:

| The launch | `text` | `failed` |
|---|---|---|
| `opening` | `Opening a window…` | no |
| `failed`, window | `Could not open the window: <detail>.` | yes |
| `opened` | `The window opened, Claude Code is starting…` | no |
| `opened`, overdue | `The window opened, but nothing in it reported after 90 seconds. Check the window.` | yes |
| `failed`, agent | `The window opened, but Claude Code did not start: <detail>.` | yes |
| `started` | `Claude Code started. Its window should say that the Fairband research skill is loaded.` | no |
| `ended` | `Claude Code ended (exit code <exitCode>).` | no |

- `following(launch)`: true while the state is `opening`, `opened` or `started`, `ageSeconds` is under 600, and, for an item's launch, `itemState` is `pending`. For a test (`launch.test`) it is false once `started` or overdue. False for no launch.
- The help under each field, one line: Window command, `How to open a terminal window. Fairband adds the launcher's words at the end.`; Claude Code command, `The program that starts Claude Code, found on the path of a login shell.`; First prompt, `The session's first message. {item}, {symbol} and {mode} are the request's.`; Model, `Empty for Claude Code's own default.`; Effort and Permission mode, the same; Folder, `Where the session starts. Fairband makes it.`

- [ ] **Step 1: Write the failing tests**, the helpers through `support.page.node("agents.<name>", args, STATIC / "agents.js")` and the drawing from the files' text, as `tests/web/test_logo_page.py` does. `edits` gives the changed names alone. Each row of `testLine`. `following` (through `node("following", …)`) on each state, at 599 and 600 seconds, for a claimed item, for a test at `started` and at `opened` overdue, and for no launch. From `agents.js`: the save sends `edits`; the test button's two conditions; the suggested button fills the draft and posts nothing; the refused save's sentence goes to its field; the section's timer is cleared when a launch stops being followed. From `settings.js`: the section is drawn after the form and loaded in `onShow.settings`. From `index.html`: `agents.js` loads before `settings.js`.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_agents_page.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 8: The request button (spec 10)

**Files:**
- Modify: `src/fairband/web/static/app.js`, `src/fairband/web/static/report.js`, `src/fairband/web/static/index.html` (the checkbox's and the line's styles, if any are new)
- Test: `tests/web/test_launch_page.py`; modify the tests in `tests/web/test_app.py` that pin `requestResearch`'s call and `requested`

**Interfaces:**
- Consumes: Task 5's routes and the detail read's `launchReady` and `item.launch`; Task 7's `following`.
- Produces, in `app.js`, each on `window.FairbandPage`:

```js
requestResearch(ask, item, redraw, after, ready)   // `ready` is the detail read's launchReady
launchLine(item, ready)   // { text, failed, action }: action is 'open', 'again' or null
openLaunch(ask, itemId, redraw, after)   // POST /api/launches, then follows the launch
```

- `asking(symbol)` gains `launch: true` (the checkbox's state) and `opening: false`.
- `launchLine`, from the open item and its `launch`:

| The item and its newest launch | `text` | `failed` | `action` |
|---|---|---|---|
| claimed, any launch | `Requested · claimed by <claimedBy>` | no | null |
| pending, no launch | `Requested · pending` | no | `open` where `ready`, else null |
| `opening` | `Requested · opening a window…` | no | null |
| `failed`, window | `Could not open the window: <detail>. Check Settings, Agents.` | yes | `again` |
| `opened` | `Requested · the window opened, Claude Code is starting…` | no | null |
| `opened`, overdue | `The window opened, but nothing in it reported after 90 seconds. Check the window.` | yes | `again` |
| `failed`, agent | `The window opened, but Claude Code did not start: <detail>. Check Settings, Agents.` | yes | `again` |
| `started` | `Requested · Claude Code started, not claimed yet` | no | null |
| `started`, overdue | `Claude Code started, but no agent claimed this request after 90 seconds. Check the window.` | yes | `again` |
| `ended`, still pending | `Claude Code ended before it claimed this request (exit code <exitCode>).` | yes | `again` |

- The buttons read **Open Claude Code** for `open` and **Open again** for `again`; each calls `openLaunch`. An `again` shows only where `ready`.
- The menu, where `ready`: a checkbox **Open Claude Code**, ticked, under the note line. `postRequest` posts the item as today; where the box is ticked and the post was taken, it calls `openLaunch` with the answer's `id` before `after()`.
- `openLaunch`: a 201 starts the following. A 409 whose item is no longer pending shows no error: it calls `after()`, and the line draws the claim (Review Focus 5). Any other refusal's sentence is `ask.error`.
- Following: one timer for an `ask`, every 2000 ms while `following(launch)`; each answer replaces the item's `launch` and redraws; when following ends it calls `after()` once. The timer is cleared when the drawer closes or shows another company, and when the report page shows another company. A view that loads with a followed launch starts following.
- `report.js` passes `d.launchReady` at both calls.

- [ ] **Step 1: Write the failing tests.** Each row of `launchLine` through node, with `ready` true and false. From `app.js`: the menu holds the checkbox only where `ready`, and `asking` starts it ticked; `postRequest` calls `openLaunch` with the post's id only where the box is ticked; `openLaunch`'s 409 for an item that is not pending calls `after()` and sets no error; the timer's 2000 ms and its three clears; a failure's line has the class of the request's error line. From `report.js`: both calls pass `d.launchReady`. Update the pins of the old `requested` and of the four-argument calls.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_launch_page.py tests/web/test_app.py`
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 9: The playbook and the documents (spec 11, 13)

**Files:**
- Modify: `playbook/fairband-research/SKILL.md`, `README.md`
- Test: `tests/test_playbook.py`

- [ ] **Step 1: Write the failing tests**, as the file pins the playbook's other sentences. Before `## The steps`, a part headed `## A launch test`: when the request is `launch test`, do no research and write nothing; answer with the one sentence `The Fairband research skill is loaded`, and say whether the Fairband tools are connected, which you can tell from seeing `identify` among your tools; then stop. In step 2: when the request names a work item, as `work item 12`, claim that item with `inbox_claim(12)` where it is pending; where another agent has claimed it, say so and stop, unless the user asks you to take it over.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/test_playbook.py`
- [ ] **Step 3: Write the two parts of the playbook.**
- [ ] **Step 4: The README.** The `claude mcp add` line gains `--scope user`, with one sentence of why: a session opened from the page starts outside this directory. A part `## Opening Claude Code from the page` names `~/.config/fairband/launch.json`, its seven names with their rules in one table, and the example of spec 7.2, written so that a person or an agent can make the file from it.
- [ ] **Step 5: Run the four commands and commit.**

---

### Task 10: The whole-branch review, the acceptance, the live steps and the backlog (spec 15)

The controller's.

- [ ] **Step 1: The whole-branch review and its one fix wave.** The reviewer reads spec 4 and 12 first: no shell, no request text in a command, the owner alone.
- [ ] **Step 2: The acceptance on a scratch server** (spec 15.1), with a scratch data folder and config folder, another port, no key, and a real browser as the memory note on viewing the page says. A window command whose program does not exist is refused at save. With the Windows Terminal line saved and a Claude Code command of `claude-nope`, a real tab opens and the drawer reads "The window opened, but Claude Code did not start: `claude-nope` was not found on the path of a login shell". The Agents section, the menu's checkbox and each line are seen in both themes. A hand-edited `launch.json` shows in Settings at the next read, and a broken one shows its sentence.
- [ ] **Step 3: The founder's word**, with the readout of step 2 and the screenshots.
- [ ] **Step 4: The live steps**, each after the founder's consent: a backup of the database; the merge and the push; the server's restart from main on 8470, which applies migration 009; **Use the Windows Terminal line**, Save, **Test** (spec 15.2); a model, an effort and a mode set and seen in the tab (15.3); one real request for a company the founder names (15.4); the settings hash as before (15.5).
- [ ] **Step 5: The backlog.** B-207 to Done with its commits; new rows for the Inbox page's button, another terminal, and the review's parked items; B-208 stays. Remove the worktree. Tell the founder that a research session already open must restart to read the playbook's two new parts.
