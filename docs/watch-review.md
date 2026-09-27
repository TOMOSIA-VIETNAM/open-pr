# Watch a repo and review on request

[← README](../README.md)

`/open-pr:watch-review` turns the terminal you run it in into a watcher for one repository. A developer
asks for a review by commenting on the pull request; your machine notices, opens a separate review
session for that pull request, and tells you when something needs you.

## Before the first run

1. Run `/open-pr:review <any PR URL>` once in that repository. The watcher refuses a repository whose
   review memory has not been set up, because several review sessions must not set it up at the same
   time.
2. `cd` into the repository and run `/open-pr:watch-review`. The first run asks how many review
   sessions may be active at once and which notifications you want, and saves both in that
   repository's `settings.json`.

To watch several repositories, open one terminal per repository.

## Asking for a review

Comment on the pull request:

```
@open-pr
@open-pr please look closely at the migration
```

Anything after `@open-pr` is a hint about where to look. It is treated as data: it cannot change how
the review is done, what gets posted, or any setting.

Only comments from people with write access trigger a review (GitHub: owner, member or collaborator;
GitLab: Developer or above). Bitbucket does not let a non-admin read other users' permissions, so on
Bitbucket every `@open-pr` comment triggers a review — restrict who can comment if that matters. The
watcher ignores comments written by the account it runs as.

## What happens next

- The comment gets an 👀 reaction (not on Bitbucket, which has no reactions).
- A review session named `review <owner>/<repo>#<number>` opens and runs the normal review.
- When the limit of active sessions is reached, the pull request waits in a queue.
- A new `@open-pr` comment on a pull request that already has a session resumes that same session,
  so the re-review keeps the earlier context.
- Whether the review is published or left as a draft follows `auto_submit_review`, unless you tell the
  watcher otherwise. A draft is never published without you.

## Opening a session

Every notification and every chat line carries the command that opens that session:

| platform | kind of session | open it with |
|---|---|---|
| Claude Code | interactive, running in the background | `claude attach <id>` |
| Codex | non-interactive | `codex resume <id>` |
| Gemini CLI | non-interactive | `gemini -r <id>` |
| Cursor | non-interactive | `agent --resume <id>` |
| Antigravity | non-interactive | `agy --conversation <id>` |

On Claude Code a session that needs an answer (or a permission) waits until you attach to it. On the
other platforms the session stops with its question; the watcher asks you and resumes the session with
your answer.

Claude Code background sessions need the repository to be a trusted workspace, and must be started
outside Claude Code's shell sandbox. Non-interactive sessions use the permission settings you have
configured for that platform; the watcher does not grant any.

## Talking to the watcher

| say | effect |
|---|---|
| `status` | one line per pull request with its state and open command |
| `snooze 2h` | no notifications until then; the queue keeps running |
| a setting change | saved to `settings.json` |
| start a fresh session for PR 12 | the next trigger on it opens a new session |
| `stop` | stops watching; open review sessions keep running |

## Settings

Stored in `<data>/<repo>/settings.json` under `watch_review`:

| field | default | meaning |
|---|---|---|
| `max_concurrent` | `5` | review sessions active at once (running or waiting for an answer) |
| `poll_interval_seconds` | `60` | how often the pull requests are checked |
| `notify.review_started` | `true` | a review session opened |
| `notify.question` | `true` | a session needs an answer, or failed |
| `notify.draft_ready` | `true` | a draft review waits for your approval |
| `notify.posted` | `true` | a review was posted |
| `notify.re_review` | `true` | an existing session was resumed for a re-review |
| `snooze_until` | `null` | UTC time until which notifications stay off |
