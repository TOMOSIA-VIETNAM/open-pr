#!/usr/bin/env python3
"""Token accounting for the open-pr plugin prompt files.

Measures what a run actually LOADS into context, not just repo size — a whole
file enters context the moment the agent `Read`s it, so per-file totals matter
more than the sum of everything shipped.

Scope: `src/` only. `CLAUDE.md` is dev context that never ships (--sections can still
inspect it), and README*/CONTRIBUTING are human prose.

Usage:
    python3 scripts/token_report.py                       # working tree vs itself
    python3 scripts/token_report.py --base <git-ref>       # compare against a ref
    python3 scripts/token_report.py --base main --json out.json
    python3 scripts/token_report.py --encoder anthropic    # exact Claude tokenizer (needs ANTHROPIC_API_KEY)

Encoders:
    tiktoken (default)  offline, cl100k_base — proxy, ~±5% vs Claude
    anthropic           exact, via the count_tokens endpoint (network + key)
"""

import argparse
import json
import re
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = "src"

# A scenario lists ROLES, not paths, so a layout change (one big file split into
# several, or a block moved into a shared atom) still compares like for like.
# Each role resolves to the first candidate path that exists in the tree being
# measured; a role resolving to nothing costs 0. Two roles landing on the same
# file count it ONCE — that is exactly what a whole-file `Read` costs.
ROLES = {
    "review-cmd": ["commands/review.md", "commands/review-pr.md"],
    "fix-cmd": ["commands/fix.md"],
    # second candidate = the pre-refactor location, so a base ref still resolves
    "stack": ["core/stack-detection.md", "stack-detection.md"],
    "always-rule": ["seeds/ALWAYS_RULE.md", "ALWAYS_RULE.md"],
    # baseline criteria: plugin-side since v4, inside the local rule file before that
    "criteria": ["core/review-criteria.md", "ALWAYS_RULE.md"],
    "pr-target": ["core/pr-target.md"],
    "repo-settings": ["core/repo-settings.md"],
    "memory-commit": ["core/memory-commit.md"],
    "setup-bootstrap": ["setup/bootstrap.md", "setup-flow.md"],
    "setup-doctor": ["setup/doctor.md", "setup-flow.md"],
    "setup-template": ["setup/template.md", "setup-flow.md"],
    "setup-lesson": ["setup/lesson.md", "setup-flow.md"],
    "setup-fix-bootstrap": ["setup/fix-bootstrap.md", "commands/fix.md"],
    "gh-fetch": ["vendors/github/fetch.md", "vendors/github.md"],
    "gh-worktree": ["vendors/github/worktree.md", "vendors/github.md"],
    "gh-post": ["vendors/github/post.md", "vendors/github.md"],
    "gh-thread": ["vendors/github/thread.md", "vendors/github.md"],
    "gl-fetch": ["vendors/gitlab/fetch.md", "vendors/gitlab.md"],
    "gl-worktree": ["vendors/gitlab/worktree.md", "vendors/gitlab.md"],
    "gl-post": ["vendors/gitlab/post.md", "vendors/gitlab.md"],
    "gl-thread": ["vendors/gitlab/thread.md", "vendors/gitlab.md"],
    "guardrails": ["core/guardrails.md"],
    "locate-repo": ["core/locate-repo.md"],
    "upgrades-index": ["core/llm-upgrades-index.md"],
    "reconfigure": ["core/reconfigure.md"],
    "upgrade-cmd": ["commands/upgrade.md"],
    "clean-cmd": ["commands/clean.md"],
    "case-post-error": ["cases/post-review.md"],
    "case-chat-requests": ["cases/chat-requests.md", "commands/review.md"],
    "case-re-review": ["cases/re-review.md"],
    # whichever file currently holds the "is this our own finding" logic
    "marker-logic": ["core/finding-markers.md", "cases/re-review.md"],
    "case-large-diff": ["cases/large-diff-guards.md"],
    "case-pr-template": ["cases/pr-template-checklist.md"],
    "case-submodule": ["cases/submodule-review.md"],
    "tpl-rails": ["templates/rails.md"],
    "tpl-vue": ["templates/vue.md"],
    "tpl-nodejs": ["templates/nodejs.md"],
    "tpl-agent-instructions": ["templates/agent-instructions.md"],
}

