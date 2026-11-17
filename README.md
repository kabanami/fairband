# Fairband

Fairband is a local valuation screen for a value investor: one page on your own machine
with one row per company, carrying a mechanical value, the levels around it and where the price
stands against the value.

Install: `uv sync` (needs Python 3.13 or later).

Keys: put `fmp` and `gurufocus` under `[keys]` in `~/.config/fairband/keys.toml`; never commit it.

Run: `uv run fairband serve` (or `uv run python -m fairband serve`), then open
http://127.0.0.1:8470.

The page has five views: Screen, Groups, Watchlists, Methodology and Settings.

## Agents over MCP

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
history and peers, the research on file, the policy and the Methodology page). Ten are vendor reads
the server fetches with its own key and stores so a report can cite them: `transcript`, `news`,
`segments`, `insider_trades`, `transcript_dates` and `dcf` from FMP, the filing reads `filings`,
`filing_report` and `filing_search` from FMP, and `pe_history` from GuruFocus, which needs the
`gurufocus` key. Nineteen write: the identity, the work inbox, notes, findings, guidance records,
overrides, the secondary valuation, the sensitivity reading, derivations, reports, kill criteria,
news items and refreshes. The newest are `quarters`, `filings`, `filing_report` and
`filing_search`; `secondary_valuation` now takes the standard discounted cash flow's `drivers`
beside its `parts`.

The playbook: `playbook/fairband-research/` is a skill that takes the agent through a research
report, step by step, starting with `identify`. For Claude Code and Claude Desktop, link it under
`~/.claude/skills/`:

```
ln -s <repo>/playbook/fairband-research ~/.claude/skills/fairband-research
```

For Codex, add a line to `AGENTS.md` that tells the agent to follow
`<repo>/playbook/fairband-research/SKILL.md`.

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
