#!/usr/bin/env python3
"""Generate the open-pr moth logo assets from one shared geometry definition.

The mascot is a moth: in September 1947 the Harvard Mark II team pulled a moth
out of a relay and taped it into the logbook as the "first actual case of bug
being found". A tool that hunts bugs takes the bug as its mark; the eyespots on
the forewings double as the eyes doing the reviewing.

Run this script to regenerate every asset after editing the geometry below:
    python3 build-moth-assets.py
Outputs land beside this script (mark, dark variant, lockups, favicon).
Everything is flat polygons in one 128x128 coordinate system, four tones of a
single hue, no gradients and no strokes.
"""
import pathlib

OUT = pathlib.Path(__file__).resolve().parent

# Four tones of one hue. The dark-background variant lifts the darkest tone so
# the body does not sink into a near-black page.
LIGHT_BG = dict(deep="#A32C06", mid="#E8450F", light="#FF8A50", pale="#FFC49E")
DARK_BG  = dict(deep="#C4380A", mid="#F0521A", light="#FF9560", pale="#FFCEAC")

WORDMARK_INK = {"light": "#1F1E1D", "dark": "#F0EEE6"}
FONT = "Inter, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif"

# Vertical nudge keeping the winged mass optically centred in the box.
DY = 2


def mirror(points):
    return [(128 - x, y) for x, y in reversed(points)]


def shift(points):
    return [(x, y + DY) for x, y in points]


def polygon(points, fill):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in shift(points))
    return f'<polygon points="{pts}" fill="{fill}"/>'


def both(points, fill):
    """The mark is symmetric about x=64; define the left side only."""
    return polygon(points, fill) + polygon(mirror(points), fill)


def full_mark(t):
    """The primary mark: two wing pairs, a segmented body, swept antennae."""
    return "".join([
        both([(56, 42), (10, 16), (6, 40), (24, 62), (56, 60)], t["pale"]),
        both([(56, 44), (16, 24), (12, 42), (56, 56)], t["light"]),
        both([(30, 32), (38, 40), (30, 48), (22, 40)], t["deep"]),
        both([(56, 62), (26, 74), (20, 94), (46, 98), (56, 84)], t["mid"]),
        both([(57, 33), (62, 30), (30, 6), (24, 13)], t["light"]),
        polygon([(57, 30), (71, 30), (73, 42), (55, 42)], t["deep"]),
        polygon([(55, 42), (73, 42), (71, 60), (57, 60)], t["deep"]),
        polygon([(57, 58), (71, 58), (69, 96), (64, 110), (59, 96)], t["deep"]),
        polygon([(58, 71), (70, 71), (69.5, 77), (58.5, 77)], t["mid"]),
        polygon([(59, 84), (69, 84), (68.5, 90), (59.5, 90)], t["mid"]),
    ])


def reduced_mark(t):
    """Favicon build: one wing pair, no body segments, larger eyespot.

    A mascot cannot simply be scaled down — small facets turn to mud below about
    24px, so the small size gets its own drawing with fewer, larger shapes.
    """
    # The antennae stay in the reduced drawing even though they nearly vanish:
    # without them the two wings read as an anonymous pair of blobs at 16px,
    # with them the silhouette still says insect.
    return "".join([
        both([(54, 34), (6, 10), (2, 52), (24, 88), (50, 82)], t["pale"]),
        both([(54, 38), (14, 26), (10, 50), (50, 74)], t["light"]),
        both([(26, 30), (38, 42), (26, 54), (14, 42)], t["deep"]),
        both([(56, 30), (64, 25), (30, 4), (21, 14)], t["light"]),
        polygon([(55, 24), (73, 24), (71, 92), (64, 108), (57, 92)], t["deep"]),
    ])


# --- contact sheet -----------------------------------------------------------
# One image showing every variant on both grounds, so the brand page is a single
# look rather than a folder of files to open one by one. Each panel paints its
# own background, so the sheet reads correctly whatever theme the viewer is in.

