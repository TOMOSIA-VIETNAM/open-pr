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
import subprocess
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


def test_reference_dir_is_never_read_at_run_time():
    """The schema doc serves a human editor and a migration author. Every number a command
    needs while running — including the build's own config checkpoint — lives in a small atom
    instead, so no run pays for the whole schema to learn one field."""
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
    """The markers are the plugin's cross-run identity, so each form has exactly one
    spelling — a variant makes a past finding invisible and it gets posted again."""
    for label in ("bot-finding", "bot-reply"):
        for name, body in all_text().items():
            for m in re.finditer(rf"<!--\s*{label}\s*-->", body):
                assert m.group(0) == f"<!-- {label} -->", f"{name}: {m.group(0)!r}"
            # the destination only, so a marker quoted inline in prose keeps its backtick
            for m in re.finditer(rf"\[\s*{label}\s*\]:\s*([^\s`]+)", body):
                assert m.group(0) == f"[{label}]: #", f"{name}: {m.group(0)!r} != [{label}]: #"


def test_a_link_reference_marker_carries_its_blank_line_rule():
    """A link reference definition cannot interrupt a paragraph: pressed against the text above
    it, the renderer emits a visible broken link instead of dropping it. The rule has to be IN the
    entry, stated: a caller loads one group, so a pointer from `thread` to `post` is a rule that
    `/open-pr:fix` never reads."""
    for v in VENDORS:
        for group, label in (("post", "bot-finding"), ("thread", "bot-reply")):
            body = text(SRC / "vendors" / v / f"{group}.md")
            entry = [p for p in re.split(r"\n(?=## )", body) if f"[{label}]: #" in p]
            if not entry:
                continue        # this vendor uses the HTML-comment form
            flat = " ".join(entry[0].split())
            assert "BLANK LINE" in flat, \
                f"{v}/{group}: uses the link-reference form without stating the blank-line rule itself"


def test_the_span_walker_survives_any_fence_tag():
    """`spans()` is tested directly because comparing the two walkers cannot catch this: both go
    through it, so a parser bug makes them wrong identically and the comparison still passes.

    A fence the regex fails to recognise is left in the text, and the inline-backtick scan then pairs
    backticks ACROSS it — inventing a span that carries the language tag, and dropping the real command
    that came after out of sight. The second half is the dangerous one: the lint reports clean on an
    entry it never looked at."""
    sys.path.insert(0, str(REPO / "scripts"))
    import vendor_lint  # noqa: E402

    for tag in ("", "bash", "json", "markdown", "sh", "Bash", "yaml"):
        part = (f"## E\n\n```{tag}\n"
                'if [ -n "$X" ]; then printf a; else gh api user; fi\n'
                "```\n\nProse `gh pr view <url>` inline.\n")
        got = list(vendor_lint.spans(part))
        assert any("printf a" in s for s in got), f"tag {tag!r}: fenced command lost"
        assert any(s == "gh pr view <url>" for s in got), f"tag {tag!r}: inline command lost — {got}"
        assert not any(tag and s.startswith(tag) for s in got), \
            f"tag {tag!r}: a span carries the language tag — {got}"


def test_the_static_lint_sees_every_entry_the_live_lint_runs():
    """`lint_curl` walks all_entries() while the live mode walks entries(). A stricter rule in
    one of them hides an entry from the static checks — `--fail-with-body`, `-v`, a credential
    literal — while it still runs against a real PR."""
    sys.path.insert(0, str(REPO / "scripts"))
    import vendor_lint  # noqa: E402

    for v in VENDORS:
        runnable = {h for h, cmd, _ in vendor_lint.entries(v) if cmd}
        seen = {h for _, h, _ in vendor_lint.all_entries(v)}
        assert runnable <= seen, f"{v}: static lint cannot see {sorted(runnable - seen)}"


