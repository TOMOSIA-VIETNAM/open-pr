"""Static invariants of the prompt graph under src/.

There is no runtime to exercise here — the "program" is a set of markdown files an
agent Reads in a particular order. What CAN be tested mechanically is the graph
itself: that every reference resolves, that both vendors expose the same
interface, that no rule is stated in two places, and that a run's context cost
has not silently inflated. Agent BEHAVIOUR (does it obey the rules, is a finding
any good) is out of scope — that needs live evals against real PRs.

Run: pytest tests/ -q     or     python3 tests/test_prompt_graph.py
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
TESTS = REPO / "tests"

sys.path.insert(0, str(REPO / "scripts"))
import dup_scan  # noqa: E402
from token_report import ROLES, SCENARIOS, scenario_totals  # noqa: E402

VENDORS = sorted(p.name for p in (SRC / "vendors").iterdir() if p.is_dir())
GROUPS = ("fetch", "worktree", "post", "thread")

# Files no scenario can put a number on. reference/ is for humans and a run must
# never pay for it. seeds/memory.md is `cp`-ed into the reviewed repo and read back
# only as that repo's own memory index, whose real size the team drives, not us.
NEVER_LOADED = {"reference/settings-schema.md", "reference/vendor-interface.md",
                "seeds/memory.md"}


def md_files():
    return sorted(p for p in SRC.rglob("*.md"))


def rel(p):
    return str(p.relative_to(SRC))


def text(p):
    return p.read_text(encoding="utf-8")


def all_text():
    return {rel(p): text(p) for p in md_files()}


def vendor_headings(vendor, group):
    f = SRC / "vendors" / vendor / f"{group}.md"
    return [h.strip() for h in re.findall(r"^## (.+)$", text(f), re.M)]


# --------------------------------------------------------------------------- #
# reference integrity
# --------------------------------------------------------------------------- #

def test_plugin_root_refs_exist():
    """Every ${CLAUDE_PLUGIN_ROOT}/<path> the agent is told to Read must exist."""
    missing = []
    for name, body in all_text().items():
        for m in re.finditer(r'CLAUDE_PLUGIN_ROOT\}"?/([A-Za-z0-9_./<>-]+)', body):
            ref = m.group(1)
            if "<" in ref or ref.endswith("/"):
                continue  # resolved at run time (vendor / stack placeholders)
            if not (SRC / ref).exists():
                missing.append((name, ref))
    assert not missing, f"dangling plugin-root refs: {missing}"


def test_backtick_file_refs_exist():
    """A `dir/file.md` mentioned in prose must resolve — catches a moved file."""
    missing = []
    for name, body in all_text().items():
        for m in re.finditer(r"`((?:core|cases|setup|commands|reference)/[a-z-]+\.md)`", body):
            if not (SRC / m.group(1)).exists():
                missing.append((name, m.group(1)))
    assert not missing, f"dangling prose refs: {missing}"


def test_section_refs_resolve():
    """`core/pr-target.md` §2 must point at a real numbered heading."""
    bad = []
    for name, body in all_text().items():
        for m in re.finditer(r"`((?:core/)?[a-z-]+\.md)` §(\d)", body):
            target = SRC / m.group(1)
            if not target.exists() or not re.search(rf"^## {m.group(2)}\.", text(target), re.M):
                bad.append((name, m.group(0)))
    assert not bad, f"unresolvable section refs: {bad}"


def test_reference_dir_is_read_only_by_update_plugin():
    """A review or fix run must never pay for the schema doc. upgrade is the one
    command whose job IS the schema — it reads the installed build's expected checkpoint
    from there to refuse running when the plugin is older than the migrations."""
    for name, body in all_text().items():
        if name == "commands/upgrade.md":
            continue
        assert "CLAUDE_PLUGIN_ROOT}/reference/" not in body.replace('}"', "}"), name


# --------------------------------------------------------------------------- #
# vendor interface
# --------------------------------------------------------------------------- #

def test_vendor_entry_parity():
    """Each group file exposes the SAME entries on every vendor, same order.

    This is the test that fails when someone adds an entry to one vendor and
    forgets the other — the failure mode that silently breaks the other vendor
    at run time, since callers address entries by name only.
    """
    for group in GROUPS:
        per_vendor = {v: vendor_headings(v, group) for v in VENDORS}
        first = per_vendor[VENDORS[0]]
        for v in VENDORS[1:]:
            assert per_vendor[v] == first, (
                f"{group}: {v} entries differ from {VENDORS[0]}\n"
                f"  only in {VENDORS[0]}: {set(first) - set(per_vendor[v])}\n"
                f"  only in {v}: {set(per_vendor[v]) - set(first)}"
            )


def test_v_notation_resolves():
    """Every V§"entry" a caller uses exists in exactly 1 group of every vendor."""
    index = {}
    for v in VENDORS:
        for g in GROUPS:
            for h in vendor_headings(v, g):
                index.setdefault(h, set()).add((v, g))
    used = set()
    for body in all_text().values():
        used |= {m.group(1) for m in re.finditer(r'V§"([^"<]+)"', body)}
    bad = {}
    for entry in used:
        where = index.get(entry, set())
        if {v for v, _ in where} != set(VENDORS) or len({g for _, g in where}) != 1:
            bad[entry] = sorted(where)
    assert not bad, f"V§ entries not uniformly resolvable: {bad}"


def test_every_vendor_entry_has_a_caller():
    """An entry nobody calls is dead weight shipped to every user."""
    entries = {h for v in VENDORS for g in GROUPS for h in vendor_headings(v, g)}
    callers = "".join(
        body for name, body in all_text().items()
        if not name.startswith("vendors/") and name not in NEVER_LOADED
    )
    orphans = [e for e in sorted(entries) if f'"{e}"' not in callers]
    assert not orphans, f"vendor entries never referenced by a caller: {orphans}"


def test_interface_doc_matches_vendor_files():
    doc = text(SRC / "reference/vendor-interface.md")
    documented = {(m.group(1), m.group(2).strip())
                  for m in re.finditer(r"^\| (fetch|worktree|post|thread) \| ([^|]+) \|", doc, re.M)}
    actual = {(g, h) for g in GROUPS for h in vendor_headings(VENDORS[0], g)}
    assert documented == actual, (
        f"interface doc drifted\n  doc-only: {documented - actual}\n  file-only: {actual - documented}"
    )


# --------------------------------------------------------------------------- #
# single source of truth
# --------------------------------------------------------------------------- #

DEFAULT_LITERALS = {
    "`30`": {"core/repo-settings.md", "setup/bootstrap.md"},
    "`20`": {"core/repo-settings.md", "setup/bootstrap.md"},
    '`"1 months"`': {"core/repo-settings.md", "setup/bootstrap.md"},
}


def test_config_defaults_have_one_source():
    """A default value lives where it is read (core/) and where it is asked
    (setup/); a third copy is how the old tree drifted out of sync."""
    for literal, allowed in DEFAULT_LITERALS.items():
        found = {n for n, b in all_text().items() if literal in b} - NEVER_LOADED
        assert found <= allowed, f"{literal} also appears in {found - allowed}"


def test_glab_api_never_uses_the_gh_only_jq_flag():
    """`gh api` accepts --jq; `glab api` does not — its own help tells you to pipe to
    jq. The flag is easy to copy across while porting an entry, and it fails at the
    FIRST fetch on the vendor half that gets exercised least."""
    bad = []
    for name, body in all_text().items():
        # Only real command text counts: prose may name the flag to warn against it.
        snippets = re.findall(r"`([^`]+)`", body) + re.findall(r"```[a-z]*\n(.*?)```", body, re.S)
        for s in snippets:
            flat = " ".join(s.split())
            if "glab api" in flat and "--jq" in flat:
                bad.append((name, "glab api + --jq", flat[:80]))
            # Verified against glab 1.110: `mr view --jq` alone errors with
            # "Using --jq requires --output=json".
            if "glab mr view" in flat and "--jq" in flat and "--output json" not in flat:
                bad.append((name, "mr view --jq without --output json", flat[:80]))
    assert not bad, f"invalid glab flag combination: {bad}"


SEVERITY_HEADINGS = ["#### 🔴 MUST FIX", "#### 🟠 SHOULD FIX",
                     "#### 🔵 SUGGESTION", "#### 📝 NOTE"]


def test_overview_headings_carry_emoji_and_label():
    """A grouping heading names the severity for someone skimming the PR body; an
    individual finding carries the emoji alone, because its description already says what
    the problem is. The two got conflated once in each direction, so both halves are
    pinned: review.md's own structure block, and every case file that writes into it."""
    review = text(SRC / "commands" / "review.md")
    for h in SEVERITY_HEADINGS:
        assert h in review, f"review.md's structure block lost {h!r}"
    labels = {h.split(" ", 2)[2] for h in SEVERITY_HEADINGS}   # drop "####" and the emoji
    for p in sorted((SRC / "cases").glob("*.md")):
        for m in re.finditer(r"`#### ([🔴🟠🔵📝])([^`]*)`", text(p)):
            assert m.group(2).strip() in labels, \
                f"{rel(p)}: heading {m.group(0)!r} has no severity label"


