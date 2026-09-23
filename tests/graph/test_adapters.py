"""The adapter layer — what platforms other than Claude Code enter through.

These files ship, are read at run time, and carry NO behaviour: each one names a command
file under src/ and gets out of the way. The tests below are what keeps them that way, so
that changing a rule stays a one-file edit under src/ no matter how many platforms exist.
"""

import json
import re
import subprocess

from _common import REPO, SRC, text, all_text

ADAPTER_ROOT = REPO / "adapters" / "root.md"
SHIMS = REPO / "skills"
TOMLS = REPO / "commands"
MANIFESTS = ("gemini-extension.json", "plugin.json", ".cursor-plugin/plugin.json",
             ".cursor-plugin/marketplace.json", ".codex-plugin/plugin.json",
             ".agents/plugins/marketplace.json")

# A shim that starts explaining the work has stopped being a shim. Each of these belongs to
# exactly one file under src/, and finding it out here means two owners.
BUSINESS_MARKERS = (
    "🔴", "🟠", "🔵", "📝", "worktree", "severity", "gh pr", "glab mr", "gh api", "glab api",
    "schema_version", ".open-pr/review", "settings.json", "ALWAYS_RULE", "memory.md",
)
SHIM_MAX_LINES = 14


def commands():
    return sorted(p.stem for p in (SRC / "commands").glob("*.md"))


def shim_files():
    return sorted(SHIMS.glob("open-pr-*/SKILL.md"))


def test_every_command_has_one_shim_per_entry_format():
    """A command with no shim is a command that platform cannot reach; a shim with no command
    is a dead slash entry. Adding a command is the ONE change that must touch this layer."""
    assert commands(), "no commands found under src/commands/"
    assert sorted(p.parent.name.removeprefix("open-pr-") for p in shim_files()) == commands()
    assert sorted(p.stem for p in TOMLS.glob("*.toml")) == commands()


def test_shims_delegate_to_a_command_that_exists():
    """The shim's whole job is the handoff, so a stale path here breaks the platform silently."""
    for shim in shim_files():
        cmd = shim.parent.name.removeprefix("open-pr-")
        body = text(shim)
        assert f"ROOT/commands/{cmd}.md" in body, f"{shim.parent.name}: no handoff to {cmd}.md"
        assert (SRC / "commands" / f"{cmd}.md").exists()
        assert "../../adapters/root.md" in body, f"{shim.parent.name}: adapter not reached"
    for toml in sorted(TOMLS.glob("*.toml")):
        body = text(toml)
        assert f"ROOT/commands/{toml.stem}.md" in body, f"{toml.name}: no handoff"
        assert "adapters/root.md" in body, f"{toml.name}: adapter not reached"


def instructions(path):
    """A shim minus its metadata. `description` is how a platform decides to trigger the skill
    at all, so it may say what the command is about; the instructions may not."""
    body = text(path)
    if path.suffix == ".toml":
        return re.sub(r"^description\s*=.*$", "", body, flags=re.M)
    return re.sub(r"\A---\n.*?\n---\n", "", body, flags=re.S)


def test_shims_carry_no_behaviour():
    """The rule the agent needs is under src/ and stays there. A shim that starts restating it
    drifts the moment src/ changes — and nothing would catch that but this test."""
    offenders = {}
    for f in (*shim_files(), *sorted(TOMLS.glob("*.toml"))):
        body = instructions(f).lower()
        hits = [m for m in BUSINESS_MARKERS if m.lower() in body]
        if hits:
            offenders[str(f.relative_to(REPO))] = hits
    assert not offenders, f"behaviour leaked into the adapter layer: {offenders}"


def test_shims_stay_short():
    """Length is the cheapest proxy for a shim growing opinions."""
    long = {str(p.relative_to(REPO)): n for p in shim_files()
            if (n := len(text(p).strip().splitlines())) > SHIM_MAX_LINES}
    assert not long, f"shims over {SHIM_MAX_LINES} lines (actual): {long}"


def test_only_the_adapter_names_platforms():
    """One file knows what Cursor, Codex, Gemini CLI and Antigravity are called and where they
    install. Spread that knowledge and every platform becomes a place to forget."""
    named = ("claude", "cursor", "codex", "gemini", "antigravity")
    leaked = {}
    for f in (*shim_files(), *sorted(TOMLS.glob("*.toml"))):
        body = text(f).lower()
        # a TOML is Gemini's own entry format, so naming Gemini in it is not a leak
        allowed = {"gemini"} if f.suffix == ".toml" else set()
        hits = [p for p in named if p in body and p not in allowed]
        if hits:
            leaked[str(f.relative_to(REPO))] = hits
    assert not leaked, f"platform names outside adapters/root.md: {leaked}"


