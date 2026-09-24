# `<data>` not set — pick it once, import existing memory

Read when `<op> data-dir` exits 7. The answer is stored per user, not per repo: every later run, from any
directory, reuses it.

1. Look for existing memory in `notebooks/review/` below the invocation directory (FORBIDDEN: `cd`):
   ```bash
   find . -maxdepth 2 -type d -path '*/notebooks/review' 2>&1 | grep -Ev 'node_modules'
   ```
   Each hit = one `<src>`; its subdirectories are the `<repo>`s it holds.
2. `<rec>` = `notebooks/review` inside the directory just OUTSIDE the repo — the parent of
   `git rev-parse --show-toplevel` when pwd is in a repo, else pwd itself. Same name users already
   know, outside every repo. ONE CHOICE per `core/guardrails.md`, naming every `<src>` found:
   - `<rec> (Recommended)` — detail: each `<src>` other than `<rec>` gets COPIED there, never moved
   - `Keep <src>` (only when exactly 1 `<src>` was found, it is not `<rec>`) — detail: stays inside
     the repo, which keeps its `.gitignore` line
   - free text = any path the user types
3. `<op> data-dir --set <answer>` → `<data>`.
4. Per `<src>` other than `<data>`, copy what `<data>` lacks — worktrees stay behind (git registered
   them at their current path).
   `<data>` empty ⇒ everything, `.git` included, so history is kept:
   ```bash
   tar -C "<src>" --exclude='*/worktrees' -cf - . | tar -C "<data>" -xf -
   ```
   `<data>` already holds files ⇒ each `<repo>` absent from `<data>`, then `core/memory-commit.md` with
   `chore: import <repo> memory`; a `<repo>` already in `<data>` stays as is — name it:
   ```bash
   tar -C "<src>" --exclude='*/worktrees' -cf - "<repo>" | tar -C "<data>" -xf -
   ```
5. Tell the user, once: where `<data>` is; what was copied; each copied `<src>` is untouched and can be
   deleted (then `git worktree prune` in each reviewed repo), along with its `notebooks/review/` line
   in `.gitignore`. Continue the calling command.