def test_markers_are_byte_identical_everywhere():
    """The bot markers are the plugin's cross-run identity — a variant spelling
    makes past findings invisible to re-review and fix."""
    for marker in ("<!-- bot-finding -->", "<!-- bot-reply -->"):
        core = marker.strip("<!- >")
        for name, body in all_text().items():
            for m in re.finditer(rf"<!--\s*{re.escape(core)}\s*-->", body):
                assert m.group(0) == marker, f"{name}: {m.group(0)!r} != {marker!r}"


def _axis_names(body):
    return {int(m.group(1)): m.group(2).strip()
            for m in re.finditer(r"^#### (\d)\. (.+)$", body, re.M)}


def test_template_axes_match_the_baseline():
    """A stack template contributes to the baseline's OWN axes.

    Axis names used to drift per template (tests under 5 in one file, 6 in
    another), which made the 6-axis framework useless as a coverage device —
    same numbers, different meanings. Axis 5 is the template's own, so its name
    is free; every other axis it defines must be the baseline's axis.
    """
    baseline = _axis_names(text(SRC / "core/review-criteria.md"))
    assert set(baseline) == {1, 2, 3, 4, 5, 6}, f"baseline axes: {sorted(baseline)}"
    bad = []
    for p in sorted((SRC / "templates").glob("*.md")):
        for n, name in _axis_names(text(p)).items():
            if n != 5 and name != baseline[n]:
                bad.append((rel(p), n, name, baseline[n]))
    assert not bad, f"axis name drift (file, axis, found, expected): {bad}"