def test_scripts_never_point_at_a_prompt_file_that_is_gone():
    """A script's own docstring is documentation too, and `src/` moves under it — the reference
    that outlived its file sat in a docstring twice before anything checked it."""
    dead = []
    for f in sorted((REPO / "scripts").glob("*.py")) + sorted((REPO / "scripts").glob("*.sh")):
        for m in re.finditer(r"src/[A-Za-z0-9_./-]+\.md", f.read_text()):
            ref = m.group(0)
            if "<" in ref or (REPO / ref).exists():
                continue
            dead.append(f"{f.name} → {ref}")
    assert not dead, f"scripts referencing a file that does not exist: {dead}"


def test_the_marker_literal_belongs_to_the_vendor():
    """What renders to nothing differs per vendor, so the literal is a vendor entry. A caller
    holding its own copy is how one vendor silently gets the other's form."""
    bad = []
    for name, body in all_text().items():
        if name.startswith("vendors/") or name in ("core/finding-markers.md",
                                                   "reference/vendor-interface.md"):
            continue
        for m in re.finditer(r"<!--\s*bot-(?:finding|reply)\s*-->|\[bot-(?:finding|reply)\]: #", body):
            bad.append((name, m.group(0)))
    assert not bad, f"a marker literal outside the vendor files: {bad}"


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


def test_no_unapproved_duplication_in_adapters():
    """Four shims saying the same two sentences is accepted and allowlisted. A FIFTH copy of
    anything, or a rule that grew a second home here, is not — that is the drift this whole
    layer exists to prevent."""
    found = dup_scan.scan("both", scope="adapters")
    assert not found, "unapproved duplication in the adapter layer:\n" + _fmt(found)


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
    (r"Reviewed at commit", "the anchor takes no English connective either"),
    (r"Thank you", "a thanks pinned in English ships English into a non-English review"),
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
    flat = " ".join(text(SRC / "commands" / "review.md").split())
    assert re.search(r"FORBIDDEN: repeating \w+ finding's description or its Fix", flat), \
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
    for name in ("commands/review.md", "commands/fix.md", "cases/re-review.md",
                 "cases/submodule-review.md", "cases/pr-template-checklist.md",
                 "cases/large-diff-guards.md"):
        body = text(SRC / name)
        for pattern, why in ENGLISH_IN_OUTPUT:
            for m in re.finditer(pattern, body, re.I):
                bad.append(f"{name}:{body[:m.start()].count(chr(10)) + 1} — {why}")
    assert not bad, "English pinned into posted output:\n  " + "\n  ".join(bad)


LANGUAGE_MARKED = re.compile(r"IN THE (OUTPUT|CHAT) LANGUAGE")
FIXED_HEADINGS = set(SEVERITY_HEADINGS) | {"### 🤖【AI REVIEW】Overview"}


def test_template_headings_other_than_severity_follow_the_language():
    """A heading inside a fenced template is copied out verbatim, so one pinned in English
    ships English into a vi/ja review or chat — as `Files skipped for detailed review` did
    above a Vietnamese body. Severity labels and the AI REVIEW banner are a fixed
    vocabulary; every other heading names the language it takes.
    """
    bad = []
    for name in ("commands/review.md", "cases/submodule-review.md"):
        for block in re.findall(r"\n```\n(.*?)\n```", text(SRC / name), re.S):
            bad += [f"{name}: {ln}" for ln in block.splitlines()
                    if re.match(r"#{3,6} ", ln) and ln not in FIXED_HEADINGS
                    and not LANGUAGE_MARKED.search(ln)]
    assert not bad, "heading pinned in one language inside a template:\n  " + "\n  ".join(bad)


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
        # jq filters it, or awk does when the diff arrives as one text blob. What must never
        # happen is a threshold nothing acts on.
        assert any(k in cmd for k in ("select", "awk -v m=<max_patch_bytes>")), \
            f"{v}: the threshold is named but nothing filters on it"


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
            markers = ("select", "| jq '{", "--json", "fields=", "No equivalent", "<patch_pipe>")
            if not any(k in flat for k in markers):
                loose.append((v, head))
    assert not loose, (
        "fetch entry neither filters nor is listed as bounded/unbounded by design: " + str(loose))


