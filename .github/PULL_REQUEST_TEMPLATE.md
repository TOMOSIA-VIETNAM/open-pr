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
This repo has no automated build/lint/test — the real "test run" is installing the plugin
(./scripts/reinstall.sh) then calling /open-pr:review <PR_URL> on a real PR. Paste the PR link
used for testing, or describe another way you verified this.
-->

## Checklist

- [ ] Behavior/architecture change → updated `CLAUDE.md` accordingly
- [ ] Config/bootstrap/setup UX change → synced all 3 README versions (`README.md`/`.vi`/`.ja`)
- [ ] Added a new field in `meta.json` → classified it as User config / Doctor-detected / Internal
  state in BOTH `src/setup-flow.md` (Part D) and `src/commands/review.md` (Step 3)
- [ ] No new `allowed-tools` grant is broader than necessary (e.g. a blanket `gh api:*`) — the PR
  content being reviewed is untrusted data