def test_seeds_carry_no_criteria_and_no_config():
    """A seed is `cp`-ed verbatim into the reviewed repo and then belongs to the
    team. Criteria inside one would freeze per repo, beyond the plugin's reach;
    a config placeholder inside one would be config living outside settings.json."""
    seeds = sorted((SRC / "seeds").glob("*.md"))
    assert seeds, "src/seeds/ is empty"
    for p in seeds:
        body = text(p)
        assert "####" not in body, f"{rel(p)} must not carry review criteria"
        assert "{{" not in body, f"{rel(p)} must not carry a config placeholder"


def test_seeds_are_copied_never_read():
    """`cp` keeps a seed's content out of context. A `Read` of one would pay for
    it in tokens for no reason."""
    for name, body in all_text().items():
        for m in re.finditer(r'(\w+)\s+`?"?\$\{CLAUDE_PLUGIN_ROOT\}"?/seeds/', body):
            assert m.group(1) == "cp", f"{name}: seeds reached via {m.group(1)}, expected cp"


def test_no_unapproved_cross_file_duplication():
    """The same rule owned by two files. Accepted cases live in
    duplication_allowlist.json WITH a reason; an unexplained one means a rule has
    two owners and they will drift."""
    found = dup_scan.scan("cross")
    assert not found, "unapproved cross-file duplication:\n" + _fmt(found)


def test_no_unapproved_intra_file_duplication():
    """The same rule restated inside one file, where both copies read as if they
    belong. Only near-verbatim repeats surface — see scripts/dup_scan.py."""
    found = dup_scan.scan("intra")
    assert not found, "unapproved repeat inside one file:\n" + _fmt(found)


