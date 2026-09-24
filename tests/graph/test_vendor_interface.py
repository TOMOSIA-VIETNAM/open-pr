"""Both halves of the vendor contract — the documented interface and the script's branches."""

import re

from _common import SRC, VENDORS, text, all_text, cli_text
import cli_doc  # on sys.path via _common


def test_cli_contract_names_only_real_subcommands():
    """`open-pr.sh --help` is the runtime contract: every subcommand it names must exist in the
    script's dispatch, and every dispatched subcommand must be in it — an undocumented one is
    dead weight, a documented ghost sends the agent into exit 1."""
    subcommands = cli_doc.sections(cli_doc.help_text())["Subcommands"]
    documented = {l.split()[0] for l in subcommands if not l.startswith("      ")}
    dispatched = set(re.findall(r"^    ([a-z-]+)\)\s+cmd_", cli_text(), re.M))
    assert documented == dispatched, (
        f"help-only: {documented - dispatched}, script-only: {dispatched - documented}")


def test_cli_md_mirrors_the_help():
    """core/cli.md is what an agent has in context before its first call; `--help` is what the
    script actually takes. The block between cli.md's markers is rendered from `--help`, so the
    two cannot drift — edit usage() in the script, then run scripts/cli_doc.py --write."""
    doc = text(SRC / "core" / "cli.md")
    assert cli_doc.current(doc).group(0) == cli_doc.render(), \
        "cli.md drifted from `open-pr.sh --help` — run scripts/cli_doc.py --write"


def test_every_vendor_branches_in_every_api_subcommand():
    """The script is where vendor differences live, so each API-facing function must decide by
    $V for all three vendors — a missing branch is the old cross-vendor parity failure, now in
    one file instead of twelve."""
    body = cli_text()
    for fn in ("ctx_info", "ctx_head", "ctx_files", "ctx_sizes", "ctx_diff", "ctx_commits",
               "ctx_comments", "ctx_ci", "ctx_reviews", "ctx_account", "ctx_threads",
               "vendor_checkout", "cmd_post", "cmd_publish", "cmd_post_verify", "cmd_reply",
               "cmd_resolve", "cmd_react", "cmd_marker", "cmd_commit_url", "post_error_hint"):
        m = re.search(rf"^{fn}\(\)" + r" \{[^\n]*\n(.*?)^\}", body, re.M | re.S)
        assert m, f"function missing from the script: {fn}"
        for v in VENDORS:
            assert re.search(rf"\b{v}[/)|]", m.group(1)) or "*)" in m.group(1), \
                f"{fn}: no {v} branch and no catch-all"


def test_the_scripts_internals_never_reach_the_user():
    """Exit codes and stderr are the agent's interface, not the user's. A locate-repo
    ambiguity once surfaced as a fenced stderr dump with "exit 5" in a user-facing
    question; the rule lives in cli.md and both exit-5 call sites ask in plain language."""
    assert "stderr is for YOU: never quote it raw" in text(SRC / "core" / "cli.md")
    assert "Exception: text the script wrote FOR the user" in text(SRC / "core" / "cli.md")
    for cmd in ("review", "fix"):
        flat = " ".join(text(SRC / "commands" / f"{cmd}.md").split())
        assert "exit 5 → ask with a CHOICE in plain language" in flat, \
            f"{cmd}.md's exit-5 branch must ask in plain language, never relay stderr"
        assert "relay stderr" not in flat


def test_prompts_never_read_or_reimplement_the_cli():
    """The script is code, not context: a prompt Reading it pays its whole size per run, and a
    prompt carrying its own gh/glab/curl call is a second owner for a mechanic the script owns."""
    for name, body in all_text().items():
        assert not re.search(r"Read[^\n]*bin/open-pr", body), f"{name} Reads the script"
        if name in ("reference/vendor-interface.md",
                    # the upgrade path is vendor-CLI-free BY DESIGN: it fetches migration
                    # files over plain curl, which is its mechanism, not a vendor API call
                    "core/llm-upgrades-index.md", "commands/upgrade.md"):
            continue
        for m in re.finditer(r"`([^`]+)`|```[a-z]*\n(.*?)```", body, re.S):
            snippet = m.group(1) or m.group(2) or ""
            flat = " ".join(snippet.split())
            assert not re.search(r"\b(gh|glab) (api|pr|mr) ", flat), \
                f"{name}: a raw vendor call outside the script: {flat[:80]}"
            assert not re.search(r"\bcurl\s+-", flat), \
                f"{name}: a raw curl call outside the script: {flat[:80]}"
