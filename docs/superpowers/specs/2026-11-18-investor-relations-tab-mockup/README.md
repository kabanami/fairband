# The Investor relations tab's mockup: sources

The sources of the mockup the founder judged on 2026-11-18 (version 1: "It looks good"), kept as
the reference for the look of `../2026-11-18-investor-relations-tab-design.md`. They are
throwaway code, not product code: nothing here is imported, tested or shipped, and the build
does not copy from them without thought. No data is in this folder.

| File | What it is |
|---|---|
| `template.html` | The page: the app's header and a company's head for their place, and the tab that works: the switch, the list of calls, the reader with its figures, its find box and its jump to the questions, and the filings with their filters |
| `build.py` | Reads one company's stored call dates, newest stored transcript, earnings rows and filing list from the live store, read-only, and the head's facts from the running server, and writes one self-contained HTML file |

To see it:

```
uv run python -I docs/superpowers/specs/2026-11-18-investor-relations-tab-mockup/build.py AAPL \
    docs/superpowers/specs/2026-11-18-investor-relations-tab-mockup/template.html \
    <scratch>/investor-relations.html
```

Open the HTML file in a browser. `build.py` needs the server running on port 8470 and a store
that holds the company's call dates, a transcript and a filing list, which a research session on
the company leaves there.

**The HTML holds vendor data, a part of an earnings call among it. Write it outside the
repository, or into a folder git ignores, and never commit it.**

Where the design and these files disagree, the design is right. The design's section 13 lists
the differences it knows of.