def test_no_unapproved_duplication_in_dev_docs():
    """CLAUDE.md never ships and never enters the token budget, but every session
    working on this plugin loads it, so a duplicate there is paid over and over."""
    found = dup_scan.scan("both", scope="dev")
    assert not found, "unapproved duplication in dev docs:\n" + _fmt(found)


def _fmt(found):
    return "\n".join(
        f"  ~{f['waste']} tok  {f['occurrences'][0][0]}:{f['occurrences'][0][1]}"
        f" + {f['occurrences'][1][0]}:{f['occurrences'][1][1]}  {f['run'][:90]}…"
        for f in found[:15])


# --------------------------------------------------------------------------- #
# durability of the files themselves
# --------------------------------------------------------------------------- #

EPHEMERAL = [
    (r"\bT[0-9]\b", "task id"),
    (r"\bPhase [0-9]", "plan phase"),
    (r"PR #[0-9]+", "a specific PR number"),
    (r"\b(?:backlogs|SPEC)/", "a doc that gets deleted"),
]


def test_no_refs_to_things_that_get_deleted():
    """These files outlive any plan or ticket that motivated them; a ref to a
    task id or a design-doc section becomes unresolvable for the next reader."""
    bad = []
    for name, body in all_text().items():
        for pattern, why in EPHEMERAL:
            for m in re.finditer(pattern, body):
                bad.append((name, m.group(0), why))
    assert not bad, f"refs to ephemeral things: {bad}"


ENGLISH_IN_OUTPUT = [
    (r"as of commit", 'the commit anchor is language-neutral: "(commit <link>)"'),
    (r"Reviewed at commit", "same — no English connective in the anchor"),
]


def test_bounded_questions_go_through_the_choice_feature():
    """A question with a fixed set of answers must reach the user as a choice with one
    option marked `(Recommended)`. Prose phrasings like "WAIT for yes/no" invited exactly
    the free-form version — a well-judged lesson proposal ending "Ghi hay bỏ?" instead of
    two options the user could click.
    """
    assert "(Recommended)" in text(SRC / "core" / "guardrails.md"), \
        "guardrails.md must state the marker the options carry"
    bad = []
    for name, body in all_text().items():
        flat = " ".join(body.split())
        for tell in ("yes/no", "Ghi hay bỏ"):
            if tell in flat:
                bad.append(f"{name} — {tell!r} reads as a prose question")
    assert not bad, "bounded question asked in prose:\n  " + "\n  ".join(bad)


def test_emoji_in_output_are_single_codepoint():
    """The overview opener was a 5-codepoint ZWJ sequence — bowing person, skin tone,
    ZWJ, male sign, variation selector — and it reached a PR as broken glyphs. A client
    or font missing any part of the sequence shows the parts.

    Emoji the plugin PRINTS must be one codepoint, like the severity set. Skin-tone
    modifiers and ZWJ joiners are the two that break, so both are refused.
    """
    bad = []
    for name, body in all_text().items():
        for i, line in enumerate(body.splitlines(), 1):
            if "\u200d" in line:
                bad.append(f"{name}:{i} — ZWJ joiner")
            if any(0x1F3FB <= ord(c) <= 0x1F3FF for c in line):
                bad.append(f"{name}:{i} — skin-tone modifier")
    assert not bad, "emoji that render as parts on some clients:\n  " + "\n  ".join(bad)


def test_review_writes_at_the_invocation_directory():
    """Standing in a workspace and reviewing three repos must leave ONE
    notebooks/review/ there holding all three. A version of this that `cd`-ed into the
    repo put the memory inside the repo instead, which is both a behaviour change and a
    split from where a later fix looks.

    So review.md may not `cd`, and its git calls against the reviewed repo must be aimed
    with -C. locate-repo.md yields the directory and decides nothing, because fix.md needs
    the opposite — it edits that repo's files and works from inside it.
    """
    atom = text(SRC / "core" / "locate-repo.md")
    assert "`<repo_dir>`" in atom, "locate-repo.md must yield a named directory"
    assert "cd` into" not in atom, "locate-repo.md decides for its callers; it must not"

    review = text(SRC / "commands" / "review.md")
    assert "FORBIDDEN: `cd`" in review, "review.md must forbid cd — it writes at pwd"
    # the aimed forms must be the ones Step 1 issues; a bare form would run against pwd,
    # which in a workspace is not a repo at all
    for cmd in ('git -C "<repo_dir>" worktree add', 'git -C "<repo_dir>" fetch origin'):
        assert cmd in review, f"review.md does not aim: {cmd}"
    assert 'git worktree add "notebooks' not in review, "review.md still has an un-aimed worktree add"


