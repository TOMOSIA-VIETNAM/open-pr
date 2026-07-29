#!/usr/bin/env python3
"""Execute every read-only Fetch entry of a vendor file against a live fixture PR.

The unit suite reads the vendor files as text, so it cannot know whether a documented
command actually runs. A whole class of defect lives in that gap: a flag the CLI does
not have, an endpoint that moved, a jq path that matches nothing, a field renamed
upstream. `glab api --jq` sat in every GitLab fetch entry with a green suite.

This runs the commands as written — placeholders substituted, nothing rephrased — and
asserts each exits 0 and, where emptiness would mean failure, returns something. Read
only: no POST, no PATCH, nothing is created or published, so it is safe on any PR.

Two modes:

    flags   offline. Every flag in every entry of EVERY group must appear in that
            subcommand's own --help. No fixture, no credentials, no network — so this is
            the half that belongs in CI. It also covers post/thread entries, which the
            live mode must not run.
    live    the read-only Fetch entries executed against an open fixture PR. Needs a
            fixture and a token, so it stays manual and is preflight for an e2e round.

Seconds and free either way, versus a full e2e round that costs a model call.

Usage:
    python3 scripts/vendor_lint.py                         # flags only, offline
    python3 scripts/vendor_lint.py --pr 20                 # flags + live, both vendors
    python3 scripts/vendor_lint.py --vendor gitlab --pr 20
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGETS = REPO / "e2e" / "targets.env"
TIMEOUT = 30

# Caller-supplied bits the entries deliberately leave open. NOT commands — only the
# values a caller would pass, so this file can never drift into a second copy of them.
FIELDS = "number,title,body,author,baseRefName,headRefName"

# Entries that legitimately come back empty on a fresh fixture PR: nobody has commented,
# nobody has reviewed, and the fixture repo has no CI.
MAY_BE_EMPTY = {
    "Fetch PR review comments (LINE-level findings)",
    "Fetch CI checks",
    "Fetch PR reviews (FILE-level findings + review_id)",
}

# An entry with no command must SAY it has none, or the parse failed and that is a bug
# in this lint rather than a clean skip. Matched case-insensitively so wording may vary.
NO_COMMAND_MARKERS = ("no equivalent", "reuse the response")


def sh(cmd, env):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       timeout=TIMEOUT, env=env, cwd=REPO)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def targets():
    out = {}
    for line in TARGETS.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def entries(vendor):
    """(heading, command | None, body) for every Fetch entry, in file order."""
    body = (REPO / "src" / "vendors" / vendor / "fetch.md").read_text()
    for part in re.split(r"\n(?=## )", body)[1:]:
        head = part.splitlines()[0][3:].strip()
        if not head.startswith("Fetch"):
            continue
        cmds = [" ".join(s.split()) for s in re.findall(r"`([^`]+)`", part, re.S)]
        cmds = [c for c in cmds if c.split()[:1] and c.split()[0] in ("gh", "glab", "git")]
        yield head, (cmds[0] if cmds else None), part


def all_entries(vendor):
    """Every entry of every group, not just Fetch — a flag typo in `Post a review` is
    the same defect and the live mode must never execute that one."""
    for group in ("fetch", "worktree", "post", "thread"):
        body = (REPO / "src" / "vendors" / vendor / f"{group}.md").read_text()
        for part in re.split(r"\n(?=## )", body)[1:]:
            head = part.splitlines()[0][3:].strip()
            for span in re.findall(r"`([^`]+)`", part, re.S) + \
                        re.findall(r"```(?:bash)?\n(.*?)```", part, re.S):
                flat = " ".join(span.split())
                if flat.split()[:1] and flat.split()[0] in ("gh", "glab"):
                    yield group, head, flat


def subcommand_and_flags(cmd):
    """('gh api', {'--paginate', '--jq'}) — the leading words that name the subcommand,
    and every flag handed to it. Stops at the first argument, so a path or a quoted
    value is never mistaken for a subcommand."""
    words, path, flags = cmd.split(), [], set()
    for w in words:
        if w.startswith("-"):
            flags.add(w.split("=")[0])
        elif not flags and (w.isalpha() or w in ("gh", "glab")):
            path.append(w)
        elif not flags:
            break  # an argument: the subcommand path ends here
    return " ".join(path), flags


_HELP = {}


def help_text(subcommand, env):
    if subcommand not in _HELP:
        rc, out, err = sh(f"{subcommand} --help", env)
        _HELP[subcommand] = (out + "\n" + err) if rc == 0 or out or err else ""
    return _HELP[subcommand]


def lint_flags(vendor, env):
    """A flag absent from its subcommand's help is the defect that hides best: the
    entry reads fine, the suite is green, and it fails on first use."""
    print(f"\n=== {vendor}: flags vs each subcommand's own --help")
    fails, checked = [], 0
    root = help_text("gh" if vendor == "github" else "glab", env)
    for group, head, cmd in all_entries(vendor):
        for segment in re.split(r"\|\||\||&&", cmd):
            segment = segment.strip()
            if not segment.split()[:1] or segment.split()[0] not in ("gh", "glab"):
                continue
            sub, flags = subcommand_and_flags(segment)
            if not flags:
                continue
            text = help_text(sub, env) or root
            unknown = sorted(f for f in flags if f not in text and f not in root)
            checked += len(flags)
            if unknown:
                fails.append((f"{group}: {head}", f"{sub} has no {', '.join(unknown)}"))
                print(f"  FAIL  {group}/{head}  →  {sub} {' '.join(unknown)}")
    print(f"  {checked} flag use(s) checked, {len(fails)} unknown")
    return fails


def fixture_url(vendor, pr, env, cfg):
    branch = f"e2e/pr-{pr}"
    if vendor == "github":
        rc, out, _ = sh(f'gh pr list -R "{cfg["GITHUB_REPO"]}" --head "{branch}" '
                        f"--json url --jq '.[0].url'", env)
    else:
        proj = cfg["GITLAB_REPO"].replace("/", "%2F")
        rc, out, _ = sh(f'glab api "projects/{proj}/merge_requests?source_branch={branch}'
                        f'&state=opened" | jq -r \'.[0].iid // empty\'', env)
        out = f'https://{cfg["GITLAB_HOST"]}/{cfg["GITLAB_REPO"]}/-/merge_requests/{out}' if out else ""
    return out if rc == 0 and out else ""


def parse_url(url):
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", url)
    if m:
        return "github", *m.groups()
    m = re.match(r"https://[^/]+/([^/]+)/([^/]+)/-/merge_requests/(\d+)", url)
    if m:
        return "gitlab", *m.groups()
    raise SystemExit(f"not a PR/MR url: {url}")


def lint(vendor, url, env):
    _, owner, repo, num = parse_url(url)
    subs = {"<url>": url, "<owner>": owner, "<repo>": repo, "<pull_number>": num,
            "<fields>": FIELDS}
    env = {**env, "OWNER": owner, "REPO": repo, "PULL_NUMBER": num}
    print(f"\n=== {vendor}  {url}")
    fails = []
    for head, cmd, body in entries(vendor):
        if cmd is None:
            if any(m in body.lower() for m in NO_COMMAND_MARKERS):
                print(f"  skip  {head} — documented as having no command")
            else:
                fails.append((head, "no command parsed, and the entry does not say it has none"))
                print(f"  PARSE {head}")
            continue
        for k, v in subs.items():
            cmd = cmd.replace(k, v)
        try:
            rc, out, err = sh(cmd, env)
        except subprocess.TimeoutExpired:
            fails.append((head, f"timed out after {TIMEOUT}s — an agent would hang here"))
            print(f"  HANG  {head}")
            continue
        if rc != 0:
            fails.append((head, f"exit {rc}: {err.splitlines()[-1] if err else '(no stderr)'}"))
            print(f"  FAIL  {head}  exit {rc}")
        elif not out and head not in MAY_BE_EMPTY:
            fails.append((head, "exit 0 but no output — the filter or the field name is wrong"))
            print(f"  EMPTY {head}")
        else:
            print(f"  ok    {head}  {len(out)}B")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor", default="both", choices=["github", "gitlab", "both"])
    ap.add_argument("--pr", help="project PR number whose fixture to lint against")
    ap.add_argument("--url", help="fixture PR/MR url, instead of deriving it from --pr")
    args = ap.parse_args()

    # A wrapper that swallows unknown flags would hide exactly the defect this looks
    # for, so ask rtk to step aside.
    env = {**os.environ, "RTK_DISABLED": "1", "NO_COLOR": "1", "GLAB_CHECK_UPDATE": "0"}
    cfg = targets()
    vendors = ["github", "gitlab"] if args.vendor == "both" else [args.vendor]
    if args.url:
        vendors = [parse_url(args.url)[0]]

    all_fails, ran = {}, 0
    for v in vendors:
        exe = "gh" if v == "github" else "glab"
        if subprocess.run(f"command -v {exe}", shell=True, capture_output=True).returncode:
            print(f"\n=== {v}: {exe} not installed, skipped")
            continue
        ran += 1
        fails = lint_flags(v, env)
        if args.pr or args.url:
            url = args.url or fixture_url(v, args.pr, env, cfg)
            if url:
                fails += lint(v, url, env)
            else:
                print(f"=== {v}: no open fixture on e2e/pr-{args.pr} — live mode skipped")
        if fails:
            all_fails[v] = fails

    print()
    if not ran:
        raise SystemExit("nothing linted — no CLI available, or no fixture open")
    if not all_fails:
        scope = "flags, and every Fetch entry ran" if (args.pr or args.url) else "flags"
        print(f"clean on {ran} vendor(s): {scope}")
        return 0
    for v, fs in all_fails.items():
        for head, why in fs:
            print(f"{v}: {head}\n    {why}")
    print(f"\n{sum(len(f) for f in all_fails.values())} broken entr(ies) — fix src/vendors/<v>/")
    return 1


if __name__ == "__main__":
    sys.exit(main())