def test_a_curl_vendor_never_leaks_its_credential():
    """A vendor with no CLI carries its own token, so the prompt files are what decide whether the
    VALUE can reach the terminal. `-v`/`-i` print the Authorization header; an interpolated literal
    would put the token itself in a command line, and from there in the shell history."""
    bad = []
    for name, body in all_text().items():
        for span in re.findall(r"`([^`]+)`", body) + re.findall(r"```(?:bash)?\n(.*?)```", body, re.S):
            flat = " ".join(span.split())
            if "curl" not in flat:
                continue   # prose naming a flag in order to forbid it carries no invocation
            for flag in (" -v", " -i", " --verbose", " --include"):
                if flag in f" {flat}":
                    bad.append((name, f"{flag.strip()} prints the Authorization header", flat[:70]))
            if re.search(r"(?i)(token|password|api_token)\s*[:=]\s*[A-Za-z0-9]{8,}", flat):
                bad.append((name, "a credential literal", flat[:70]))
    assert not bad, f"credential leak in a curl entry: {bad}"


def test_a_curl_vendor_reports_http_errors_with_their_body():
    """`--fail-with-body` is the only curl form that both exits non-zero on an HTTP error and keeps
    the response body — and the body is where the API says what it rejected. Plain `-f` throws that
    away; no flag at all makes an error page look like a successful empty answer."""
    for v in VENDORS:
        body = text(SRC / "vendors" / v / "fetch.md")
        if "curl" not in body:
            continue  # a vendor with a CLI of its own
        assert "--fail-with-body" in body, \
            f"{v}: defines a curl shorthand that does not fail loudly with its body"
        assert not re.search(r"curl (?:-[a-zA-Z]+ )*-f(?: |$)", body), \
            f"{v}: bare -f discards the error body"


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

    # the bare form can span several repos: the one question must name each of them,
    # and must stay one question — a repo picker on top of it is the hedge in disguise
    step4 = " ".join(up[ask:apply_].split())
    assert "NAMES every `<set>`" in step4, "the ask must enumerate what is in scope"
    assert "FORBIDDEN: a SECOND question" in step4, "selection and consent are one question"


