# Bootstrap the `.fix` node

Reached on the first `/open-pr:fix` in a repo — `settings.json` absent, or present without a `.fix` node.

Ask the dev both questions in 1 batch, defaults pre-marked, WAIT for a complete answer:

| field | question | default |
|---|---|---|
| `decline_needs_confirmation` | must a MUST/SHOULD FIX finding the agent itself judges wrong get the dev's confirmation before being declined? | **true** |
| `auto_push` | `git push` automatically once fixed, or stop at local and wait for the dev's order? | **false** |

No answer → the defaults. Then write `.fix`:

- new file → `schema_version` per `core/repo-settings.md` "Fresh file", `.fix` and nothing else
- existing file → `Edit` in place, adding `.fix`, leaving `schema_version`/`.review`/`.shared` untouched

A repo that never ran `/open-pr:review` still gets `settings.json` with just a `.fix` node. FORBIDDEN:
creating `memory.md`/`ALWAYS_RULE.md`/`templates/` here — those are `review.md`'s, and `fix.md` Step 4
skips itself when that directory is absent.

Then `core/memory-commit.md`, and the `.gitignore` rule in `core/repo-settings.md`.
