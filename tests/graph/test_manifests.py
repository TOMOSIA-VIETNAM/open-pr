"""What a user sees before installing, and what the installer actually ships."""

import json
import re
import subprocess
import sys

from _common import REPO, SRC, TESTS, VENDORS, text, all_text, cli_text, dup_scan, SCENARIOS


def _manifests():
    plugin = json.loads((SRC / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    return plugin, market


def test_upgrade_confirms_before_writing():
    """An upgrade rewrites a repo's config, so the user answers first. Two options only —
    a hedging third ("maybe later, show me more") leaves the command with no defined next
    move. The ask must also come BEFORE the apply step, or consent arrives too late."""
    up = text(SRC / "commands" / "upgrade.md")
    assert "(Recommended)" in up, "the upgrade option must carry the recommendation marker"
    assert "`Not now`" in up, "the decline option must exist and be named"
    ask = up.index("## Step 4 — Summarise, then ask")
    apply_ = up.index("## Step 5 — Apply")
    assert ask < apply_, "the confirm step must precede the apply step"

    # the bare form can span several repos: the one question must name each of them,
    # and must stay one question — a repo picker on top of it is the hedge in disguise
    step4 = " ".join(up[ask:apply_].split())
    assert "NAMES every `<set>`" in step4, "the ask must enumerate what is in scope"
    assert "FORBIDDEN: a SECOND question" in step4, "selection and consent are one question"


def test_upgrade_finds_its_targets_without_a_git_remote():
    """The command takes no PR URL, and users call it from the workspace they review from —
    a directory with no git remote of its own. Config sits in the data directory, one
    subdirectory per repo. Bare form takes every set found; a named repo filters them."""
    up = text(SRC / "commands" / "upgrade.md")
    flat = " ".join(up.split())
    assert "open-pr.sh data-dir" in flat and "each subdirectory of `<data>`" in flat, \
        "the sets are read from the data directory, not searched for below pwd"
    assert "deriving `<repo>` from a git remote" in flat, \
        "a workspace has no remote to derive from — the ban must be stated"
    assert "FORBIDDEN: asking which" in flat, \
        "the bare form upgrades everything it found instead of asking"
    assert up.rstrip().endswith("ARGUMENTS: $ARGUMENTS"), \
        "a repo named on the command line must reach the prompt"
    assert flat.index("`ARGUMENTS`") < flat.index("## Step 2"), \
        "the selection step is what consumes the argument"


def test_bootstrap_defers_to_upgrade_on_a_premigration_repo():
    """A repo configured before settings.json existed has only meta.json, which a review run
    reads as never-bootstrapped. Bootstrapping over it re-asks every answer the user already
    gave, so the check must fire before the first question."""
    flat = " ".join(text(SRC / "setup" / "bootstrap.md").split())
    assert "meta.json" in flat, "bootstrap must recognise a pre-migration repo"
    assert flat.index("meta.json") < flat.index("## 1."), \
        "the check must precede the skeleton and the questions"
    assert "/open-pr:upgrade" in flat[:flat.index("## 1.")], \
        "bootstrap must hand that repo to /open-pr:upgrade"


def test_migrations_are_fetched_without_a_vendor_cli():
    """The plugin's own repo is on GitHub whatever vendor the user's PRs are on, so a
    GitLab-only user has no `gh` to authenticate. Raw HTTP needs neither."""
    atom = text(SRC / "core" / "llm-upgrades-index.md")
    assert "raw.githubusercontent.com" in atom, "the migration fetch must not need a vendor CLI"
    assert "curl -fsSL" in atom, "-f is what turns a 404 into a non-zero exit"
    # command text only: the prose names `gh api` in order to rule it out
    for snippet in re.findall(r"`([^`]+)`", atom) + re.findall(r"```\n(.*?)```", atom, re.S):
        assert "gh api" not in snippet, f"gh api is unavailable to a GitLab-only user: {snippet[:60]}"


def test_upgrade_refuses_to_outrun_the_installed_build():
    """Migrations are fetched live, so this command can move a config to a shape the
    installed prompts do not understand. It must compare against the build's own expected
    checkpoint and stop, or a stale plugin silently misreads every later review."""
    up = text(SRC / "commands" / "upgrade.md")
    assert "core/llm-upgrades-index.md" in up, \
        "upgrade must read the atom stating the installed build's checkpoint"
    flat = " ".join(up.split())
    assert "The plugin is older than the migrations available" in flat, \
        "the user must be told, in text, to update the plugin first"
    assert "STOP before applying" in flat, "upgrade must stop when the plugin is behind"


def test_migration_index_matches_the_files_on_disk():
    """`schema_version` is a checkpoint: upgrade collects every N above it. A version
    listed with no file makes that fetch 404 mid-migration; a file nobody lists never runs.
    Numbering starts at 1 and has no gaps, so "highest listed N" is the current shape."""
    up = REPO / "llm-upgrades"
    listed = [int(m) for m in re.findall(r"^- v(\d+):", (up / "index.md").read_text(), re.M)]
    on_disk = sorted(int(p.stem[1:]) for p in up.glob("v*.md"))
    assert listed == sorted(listed), f"index is out of order: {listed}"
    assert listed == list(range(1, len(listed) + 1)), f"versions must run 1..N with no gap: {listed}"
    assert listed == on_disk, f"index lists {listed}, files on disk are {on_disk}"

    schema = json.loads(re.search(r"```json\n(.*?)```", text(SRC / "reference/settings-schema.md"), re.S).group(1))
    assert schema["schema_version"] == listed[-1], \
        f"the schema example shows {schema['schema_version']}, highest migration is v{listed[-1]}"

    # a fresh bootstrap and upgrade's own guard both take the number from this atom
    stated = re.search(r"`schema_version` = (\d+)", text(SRC / "core" / "llm-upgrades-index.md"))
    assert stated, "the atom must state this build's config checkpoint"
    assert int(stated.group(1)) == listed[-1], \
        f"the build claims checkpoint {stated.group(1)}, highest migration is v{listed[-1]}"


def test_manifests_are_valid_and_agree():
    """These ship and are what a user sees before installing. Nothing else in the suite
    reads them, so a broken path or a renamed plugin would surface only on someone's
    failed install."""
    plugin, market = _manifests()
    for key in ("name", "description", "commands"):
        assert plugin.get(key), f"plugin.json is missing {key}"
    assert (SRC / plugin["commands"].lstrip("./")).is_dir(), plugin["commands"]

    listed = [p for p in market["plugins"] if p["name"] == plugin["name"]]
    assert listed, f"marketplace.json does not list {plugin['name']}"
    src = (REPO / listed[0]["source"].lstrip("./")).resolve()
    assert src == SRC, f"marketplace source points at {src}, not {SRC}"


def test_submodules_are_checked_out_only_when_bumped():
    """Every submodule is a full checkout on disk. Initialising all of them on every review
    multiplies the worktree's cost by the ones the PR never touched — so the only
    `submodule update` lives in the script's submodule checkout path, names ONE path, and is
    never recursive; no prompt runs one at all."""
    for name, body in all_text().items():
        assert "submodule update" not in body, f"{name} runs a submodule checkout itself"
    body = cli_text()
    cmds = [l for l in body.splitlines() if "submodule update" in l]
    assert cmds, "the bumped path has to be checked out somewhere"
    for c in cmds:
        assert "--recursive" not in c, f"nested submodules are out of scope: {c}"
        assert '-- "$sub"' in c, f"a bare --init checks out every submodule: {c}"
    sub = " ".join(text(SRC / "cases" / "submodule-review.md").split())
    assert "never gets a memory directory of its own" in sub, \
        "the worktree sits beside the project repo; a submodule holds no memory directory"


def test_every_reviewed_tree_is_gated_against_its_own_head_sha():
    """A tree on disk can be one the PR does not describe: the checkout errored, or the ref
    still served the previous commit. The script compares every tree it prepares to the head
    SHA fetched for THAT PR (one retry, then exit 2), and each caller states what exit 2 means
    for it — the main pass STOPs, a submodule pass is skipped while the main review continues."""
    body = cli_text()
    checkout = re.search(r"^cmd_checkout\(\) \{\n(.*?)^\}", body, re.M | re.S).group(1)
    assert "rev-parse HEAD" in checkout and "for attempt in 1 2" in checkout, \
        "the gate or its single retry is gone"
    assert "exit 2" in checkout, "a failed gate must exit 2"
    review = " ".join(text(SRC / "commands" / "review.md").split())
    assert "Exit 2 ⇒ STOP" in review, "review.md no longer stops on a failed gate"
    sub = " ".join(text(SRC / "cases" / "submodule-review.md").split())
    assert "Exit 2 ⇒ SKIP Step E + Step F" in sub and "MAIN PR's review continues unblocked" in sub, \
        "a submodule tree that stays mismatched drops its own pass, never the main PR's review"


def test_the_submodule_pass_reads_its_own_tree():
    """The reapplied Steps name `<worktree>/<path>` and `git -C "<worktree>"` — the PARENT repo, where
    the same path holds a different file. A submodule pass reading there would confirm line numbers and
    compare old findings against code from another repository, so its differences list carries the
    redirect, and the count that list states has to match what it holds."""
    sub = text(SRC / "cases" / "submodule-review.md")
    flat = " ".join(sub.split())
    assert "<worktree>/<submodule-path>/<path>" in flat, \
        "the submodule pass must name its own read root"
    assert "--worktree <worktree>/<submodule-path>" in flat, \
        "verify-line in the submodule pass must be aimed at the submodule's checkout"

    m = re.search(r"with exactly (\d+) differences:\n\n(.*?)\n\n", sub, re.S)
    assert m, "the reapply instruction must state how many differences it lists"
    listed = len(re.findall(r"^- ", m.group(2), re.M))
    assert int(m.group(1)) == listed, \
        f"the list says {m.group(1)} differences and holds {listed}"


def test_clean_deletes_worktrees_and_nothing_else():
    """This is the only command whose job is `rm`, standing in a directory that also holds the
    one thing here nobody can regenerate: what the repo taught it. A worktree comes back on the
    next review; memory does not come back at all. So the ban is named file by file, and the
    user answers before anything goes."""
    c = text(SRC / "commands" / "clean.md")
    flat = " ".join(c.split())
    for keep in ("memory.md", "memories/", "ALWAYS_RULE.md", "settings.json", "templates/"):
        assert keep in flat.split("## Step 1")[0], f"the CRITICAL block must rule out {keep}"
    assert "<data>/*/worktrees/" in flat, "the only deletable path must be named"
    ask = c.index("## Step 3")
    assert c.index("## Step 4 — Remove") > ask, "the ask must come before the removal"
    assert "(Recommended)" in c and "`Keep them`" in c, "two options, one of them recommended"
    assert "worktree prune" in flat, \
        "a removed checkout leaves a registration behind in the reviewed repo"
    # review.md points at it and must not do the deleting itself
    r = " ".join(text(SRC / "commands" / "review.md").split())
    assert "/open-pr:clean" in r, "the run that creates a worktree must say what removes it"
    assert "removing the worktree, or asking to" in r, \
        "review must leave the decision to the user, not prompt for it every run"


def test_docs_exist_in_every_language_and_their_links_resolve():
    """The READMEs hand their reference material to docs/, one tree per language. A page
    translated in one language and not another leaves that reader at a 404, and a relative
    link written at the wrong depth (a translated tree is two levels down, docs/ is one)
    breaks silently — GitHub renders the text and only the click fails."""
    en = sorted(p.name for p in (REPO / "docs").glob("*.md"))
    assert en, "docs/ holds no English page"
    # every translated tree is discovered, so adding a language cannot skip the check
    langs = sorted(d.name for d in (REPO / "docs").iterdir()
                   if d.is_dir() and d.name != "images")
    assert langs, "docs/ holds no translated tree"
    for lang in langs:
        got = sorted(p.name for p in (REPO / "docs" / lang).glob("*.md"))
        assert got == en, f"docs/{lang} has {got}, English has {en}"

    readmes = sorted(p.name for p in REPO.glob("README*.md"))
    assert len(readmes) == len(langs) + 1, \
        f"{readmes} does not pair with docs trees {langs} plus English"
    pages = [REPO / f for f in readmes]
    pages += sorted((REPO / "docs").rglob("*.md"))
    dead = []
    for page in pages:
        body = re.sub(r"```.*?```", "", text(page), flags=re.S)   # mermaid uses [] too
        for m in re.finditer(r"\[[^\]]+\]\((\.[^)#]+)\)", body):
            if not (page.parent / m.group(1)).resolve().exists():
                dead.append(f"{page.relative_to(REPO)} → {m.group(1)}")
    assert not dead, f"links that resolve to nothing: {dead}"


def test_scans_skip_a_checkout_parked_inside_the_tree():
    """An agent puts its isolated worktree under `.claude/worktrees/`. That is a full copy of
    this repo, so a scan reaching into it reports our own prose as duplicated against itself and
    reddens the gate for a change nobody made. Real occurrence, not hypothetical. The probe has
    to sit under REPO — `in_nested_checkout` judges by REPO — so it cleans up behind itself
    rather than taking a tmp_path it cannot use."""
    nested = REPO / ".claude" / "worktrees" / "__guard_probe__"
    md = nested / "doc.md"
    parent_existed = nested.parent.exists()
    try:
        nested.mkdir(parents=True, exist_ok=True)
        (nested / ".git").write_text("gitdir: /nowhere\n")     # what `git worktree add` leaves
        md.write_text("# probe\n\n" + "the same sentence repeated verbatim many times over. " * 30)
        assert md not in dup_scan.md_files("dev"), \
            "the dev scan must not read a checkout parked inside the tree"
    finally:
        for f in (md, nested / ".git"):
            f.unlink(missing_ok=True)
        if nested.exists():
            nested.rmdir()
        if not parent_existed and nested.parent.exists():
            nested.parent.rmdir()


def test_the_chart_push_guard_reads_a_trimmed_status_line():
    """An unstaged file's porcelain status starts with a space, and the helper that runs git
    trims the whole output — so the first line arrives one character short. Slicing a fixed
    offset then cut into the path and the guard rejected the exact two files it exists to
    allow, which is the only push to main this repo permits."""
    sys.path.insert(0, str(REPO / "scripts"))
    import token_chart  # noqa: E402
    want = ["tests/token-history.json", "token-history.svg"]
    trimmed = "M tests/token-history.json\n M token-history.svg"
    intact = " M tests/token-history.json\n M token-history.svg"
    for status in (trimmed, intact):
        assert token_chart.porcelain_paths(status) == want, f"misread: {status!r}"
    assert token_chart.porcelain_paths("?? docs/a b.md") == ["docs/a b.md"], \
        "a path with a space in it must survive"


def test_every_scenario_is_owned_by_a_chart_line():
    """A scenario the chart does not recognise used to fall into `review`, so adding a command
    moved a line that is supposed to describe review alone — and the release that recorded it
    would have frozen the wrong number for good."""
    sys.path.insert(0, str(REPO / "scripts"))
    import token_chart  # noqa: E402
    for name in SCENARIOS:
        token_chart.group_of(name)          # raises if no line owns it
    keys = {l["key"] for l in token_chart.LINES}
    cmds = {p.stem for p in (SRC / "commands").glob("*.md")}
    assert cmds <= keys, f"commands with no line on the chart: {cmds - keys}"


def test_token_history_is_frozen_and_its_chart_matches():
    """The chart in the READMEs is the repo's own claim about its context cost, so it has
    to be checkable: every point a real tag, ordered, measured once, and an image that is
    exactly what those numbers draw. A hand-edited SVG, or numbers changed without redrawing,
    is a published figure nobody can reproduce."""
    sys.path.insert(0, str(REPO / "scripts"))
    import token_chart  # noqa: E402

    data = json.loads((TESTS / "token-history.json").read_text())
    points = data["points"]
    assert points, "the history has no points"
    assert data.get("_note"), "the note is what stops a rerun being read as a contradiction"

    tags = subprocess.run(["git", "-C", str(REPO), "tag", "--list"],
                          capture_output=True, text=True, check=True).stdout.split()
    # a release PR prepares its own point: only the last one, and only the declared version
    prepared = points[-1]["tag"] == token_chart.declared_tag()
    for p in points[:-1] if prepared else points:
        assert p["tag"] in tags, f"{p['tag']} is not a tag in this repo"
        for line in token_chart.LINES:
            v = p.get(line["key"])
            assert v is None or v > 0, f"{p['tag']}.{line['key']} = {v}: use null, never 0"
    keys = [token_chart.version_key(p["tag"]) for p in points]
    assert keys == sorted(keys), f"points are out of order: {[p['tag'] for p in points]}"
    assert len(set(keys)) == len(keys), "a tag appears twice — a point is measured once"

    before = token_chart.SVG.read_text()
    token_chart.render(data)          # redraws from the stored numbers alone
    after = token_chart.SVG.read_text()
    if before != after:
        token_chart.SVG.write_text(before)
        raise AssertionError("token-history.svg is not what these numbers draw — "
                             "run scripts/token_chart.py --render")


def test_install_instructions_match_the_manifests():
    """Every line a user is told to type carries an id built from the two manifests —
    `<plugin>@<marketplace>` to install, the marketplace name alone to update it. Rename
    either manifest and these strings become a failed install nobody notices until someone
    types one. The plugin's own stale-build message is the worst case: it is printed to
    somebody already stuck."""
    plugin, market = _manifests()
    pid = f"{plugin['name']}@{market['name']}"
    files = [SRC / "commands" / "upgrade.md", REPO / ".claude" / "commands" / "release-now.md"]
    files += sorted(REPO.glob("README*.md"))
    for f in files:
        body = text(f)
        for m in re.finditer(r"/plugin (?:install|update) ([\w@.-]+)", body):
            assert m.group(1) == pid, f"{f.name}: `{m.group(0)}` should name {pid}"
        for m in re.finditer(r"/plugin uninstall ([\w@.-]+)", body):
            assert m.group(1) == plugin["name"], \
                f"{f.name}: `{m.group(0)}` should name {plugin['name']}"
        # `marketplace remove` is exempt: it retires a registration under whatever name the
        # user installed it as, which is exactly the name this manifest no longer carries
        for m in re.finditer(r"/plugin marketplace update ([\w@.-]+)", body):
            assert m.group(1) == market["name"], \
                f"{f.name}: `{m.group(0)}` should name {market['name']}"


def test_manifest_descriptions_name_every_vendor():
    """The descriptions said "GitHub" alone for as long as GitLab had been supported.
    A vendor directory is the fact; the prose has to keep up with it."""
    plugin, market = _manifests()
    texts = {"plugin.json": plugin["description"] + plugin.get("displayName", "")}
    for p in market["plugins"]:
        texts[f"marketplace.json[{p['name']}]"] = p["description"]
    missing = {}
    for where, text in texts.items():
        # A directory name is one token; prose may spell the same vendor with a space. Compare
        # on the flattened form so both spellings count as naming it.
        flat = text.lower().replace("-", " ")
        absent = [v for v in VENDORS if v.replace("-", " ") not in flat]
        if absent:
            missing[where] = absent
    assert not missing, f"description does not mention every supported vendor: {missing}"
