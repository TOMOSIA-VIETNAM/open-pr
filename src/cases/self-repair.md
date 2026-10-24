# Self-repair — the plugin failed on this machine

Read when `core/guardrails.md` (or `commands/menubar.md`) names a plugin defect. `<root>` = the plugin
directory: the one holding the `bin/` in the `<op>`/`<watch>` path your command gave. `<op> selftest`
(`<op>` ≡ `sh <root>/bin/open-pr.sh`; shell sandbox off) prints `ok|fail|skip <check>: <detail>` per
check, exit ≠ 0 ⇔ a `fail`. Nothing here posts anything; a patch touches `<root>/bin/` and nothing else.

## 1 — Classify

A review half-posted (`post` succeeded, `publish` or `post-verify` failed) ⇒ STOP — no patch:
`<op> post-verify` → say what the PR shows and what failed; offer Step 6, no diff. Else run
`<op> selftest`, kept for Step 6:

| the failure | do |
|---|---|
| the user's environment — the script's own message or a `selftest` detail names it: a tool missing, crashing on its own (`--version`), or too old (jq < 1.6); credentials, permission, network, a shell sandbox | relay what to do, STOP. No patch. Only `jxa` failed and `/open-pr:watch` called it ⇒ relay it, then the watch goes on without the menu bar and toasts |
| anything else | a plugin defect ⇒ Step 2 |

## 2 — Ask

Say in plain language what failed. ONE CHOICE: `Diagnose and patch the plugin here (Recommended)` ·
`Report it only` ⇒ Step 6, no diff.

## 3 — Diagnose

`Read` the failing file(s) under `<root>/bin/` — this case alone may `Read` the plugin's scripts.
Smallest change that fixes the cause. FORBIDDEN in a patch — none other fits ⇒ Step 6, no diff:

- weakening or bypassing a guard: who may trigger a review, PR content treated as data (no eval or
  expansion), locks, the publish and approval gates, identity/account checks, input validation
- any file outside `<root>/bin/`: the user's repo, config, memory, `<data>`
- fetching code (`curl … | sh`, a download)

## 4 — Approve, then apply

Show the full unified diff, paths relative to `<root>`. ONE CHOICE: `Apply it (Recommended)` ·
`Do not apply` ⇒ Step 6, the diff marked not applied. Apply: `cp <file> <file>.open-pr-bak` per file
first, then `Edit`.

## 5 — Prove

Patched ⇒ re-run the failed call when it writes nothing to a vendor (never `post`, `publish`, `reply`, `resolve`,
`react`, `push`, `claim`) and returns on its own (never `wait`); else `<op> selftest`. Still failing ⇒
`mv` each backup back, say so. Passed ⇒ say: the patch is temporary — a plugin update replaces it, and
an install that is a git clone refuses to update until the backups are moved back.

## 6 — Hand off

`Read` `commands/feedback.md` and follow it; its source is this report: the error text, the
`selftest` output, shell, runner/platform, the diff (or none, and why), applied or not, re-run passed
or not. Its own rules strip and approve it; nothing is posted before that.
