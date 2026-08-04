---
name: open-pr-upgrade
description: Bring every per-repo open-pr config found below the current directory up to the schema this build expects. Use when a command reports a config too old, or after updating the plugin. Takes no PR URL.
---

1. `Read` `../../adapters/root.md` (relative to this file) → `ROOT` + this platform's tool names.
2. `Read` `ROOT/commands/upgrade.md` → obey VERBATIM, every step, in order. Arguments handed to this
   skill are that file's `Usage:` block.

FORBIDDEN: summarizing, reordering or skipping a step; migrating from what this file says; treating a
tool you lack as a step you may drop.
