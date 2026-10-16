---
argument-hint: "[open|close]"
description: Open or close the macOS menu bar item — reviews and fixes in progress, "Fix now", recent toasts and snooze for every watcher on this machine. A watcher opens it on start.
---

`<watch>` ≡ `sh "${CLAUDE_PLUGIN_ROOT}"/bin/open-pr-watch.sh`, exactly as spelled. Reads no PR; run it
with the shell sandbox off where your shell has one.

`ARGUMENTS` is `close` ⇒ `<watch> menubar --close`; else `<watch> menubar`. Then 1 line in the user's
language:

| prints | say |
|---|---|
| `started`, `running` | it is in the menu bar, covering every watcher here; `/open-pr:menubar close` removes it |
| `closed`, `not running` | closed (or was not open); watching goes on |
| exit 1 | its stderr line: the menu bar did not stay up; run again with the sandbox off |
| `NO-EQUIVALENT` | no menu bar on this platform — a watcher answers `status` and `snooze` in its chat |