def test_fix_suggestions_prefer_a_code_fence():
    """A finding whose Fix is prose makes the dev reconstruct the intended logic. The
    fence is the default; prose is for fixes with no code form."""
    step7 = text(SRC / "commands" / "review.md")
    assert "shows the corrected CODE in a fence by default" in step7
    assert "FORBIDDEN: prose when the" in step7, "prose must be the exception, not a sibling option"


def test_chat_does_not_repeat_the_posted_findings():
    """The finding text is on the PR. Restating it in chat doubles the output for a reader
    who already has the better copy."""
    review = text(SRC / "commands" / "review.md")
    flat = " ".join(review.split())
    assert "FORBIDDEN: repeating any finding's description or its Fix" in flat, \
        "Step 9 must forbid restating findings in chat"


def test_posted_output_hardcodes_no_english_connective():
    """A review is posted in the repo's output language, so a phrase the rules pin in
    English ships English into a Vietnamese or Japanese review. It reached a real PR as
    `LGTM 🌟 (as of commit c5ba906)`.

    Prose carries the meaning in the output language; the bare anchor stays
    `(commit <link>)`, which needs no translating. Only text that ends up ON the PR is
    covered — the rules describing it are written in English by design.
    """
    bad = []
    for name in ("commands/review.md", "cases/re-review.md", "cases/submodule-review.md",
                 "cases/pr-template-checklist.md", "cases/large-diff-guards.md"):
        body = text(SRC / name)
        for pattern, why in ENGLISH_IN_OUTPUT:
            for m in re.finditer(pattern, body, re.I):
                bad.append(f"{name}:{body[:m.start()].count(chr(10)) + 1} — {why}")
    assert not bad, "English pinned into posted output:\n  " + "\n  ".join(bad)


def test_no_harness_auto_exec_syntax():
    """`` !`cmd` `` in a slash-command body is executed by the harness before the model
    ever sees the file. A `!` used as logical NOT next to a backticked field name reads
    as exactly that, and the command dies on `command not found` at the step containing
    it — which is how this reached a real PR review.

    Negation gets spelled out instead. The saving from an operator is a few tokens; the
    cost is the command not running at all.
    """
    bad = []
    for name, body in all_text().items():
        for m in re.finditer(r"!`", body):
            line = body[:m.start()].count("\n") + 1
            bad.append(f"{name}:{line}")
    assert not bad, ("`!` immediately before a backtick is auto-exec syntax; write the negation "
                     f"in words: {bad}")


def test_frontmatter_only_in_commands():
    """Frontmatter is what makes a file a slash command; a stray one exposes a
    helper file as a user-visible command."""
    for p in md_files():
        has = text(p).startswith("---\n")
        assert has == rel(p).startswith("commands/"), f"{rel(p)}: frontmatter={has}"


def test_every_file_is_reachable_from_a_command():
    """A file nothing leads to still ships to every user and still rots."""
    graph, files = {}, {rel(p) for p in md_files()}
    for name, body in all_text().items():
        out = set()
        for m in re.finditer(r'CLAUDE_PLUGIN_ROOT\}"?/([A-Za-z0-9_./<>-]+)', body):
            ref = m.group(1)
            if ref == "vendors/<git_remote_type>.md" or "<" in ref or ref.endswith("/"):
                continue
            out.add(ref)
        for m in re.finditer(r"`((?:core|cases|setup|commands|reference)/[a-z-]+\.md)`", body):
            out.add(m.group(1))
        if "V§" in body:  # vendor group files are addressed by entry name, not path
            out |= {f"vendors/{v}/{g}.md" for v in VENDORS for g in GROUPS}
        if "templates/<stack>.md" in body or "${CLAUDE_PLUGIN_ROOT}/templates/" in body:
            out |= {f for f in files if f.startswith("templates/")}
        graph[name] = out & files

    seen, stack = set(), [f for f in files if f.startswith("commands/")]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(graph.get(n, ()))
    unreachable = files - seen - NEVER_LOADED
    assert not unreachable, f"unreachable files: {sorted(unreachable)}"