def test_upgrade_finds_its_targets_without_a_git_remote():
    """The command takes no PR URL, and users call it from the workspace they review from —
    a directory with no git remote of its own. Config sits under notebooks/review/ either
    there or one level down inside each repo, so the search must span both depths. Bare form
    takes every set found; a named repo filters them."""
    up = text(SRC / "commands" / "upgrade.md")
    flat = " ".join(up.split())
    assert "-path '*/notebooks/review'" in flat and "-maxdepth" in flat, \
        "a depth-spanning search is what finds config in both layouts"
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
    multiplies the worktree's cost by the ones the PR never touched, and a bare or recursive
    `--init` does exactly that — so the only `submodule update` lives where the bumped paths
    are known, and names one."""
    review = " ".join(text(SRC / "commands" / "review.md").split())
    assert "submodule update" not in review.replace("FORBIDDEN: `submodule update` here", ""), \
        "review.md must not check out submodules — it does not yet know which are bumped"

    sub = text(SRC / "cases" / "submodule-review.md")
    flat = " ".join(sub.split())
    cmds = list(re.finditer(r"submodule update[^`\n]*", flat))
    assert cmds, "the bumped path has to be checked out somewhere"
    for m in cmds:
        c = m.group(0)
        if "FORBIDDEN" in flat[max(0, m.start() - 30):m.start()]:
            continue
        assert "--recursive" not in c, f"nested submodules are out of scope: {c}"
        assert "-- \"<submodule-path>\"" in c or "-- <path>" in c, \
            f"a bare --init checks out every submodule: {c}"
    assert "never gets a `notebooks/` of its own" in flat, \
        "the worktree sits beside the project repo; a submodule holds no memory directory"


def test_clean_deletes_worktrees_and_nothing_else():
    """This is the only command whose job is `rm`, standing in a directory that also holds the
    one thing here nobody can regenerate: what the repo taught it. A worktree comes back on the
    next review; memory does not come back at all. So the ban is named file by file, and the
    user answers before anything goes."""
    c = text(SRC / "commands" / "clean.md")
    flat = " ".join(c.split())
    for keep in ("memory.md", "memories/", "ALWAYS_RULE.md", "settings.json", "templates/"):
        assert keep in flat.split("## Step 1")[0], f"the CRITICAL block must rule out {keep}"
    assert "notebooks/review/*/worktrees/" in flat, "the only deletable path must be named"
    ask = c.index("## Step 3")
    assert c.index("## Step 4 — Remove") > ask, "the ask must come before the removal"
    assert "(Recommended)" in c and "`Keep them`" in c, "two options, one of them recommended"
    assert "worktree prune" in flat, \
        "a removed checkout leaves a registration behind in the reviewed repo"
    # review.md points at it and must not do the deleting itself
    r = " ".join(text(SRC / "commands" / "review.md").split())
    assert "/open-pr:clean" in r, "the run that creates a worktree must say what removes it"
    assert "removing the worktree or asking to" in r, \
        "review must leave the decision to the user, not prompt for it every run"


def test_docs_exist_in_every_language_and_their_links_resolve():
    """The READMEs hand their reference material to docs/, one tree per language. A page
    translated in one language and not another leaves that reader at a 404, and a relative
    link written at the wrong depth (docs/vi/ is two levels down, docs/ is one) breaks
    silently — GitHub renders the text and only the click fails."""
    en = sorted(p.name for p in (REPO / "docs").glob("*.md"))
    assert en, "docs/ holds no English page"
    for lang in ("vi", "ja"):
        got = sorted(p.name for p in (REPO / "docs" / lang).glob("*.md"))
        assert got == en, f"docs/{lang} has {got}, English has {en}"

    pages = [REPO / f for f in ("README.md", "README.vi.md", "README.ja.md")]
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
    for p in points:
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
    """Every file a Claude Code run can load belongs to some role, or a split could shrink a
    file to zero measured cost without anyone noticing. Scope is `src/`: the adapter layer ships and
    is read at run time on other platforms, but no Claude scenario loads it, so it carries no
    ceiling here."""
    covered = {c for cands in ROLES.values() for c in cands}
    shipped = {rel(p) for p in md_files()} - NEVER_LOADED
    # templates and vendor groups are represented by samples, not exhaustively
    shipped = {f for f in shipped if not f.startswith("templates/")}
    missing = {f for f in shipped if f not in covered}
    assert not missing, f"files no scenario role can reach: {sorted(missing)}"


# --------------------------------------------------------------------------- #
# the adapter layer — what platforms other than Claude Code enter through
# --------------------------------------------------------------------------- #
#
# These files ship, are read at run time, and carry NO behaviour: each one names a command
# file under src/ and gets out of the way. The tests below are what keeps them that way, so
# that changing a rule stays a one-file edit under src/ no matter how many platforms exist.

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
    "schema_version", "notebooks/review", "settings.json", "ALWAYS_RULE", "memory.md",
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


def test_the_declared_version_keeps_up_with_the_release_tags():
    """The one declared version is the one nobody thinks to bump. Tags are what say which release a
    checkout is, so the manifest may equal the newest tag or run ahead of it (a bump prepared for the
    next release) — never behind, which is what shipping a stale number looks like."""
    tags = subprocess.run(["git", "tag", "--list", "v[0-9]*"], cwd=REPO,
                          capture_output=True, text=True).stdout.split()
    if not tags:
        return  # a shallow clone with no tags cannot judge this
    def parts(v):
        return tuple(int(x) for x in re.match(r"v?(\d+)\.(\d+)\.(\d+)", v).groups())
    newest = max(parts(t) for t in tags if re.match(r"v?\d+\.\d+\.\d+", t))
    declared = parts(json.loads((REPO / "gemini-extension.json").read_text(encoding="utf-8"))["version"])
    assert declared >= newest, (
        f"gemini-extension.json says {declared}, newest release tag is {newest} — bump it")


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
