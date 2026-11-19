# The GuruFocus removal's look: sources

The sources of the look the founder approved on 2026-11-19 with
`../2026-11-19-gurufocus-removal-design.md` (its section 9): the warnings mark beside a
mechanical value, and the moat control on the company page. They are throwaway code, not product
code: nothing here is imported, tested or shipped. No data is in this folder.

The look was not drawn on a mock page. The real pages ran on a scratch database, and a script
changed the page in the browser before each screenshot.

| File | What it is |
|---|---|
| `make_scratch.py` | Makes a scratch database: the migrations, then, from the live store opened read-only, the small tables whole and 22 companies' newest universe row, snapshot and profile |
| `pw.mjs` | Opens the cached Chromium through `playwright-core` from the npx cache, in a light or a dark theme |
| `dots.mjs` | On the screen, puts the mark before the mechanical value of six rows, in the forms compared, and takes a screenshot of each form in both themes |
| `moat.mjs` | On a company page, draws the six states of the moat control after the stamp and takes a screenshot of each in both themes |

To see it:

```
uv run python -I docs/superpowers/specs/2026-11-19-gurufocus-removal-mockup/make_scratch.py <scratch>/data
env -u FAIRBAND_FMP_KEY -u FAIRBAND_GURUFOCUS_KEY FAIRBAND_DATA_DIR=<scratch>/data \
    XDG_CONFIG_HOME=<scratch>/config uv run python -m fairband serve --port 8499
node docs/superpowers/specs/2026-11-19-gurufocus-removal-mockup/dots.mjs <scratch>/shots
node docs/superpowers/specs/2026-11-19-gurufocus-removal-mockup/moat.mjs <scratch>/shots
lsof -ti:8499 -sTCP:LISTEN | xargs -r kill
```

Never start a second server on the live data: use the scratch folder. `pw.mjs` names the
folder of the npx cache on the machine it was written on; change it to yours.

**The screenshots hold vendor data: companies' prices, values and descriptions. Write them
outside the repository and never commit them.** The sheets the founder saw are in
`~/.local/share/fairband/research/gurufocus-removal-2026-11-19/look/`.

Four forms of the mark were drawn: the bullet of IBM Plex Mono at the cell's size (too small
to see), a round glyph that the vendored font does not hold (a system font draws it), a drawn
circle, and a drawn square. The enlarged bullet, form A in `dots.mjs`, was taken: it reads as
the drawn circle does and comes from the page's own font. `dots.mjs` holds forms A and C.

Where the design and these files disagree, the design is right.
