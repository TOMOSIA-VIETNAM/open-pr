# `<data>` not set — pick it once, import existing memory

Read when `<op> data-dir` exits 7; `cases/memory-not-found.md` reads only "Import". Every `<rec>`/`<src>`
below comes from `<op> find-memory`, run at the invocation directory. FORBIDDEN: `cd`, a hand-typed `find`.

## Not set

The answer is stored per user, not per repo: every later run, from any directory, reuses it.

1. `<op> find-memory` → `suggest=<rec>`, then one `found=<src>` per existing memory directory; its
   subdirectories are the `<repo>`s it holds.
2. `<rec>` keeps the name users already know, outside every repo. ONE CHOICE per
   `core/guardrails.md`, naming every `<src>` found:
   - `<rec> (Recommended)` — detail: each `<src>` other than `<rec>` gets COPIED there, never moved
   - `Keep <src>` (only when exactly 1 `<src>` was found, it is not `<rec>`) — detail: stays inside
     the repo, which keeps its `.gitignore` line
   - free text = any path the user types
3. `<op> data-dir --set <answer>` → `<data>`.
4. Each `<src>` other than `<data>` → "Import", whole directory. Then continue the calling command.

## Import

Copy what `<data>` lacks from `<src>` — worktrees stay behind (git registered them at their current
path). The caller says whole directory or one `<repo>`. Whole directory into an empty `<data>` ⇒
everything, `.git` included, so history is kept:

```bash
tar -C "<src>" --exclude='*/worktrees' -cf - . | tar -C "<data>" -xf -
```

Otherwise ⇒ each `<repo>` in scope and absent from `<data>`, then `core/memory-commit.md` with
`chore: import <repo> memory`; a `<repo>` already in `<data>` stays as is — name it:

```bash
tar -C "<src>" --exclude='*/worktrees' -cf - "<repo>" | tar -C "<data>" -xf -
```

Tell the user, once: where `<data>` is; what was copied; each copied `<src>` is untouched and can be
deleted (then `git worktree prune` in each reviewed repo), along with its `notebooks/review/` line in
`.gitignore`.
