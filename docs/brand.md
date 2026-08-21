# Brand

[← README](../README.md)

The mark is a moth. In September 1947 the team running the Harvard Mark II pulled one out of a
relay and taped it into the logbook as the *"first actual case of bug being found"*. A tool that
hunts bugs takes the bug as its mark, and the eyespots on the forewings double as the eyes doing
the reviewing.

![Every variant, on light and on dark grounds](./images/logo/brand-sheet.svg)

## Files

| File | Where it goes |
| --- | --- |
| [`logo.svg`](./images/logo/logo.svg) | The mark, on light grounds |
| [`logo-dark.svg`](./images/logo/logo-dark.svg) | The mark, on dark grounds — the darkest tone is lifted so the body does not sink into the page |
| [`logo-lockup.svg`](./images/logo/logo-lockup.svg) | Mark plus wordmark, horizontal. This is what the README headers use |
| [`logo-lockup-dark.svg`](./images/logo/logo-lockup-dark.svg) | The same lockup, on dark grounds |
| [`favicon.svg`](./images/logo/favicon.svg) | Anything small — a separate, reduced drawing |
| [`brand-sheet.svg`](./images/logo/brand-sheet.svg) | The sheet above |

## Rules

- Flat polygons only: no gradients, no strokes, no glow, no rounded corners.
- Four tones of one hue, the ones printed on the sheet. Nothing else joins the palette.
- Below roughly 24px use `favicon.svg`, never a scaled-down `logo.svg` — the small facets turn to
  mud. That reduced drawing keeps the antennae even though they almost vanish, because without them
  the wings read as an anonymous pair of blobs.
- Leave clear space around the mark of at least one wing's width.
- The mark carries its own colour. Do not place it on a coloured field, and do not recolour it to
  match one.

## Regenerating

Every file in `images/logo/` is written by one script from one geometry definition:

```sh
python3 docs/images/logo/build-moth-assets.py
```

Edit the coordinates in that script rather than the SVGs, so the variants cannot drift apart. The
script is idempotent — running it against an unchanged checkout rewrites the same bytes.