# A "load set" = what a single run of one command Reads into context.
SCENARIOS = {
    "review/new-repo-github": [
        "review-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "setup-bootstrap",
        "setup-doctor", "memory-commit", "upgrades-index", "gh-fetch", "gh-worktree",
        "gh-post",
        "criteria", "always-rule", "setup-template", "tpl-rails",
    ],
    "review/known-repo-github-clean": [
        "review-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "gh-fetch",
        "gh-worktree", "gh-post", "criteria", "always-rule", "tpl-rails",
    ],
    "review/known-repo-gitlab-rereview": [
        "review-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "gl-fetch", "gl-worktree",
        "gl-post", "gl-thread", "case-re-review", "marker-logic", "setup-doctor",
        "memory-commit",
        "criteria", "always-rule", "tpl-vue",
    ],
    "review/large-diff-multistack": [
        "review-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "gh-fetch", "gh-worktree",
        "gh-post", "case-large-diff", "case-pr-template", "criteria", "always-rule", "tpl-rails",
        "tpl-vue",
    ],
    "review/submodule-bump": [
        "review-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "gh-fetch", "gh-worktree",
        "gh-post", "case-submodule", "criteria", "always-rule", "tpl-nodejs",
    ],
    "review/agent-instructions-repo": [
        "review-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "gh-fetch",
        "gh-worktree", "gh-post", "criteria", "always-rule", "tpl-agent-instructions",
    ],
    "review/post-error-github": [
        "review-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "gh-fetch",
        "gh-worktree", "gh-post", "case-post-error", "criteria", "always-rule", "tpl-rails",
    ],
    "chat/reconfigure-review": [
        "review-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings",
        "case-chat-requests", "reconfigure", "memory-commit",
    ],
    "upgrade": [
        "upgrade-cmd", "upgrades-index", "guardrails",
    ],
    "clean": [
        "clean-cmd", "guardrails",
    ],
    "fix/known-repo-github": [
        "fix-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "gh-fetch", "gh-thread",
        "marker-logic", "criteria", "always-rule", "tpl-rails",
    ],
    "fix/first-run-gitlab": [
        "fix-cmd", "guardrails", "locate-repo", "pr-target", "repo-settings", "stack", "gl-fetch", "gl-thread",
        "marker-logic", "criteria", "setup-fix-bootstrap", "memory-commit",
    ],
}


def make_counter(kind):
    if kind == "tiktoken":
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(enc.encode(text)), "cl100k_base (proxy)"
    if kind == "anthropic":
        import anthropic
        client = anthropic.Anthropic()
        model = os.environ.get("TOKEN_REPORT_MODEL", "claude-sonnet-4-5-20250929")

        def count(text):
            if not text.strip():
                return 0
            r = client.messages.count_tokens(
                model=model, messages=[{"role": "user", "content": text}]
            )
            # Subtract the fixed per-message envelope so numbers stay comparable
            # to a raw file cost.
            return r.input_tokens
        return count, f"anthropic count_tokens ({model})"
    raise SystemExit(f"unknown encoder: {kind}")


def read_tree(ref):
    """Return {relpath: text} for every .md under src/ at `ref` (None = worktree)."""
    out = {}
    if ref is None:
        for p in sorted((REPO / SRC).rglob("*.md")):
            out[str(p.relative_to(REPO / SRC))] = p.read_text(encoding="utf-8")
        return out
    listing = subprocess.run(
        ["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", ref, "--", SRC],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    for path in sorted(listing):
        if not path.endswith(".md"):
            continue
        text = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-p", f"{ref}:{path}"],
            capture_output=True, text=True, check=True,
        ).stdout
        out[path[len(SRC) + 1:]] = text
    return out


def tokenize_tree(tree, count):
    return {rel: count(text) for rel, text in tree.items()}


def scenario_totals(per_file):
    totals = {}
    for name, roles in SCENARIOS.items():
        resolved, absent = {}, []
        for role in roles:
            hit = next((c for c in ROLES[role] if c in per_file), None)
            if hit is None:
                absent.append(role)
            else:
                resolved[hit] = per_file[hit]  # same file twice ⇒ counted once
        totals[name] = {"tokens": sum(resolved.values()),
                        "files": sorted(resolved), "absent": absent}
    return totals


