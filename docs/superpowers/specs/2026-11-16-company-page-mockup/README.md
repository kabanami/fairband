# The company page's mockups: sources

The sources of the mockups the founder judged on 2026-11-16, kept as the reference for the look
of `../2026-11-16-company-page-design.md`. They are throwaway code, not product code: nothing
here is imported, tested or shipped, and the build does not copy from them without thought.
No data is in this folder.

| File | What it is |
|---|---|
| `overview.js`, `overview.css` | The page's head, its tabs, the Overview tab as the founder approved it (version 3: the two columns end on one line) and the Estimates tab |
| `drawer.js`, `drawer.css` | The drawer in three forms. The founder picked form A |
| `gather.py` | Gathers one company's data into a JSON file |
| `build_mock.py` | Makes one self-contained HTML file from a page's two files and the data |

To see one:

```
uv run python docs/superpowers/specs/2026-11-16-company-page-mockup/gather.py \
    AAPL ~/.local/share/fairband/fairband.db <scratch>/aapl.json
uv run python -I docs/superpowers/specs/2026-11-16-company-page-mockup/build_mock.py \
    src/fairband/web/static <scratch>/aapl.json \
    docs/superpowers/specs/2026-11-16-company-page-mockup/overview.css \
    docs/superpowers/specs/2026-11-16-company-page-mockup/overview.js <scratch>/overview.html
```

Open the HTML file in a browser. `gather.py` needs the FMP key of `keys.toml` and the server
running on port 8470; it prints no key.

**The JSON and the HTML hold vendor data. Write them outside the repository, or into a folder
git ignores, and never commit them.**

Where the design and these files disagree, the design is right. The mockup reads FMP's fields in
the page and does the yearly rate there; the build shapes the figures in the server's reads
(design 10.3 and 14.3). The mockup shows five tabs' names; the design's 7.3 rules which
of them plan 1 shows.
