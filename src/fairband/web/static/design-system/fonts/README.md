# Fonts

IBM Plex Sans and IBM Plex Mono, vendored so Fairband renders identically with no network
and so no request leaves the machine on a page load.

| | |
| --- | --- |
| Families | IBM Plex Sans, IBM Plex Mono |
| Weights | 400, 500, 600 — the three the type scale uses |
| Subset | latin |
| Format | woff2 |
| Copyright | Copyright 2019 IBM Corp. All rights reserved. |
| Licence | SIL Open Font License, Version 1.1 |
| Packaged by | `@fontsource/ibm-plex-sans` 5.3.0, `@fontsource/ibm-plex-mono` 5.2.6 |

The full licence text sits beside the files, one per family, because each carries its own
copyright line:

- [LICENSE-IBMPlexSans.txt](LICENSE-IBMPlexSans.txt)
- [LICENSE-IBMPlexMono.txt](LICENSE-IBMPlexMono.txt)

## What the OFL asks of you

Keeping these files in the repo and shipping them inside Fairband is exactly what the
licence is for, including commercially. Three conditions are worth knowing, none of them
onerous:

**The licence travels with the fonts.** Wherever the `.woff2` files go — a build output, a
container image, a packaged release — the two licence files and the copyright notice go
too. Don't let a build step strip this folder down to the binaries.

**The fonts are not sold on their own.** They can be bundled and sold as part of Fairband;
they cannot be sold as a font package.

**A modified font gets a new name.** If anyone ever subsets, hints or otherwise edits these
files, the result must not be called IBM Plex. Reserved Font Names are the one thing the
OFL is strict about. Regenerating from the same upstream packages is not a modification.

Nothing here constrains Fairband's own licence: the OFL covers the font files, not the
software that displays them, and it does not reach your code.

## Other weights and subsets

The upstream packages carry italics, the full weight range (100–700) and the greek,
cyrillic and vietnamese subsets. If the type scale grows, take them from the same two
packages at the same versions rather than a different source, so the licence provenance
stays a single line.
