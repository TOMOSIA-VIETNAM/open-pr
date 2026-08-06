---
name: open-pr-clean
description: Remove the git worktrees open-pr review checked PR code out into, each a full checkout on disk. Use when reclaiming disk space after reviews. Asks first; takes no URL.
---

1. `Read` `../../adapters/root.md` (relative to this file) → `ROOT` + this platform's tool names.
2. `Read` `ROOT/commands/clean.md` → obey VERBATIM, every step, in order. Arguments handed to this
   skill are that file's `Usage:` block.

This one deletes directories. What may be deleted, and what is unrecoverable if you touch it, is
stated in that file — read it before listing anything, and never delete before the user answers.

FORBIDDEN: summarizing, reordering or skipping a step; deleting from what this file says; treating a
tool you lack as a step you may drop.
