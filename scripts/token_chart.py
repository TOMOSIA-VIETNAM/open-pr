#!/usr/bin/env python3
"""Context cost per release, as the chart the READMEs embed.

`token_report.py` answers "what does a run cost right now". This answers "how has
that moved across releases" — one point per git tag, one line per command.

Numbers are measured ONCE, at the release that produced them, and stored in
tests/token-history.json. Nothing recomputes an existing point: the ROLES map in
token_report.py evolves (a file gets split, a scenario is added), so a rerun years
later would quietly rewrite what was published. Frozen rows keep the chart honest
about what each release actually shipped.

Usage:
    scripts/token_chart.py --add v1.1.0        # measure that tag, append, redraw
    scripts/token_chart.py --add v1.1.0 --commit   # ... then commit + push to main
    scripts/token_chart.py --render            # redraw from the stored numbers only
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from token_report import (  # noqa: E402
    ROLES, SCENARIOS, make_counter, read_tree, scenario_totals, tokenize_tree,
)

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "tests" / "token-history.json"
SVG = REPO / "token-history.svg"

# A line per command. `cmd_role` is what proves the command EXISTED at a tag: a
# group whose command file is absent gets null, never 0 — 0 would read as free.
LINES = [
    {"key": "review", "label": "/open-pr:review", "colour": "#2f81f7", "cmd_role": "review-cmd"},
    {"key": "fix", "label": "/open-pr:fix", "colour": "#e3742f", "cmd_role": "fix-cmd"},
    {"key": "upgrade", "label": "/open-pr:upgrade", "colour": "#a371f7", "cmd_role": "upgrade-cmd"},
    {"key": "clean", "label": "/open-pr:clean", "colour": "#3fb950", "cmd_role": "clean-cmd"},
    {"key": "feedback", "label": "/open-pr:feedback", "colour": "#db61a2", "cmd_role": "feedback-cmd"},
]

NOTE = (
    "One point per release tag; one line per command. A line is the MEAN token cost of that "
    "command's scenarios in scripts/token_report.py — every scenario that command owns, review "
    "including the reconfigure chat path — counting every prompt file a single run Reads into "
    "context. Encoder: cl100k_base via tiktoken, a proxy for Claude's own "
    "tokenizer (within a few percent, not identical). null = the command did not exist at that "
    "tag, which is why a line can start later than the chart. Every point is measured once, at "
    "its release, and never recomputed: token_report.py's ROLES map keeps evolving, so rerunning "
    "old tags today produces different numbers than were published then — ROLES lists a pre-1.0 "
    "filename as a fallback candidate for exactly that reason. Reproduce a NEW point with "
    "`scripts/token_chart.py --add <tag>`; redraw the image from these numbers with `--render`."
)

STAMP = "mean per group · cl100k_base proxy · each point frozen at its release · tests/token-history.json"

W, H = 720, 260
PAD_L, PAD_R, PAD_T, PAD_B = 62, 18, 38, 46
GREY = "#8b949e"


def sh(*args):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def load():
    if not DATA.exists():
        return {"_note": NOTE, "encoder": None, "points": []}
    return json.loads(DATA.read_text(encoding="utf-8"))


def measure(tag, encoder):
    """Group means for `tag`, or None per group whose command is absent there."""
    count, label = make_counter(encoder)
    tree = read_tree(tag)
    if not tree:
        raise SystemExit(f"{tag}: nothing under src/ — is that a real tag?")
    per_file = tokenize_tree(tree, count)
    totals = scenario_totals(per_file)

    out = {}
    for line in LINES:
        if not any(c in per_file for c in ROLES[line["cmd_role"]]):
            out[line["key"]] = None
            continue
        vals = [t["tokens"] for name, t in totals.items()
                if group_of(name) == line["key"] and t["tokens"]]
        out[line["key"]] = round(sum(vals) / len(vals)) if vals else None
    return out, label


def group_of(scenario):
    """A scenario belongs to the command it exercises. Anything unrecognised would land in
    `review` and silently move that line, so a command without its own LINES entry is an
    error rather than a default."""
    for line in LINES:
        if scenario == line["key"] or scenario.startswith(line["key"] + "/"):
            return line["key"]
    if scenario.startswith("chat/"):
        return "review"     # the review command, reached without a PR
    raise SystemExit(f"{scenario}: no line owns this scenario — add it to LINES")


def version_key(tag):
    return tuple(int(p) for p in tag.lstrip("v").split("-")[0].split("."))


def y_ceiling(values):
    """Round the axis up to a 2k step so the gridlines land on readable numbers."""
    top = max(values)
    step = 2000
    return ((top // step) + 1) * step


def render(data):
    points = data["points"]
    if not points:
        raise SystemExit("no points yet — run --add <tag> first")
    values = [v for p in points for v in (p.get(l["key"]) for l in LINES) if v is not None]
    ymax = y_ceiling(values)
    plot_w, plot_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B

    inset = 16  # keeps the first and last dot off the axis and off the right edge
    span = plot_w - 2 * inset

    def x(i):
        if len(points) == 1:
            return PAD_L + plot_w / 2
        return PAD_L + inset + i * span / (len(points) - 1)

    def y(v):
        return PAD_T + plot_h - (v / ymax) * plot_h

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"'
         f' font-family="system-ui,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"'
         f' role="img" aria-label="Context cost per release, one line per command">']

    # gridlines + y labels
    for gv in range(0, ymax + 1, 2000):
        gy = y(gv)
        s.append(f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W - PAD_R}" y2="{gy:.1f}"'
                 f' stroke="{GREY}" stroke-opacity="0.25"/>')
        s.append(f'<text x="{PAD_L - 8}" y="{gy + 3.5:.1f}" text-anchor="end" font-size="10"'
                 f' fill="{GREY}">{gv // 1000}k</text>')

    # x labels
    for i, p in enumerate(points):
        s.append(f'<text x="{x(i):.1f}" y="{H - PAD_B + 18:.1f}" text-anchor="middle"'
                 f' font-size="10" fill="{GREY}">{p["tag"]}</text>')

    # one polyline + dots per command, skipping the tags where it did not exist
    for line in LINES:
        seq = [(x(i), y(p[line["key"]])) for i, p in enumerate(points) if p.get(line["key"]) is not None]
        if len(seq) > 1:
            pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in seq)
            s.append(f'<polyline points="{pts}" fill="none" stroke="{line["colour"]}"'
                     f' stroke-width="2" stroke-linejoin="round"/>')
        for px, py in seq:
            s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{line["colour"]}"/>')

    # legend, and the value each line ends on. A command with no released point yet gets no
    # legend entry: the image is redrawn only when a release adds data, never when code changes.
    lx = PAD_L
    for line in LINES:
        last = next((p[line["key"]] for p in reversed(points) if p.get(line["key"]) is not None), None)
        if last is None:
            continue
        text = f'{line["label"]} {last:,}'
        s.append(f'<circle cx="{lx + 4}" cy="{PAD_T - 20}" r="3.5" fill="{line["colour"]}"/>')
        s.append(f'<text x="{lx + 13}" y="{PAD_T - 16.5}" font-size="11" fill="{GREY}">{text}</text>')
        lx += 26 + 7.0 * len(text)

    s.append(f'<text x="{PAD_L}" y="{H - 8}" font-size="9" fill="{GREY}"'
             f' fill-opacity="0.85">{STAMP}</text>')
    s.append("</svg>")
    SVG.write_text("\n".join(s) + "\n", encoding="utf-8")


def porcelain_paths(status):
    """Paths out of `git status --porcelain`, by splitting off the XY code rather than
    slicing a fixed offset: a leading unstaged status is a space, and any caller that
    trimmed the output has already eaten it, which a fixed offset then pays for by
    cutting the first character of a real path."""
    return sorted(line.split(maxsplit=1)[1] for line in status.splitlines() if line.strip())


def commit_and_push(tag):
    """The ONE push to main this repo allows, and only ever these two files."""
    paths = porcelain_paths(sh("git", "status", "--porcelain"))
    allowed = ["tests/token-history.json", "token-history.svg"]
    if not paths:
        print("nothing to commit — the chart already holds this tag")
        return
    if paths != allowed:
        raise SystemExit(f"refusing to push: the tree also changes {set(paths) - set(allowed)}")
    if sh("git", "branch", "--show-current") != "main":
        raise SystemExit("refusing to push: the chart commit belongs on main")
    sh("git", "fetch", "origin", "main")
    if sh("git", "rev-parse", "HEAD") != sh("git", "rev-parse", "origin/main"):
        raise SystemExit("refusing to push: HEAD is not origin/main — sync first, never force")
    sh("git", "add", *allowed)
    sh("git", "commit", "-m", f"chore(chart): context cost at {tag}")
    sh("git", "push", "origin", "main")
    print(f"pushed the {tag} point to main")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", metavar="TAG", help="measure this git tag and append it")
    ap.add_argument("--render", action="store_true", help="redraw the SVG from stored numbers")
    ap.add_argument("--commit", action="store_true",
                    help="with --add: commit and push the two chart files to main")
    ap.add_argument("--encoder", default="tiktoken", choices=["tiktoken", "anthropic"])
    args = ap.parse_args()
    if not args.add and not args.render:
        ap.error("nothing to do: pass --add <tag> or --render")

    data = load()
    data["_note"] = NOTE

    if args.add:
        if any(p["tag"] == args.add for p in data["points"]):
            raise SystemExit(f"{args.add} is already recorded — a point is never remeasured")
        if args.add not in sh("git", "tag", "--list").split():
            raise SystemExit(f"{args.add} is not a tag in this repo")
        row, enc = measure(args.add, args.encoder)
        data["encoder"] = enc
        data["points"].append({
            "tag": args.add,
            "date": sh("git", "log", "-1", "--format=%as", args.add),
            **row,
        })
        data["points"].sort(key=lambda p: version_key(p["tag"]))
        DATA.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"{args.add}: " + "  ".join(
            f'{l["key"]}={row[l["key"]] or "-"}' for l in LINES))

    render(data)
    print(f"wrote {SVG.relative_to(REPO)}")
    if args.commit:
        commit_and_push(args.add)


if __name__ == "__main__":
    sys.exit(main())
