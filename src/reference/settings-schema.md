# `settings.json` schema

One file per reviewed repo: `notebooks/review/<repo>/settings.json`, 1 node per feature. Reference
for `/open-pr:upgrade`, for `llm-upgrades/*.md`, and for a human editing the file by hand.
`review.md`/`fix.md` never `Read` this file — their run-time view is `core/repo-settings.md`.

```json
{
  "schema_version": 1,
  "shared": {
    "chat_language": "vi",
    "output_language": "en",
    "git_remote_type": "github"
  },
  "review": {
    "bootstrapped": true,
    "doctored": true,
    "doctored_at": "2026-07-13T10:00:00Z",
    "doctor_schedule": "1 months",
    "project_docs_found": ["README.md", "CLAUDE.md"],
    "templates_copied": ["rails", "vue"],
    "auto_submit_review": false,
    "auto_resolve_fixed_findings": false,
    "pr_template_paths": [".github/PULL_REQUEST_TEMPLATE.md"],
    "review_ci_status": true,
    "many_files_threshold": 30,
    "big_file_threshold_kb": 20,
    "_comments": {
      "doctor_schedule": "Allowed: \"{N} days\" | \"{N} weeks\" | \"{N} months\" | \"never\". Examples: \"7 days\", \"2 weeks\", \"1 months\". Default: \"1 months\"."
    }
  },
  "fix": {
    "decline_needs_confirmation": true,
    "auto_push": false
  }
}
```

`schema_version`: 1 checkpoint for the WHOLE file, not per node. Written by a fresh bootstrap
(derived live, `core/repo-settings.md` "Fresh file") or by `/open-pr:upgrade` — nobody else, and no
command ever reads it at review/fix time.

`_comments` (under `.review`): a note for a human editor, NOT run-time config — every key inside is
ignored. Bootstrap always writes `doctor_schedule`; any later `Edit` of `.review` keeps the object.

Submodules get NO field here: `review.md` Step 1 tries `Read`ing `<worktree>/.gitmodules` directly
every run, so a repo whose doctor has never run still detects a bump.

## Field groups — classify a new field into exactly 1

| group | node | fields | when missing |
|---|---|---|---|
| User config | `.review` | `auto_submit_review`, `auto_resolve_fixed_findings`, `doctor_schedule`, `review_ci_status`, `many_files_threshold`, `big_file_threshold_kb` | read-time default only; the file is upgraded by `/open-pr:upgrade` alone |
| User config | `.fix` | `decline_needs_confirmation`, `auto_push` | same, owned by `fix.md` |
| User config | `.shared` | `git_remote_type` — both commands need it to pick a vendor file; `output_language` — the language both commands POST in, distinct from `chat_language` | reconciled per run against the PR URL's own shape (`core/pr-target.md` §2), so a stale value is caught rather than trusted |
| Doctor-detected | `.review` | `project_docs_found`, `templates_copied`, `pr_template_paths` | heals itself on the next doctor run; `/open-pr:upgrade` never touches these |
| Detected-once | `.shared` | `chat_language` | detected on demand by whichever command runs first; no fixed default |
| Internal state | `.review` | `bootstrapped`, `doctored`, `doctored_at`, `_comments` | written by bootstrap/doctor exactly when needed |

**Adding a field:** classify it in the table above, and — if it is User config — add its read-time
default to the table in `core/repo-settings.md`, the SOLE place either command reads a default from.
Skipping that leaves an older repo with no fallback until `/open-pr:upgrade` upgrades it.
