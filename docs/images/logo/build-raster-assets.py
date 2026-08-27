#!/usr/bin/env python3
"""Render the raster assets a hosting site needs, from the moth geometry.

Every shape and colour comes from build-moth-assets.py; nothing here restates a
coordinate. The SVG assets it writes cannot be uploaded to a hosting site
directly, because each upload slot imposes its own frame:

  avatar        square, cropped to a circle. The wing tips of the mark reach
                into the corners of its 128x128 box and the crop would slice
                them off, so the mark is scaled to fit inside the circle.
  social card   2:1 (1280x640), used as the link preview when the repository is
                shared. A square avatar dropped in this slot leaves the frame
                mostly empty ground, so the card is its own composition, laid
                out inside the 40pt safe border the host recommends.

Run after editing the geometry in build-moth-assets.py:
    python3 build-raster-assets.py            # every asset
    python3 build-raster-assets.py --preview  # plus a circle-cropped avatar to eyeball
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


# --- social card -------------------------------------------------------------
# The host serves this slot at 1280x640, so the 40pt safe border it recommends
# on the logical 640x320 card is 80px here. Nothing may cross that band: each
# surface sharing the link crops the outside differently.

CARD_W, CARD_H, SAFE = 1280, 640, 80
TAGLINE = "The review lands on the PR itself."
VENDORS = "GitHub \u00b7 GitLab \u00b7 Bitbucket"
COMMANDS = "/open-pr:review \u00b7 /open-pr:fix"

CARD_GROUNDS = {
    "light": dict(bg="#FFFFFF", tones=moth.LIGHT_BG,
                  ink=moth.WORDMARK_INK["light"], muted="#57534E"),
    "dark":  dict(bg="#17130F", tones=moth.DARK_BG,
                  ink=moth.WORDMARK_INK["dark"], muted="#A8A29E"),
}


def _centred_text(y, text, fill, size, weight="500", spacing=".01em"):
    return (f'<text x="{CARD_W / 2}" y="{y}" text-anchor="middle" '
            f'font-family="{moth.FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" letter-spacing="{spacing}">{text}</text>')


def social_svg(g):
    """A stacked lockup over tagline and meta lines, centred in the safe area.

    Stacked rather than side-by-side so every element centres by text anchor
    alone: no text width has to be guessed to keep the composition balanced.
    """
    mark_h = 156
    k = mark_h / BOX
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}" '
        f'role="img" aria-label="open-pr \u2014 {TAGLINE}">'
        f'<rect width="{CARD_W}" height="{CARD_H}" fill="{g["bg"]}"/>'
        f'<g transform="translate({(CARD_W - mark_h) / 2} 122) scale({k:.4f})">'
        f'{moth.full_mark(g["tones"])}</g>'
        + _centred_text(360, "open-pr", g["ink"], 88, "600", "-2.2")
        + _centred_text(414, TAGLINE, g["ink"], 32, "500")
        + _centred_text(474, VENDORS, g["muted"], 23, "400", ".04em")
        + _centred_text(508, COMMANDS, g["muted"], 23, "400", ".02em")
        + '</svg>')


def write_png(name, svg, size, height=None):
    OUT.mkdir(exist_ok=True)
    height = height or size
    stem = f"{name}-{size}" if height == size else f"{name}-{size}x{height}"
    path = OUT / f"{stem}.png"
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(path),
                     output_width=size, output_height=height)
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

    for ground, g in CARD_GROUNDS.items():
        write_png(f"social-card-{ground}", social_svg(g), CARD_W, CARD_H)


if __name__ == "__main__":
    main()
