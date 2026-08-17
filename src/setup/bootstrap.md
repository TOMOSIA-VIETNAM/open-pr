# Bootstrap `notebooks/review/<repo>/`

Everything below happens at the directory `core/locate-repo.md` established — FORBIDDEN: `cd` elsewhere,
inferring `<repo>` from any directory's basename (`<repo>` = `core/pr-target.md` §4). `cp` for a verbatim
file copy (never Read+Write through context), `mkdir -p` for directories.

## 0. Pre-migration?

`notebooks/review/<repo>/meta.json` exists ⇒ an older build configured this repo. STOP, write nothing:
user runs `/open-pr:upgrade` once, then re-invokes. Bootstrapping over it re-asks settled answers.

## 1. Skeleton

- `cp "${CLAUDE_PLUGIN_ROOT}/seeds/memory.md" "notebooks/review/<repo>/memory.md"` — an empty index
  whose own comment defines the entry format every later write follows.
- `memories/.gitkeep`, `templates/.gitkeep` — empty files, so git tracks both dirs.
- `notebooks/review/.gitignore` MUST contain the line `worktrees/` (`Write` it when absent, `Edit` to
  append when the file exists without it). This is the NESTED repo's ignore file, separate from the
  reviewed repo's own `.gitignore` (`core/repo-settings.md`): it keeps the ephemeral worktree
  (`review.md` Step 1) out of the memory repo, which must only ever hold rules/memory/templates.
- `cp "${CLAUDE_PLUGIN_ROOT}/seeds/ALWAYS_RULE.md" "notebooks/review/<repo>/ALWAYS_RULE.md"` — an
  empty file for the team's own rules, theirs from here on. The plugin's baseline criteria are NOT in
  it (`core/review-criteria.md` owns those) — FORBIDDEN: writing criteria into this copy.

## 2. Ask — 1 batch, every option pre-marked with the default below

q6 is conditional ⇒ 7 or 8 questions. The choice-Q&A feature caps questions per call ⇒ split into
SEQUENTIAL calls (q1-4, then the rest), finishing one before the next.

| # | field | values | default |
|---|---|---|---|
| 1 | `git_remote_type` | one `<vendor_guess>` value of `core/pr-target.md` §1's table | `<vendor_guess>` already computed by the caller (`core/pr-target.md` §2) — reuse, FORBIDDEN: re-deriving or asking twice |
| 2 | `output_language` | the language findings/replies get POSTED in — offer per `cases/language-choice.md` | that file's own |
| 3 | `auto_submit_review` | `true` = published when the run ends; `false` = seen by you alone, in this vendor's draft or — where it has none — in THIS CHAT. FORBIDDEN: promising a draft ON the PR without knowing this vendor has them | `false` |
| 4 | `auto_resolve_fixed_findings` | true/false | `false` |
| 5 | `doctor_schedule` | `{N} days`\|`{N} weeks`\|`{N} months`\|`never` | `"1 months"` |
| 6 | `review_ci_status` | true/false — ASK ONLY WHEN this PR's "CI checks" array is non-empty (≥1 check ⇒ CI configured). Empty → skip the question, write `false`, no explanation needed | `true` |
| 7 | `many_files_threshold` | file count above which review strategy gets asked first | `30` |
| 8 | `big_file_threshold_kb` | per-file diff KB above which it counts as a large/dump file | `20` |

## 3. Write `settings.json`

`schema_version` per `core/repo-settings.md` "Fresh file". Then:

- `.review` ← `"bootstrapped": true` + q3-q8, plus `_comments.doctor_schedule` = a hint string
  listing the valid `doctor_schedule` values for whoever edits the file by hand (ignored at run
  time, `reference/settings-schema.md`).
- `.shared` ← `"git_remote_type"` = q1 (a value always exists: the reused guess or the user's pick —
  FORBIDDEN: omitting it or writing `false`) + `"output_language"` = q2.
- FORBIDDEN: creating `.fix` here (`fix.md`'s own bootstrap owns it). An existing `.fix`/
  `.shared.chat_language` from a prior `/open-pr:fix` run stays untouched.

## 4. Ignore + commit

`.gitignore` at pwd per `core/repo-settings.md`, then `core/memory-commit.md` with message
`chore: init review memory for <repo>` (nested repo just created) or
`chore: add review memory for <repo>` (it already existed from another repo's review).
