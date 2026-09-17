"""One rule, one owner: a value or a sentence must not exist twice under src/."""

import re

from _common import SEVERITY_HEADINGS, REPO, SRC, NEVER_LOADED, rel, text, all_text, cli_text, dup_scan


def _section(body, heading):
    """One `## <heading>` section, flattened. Scoping an assert to the section that owns the
    rule is what lets the wording inside it be rewritten without the assert going looking for
    its keywords somewhere else in the file."""
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    assert m, f"section missing: {heading}"
    return " ".join(m.group(1).split())


DEFAULT_LITERALS = {
    "`30`": {"setup/bootstrap.md"},
    "`20`": {"setup/bootstrap.md"},
    '`"1 months"`': {"setup/bootstrap.md"},
}


def test_config_defaults_have_one_source():
    """Under src/, a default literal belongs to the question that offers it and nowhere else —
    a third copy in prose is how the old tree drifted out of sync. The value the runtime
    applies is the other half, and lives in the script
    (test_the_default_offered_at_bootstrap_is_the_one_the_runtime_applies holds the two equal)."""
    for literal, allowed in DEFAULT_LITERALS.items():
        found = {n for n, b in all_text().items() if literal in b} - NEVER_LOADED
        assert found <= allowed, f"{literal} also appears in {found - allowed}"


def test_feedback_carries_every_issue_form_heading():
    """The feedback command composes an issue body under `### <the form's heading>`, and
    the forms do not ship with the plugin — only src/ does. So the headings must be
    written into the command itself, byte-exact, or the body reaches the tracker with
    invented ones the form cannot match. pr_url/evidence stay out: Step 2 strips what
    they ask for."""
    body = (SRC / "commands" / "feedback.md").read_text()
    # a form is what carries `body:`; picking by filename shape silently skips a new one
    forms = [f for f in sorted((REPO / ".github" / "ISSUE_TEMPLATE").glob("*.yml"))
             if re.search(r"^body:", f.read_text(), re.M)]
    assert forms, ".github/ISSUE_TEMPLATE holds no issue form"
    for form in forms:
        # per field block, since a YAML mapping puts id/label in any order
        blocks = re.split(r"\n\s*- type:", form.read_text())[1:]
        assert blocks, f"{form.name} exposes no field block"
        for block in blocks:
            if re.match(r"\s*[\"']?markdown\b", block):   # informational: carries value, no id/label
                continue
            fid = re.search(r"\bid:\s*[\"']?([\w-]+)", block)
            lab = re.search(r"\blabel:\s*(.+)", block)
            assert fid and lab, f"{form.name} has a field block with no id/label"
            field_id, label = fid.group(1), lab.group(1).strip()
            if field_id in ("pr_url", "evidence"):
                assert label not in body, f"{form.name}:{field_id} is never filled by the command"
            else:
                # adjacent, bounded by the backtick that would open the next field, so a heading
                # cannot pass while sitting against the wrong one — and any separator width is fine
                assert re.search(rf"`{re.escape(field_id)}`[^`]{{0,6}}{re.escape(label)}", body), \
                    f"{form.name}:{field_id} heading '{label}' is not next to its id in feedback.md"


def test_glab_api_never_uses_the_gh_only_jq_flag():
    """`gh api` accepts --jq; `glab api` does not — its own help tells you to pipe to
    jq. The flag is easy to copy across while porting an entry, and it fails at the
    FIRST fetch on the vendor half that gets exercised least."""
    bad = []
    for line in cli_text().splitlines():
        if "glab api" in line and "--jq" in line:
            bad.append(("glab api + --jq", line.strip()[:80]))
        if "glab mr view" in line and "--jq" in line and "--output json" not in line:
            bad.append(("mr view --jq without --output json", line.strip()[:80]))
    assert not bad, f"invalid glab flag combination: {bad}"


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
    pool = dict(all_text())
    pool["bin/open-pr.sh"] = cli_text()
    for label in ("bot-finding", "bot-reply"):
        for name, body in pool.items():
            for m in re.finditer(rf"<!--\s*{label}\s*-->", body):
                assert m.group(0) == f"<!-- {label} -->", f"{name}: {m.group(0)!r}"
            # the destination only, so a marker quoted inline in prose keeps its backtick
            for m in re.finditer(rf"\[\s*{label}\s*\]:\s*(\S{{1,2}})", body):
                assert m.group(0).startswith(f"[{label}]: #"), \
                    f"{name}: {m.group(0)!r} != [{label}]: #"


def test_the_marker_rule_carries_its_blank_line():
    """Bitbucket's marker is a link reference definition, which cannot interrupt a paragraph —
    pressed against the text above it renders as a visible broken link. The one finding-format
    rule (review.md) must therefore demand the blank line for every vendor's marker."""
    flat = " ".join(text(SRC / "commands" / "review.md").split())
    assert "on its own line after a blank line" in flat, \
        "review.md's finding format lost the marker blank-line rule"


