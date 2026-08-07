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
            live mode must not run. A vendor reached by `curl` has no subcommand help to
            check against, so its entries are held to the rules of
            src/core/raw-http-vendor.md instead: fail loudly with the body, follow a
            documented redirect, never print the Authorization header, never carry a
            credential literal.
    live    the read-only Fetch entries executed against an open fixture PR. Needs a
            fixture and a token, so it stays manual and is preflight for an e2e round.

Seconds and free either way, versus a full e2e round that costs a model call.

Usage:
    python3 scripts/vendor_lint.py                         # flags only, offline
    python3 scripts/vendor_lint.py --pr 20                 # flags + live, every vendor
    python3 scripts/vendor_lint.py --vendor gitlab --pr 20
    python3 scripts/vendor_lint.py --url https://bitbucket.org/<ws>/<repo>/pull-requests/7
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
VENDORS = sorted(p.name for p in (REPO / "src" / "vendors").iterdir() if p.is_dir())

# The executable each vendor drives. A vendor with no CLI of its own drives `curl`, whose
# presence is not worth testing separately.
CLI = {"github": "gh", "gitlab": "glab"}


def cli(vendor):
    return CLI.get(vendor, "curl")

# Caller-supplied bits the entries deliberately leave open. NOT commands — only the
# values a caller would pass, so this file can never drift into a second copy of them.
FIELDS = "number,title,body,author,baseRefName,headRefName"
MAX_PATCH_BYTES = "20480"   # the big_file_threshold_kb default, 20 KB

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


def auth_flag():
    """`<auth>` is a caller-supplied bit like <fields>: the entries name the env vars, and this
    picks whichever pair the operator actually exported. Values are never read here."""
    if os.environ.get("BITBUCKET_EMAIL") and os.environ.get("BITBUCKET_API_TOKEN"):
        return '-u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN"'
    if os.environ.get("BITBUCKET_TOKEN"):
        return '-H "Authorization: Bearer $BITBUCKET_TOKEN"'
    return ""


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


RUNNERS = ("gh", "glab", "git", "curl", "LC_ALL=C")


def shorthands(vendor):
    """A CLI-less vendor factors its base URL, its curl invocation and its whole-diff command
    into a table of `<name>` = value at the top of fetch.md, so entries stay one line. Read that
    table rather than restating any of it here — a second copy is what drifts."""
    body = (REPO / "src" / "vendors" / vendor / "fetch.md").read_text()
    out = {}
    for row in re.findall(r"^\| `(<[a-z_]+>)` \| (.+?) \|$", body, re.M):
        name, value = row[0], row[1]
        m = re.match(r"\s*`([^`]+)`", value)
        if m:
            out[name] = " ".join(m.group(1).split())
    for _ in range(3):          # a shorthand may be written in terms of another
        for k, v in out.items():
            for k2, v2 in out.items():
                if k2 != k and k2 in v:
                    out[k] = v.replace(k2, v2)
    return out


def expand(cmd, subs):
    for _ in range(3):
        for k, v in subs.items():
            cmd = cmd.replace(k, v)
    return " ".join(cmd.split())


def is_command(flat):
    head = flat.split()[:1]
    return bool(head) and head[0] in RUNNERS


ATOM = REPO / "src" / "core" / "raw-http-vendor.md"


def atom_pipeline(part):
    """An entry of a CLI-less vendor may hand its whole-diff command to a shared pipeline instead
    of spelling one out. Rebuild what the agent would run: the atom's own pipeline, fed this
    entry's `<diff_cmd>`. Without this the 2 costliest fetches would never execute live."""
    if "core/raw-http-vendor.md" not in part:
        return None
    blocks = [" ".join(b.split()) for b in re.findall(r"```bash\n(.*?)```", ATOM.read_text(), re.S)]
    wanted = [b for b in blocks if ("-v m=" in b) == ("<max_patch_bytes>" in part)]
    return wanted[0] if wanted else None


def entries(vendor):
    """(heading, command | None, body) for every Fetch entry, in file order."""
    body = (REPO / "src" / "vendors" / vendor / "fetch.md").read_text()
    short = shorthands(vendor)
    for part in re.split(r"\n(?=## )", body)[1:]:
        head = part.splitlines()[0][3:].strip()
        if not head.startswith("Fetch"):
            continue
        cmds = [expand(s, short) for s in re.findall(r"`([^`]+)`", part, re.S)]
        cmds = [c for c in cmds if is_command(c)]
        if not cmds and (piped := atom_pipeline(part)):
            cmds = [expand(piped, short)]
        yield head, (cmds[0] if cmds else None), part


def all_entries(vendor, keep=("gh", "glab", "curl", "LC_ALL=C")):
    """Every entry of every group, not just Fetch — a flag typo in `Post a review` is
    the same defect and the live mode must never execute that one."""
    short = shorthands(vendor)
    for group in ("fetch", "worktree", "post", "thread"):
        body = (REPO / "src" / "vendors" / vendor / f"{group}.md").read_text()
        for part in re.split(r"\n(?=## )", body)[1:]:
            head = part.splitlines()[0][3:].strip()
            for span in re.findall(r"`([^`]+)`", part, re.S) + \
                        re.findall(r"```(?:bash)?\n(.*?)```", part, re.S):
                flat = expand(span, short)
                if flat.split()[:1] and flat.split()[0] in keep:
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


