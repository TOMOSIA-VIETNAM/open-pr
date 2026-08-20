# Repo settings — `notebooks/review/<repo>/settings.json` at run time

Read/written by `commands/review.md` + `commands/fix.md`. Full schema + field classification live in
`reference/settings-schema.md` — FORBIDDEN: `Read`ing that file during a review/fix run, nothing here needs it.

## Node ownership (invariant)

`review.md` ⇄ `.review`; `fix.md` ⇄ `.fix`; both ⇄ `.shared`. Neither ever writes the other's node.
`.shared.git_remote_type` is written ONLY by `setup/bootstrap.md` or a confirmed mismatch
(`core/pr-target.md` §2). `schema_version` is written ONLY by a fresh bootstrap or
`/open-pr:upgrade` — FORBIDDEN: either command reading or checking it.

## Read AS-IS

FORBIDDEN: diffing a node against fields this run "expects", `Edit`-ing to backfill a missing one. A
field never asked at bootstrap simply isn't there → use its default AT READ TIME ONLY, write nothing.
Upgrading the file is `/open-pr:upgrade`'s sole job, never inline.

| field | node | read-time default |
|---|---|---|
| `auto_submit_review`, `auto_resolve_fixed_findings` | `.review` | `false` |
| `doctor_schedule` | `.review` | `"1 months"` |
| `review_ci_status` | `.review` | this run's "CI checks" non-empty ⇒ `true`, empty ⇒ `false` |
| `many_files_threshold` | `.review` | `30` |
| `big_file_threshold_kb` | `.review` | `20` (≈5,000 tokens @ ~4 chars/token) |
| `project_docs_found`, `templates_copied`, `pr_template_paths` | `.review` | `[]` — doctor-detected |
| `decline_needs_confirmation` | `.fix` | `true` |
| `auto_push` | `.fix` | `false` |
| `git_remote_type` | `.shared` | `core/pr-target.md` §2 |
| `output_language` | `.shared` | none — ask once, then store |

`doctor_due` ⇔ `.review.doctored` != `true` (true even when `doctor_schedule: "never"`) ||
`now > doctored_at + doctor_schedule`. `doctor_schedule` = `{N} days`|`{N} weeks`|`{N} months`|
`never`; `never` ⇒ never due on a schedule (still due on request or `doctored: false`).
Missing/unparsable `doctored_at` while `doctored: true` ⇒ due.

## `chat_language` (`.shared`, detected once)

The language the agent TALKS to the user in; `output_language` = the language it POSTS in. Never
conflate them. BOTH govern PROSE only ⇒ identifiers, quoted error/log text and any domain term this
project defines only as an identifier stay VERBATIM in backticks — `UserChildDivision` stays
`UserChildDivision`, never what it means.

Set → use it, no announcement. Missing → detect, stop at first hit: free-form `ARGUMENTS` text →
language already used earlier this session → Claude Code memory, this project's || the user's → OS
locale (`$LANG`/`locale`) → ask per `cases/language-choice.md`. Write to `.shared.chat_language` ONLY.
Whichever command detects it first wins, the other never re-detects.

## Fresh file → `schema_version`

Never a literal written in any prompt file: `Read`
`"${CLAUDE_PLUGIN_ROOT}"/core/llm-upgrades-index.md` and take the checkpoint it states.
File already exists → keep `schema_version` + every foreign node untouched, add only your own node.

## `.gitignore` at pwd

No `notebooks/review/` line → `Edit`/`Write` to add exactly that line.
