# Commit into the review-memory repo

Every write under `~/.open-pr-data/review/` ends here, run from the directory `<op> locate-repo`
established. `~/.open-pr-data/review/.git` = 1 repo shared by every reviewed repo, local only — FORBIDDEN:
adding a remote, pushing.

1. `~/.open-pr-data/review/.git` absent (try `Read` `<memory_dir>/../.git/HEAD`)? Caller is
   `setup/bootstrap.md` → `git init "$HOME/.open-pr-data/review"`. Any OTHER caller → skip committing
   entirely, FORBIDDEN: `git init` (bootstrap's job alone).
2. `git -C "$HOME/.open-pr-data/review" add <repo>` (+ `.gitignore` when just touched).
3. `git -C "$HOME/.open-pr-data/review" commit -m "<message>"`.

**Identity:** `git config user.name`/`user.email` at pwd — no `--local`/`--global`, so it resolves
local-then-global, the priority wanted. Found → `git -C "$HOME/.open-pr-data/review" -c user.name="<v>" -c
user.email="<v>" commit -m "…"`; `-c` MUST come after `-C` (git's own option order). No identity
anywhere ⇒ the commit errors → only then retry with `-c user.name="review-plugin" -c
user.email="review-plugin@local"`. FORBIDDEN: writing the machine's global config.
