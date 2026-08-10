---
argument-hint: "[repo name...]"
description: Remove the git worktrees review checked PR code out into. Each one is a full checkout on disk; nothing else is touched.
---

> **CRITICAL:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/guardrails.md` FIRST — shared rules, not repeated
> here. On top of those:
> - Deletes ONLY directories under `notebooks/review/*/worktrees/`. FORBIDDEN, in the same tree and
>   unrecoverable: `memory.md`, `memories/`, `templates/`, `ALWAYS_RULE.md`, `settings.json`,
>   `notebooks/review/.git`, and any path outside `notebooks/review/*/worktrees/`.
> - FORBIDDEN: deleting anything before the user answers Step 3.
> - Reads no PR and needs no vendor CLI.
>
> This CRITICAL block is the SOLE enforcement layer — no `allowed-tools` backs it (deliberate).

## Step 1 — Find the worktrees

Same layout `/open-pr:upgrade` searches: `notebooks/review/` sits wherever `/open-pr:review` ran, from
pwd or one level down. FORBIDDEN: `cd`.

```bash
find . -maxdepth 6 -type d -path '*/notebooks/review/*/worktrees/*' 2>&1 | grep -Ev '/worktrees/[^/]+/'
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
size and the total, so consent covers a list the user has read:

- `Remove all N (Recommended)` — detail: the reclaimed total; review re-creates a worktree next run, so
  nothing is lost but disk — unless `/open-pr:fix` committed there and never pushed
- `Keep them` — detail: nothing deleted

Subset wanted (free text, or a re-run naming those repos) ⇒ honour it, those only. `Keep them` ⇒ STOP.

## Step 4 — Remove

Per worktree, in this order — a plain `rm -rf` leaves the reviewed repo registering a worktree that no
longer exists:

```bash
git -C "<worktree>" rev-parse --git-common-dir     # ABSOLUTE <repo>/.git; <repo> = that minus /.git
git -C "<repo>" worktree remove --force "<worktree>"
```

`--force` because the checkout is detached and holds untracked review scratch files.

That first command failing (the repo was moved or deleted) ⇒ the registration is already orphaned:
`rm -rf "<worktree>"` instead.

Finish with `git -C "<repo>" worktree prune` per distinct repo, which drops any stale registration left
by an earlier manual delete.

## Step 5 — Report

Per repo: how many worktrees went and how much disk came back. Then, once: `notebooks/review/` still
holds this repo's memory and settings — only the checkouts were removed.

ARGUMENTS: $ARGUMENTS