def lint_curl(vendor):
    """A `curl` vendor has no subcommand help to check a flag against, so what gets checked is
    the contract src/core/raw-http-vendor.md states: an HTTP error must exit non-zero AND keep its
    body, the credential must stay a variable name, and no flag may echo the Authorization header.
    Every rule is read off the vendor's own text, so this never becomes a second copy of it."""
    print(f"\n=== {vendor}: curl entries vs the raw-HTTP contract")
    fails, checked = [], 0
    api = shorthands(vendor).get("<api>", "")
    host = re.match(r"(<host>|https://[^/]+)", api)
    host = host.group(1) if host else ""
    for group, head, cmd in all_entries(vendor):
        for segment in re.split(r"\|\||\||&&", cmd):
            segment = segment.strip()
            if not segment.startswith(("curl", "LC_ALL=C curl")):
                continue
            checked += 1
            bad = []
            if "--fail-with-body" not in segment:
                bad.append("no --fail-with-body: an HTTP error would read as success")
            for flag in (" -f ", " -v ", " -i ", " --verbose", " --include"):
                if flag in f"{segment} ":
                    bad.append(f"{flag.strip()} discards the error body or prints the auth header")
            if re.search(r'-u "[^$"]+"', segment) or re.search(r"Bearer [A-Za-z0-9]{8,}", segment):
                bad.append("a credential literal, not a variable name")
            for url in re.findall(r'"(https?://[^"]+|<host>[^"]*)"', segment):
                if host and not url.startswith(host):
                    bad.append(f"reaches {url.split('/')[2] if '//' in url else url} outside {host}")
            for why in bad:
                fails.append((f"{group}: {head}", why))
                print(f"  FAIL  {group}/{head}  →  {why}")
    # A shorthand that documents a mandatory flag must carry it — the file's own claim, tested.
    body = (REPO / "src" / "vendors" / vendor / "fetch.md").read_text()
    for name, rest in re.findall(r"^\| `(<[a-z_]+>)` \| (.+?) \|$", body, re.M):
        for flag in re.findall(r"`(-[A-Za-z])` MANDATORY", rest):
            if flag not in shorthands(vendor).get(name, ""):
                fails.append((name, f"calls {flag} MANDATORY but does not use it"))
                print(f"  FAIL  {name}  →  {flag} called mandatory, absent")
    print(f"  {checked} curl invocation(s) checked, {len(fails)} problem(s)")
    return fails


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
    if vendor.startswith("bitbucket"):
        return ""   # no fixture repo of this project's own exists yet; pass --url instead
    if vendor == "github":
        rc, out, _ = sh(f'gh pr list -R "{cfg["GITHUB_REPO"]}" --head "{branch}" '
                        f"--json url --jq '.[0].url'", env)
    else:
        proj = cfg["GITLAB_REPO"].replace("/", "%2F")
        rc, out, _ = sh(f'glab api "projects/{proj}/merge_requests?source_branch={branch}'
                        f'&state=opened" | jq -r \'.[0].iid // empty\'', env)
        out = f'https://{cfg["GITLAB_HOST"]}/{cfg["GITLAB_REPO"]}/-/merge_requests/{out}' if out else ""
    return out if rc == 0 and out else ""


# Same 4 shapes as src/core/pr-target.md §1, most specific first: a Data Center URL also
# matches the Cloud shape's segment count, so its /projects/…/repos/… form has to be tried first.
URL_SHAPES = (
    ("github", r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)"),
    ("gitlab", r"https://[^/]+/([^/]+)/([^/]+)/-/merge_requests/(\d+)"),
    ("bitbucket-server", r"https://[^/]+/projects/([^/]+)/repos/([^/]+)/pull-requests/(\d+)"),
    ("bitbucket", r"https://bitbucket\.org/([^/]+)/([^/]+)/pull-requests/(\d+)"),
)


def parse_url(url):
    for vendor, shape in URL_SHAPES:
        m = re.match(shape, url)
        if m:
            return vendor, *m.groups()
    raise SystemExit(f"not a PR/MR url: {url}")


def lint(vendor, url, env):
    _, owner, repo, num = parse_url(url)
    subs = {"<url>": url, "<owner>": owner, "<repo>": repo, "<pull_number>": num,
            "<fields>": FIELDS, "<max_patch_bytes>": MAX_PATCH_BYTES,
            "<host>": "https://" + url.split("/")[2], "<auth>": auth_flag()}
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
    ap.add_argument("--vendor", default="all", choices=[*VENDORS, "all"])
    ap.add_argument("--pr", help="project PR number whose fixture to lint against")
    ap.add_argument("--url", help="fixture PR/MR url, instead of deriving it from --pr")
    args = ap.parse_args()

    # A wrapper that swallows unknown flags would hide exactly the defect this looks
    # for, so ask rtk to step aside.
    env = {**os.environ, "RTK_DISABLED": "1", "NO_COLOR": "1", "GLAB_CHECK_UPDATE": "0"}
    cfg = targets()
    vendors = VENDORS if args.vendor == "all" else [args.vendor]
    if args.url:
        vendors = [parse_url(args.url)[0]]

    all_fails, ran = {}, 0
    for v in vendors:
        exe = cli(v)
        if subprocess.run(f"command -v {exe}", shell=True, capture_output=True).returncode:
            print(f"\n=== {v}: {exe} not installed, skipped")
            continue
        ran += 1
        fails = lint_curl(v) if exe == "curl" else lint_flags(v, env)
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
        scope = ("static checks, and every Fetch entry ran" if (args.pr or args.url)
                 else "static checks")
        print(f"clean on {ran} vendor(s): {scope}")
        return 0
    for v, fs in all_fails.items():
        for head, why in fs:
            print(f"{v}: {head}\n    {why}")
    print(f"\n{sum(len(f) for f in all_fails.values())} broken entr(ies) — fix src/vendors/<v>/")
    return 1


if __name__ == "__main__":
    sys.exit(main())
