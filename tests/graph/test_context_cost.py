"""What one invocation Reads, against the ceilings in budgets.json."""

import json

from _common import TESTS, NEVER_LOADED, md_files, rel, text, ROLES, SCENARIOS, scenario_totals


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
    legacy = {"stack", "locate-repo"} | {
        f"{v}-{g}" for v in ("gh", "gl", "bb") for g in ("fetch", "worktree", "post", "thread")}
    per_file = {rel(p): 1 for p in md_files()}
    absent = {n: set(v["absent"]) - legacy
              for n, v in scenario_totals(per_file).items() if set(v["absent"]) - legacy}
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
