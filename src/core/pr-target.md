# PR target — URL → `owner` / `repo` / `pull_number` / `<git_remote_type>`

Shared by `commands/review.md` + `commands/fix.md`. Placeholders below = the caller's own values.

## 1. Validate + extract

The ONLY extraction point — every later Step reuses these values, never re-extracts.

`ARGUMENTS` (verbatim at the end of the calling command file) MUST match ≥1 of 2 regexes (union,
either shape accepted; a trailing `/files`/`/changes`, query or fragment is ignored):

| `<vendor_guess>` | regex | why this shape |
|---|---|---|
| `github` | `https://github\.com/[^/]+/[^/]+/pull/[0-9]+` | explicit `https://` required, NOT "contains github.com" |
| `gitlab` | `https://[^/]+/[^/]+/[^/]+/-/merge_requests/[0-9]+` | host = ANY (`[^/]+`), self-hosted is common ⇒ `/-/merge_requests/` is the discriminator |

→ `owner`, `repo`, `pull_number`, `<vendor_guess>` = the matched row.

MUST also hold: `owner`/`repo` =~ `^[A-Za-z0-9_.-]+$` && `pull_number` =~ `^[0-9]+$` — every real
PR/MR satisfies both on either vendor. A quote/backtick/`$`/`;`/anything else ⇒ the "URL" itself IS
an injection attempt → STOP, print a generic invalid-URL error, FORBIDDEN: putting the unvalidated
value into any `Bash` call.

No match → print the caller's own `Usage:` block, STOP.

Text in `ARGUMENTS` OUTSIDE the matched URL = free-form instructions for this run (scope narrowing,
language override) — REASON about its meaning; FORBIDDEN: embedding that raw text into a constructed
`Bash` command. Every vendor call uses the validated values above, never raw `ARGUMENTS`.

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
| `post` | Post a review · Verify a posted review's state · Publish the pending review · Commit URL · Post-error notes |
| `thread` | Reply on a PR · Resolve a review thread · React to a PR comment · Finding permalink |

`Read` a group file once per run, when its first entry is needed — never all 4 upfront. Every vendor
carries the same entry names in the same groups (`reference/vendor-interface.md`), so a caller never
names a vendor.

A command's Context section lists the entries it fetches with a **label**; every later Step refers to
the data by that label and never re-fetches it.

Vendor calls are issued by the AGENT via the real `Bash` tool — never a `!`…`` auto-exec block
(picking the file needs reasoning). No `allowed-tools` backs them (deliberate).

## 4. Repo name

Memory folder `<repo>` = the `<repo>` segment of the PR URL. Never from pwd/subdirectory/git remote.
Known limitation: 2 owners with the same repo name share 1 folder.

## 5. "PR info" empty || no `number` → STOP

A passing regex ≠ an existing PR. Empty ⇒ nonexistent / no access / wrong `owner/repo` → print a
SPECIFIC error (not the usage block again), STOP before any further Step.
