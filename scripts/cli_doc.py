#!/usr/bin/env python3
"""Keep src/core/cli.md and src/commands/watch.md in step with `open-pr.sh --help`.

`--help` is the single source for the runtime's subcommands, common options and exit codes.
cli.md carries its `Subcommands:`, common options and exit codes, rendered as markdown between
two markers, so an agent has them in context before its first call; every review and fix run
loads it. `Watch subcommands:` render into commands/watch.md alone, the one command that calls
them. `Internal subcommands:` are open-pr-watch.sh's own and render nowhere. Everything outside
the markers is each file's own guidance.

Usage:
    python3 scripts/cli_doc.py            # exit 1 when a block drifted from --help
    python3 scripts/cli_doc.py --write    # regenerate the blocks

`tests/graph/test_vendor_interface.py` imports `render()` and `render_watch()` from here, so
the gate and this tool can never disagree.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "src" / "bin" / "open-pr.sh"
DOC = REPO / "src" / "core" / "cli.md"
WATCH_DOC = REPO / "src" / "commands" / "watch.md"
BEGIN = "<!-- open-pr.sh --help, via scripts/cli_doc.py -->"
END = "<!-- /open-pr.sh --help -->"
WATCH_BEGIN = "<!-- open-pr.sh --help Watch subcommands, via scripts/cli_doc.py -->"
WATCH_END = "<!-- /open-pr.sh --help Watch subcommands -->"


def help_text():
    return subprocess.run(["sh", str(CLI), "--help"], capture_output=True, text=True,
                          check=True).stdout


def sections(text):
    """{header: [lines]} for every `Header:` or `Header (note):` line at column 0."""
    out, cur = {}, None
    for line in text.splitlines():
        if m := re.match(r"^([A-Z][A-Za-z ]*)(?: \(.*\))?:$", line):
            cur = m.group(1)
            out[cur] = []
        elif cur and line.strip():
            out[cur].append(line)
    return out


def cell(s):
    return s.replace("|", "\\|")


def table(lines):
    """A `| subcommand | does |` table: a 2-space line is a signature, a 6-space one describes it."""
    rows, sig, desc = ["| subcommand | does |", "|---|---|"], None, []
    for line in lines + ["  "]:
        if line.startswith("      "):
            desc.append(line.strip())
            continue
        if sig:
            rows.append(f"| `{cell(sig)}` | {cell(' '.join(desc))} |")
        sig, desc = line.strip(), []
    return rows


def render(text=None):
    sec = sections(text if text is not None else help_text())
    common = " ".join(l.strip() for l in sec["Common options"])
    codes = " · ".join(
        f"{m.group(1)} = {m.group(2)}"
        for m in (re.match(r"^\s+(\d+)\s+(.*)$", l) for l in sec["Exit codes"]))
    return "\n".join([
        BEGIN,
        f"Common options, elided from the table: {common}",
        "",
        *table(sec["Subcommands"]),
        "",
        f"Exit codes: {codes}.",
        END,
    ])


def render_watch(text=None):
    sec = sections(text if text is not None else help_text())
    return "\n".join([WATCH_BEGIN, *table(sec["Watch subcommands"]), WATCH_END])


def current(doc, begin=BEGIN, end=END):
    m = re.search(re.escape(begin) + r".*?" + re.escape(end), doc, re.S)
    if not m:
        sys.exit(f"generated-block markers missing: {begin}")
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="regenerate the blocks")
    args = ap.parse_args()
    text = help_text()
    drifted = 0
    for path, begin, end, block in ((DOC, BEGIN, END, render(text)),
                                    (WATCH_DOC, WATCH_BEGIN, WATCH_END, render_watch(text))):
        doc = path.read_text()
        m = current(doc, begin, end)
        if m.group(0) == block:
            continue
        if args.write:
            path.write_text(doc[:m.start()] + block + doc[m.end():])
            print(f"rewrote the generated block in {path.relative_to(REPO)}")
            continue
        print(f"{path.relative_to(REPO)} drifted from `open-pr.sh --help` — run scripts/cli_doc.py --write")
        drifted = 1
    return drifted


if __name__ == "__main__":
    sys.exit(main())
