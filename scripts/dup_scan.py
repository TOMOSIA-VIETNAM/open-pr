#!/usr/bin/env python3
"""Find duplicated prose across and inside the prompt files under src/.

One algorithm, two modes: normalise to words, slide a window, hash it, report a
window that appears twice.

    cross   the same rule grew a second owner in another file
    intra   the same rule restated inside one file, where both copies read as if
            they belong — the harder kind to notice by eye

Only NEAR-VERBATIM repeats surface. A restatement in fresh words does not, so a
clean run is not proof that every rule is stated once.

Findings are ranked by wasted tokens (block size × extra copies), which is the
number that decides whether a block is worth chasing.

Usage:
    python3 scripts/dup_scan.py                    # both modes, both scopes
    python3 scripts/dup_scan.py --mode intra --scope dev
    python3 scripts/dup_scan.py --window 10 --all   # explore; include allowlisted
    python3 scripts/dup_scan.py --min-waste 40      # only blocks worth the edit
    python3 scripts/dup_scan.py --json out.json

`tests/test_prompt_graph.py` imports `scan()` from here, so the gate and this tool
can never disagree.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
ALLOWLIST = REPO / "tests" / "duplication_allowlist.json"

# Within one file a shorter repeat is already suspicious; across files a short
# match is more often shared vocabulary than a shared rule.
WINDOW = {"cross": 18, "intra": 12}

# Scopes are scanned INDEPENDENTLY — a phrase shared between a shipped file and a
# dev file is not a duplicated rule, they address different readers.
#   src       the plugin itself; also what the token budget measures
#   dev       read by an agent working ON the plugin: never shipped, never in the budget,
#             but a duplicate still costs every session that loads it
#   adapters  the entry layer other platforms read instead of src/commands/: shipped and
#             read at run time, outside the budget because Claude Code never loads it
# README*.md and CONTRIBUTING.md are human prose and belong to none of them.
SCOPES = {"src": lambda: sorted(SRC.rglob("*.md")),
          "dev": lambda: [REPO / "CLAUDE.md", *sorted((REPO / ".claude").rglob("*.md"))],
          "adapters": lambda: sorted([*(REPO / "adapters").rglob("*.md"),
                                      *(REPO / "skills").rglob("*.md")])}


def in_nested_checkout(p):
    """A git worktree or clone parked inside the tree — `.claude/worktrees/<name>` is where
    an agent puts one. Its files are a copy of this repo, so scanning them reports this
    repo's own prose as duplicated against itself."""
    for parent in p.parents:
        if parent == REPO:
            return False
        if (parent / ".git").exists():
            return True
    return False


def md_files(scope="src"):
    return [p for p in SCOPES[scope]() if p.exists() and not in_nested_checkout(p)]


def rel(p):
    return str(p.relative_to(SRC)) if SRC in p.parents else str(p.relative_to(REPO))


def strip_frontmatter(body):
    """Blank out YAML frontmatter, keeping line numbers intact — every scope holds files
    that carry one. Field names and the values the harness dictates repeat across files by
    necessity, so a match there is not a duplicated rule. `description:` is written by hand
    and stays in the scan, wrapped lines included."""
    lines = body.splitlines()
    if not lines or lines[0].strip() != "---":
        return body
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            kept, in_description = [], False
            for l in lines[:i + 1]:
                if l.startswith("description:"):
                    in_description = True
                elif re.match(r"\S", l):
                    in_description = False
                kept.append(l if in_description else "")
            return "\n".join(kept + lines[i + 1:])
    return body


def strip_fences(body):
    """Blank out fenced blocks, keeping line numbers intact. A fence is verbatim by
    policy (commands, payloads, error text), so a repeat inside one is not a
    duplicated rule."""
    out, in_fence = [], False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
        else:
            out.append("" if in_fence else line)
    return out


def words_with_lines(lines):
    for n, line in enumerate(lines, 1):
        for w in re.sub(r"[^a-z0-9 ]+", " ", line.lower()).split():
            yield w, n


