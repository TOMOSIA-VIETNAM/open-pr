"""Shared ground for the prompt-graph suite.

There is no runtime to exercise under src/ — the "program" is a set of markdown files an
agent Reads in a particular order. What CAN be tested mechanically is the graph itself, and
each test_*.py beside this module takes one part of it. Agent BEHAVIOUR (does it obey the
rules, is a finding any good) is out of scope; that needs live runs against real PRs.

Run: pytest tests/ -q
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SRC = REPO / "src"
TESTS = REPO / "tests"

sys.path.insert(0, str(REPO / "scripts"))
import dup_scan  # noqa: E402,F401  (re-exported: the duplication tests import it from here)
from token_report import ROLES, SCENARIOS, scenario_totals  # noqa: E402,F401

CLI = SRC / "bin" / "open-pr.sh"
VENDORS = ("bitbucket", "github", "gitlab")

# Files no scenario can put a number on. reference/ is for humans and a run must
# never pay for it. seeds/memory.md is `cp`-ed into the reviewed repo and read back
# only as that repo's own memory index, whose real size the team drives, not us.
NEVER_LOADED = {"reference/settings-schema.md", "reference/vendor-interface.md",
                "seeds/memory.md",
                # shipped for the humans and scanners that read an INSTALLED plugin
                # standalone — no run ever Reads it (src/LICENSE is not markdown)
                "SECURITY.md"}


SEVERITY_HEADINGS = ["#### 🔴 MUST FIX", "#### 🟠 SHOULD FIX",
                     "#### 🔵 SUGGESTION", "#### 📝 NOTE"]


def md_files():
    return sorted(p for p in SRC.rglob("*.md"))


def rel(p):
    return str(p.relative_to(SRC))


def text(p):
    return p.read_text(encoding="utf-8")


def all_text():
    return {rel(p): text(p) for p in md_files()}


def cli_text():
    return CLI.read_text(encoding="utf-8")
