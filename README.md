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
  claude mcp add fairband -- uv run --directory <repo> fairband mcp
  ```

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

The playbook: `playbook/fairband-research/` is a skill that takes the agent through a research
report, step by step, starting with `identify`. For Claude Code and Claude Desktop, link it under
`~/.claude/skills/`:

```
ln -s <repo>/playbook/fairband-research ~/.claude/skills/fairband-research
```

For Codex, add a line to `AGENTS.md` that tells the agent to follow
`<repo>/playbook/fairband-research/SKILL.md`.