def test_adapter_resolves_root_by_files_that_exist():
    """ROOT is defined as the directory holding these two files. Rename either and every
    platform but Claude Code stops finding the plugin."""
    body = text(ADAPTER_ROOT)
    for probe in ("commands/review.md", "core/guardrails.md"):
        assert probe in body, f"adapters/root.md no longer anchors ROOT on {probe}"
        assert (SRC / probe).exists(), f"{probe} moved; adapters/root.md must follow"


def test_adapter_maps_every_tool_the_prompts_name():
    """A tool named under src/ but absent from the map leaves a platform guessing — and the
    guess is usually to skip the step."""
    used = {t for _, body in all_text().items()
            for t in re.findall(r"`(Read|Write|Edit|Grep|Glob|Bash|AskUserQuestion)`", body)}
    used.add("Agent")  # named as a subagent in prose, not as a backticked tool
    body = text(ADAPTER_ROOT)
    missing = sorted(t for t in used if f"`{t}`" not in body)
    assert not missing, f"tools src/ names but adapters/root.md does not map: {missing}"


def test_manifests_agree_on_name_and_declare_one_version():
    """Every platform installs the same plugin, and the git tag is what says which release that is.
    Only Gemini CLI requires a version field, so it is the only manifest allowed to carry one — a
    second copy is a second thing to bump, and the one nobody bumps is the one that lies."""
    names, versioned = set(), []
    for m in MANIFESTS:
        path = REPO / m
        assert path.exists(), f"missing manifest: {m}"
        data = json.loads(path.read_text(encoding="utf-8"))
        names.add(data["name"])
        if "version" in data:
            versioned.append(m)
    claude = json.loads((SRC / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    names.add(claude["name"])
    assert names == {"open-pr"}, f"manifests disagree on the plugin name: {names}"
    assert versioned == ["gemini-extension.json"], \
        f"a version belongs in gemini-extension.json alone, found in: {versioned}"


PUBLIC_RELEASE_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
"""A tag names a public release only when it is exactly vX.Y.Z. Anything after the patch number —
-rc1, -beta, a build suffix — is a release still being cut, and nothing outside the branch cutting it
is expected to carry that number yet."""


def test_the_declared_version_keeps_up_with_the_public_releases():
    """The one declared version is the one nobody thinks to bump. Tags are what say which release a
    checkout is, so the manifest may equal the newest public release or run ahead of it (a bump
    prepared for the next one) — never behind, which is what shipping a stale number looks like."""
    tags = subprocess.run(["git", "tag", "--list", "v[0-9]*"], cwd=REPO,
                          capture_output=True, text=True).stdout.split()
    released = [m for m in (PUBLIC_RELEASE_TAG.match(t) for t in tags) if m]
    if not released:
        return  # a shallow clone, or a checkout with only pre-release tags, cannot judge this
    newest = max(tuple(int(g) for g in m.groups()) for m in released)
    declared = PUBLIC_RELEASE_TAG.match(
        json.loads((REPO / "gemini-extension.json").read_text(encoding="utf-8"))["version"])
    assert declared, "gemini-extension.json must declare a plain X.Y.Z version"
    assert tuple(int(g) for g in declared.groups()) >= newest, (
        f"gemini-extension.json says {declared.group(0)}, newest public release is "
        f"v{'.'.join(str(n) for n in newest)} — bump it")


def test_the_release_command_gates_on_the_declared_version():
    """The version check above can only fail once a tag exists, and a tag is immutable — so the
    release command is the only thing standing between a stale manifest and a permanent bad number.
    It gates twice, because the two failures are different: the file already behind the last release
    (stop before any drafting work is spent), and the file not yet naming the version just confirmed
    (stop before the tag). The edge itself lives in CLAUDE.md, where an agent that never runs this
    command still reads it."""
    release = text(REPO / ".claude" / "commands" / "release-now.md")
    flat = " ".join(release.split())

    assert "behind the newest `vX.Y.Z` tag ⇒ STOP before drafting anything" in flat, \
        "a manifest already behind the last release must stop the run before the note is written"
    assert "must read the version confirmed at Step 4" in flat, \
        "passing the first gate does not prove the file names the release being cut"
    assert release.index("gemini-extension.json") < release.index("## Step 2A"), \
        "the first gate must sit ahead of the drafting steps, or it stops nothing that matters"

    edge = " ".join(text(REPO / "CLAUDE.md").split())
    assert "A release tag and the declared version move together" in edge, \
        "the invariant must be readable without opening the release command"
    assert "the bump merges BEFORE the tag is pushed" in edge, \
        "the edge has to name the ordering, which is the whole of it"


def test_install_paths_have_one_owner():
    """Where a platform keeps its skills is stated twice: install-local.sh writes there, and the ROOT
    fallback in adapters/root.md looks there. They drifted apart once already, leaving the fallback
    unable to find any skills install."""
    script = (REPO / "scripts" / "install-local.sh").read_text(encoding="utf-8")
    targets = re.findall(r'printf \'%s\\n\' "\$HOME/([^"]+)"', script)
    assert targets, "install-local.sh no longer states its target directories"
    # the search command itself, not the prose around it: a path named in a nearby table would
    # otherwise satisfy this while the fallback still finds nothing
    row = [l for l in text(ADAPTER_ROOT).splitlines() if l.startswith("| 3 |")]
    assert len(row) == 1, "adapters/root.md has no single last-resort ROOT search"
    missing = [t for t in targets if t not in row[0]]
    assert not missing, f"the ROOT fallback cannot find installs in: {missing}"


def test_the_platform_question_is_asked_once_per_run():
    """--update replaces install-local.sh and hands over to the new copy, and the answer to the
    platform question does not survive that hand-over. Asked before the update, it is asked again
    after — the same menu twice for one install. Two things keep it to one: the update runs before
    anything is asked, and install.sh, which has already moved the clone itself, does not pass
    --update down to a second mover."""
    script = (REPO / "scripts" / "install-local.sh").read_text(encoding="utf-8")
    update = script.index('if [ "$ACTION" = update ]')
    ask = script.index("say 'Which platform?")
    assert update < ask, "install-local.sh asks which platform before the update hands over"

    bootstrap = (REPO / "install.sh").read_text(encoding="utf-8")
    assert re.search(r"^\s*--update\) shift ;;", bootstrap, re.M), (
        "install.sh forwards --update to install-local.sh, which then updates and re-execs a "
        "second time")


def test_an_install_off_the_release_channel_stays_there():
    """--ref installs a branch so a big change can be tried before it merges. Both scripts then have
    to read back what this clone follows, or the next update pulls the user onto a release and the
    branch they were testing is gone without a word."""
    for name in ("install.sh", "scripts/install-local.sh"):
        script = (REPO / name).read_text(encoding="utf-8")
        assert "config --get open-pr.ref" in script, f"{name} never reads back the ref it follows"
        assert re.search(r"config open-pr\.ref", script), f"{name} never records the ref it follows"
        assert "config --unset open-pr.ref" in script, (
            f"{name} offers no way back to the release channel")


def test_local_installer_covers_every_shim():
    """It discovers skills by glob, but its closing message names them. A fifth command must
    show up there too, or users never learn it exists."""
    script = (REPO / "scripts" / "install-local.sh").read_text(encoding="utf-8")
    missing = [p.parent.name for p in shim_files() if p.parent.name not in script]
    assert not missing, f"install-local.sh never mentions: {missing}"


def test_everything_a_run_needs_is_shipped_to_the_user():
    """install.sh checks out an include list, so a file added to this repository stays off a user's
    disk until it is named there — which is the point, and also the trap: a new manifest or entry
    directory that nobody adds to the list is simply missing at run time, on their machine only."""
    ship = re.search(r"^SHIP='(.*?)'", (REPO / "install.sh").read_text(encoding="utf-8"),
                     re.S | re.M)
    assert ship, "install.sh no longer states what it ships"
    entries = ship.group(1).split()
    needed = ["src", "skills", "commands", "adapters", "scripts/install-local.sh", *MANIFESTS]
    missing = [n for n in needed
               if not any(e.strip("/") == n or n.startswith(e.strip("/") + "/") for e in entries)]
    assert not missing, f"a run needs these, and install.sh does not ship them: {missing}"


def test_bootstrap_owns_no_platform_knowledge():
    """install.sh is the one-command entry: it fetches a clone and hands over. Every platform path
    stays in install-local.sh, or the two drift and the one-liner installs somewhere stale.

    Ending on `main "$@"` matters for a script served over the network: a download cut short then
    defines a function and does nothing, instead of running half an install."""
    body = (REPO / "install.sh").read_text(encoding="utf-8")
    assert "scripts/install-local.sh" in body, "the bootstrap must delegate, not install"
    leaked = [d for d in (".cursor/skills", ".agents/skills", ".cursor/plugins",
                          "antigravity-cli", ".gemini/config/skills") if d in body]
    assert not leaked, f"platform paths duplicated into install.sh: {leaked}"
    assert body.rstrip().endswith('main "$@"'), "a truncated download must not execute anything"


def test_adapter_layer_stays_out_of_the_claude_budget():
    """Claude Code installs src/ alone, so this layer must cost its runs nothing. A shim that
    migrated under src/ would be paid for by every review on every platform."""
    assert not list(SRC.glob("**/SKILL.md")), "a shim moved under src/ — Claude Code now pays for it"
    for scope_file in (ADAPTER_ROOT, *shim_files()):
        assert SRC not in scope_file.parents, f"{scope_file} sits under src/"
