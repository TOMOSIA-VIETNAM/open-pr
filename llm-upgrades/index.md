# llm-upgrades index

Fetched LIVE by `/open-pr:upgrade` — mechanism + line grammar live in `src/core/llm-upgrades-index.md`.
Repo ROOT, sibling of `src/`: never packaged into `/plugin install`, never read at review/fix time.

NOT a changelog — GitHub Releases cover humans. This file answers exactly one question: WHICH config
`schema_version`s need a migration, so a repo's checkpoint can be diffed against it. A version needing
no config migration gets NO entry — an absence is the answer, never an omission to check elsewhere.
`ADDED`/`MODIFIED`/`REMOVED`/`RENAMED` = what happened to config FIELDS; the steps live in `vN.md`.

## Versions

- v1: RENAMED `meta.json` + `fix-meta.json` into `settings.json` (nodes `shared`/`review`/`fix`), ADDED
  `schema_version`, `shared.chat_language`, `shared.git_remote_type`, `shared.output_language`, MODIFIED
  `ALWAYS_RULE.md` — llm-upgrades/v1.md