def approved():
    if not ALLOWLIST.exists():
        return {}
    return {e["sha"]: e.get("reason", "") for e in json.loads(ALLOWLIST.read_text())["approved"]}


def _count_tokens():
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return lambda s: len(enc.encode(s))
    except ImportError:
        return lambda s: len(s.split())  # word count is close enough to rank by


def scan(mode="both", window=None, include_approved=False, scope="src"):
    """Return findings sorted by wasted tokens, descending.

    A finding: {mode, sha, run, occurrences: [(file, line)], waste}. A repeat longer
    than the window shows up as several overlapping windows, so occurrences are keyed
    by location — one block, one finding, one allowlist entry.
    """
    count, allow, findings = _count_tokens(), approved(), []
    modes = ["cross", "intra"] if mode == "both" else [mode]
    per_file = {rel(p): words_with_lines(strip_fences(strip_frontmatter(
                   p.read_text(encoding="utf-8"))))
                for p in md_files(scope)}
    per_file = {k: list(v) for k, v in per_file.items()}

    for m in modes:
        w = window or WINDOW[m]
        blocks = {}
        seen = {}  # cross: sha -> (file, line);  intra: reset per file
        for name, pairs in per_file.items():
            if m == "intra":
                seen = {}
            for i in range(len(pairs) - w + 1):
                win = pairs[i:i + w]
                run = " ".join(x for x, _ in win)
                sha = hashlib.sha1(run.encode()).hexdigest()[:12]
                line = win[0][1]
                prev = seen.get(sha)
                repeat = prev and (prev[0] != name if m == "cross" else line - prev[1] >= w)
                if repeat:
                    blocks.setdefault(_key(prev, name, line), (sha, run, prev, (name, line)))
                else:
                    seen.setdefault(sha, (name, line))
        for _, (sha, run, a, b) in blocks.items():
            if sha in allow and not include_approved:
                continue
            findings.append({
                "mode": m, "sha": sha, "run": run,
                "occurrences": [a, b],
                "waste": count(run),
                "approved_reason": allow.get(sha, ""),
            })
    findings.sort(key=lambda f: -f["waste"])
    return findings


def _key(prev, name, line):
    """Group every overlapping window of one repeat under a single location key."""
    return f"{prev[0]}:{prev[1]}+{name}:{line}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="both", choices=["cross", "intra", "both"])
    ap.add_argument("--scope", default="all", choices=[*SCOPES, "all"],
                    help="src = the shipped plugin, dev = CLAUDE.md, adapters = the non-Claude "
                         "entry layer (default: all, each scanned apart)")
    ap.add_argument("--window", type=int, help="words per window (default 18 cross / 12 intra)")
    ap.add_argument("--min-waste", type=int, default=0, help="hide blocks below this token count")
    ap.add_argument("--all", action="store_true", help="include allowlisted blocks")
    ap.add_argument("--json", help="write raw findings here")
    args = ap.parse_args()

    scopes = list(SCOPES) if args.scope == "all" else [args.scope]
    found = [f for s in scopes for f in scan(args.mode, args.window, args.all, s)
             if f["waste"] >= args.min_waste]
    found.sort(key=lambda f: -f["waste"])
    if not found:
        print("no duplication found (near-verbatim only — a reworded restatement still needs a human)")
        return 0

    for f in found:
        (fa, la), (fb, lb) = f["occurrences"]
        tag = f"[{f['mode']}]" + (" [approved]" if f["approved_reason"] else "")
        print(f"\n~{f['waste']:>4} tok  {tag}  {f['sha']}")
        print(f"           {fa}:{la}")
        print(f"           {fb}:{lb}")
        print(f"           {f['run'][:120]}…")
        if f["approved_reason"]:
            print(f"           reason: {f['approved_reason'][:100]}")

    print(f"\n{len(found)} block(s), ~{sum(f['waste'] for f in found)} tokens of near-verbatim repeat")
    if args.json:
        Path(args.json).write_text(json.dumps(found, indent=2))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
