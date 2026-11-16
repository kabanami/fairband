# The research button opens Claude Code: design

Status: written 2026-11-16 for backlog item B-207, on the founder's requests of that day, quoted
in the decision log. The founder decided what it does, that its details live in Settings, that a
failure has a clear message, that it is for Claude Code alone, and that the settings hold the
model, the effort and the permission mode. Every other choice below is Claude's, marked *my call*
where it is more than a reading of those requests, and can be overturned as any other. Not built.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value: the method stays `fairband-mechanical/1.5` and the policy v16. The schema goes from
008 to 009 with one new table and no change to a stored row. The changes are in
`src/fairband/web/`, `src/fairband/store/`, a new `src/fairband/launch/`, the command line and the
playbook.

## 1. What this is

Today the founder clicks **Request research** in a company's drawer or on its report page, and
the page posts a work item to the inbox. Nothing else happens. To start the research the founder
opens a terminal by hand, starts Claude Code, and asks it to take the item.

After this work, the same click also opens a terminal window in which Claude Code starts with the
research skill and the item's id as its first prompt. The skill identifies itself and claims the
item, and the drawer shows the request as claimed. The founder watches the window and answers
its prompts. When the window cannot open, or Claude Code does not start in it, the page says
which of the two failed and why.

## 2. Goals

- One click starts interactive research on one company in Claude Code, with no terminal opened
  by hand.
- Everything the launch needs is in a new **Agents** section of Settings: how to open a window,
  how to start Claude Code, its first prompt, its model, its effort, its permission mode and its
  folder.
- A failure is never silent. The page tells apart three cases, each with its reason: the window
  did not open; the window opened but Claude Code did not start; Claude Code started but no agent
  claimed the request in 90 seconds.
- With the Agents section empty, the button does exactly what it does today.
- The section's values are one small file. The founder, or an agent the founder tells to, can set
  them by writing that file, and the Settings page shows what the file holds.
- Codex can be added later as a second entry of the same section and its first prompt, not as a
  second design (B-208).

## 3. Non-goals

- Codex. It is B-208.
- The Inbox page and the Watchlists page. The Inbox lists items and the Watchlists page posts a
  request for every company of a list; neither opens a window here. (*My call*; a pending item's
  button on the Inbox page is a small follow-up, filed at the end.)
- A run with no window. The session is interactive.
- Another terminal than Windows Terminal over WSL, the founder's machine and the only one
  tested. The window command is a setting, so a terminal that takes its command as trailing words
  and returns at once may work, and nothing here promises it. Two kinds cannot: one that wants
  its command inside a script string, as macOS Terminal does, and one that does not return until
  its window closes, as `xterm -e` does, which the 15 seconds of 6.1 would end.
- A window for an item that an agent has claimed. The playbook says an agent does not take over a
  claimed item unless the user asks.
- Anything after the claim. Once an agent has claimed the item, the page shows what it shows
  today; the launch is not followed further.

## 4. Anti-goals

Each of these would make the work a failure even if the window opens.

- Text from a request reaches a command line. Every word of a command comes from the Agents
  section, from the server's own files, or from a stored item's id.
- An agent's request starts a session, or changes the Agents section, through the server or
  through a Fairband tool. Both routes are the owner's, and no tool does either. (The section's
  file is the founder's own, and an agent the founder directs may write it as it may write any
  file of his: 7.2.)
- A launch setting moves the settings hash, so that every valuation reads as made under other
  settings.
- A failure with no sentence, or a sentence that does not say what to do.
- Two windows for one click.

## 5. The evidence (tests of 2026-11-16 on the founder's machine)

WSL 2.6.1 with Ubuntu, Windows Terminal, Claude Code 2.1.325. Each test started from a detached
process with its input closed, as the server runs. A throwaway skill stood in for the research
skill, so no research started.

