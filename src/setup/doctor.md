# Doctor — discover the reviewed project's own conventions

Goal: the project already documents its conventions somewhere → the review must REFERENCE that exact
source, never guess or impose an unrelated external rule. Every run scans the ENTIRE repo, never
scoped to the current PR's stack or feature.

1. RECURSIVELY scan the whole tree of the located repo — real projects scatter these across subfolders (e.g.
   `app/operation/AGENTS.md` as well as a root file). Targets: `README.md`, `CLAUDE.md`, `AGENTS.md`,
   `GEMINI.md` + similar agent-instruction `.md` variants, `docs/`, `wiki/`,
   `.cursorrules`/`.cursor/rules/`, `.github/copilot-instructions.md`. Absent → skip, not an error.

   Run this with `Agent` IN PARALLEL on large repos: 1 subagent globs/greps the tree → the list of
   paths; then several subagents (1 file or group each) read + summarize + surface conflicts. No
   specific subagent type — stays portable across environments.

   SAME pass, no separate step: also collect the PR-template paths that actually exist among
   `.github/PULL_REQUEST_TEMPLATE.md`, `.github/pull_request_template.md`,
   `.github/PULL_REQUEST_TEMPLATE/*.md`, `PULL_REQUEST_TEMPLATE.md`, `docs/PULL_REQUEST_TEMPLATE.md`.
2. Read each source's convention/review-criteria parts only — skip product intro, install/deploy.
3. FORBIDDEN: copying that content into memory. Each clear, non-conflicting source → 1 REFERENCE line
   in `memory.md`, format per its own index comment, e.g.
   `- [rails] [Controllers](app/controllers/AGENTS.md) — thin, no params.permit`. The reviewing agent
   re-reads that path when needed — never a cached copy.
4. **Conflict** (2 sources disagree, || 1 source contradicts itself, || a source contradicts
   the baseline in `core/review-criteria.md` or a stack template) → reconcile with your own judgment: prefer a source written
   for convention/AI agents (`CLAUDE.md`/`AGENTS.md`) over a general `README.md`, and specific over
   generic. Record the reconciled version as 1 lesson (`setup/lesson.md`), authored by you, naming
   which sources conflicted and why this direction won. This is the ONE lesson logged WITHOUT the
   user's confirmation.
5. `.review` ← `"doctored": true`, `"doctored_at": "<now, ISO 8601 with time — e.g. 2026-08-22T10:00:00Z>"`, `"project_docs_found": [step 1]`,
   `"pr_template_paths": [step 1]`.
6. `core/memory-commit.md`.
