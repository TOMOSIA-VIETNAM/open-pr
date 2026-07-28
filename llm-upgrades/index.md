# llm-upgrades index

Fetched LIVE by `/open-pr:update-plugin` via `gh api repos/TOMOSIA-VIETNAM/open-pr/contents/llm-upgrades/*`
— lives at the repo ROOT, sibling of `src/`, never packaged into `/plugin install`, never read by
`review.md`/`fix.md` at review time. This is NOT a human-facing changelog (GitHub Releases, drafted
by the dev-only `.claude/commands/release-now.md`, cover that) — this file exists solely so
`/open-pr:update-plugin` can diff a repo's local config `schema_version` against what's available
upstream and fetch only the migrations that actually apply.

## Format

One line per config `schema_version` that requires a migration, inspired by OpenSpec's
ADDED/MODIFIED/REMOVED/RENAMED delta convention (chosen because it matches exactly the shape
`/open-pr:update-plugin` needs to diff by version):

```
- vN: <ADDED|MODIFIED|REMOVED|RENAMED> <short one-line summary> — llm-upgrades/vN.md
```

`ADDED`/`MODIFIED`/`REMOVED`/`RENAMED` describe what happened to config fields in that version. Full
migration steps live in the linked `llm-upgrades/vN.md`; this index only lists WHICH versions exist
and WHAT KIND of change each is, so `/open-pr:update-plugin` fetches only the files it actually needs.

**A `schema_version` that needs no config migration gets NO entry here at all.** This file is the
single source of truth for "does version N need a migration" — a version's absence from this list
always means no action is needed for it, never an omission to double-check elsewhere.

## Versions

- v2: RENAMED merge `meta.json` + `fix-meta.json` into 1 file `settings.json` (node split:
  `shared`/`review`/`fix`), ADDED top-level `schema_version` + `shared.chat_language` — llm-upgrades/v2.md
- v3: ADDED `shared.git_remote_type` (default `"github"` for pre-existing repos) — llm-upgrades/v3.md
