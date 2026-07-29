# e2e checklist

Run after `/open-pr:review <fixture PR url>` finishes. Assertions are about SHAPE, not wording — the
review is model output and will never be byte-identical twice.

Each planted defect and the path it exercises:

| planted in | expected | exercises |
|---|---|---|
| `app/models/order.rb` — N+1 in `recalculate_all` | a finding on that method, 🔴 or 🟠 | `templates/rails.md` axis 3 |
| same file — 2 writes, no transaction | a finding naming the transaction | `rails` axis 1 |
| same file — `total_cents / 100.0` | a finding citing the repo's own README convention (money in cents) | doctor found `README.md`, memory referenced it |
| `prompts/agent.py` — knowledge-base rule stated 3 ways | a finding about the repeat | `agent-instructions` axis 3, via the EMBEDDED overlay on a `.py` |
| same file — `account_note` interpolated into the system prompt | a finding about untrusted data in the instruction section | `agent-instructions` axis 2 |
| `.claude/commands/deploy.md` — `rm -rf` with no confirmation | a finding, 🔴 | `agent-instructions` axis 2, base stack on `.md` |
| same file — `see task DEV-4821` | a finding about the ephemeral reference | `agent-instructions` axis 4 |
| `db/seeds_dump.sql` — ~40KB of generated inserts | listed under "Files skipped for detailed review", NOT reviewed line by line | `cases/large-diff-guards.md` |
| PR body — every checklist box unchecked | exactly 1 consolidated 🟠 finding | `cases/pr-template-checklist.md` |

Then check the mechanics:

- [ ] exactly ONE review posted, not several
- [ ] `.py` got BOTH `python` and `agent-instructions` criteria applied
- [ ] every finding ends with `<!-- bot-finding -->`
- [ ] severity is emoji only — no "Must fix" wording, no count of N
- [ ] no heading printed with nothing under it
- [ ] the overview never repeats a line comment's text
- [ ] `notebooks/review/open-pr-test/` was created, and the reviewed repo's `.gitignore` covers it
- [ ] output language matches `.shared.output_language`
- [ ] nothing was pushed to the fixture repo, no branch created, no code edited

Re-review pass — re-run the same command without changing the PR:

- [ ] no duplicate finding for anything already open
- [ ] no second overview when the round found nothing new

Fix pass — `/open-pr:fix <same url>`:

- [ ] refuses to run while the current branch is not the PR's branch
- [ ] 🔵/📝 findings are asked about, never decided alone
- [ ] exactly 1 commit, containing only the files it edited
- [ ] the reply on the PR lands only after a push, and ends with `<!-- bot-reply -->`

Teardown: `e2e/bootstrap.sh --teardown` (deletes the fixture repo).
