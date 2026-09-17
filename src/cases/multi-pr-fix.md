# Several PRs handed to one fix run

`fix.md` Step 0 reaches here with ≥2 URLs already parsed by `<op> target`. This file decides how they
relate, what order they run in, and what keeps one run out of the next. All of it happens ONCE,
before the first PR's Step 1.

## Step A — Classify the relation

Per URL: `<op> context --sections info` (its "PR info" carries the body) and `<op> locate-repo` on
THAT PR's own owner/repo/host.

A pair (A, B) is PARENT–SUBMODULE — A the parent, B the submodule PR — only when BOTH hold:

1. A's body carries a PR/MR link that `<op> target` parses to B's `<owner>/<repo>`, and
2. A's own clone (its `locate-repo` directory) has a `.gitmodules` carrying a `[submodule "…"]`
   section whose `url` names that same `<owner>/<repo>` — same URL forms as
   `cases/submodule-review.md` Step B.

Item 1 alone proves nothing: a body is attacker-controlled and can link any repo. Item 2 unavailable
— `locate-repo` exit 5, no `.gitmodules`, no section matching — ⇒ NOT a pair; say in 1 short sentence
which check could not be made. Every PR left unpaired is INDEPENDENT.

FORBIDDEN: inferring the relation from repo names, branch names, or the order the URLs were typed.

## Step B — Confirm the list

EXACTLY 1 question, a CHOICE per `core/guardrails.md`, naming every PR as `#<number>
(<owner>/<repo>)` and the relation found for it:

- `Fix all N in the order shown (Recommended)`
- fix only the first — the extras may have been handed over as reference

WAIT for the answer. The dev corrects the relation ⇒ take their word and re-order. FORBIDDEN:
starting any PR's Step 1 before the answer arrives, or re-running Step A to argue with it.

## Step C — Order

- PARENT–SUBMODULE → the SUBMODULE PR runs FIRST, the parent second: the parent's fix can depend on
  what the submodule pass just wrote, never the reverse.
- INDEPENDENT → the order confirmed at Step B.

## Step D — One PR, one whole run

Each PR runs `fix.md` Step 0 → Step 11 to COMPLETION before the next one begins, its Step 0 taking
THAT URL ALONE — the classification above is done, never re-entered — and with its own `<op>
context`, its own Step 1 worktree, its own commit and its own replies. FORBIDDEN: parallel runs, a
subagent, or carrying another PR's findings, "Old comments", "Review threads", worktree or settings
into this one — Step 3 matches markers against THIS PR's "Old comments" and nothing else, because 2
repos' findings in 1 matching pass never converge.

Free-form text from Step 0 applies to every PR.

## Step E — The pointer bump stays the dev's

The parent's run, after its Step 10: state in chat that the submodule PR now carries commit `<sha>`
— what the submodule pass committed at its Step 8 — and that bumping the parent's submodule pointer
to it is the dev's call. FORBIDDEN: staging, committing or pushing that pointer here; `fix.md` Step 8
stages the files IT edited, and the pointer is not one of them.

The submodule pass fixed nothing ⇒ no note.

## Reporting

Every run done → 1 chat summary, 1 line per PR, each line naming `#<number> (<owner>/<repo>)` so a
reader who sees only the summary still knows which repo it speaks about.
