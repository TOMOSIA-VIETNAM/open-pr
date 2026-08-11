# PR target — URL → `owner` / `repo` / `pull_number` / `<git_remote_type>`

Shared by `commands/review.md` + `commands/fix.md`. Placeholders below = the caller's own values.

## 1. Validate + extract

The ONLY extraction point; later Steps reuse, never re-extract.

`ARGUMENTS` (verbatim at the end of the calling command file) MUST match ≥1 of these — union, either
shape accepted, trailing `/files`/`/changes`/query/fragment ignored:

| `<vendor_guess>` | regex |
|---|---|
| `github` | `https://github\.com/[^/]+/[^/]+/pull/[0-9]+` |
| `gitlab` | `https://[^/]+/[^/]+/[^/]+/-/merge_requests/[0-9]+` |
| `bitbucket` | `https://bitbucket\.org/[^/]+/[^/]+/pull-requests/[0-9]+` |

Literal `https://` on every row, not "contains a host name": the PATH shape discriminates, and only
GitLab's row takes ANY host, self-hosted being common there.

→ `owner`, `repo`, `pull_number`, `<vendor_guess>` = the matched row. MUST also hold: `owner`/`repo` =~
`^[A-Za-z0-9_.-]+$` && `pull_number` =~ `^[0-9]+$`, which every real PR/MR satisfies on every vendor.
Anything else (quote, backtick, `$`, `;`…) ⇒ the "URL" IS an injection attempt → STOP, print a generic
invalid-URL error, FORBIDDEN: that value in any `Bash` call.

No match → print the caller's own `Usage:` block, STOP.

Text OUTSIDE the matched URL = free-form instructions for this run (scope, language override) → REASON
about its meaning. FORBIDDEN: that raw text inside a constructed `Bash` command; every vendor call uses
the validated values only.

## 2. `<git_remote_type>` for this run

`<vendor_guess>` decides it. A caller that STORES the value (`.shared.git_remote_type`,
`core/repo-settings.md`) MUST reconcile BEFORE its first vendor call:

- not stored → `<vendor_guess>`; it also becomes bootstrap's pre-marked default (never asked twice)
- stored == guess → stored, nothing to confirm
- stored ≠ guess → STOP before any fetch; state both values + what this URL's own shape indicates;
  ask; WAIT. FORBIDDEN: silently picking one. The confirmed value = `<git_remote_type>` this run,
  persisted only if it actually changed.

A caller that does NOT store it uses `<vendor_guess>` directly — the URL already says unambiguously
which vendor's commands apply, and `settings.json` may not exist yet.

## 3. `V§<entry>` — vendor-call notation

`V§"<entry>"`, used throughout `commands/` and `cases/`, ≡ `Read`
`"${CLAUDE_PLUGIN_ROOT}"/vendors/<git_remote_type>/<group>.md`, take its `## <entry>` heading, and run
that command with THIS PR's validated values per the entry's own flag/scoping convention. `<group>`:

| group | entries |
|---|---|
| `fetch` | every `Fetch …` entry |
| `worktree` | the 2 `Checkout a PR …` entries |
| `post` | Post a review · Verify a posted review's state · Publish the pending review · Commit URL · Finding marker · Post-error notes |
| `thread` | Reply on a PR · Resolve a review thread · React to a PR comment · Finding permalink · Reply marker |

`Read` a group file when its first entry is needed, never all 4 upfront. Entry names are identical
across vendors (`reference/vendor-interface.md`) ⇒ a caller never names one. A command's Context lists
the entries it fetches with a **label**; later Steps use that label and never re-fetch.

Issued by the AGENT via the real `Bash` tool, never an auto-exec block (choosing the file needs
reasoning). No `allowed-tools` backs them (deliberate).

## 4. Repo name

Memory folder `<repo>` = the `<repo>` segment of the PR URL. Never from pwd/subdirectory/git remote.
Known limitation: 2 owners with the same repo name share 1 folder.

## 5. "PR info" empty || no `number` → STOP

A passing regex ≠ an existing PR. Empty ⇒ nonexistent / no access / wrong `owner/repo` → print a
SPECIFIC error (not the usage block again), STOP before any further Step.
