# The Research tab's mockup: sources

The sources of the mockup the founder judged on 2026-11-17 (version 3: version 1, "it looks
good", with the chart corrections of version 2: "I prefer the apple version. Let's just go with
that"), kept as the reference for the look of `../2026-11-17-research-tab-design.md`. They are
throwaway code, not product code: nothing here is imported, tested or shipped, and the build
does not copy from them without thought. No data is in this folder.

| File | What it is |
|---|---|
| `template.html` | The page: the app's header and a company's head for their place, and the Research tab that works: the bar, the section list, the panels with their layout rules and their cards, the three closed parts, and Records |
| `gather.py` | Gathers one company's detail, reports, latest report, research records, financial tables, closes and logo, and the sensitivity readings the report cites, from the running server |
| `build.py` | Puts the gathered answers of one or more companies into the template and writes one self-contained HTML file. With two companies the page shows a switch between them |

To see it:

```
uv run python -I docs/superpowers/specs/2026-11-17-research-tab-mockup/gather.py AAPL <scratch>/data
uv run python -I docs/superpowers/specs/2026-11-17-research-tab-mockup/build.py \
    <scratch>/data docs/superpowers/specs/2026-11-17-research-tab-mockup/template.html \
    <scratch>/research.html AAPL
```

Open the HTML file in a browser. `gather.py` needs the server running on port 8470.

**The gathered files and the HTML hold vendor data and a report on file. Write them outside the
repository, or into a folder git ignores, and never commit them.**

Where the design and these files disagree, the design is right. The design's section 13 lists
the differences it knows of.
