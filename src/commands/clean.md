---
argument-hint: "[repo name...]"
description: Remove the git worktrees review checked PR code out into. Each one is a full checkout on disk; nothing else is touched.
---

> **CRITICAL:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/guardrails.md` FIRST — shared rules, not repeated
> here. On top of those:
> - Deletes ONLY directories under `~/.open-pr-data/review/*/worktrees/`. FORBIDDEN, in the same tree and
>   unrecoverable: `memory.md`, `memories/`, `templates/`, `ALWAYS_RULE.md`, `settings.json`,
>   `~/.open-pr-data/review/.git`, and any path outside `~/.open-pr-data/review/*/worktrees/`.
> - FORBIDDEN: deleting anything before the user answers Step 3.
> - Reads no PR and needs no vendor CLI.
>
> This CRITICAL block is the SOLE enforcement layer — no `allowed-tools` backs it (deliberate).

## Step 1 — Find the worktrees

Every worktree `/open-pr:review` made sits under `~/.open-pr-data/review/`, whatever pwd is. FORBIDDEN: `cd`.

```bash
[ -d "$HOME/.open-pr-data/review" ] && find "$HOME/.open-pr-data/review" -mindepth 3 -maxdepth 3 -type d -path '*/worktrees/*' 2>&1
```

None → say there is nothing to clean, STOP.

## Step 2 — Narrow, then size

`ARGUMENTS` non-empty ⇒ keep only worktrees whose `<repo>` segment it names, case-insensitive; 0
matched ⇒ STOP, listing the `<repo>`s found. Over what remains — never over what was just dropped,
since each is a full checkout and `du` walks all of it:

```bash
du -sh <each worktree>
```

## Step 3 — Show what would go, then ask

ONE CHOICE per `core/guardrails.md`, EXACTLY 2 options. Its body lists every worktree by path with its
size and the total ⇒ consent covers a list the user has read:

- `Remove all N (Recommended)` — detail: the reclaimed total; review re-creates a worktree next run ⇒
  only disk is lost, unless `/open-pr:fix` committed there and never pushed
- `Keep them` — detail: nothing deleted

Subset wanted (free text, or a re-run naming those repos) ⇒ honour it, those only. `Keep them` ⇒ STOP.

## Step 4 — Remove

Per worktree, in this order — a bare `rm -rf` leaves a stale worktree registration behind:

```bash
git -C "<worktree>" rev-parse --git-common-dir     # ABSOLUTE <repo>/.git; <repo> = that minus /.git
git -C "<repo>" worktree remove --force "<worktree>"
```

`--force`: the checkout is detached + holds untracked review scratch files.

That first command failing (repo moved/deleted) ⇒ registration already orphaned: `rm -rf "<worktree>"`
instead.

Finish with `git -C "<repo>" worktree prune` per distinct repo — drops stale registrations.

## Step 5 — Report

Per repo: how many worktrees went and how much disk came back. Then, once: `~/.open-pr-data/review/` still
holds this repo's memory and settings — only the checkouts were removed.

ARGUMENTS: $ARGUMENTS
