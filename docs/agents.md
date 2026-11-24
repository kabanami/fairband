# Agents

Fairband is currently designed for Claude Code, with Codex coming soon. An agent works on Fairband
through one MCP server and one playbook, and the page can open Claude Code on a piece of research
for you. This document holds the setup of each.

The server is a plain MCP server over stdio, so it registers with other MCP hosts in the same
way; the registration for Claude Desktop and for Codex is below beside Claude Code's. The playbook
and the page's launch are built around Claude Code today.

## The MCP server

An agent reads and writes Fairband through `fairband mcp`, a stdio server that the agent's host
starts. It calls the web server on 127.0.0.1 and holds no database and no key, so the screen must
be running: `uv run fairband serve`. When it is not, every tool answers one sentence: "the
Fairband server is not running: start `uv run fairband serve`". If the server runs on a port
other than 8470, add `--port <port>` after `mcp`.

Register the server with the host; `<repo>` is the absolute path of this directory. If the host
cannot find `uv`, give its absolute path (`which uv`) as the command.

- Claude Code:

  ```
  claude mcp add --scope user fairband -- uv run --directory <repo> fairband mcp
  ```

  `--scope user` makes the tools known in every directory: a session that the page opens (below)
  starts outside this one, and a server added without a scope is known in one directory only.

- Claude Desktop, in `claude_desktop_config.json`:

  ```json
  {
    "mcpServers": {
      "fairband": {
        "command": "uv",
        "args": ["run", "--directory", "<repo>", "fairband", "mcp"]
      }
    }
  }
  ```

- Codex, in `~/.codex/config.toml`:

  ```toml
  [mcp_servers.fairband]
  command = "uv"
  args = ["run", "--directory", "<repo>", "fairband", "mcp"]
  ```

Identity: the agent's first call is `identify`, with the model identifier it runs as, such as
`claude-opus-5-5` or `gpt-5`. Fairband records every write under that name, with the host's name
and version from the MCP handshake. A write before `identify` is refused.

The tools: 55, listed with their arguments in
`playbook/fairband-research/reference/tools.md`. Twenty-six read the store (the screen, a
company's snapshot, its statements, its stored quarters, tables, consensus, closes, multiples
history and peers, the research on file, the policy and the Methodology page). Nine are vendor
reads the server fetches with its own key and stores so a report can cite them: `transcript`,
`news`, `segments`, `insider_trades`, `transcript_dates` and `dcf` from FMP, and the filing reads
`filings`, `filing_report` and `filing_search` from FMP. A refresh
stores some of their answers for each company under the keys the tools read: its segments, its
news at 60 stories, its list of earnings calls, its filings of the 365 days to the refresh's day,
and its newest call's transcript where the store holds no copy of it with words. So `segments`,
`news` at a `limit` of 60, `transcript_dates`, `filings`
with its default window on the day of the refresh, and `transcript` of that call may answer
from the refresh's copy within the reuse window, with `reused` true. FMP's error object in
place of the list of calls is answered as it came, stored as an error and never reused, so the
next call asks FMP again. Twenty write: the identity, the work inbox, notes, findings,
guidance records, the moat class, overrides, the secondary valuation, the sensitivity reading,
derivations, reports, kill criteria, news items and refreshes. The newest is `moat_set`, the
agent's verdict on the company's moat class, which every review records; before it came
`quarters`, `filings`, `filing_report` and `filing_search`, and `secondary_valuation` took the
standard discounted cash flow's `drivers` beside its `parts`.

The playbook: `playbook/fairband-research/` is a skill that takes the agent through a research
report, step by step, starting with `identify`. For Claude Code and Claude Desktop, link it under
`~/.claude/skills/`:

```
ln -s <repo>/playbook/fairband-research ~/.claude/skills/fairband-research
```

For Codex, add a line to `AGENTS.md` that tells the agent to follow
`<repo>/playbook/fairband-research/SKILL.md`.

## Claude Code on Windows

The steps above are for a Claude Code that runs on the same system as Fairband: Linux, or Linux
under WSL. A Claude Code that runs on Windows itself (`claude` in PowerShell or `cmd`) works with
Fairband in two ways. Both were tested with Claude Code 2.1.178: the playbook's `launch test` and
calls of the tools, with the playbook in a project's `.claude\skills` folder.

**Fairband in WSL, Claude Code on Windows.** Windows starts the MCP server through `wsl.exe`,
which reads no profile, so give `uv` by its absolute path in WSL (`which uv`). `<repo>` is the
path in WSL, and `Ubuntu` is the distribution's name:

```
claude mcp add --scope user fairband -- wsl.exe -d Ubuntu -e /home/<you>/.local/bin/uv run --directory <repo> fairband mcp
```

