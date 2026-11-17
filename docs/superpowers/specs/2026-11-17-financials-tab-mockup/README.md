# The Financials tab's mockup: sources

The sources of the mockup the founder judged on 2026-11-17 (version 3: "its right, proceed"),
kept as the reference for the look of `../2026-11-17-financials-tab-design.md`. They are
throwaway code, not product code: nothing here is imported, tested or shipped, and the build
does not copy from them without thought. No data is in this folder.

| File | What it is |
|---|---|
| `template.html` | The page: the app's header and a company's head for their place, and the Financials tab that works: the five sub-tabs, Millions and Billions, Annual and Quarterly, the chart of up to four lines, the table |
| `gather_fin.py` | Gathers one company's stored statements and segments, FMP's ratios and key metrics by fiscal year, its detail and its logo into a JSON file |
| `build_fin.py` | Shapes the gathered data into the page's tables and writes one self-contained HTML file. It holds the lists of each table's lines: FMP's field, the line's name, its kind |

To see it:

```
uv run python docs/superpowers/specs/2026-11-17-financials-tab-mockup/gather_fin.py \
    AAPL ~/.local/share/fairband/fairband.db <scratch>/aapl.json
uv run python -I docs/superpowers/specs/2026-11-17-financials-tab-mockup/build_fin.py \
    <scratch>/aapl.json docs/superpowers/specs/2026-11-17-financials-tab-mockup/template.html \
    <scratch>/financials.html
```

Open the HTML file in a browser. `gather_fin.py` needs the FMP key of `keys.toml` and the server
running on port 8470; it prints no key.

**The JSON and the HTML hold vendor data. Write them outside the repository, or into a folder
git ignores, and never commit them.**

Where the design and these files disagree, the design is right. The design's section 13 lists
the differences it knows of.
