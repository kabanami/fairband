# The refresh experience's look: sources

The sources of the look in a browser of `../2026-11-23-refresh-experience-design.md` (its section
5), taken on 2026-11-24 as the last task of its plan. They are throwaway code, not product code:
nothing here is imported, tested or shipped. No data is in this folder.

The look ran on the real page, the branch's server on a scratch database of the whole universe.
No refresh ran: the script answers the page's reads of the refresh's state and its start, and
changes the rows the server sends after a simulated run, so the page has something to mark. The
meters ran on a page the script serves, which mounts the bundle's `BandMeter` on invented
figures.

| File | What it is |
|---|---|
| `make_scratch.py` | Makes a scratch database: the migrations, then, from the live store opened read-only, the small tables whole, every row of the newest universe refresh's companies, the newest snapshot of each company and the snapshots its reviews, reports and secondary valuations rest on (about 60 MB) |
| `look.mjs` | Opens the cached Chromium through `playwright-core` from the npx cache, its scrollbars shown, and checks each state the design names in both themes, at 1,600 by 600px, at 375px for the layer and the company page's head, and under the reduced-motion setting for the fades. It prints ok or FAIL for each check, exits 1 on a FAIL, and saves a screenshot of each state |

What `look.mjs` checks:

- A price run: the layer up, titled, with no Keep reading, the panel holding the focus with no
  ring, everything under it inert; a press on the menu, Escape and a hash typed change no view.
  At the end the changed cells hold the tint, the changed prices their arrows and the line its
  count; 3 seconds on no tint and no arrow is left; no column head, cell or row moves as the
  arrows come and go. With and without reduced motion, in both themes.
- A full run: Keep reading lifts the layer, the bar stays in the status line with Cancel in the
  header, the tables fade, the menu answers; the end counts the prices and the values.
- A revalue of one named company: no layer, no fade, nothing inert; that row's cells tinted and
  no count.
- Statistics: for each grouping, a group's name opens the Screen, which counts the group's
  Companies; the links at rest, under the pointer and faded while a grouping loads.
- The layer at 1,600 and 375px: the panel inside 16px gutters, its fade out with the scrim, a
  second lock.
- The Methodology view, scrolled, under the layer: the wheel and the keys scroll nothing.
- The company page's head: the arrow before the price, which does not move as it comes and goes,
  wide and narrow.
- The tint beside the approved mockup's grey, one picture for each theme, when the mockup's path
  is given.
- The meters: prices at 0.20 to 2.76 times values of 9.99, 61.77 and 1,587.00, at 256 and 380px.
  By their rectangles, the two labels apart, neither on the price marker's dot, nothing outside
  the meter, no NaN.

To see it:

```
uv run python -I docs/superpowers/specs/2026-11-23-refresh-experience-mockup/make_scratch.py <scratch>/data
env -u FAIRBAND_FMP_KEY FAIRBAND_DATA_DIR=<scratch>/data XDG_CONFIG_HOME=<scratch>/config \
    uv run python -m fairband serve --port 8499
node docs/superpowers/specs/2026-11-23-refresh-experience-mockup/look.mjs <scratch>/shots \
    [.superpowers/brainstorm/2553069-1795455894/content/refresh-and-meter-v3.html]
lsof -ti:8499 -sTCP:LISTEN | xargs -r kill
```

Never start a second server on the live data: use the scratch folder. The harness refuses
`XDG_CONFIG_HOME` on a command line, so set it in a small start script. `LOOK_ONLY` runs some
parts alone (`LOOK_ONLY=price,company`); `LOOK_CSS` adds a rule to every page, to try a
correction in the browser before it is written. The mockup is under the main checkout's
`.superpowers/`, not committed: it shows real prices.

**The screenshots hold vendor data: companies' prices, values and names. Write them outside
the repository and never commit them.**

The first run found two faults, each corrected test-first in the task that owns it. The arrow
before a changed price widened the price's column by its glyph and its gap, so every column of the
Screen moved about 11px as the arrows came and again as they went, and on a narrow window it moved
the company page's price by 10px: it is now a box of no width and no height (Task 6). A price at
an end of the scale stood on the track's end, its dot 6.5px off the meter: a marker inside the
scale now never stands nearer an end than the 7px a pinned one takes (Task 2). An arrow taken
out of the flow by absolute position was tried first and set aside: the arrows of rows far down
the table stretched the document and drew a scrollbar beside it.

Where the design and these files disagree, the design is right.