| Test | Result |
|---|---|
| The process starts a Windows program | Works with the inherited `WSL_INTEROP`, with none, and with a stale one. |
| It opens a Windows Terminal tab that runs a Linux command | Works. `wt.exe` answers exit 0 after 0.15 s, before the tab's program starts. |
| Claude Code takes a slash command as its first prompt | `claude "/hello-test work item 12"` opened an interactive session, loaded the skill with its arguments and stayed at its prompt. |
| The whole chain, to an interactive Claude Code in a new tab | Works; the skill ran in the tab, on a real terminal (`/dev/pts/4`). |
| An argument with spaces through Windows Terminal | **Fails.** `/fairband-research work item 12` reached the tab as four words, quoted or not. |
| `wsl.exe -- <words>` | **Fails** on a quote: it passes the words through a shell again. `wsl.exe -e <words>` passes them whole. |
| The program a new WSL session finds | Without a login shell `claude` is `/mnt/c/Users/.../npm/claude`, the Windows install. With one it is `~/.local/bin/claude`. |
| `bash -l <script> <three plain words>` behind `wsl.exe -e`, from the server's folder | Works: the words arrive whole, the script needs no exec bit, and `claude` is the login shell's. |
| Claude Code's options, read from `claude --help` | `--model <model>`; `--effort <level>` with `low`, `medium`, `high`, `xhigh`, `max`; `--permission-mode <mode>` with `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`. No session was started with one. |
| Where the Fairband tools are registered, read with `claude mcp get fairband` from another folder | "User config (available in all your projects)", connected. The skill is linked in `~/.claude/skills`. So both load in any folder. |

Three results set the design:

1. **Only plain words cross the window.** A prompt has spaces, so it cannot be a word of the
   window command. A launcher on the Linux side builds it.
2. **The launcher starts as a login shell**, or it starts the wrong `claude`.
3. **The window command's exit code says only that the window command ran.** What happens in the
   window must be reported from inside it.

## 6. How a launch runs

```
page      POST /api/inbox                    the work item, as today
page      POST /api/launches                 {itemId}
server    stores the launch (opening), runs the window command with six words added
window    bash -l <launcher.sh> <python> <port> <launch id>
launcher  GET  /api/launches/{id}/command    the agent's words and its folder
launcher  POST /api/launches/{id}/status     started
launcher  runs Claude Code as its child, in the folder, on the window's terminal
agent     /fairband-research work item 12    identify, then inbox_claim(12)
launcher  POST /api/launches/{id}/status     ended, with the exit code; or failed, with the reason
page      GET  /api/launches/{id}            every 2 s, until claimed, failed or ended, or ten minutes
```

### 6.1 The window command

The Agents section holds one line, the window command: how to open a terminal window that runs
the words added at its end. On the founder's machine it is

```
wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e
```

The server splits the line into words by the shell's rules (`shlex.split`), replaces `{title}`
in each word, and adds six words:

```
bash  -l  <the launcher script's path>  <the server's Python>  <the server's port>  <the launch id>
```

- `{title}` is `Fairband-<SYMBOL>`, the stored item's symbol, or `Fairband-test`.
- The launcher script is a file of the package (6.2). The Python is `sys.executable`. The port is
  the one the server listens on, which `serve` passes to the app.
- The server runs the words as a list of arguments, with no shell, its input closed, its standard
  output discarded and its error output kept in a temporary file, so that it waits for the
  command's exit and not for a pipe to close, in the server's own folder and environment, and
  waits at most 15 seconds.
- **A word that is not plain fails the launch before anything runs.** A plain word is one or more
  of letters, digits and `_ . / : @ + -`. The rule covers the six added words and the title; a
  path with a space cannot cross Windows Terminal, and the failure's sentence names the path.

The window's program may reach the server before the window command has returned. `wt.exe`
returned first in every test, and nothing here rests on that: the launcher's calls are taken
while the launch is `opening` as well as `opened` (section 8).

The launch fails at the window stage when the first word is not a program the server finds, when
the command cannot start, when it ends with another exit code than 0, or when it has not ended
after 15 seconds. The sentence is the reason: "`wt.exe` was not found", "the window command ended
with exit code 1: <the first line it wrote to its error output>", "the window command did not end
in 15 seconds".

