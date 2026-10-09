# Menu bar: per-repo settings and doctor status

## Goal

Open the menu bar, change a watched repository's open-pr settings without editing
`<data>/<repo>/settings.json` by hand, and see when the doctor last ran and when it runs next.

## Branch and release

- Branch `feat/menubar-settings`, checked out from the tip of `feat/watch-fix` once the poll default
  and quota gauge work has landed there. It builds on the watcher, menu bar and settings code that
  only exists on `feat/watch-fix`; branching from `main` or `feat/watch-review` would mean
  re-merging all of it.
- Merge it back into `feat/watch-fix` when done (stacked, so its review stays small).
- One release for everything: when watch-review, watch-fix and menubar-settings are all done,
  merge `feat/watch-fix` into `feat/watch-review` so the open PR #140 (`feat/watch-review` → `main`)
  carries the whole feature, then release once from `main`. Never squash or force-push PR #140:
  it already has review history.
- Schema: this feature writes existing keys only, so no `schema_version` bump. If the release
  needs a config migration (the settings node renamed `watch_review` → `watch` on `feat/watch-fix`
  is unreleased, so none so far), edit the pending `llm-upgrades/vN.md` on the branch; never add a
  second one.

## UI

A native submenu, no modal: every setting below is a toggle or a pick among a few values, which an
`NSMenu` shows well. A modal window in JXA costs far more and only pays off for free-text fields,
which this feature leaves out.

Each watcher block gets one item `Settings ▸` per repository it watches (one repo ⇒ directly
`Settings ▸`; several ⇒ `Settings ▸ <repo> ▸`):

| group | key | control |
|---|---|---|
| Watch | `watch.max_concurrent` | radio 1, 2, 3, 5, 8, 10 |
| Watch | `watch.poll_interval_seconds` | radio 1, 2, 3, 5, 10 min (each with the requests/hour estimate and the warning the "Poll every" menu shows) |
| Watch | `watch.trigger` | radio `/open-pr` · `@me` (a typed login stays a chat change) |
| Watch | `watch.notify.<event>` | one checkmark per event: review_started, question, draft_ready, posted, re_review, findings, error |
| Review | `review.auto_submit_review` | checkmark |
| Review | `review.post_lgtm` | checkmark |
| Review | `review.auto_resolve_fixed_findings` | checkmark |
| Review | `review.review_ci_status` | checkmark |
| Review | `review.doctor_schedule` | radio 1 week, 2 weeks, 1 month, 3 months, never |
| Doctor | — | read-only line: `Doctor: <doctored_at as date> · next in N days` (or `due now`, or `never run`), from `doctored_at` + `doctor_schedule` (the same rule `open-pr.sh settings` uses for `doctor_due`) |

Left out on purpose: doctor-detected keys (`project_docs_found`, `templates_copied`,
`pr_template_paths`), `schema_version`, numeric thresholds (`many_files_threshold`,
`big_file_threshold_kb`), data directory paths, a typed trigger login. These stay chat or
`/open-pr:upgrade` changes.

The checked item reflects the file's current value with read-time defaults applied (read through
`open-pr.sh settings`, never by parsing the file in JS).

## Writing

- One owner: a new write op in `src/bin/open-pr.sh` (e.g. `settings --repo <repo> --repo-dir D
  --set <key> --value <v>`), not JS editing JSON. It accepts only the keys in the table above,
  validates the value against `src/reference/settings-schema.md`, and writes atomically (temp file +
  rename) under the same lock the watcher uses for its state, so a concurrent read never sees half a
  file. Unknown key or bad value ⇒ exit ≠ 0, file untouched.
- The menu bar calls it like `hide`/`fix-now`: through `open-pr-watch.sh` with argv checked
  against fixed patterns before it runs.
- A running review session that already read settings keeps its values; the change applies from
  the next run, as a hand edit does. The watcher re-reads `poll_interval_seconds` and
  `max_concurrent` at its next poll.

## Tests

- `tests/test_cli.py`: the write op per key type (bool, enum, int, schedule), refusal of an unknown
  key and of a bad value, file untouched on refusal, atomic write, defaults reflected on read.
- `tests/test_watch.py`: the menu bar's argv for a settings change (headless, like `fix-now`);
  scan shows the doctor line for done, due and never-run repositories.
- Real menu bar run (`open-pr-watch.sh menubar` must print `started` and stay alive; empty
  `menubar.log`), one screenshot of the Settings submenu.

## Docs

`docs/watch.md` and its vi-VN, ja-JP, zh-Hans versions: the Settings submenu, what it changes, what
stays a chat change, the doctor line. `src/reference/settings-schema.md`: which keys the menu bar
writes.