Copy the playbook to the Windows side, from a shell in WSL. The copy does not follow the
repository, so copy it again after an update of Fairband:

```
mkdir -p /mnt/c/Users/<you>/.claude/skills
cp -rL <repo>/playbook/fairband-research /mnt/c/Users/<you>/.claude/skills/
```

**Fairband on Windows.** `uv run fairband serve` runs on Windows as it does on Linux, and the
registration is Claude Code's line above with the Windows path of `<repo>`. Link the playbook with
a junction, in `cmd`:

```
mklink /J %USERPROFILE%\.claude\skills\fairband-research <repo>\playbook\fairband-research
```

The keys file and the data are under the user's folder there:
`%USERPROFILE%\.config\fairband\keys.toml` and `%USERPROFILE%\.local\share\fairband`. Three limits
hold on Windows itself. The page's button does not open a window (below): the launch runs
through `bash`, and Fairband refuses the launcher's Windows path. At a start the log says that
other users can read `keys.toml`: the check reads Linux file modes, which Windows does not keep.
And a refresh with an FMP key was not run there; the server, the page and the tools were.

## Opening Claude Code from the page

Once `launch.json` holds a window command, **Request research** in a company's drawer or on its
company page also opens a terminal window, in which Claude Code starts with
the research skill and the work item as its first prompt, `/fairband-research work item 12`. The
agent claims the item, and the line under the button follows the launch until it does, or says
what failed: the window, or Claude Code in it. The menu's box **Open Claude Code**, cleared, posts
the request without a window. Without a window command the button only posts the work item. A
pending item's row on the Inbox page has **Open Claude Code** too, for an item that no click made:
the review Fairband posts when a watched company's window ends, or an item an agent posted.

The file is `~/.config/fairband/launch.json`, beside `keys.toml`. The Agents section of the
Settings page shows what it holds and writes it on Save; its **Test** opens a window in which
Claude Code says that the skill is loaded and whether the Fairband tools are connected. A person or
an agent may also write the file by hand (no Fairband tool writes it): the server reads it at each
use, so a change shows with no restart. For Windows Terminal over WSL, with the distribution
`Ubuntu`:

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

`window_command` stands at the top, and the six names after `claude.` stand under `claude`. Every
value is a string.

| Name | What it sets | Default | Rule |
|---|---|---|---|
| `window_command` | How to open a terminal window | empty | Splits into words by the shell's rules. Its first word is a program the server finds. Empty turns launching off. |
| `claude.command` | The program that starts Claude Code, found on the path of a login shell | `claude` | Splits into words by the shell's rules. At least one word; the first does not start with `-`. |
| `claude.prompt` | The session's first message; `{item}`, `{symbol}` and `{mode}` are the request's | `/fairband-research work item {item}` | One line of at most 500 characters. Holds `{item}`. No other name in braces than `item`, `symbol` and `mode`. |
| `claude.model` | Claude Code's `--model` | empty | No white space, no leading `-`, at most 100 characters. Free text, because model names change: an alias (`fable`, `opus`, `sonnet`), which means the newest model of its family, or a full name such as `claude-opus-5-5`. |
| `claude.effort` | Claude Code's `--effort` | empty | One of `low`, `medium`, `high`, `xhigh`, `max`. |
| `claude.permission_mode` | Claude Code's `--permission-mode` | empty | One of `acceptEdits`, `auto`, `bypassPermissions`, `dontAsk`, `manual`, `plan`. `bypassPermissions` skips every permission check. |
| `claude.folder` | Where the session starts | `~/fairband-research` | An absolute path once `~` is the user's home. The launcher makes it. |

An empty model, effort or permission mode adds no option, so Claude Code uses its own default. A
name left out has its default, and no file is every default, so launching is off. A file the server
cannot use (not JSON, not an object, a name it does not know, a value that is not a string, or one
that breaks its rule) turns launching off too: the Agents section says why at its head, and a save
there writes the file again. The server looks for the window command's program at Save and at each
launch, so a missing program in a file written by hand shows when a launch runs: the page says it
could not open the window.

The window command opens a window that runs the words Fairband adds at its end: `bash -l`, the
launcher's path, the server's Python, its port and the launch's id. Each must be a plain word, of
letters, digits and `_ . / : @ + -`, so a path with a space fails the launch. `{title}` in the
command becomes `Fairband-<symbol>`, or `Fairband-test`. Only Windows Terminal over WSL is tested;
another terminal may work where it takes its command as words at its end and returns at once.

The session starts in the folder, not in this directory, so it loads neither this repository's
instructions nor its memory; the skill and the Fairband tools load there because they are set up
for the user, as above. Claude Code asks once to trust a new folder.
