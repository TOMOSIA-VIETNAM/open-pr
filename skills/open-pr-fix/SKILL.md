---
name: open-pr-fix
description: Act on the findings a review left on a PR or MR — take or decline each by severity, edit the code to match the project, one commit, then reply on the PR. Use when handed a PR or MR URL that has already been reviewed. Edits real code in the current working directory.
---

1. `Read` `../../adapters/root.md` (relative to this file) → `ROOT` + this platform's tool names.
2. `Read` `ROOT/commands/fix.md` → obey VERBATIM, every step, in order. Arguments handed to this
   skill are that file's `Usage:` block.

This one writes to real code and pushes. Its safety checks live in that file and in
`ROOT/core/guardrails.md` — run them where they say, before anything else.

FORBIDDEN: summarizing, reordering or skipping a step; fixing from what this file says; treating a
tool you lack as a step you may drop.
