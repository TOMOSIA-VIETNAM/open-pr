"""The relations BETWEEN files.

A test that quotes one sentence proves that sentence exists in one file. It cannot see a
second file saying the opposite, and every contradiction this suite has missed was exactly
that: two files describing one behaviour. What follows pins the relations instead — a field
and its readers, a question number and whoever writes the answer, a shared rule and the
Steps it governs.
"""

import hashlib
import json
import re

from _common import SRC, TESTS, md_files, rel, text, all_text, cli_text

SETTINGS_SCHEMA = SRC / "reference" / "settings-schema.md"
BOOTSTRAP = SRC / "setup" / "bootstrap.md"
GUARDRAILS = SRC / "core" / "guardrails.md"


def _schema_example():
    """The schema doc's JSON block as {node: {field: value}} — its settings nodes only."""
    block = re.search(r"```json\n(.*?)```", text(SETTINGS_SCHEMA), re.S)
    assert block, "the schema doc must carry one json example"
    return {n: v for n, v in json.loads(block.group(1)).items() if isinstance(v, dict)}


def _schema_groups():
    """The "Field groups" table as [(group, node, [fields])]. Every backticked token in a
    `fields` cell is taken as a classification — which is why that column carries names alone
    and what a field means sits under the table. Filtering the cell against the JSON instead
    would make the JSON the only source: a table naming a field the JSON never declares would
    vanish rather than fail."""
    rows = []
    for m in re.finditer(r"^\| ([A-Z][a-z-]+(?: [a-z]+)*) \| `\.([a-z]+)` \| (.+?) \|",
                         text(SETTINGS_SCHEMA), re.M):
        rows.append((m.group(1), m.group(2), re.findall(r"`([a-z_]+)`", m.group(3))))
    assert rows, "the schema doc must carry the field-group table"
    return rows


