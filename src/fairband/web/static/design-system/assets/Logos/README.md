The mark and the cover, as flat files for everywhere outside the running app.

Inside the app, use `Fairband.Mark` from `components/bundle.js` instead. It is the same drawing in SVG that reads the tokens, so it follows the theme; these files have the values baked in and cannot.

## The mark

Three unequal bands crossed by a price marker — the cover's picture, cut to the fewest parts that still read at 24px.

| File | Ink | Where |
| --- | --- | --- |
| `mark-on-dark.svg` | `phase-1` / `accent` / `caution`, marker in `ink`, dark values | Anything on `#121417` or another dark ground |
| `mark-on-light.svg` | the same three, light values | Anything on `#fbfcfd` or white |
| `mark-one-ink-on-dark.svg` | one ink, `#e8eaed` at 45% / 80% / 100% | A dark ground that cannot take three colours |
| `mark-one-ink-on-light.svg` | one ink, `#11161b` at 45% / 80% / 100% | Print, a monochrome favicon mask, a stamp |

None of them use `currentColor`, because an SVG loaded through `<img>` never inherits it. Pick the file that matches the ground.

**Clear space** is a quarter of the mark's width on all four sides — 6px at 24px, 8px at 32px. Nothing enters it, including the wordmark.

**Minimum size** is 16px. The three bands fuse below about 20px and it reads as stripes with a pin rather than three bands; that is the intended behaviour at favicon size, not a defect. Do not redraw a simplified version for small sizes — one drawing, or the favicon and the header stop being the same thing.

**The lockup** is the mark at 24px, `space-2` of air, then *Fairband* in `sans` 600 at 16px in `ink`, baselines centred. At display sizes the ratio holds: the wordmark is two-thirds of the mark's height. There is no lockup file, because the wordmark is live type — set it, do not place an image of it.

Do not rotate, outline, add a gradient, put the mark in a circle, or reorder the bands. Do not reconstruct it from the component's markup for a new size; scale one of these files.

## The cover

| File | Where |
| --- | --- |
| `cover-on-dark.png` | 1920×576 (960×288 at 2×) |
| `cover-on-light.png` | the same, light ground |

The cover is a first-impression object: the repository README, the docs landing page, the social card, a splash on first launch. It is not chrome — at 288px above the screen it costs five rows out of ten in a 520px window, which is the opposite of what the system asks for. The application header is `AppHeader`, and it is 44px.

PNG rather than SVG because the wordmark is live type in the source and a placed SVG would fall back to whatever face the reader has. The source is `components/Cover/preview.html`; re-render it rather than editing these.
