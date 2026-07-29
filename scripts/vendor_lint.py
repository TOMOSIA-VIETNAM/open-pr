#!/usr/bin/env python3
"""Execute every read-only Fetch entry of a vendor file against a live fixture PR.

The unit suite reads the vendor files as text, so it cannot know whether a documented
command actually runs. A whole class of defect lives in that gap: a flag the CLI does
not have, an endpoint that moved, a jq path that matches nothing, a field renamed
upstream. `glab api --jq` sat in every GitLab fetch entry with a green suite.

This runs the commands as written — placeholders substituted, nothing rephrased — and
asserts each exits 0 and, where emptiness would mean failure, returns something. Read
only: no POST, no PATCH, nothing is created or published, so it is safe on any PR.

Seconds and free, versus a full e2e round that costs a model call. Run it first.

Usage:
    python3 scripts/vendor_lint.py --pr 20                 # both vendors, fixture of PR 20
    python3 scripts/vendor_lint.py --vendor gitlab --pr 20
    python3 scripts/vendor_lint.py --vendor github --url <fixture PR url>
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
    if not (args.pr or args.url):
        raise SystemExit("need --pr <n> or --url <fixture url>")

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
        url = args.url or fixture_url(v, args.pr, env, cfg)
        if not url:
            print(f"\n=== {v}: no open fixture on e2e/pr-{args.pr} — run e2e/bootstrap.sh first")
            continue
        ran += 1
        f = lint(v, url, env)
        if f:
            all_fails[v] = f

    print()
    if not ran:
        raise SystemExit("nothing linted — no CLI available, or no fixture open")
    if not all_fails:
        print(f"every documented Fetch entry runs, on {ran} vendor(s)")
        return 0
    for v, fs in all_fails.items():
        for head, why in fs:
            print(f"{v}: {head}\n    {why}")
    print(f"\n{sum(len(f) for f in all_fails.values())} broken entr(ies) — fix src/vendors/<v>/fetch.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