def print_sections(per_text, count, pattern):
    """Token cost per `##` section — the view you need before deciding what to cut."""
    import fnmatch
    hits = [k for k in sorted(per_text) if fnmatch.fnmatch(k, pattern)]
    if not hits:
        print(f"no file matches {pattern!r}")
        return
    for name in hits:
        body = per_text[name]
        print(f"\n{count(body):>6}  {name}")
        for part in re.split(r"\n(?=## )", body):
            head = part.splitlines()[0][:58] if part.strip() else "(empty)"
            print(f"  {count(part):>5}  {head}")


def bar(delta_pct, width=18):
    n = min(width, int(abs(delta_pct) / 100 * width * 2))
    return ("-" if delta_pct < 0 else "+") * max(n, 1) if delta_pct else ""


def fmt_delta(new, old):
    if old == 0:
        return f"{new:>7,}      new"
    d = new - old
    pct = d / old * 100
    return f"{new:>7,}  {d:+7,}  {pct:+6.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="git ref to compare against (e.g. main)")
    ap.add_argument("--head", help="git ref to measure (default: working tree)")
    ap.add_argument("--encoder", default="tiktoken", choices=["tiktoken", "anthropic"])
    ap.add_argument("--json", help="also write raw numbers to this path")
    ap.add_argument("--sections", metavar="GLOB",
                    help="print per-section tokens for files matching this glob, then exit")
    ap.add_argument("--update-budgets", action="store_true",
                    help="rewrite tests/budgets.json from this measurement (+2%% headroom)")
    args = ap.parse_args()

    count, enc_label = make_counter(args.encoder)
    if args.sections:
        pool = read_tree(args.head)
        if args.head is None:  # dev files are inspectable, though never measured
            pool["CLAUDE.md"] = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
        print_sections(pool, count, args.sections)
        return 0
    head = tokenize_tree(read_tree(args.head), count)
    base = tokenize_tree(read_tree(args.base), count) if args.base else None

    print(f"encoder: {enc_label}")
    print(f"head:    {args.head or 'working tree'}")
    if args.base:
        print(f"base:    {args.base}")

    print("\n== PER FILE ==")
    keys = sorted(set(head) | set(base or {}), key=lambda k: -head.get(k, 0))
    for k in keys:
        h, b = head.get(k, 0), (base or {}).get(k, 0)
        if base is None:
            print(f"{h:>7,}  {k}")
        else:
            print(f"{fmt_delta(h, b)}  {k}  {bar((h-b)/b*100 if b else 0)}")

    print("\n== SHIPPED TOTAL (all src/*.md) ==")
    ht = sum(head.values())
    if base is None:
        print(f"{ht:>7,}")
    else:
        print(fmt_delta(ht, sum(base.values())))

    print("\n== PER-RUN CONTEXT COST (what one invocation actually Reads) ==")
    hs = scenario_totals(head)
    bs = scenario_totals(base) if base else None
    for name in SCENARIOS:
        h = hs[name]["tokens"]
        if bs is None:
            print(f"{h:>7,}  {name}")
        else:
            b = bs[name]["tokens"]
            print(f"{fmt_delta(h, b)}  {name}")
    if bs:
        # Averaging over a scenario the base never had would flatter or punish the
        # head unfairly, so the mean covers only scenarios both trees can run.
        both = [n for n in SCENARIOS if bs[n]["tokens"] > 0]
        hm = sum(hs[n]["tokens"] for n in both) / len(both)
        bm = sum(bs[n]["tokens"] for n in both) / len(both)
        skipped = [n for n in SCENARIOS if n not in both]
        print(f"{fmt_delta(int(hm), int(bm))}  MEAN over {len(both)} comparable scenarios")
        if skipped:
            print(f"{'':>7}  (head-only, excluded from the mean: {', '.join(skipped)})")

    if args.update_budgets:
        b = {"scenarios": {k: int(v["tokens"] * 1.02) for k, v in hs.items()},
             "mean": int(sum(v["tokens"] for v in hs.values()) / len(hs) * 1.02),
             "_note": "Ceilings measured by scripts/token_report.py (cl100k proxy), +2% headroom. "
                      "Lower them when a change wins tokens back."}
        (REPO / "tests" / "budgets.json").write_text(json.dumps(b, indent=2) + "\n")
        print("\nwrote tests/budgets.json")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"encoder": enc_label, "head": head, "base": base,
             "scenarios_head": hs, "scenarios_base": bs}, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    sys.exit(main())
