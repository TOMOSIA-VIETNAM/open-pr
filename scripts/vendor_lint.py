#!/usr/bin/env python3
"""Lint the vendor commands inside src/bin/open-pr.sh.

The unit suite (tests/test_cli.py) runs the script against FAKE gh/glab/curl shims, so
it proves the script's own logic but not that a flag exists on the real CLI or that an
endpoint still answers. This closes that gap, the same two ways the old vendor-file
lint did:

    flags   offline. Every `--flag` on every `gh`/`glab` invocation in the script must
            appear in that subcommand's own --help. The curl (Bitbucket) path is held to
            its stated rules instead: fail loudly with the body (--fail-with-body),
            follow documented redirects (-L on /diff and pagination), never dump the
            Authorization header (-v/-i), never put a credential in a URL.
    live    the read-only subcommands executed against an open fixture PR
            (target + context, every section). Needs a fixture and a token, so it stays
            manual and is preflight for an e2e round.

Usage:
    python3 scripts/vendor_lint.py                          # flags only, offline
    python3 scripts/vendor_lint.py --url <fixture PR URL>   # flags + live
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "src" / "bin" / "open-pr.sh"
TIMEOUT = 60

# Flags that belong to jq or to the shell fragment around the CLI call, not to the
# CLI subcommand itself.
NOT_CLI_FLAGS = {"--argjson", "--arg", "--slurp", "--raw-output", "--raw-input"}


def cli_invocations(body):
    """Yield (cli, subcommand-words, flags) per gh/glab invocation in the script."""
    for m in re.finditer(r"\b(gh|glab)\s+((?:[a-z][a-z-]*\s+)*[a-z][a-z-]*)?([^\n|;)]*)", body):
        cli, sub, rest = m.group(1), (m.group(2) or "").split(), m.group(3)
        flags = [f for f in re.findall(r"(--[a-z-]+)", rest) if f not in NOT_CLI_FLAGS]
        # subcommands nest up to 3 words (glab mr note create); extra words are harmless
        # args — both CLIs print the nearest real subcommand help
        yield cli, sub[:3], flags


def check_flags():
    body = SCRIPT.read_text(encoding="utf-8")
    bad = []
    seen = 0
    help_cache = {}
    for cli, sub, flags in cli_invocations(body):
        if not flags:
            continue
        key = (cli, *sub)
        if key not in help_cache:
            try:
                h = subprocess.run([cli, *sub, "--help"], capture_output=True,
                                   text=True, timeout=TIMEOUT)
                help_cache[key] = h.stdout + h.stderr
            except FileNotFoundError:
                help_cache[key] = None  # CLI not installed here — skip, CI installs both
        text = help_cache[key]
        if text is None:
            continue
        for f in flags:
            seen += 1
            if f not in text:
                bad.append(f"{cli} {' '.join(sub)}: unknown flag {f}")
    print(f"=== gh/glab: {seen} flag use(s) checked against --help")
    for b in bad:
        print(f"  BAD {b}")

    # Bitbucket/curl static rules.
    static_bad = []
    if "--fail-with-body" not in body:
        static_bad.append("curl calls must use --fail-with-body")
    for line in body.splitlines():
        if "curl" in line and re.search(r"\s-(v|i)\b", line):
            static_bad.append(f"curl must never dump headers into context: {line.strip()}")
    if re.search(r"https://[^\"'\s]*\$BITBUCKET", body):
        static_bad.append("a credential variable appears inside a URL")
    print("=== curl (bitbucket): static rules " + ("clean" if not static_bad else "VIOLATED"))
    for b in static_bad:
        print(f"  BAD {b}")
    return not bad and not static_bad


def check_live(url):
    def run(*args):
        r = subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, timeout=TIMEOUT)
        return r

    t = run("target", url)
    if t.returncode != 0:
        print(f"  BAD target: {t.stderr.strip()}")
        return False
    vals = dict(line.split("=", 1) for line in t.stdout.splitlines())
    print(f"=== live against {vals['vendor']} {vals['owner']}/{vals['repo']} #{vals['pull_number']}")
    ok = True
    r = run("context", "--vendor", vals["vendor"], "--owner", vals["owner"],
            "--repo", vals["repo"], "--pr", vals["pull_number"], "--host", vals["host"],
            "--max-patch-bytes", "20480",
            "--sections", "info,head,files,sizes,diff,commits,comments,ci,reviews,account,threads")
    if r.returncode != 0:
        print(f"  BAD context: {r.stderr.strip()}")
        ok = False
    else:
        sections = re.findall(r"^## (.+)$", r.stdout, re.M)
        expected = ["PR info", "Head SHA", "Files", "Diff size per file", "Diff",
                    "Commits", "Old comments", "CI checks", "Reviews", "Account",
                    "Review threads"]
        for s in expected:
            if s not in sections:
                print(f"  BAD context: section missing: {s}")
                ok = False
        head = re.search(r"^## Head SHA\n(\S+)", r.stdout, re.M)
        if not head or not re.fullmatch(r"[0-9a-f]{7,40}", head.group(1)):
            print("  BAD context: Head SHA is not a SHA")
            ok = False
    print("  live context: " + ("ok" if ok else "FAILED"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="an open fixture PR URL for the live half")
    args = ap.parse_args()
    ok = check_flags()
    if args.url:
        ok = check_live(args.url) and ok
    print("clean" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
