# PR target — shared judgment around `<op> target`

Shared by `commands/review.md` + `commands/fix.md`. `<op> target` is the ONLY extraction point; later
Steps reuse its values, never re-extract. The PATH shape discriminates the vendor ⇒ any host matches.

Text OUTSIDE the URL = free-form instructions for this run (scope, language override) → REASON about
its meaning. FORBIDDEN in any `Bash` call: that raw text — every `<op>` call uses parsed values only.

## 2. `<vendor>` for this run

`<op> target`'s `vendor` decides it. A caller that STORES the value (`.shared.git_remote_type`) MUST
reconcile BEFORE its first fetch:

- not stored → the parsed vendor; it also becomes bootstrap's pre-marked default (never asked twice)
- stored == parsed → stored, nothing to confirm
- stored ≠ parsed → STOP before any fetch; state both values + what the URL's shape indicates; ask;
  WAIT. FORBIDDEN: silently picking one. The confirmed value = `<vendor>` this run, persisted only if
  it actually changed.

A caller that does NOT store it uses the parsed vendor directly.

## 4. Repo name

Memory folder `<repo>` = the `repo` value of `<op> target`. Never from pwd/subdirectory/git remote.
Known limitation: 2 owners with the same repo name share 1 folder.

## 5. "PR info" empty || no `number` → STOP

A passing parse ≠ an existing PR. Empty ⇒ nonexistent / no access / wrong `owner/repo` → print a
SPECIFIC error (not the usage block again), STOP before any further Step.
