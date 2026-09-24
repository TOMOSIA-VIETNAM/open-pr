# `memory_found: false` — new repo, or memory kept elsewhere?

The defaults for the two are identical, so BEFORE any bootstrap runs, look for this repo's memory below
the invocation directory (FORBIDDEN: `cd`):

```bash
find . -maxdepth 4 -type d -path '*/notebooks/review/<repo>' 2>&1 | grep -Ev 'node_modules|/worktrees/'
```

- hit → ONE CHOICE per `core/guardrails.md`, one per hit: `Import <hit> (Recommended)` → `Read`
  `cases/data-dir.md` "Import" with `<src>` = the hit's parent, this `<repo>` only, then
  `<op> settings --repo <repo>` again (the file was WRITTEN since) — vs `First run for this repo` →
  the caller's bootstrap
- none → ONE CHOICE: `First run for this repo (Recommended)` → the caller's bootstrap — vs its memory
  sits in another directory ⇒ STOP, print `memory_dir` and say to copy that repo's memory there

A repo bootstrapped elsewhere answers to defaults here, and re-asking setup is the symptom the user sees.
