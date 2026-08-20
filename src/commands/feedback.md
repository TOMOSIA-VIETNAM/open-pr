---
argument-hint: "[what should be better]"
description: Report a problem with the open-pr plugin itself, or ask for a change, on its public issue tracker. Reads no PR; writes nothing in your repo.
disable-model-invocation: true
---

> **CRITICAL:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/guardrails.md` FIRST — shared rules, not repeated
> here. On top of those:
> - Destination is FIXED: `TOMOSIA-VIETNAM/open-pr`, the plugin's own tracker. FORBIDDEN: any other
>   repo, and any write to the user's repo, config, memory or worktrees.
> - The issue is PUBLIC and cannot be unposted. FORBIDDEN: creating or commenting before the user
>   approves the exact text at Step 4.
> - Carries the PROBLEM, never the user's work — Step 2.
>
> This CRITICAL block is the SOLE enforcement layer — no `allowed-tools` backs it (deliberate).

## Step 1 — What is being reported

Sources, in order: `ARGUMENTS`, then what THIS chat session shows — which `/open-pr:` command the user
ran, what it did, what they wanted instead. FORBIDDEN: reading the reviewed repo, its diff, its
`notebooks/review/`, its settings or memory.

Both empty ⇒ ONE free-text question — what should change, and what prompted it — then WAIT.

## Step 2 — Strip what identifies the user

Anonymise: a reader MUST NOT be able to tell which repo, company or person it came from.

| in the report | goes in as |
|---|---|
| repo / org / product / host name, remote or PR URL, PR number | drop — "a PR" |
| path, filename, branch, sha, ticket id | its generic kind — "a config file", "a large diff" |
| code, diff, log or error text quoting the user's content | the behaviour, in your own words |
| person name, email, handle | drop |
| token, key, password, internal hostname, IP | drop — never echoed, not even masked |
| vendor (GitHub/GitLab/Bitbucket), stack, language, command name, plugin's own message text | KEEP |

Unsure whether a detail identifies ⇒ drop it.

## Step 3 — Draft it, in English

English whatever the chat language. Title ≤ 70 chars, states the problem. The tracker answers 2 forms
— pick by what is reported, fill that form's fields, nothing else:

| the plugin | form | label | field → content |
|---|---|---|---|
| misbehaved, crashed, reviewed wrongly | `bug_report.yml` | `bug` | `description` ← what it did + what was expected · `steps` ← the sequence that reached it · `version` ← below · `env` ← OS, vendor, stack |
| lacks something, could be better | `feature_request.yml` | `enhancement` | `problem` ← the situation hit · `solution` ← the wish · `alternatives` ← what was tried instead, omitted when nothing was |

FORBIDDEN to fill: `pr_url`, `evidence` — Step 2 strips exactly what they ask for. Only the user, in
the browser, may add them.

Each field: 1-3 sentences. FORBIDDEN in any of them: the chat transcript, your own reasoning or steps,
a proposed diff, apologies.

Version:

```bash
git -C "${CLAUDE_PLUGIN_ROOT}" describe --tags --always
```

No usable output ⇒ `unknown`.

## Step 4 — Check it is not already reported, then ask

`gh` installed && `gh auth status --hostname github.com` succeeds ⇒

```bash
gh search issues --repo TOMOSIA-VIETNAM/open-pr --state all --limit 5 "<2-4 keywords from the title>"
```

Either failing ⇒ no search; the draft still goes to the user, and Step 5 takes path B.

Print the drafted title and every filled field VERBATIM — that text, never a summary — and which form
it goes to. Then ONE CHOICE per `core/guardrails.md`, at most 4 options:

- `Post it (Recommended)` — a public issue on the tracker
- `Comment on #<n>` — the CLOSEST match the search returned, named in the question body along with any
  others; omit this option when the search found nothing, or never ran
- `Edit first` — take the user's changes, redo Step 3
- `Cancel` — nothing is sent

## Step 5 — Send it

`Write` both files first — a multi-line body is not shell-quotable. `$T` ≡ `"${TMPDIR:-/tmp}"`:

| file | holds |
|---|---|
| `$T/open-pr-feedback.json` | 1 flat object: `template` = the form's filename, `title`, 1 key per field ID filled at Step 3 |
| `$T/open-pr-feedback.md` | same fields, each `### <the form's label for it>` + content, in the form's order |

| path | when | run |
|---|---|---|
| A | `gh` authenticated, `Post it` | `gh issue create --repo TOMOSIA-VIETNAM/open-pr --title "<title>" --label <label> --body-file "$T"/open-pr-feedback.md` |
| A | `gh` authenticated, `Comment on #<n>` | `gh issue comment <n> --repo TOMOSIA-VIETNAM/open-pr --body-file "$T"/open-pr-feedback.md` |
| B | no `gh`, not authenticated, or A errored | prefilled link, below — the user submits it |

`--label` rejected (the label was renamed) ⇒ run it again without that flag; nothing else changes.

Path B goes through the form: a blank issue is refused there, and the form is what carries the label.
Print the URL on its own line, clickable:

```bash
python3 -c 'import json,os,urllib.parse as u;d=json.load(open(os.environ.get("TMPDIR","/tmp")+"/open-pr-feedback.json"));print("https://github.com/TOMOSIA-VIETNAM/open-pr/issues/new?"+u.urlencode(d))'
```

No `python3` ⇒ print `https://github.com/TOMOSIA-VIETNAM/open-pr/issues/new/choose` plus the title and
the fields, for the user to paste into the form they pick. A errors (403, network, repo moved) ⇒ print
the error, then path B. FORBIDDEN: a second attempt at a different repo.

## Step 6 — Report

| path | say |
|---|---|
| A | the URL `gh` printed, on its own line — the maintainers see it there |
| B | the issue does NOT exist until they open the link and submit it |

Then, once: nothing in their own repo was read or changed.

ARGUMENTS: $ARGUMENTS
