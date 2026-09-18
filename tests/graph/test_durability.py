"""The files themselves: no dangling lifetime, no leaked English, no emoji a terminal splits.

The suite's own files are here too — what keeps a two-level tests/ tree collectable is a
naming rule, and a rule nothing checks is a rule the next contributor breaks.
"""

import re

from _common import (SEVERITY_HEADINGS, SRC, TESTS, VENDORS, NEVER_LOADED,
                     md_files, rel, text, all_text, cli_text)


def test_test_file_basenames_stay_unique():
    """tests/graph/ carries no __init__.py, so pytest imports each test file under its bare
    basename. Two files sharing one name anywhere under tests/ is not one broken file — the
    import collides and collection aborts for the WHOLE suite, with a hint about .pyc files
    that points nowhere near the cause. Adding __init__.py is not the alternative: the
    package directory then stops reaching sys.path and every `from _common import …` breaks."""
    names = [p.name for p in TESTS.rglob("test_*.py")]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"duplicate test-file basenames: {dupes}"


EPHEMERAL = [
    (r"\bT[0-9]\b", "task id"),
    (r"\bPhase [0-9]", "plan phase"),
    (r"PR #[0-9]+", "a specific PR number"),
    (r"issue #[0-9]+", "a specific issue number"),
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
    """Standing in a workspace and reviewing three repos must leave ONE notebooks/review/
    there holding all three. A version of this that `cd`-ed into the repo put the memory
    inside the repo instead. So review.md may not `cd`; locate-repo yields a directory and
    decides nothing (fix.md needs the opposite); and the script aims its git calls with -C
    while rooting the worktree at $PWD — the invocation directory."""
    review = text(SRC / "commands" / "review.md")
    assert "FORBIDDEN: `cd`" in review, "review.md must forbid cd — it writes at pwd"
    body = cli_text()
    assert 'git -C "$repo_dir" worktree add' in body, "the worktree add is not aimed with -C"
    assert 'target="$PWD/notebooks/review/' in body, "the worktree must root at the invocation directory"
    locate = re.search(r"^cmd_locate_repo\(\) \{\n(.*?)^\}", body, re.M | re.S).group(1)
    assert "cd " not in locate, "locate-repo decides for its callers; it must not cd"


def test_fix_reuses_what_the_session_already_established():
    """#123: run from a side worktree, fix re-asked the bootstrap CHOICE and offered only a
    fresh checkout although the same session had the repo's memory and a gated checkout in
    hand. Session knowledge comes first in both places; the gate still judges the tree."""
    flat = " ".join(text(SRC / "commands" / "fix.md").split())
    assert "the one THIS session already established for `<repo>`" in flat
    assert "A checkout THIS session already established that prefix-matches" in flat
    assert "probes beside the repo's main worktree" in flat


def test_fix_reads_the_memory_review_wrote():
    """review.md writes notebooks/review/<repo> at ITS pwd (the invocation directory); fix.md
    cd's into the repo — resolving memory relative to the repo there grew a second, drifting
    settings.json inside the reviewed tree (seen live: the two copies disagreed on
    git_remote_type). fix must resolve memory at the invocation directory, absolutely."""
    flat = " ".join(text(SRC / "commands" / "fix.md").split())
    assert "at THIS invocation directory, ABSOLUTE" in flat
    assert "FORBIDDEN: resolving memory inside `<repo_dir>`" in flat
    assert "run FROM the invocation directory so the worktree lands under `<memory-dir>`" in flat


def test_fix_matches_findings_in_one_pass():
    """Re-reading the marker rules and the findings to "double-check" a match is what burned
    110 requests in 13 minutes on a single run: the data never changes between passes, so the
    second lookup answers exactly what the first did and there is no natural end to the loop.
    The only way out of an ambiguous match is the question Step 6 already asks."""
    flat = " ".join(text(SRC / "commands" / "fix.md").split())
    assert re.search(r"\bONE pass\b.{0,40}\balready fetched\b", flat), \
        "the matching pass has to be bounded to the data already in context"
    assert re.search(r"FORBIDDEN:.{0,20}re-`Read`ing.{0,30}finding-markers", flat) and \
        re.search(r"re-running `<op> context`", flat), \
        "both re-reads that fed the loop must be named as forbidden"
    assert re.search(r"asks the dev.{0,20}never another lookup", flat), \
        "an unresolved match must become a question, not a retry"
    assert re.search(r"single pass Step 3 names", flat), \
        "Step 5 reads the same threads; it must be bound to that one pass too"


def test_several_prs_in_one_fix_run_stay_separate():
    """One `/open-pr:fix` invocation can be handed a main PR and its submodule PR. Matching one
    repo's findings against the other's comments never converges, so each PR gets its own whole
    run, and the relation that decides the order is verified against `.gitmodules` rather than
    taken from a body anyone can write."""
    fix = " ".join(text(SRC / "commands" / "fix.md").split())
    assert "**≥2 valid PR URLs**" in fix and "cases/multi-pr-fix.md" in fix, \
        "fix.md must route a multi-URL invocation to the case file"

    case = " ".join(text(SRC / "cases" / "multi-pr-fix.md").split())
    assert re.search(r"only when BOTH hold", case), \
        "a body link alone must not establish the parent-submodule relation"
    assert re.search(r"`\.gitmodules`.{0,60}`url` names that same", case), \
        "the relation must be verified against the parent's own .gitmodules"
    assert re.search(r"SUBMODULE PR runs FIRST", case), \
        "the parent's fix can depend on what the submodule pass wrote"
    assert re.search(r"Step 0 → Step 11 to COMPLETION", case), \
        "each PR needs a whole run, not a shared pass"
    assert re.search(r"FORBIDDEN: parallel runs, a subagent, or carrying another PR's findings", case), \
        "the runs must not share findings, comments, worktree or settings"
    assert re.search(r"matches markers against THIS PR's \"Old comments\" and nothing else", case), \
        "marker matching is per-PR; two repos in one pass is the loop"
    assert re.search(r"submodule pointer.{0,20}is the dev's call", case), \
        "fix commits only what it edited — the pointer bump is handed back"


def test_the_fix_snippet_is_reviewed_like_the_diff():
    """The snippet in a finding is the one piece of code in the loop no criteria covered —
    a dev applies the fence as written, so a wrong snippet lands and only the NEXT round
    catches it, as a finding against the reviewer's own suggestion. The rule and its escape
    hatch (prose direction when the snippet cannot be verified) live beside the fix format."""
    flat = " ".join(text(SRC / "commands" / "review.md").split())
    assert "apply the same criteria to the fix you wrote" in flat
    assert "the path it replaces is actually gone" in flat
    assert "state the DIRECTION in prose instead" in flat


def test_fix_suggestions_prefer_a_code_fence():
    """A finding whose Fix is prose makes the dev reconstruct the intended logic. The
    fence is the default; prose is for fixes with no code form."""
    step7 = text(SRC / "commands" / "review.md")
    assert "shows the corrected CODE in a fence by default" in step7
    assert "FORBIDDEN: prose merely because writing the code is effort" in step7, \
        "prose must be the exception, not a sibling option"


def test_a_cross_file_assumption_is_checked_before_it_is_concluded():
    """A diff-scoped pass structurally cannot see whether the code around the diff agrees with
    what the new code assumes — a caller invoking it the wrong way, a capability it takes for
    granted. Scope carries the check, and all three parts of it are load-bearing:

    the trigger is the conclusion FLIPPING on that symbol, not merely mentioning it, and it
    binds the decision to stay silent as much as the decision to raise; the spend is the
    agent's own judgment, bound to the flip trigger rather than a numeric cap — a hard cap
    bounds the evidence, and bounded evidence is where an expert model's misses come from;
    and an inconclusive `Grep` still has to surface, or the rule quietly becomes permission
    to assume.
    """
    flat = " ".join(text(SRC / "commands" / "review.md").split())

    assert "conclusion that FLIPS on how a symbol outside the diff behaves" in flat, \
        "Scope must trigger on the conclusion flipping, not on any mention of an outside symbol"
    assert "raise and stay-silent alike" in flat, \
        "the check must bind the decision NOT to raise a finding too"
    assert re.search(r"`Grep` for that symbol under `<worktree>` BEFORE concluding", flat), \
        "the check must be a Grep aimed at the worktree, run before concluding"
    assert "as many as flipping conclusions genuinely need" in flat, \
        "the spend must stay bound to the flip trigger, not become free-roaming exploration"
    assert re.search(r"`Grep` before `Read`", flat), \
        "the cheap tool must stay the first tool"
    assert re.search(r"`Grep` inconclusive ⇒ raise it at 🔵", flat), \
        "an inconclusive Grep must still reach the PR, at the severity Scope names"
    assert "FORBIDDEN: asserting the behaviour, or dropping it silently" in flat, \
        "both ways out of an inconclusive Grep must stay closed"


def test_read_spend_is_owned_judgment_with_a_stated_cost():
    """A hard read cap (a mandatory offset/limit, a numeric Grep budget) bounds the evidence
    a review can see, and bounded evidence is where an expert model's misses come from. The
    caps are owned judgment instead — but ownership needs the cost stated where the decision
    happens, or judgment decays into reading everything."""
    flat = " ".join(text(SRC / "commands" / "review.md").split())
    scope = flat[flat.index("**Scope:**"):flat.index("**Finding format**")]
    assert re.search(r"default to `offset`/`limit` around the changed region", scope), \
        "the bounded read must stay the DEFAULT even with the cap gone"
    assert "when a conclusion genuinely needs it" in scope, \
        "the wider read must be tied to a conclusion needing it, not availability"
    assert "Every read is context the rest of the review pays for" in scope, \
        "the cost must be stated where the judgment is exercised"


def test_fix_owns_the_edit_and_checks_the_callers():
    """A pasted snippet can break another caller and cost a whole round. The fixer owns the
    edit — the finding names the problem, the code decides the fix — and an edit to shared
    code checks the call sites the finding may not have listed."""
    flat = " ".join(text(SRC / "commands" / "fix.md").split())
    assert "You OWN what you apply" in flat
    assert "re-derive a suggested snippet against the code before applying it" in flat, \
        "the reviewer's snippet must be re-derived in context, never pasted as-is"
    assert re.search(r"`Grep` those callers at `<repo_dir>`", flat), \
        "an edit to shared code must check its call sites"
    assert "the finding may not list them" in flat, \
        "the caller check must not depend on the finding having named the callers"


def test_a_recommendation_is_earned_not_defaulted():
    """Users pick the `(Recommended)` option without reading the alternatives, so a wrong
    mark is silently followed. The mark must survive the case for the other option before
    it is placed; a genuine tie stays blank rather than guessing."""
    g = " ".join(text(SRC / "core" / "guardrails.md").split())
    assert "EARN it: make the case for the OTHER option first" in g, \
        "the recommendation must be tested against the alternative before it is marked"
    assert "genuinely tied ⇒ blank" in g, \
        "a tie must stay unmarked, not get a guessed recommendation"


def test_the_prs_own_hunks_are_checked_against_each_other():
    """A per-file pass can bless every hunk while the PR contradicts itself: two commits
    touch the same function, or a helper the diff edits is called elsewhere in the same
    diff under a contract the edit broke. Each round that misses this publishes another
    review and costs the author a push. Every trigger must be readable off the diff text
    itself — a trigger that needs a symbol index of the whole diff either gets skipped or
    eats the context. The check must bind the decision to stay silent, not only the
    decision to raise, and it must hand out-of-diff callers to the flip-bound `Grep` rule
    instead of growing a read of its own."""
    flat = " ".join(text(SRC / "commands" / "review.md").split())
    scope = flat[flat.index("**Scope:**"):flat.index("**Finding format**")]
    assert "hunks editing the SAME function" in scope, \
        "Scope must name the twice-edited-function trigger"
    assert "a rule another hunk RESTATES in prose" in scope, \
        "Scope must name the rule-vs-restatement trigger — code and its prose echo drift apart"
    assert "editing a definition another hunk CALLS" in scope, \
        "Scope must name the definition-vs-caller trigger"
    assert "never a symbol index" in scope, \
        "every trigger must stay readable off the diff, or the check has no stop condition"
    assert re.search(r"AGAINST EACH OTHER before concluding, silence included", scope), \
        "the cross-hunk check must bind the decision to stay silent too"
    assert re.search(r"out-of-diff caller is the `Grep` rule", scope), \
        "out-of-diff callers must route to the `Grep` rule, not a new read of their own"


def test_a_fix_to_shared_code_names_the_callers_it_must_keep_working():
    """A suggested fix to a shared helper can break the helper's other callers, and the dev
    applying the fence as written cannot see that. The snippet rule must make the finding
    name those callers, so the fix carries its own blast radius."""
    flat = " ".join(text(SRC / "commands" / "review.md").split())
    assert re.search(r"OTHER CALLERS ⇒ the finding NAMES the callers it must keep working", flat), \
        "a fix to shared code must carry its blast radius in the finding itself"


def test_a_clean_review_can_be_kept_off_the_pr():
    """`post_lgtm` is the one setting that decides whether something reaches the PR at all,
    so the gate has to sit where the posting happens and name the single body it covers —
    a finding of any kind still posts. The re-review early-stop row reaches Step 9 for the
    same one-liner and must defer to the gate rather than carry a second copy of it."""
    flat = " ".join(text(SRC / "commands" / "review.md").split())
    assert re.search(r"`\.review\.post_lgtm`.{0,60}LGTM one-liner.{0,20}put NOTHING on the PR", flat), \
        "the gate must name the setting and the one body shape it covers"
    assert re.search(r"in chat instead.{0,60}this setting is why it was not posted", flat), \
        "the user must still see the result, and why the PR did not"
    assert re.search(r"Every other body shape posts as usual", flat), \
        "the setting must not reach a review that carries findings"

    rr = " ".join(text(SRC / "cases" / "re-review.md").split())
    assert re.search(r"lands on the PR or in chat is Step 9's `post_lgtm` gate", rr), \
        "the early-stop row must defer to the gate, not restate it"


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

    A fence opened ```` ```! ```` is the multi-line form of the same feature and runs just
    as early, so both shapes are banned.

    Negation gets spelled out instead. The saving from an operator is a few tokens; the
    cost is the command not running at all.
    """
    bad = []
    for name, body in all_text().items():
        for m in re.finditer(r"!`|^ {0,3}```!", body, re.M):
            line = body[:m.start()].count("\n") + 1
            bad.append(f"{name}:{line}")
    assert not bad, ("`!` before a backtick, or opening a fence, is auto-exec syntax; write the "
                     f"negation in words: {bad}")


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
    """A patch that reaches the terminal is in context for the rest of the run, and the Step 7
    guard fires long after Context has already paid for it — so the omission lives inside
    ctx_diff itself, per vendor. Measured once: an ungated fetch pulled 30,517 tokens for one
    86KB dump."""
    body = re.search(r"^ctx_diff\(\) \{\n(.*?)^\}", cli_text(), re.M | re.S).group(1)
    assert 'm="$MAXPATCH"' in body, "ctx_diff takes no size threshold"
    for v, marker in (("github", "length) < $m"), ("gitlab", "length) < $m"),
                      ("bitbucket", "awk -v m=")):
        line = next(l for l in body.splitlines() if f"{v})" in l or f"{v}) " in l or v in l.split(")")[0])
        section = body[body.index(v):]
        assert marker in section.split(";;")[0], f"{v}: the threshold is named but nothing filters on it"


def test_size_entry_never_reports_zero_for_a_withheld_patch():
    """A vendor that withholds a patch (too large, binary, collapsed) must surface UNKNOWN —
    a 0 would slip the biggest file in the PR under every threshold, so it is neither reviewed
    nor listed as skipped."""
    body = re.search(r"^ctx_sizes\(\) \{\n(.*?)^\}", cli_text(), re.M | re.S).group(1)
    for v in VENDORS:
        section = body[body.index(v):].split(";;")[0]
        assert "UNKNOWN" in section, f"{v}: size branch has no UNKNOWN case"


def test_the_script_never_leaks_a_credential():
    """The Bitbucket token is the script's to protect: -v/-i dump the Authorization header into
    context, a token in a URL reaches the access log and the shell history, and echoing either
    variable prints it. vendor_lint covers the flag half offline; this pins the rest in CI."""
    body = cli_text()
    for line in body.splitlines():
        if "curl" in line:
            assert not re.search(r"\s-(v|i)\b", line), f"curl dumps headers: {line.strip()}"
    assert not re.search(r"https://[^\"'\s]*\$BITBUCKET", body), "a credential inside a URL"
    assert "--fail-with-body" in body, "curl must fail loudly WITH the response body"
    # argv is readable via `ps` by any user on the machine — a credential may reach
    # curl only through its own config file, written by the printf BUILTIN
    for line in body.splitlines():
        # a curl INVOCATION — "curl " with a boundary; the printf writing bb.curlrc
        # uses the shell builtin, which never becomes an argv another user can read
        if re.search(r"\bcurl\s", line):
            assert "$BITBUCKET" not in line, f"a credential variable on a curl line: {line.strip()}"
        # printing a credential is legal ONLY into the temp-dir config file — anything
        # else lands in the agent's context or the shell history
        if re.search(r"\b(echo|printf)\b", line) and "$BITBUCKET" in line:
            assert '> "$TMPD/' in line, \
                f"a credential may only be written into the temp dir, never printed: {line.strip()}"
    assert re.search(r"--config \"\$TMPD/", body), "curl no longer reads its credential from a config file"


def test_paged_walks_every_bitbucket_page():
    """A list endpoint caps a page at 100 and hands back `next`; stopping at page 1 silently
    loses every finding past it, which reads as \"nothing there\"."""
    body = cli_text()
    assert re.search(r"bb_paged\(\) \{", body), "the pagination walker is gone"
    walker = re.search(r"bb_paged\(\) \{\n(.*?)^\}", body, re.M | re.S).group(1)
    assert ".next // empty" in walker and "while" in walker, "the walker no longer follows .next"
    assert "return 1" in walker, "an HTTP error must abort, not end the loop as success"
