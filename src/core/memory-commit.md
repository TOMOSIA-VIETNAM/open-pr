# Commit into the review-memory repo

Every write under `notebooks/review/` ends here, inside the repo `core/locate-repo.md` established.
`notebooks/review/.git` = 1 nested repo, local only — FORBIDDEN: adding a remote, pushing.

1. `notebooks/review/.git` absent (try `Read` `notebooks/review/.git/HEAD`)? Caller is
   `setup/bootstrap.md` → `git init notebooks/review`. Any OTHER caller → skip committing entirely,
   FORBIDDEN: `git init` (bootstrap's job alone).
2. `git -C notebooks/review add <repo>` (+ `notebooks/review/.gitignore` when just touched).
3. `git -C notebooks/review commit -m "<message>"`.

**Identity:** `git config user.name`/`user.email` at pwd — no `--local`/`--global`, so it resolves
local-then-global, the priority wanted. Found → `git -C notebooks/review -c user.name="<v>" -c
user.email="<v>" commit -m "…"`; `-c` MUST come after `-C` (git's own option order). No identity
anywhere ⇒ the commit errors → only then retry with `-c user.name="review-plugin" -c
user.email="review-plugin@local"`. FORBIDDEN: writing the machine's global config.
