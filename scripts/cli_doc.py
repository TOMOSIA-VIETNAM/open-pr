#!/usr/bin/env python3
"""Keep src/core/cli.md in step with `open-pr.sh --help`.

`--help` is the single source for the runtime's subcommands, common options and exit codes.
cli.md carries the same facts, rendered as markdown between two markers, so an agent has them
in context before its first call. Everything outside the markers is cli.md's own guidance.

Usage:
    python3 scripts/cli_doc.py            # exit 1 when cli.md drifted from --help
    python3 scripts/cli_doc.py --write    # regenerate the block in cli.md

`tests/graph/test_vendor_interface.py` imports `render()` from here, so the gate and this
tool can never disagree.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "src" / "bin" / "open-pr.sh"
DOC = REPO / "src" / "core" / "cli.md"
BEGIN = "<!-- open-pr.sh --help, via scripts/cli_doc.py -->"
END = "<!-- /open-pr.sh --help -->"


def help_text():
    return subprocess.run(["sh", str(CLI), "--help"], capture_output=True, text=True,
                          check=True).stdout


def sections(text):
    """{header: [lines]} for every `Header:` line at column 0."""
    out, cur = {}, None
    for line in text.splitlines():
        if re.match(r"^[A-Z][A-Za-z ]*:$", line):
            cur = line[:-1]
            out[cur] = []
        elif cur and line.strip():
            out[cur].append(line)
    return out


def cell(s):
    return s.replace("|", "\\|")


def render(text=None):
    sec = sections(text if text is not None else help_text())
    common = " ".join(l.strip() for l in sec["Common options"])
    rows, sig, desc = [], None, []
    for line in sec["Subcommands"] + ["  "]:
        if line.startswith("      "):
            desc.append(line.strip())
            continue
        if sig:
            rows.append(f"| `{cell(sig)}` | {cell(' '.join(desc))} |")
        sig, desc = line.strip(), []
    codes = " · ".join(
        f"{m.group(1)} = {m.group(2)}"
        for m in (re.match(r"^\s+(\d+)\s+(.*)$", l) for l in sec["Exit codes"]))
    return "\n".join([
        BEGIN,
        f"Common options, elided from the table: {common}",
        "",
        "| subcommand | does |",
        "|---|---|",
        *rows,
        "",
        f"Exit codes: {codes}.",
        END,
    ])


def current(doc):
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), doc, re.S)
    if not m:
        sys.exit(f"{DOC.relative_to(REPO)}: generated-block markers missing")
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="regenerate the block in cli.md")
    args = ap.parse_args()
    doc = DOC.read_text()
    m = current(doc)
    block = render()
    if m.group(0) == block:
        return 0
    if args.write:
        DOC.write_text(doc[:m.start()] + block + doc[m.end():])
        print(f"rewrote the generated block in {DOC.relative_to(REPO)}")
        return 0
    print(f"{DOC.relative_to(REPO)} drifted from `open-pr.sh --help` — run scripts/cli_doc.py --write")
    return 1


if __name__ == "__main__":
    sys.exit(main())
