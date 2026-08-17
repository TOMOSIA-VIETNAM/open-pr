---
argument-hint: "[what should be better]"
description: Report a problem with the open-pr plugin itself, or ask for a change, on its public issue tracker. Reads no PR; writes nothing in your repo.
---

> **CRITICAL:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/guardrails.md` FIRST — shared rules, not repeated
> here. On top of those:
> - Destination is FIXED: `TOMOSIA-VIETNAM/open-pr`, the plugin's own tracker. FORBIDDEN: any other
>   repo, and any write to the user's repo, config, memory or worktrees — this run only reads the chat.
> - The issue is PUBLIC and cannot be unposted. FORBIDDEN: creating or commenting before the user
>   approves the exact text at Step 4.
> - It carries the PROBLEM, never the user's work. Step 2 is what keeps that true.
>
> This CRITICAL block is the SOLE enforcement layer — no `allowed-tools` backs it (deliberate).

## Step 1 — What is being reported

Sources, in order: `ARGUMENTS`, then what THIS chat session shows — which `/open-pr:` command the user
ran, what it did, what they wanted instead. FORBIDDEN, however useful it looks: reading the reviewed
repo, its diff, its `notebooks/review/`, its settings or memory to enrich the report.

Both empty ⇒ ONE free-text question — what should change, and what prompted it — then WAIT.

## Step 2 — Strip what identifies the user

A reader of the issue MUST NOT be able to tell which repo, company or person it came from.

| in the report | goes in as |
|---|---|
| repo / org / product / host name, remote or PR URL, PR number | drop — "a PR" |
| path, filename, branch, sha, ticket id | its generic kind — "a config file", "a large diff" |
| code, diff, log or error text quoting the user's content | the behaviour, in your own words |
| person name, email, handle | drop |
| token, key, password, internal hostname, IP | drop — never echoed, not even masked |
| vendor (GitHub/GitLab/Bitbucket), stack, language, command name, plugin's own message text | KEEP — the plugin's behaviour depends on these |

Unsure whether a detail identifies ⇒ drop it. Nothing in the issue may need it.

## Step 3 — Draft it, in English

English whatever language the chat is in: the tracker is public and its readers maintain the plugin.
Title ≤ 70 chars, states the problem. Body EXACTLY this shape:

```
### What happened

<1-3 sentences — the behaviour>

### What would be better

<1-3 sentences — the wish>

### Context

- command: `/open-pr:<name>`
- vendor: <GitHub | GitLab | Bitbucket | n/a>
- stack: <what the reviewed project is built in, or n/a>
- plugin: <version, or `unknown`>
```

FORBIDDEN in the body: the chat transcript, your own reasoning or steps, a proposed diff, apologies.

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

Print the drafted title and body VERBATIM — that text, never a summary of it. Then ONE CHOICE per
`core/guardrails.md`, at most 4 options:

- `Post it (Recommended)` — a public issue on the tracker
- `Comment on #<n>` — the CLOSEST match the search returned, named in the question body along with any
  others; omit this option when the search found nothing, or never ran
- `Edit first` — take the user's changes, redo Step 3
- `Cancel` — nothing is sent

## Step 5 — Send it

`Write` the body to `"${TMPDIR:-/tmp}"/open-pr-feedback.md` first — shell quoting reshapes a multi-line
body, a file does not.

| path | when | run |
|---|---|---|
| A | `gh` authenticated, `Post it` | `gh issue create --repo TOMOSIA-VIETNAM/open-pr --title "<title>" --body-file "${TMPDIR:-/tmp}"/open-pr-feedback.md` |
| A | `gh` authenticated, `Comment on #<n>` | `gh issue comment <n> --repo TOMOSIA-VIETNAM/open-pr --body-file "${TMPDIR:-/tmp}"/open-pr-feedback.md` |
| B | no `gh`, not authenticated, or A errored | prefilled link, below — the user submits it |

Path B, printed on its own line so it is clickable:

```bash
python3 -c 'import sys,urllib.parse as u;print("https://github.com/TOMOSIA-VIETNAM/open-pr/issues/new?title="+u.quote(sys.argv[1])+"&body="+u.quote(sys.argv[2]))' "<title>" "$(cat "${TMPDIR:-/tmp}"/open-pr-feedback.md)"
```

No `python3` ⇒ print `https://github.com/TOMOSIA-VIETNAM/open-pr/issues/new` plus the title and body,
for the user to paste. A errors (403, network, repo moved) ⇒ print the error, then path B. FORBIDDEN:
a second attempt at a different repo.

## Step 6 — Report

| path | say |
|---|---|
| A | the URL `gh` printed, on its own line — the maintainers see it there |
| B | the issue does NOT exist until they open the link and submit it |

Then, once: nothing in their own repo was read or changed.

ARGUMENTS: $ARGUMENTS
