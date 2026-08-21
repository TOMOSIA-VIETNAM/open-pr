# Repo settings — `notebooks/review/<repo>/settings.json` at run time

`<op> settings` is how a run READS this file: it applies every read-time default and computes
`doctor_due`, so a field it prints may not exist on disk. Full schema + field classification live in
`reference/settings-schema.md` — FORBIDDEN: `Read`ing that file during a review/fix run, nothing here
needs it.

## Node ownership (invariant)

`review.md` ⇄ `.review`; `fix.md` ⇄ `.fix`; both ⇄ `.shared`. Neither ever writes the other's node.
`.shared.git_remote_type` is written ONLY by `setup/bootstrap.md` or a confirmed mismatch
(`core/pr-target.md` §2). `schema_version` is written ONLY by a fresh bootstrap or
`/open-pr:upgrade` — FORBIDDEN: either command reading or checking it.

## Write AS-IS

FORBIDDEN: `Edit`-ing the FILE to backfill a field `<op> settings` defaulted — the default exists at
read time only. Upgrading the file is `/open-pr:upgrade`'s sole job, never inline. Field meanings a run
judges by: `review_ci_status` defaults to whether this run's "CI checks" is non-empty;
`output_language` has no default — ask once, then store.

## `chat_language` (`.shared`, detected once)

The language the agent TALKS in; `output_language` = what it POSTS in — never conflate. BOTH govern
PROSE only ⇒ identifiers, quoted error/log text and domain terms defined only as identifiers stay
VERBATIM in backticks.

Set → use it, no announcement. Missing → detect, stop at first hit: free-form `ARGUMENTS` text →
language already used this session → Claude Code memory → OS locale (`$LANG`/`locale`) → ask per
`cases/language-choice.md`. Write to `.shared.chat_language` ONLY; whichever command detects it first
wins.

## Fresh file → `schema_version`

Never a literal written in any prompt file: `Read`
`"${CLAUDE_PLUGIN_ROOT}"/core/llm-upgrades-index.md` and take the checkpoint it states.
File already exists → keep `schema_version` + every foreign node untouched, add only your own node.
