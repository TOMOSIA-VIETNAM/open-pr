# Watch a repo and review on request

[← README](../README.md)

`/open-pr:watch-review` turns the terminal you run it in into a watcher for one or more repositories. A
developer asks for a review by commenting on the pull request; your machine opens a separate review
session for it and tells you when something needs you.

## Before the first run

1. Run `/open-pr:review <any PR URL>` once in each repository. The watcher refuses a repository whose
   review memory is not set up, so that several sessions never set it up at once.
2. Run `/open-pr:watch-review` inside a repository, or in a workspace folder holding several. It lists
   every repository and remote found there (a clone with a remote per host is listed once per remote)
   and asks which to watch; those with review memory set up are recommended.
   `/open-pr:watch-review owner/api owner/web` (or PR URLs) picks directly.
3. The first run in a repository asks how many review sessions may be active at once, what asks for a
   review (`/open-pr` or a mention of you) and which toasts you want, and saves the answers in that
   repository's `settings.json`.
4. Review sessions start in the folder you run the watcher from, as if you typed `/open-pr:review`
   there — same data directory, same trust. On Claude Code that folder must be a trusted workspace; the
   watcher checks at start and, if it is not, tells you to open `claude` there once and accept the
   trust prompt.

Each watched repository keeps its own settings, including its session limit. A repository has at most
one watcher per machine: a second one names the process that already has it and leaves that repository
alone. When the host stays unreachable (no network, an expired login), the watcher tells you.

## Asking for a review

Comment on the pull request:

```
/open-pr
/open-pr please look closely at the migration
```

Text after `/open-pr` is a hint about where to look. It is treated as data: it cannot change how the
review is done, what gets posted, or any setting.

With the "a mention of me" trigger, a comment opening with `@<your login>` asks instead, so no tool
command shows on the pull request. The watcher takes it only when it really asks you to review this
pull request: `@minh please review` counts, `@minh thanks` does not.

Only comments from people with write access trigger a review:

| host | who triggers |
|---|---|
| GitHub | owner, member or collaborator |
| GitLab | Developer or above |
| Bitbucket | anyone who can comment — a non-admin cannot read other users' permissions, so restrict who can comment if that matters |

Comments the plugin posts never trigger; your own do, so one person can be both developer and reviewer.

## What happens next

- The watcher replies to the comment — "reviewing (commit abc1234)", in the request's language — naming
  the commit it took. With several machines watching one repository, that reply is the lock: the first
  reply wins, a machine that finds one steps back, and one that loses a close race deletes its own.
- A session named `review <owner>/<repo>#<number>` runs the normal review. At the session limit, the
  pull request waits in a queue.
- A new request on a pull request that already has a session resumes it when it asks to re-check the
  earlier findings, and opens a new one when it asks for a review from scratch (an old context misleads
  once the pull request has moved on). When unclear, the watcher asks you.
- `auto_submit_review` decides whether the review is published or left as a draft, unless you tell the
  watcher otherwise. A draft is never published without you.
- Once a session has reported its result, it is yours: the watcher stays silent about it and never reads
  what you write there, until the next request on that pull request.
- A Claude Code review session left idle for 10 minutes after its result is stopped to free memory;
  its conversation is kept, so `claude attach <id>` and a later re-review still work. Sessions the
  watcher did not open are never touched.

## Opening a session

A toast in the top-right corner says what is happening — "Reviewing PR #12", "Posted review on PR #12 —
1 🔴 2 🟠", "LGTM on PR #12", a draft waiting, a session needing an answer. Click it to open the pull
request; hover to keep it on screen; its "1h" control turns toasts off for an hour. When you have to
act, it shows the command that opens the session. On macOS the watcher draws the toast itself (no
notification permission needed); on Linux it uses `notify-send`.

Every chat line carries the command that opens the session:

| platform | kind of session | open it with |
|---|---|---|
| Claude Code | interactive, running in the background | `claude attach <id>` |
| Codex | non-interactive | `codex resume <id>` |
| Gemini CLI | non-interactive | `gemini -r <id>` |
| Cursor | non-interactive | `agent --resume <id>` |
| Antigravity | non-interactive | `agy --conversation <id>` |

On Claude Code a session that needs an answer (or a permission) waits until you attach to it. Elsewhere
the session stops with its question; the watcher asks you and resumes it with your answer.

The watcher runs outside the shell sandbox: inside it, polling reaches no host and a Claude Code
background session hangs at starting. Non-interactive sessions use the permission settings you have
configured for that platform; the watcher grants none.

## Menu bar (macOS)

A watcher puts the moth in the menu bar when it starts, with the number of reviews in progress. There
is one for the whole machine, covering every watcher; it stays until `/open-pr:menubar close` (or its
Quit item), and `/open-pr:menubar` brings it back. Its menu lists:

- one row per pull request, grouped by watcher (`<folder> · <terminal>`) — the group's "Go to watcher
  tab" brings that terminal tab to the front (iTerm and Terminal select the exact tab after macOS asks
  once for Automation permission; otherwise the terminal app comes to the front); a row shows the latest
  state in place (reviewing, posted with counts, LGTM, draft, needs an answer, failed) and always offers:
  open the pull request, open its session in the terminal that watcher runs in, copy the command;
- snooze: 30 minutes, 1 hour, until 9:00 tomorrow, or turn toasts back on.

On Windows and Linux, ask the watcher in chat instead (`status`, `snooze 1h`).

## Talking to the watcher

| say | effect |
|---|---|
| `status` | one line per pull request with its state and open command |
| `snooze 2h` / `resume toasts` | no toasts on this machine until then — the same switch as the toast's "1h" and the menu bar's snooze; the queue keeps running |
| a setting change | saved to `settings.json` |
| start a fresh session for PR 12 | the next trigger on it opens a new session |
| `stop` | stops watching; open review sessions keep running |

## Rate limits

Each poll costs three API calls on GitHub; on GitLab and Bitbucket, one plus one per pull request
updated since the last poll. When the host reports a rate limit, the watcher doubles its interval (up
to 15 minutes) and returns to `poll_interval_seconds` after the next successful poll.

## Settings

Stored in `<data>/<repo>/settings.json` under `watch_review`:

| field | default | meaning |
|---|---|---|
| `max_concurrent` | `5` | review sessions active at once (running or waiting for an answer) |
| `poll_interval_seconds` | `60` | how often the pull requests are checked |
| `notify.review_started` | `true` | toast: a review session opened |
| `notify.question` | `true` | toast: a session needs an answer, or failed |
| `notify.draft_ready` | `true` | toast: a draft review waits for your approval |
| `notify.posted` | `true` | toast: a review was posted, or LGTM |
| `notify.re_review` | `true` | toast: an existing session was resumed for a re-review |
| `notify.error` | `true` | toast: something failed (a claim, a session, the poll) — check the watcher's terminal |
| `trigger` | `/open-pr` | what asks for a review: `/open-pr`, or `@me` for a mention of the account the watcher runs as |