SHEET_W, PANEL_H = 1040, 300
PANEL = [
    dict(name="On light", bg="#FFFFFF", label="#57534E", tones=LIGHT_BG, ink=WORDMARK_INK["light"]),
    dict(name="On dark",  bg="#17130F", label="#A8A29E", tones=DARK_BG,  ink=WORDMARK_INK["dark"]),
]


def _label(x, y, text, fill, size=13, weight="500"):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" letter-spacing=".02em">{text}</text>')


def _panel(p, dy):
    t, out = p["tones"], [f'<rect x="0" y="{dy}" width="{SHEET_W}" height="{PANEL_H}" fill="{p["bg"]}"/>']
    out.append(_label(48, dy + 44, p["name"].upper(), p["label"], 11, "600"))

    # the mark, at its native 128
    out.append(f'<g transform="translate(64 {dy + 92})">{full_mark(t)}</g>')
    out.append(_label(64, dy + 254, "mark · 128px", p["label"]))

    # the lockup, scaled to 360 wide
    k = 360 / 356
    out.append(f'<g transform="translate(268 {dy + 92}) scale({k:.4f})">'
               f'{full_mark(t)}<text x="138" y="86" font-family="{FONT}" font-size="56" '
               f'font-weight="600" fill="{p["ink"]}" letter-spacing="-1.2">open-pr</text></g>')
    out.append(_label(268, dy + 254, "lockup · 360px wide", p["label"]))

    # the favicon drawing at the sizes it actually gets used at
    x = 700
    for size in (32, 24, 16):
        k = size / 128
        out.append(f'<g transform="translate({x} {dy + 160 - size}) scale({k:.4f})">'
                   f'{reduced_mark(t)}</g>')
        x += size + 22
    out.append(_label(700, dy + 254, "favicon · 32 / 24 / 16px", p["label"]))

    # the four tones, named
    for i, key in enumerate(("deep", "mid", "light", "pale")):
        y = dy + 100 + i * 34
        out.append(f'<rect x="860" y="{y}" width="24" height="24" rx="3" fill="{t[key]}"/>')
        out.append(_label(896, y + 17, f'{key} &#183; {t[key]}', p["label"], 12, "400"))
    out.append(_label(860, dy + 254, "tones", p["label"]))
    return "".join(out)


def sheet_svg():
    panels = "".join(_panel(p, i * PANEL_H) for i, p in enumerate(PANEL))
    return ('<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {SHEET_W} {PANEL_H * len(PANEL)}" role="img" '
            'aria-label="open-pr logo variants on light and dark grounds">\n'
            f'  {panels}\n</svg>\n')


def icon_svg(body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" '
            f'role="img" aria-label="open-pr">\n  {body}\n</svg>\n')


def lockup_svg(body, ink):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 356 128" '
        'role="img" aria-label="open-pr">\n'
        f'  {body}\n'
        f'  <text x="138" y="86" font-family="{FONT}" font-size="56" '
        f'font-weight="600" fill="{ink}" letter-spacing="-1.2">open-pr</text>\n'
        '</svg>\n')


def main():
    """Write every asset. Guarded so other build scripts can import the geometry."""
    for name, content in {
        "logo.svg":              icon_svg(full_mark(LIGHT_BG)),
        "logo-dark.svg":         icon_svg(full_mark(DARK_BG)),
        "favicon.svg":           icon_svg(reduced_mark(LIGHT_BG)),
        "logo-lockup.svg":       lockup_svg(full_mark(LIGHT_BG), WORDMARK_INK["light"]),
        "logo-lockup-dark.svg":  lockup_svg(full_mark(DARK_BG), WORDMARK_INK["dark"]),
        "brand-sheet.svg":       sheet_svg(),
    }.items():
        (OUT / name).write_text(content)
        print("wrote", name)


if __name__ == "__main__":
    main()
