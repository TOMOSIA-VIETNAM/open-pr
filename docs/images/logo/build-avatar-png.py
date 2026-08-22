#!/usr/bin/env python3
"""Render PNG avatars from the moth geometry defined in build-moth-assets.py.

GitHub (and most other profile hosts) accept only raster avatars and crop them
to a circle, so the SVG assets cannot be uploaded as-is: the wing tips of the
mark reach into the corners of its 128x128 box and would be sliced off.

This script solves both problems from the same single geometry source:
  * it measures how far the ink actually reaches from its own centre and scales
    the mark so every point lands inside the circle, with margin to spare;
  * it renders square PNGs at the sizes a profile picture is served at.

Run after editing the geometry in build-moth-assets.py:
    python3 build-avatar-png.py            # the avatars themselves
    python3 build-avatar-png.py --preview  # plus a circle-cropped render to eyeball
Outputs land in ./png/ beside this script.
"""
import argparse
import importlib.util
import math
import pathlib
import re

import cairosvg

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "png"

# The geometry lives in one place only; this script imports it rather than
# restating any coordinate or colour.
_spec = importlib.util.spec_from_file_location("moth", HERE / "build-moth-assets.py")
moth = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(moth)

BOX = 128          # the coordinate system every mark is drawn in
CIRCLE_FILL = 0.90  # fraction of the crop circle's radius the ink may use
SIZES = (1024, 512)

# Grounds an avatar is rendered on. Names become file names.
GROUNDS = {
    "light": dict(bg="#FFFFFF", tones=moth.LIGHT_BG),
    "dark":  dict(bg="#17130F", tones=moth.DARK_BG),
}


def ink_points(body):
    """Every polygon vertex in a rendered mark, as (x, y) floats."""
    pts = []
    for attr in re.findall(r'points="([^"]+)"', body):
        for pair in attr.split():
            x, y = pair.split(",")
            pts.append((float(x), float(y)))
    return pts


def fit_transform(body):
    """Centre the ink in the box and scale it inside the circular crop.

    Returns an SVG transform placing the mark so that its furthest vertex sits
    at CIRCLE_FILL of the inscribed circle's radius.
    """
    pts = ink_points(body)
    cx = (min(x for x, _ in pts) + max(x for x, _ in pts)) / 2
    cy = (min(y for _, y in pts) + max(y for _, y in pts)) / 2
    reach = max(math.hypot(x - cx, y - cy) for x, y in pts)
    k = (BOX / 2 * CIRCLE_FILL) / reach
    return (f"translate({BOX / 2:.3f} {BOX / 2:.3f}) scale({k:.4f}) "
            f"translate({-cx:.3f} {-cy:.3f})"), k, reach


def avatar_svg(body, bg, circle_mask=False):
    """A square avatar. circle_mask previews the crop the host applies."""
    ground = (f'<circle cx="{BOX / 2}" cy="{BOX / 2}" r="{BOX / 2}" fill="{bg}"/>'
              if circle_mask else
              f'<rect width="{BOX}" height="{BOX}" fill="{bg}"/>')
    clip = ''
    if circle_mask:
        clip = (f'<clipPath id="crop"><circle cx="{BOX / 2}" cy="{BOX / 2}" '
                f'r="{BOX / 2}"/></clipPath>')
    transform, _, _ = fit_transform(body)
    group = f'<g transform="{transform}"'
    group += ' clip-path="url(#crop)">' if circle_mask else '>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BOX} {BOX}" '
            f'role="img" aria-label="open-pr">{clip}{ground}'
            f'{group}{body}</g></svg>')


def write_png(name, svg, size):
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}-{size}.png"
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(path),
                     output_width=size, output_height=size)
    print(f"wrote {path.relative_to(HERE)}  {path.stat().st_size / 1024:.0f} KB")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", action="store_true",
                    help="also render a circle-cropped copy of each avatar, "
                         "showing the crop a profile host applies")
    args = ap.parse_args()

    for ground, g in GROUNDS.items():
        body = moth.full_mark(g["tones"])
        _, k, reach = fit_transform(body)
        print(f"{ground}: ink reach {reach:.1f} -> scale {k:.3f}")
        square = avatar_svg(body, g["bg"])
        for size in SIZES:
            write_png(f"avatar-{ground}", square, size)
        if args.preview:
            write_png(f"avatar-{ground}-circle-preview",
                      avatar_svg(body, g["bg"], circle_mask=True), 512)


if __name__ == "__main__":
    main()
