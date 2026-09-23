# Bootstrap `~/.open-pr/review/<repo>/`

Everything below writes under `<memory_dir>` (`<op> settings`), never at pwd — FORBIDDEN: `cd`,
inferring `<repo>` from any directory's basename (`<repo>` = `core/pr-target.md` §4). `cp` for a verbatim
file copy (never Read+Write through context), `mkdir -p` for directories.

## 0. Pre-migration?

`<memory_dir>/meta.json` exists ⇒ an older build configured this repo. STOP, write nothing:
user runs `/open-pr:upgrade` once, then re-invokes. Bootstrapping over it re-asks settled answers.

## 1. Skeleton

- `cp "${CLAUDE_PLUGIN_ROOT}/seeds/memory.md" "<memory_dir>/memory.md"` — an empty index
  whose own comment defines the entry format every later write follows.
- `memories/.gitkeep`, `templates/.gitkeep` — empty.
- `~/.open-pr/review/.gitignore` MUST contain the line `worktrees/` (`Write` it when absent, `Edit` to
  append when the file exists without it). It keeps the ephemeral worktree out of the memory repo,
  which only ever holds rules/memory/templates.
- `cp "${CLAUDE_PLUGIN_ROOT}/seeds/ALWAYS_RULE.md" "<memory_dir>/ALWAYS_RULE.md"` — an
  empty file for the team's own rules, theirs from here on. The plugin's baseline criteria are NOT in
  it (`core/review-criteria.md` owns those) — FORBIDDEN: writing criteria into this copy.

## 2. Ask — 1 batch, every option pre-marked with the default below

q7 is conditional ⇒ 8 or 9 questions. The choice-Q&A feature caps questions per call ⇒ split into
SEQUENTIAL calls of at most 4 (q1-4, then q5-8, then the rest), finishing one before the next.

| # | field | values | default |
|---|---|---|---|
| 1 | `git_remote_type` | `github`/`gitlab`/`bitbucket`, as `<op> target` parses them | the parsed vendor, already computed by the caller (`core/pr-target.md` §2) — reuse, FORBIDDEN: re-deriving or asking twice |
| 2 | `output_language` | the language findings/replies get POSTED in — offer per `cases/language-choice.md` | that file's own |
| 3 | `auto_submit_review` | `true` = published when the run ends; `false` = seen by you alone, in this vendor's draft or — where it has none — in THIS CHAT. FORBIDDEN: promising a draft ON the PR without knowing this vendor has them | `false` |
| 4 | `auto_resolve_fixed_findings` | true/false | `false` |
| 5 | `post_lgtm` | true/false — `true` posts a clean review (no finding at all) on the PR as a review of its own; `false` keeps that one case in chat and puts nothing on the PR | `true` |
| 6 | `doctor_schedule` | `{N} days`\|`{N} weeks`\|`{N} months`\|`never` | `"1 months"` |
| 7 | `review_ci_status` | true/false — ASK ONLY WHEN this PR's "CI checks" array is non-empty (≥1 check ⇒ CI configured). Empty → skip the question, write `false`, no explanation needed | `true` |
| 8 | `many_files_threshold` | file count above which review strategy gets asked first | `30` |
| 9 | `big_file_threshold_kb` | per-file diff KB above which it counts as a large/dump file | `20` |

## 3. Write `settings.json`

`schema_version` per `core/repo-settings.md` "Fresh file". Then:

- `.review` ← `"bootstrapped": true` + q3-q9, plus `_comments.doctor_schedule` = a hint string
  listing the valid `doctor_schedule` values for whoever edits the file by hand (ignored at run
  time, `reference/settings-schema.md`).
- `.shared` ← `"git_remote_type"` = q1 (a value always exists: the reused guess or the user's pick —
  FORBIDDEN: omitting it or writing `false`) + `"output_language"` = q2.
- FORBIDDEN: creating `.fix` here (`fix.md`'s own bootstrap owns it). An existing `.fix`/
  `.shared.chat_language` from a prior `/open-pr:fix` run stays untouched.

## 4. Commit

`core/memory-commit.md` with message
`chore: init review memory for <repo>` (nested repo just created) or
`chore: add review memory for <repo>` (it already existed from another repo's review).
