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


def test_reference_dir_is_never_read_at_runtime():
    for name, body in all_text().items():
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
                bad.append((name, flat[:90]))
    assert not bad, f"glab api cannot take --jq: {bad}"


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
