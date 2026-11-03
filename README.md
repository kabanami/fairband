# Fairband

Fairband is a local valuation screen for a value investor: one page on your own machine
with one row per company, carrying a mechanical value, the levels around it and where the price
stands against the value.

Install: `uv sync` (needs Python 3.13 or later).

Keys: put `fmp` and `gurufocus` under `[keys]` in `~/.config/fairband/keys.toml`; never commit it.

Run: `uv run python -m fairband serve`, then open http://127.0.0.1:8470.