def _cells(row):
    """A markdown row's cells, keeping an escaped pipe inside a cell."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", row)[1:-1]]


def test_every_settings_field_is_classified_exactly_once():
    """The JSON example and the field-group table are two lists of the same fields. A field
    the JSON shows and no group classifies has no documented lifecycle — whether
    `/open-pr:upgrade` must backfill it is then anyone's guess; a group naming a field the
    JSON dropped sends a migration author after a key that is not there."""
    schema = _schema_example()
    seen = {}
    for group, node, fields in _schema_groups():
        for f in fields:
            seen.setdefault((node, f), []).append(group)
    twice = {k: v for k, v in seen.items() if len(v) > 1}
    assert not twice, f"classified in more than one group: {twice}"
    declared = {(n, f) for n, fields in schema.items() for f in fields}
    assert declared == set(seen), (
        f"declared but unclassified: {sorted(declared - set(seen))}; "
        f"classified but undeclared: {sorted(set(seen) - declared)}")


def test_a_settings_field_a_prompt_names_exists_in_the_schema():
    """`.review.post_lgtm` in a command and `post_lgtm` in the schema are one field under two
    spellings, tied together by nothing but a reader's memory. A field renamed on one side
    leaves the prompt reading a key `<op> settings` stopped printing — which resolves to
    absent, so the run takes the default instead of failing."""
    schema = _schema_example()
    bad = []
    for name, body in all_text().items():
        for m in re.finditer(r"\.(review|shared|fix)\.([a-z_]+)", body):
            if m.group(2) not in schema.get(m.group(1), {}):
                bad.append((name, f".{m.group(1)}.{m.group(2)}"))
    assert not bad, f"settings fields no schema node declares: {sorted(set(bad))}"


# A User config field whose default cannot be a constant in the runtime. Each needs the
# reason here, or "no default" becomes the way to skip the check above.
NO_CONSTANT_DEFAULT = {
    # the default IS this run's own "CI checks" list being non-empty (core/repo-settings.md)
    "review_ci_status",
    # reconciled against the PR URL on every run, never defaulted (core/pr-target.md §2)
    "git_remote_type",
    # asked once and stored; a guessed posting language is worse than a question
    "output_language",
}


def _runtime_defaults():
    """{field: default literal} the `settings` subcommand applies. The patterns bind the key
    and the path it reads to the same name, so `post_lgtm: (.review.post_lgtmm // true)` is
    reported as a field with no default rather than matching."""
    body = cli_text()
    out = {}
    for m in re.finditer(r"^ +([a-z_]+): \(\.(?:review|fix)\.\1 // ([^)]+)\)", body, re.M):
        out[m.group(1)] = m.group(2).strip()
    for m in re.finditer(r'^ +([a-z_]+): default_bool\(\.(?:review|fix); "\1"; ([^)]+)\)', body, re.M):
        out[m.group(1)] = m.group(2).strip()
    return out


def test_every_user_config_field_has_a_runtime_default():
    """The schema and the runtime must name the same fields, in both directions. A User config
    field is one an older repo's settings.json may not carry yet, and `<op> settings` is the
    sole place a default is applied: ship the field without one and every repo bootstrapped
    before it reads empty — silently, because a missing key and a stored false look the same to
    the prompt. The other way round, a default applied to a field the schema never declares is
    one no reader of this doc can classify and no migration can reach."""
    schema = _schema_example()
    wanted = {f for group, node, fields in _schema_groups() if group == "User config"
              for f in fields}
    missing = wanted - set(_runtime_defaults()) - NO_CONSTANT_DEFAULT
    assert not missing, f"User config fields the runtime never defaults: {sorted(missing)}"
    stale = NO_CONSTANT_DEFAULT - wanted
    assert not stale, f"listed as having no constant default, but no longer User config: {sorted(stale)}"

    # and the way back: a default the runtime applies to a field the doc never mentions is a
    # field nobody can find, upgrade cannot migrate and this file's own reader cannot classify
    declared = {f for fields in schema.values() for f in fields}
    undocumented = set(_runtime_defaults()) - declared
    assert not undocumented, \
        f"the runtime defaults fields the schema never declares: {sorted(undocumented)}"


def test_a_question_number_is_named_only_where_it_is_defined():
    """`q6` says nothing on its own — it is an index into a table in another file, and it goes
    stale in silence the moment that table gains a row. The number is usable only beside the
    table that defines it; everywhere else the field's own name says the same thing and cannot
    rot. `<op> settings` prints fields, never question numbers, so no reader loses anything."""
    owner = rel(BOOTSTRAP)
    stale = []
    for name, body in all_text().items():
        if name == owner:
            continue
        for m in re.finditer(r"\bq(\d+)\b", body):
            stale.append((name, m.group(0)))
    assert not stale, (
        f"question numbers outside {owner} — name the field instead: {sorted(set(stale))}")


def test_bootstrap_asks_exactly_the_user_config_fields():
    """The ask table is numbered and Step 3 writes the answers BY NUMBER, so inserting a
    question re-points every number after it while both files still read as correct. Binding
    the numbers back to the schema is what turns that renumbering into a failure: each node
    bootstrap writes must receive exactly the fields classified User config for it."""
    schema = _schema_example()
    user_config = {}
    for group, node, fields in _schema_groups():
        if group == "User config":
            user_config.setdefault(node, set()).update(fields)

    body = text(BOOTSTRAP)
    questions = {int(n): f for n, f in re.findall(r"^\| (\d+) \| `([a-z_]+)` \|", body, re.M)}
    assert questions, "the ask table must number its questions"
    assert sorted(questions) == list(range(1, len(questions) + 1)), \
        f"question numbers must run 1..N with no gap: {sorted(questions)}"

    section = re.search(r"^## 3\. .*?(?=^## )", body, re.M | re.S)
    assert section, "bootstrap must carry the Step that writes the answers"
    written = {}
    for bullet in re.split(r"\n- ", section.group(0))[1:]:
        m = re.match(r"`\.([a-z]+)`", bullet)
        if not m:
            continue
        nums = set()
        for lo, hi in re.findall(r"\bq(\d+)-q?(\d+)", bullet):
            nums.update(range(int(lo), int(hi) + 1))
        nums.update(int(n) for n in re.findall(r"\bq(\d+)(?!-)", bullet))
        unknown = nums - set(questions)
        assert not unknown, f"Step 3 writes q{sorted(unknown)}, which the ask table does not have"
        written[m.group(1)] = {questions[n] for n in nums}

    for node, fields in written.items():
        assert fields == user_config.get(node, set()), (
            f".{node}: bootstrap writes {sorted(fields)}, "
            f"the schema classifies {sorted(user_config.get(node, set()))} as its User config")
    unwritten = set(user_config) - set(written)
    assert unwritten == {"fix"}, f"User config nodes bootstrap never writes: {sorted(unwritten)}"
    assert "FORBIDDEN: creating `.fix` here" in " ".join(body.split()), \
        "the one node bootstrap skips must say so, and name the bootstrap that owns it"


def test_the_default_offered_at_bootstrap_is_the_one_the_runtime_applies():
    """Two literals for one value: the recommendation the user accepts without reading, and
    what an un-bootstrapped repo actually gets. Drift between them is invisible — both files
    look right on their own, and the user never sees the second number."""
    runtime = _runtime_defaults()
    mismatched = []
    for row in re.findall(r"^\| \d+ \|.*$", text(BOOTSTRAP), re.M):
        cells = _cells(row)
        if len(cells) != 4:
            continue
        field = cells[1].strip("`")
        if field not in runtime:
            continue
        shown = re.findall(r"`([^`]+)`", cells[3])
        if shown != [runtime[field]]:
            mismatched.append((field, cells[3], runtime[field]))
    assert not mismatched, \
        f"the question offers a default the runtime does not apply: {mismatched}"


# A repeat qualifier next to a lookup: the shapes a Step uses when it orders, or bans, a
# second look at something. Over-matching is the point — a site that turns out to be
# neither still gets classified once, in tests/ordered_repeats.json, with its reason.
REPEAT_QUALIFIER = re.compile(
    r"\bagain\b|\bnever cached\b|\bevery run\b|\bRIGHT NOW\b|\brely on context\b"
    r"|\bre-`?Read|\bre-read|\bre-fetch|\bre-run|\btwice\b")
LOOKUP = re.compile(r"`Read`|`Grep`|\bRead\b|\bfetch|<op> [a-z-]+|\.gitmodules")
# criteria copied into the reviewed repo — they question THAT repo's code, and name no Step
REPEAT_SCAN_SKIP = ("reference/", "seeds/", "templates/")


def _repeat_sites():
    """[(file, window, sha)] for every repeat qualifier sitting in a block that also performs
    a lookup. The window, not the whole block, is what carries the sha: an unrelated edit
    elsewhere in the block must not force the site to be re-justified."""
    sites = []
    for path in md_files():
        name = rel(path)
        if name.startswith(REPEAT_SCAN_SKIP) or name == "core/guardrails.md":
            continue  # the rule's own home states it; it is not a site obeying it
        for block in re.split(r"\n\s*\n|\n(?=[-*|#])", text(path)):
            flat = " ".join(block.split())
            if not LOOKUP.search(flat):
                continue
            spans = []
            for m in REPEAT_QUALIFIER.finditer(flat):
                lo, hi = max(0, m.start() - 45), min(len(flat), m.end() + 45)
                if spans and lo <= spans[-1][1]:
                    spans[-1] = (spans[-1][0], max(spans[-1][1], hi))
                else:
                    spans.append((lo, hi))
            for lo, hi in spans:
                window = flat[lo:hi]
                sites.append((name, window,
                              hashlib.sha256(f"{name}|{window}".encode()).hexdigest()[:12]))
    return sites


def _exemption_claims(guardrails_flat):
    m = re.search(r"EXEMPT, and nothing else: ([^.]+)\.", guardrails_flat)
    return {w.lower() for w in re.findall(r"\b([A-Z]{4,})\b", m.group(1))} if m else set()


def test_the_stall_rule_states_a_closed_list_of_exemptions():
    """The rule earns nothing if the way past it is to have a Step order the repeat: that
    exempts every site by construction, and the cheapest fix for a future contradiction
    becomes one more appended clause. So the exemptions are enumerated, the enumeration says
    it is the whole list, and each CAPS word in it is the claim a site may make."""
    flat = " ".join(text(GUARDRAILS).split())
    assert "ALREADY in context is a stall" in flat, \
        "the rule must name what makes a second lookup a stall"
    assert "STOP" in flat and "ASK" in flat, "it must name the exit, not only the ban"
    assert re.search(r"FORBIDDEN: a lookup as the way out of an ambiguity", flat), \
        "an ambiguity answered by another lookup is the loop itself"
    exempt = re.search(r"EXEMPT, and nothing else: ([^.]+)\.", flat)
    assert exempt, "the exemptions must be enumerated, and stated to be the whole list"
    assert _exemption_claims(flat), "each exemption must carry the CAPS word a site claims"


def test_an_ordered_repeat_is_registered_against_the_stall_rule():
    """This is the cross-file half of the rule above. A Step that orders a second lookup and
    a shared rule that forbids one are two files describing one behaviour, and a suite that
    reads each alone sees no disagreement. Every such site is registered with the claim that
    excuses it, so dropping an exemption from the rule reddens whatever leaned on it, and a
    new repeat has to be argued for here instead of appended to the rule as one more clause."""
    doc = json.loads((TESTS / "ordered_repeats.json").read_text(encoding="utf-8"))
    registered = {s["sha"]: s for s in doc["sites"]}
    claims = _exemption_claims(" ".join(text(GUARDRAILS).split())) | {"forbidden", "not-a-repeat"}

    found = _repeat_sites()
    unregistered = [(n, w, h) for n, w, h in found if h not in registered]
    assert not unregistered, "ordered repeats nothing justifies — add each to " \
        "tests/ordered_repeats.json with a claim and a reason:\n" + "\n".join(
            f'    {{"sha": "{h}", "file": "{n}", "claim": "", "reason": ""}}  …{w}…'
            for n, w, h in unregistered)

    gone = set(registered) - {h for _, _, h in found}
    assert not gone, f"registered sites that no longer exist — drop them: {sorted(gone)}"

    for sha, site in registered.items():
        assert site["claim"] in claims, (
            f"{site['file']} claims {site['claim']!r}, which core/guardrails.md does not exempt "
            f"(it allows {sorted(claims)})")
        assert site.get("reason", "").strip(), f"{sha} needs a reason, not just a claim"
        assert any(n == site["file"] for n, _, h in found if h == sha), \
            f"{sha} is registered against {site['file']}, which is not where it was found"
