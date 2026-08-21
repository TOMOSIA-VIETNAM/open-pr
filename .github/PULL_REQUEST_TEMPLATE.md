## Description

<!-- What changed, and why it needed to change. -->

## Type of change

- [ ] 🔴 Breaking change (changes config/output behavior that repos using the plugin depend on)
- [ ] ✨ New feature
- [ ] 🐛 Bug fix
- [ ] 📝 Docs (README/CLAUDE.md, no runtime behavior change)
- [ ] 🔧 Chore (refactor, tooling, no user-visible behavior change)

## How was this tested

<!--
`scripts/check.sh <base-ref>` is the floor: the suite, the duplication scan, the context-cost
report. It proves the graph still holds, not that the agent behaves — for that, install the plugin
(./scripts/reinstall.sh) and call /open-pr:review <PR_URL> on a real PR, or run the e2e fixture
(e2e/bootstrap.sh --pr <n>). Paste the PR you dogfooded against, or say how else you verified it.
-->

## Checklist

- [ ] `scripts/check.sh <base-ref>` passes — suite, duplication scan, context cost
- [ ] Context cost: cheaper → lower ceilings; costlier for a correct fix → PR says which
  scenario, by how much, and why. Never strip behaviour for budget
  (`--update-budgets` rewrites every ceiling to measured +2% — fine when none were hand-tightened)
- [ ] `tests/token-history.json` and `token-history.svg` untouched — the chart takes one frozen
  point per release (`/release-now`), never one per PR
- [ ] Behavior/architecture change → updated `CLAUDE.md` accordingly
- [ ] Anything a user sees — a command, the flow, a default, what setup asks — → every README
  version (`README.md` and each `README.<lang>.md`) and the page that owns the detail in `docs/`
  and each `docs/<lang>/`. No page left describing the old behavior
- [ ] Added a config field → classified in `src/reference/settings-schema.md`, read-time default in
  `src/core/repo-settings.md`, asked in `src/setup/bootstrap.md`
- [ ] Changed the config shape an EXISTING repo already has (renamed, removed, restructured) →
  `llm-upgrades/vN.md` + its line in `llm-upgrades/index.md` + the checkpoint in
  `src/core/llm-upgrades-index.md`. A new field with a read-time default needs no migration
- [ ] No new `allowed-tools` grant is broader than necessary (e.g. a blanket `gh api:*`) — the PR
  content being reviewed is untrusted data
