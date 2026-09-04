# e2e checklist

Run after `/open-pr:review <fixture PR url>` finishes. Assertions are about SHAPE, not wording — the
review is model output and will never be byte-identical twice.

Every row applies to all three vendors except where it names one. Bitbucket has no draft: with
`auto_submit_review: false` the review stays in the chat and nothing reaches the PR, so read those rows
as "not published yet" rather than "pending on the PR".

Each planted defect and the path it exercises:

| planted in | expected | exercises |
|---|---|---|
| `app/models/order.rb` — N+1 in `recalculate_all` | a finding on that method, 🔴 or 🟠 | `templates/rails.md` axis 3 |
| same file — 2 writes, no transaction | a finding naming the transaction | `rails` axis 1 |
| same file — `total_cents / 100.0` | a finding citing the repo's own README convention (money in cents) | doctor found `README.md`, memory referenced it |
| `prompts/agent.py` — knowledge-base rule stated 3 ways | a finding about the repeat | `agent-instructions` axis 3, via the EMBEDDED overlay on a `.py` |
| same file — `account_note` interpolated into the system prompt | a finding about untrusted data in the instruction section | `agent-instructions` axis 2 |
| same file — `history: list = []` default | a finding about the mutable default argument | `templates/python.md` axis 1 — a `.py`-only criterion, so it is the proof the overlay applied BOTH templates and not just one |
| `.claude/commands/deploy.md` — `rm -rf` with no confirmation | a finding, 🔴 | `agent-instructions` axis 2, base stack on `.md` |
| same file — `see task DEV-4821` | a finding about the ephemeral reference | `agent-instructions` axis 4 |
| `db/seeds_dump.sql` — ~40KB of generated inserts | listed under the files-skipped heading, itself written in the output language, NOT reviewed line by line | `cases/large-diff-guards.md` |
| PR body — every checklist box unchecked | exactly 1 consolidated 🟠 finding | `cases/pr-template-checklist.md` |

Then check the mechanics:

- [ ] run it from a WORKSPACE (a parent dir, not a repo): `notebooks/review/open-pr-test/` appears in
      that workspace, NOT inside the cloned repo, and the worktree lands under it too
- [ ] every `Fix` that has a code form arrived as a fence — a LINE one as ` ```suggestion `; inline code
      inside a sentence does not count
- [ ] the chat message after posting is ≤3 sentences with the link and the counts, and repeats NO
      finding text
- [ ] a lesson proposal arrives as a CHOICE with `(Recommended)` on one option, not a prose question
- [ ] with `output_language` non-English, the anchor reads `(commit <link>)` — no "as of"

- [ ] exactly ONE review posted, not several
- [ ] `.py` got BOTH `python` and `agent-instructions` criteria applied — i.e. the mutable-default row
      AND at least one prompt-quality row both produced findings on `prompts/agent.py`
- [ ] every finding ends with the finding marker of `src/core/finding-markers.md`, INVISIBLE on the
      rendered page — a marker you can read on the PR is a defect, not a passing row. Confirm it is
      there by reading the comment's raw body (the vendor's own comment API, or the UI's Edit box)
- [ ] severity is emoji only — no "Must fix" wording, no count of N
- [ ] no heading printed with nothing under it
- [ ] the overview never repeats a line comment's text
- [ ] `notebooks/review/open-pr-test/` was created, and the reviewed repo's `.gitignore` covers it
- [ ] output language matches `.shared.output_language`
- [ ] nothing was pushed to the fixture repo, no branch created, no code edited

Re-review pass — re-run the same command without changing the PR:

- [ ] no duplicate finding for anything already open
- [ ] no second overview when the round found nothing new

Fix pass — needs a working copy of the fixture, on the fixture branch:

```bash
e2e/bootstrap.sh --pr <n> --checkout --clone-dir /tmp/fixture   # no writes to the remote
cd /tmp/fixture                                                 # then /open-pr:fix <fixture url>
```

The checkout also copies this project's `notebooks/review/open-pr-test/` into the clone, so the run has
the learned convention to fix against rather than falling back to ordinary judgment. Expect the
fixture's own `.gitignore` to gain a `notebooks/review/` line, uncommitted — Step 8 commits only the
files Step 7 edited, which is correct.

Then, `/open-pr:fix <same url>`:

- [ ] refuses to run while the current branch is not the PR's branch
- [ ] 🔵/📝 findings are asked about, never decided alone
- [ ] exactly 1 commit, containing only the files it edited
- [ ] the reply on the PR lands only after a push, and ends with `<!-- bot-reply -->`

## Which path a round exercises

The fixture PR is per project PR; the plugin's own setup state is separate and lives at the pwd the
REVIEW runs from — this project, in `notebooks/review/open-pr-test/`.

| that directory | the round exercises | run it when |
|---|---|---|
| present | the warm path: review straight through, no bootstrap, no doctor | the common case — default |
| deleted first | the first-run path: 8 bootstrap questions, doctor reading `README.md`, 3 templates copied | you changed `setup/`, `core/repo-settings.md`, or the schema |

So a later round needs no re-setup: `bootstrap.sh --pr <n>` for a fresh fixture, then review. Only
delete the memory directory when the first-run path is what you mean to test.

Teardown: `e2e/bootstrap.sh --pr <n> --teardown` — closes the fixture PR/MR and deletes its branch. The
fixture repo itself is never touched. The link stays in this project's PR description as the record that
the run happened.

## Windows smoke (once per release that touches `src/bin/`)

On a Windows machine with Git for Windows + jq: run `/open-pr:review` against the GitHub fixture from
Git Bash. What it proves that macOS/Linux runs cannot: the `sh` invocation path, LF survival
(`.gitattributes`), and GNU-vs-BSD `date` handling in `settings`.