### 6.2 The launcher

Two pieces, both on the Linux side.

- **The script**, a packaged file `src/fairband/launch/launcher.sh` of one line and a comment,
  `exec "$1" -P -m fairband launch "$2" "$3"`. The window runs it with `bash -l`, so it has the
  user's login path and needs neither a first line that names a shell nor an exec bit. `-P` keeps
  the window's folder off Python's import path, so a file there cannot stand in for a module the
  launcher imports.
- **The command** `fairband launch <port> <launch id>`, a new subcommand that only the script
  calls. It talks to the server at `127.0.0.1:<port>` and reads nothing from the environment, as
  the MCP server's client does. It reads no key and opens no database: a server on another data
  folder or port is found by the port alone. (*My call*: the launcher asks the server over HTTP
  rather than reading the database, so all the logic is the server's and is tested there.)

What the command does:

1. Reads `GET /api/launches/{id}/command`: the agent's words and its folder.
2. Makes the folder if it is missing, and enters it.
3. Starts the agent as its child on the window's terminal, and reports `started`.
4. Waits for it. While it waits, Ctrl-C belongs to the agent: the launcher does not end on it.
5. Reports `ended` with the agent's exit code.
6. Where that code is not 0, writes "Claude Code ended with exit code <n>.", an empty line and
   "Press Enter to close this window.", and waits for Enter: the agent's own error (a refused
   option, an unknown model) is on the window's screen, and a window that closes takes it away.
   Then it ends.

