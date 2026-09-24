# Commit into the review-memory repo

Every write under `<data>` (`core/cli.md`) ends here. `<data>/.git` = 1 nested repo, local only —
FORBIDDEN: adding a remote, pushing.

1. `<data>/.git` absent (try `Read` `<data>/.git/HEAD`)? Caller is
   `setup/bootstrap.md` → `git init "<data>"`. Any OTHER caller → skip committing entirely,
   FORBIDDEN: `git init` (bootstrap's job alone).
2. `git -C "<data>" add <repo>` (+ `.gitignore` when just touched).
3. `git -C "<data>" commit -m "<message>"`.

**Identity:** `git config user.name`/`user.email` at pwd — no `--local`/`--global`, so it resolves
local-then-global, the priority wanted. Found → `git -C "<data>" -c user.name="<v>" -c
user.email="<v>" commit -m "…"`; `-c` MUST come after `-C` (git's own option order). No identity
anywhere ⇒ the commit errors → only then retry with `-c user.name="review-plugin" -c
user.email="review-plugin@local"`. FORBIDDEN: writing the machine's global config.