def test_diff_fetch_is_size_gated_in_every_vendor():
    """A patch that reaches the terminal is in context for the rest of the run, and the
    Step 7 guard fires long after Context has already paid for it. So the omission has to
    live inside the fetch command itself.

    Measured on the e2e fixture: an ungated fetch pulled 30,517 tokens for one 86KB dump,
    against 8,833 tokens for every prompt file a review loads. The data half of a run's
    cost dwarfs the prompt half, and only this makes it bounded.
    """
    for v in VENDORS:
        body = text(SRC / "vendors" / v / "fetch.md")
        assert "<max_patch_bytes>" in body, f"{v}: the diff entry takes no size threshold"
        entry = [p for p in re.split(r"\n(?=## )", body) if "<max_patch_bytes>" in p]
        assert entry, v
        cmd = " ".join(" ".join(entry[0].split()).split())
        assert "select" in cmd, f"{v}: the threshold is named but nothing filters on it"


# An entry is bounded when its output cannot grow with the PR. Either the command filters
# or projects, or its shape caps it: one value, one line per file, one line per commit.
# Anything else has to say what bounds it, in the entry, so a reader can check the claim.
BOUNDED_BY_SHAPE = {
    "Fetch PR head commit SHA", "Fetch account running the command",
    "Fetch PR diff — file list", "Fetch PR diff size per file",
    "Fetch PR commits headlines",
}
# Entries that legitimately return everything, because the caller filters on content it
# cannot predict. Each is a deliberate cost, so each is named here rather than assumed.
UNBOUNDED_BY_DESIGN = {
    "Fetch PR review comments (LINE-level findings)",  # every past finding must be matched
    "Fetch review threads (id + isResolved + comment ids)",
    "Fetch PR reviews (FILE-level findings + review_id)",
    "Fetch CI checks",  # the caller filters bucket==fail itself, and bootstrap counts them
}


def test_every_fetch_entry_is_bounded_or_declared():
    """The diff entry pulled 30,517 tokens on a 5-file fixture because nothing said a fetch
    must bound its output. This makes that explicit for every entry, so the next unbounded
    one is a deliberate, listed decision instead of an oversight."""
    loose = []
    for v in VENDORS:
        body = text(SRC / "vendors" / v / "fetch.md")
        for part in re.split(r"\n(?=## )", body)[1:]:
            head = part.splitlines()[0][3:].strip()
            if not head.startswith("Fetch"):
                continue
            if head in BOUNDED_BY_SHAPE or head in UNBOUNDED_BY_DESIGN:
                continue
            flat = " ".join(part.split())
            if not any(k in flat for k in ("select", "| jq '{", "--json", "No equivalent")):
                loose.append((v, head))
    assert not loose, (
        "fetch entry neither filters nor is listed as bounded/unbounded by design: " + str(loose))


def test_size_entry_never_reports_zero_for_a_withheld_patch():
    """GitLab collapses a large diff and returns diff: "", whose length reads 0 — which
    would place the biggest file in the PR under every threshold, so it is neither
    reviewed nor listed as skipped. Whatever a vendor calls that state, the size entry
    must map it to UNKNOWN."""
    for v in VENDORS:
        body = text(SRC / "vendors" / v / "fetch.md")
        entry = [p for p in re.split(r"\n(?=## )", body) if p.startswith("## Fetch PR diff size")]
        assert entry, f"{v} has no size entry"
        assert "UNKNOWN" in entry[0], f"{v}: size entry has no UNKNOWN branch"


# --------------------------------------------------------------------------- #
# the shipped manifests
# --------------------------------------------------------------------------- #

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