def test_the_flag_lint_sees_nested_subcommands():
    """vendor_lint checks each flag against the real CLI's --help. Its extractor once cut
    subcommands at two words, asking `glab mr note --help` about a flag that only
    `glab mr note create` documents — reporting a real flag as unknown and training people to
    ignore the lint."""
    import vendor_lint

    rows = list(vendor_lint.cli_invocations(
        'glab mr note create "$N" -R "$OWNER/$REPO" --reply "$T" -m "$(cat "$F")"\n'
        'gh api --paginate "repos/x/y/pulls/1/comments"\n'))
    assert (["mr", "note", "create"], ["--reply"]) in [(s, f) for _, s, f in rows if f]
    assert any(c == "gh" and f == ["--paginate"] for c, s, f in rows)


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


def test_the_marker_literal_belongs_to_the_script():
    """What renders to nothing differs per vendor, so the literal lives in `marker` alone. A
    prompt holding its own copy is how one vendor silently gets the other's form."""
    bad = []
    for name, body in all_text().items():
        if name in ("core/finding-markers.md", "reference/vendor-interface.md"):
            continue
        for m in re.finditer(r"<!--\s*bot-(?:finding|reply)\s*-->|\[bot-(?:finding|reply)\]: #", body):
            bad.append((name, m.group(0)))
    assert not bad, f"a marker literal outside the script: {bad}"


def test_a_reply_marker_does_not_mean_the_finding_is_settled():
    """One account runs both commands, so the fix command's "done" reply and a review
    confirmation are the same bytes. Reading the marker as "already handled" swallowed the
    confirmation on every thread the fix command had answered — including partly fixed ones,
    which then read as settled."""
    s = _section(text(SRC / "core" / "finding-markers.md"), "A reply this plugin already posted")
    assert re.search(r"\bNOT\b.{0,70}\bSETTLED\b", s, re.I), \
        "the marker must not be readable as work already settled"
    assert re.search(r"\bCURRENT code\b", s) and re.search(r"\breplies\b.{0,20}\bSAY\b", s), \
        "what settles a finding is the current code plus what the thread says"
    assert "cases/re-review.md" in s, "and the file owning that judgment must be named"


def test_re_review_reads_a_confirmation_out_of_the_thread_text():
    """With the marker demoted, the words in the thread are the only thing that can hold a
    confirmation back: one already posted (by anyone), or a human deciding to leave the code
    as it is. Both silences must be content-driven, and both must be reachable without
    fetching anything the run does not already hold."""
    s = _section(text(SRC / "cases" / "re-review.md"),
                 "Checking whether old findings (left by this command) have been fixed")
    assert re.search(r"reply SAYS decides", s) and re.search(r"never its marker", s), \
        "content decides whether a finding is settled — not authorship, not the marker"
    assert re.search(r"fetch nothing more", s), \
        "the thread text is on hand already; reading it must cost no extra call"
    assert re.search(r"reply settles it.{0,90}count it closed", s), \
        "a reply that settles the finding closes it whatever the code shows"
    assert re.search(r"FORBIDDEN: a second confirmation", s), \
        "double-confirming is what the demoted marker no longer prevents"
    assert re.search(r"`auto_resolve_fixed_findings` `true`.{0,20}`<op> resolve`", s), \
        "a silent close must still resolve when the setting asks for it"
    assert re.search(r"no reply says so yet.{0,40}reply on THAT EXACT thread", s), \
        "a fix nothing has confirmed must still get its confirming reply"


def test_fix_still_stops_on_its_own_earlier_reply():
    """Demoting the marker is about confirmations, not about the fix command redoing work it
    already answered — there, a reply of this plugin's in the thread still drops the finding."""
    flat = " ".join(text(SRC / "commands" / "fix.md").split())
    assert re.search(r"\bthread\b.{0,40}\breply from this plugin\b", flat), \
        "fix must keep dropping a finding it has answered once"


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


def test_strip_frontmatter_keeps_handwritten_description():
    """Harness-dictated fields repeat by necessity; `description:` is authored, so a
    repeat there IS a duplicated rule and must stay visible to the scan. Every scan
    returns 0 either way, so only this pins which half gets blanked."""
    body = ('---\nargument-hint: "[x]"\ndescription: alpha beta\n  gamma delta\n'
            'disable-model-invocation: true\n---\nbody\n')
    out = dup_scan.strip_frontmatter(body)
    assert out.splitlines()[:6] == ["", "", "description: alpha beta", "  gamma delta", "", ""]
    assert len(out.splitlines()) == len(body.splitlines())


def _fmt(found):
    return "\n".join(
        f"  ~{f['waste']} tok  {f['occurrences'][0][0]}:{f['occurrences'][0][1]}"
        f" + {f['occurrences'][1][0]}:{f['occurrences'][1][1]}  {f['run'][:90]}…"
        for f in found[:15])