When a step fails, the command reports `failed` with the reason where it can, writes the same
sentence in the window, and waits for Enter, so the window does not close on the reader. The
reasons: the server did not answer ("no Fairband server answered on port 8470"); the launch is
not one it may run (the server's sentence); the folder cannot be made; the program is not found
("`claude` was not found on the path of a login shell"); the program cannot start.

### 6.3 The agent's words

The server builds them, and the launcher runs them as it gets them:

1. the words of the Claude Code command, split by the shell's rules: `claude`;
2. `--model <model>`, where the model is set;
3. `--effort <effort>`, where the effort is set;
4. `--permission-mode <mode>`, where the mode is set;
5. one last word, the first prompt, with `{item}`, `{symbol}` and `{mode}` replaced by the stored
   item's id, symbol and mode.

For item 12 with every field set: `claude --model claude-opus-5-5 --effort xhigh
--permission-mode auto "/fairband-research work item 12"`. The prompt's spaces are safe here: the
launcher starts the program with a list of arguments, and no shell reads them.

## 7. The Agents section of Settings

### 7.1 The fields

| Field | Name | Default | Rule at save |
|---|---|---|---|
| Window command | `window_command` | empty | Splits into words by the shell's rules. Its first word is a program the server finds. Empty turns launching off. |
| Claude Code command | `claude.command` | `claude` | Splits into words by the shell's rules. At least one word; the first does not start with `-`. |
| First prompt | `claude.prompt` | `/fairband-research work item {item}` | One line of at most 500 characters. Holds `{item}`. No other name in braces than `item`, `symbol` and `mode`. |
| Model | `claude.model` | empty | No white space, no leading `-`, at most 100 characters. Free text, because model names change: `opus`, `claude-opus-5-5`. |
| Effort | `claude.effort` | empty | One of `low`, `medium`, `high`, `xhigh`, `max`. |
| Permission mode | `claude.permission_mode` | empty | One of `acceptEdits`, `auto`, `dontAsk`, `manual`, `plan`. |
| Folder | `claude.folder` | `~/fairband-research` | An absolute path once `~` is the user's home. The launcher makes it. |

- A value that holds a NUL byte, or that is not text the server can send as UTF-8, is refused for
  every name.
- An empty model, effort or mode adds no option, so Claude Code uses its own default.
- The lists of efforts and modes are Claude Code 2.1.325's, kept in one place in the code.
- **`bypassPermissions` is not offered** (*my call*). Claude Code has it; it skips every
  permission check, and a research session reads web pages a stranger wrote. A founder who wants
  it can still add an option to the Claude Code command, and then has typed it on purpose.
- **The folder is not the repository** (*my call*). In the repository a session loads the
  developer's instructions and memory, which are not for research. The skill and the Fairband
  tools are set up for the user, so they load in any folder. Claude Code asks once to trust a new
  folder.
- Launching is **set up** when the window command is not empty.
- The Claude Code command cannot be checked at save: it is found on the path of a login shell in
  the new window, not on the server's. The test (7.4) checks it.

### 7.2 Storage: one file

The values are a file, `launch.json`, in the config folder beside `keys.toml`
(`~/.config/fairband/launch.json`). It is not the `settings` table: every row of that table
overlays the policy and feeds the settings hash each valuation cites, and a launch setting is no
policy value. It is not a table at all (the founder's question of 2026-11-16, in the decision
log): these are one machine's details, and a file is what a person or an agent can read and
write without the server.

```json
{
  "window_command": "wt.exe -w 0 new-tab --title {title} wsl.exe -d Ubuntu -e",
  "claude": {
    "command": "claude",
    "prompt": "/fairband-research work item {item}",
    "model": "claude-opus-5-5",
    "effort": "xhigh",
    "permission_mode": "auto",
    "folder": "~/fairband-research"
  }
}
```

- The names are 7.1's: `window_command`, and under `claude` the six names after the dot. A name
  left out has its default; no file is every default, so launching is off.
- **The server reads the file at each use and keeps no copy**: at the settings read, at a launch,
  and for the detail read's `launchReady`. A change made by hand or by an agent shows at the next
  read, with no restart.
- **Save on the page writes the whole file**, every name in the order above, through a temporary
  file that replaces the old one whole (*my call*: every name is written, defaults too, so a
  reader of the file sees all there is to set).
- **A file the server cannot use turns launching off and says why.** Not JSON, not an object, a
  name it does not know, a value of the wrong kind, or a value that breaks a rule of 7.1: the
  settings read answers the defaults with `fileError`, one sentence that names the file and the
  fault ("launch.json: `claude.effort` is `extreme`; it is one of low, medium, high, xhigh, max").
  The Agents section shows the sentence at its head, with "Correct the file, or save here to
  write it again with the values shown." A launch asked meanwhile is refused with the same
  sentence.
- The rule that the window command's first word is a program the server finds is checked at Save
  and when a launch runs, not at each read: a file written by hand that names a missing program
  fails its launch at the window stage, with the sentence of 6.1.
- There is no change log (*my call*) and no Fairband tool that writes the file. The README names
  the file and its fields, so an agent asked to set it up knows what to write.

### 7.3 The page

The Settings page gains an **Agents** section under the valuation groups, with a save of its own:
the valuation save asks for a reason and warns of a revalue, and neither fits here.

- Each field has one line of help under it. The window command's says what Fairband adds.
- A file the server cannot use (7.2) shows its sentence at the section's head, and under it
  "Correct the file, or save here to write it again with the values shown." The fields then show
  the defaults, and Save writes them, with any change, whole.
- **Use the Windows Terminal line** fills the window command with the line of 6.1 for this
  machine's distribution. The button shows only where the server runs under WSL and finds
  `wt.exe`; the server suggests the line, the page does not build it. Nothing is saved until Save.
- **Save** applies every change or none. A refused save shows the server's sentence beside the
  field it names, as the valuation settings do.
- **Test** is the button of 7.4. It is off while the form holds an unsaved change, since a test
  runs the saved values.

### 7.4 The test

**Test** starts a launch with no work item. Its last word is `/fairband-research launch test`,
and the playbook answers that with one sentence and no research (section 11). The Settings page
follows the launch as section 10 follows one, and shows a line of its own for each state:

| The test's launch | The line |
|---|---|
| `opening` | `Opening a window…` |
| `failed` at the window | `Could not open the window: <reason>.` |
| `opened` | `The window opened, Claude Code is starting…` |
| `opened`, overdue | `The window opened, but nothing in it reported after 90 seconds. Check the window.` |
| `failed` at the agent | `The window opened, but Claude Code did not start: <reason>.` |
| `started` | `Claude Code started. Its window should say that the Fairband research skill is loaded.` |
| `ended`, exit code 0 | `Claude Code ended (exit code 0).` |
| `ended`, another exit code | `Claude Code ended (exit code <n>). Check the window.` |

A test waits for no claim, so it is never overdue once it has started. It is overdue while it is
still `opened` after 90 seconds: a wrong distribution name or a `bash` that fails leaves a window
in which nothing reports, and that is the failure a first setup most often meets. The test is
followed for its first 60 seconds after it starts, so that an agent that ends at once shows; an
end with another exit code than 0 is in the error style, and the window, held by the launcher
(6.2), shows why.

## 8. The launch record

The one new table, `launches`: the launch's id, its item (none for a test), its agent (`claude`),
its state, the stage and the sentence of a failure, the exit code of an agent that ended, and when
it was made and last changed.

| State | Set by | Means |
|---|---|---|
| `opening` | the server, before the window command runs | A launch is in flight. |
| `opened` | the server | The window command ended with exit 0. |
| `started` | the launcher | Claude Code is running in the window. |
| `ended` | the launcher | Claude Code's process ended; the exit code is kept. |
| `failed` | the server (stage `window`) or the launcher (stage `agent`) | The reason is kept as one sentence. |

- The moves are `opening` to `opened`, `started` or `failed`; `opened` to `started` or `failed`;
  `started` to `ended`. Any other is refused. When the window command ends with exit 0 and the
  launcher has already reported, the state stays as the launcher left it.
- A launch is **overdue** when it is `opened` or `started`, its item is still pending, and 90
  seconds have passed since it was made. The server works this out when it is read, on its clock;
  the 90 is one constant in the code. A test has no item: it is overdue while it is `opened`
  after 90 seconds, and never once it has started (7.4).
- **A launch left `opening` by a server that stopped** is marked failed at the window stage when
  the app starts, "the server stopped while the window command ran", as a refresh left running is
  marked interrupted. Otherwise it would hold its item's one launch for ever.
- **One launch in flight for an item.** A new launch for an item is refused while its newest
  launch is `opening`, `opened` or `started` and not overdue. After a failure, an end or an
  overdue launch the owner may open a window again.
- A launch is not written to the ledger (*my call*): the ledger holds the research record, and a
  window that opened is not part of it.

## 9. The routes and the reads

| Route | Who | Answers |
|---|---|---|
| `GET /api/launch-settings` | anyone | Whether launching is set up; each field with its value, default, help and choices; the suggested window command, or none. |
| `PUT /api/launch-settings` | the owner | The form again. A refused save is a 400, "`<name>`: `<rule>`". |
| `POST /api/launches` with `{itemId}` or `{test: true}` | the owner | 201 with the launch, in the state the window command left it: `opened`, or `failed` at the window stage. |
| `GET /api/launches/{id}` | anyone | The launch, with `overdue`, and its item's state and claimant. |
| `GET /api/launches/{id}/command` | the launcher | The agent's words and its folder, while the launch is `opening` or `opened` and its item is pending. |
| `POST /api/launches/{id}/status` | the launcher | The launch after the move. |

- A launch is refused with a sentence, and nothing runs: launching is not set up (400, "launching
  is not set up: see Settings, Agents"); the item does not exist (404); the item is not pending
  (409, "item 12 is claimed by claude-opus-5-5"); a launch is in flight (409, "a window for this
  request opened 20 seconds ago").
- The command read is refused with 409 once the launch has moved on, and once its item is no
  longer pending, "item 12 is claimed by claude-opus-5-5": a second window opened for an item
  that an agent took meanwhile starts no second agent. The launcher shows the sentence (6.2).
- The owner's routes refuse a request that carries the agent's principal header, with 403 and "a
  launch is the owner's" or "the Agents section is the owner's". The launcher sends no principal
  header, so its two calls are the owner's.
- Every route but the three reads changes something, so it needs the `X-Fairband-Request` header
  as every write does (D11). The reads call no vendor and need none.
- The company detail read gains two things: `launchReady`, whether launching is set up; and, on
  its open `item`, `launch`: the item's newest launch as `GET /api/launches/{id}` answers it, or
  none.

## 10. The request button

In the drawer and on the report page, which share `requestResearch` and `RequestMenu`.

**The menu.** Where launching is set up, the menu gains a checkbox **Open Claude Code**, ticked
(*my call*: a way to post a request without a window, for a session that already runs). The
submit posts the item as today and then, where the box is ticked, posts the launch. Where
launching is not set up, the menu is today's.

**The line under the button**, for the open item:

| The item and its newest launch | The line |
|---|---|
| pending, no launch | `Requested · pending`, and a button **Open Claude Code** where launching is set up |
| `opening` | `Requested · opening a window…` |
| `failed` at the window | `Could not open the window: <reason>. Check Settings, Agents.` and **Open again** |
| `opened` | `Requested · the window opened, Claude Code is starting…` |
| `opened`, overdue | `The window opened, but nothing in it reported after 90 seconds. Check the window.` and **Open again** |
| `failed` at the agent | `The window opened, but Claude Code did not start: <reason>. Check Settings, Agents.` and **Open again** |
| `started` | `Requested · Claude Code started, not claimed yet` |
| `started`, overdue | `Claude Code started, but no agent claimed this request after 90 seconds. Check the window.` and **Open again** |
| `ended`, still pending | `Claude Code ended before it claimed this request (exit code 1).` and **Open again** |
| claimed | `Requested · claimed by <the agent>`, as today, whatever the launch |

A failure's line is in the style the request's error line has today. **Open again** and **Open
Claude Code** post a launch for the pending item.

**Following a launch.** While the open item is pending and its newest launch is `opening`,
`opened` or `started`, the page reads `GET /api/launches/{id}` every 2 seconds and draws the line
of the answer. It goes on past overdue, with the overdue line showing: a founder who answers the
window's trust prompt after two minutes still sees the claim arrive. It stops when the item is no
longer pending or the launch is failed or ended, and reads the company again, so the line shows
the claim or the failure. It also stops when the drawer closes or shows another company, and ten
minutes after the launch was made (*my call*, so that a window nobody answers is not asked about
for ever). A page opened later starts following from the detail read's `launch`.

**Open again while a first window lives.** An overdue launch may have a Claude Code that still
waits on a prompt. A second window then gives two sessions for one item. The command read's
refusal (section 9) stops the second where the first has claimed, and the playbook's line
(section 11) stops a session from taking over a claimed item. Where both start while the item is
pending, the founder is at both windows and closes one.

## 11. The playbook

Two additions to `playbook/fairband-research/SKILL.md`, and to its tests.

- **Before the steps:** when the request is `launch test`, do no research, write nothing, and
  answer with one sentence, "The Fairband research skill is loaded", and whether the Fairband
  tools are connected, which the agent can tell from seeing `identify` among its tools. Then
  stop.
- **In step 2:** when the request names a work item, as `work item 12`, claim that item with
  `inbox_claim(12)` where it is pending, reading its state in the list first. Where it is already
  claimed, by any session but this one, say so and stop, unless the user asks you to take it over:
  two sessions may run as one model identifier, so "another agent" would not tell them apart.
  Where it is done, declined, dropped or not in the list, say so and stop: do not claim another
  item in its place. This keeps the step's rule of today, "Do not take over an item that another
  agent has claimed unless the user asks": the server lets a claim by id take an item over, so the
  rule is the playbook's to keep.

## 12. Safety

This is the first route that starts a program on the founder's machine.

- **No shell.** The server and the launcher each start a program from a list of arguments.
- **No text from a request in a command.** A launch request holds an item's id or the word test.
  The window command and the agent's words come from the Agents section, which the owner writes;
  the title and the prompt take a stored item's symbol, mode and id, which the inbox route
  checked when it stored them (a symbol is letters, digits, a dot or a dash; a mode is one of
  two).
- **Through the server, the owner alone** launches and writes the Agents section. No MCP tool
  does either. The check is on the principal header, as the claim route checks that only an agent
  claims.
- **The file is as safe as the founder's other files, and no safer.** Whatever can write
  `~/.config/fairband/launch.json` decides what the button runs: the founder, an agent he tells
  to set it up, and any program that runs as him. Such a program can already run a command as
  him, so the file opens no new door. What it adds is that a change waits there until the next
  click. Two things limit that: the Settings page shows exactly what the file holds, and a
  research session works in its own folder, where Claude Code asks before it writes a file
  outside it unless the founder chose a mode that does not ask.
- **D11 holds.** The server listens on 127.0.0.1, refuses another host name, and wants the
  request header on every write, so a page on another site can neither launch nor change the
  section.
- **Bounded.** One launch in flight for an item; the window command has 15 seconds.

What this does not stop: a program on the founder's own machine that calls the routes without
the agent's header, or writes the file. Such a program can already run any command as the
founder.

## 13. The documents

- `docs/method.md` and the Methodology page do not change: no rule of the engine, the classifier,
  the universe or the policy moves.
- The module docstring of `web/app.py` names the launch routes under D11, as it names the logo's
  read.
- `README.md` gains a short part on `launch.json`: where it is, its names and their rules, with
  the example of 7.2, written so that a person or an agent can make the file from it.
- `README.md` registers the Fairband tools with `claude mcp add fairband` and names no scope,
  which registers them for one folder. The line gains `--scope user`, as the founder's machine
  has it: a launched session runs outside the repository.
- The backlog: B-207's row, written before this design, is rewritten to it and moves to Done;
  B-208 (Codex) stays; a new row holds the Inbox page's button and other terminals.

## 14. Tests the builder must write

Test-first, with no network, no real window and no real agent: the window command's runner and
the launcher's program start are doubles.

- **Settings:** each rule of 7.1 with its sentence; a save applies all or none and writes every
  name, whole, with no temporary file left; no file is every default; a name left out has its
  default; a change to the file shows at the next read, with no restart; each kind of file the
  server cannot use, with its sentence, turns launching off and refuses a launch; a save writes a
  good file over a bad one; nothing here writes the `settings` table or moves the settings hash;
  an agent's write through the server is refused; the suggested line appears only under WSL with
  `wt.exe` found.
- **The window command:** the words run are the setting's words, the title replaced, and the six
  added words, in that order; no shell; a word that is not plain fails the launch and runs
  nothing; each failure of 6.1 with its sentence; exit 0 leaves `opened`.
- **The agent's words:** every combination of an empty and a set model, effort and mode; the
  prompt is one word with its three names replaced; a test's last word.
- **The launch record:** each allowed move and each refused one, a report that arrives while the
  launch is `opening` among the allowed; overdue at 90 seconds and not at 89, never once the item
  is claimed; a test overdue while `opened` and never once started; a launch left `opening` is
  failed when the app starts; one launch in flight, and a second allowed after a failure, an end
  or an overdue launch.
- **The routes:** each refusal of section 9 with its status and sentence, the command read's for
  an item that is no longer pending among them; an agent's principal is
  refused; a write without the request header is a 403; the detail read's `launchReady` and
  `item.launch`.
- **The launcher:** the order of its steps; the folder made; `started` reported after the program
  starts, `ended` with the exit code; each failure reported, written and held until Enter; no key
  and no database read.
- **The page:** each line of section 10 from its item and launch; the menu with and without the
  checkbox; following goes on past overdue and stops on each stop condition; the Agents section's
  fields, save, refusal beside its field, the test's lines of 7.4, and the test button off with
  an unsaved change.
- **The playbook:** its two additions, the claimed item's case among them.

## 15. Acceptance

Each step on the live server needs the founder's consent first: a backup of the database, then
the restart that applies migration 009.

1. On a scratch server and data folder: a window command whose program does not exist is refused
   at save; a Claude Code command of `claude-nope` gives, in the drawer, "The window opened, but
   Claude Code did not start: `claude-nope` was not found on the path of a login shell".
2. On the live server: **Use the Windows Terminal line**, Save, **Test**. A tab opens, and Claude
   Code says the skill is loaded and the tools are connected.
3. With a model, an effort and a mode set: the tab's Claude Code shows that model and effort.
4. One real request, for a company the founder wants researched: the tab opens, the drawer goes
   from the window opened to claimed inside 90 seconds, and the research runs as it does today.
5. Every valuation's settings hash is what it was before the Agents section was saved.

## 16. Left to the builder

The names of the new modules and of the tables' columns; the JSON of the settings form; how the
page keeps its timer; the help line under each field; where in the menu the checkbox sits; how
the launcher leaves Ctrl-C to the agent; whether the two launcher routes share a module with the
launch route.

## 17. Order of work

1. The `launches` table, migration 009 and its store.
2. The launch settings: the file, the rules, the routes, the suggested line.
3. The launch: the record, the window command, `POST /api/launches`, the read.
4. The launcher: the script, the `launch` subcommand, its two routes.
5. The detail read's `launchReady` and `item.launch`.
6. The Agents section of the Settings page, with the test.
7. The request menu, the line under the button, and following a launch.
8. The playbook's two additions.
9. The documents, then the live steps of section 15.

## Decision log

- 2026-11-16, the founder: "when the user clicks the research button for at ticker, that a claude
  code or codex interactive window is opened and the fairband research skill is loaded by the
  agent."
- 2026-11-16, the founder: "the user enters the necessary details in settings, so all the info we
  need to open an interctive window either in codex or claude code should be there, and a clear
  failure message if the settings has values but the load failed."
- 2026-11-16, the founder, after the launch tests of section 5: "let's just do this for claude
  code, but make sure that codex in the back log so we don't forget it." Codex is B-208.
- 2026-11-16, the founder, on the model, the effort and the permission mode as settings: "ok add
  all three fields and write the spec."
- 2026-11-16, Claude's calls, each marked in its section: the launcher asks the server over HTTP
  (6.2); `bypassPermissions` is not offered and the folder is not the repository (7.1); no change
  log for a launch setting, and a save writes every name (7.2); a launch is not in the ledger (8);
  the Inbox and Watchlists pages are left out (3); the menu's checkbox (10). And unmarked, as
  readings of "a clear failure message": the launch record that the launcher reports to, the 90
  seconds, and the test button.
- 2026-11-16, the builder check (a fresh reader asked to plan from this document). Its four
  questions were settled without the founder, each a reading of "a failure is never silent" or a
  fact: a test is overdue while nothing in its window has reported (7.4, 8); a launched session does
  not take over a claimed item, and the command read refuses once the item is not pending (9, 11);
  only Windows Terminal is promised (3), and the launcher's calls are taken while the window command
  still runs (6.1, 8); Claude Code's options and the user scope of the Fairband tools were read on
  the machine (5). Its three contradictions were corrected: a launch left `opening` (8), the test's
  own lines (7.4), and B-207's row (13).
- 2026-11-16, the founder, on reading this design: "should we provide a way for the user's own agent
  to update these values so that the user does not have to do it manually via the settings? so is
  there something like a settings.json that an agent can update and it would show in the settings?"
  Yes: the section's values are the file `launch.json` and nothing else (7.2), in place of the table
  this design first gave them. The server's two owner-only routes stay, and section 12 says what the
  file does and does not change about safety.
