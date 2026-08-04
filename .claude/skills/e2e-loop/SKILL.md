---
name: e2e-loop
description: Run the open-pr e2e fixture through a real review in a fresh subagent, grade it against e2e/checklist.md with a second independent subagent, diagnose each failure to the prompt file that owns it, fix, and repeat until clean or the round budget runs out. Use when changing anything under src/ and you want evidence the review still behaves, not just green unit tests.
---

# e2e loop

The unit suite proves the prompt graph is well-formed. It cannot prove a review still comes out right.
This closes that gap: run → grade → diagnose → fix → re-run, with the running and the grading done by
DIFFERENT agents so neither marks its own work.

Costs real money and posts to a real PR on `open-pr-test`. Never start a round the user did not ask for.

## Why subagents rather than this session

A dev session already knows which defects the fixture plants and which rule was just edited. Reviewing
from that context tests the session's memory, not the prompts. Each round therefore spawns fresh agents
that were told nothing beyond what a real user's session gets.

## Round budget

Ask for `max_rounds` if the user did not say; default **2**. Stop early when every checklist row passes,
or when a round produces no NEW passing row — a loop that keeps editing without moving the score is the
failure mode this skill is most likely to hit.

## Preflight

1. `scripts/check.sh <base-ref>` must be green. A red suite makes every later verdict unreadable.
2. `e2e/bootstrap.sh --pr <n> [--vendor …]` if no fixture PR is open for this round.
3. `python3 scripts/vendor_lint.py --pr <n>` — every documented Fetch command must run. A broken
   vendor command wastes a whole round: the review fails at fetch and every checklist row reads
   `fail` for a reason that has nothing to do with the rules being tested. Seconds, and free.
4. Note the fixture URL. Every later stage refers to it.

## Stage 1 — run the review (subagent, fresh)

Spawn a subagent whose whole brief is:

> `Read` `<repo>/src/commands/review.md` VERBATIM and follow it against `<fixture PR url>`.
> Wherever it says `${CLAUDE_PLUGIN_ROOT}`, substitute `<repo>/src` — you are exercising the WORKING
> TREE, not the installed plugin. You have no other instructions and no knowledge of what the PR
> contains.

FORBIDDEN: paraphrasing the command file into the brief, hinting at the planted defects, naming the
stacks involved, or telling it what a good review looks like. Every one of those invalidates the round.

The plugin's own rule already requires a delegated run to read the command file verbatim, so this stage
is the same path a real user's subagent takes.

Covering `/open-pr:fix` in the same round: `e2e/bootstrap.sh --pr <n> --checkout --clone-dir <dir>`
gives a working copy on the fixture branch without touching the remote, and carries this project's
`notebooks/review/<repo>/` into it so the fix has a convention to follow. FORBIDDEN: re-running the
seeding mode for that — it force-pushes the branch the posted review is anchored to.

## Stage 2 — grade it (a DIFFERENT subagent, fresh)

Spawn a second subagent with `e2e/checklist.md`, the fixture URL, and read access to the posted review.
Its brief: for EVERY row and checkbox, return `pass` / `fail` / `partial` plus the exact quote from the
review that justifies the verdict, and nothing else.

FORBIDDEN: this agent proposing fixes, or the Stage 1 agent grading itself — a runner asked to grade
its own output rationalises rather than reports.

A row with no quote to back it is `fail`, not `partial`. Missing evidence IS the finding.

## Stage 3 — diagnose each failure

For every `fail` / `partial`, name the ONE file that owns the rule that should have caught it
(`src/core/review-criteria.md`, a `src/templates/<stack>.md`, a `src/cases/*.md`, a vendor group…).
Then classify:

| cause | fix |
|---|---|
| the rule is missing | add it to the file that owns that axis |
| the rule exists but reads as optional | tighten to `MUST`/`FORBIDDEN:` |
| the rule is in a file that run never loads | move it, or gate the load correctly |
| the rule is stated twice and the copies disagree | delete the copy, keep the owner |
| the checklist expects something no rule ever promised | STOP and ask the user — the checklist may be wrong |

FORBIDDEN: a fix that mentions the fixture, its filenames or its defects. A prompt that only works on
`open-pr-test` is worse than the failure it hides.

## Stage 4 — apply, then re-verify

Apply the fixes. Then `scripts/check.sh <base-ref>`:

- suite red → the fix broke an invariant; fix that before another round
- context cost up → report it per the token rule in `CLAUDE.md`; a passing checklist does not buy a
  budget regression

FORBIDDEN: editing `e2e/checklist.md` to make a failure pass, unless the user agreed in Stage 3 that
the expectation itself was wrong. That is grading your own homework.

Leave the changes uncommitted. Report them; committing and pushing stay the user's call.

## Stage 5 — close the round

1. `e2e/bootstrap.sh --pr <n> --teardown` — closes the fixture PR/MR, leaving its link recorded on the
   project PR as the evidence the round happened.
2. Report, in this shape:

```
round <k>/<max>   <passed>/<total> checklist rows
fixed      <row> ← <file that owned it>
still open <row> ← why, and what it would take
token      <mean delta vs base>, per-scenario deltas if any moved
uncommitted <files>
```

3. Rows still failing && rounds left && the last round moved the score → bootstrap a new fixture and go
   again. Score unmoved ⇒ stop and hand back: two rounds of edits with no new row passing means the
   diagnosis is wrong, and a third round of guessing makes the prompts worse, not better.