def test_migrations_are_fetched_without_a_vendor_cli():
    """The plugin's own repo is on GitHub whatever vendor the user's PRs are on, so a
    GitLab-only user has no `gh` to authenticate. Raw HTTP needs neither."""
    atom = text(SRC / "core" / "llm-upgrades-index.md")
    assert "raw.githubusercontent.com" in atom, "the migration fetch must not need a vendor CLI"
    assert "curl -fsSL" in atom, "-f is what turns a 404 into a non-zero exit"
    # command text only: the prose names `gh api` in order to rule it out
    for snippet in re.findall(r"`([^`]+)`", atom) + re.findall(r"```\n(.*?)```", atom, re.S):
        assert "gh api" not in snippet, f"gh api is unavailable to a GitLab-only user: {snippet[:60]}"


def test_update_plugin_refuses_to_outrun_the_installed_build():
    """Migrations are fetched live, so this command can move a config to a shape the
    installed prompts do not understand. It must compare against the build's own expected
    checkpoint and stop, or a stale plugin silently misreads every later review."""
    up = text(SRC / "commands" / "upgrade.md")
    assert "CLAUDE_PLUGIN_ROOT}\"/reference/settings-schema.md" in up, \
        "upgrade must read the installed build's expected checkpoint"
    flat = " ".join(up.split())
    assert "older than the index" in flat and "STOP before applying" in flat, \
        "upgrade must stop when the plugin is behind"


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


def test_manifest_descriptions_name_every_vendor():
    """The descriptions said "GitHub" alone for as long as GitLab had been supported.
    A vendor directory is the fact; the prose has to keep up with it."""
    plugin, market = _manifests()
    texts = {"plugin.json": plugin["description"] + plugin.get("displayName", "")}
    for p in market["plugins"]:
        texts[f"marketplace.json[{p['name']}]"] = p["description"]
    missing = {}
    for where, text in texts.items():
        absent = [v for v in VENDORS if v not in text.lower()]
        if absent:
            missing[where] = absent
    assert not missing, f"description does not mention every supported vendor: {missing}"


# --------------------------------------------------------------------------- #
# context-cost regression
# --------------------------------------------------------------------------- #

def test_scenario_token_budgets():
    """A refactor that reads well but inflates what a run loads is a regression.
    Budgets in budgets.json are ceilings measured with scripts/token_report.py;
    lower them deliberately when a change wins tokens back."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    per_file = {rel(p): len(enc.encode(text(p))) for p in md_files()}
    totals = scenario_totals(per_file)
    budgets = json.loads((TESTS / "budgets.json").read_text())
    over = {
        name: (totals[name]["tokens"], budgets["scenarios"][name])
        for name in SCENARIOS
        if totals[name]["tokens"] > budgets["scenarios"][name]
    }
    assert not over, f"over budget (actual, ceiling): {over}"

    mean = sum(t["tokens"] for t in totals.values()) / len(totals)
    assert mean <= budgets["mean"], f"mean {mean:.0f} > ceiling {budgets['mean']}"


def test_every_scenario_role_resolves():
    """A role pointing at nothing means the scenario silently measures less than
    the run really loads."""
    per_file = {rel(p): 1 for p in md_files()}
    absent = {n: v["absent"] for n, v in scenario_totals(per_file).items() if v["absent"]}
    assert not absent, f"roles resolving to no file: {absent}"


def test_roles_cover_every_shipped_file():
    """Every file a run can load belongs to some role, or a split could shrink a
    file to zero measured cost without anyone noticing."""
    covered = {c for cands in ROLES.values() for c in cands}
    shipped = {rel(p) for p in md_files()} - NEVER_LOADED
    # templates and vendor groups are represented by samples, not exhaustively
    shipped = {f for f in shipped if not f.startswith("templates/")}
    missing = {f for f in shipped if f not in covered}
    assert not missing, f"files no scenario role can reach: {sorted(missing)}"


if __name__ == "__main__":
    import traceback
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError:
                fails += 1
                print(f"FAIL  {name}\n      {traceback.format_exc().splitlines()[-1][:400]}")
    sys.exit(1 if fails else 0)
