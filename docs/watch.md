# Watch a repo: review on request, fix your own PRs

[← README](../README.md)

`/open-pr:watch` turns the terminal you run it in into a watcher for one or more repositories, in two
roles at once:

- **review** — a developer asks for a review by commenting on the pull request; your machine opens a
  separate review session for it.
- **fix** — a new review on one of your own pull requests toasts its findings with "Fix now"; one click
  opens a separate fix session for it.

It tells you whenever something needs you. `/open-pr:watch review` or `/open-pr:watch fix` keeps one
role only.

## Before the first run

1. Run `/open-pr:review <any PR URL>` once in each repository. The watcher refuses a repository whose
   review memory is not set up, so that several sessions never set it up at once.
2. Run `/open-pr:watch` inside a repository, or in a workspace folder holding several. It lists
   every repository and remote found there (a clone with a remote per host is listed once per remote)
   and asks which to watch; those with review memory set up are recommended.
   `/open-pr:watch owner/api owner/web` (or PR URLs) picks directly; PR URLs also limit the fix role to
   those pull requests.
3. The first run in a repository asks how many review sessions may be active at once, what asks for a
   review (`/open-pr` or a mention of you) and which toasts you want, and saves the answers in that
   repository's `settings.json`.
4. Review sessions start in the folder you run the watcher from, as if you typed `/open-pr:review`
   there — same data directory, same trust. On Claude Code that folder must be a trusted workspace; the
   watcher checks at start and, if it is not, tells you to open `claude` there once and accept the
   trust prompt.

Each watched repository keeps its own settings, including its session limit (review and fix sessions
share it). A repository has at most one watcher per machine and role: a review watcher and a fix
watcher (`/open-pr:watch review` in one tab, `/open-pr:watch fix` in another) run side by side, each
delivering only its own role. A second watcher for a role already taken names the process that has it
and leaves that repository alone. When the host stays unreachable (no network, an expired login), the watcher tells you.

## Asking for a review

Comment on the pull request:

```
/open-pr
/open-pr please look closely at the migration
```

Text after `/open-pr` is a hint about where to look — or a question (`/open-pr why is this lock
needed?`), answered in the comment's thread instead of a review. A mention trigger only asks for
reviews: a question addressed to you that way is toasted to you, never answered by the watcher. It is treated as data: it cannot change how the
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

- The watcher replies to the comment (in its thread; a GitHub conversation comment has none, so the
  reply quotes it with its link) — "taking a look (commit abc1234)", in the request's language — naming
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
- A merged or closed pull request leaves the menu bar within 10 minutes, and its session is stopped
  once idle (its conversation is kept).

## Fixing your own pull requests

The fix role watches the pull requests you opened (the author is the account the watcher runs as), or
only those you named. A pull request also joins when you ask for a review of it yourself — comment
`/open-pr` on your own pull request, and its findings come back to you.

1. A new review from this plugin lands with findings nobody replied to yet: a toast says
   "#12: 2 🟠 SHOULD FIX, 4 🔵 SUGGESTION" with **Fix now**; the menu bar row offers the same.
2. Click **Fix now** (or say `fix #12` to the watcher). A session named `fix <owner>/<repo>#12` runs
   `/open-pr:fix` in its own worktree of the pull request's branch — the tree you are working in is never
   touched. 🔵 and 📝 findings still ask you first; with `auto_push` off it asks before pushing.
3. When it is done, the watcher toasts the result and asks whether to ask for a re-review. Only on
   your yes does it reply on the pull request with the trigger (`/open-pr re-review`, or a mention of
   the reviewer when the repository uses mentions) — it never asks for one on its own. The request
   goes in the thread of the original review request, so request, claim and re-review stay together;
   a GitHub conversation comment has no thread, so there it is a new comment.

Nothing is fixed without your click. `remove #12` (or the row's "Remove from list") takes a pull
request out of both roles.

## Opening a session

A toast in the top-right corner says what is happening — "Reviewing PR #12", "Posted review on PR #12 —
1 🔴 2 🟠", "LGTM on PR #12", a draft waiting, a session needing an answer. Click it to go where you act: a
session's question opens that session in your terminal, the watcher's own question or an error brings
the watcher's tab forward, anything else opens the pull request; hover to keep it on screen and show its close button and "1h" control, which turns toasts off for an hour. When you have to
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

A watcher puts the moth in the menu bar when it starts, with the number of sessions in progress. There
is one for the whole machine, covering every watcher; it stays until `/open-pr:menubar close` (or its
Quit item), and `/open-pr:menubar` brings it back. Its menu lists:

- one row per pull request and role, grouped by watcher (titled with the repos it watches; under them
  the role it serves, its terminal, the folder it runs in when that is not its one repo, and when it
  last polled — `no poll for …` in orange once it missed two polls; each row under the watcher of its
  role); a watcher with none says "No pull requests yet"; review rows first,
  then fix rows, each labelled `· review` or `· fix` — the group's "Go to watcher
  tab" brings that terminal tab to the front (iTerm and Terminal select the exact tab after macOS asks
  once for Automation permission; otherwise the terminal app comes to the front; a watcher whose tab was
  closed is reopened with `claude attach`), and its "Stop" ends every repo it watches, leaving another role's watcher running; a row shows the latest
  state in place (reviewing, posted with counts, LGTM, draft, needs an answer, new findings, fixing,
  fixed, failed) and always offers: **Fix now** on a row with new findings,
  open the pull request, open its session in the terminal that watcher runs in (a new tab of iTerm,
  Terminal, Ghostty or WezTerm; any other terminal opens Terminal), copy the command;
- under each watcher, **Settings** (with several repos, **Settings ▸ <repo>**): that repo's settings,
  each showing its current value — sessions at once (1, 2, 3, 5, 8, 10), poll every (1, 2, 3, 5 or
  10 minutes, each with its requests per hour), trigger (`/open-pr` or `@me`), one toast checkmark per
  event, and the review options: post reviews without a draft, post LGTM when nothing is found, resolve
  fixed findings, warn about failing CI, doctor every (1 week, 2 weeks, 1 month, 3 months, never). Its
  last line says when the doctor last ran and when it runs next: `Doctor: Sep 20, 2026 · next in 11
  days`, `· due now`, `· not scheduled`, or `Doctor: never run`;
- poll every 15 s, 30 s, 1, 2, 3, 5 or 10 minutes, or each repo's setting — applies within seconds, each
  with its estimated requests per hour (see Rate limits);
- snooze: 30 minutes, 1 hour, until 9:00 tomorrow, or turn toasts back on.

A Settings click writes that one key into `settings.json` (see Settings below); a value set in a chat
that the menu does not offer shows checked and greyed out.

A row's "Remove from list" hides the pull request and takes it out of the fix role, a merged or closed
pull request leaves on its own within 10 minutes, and a new request on it brings the row back.

On Windows and Linux, ask the watcher in chat instead (`status`, `snooze 1h`).

## Talking to the watcher

| say | effect |
|---|---|
| `status` | one line per session (pull request, role, state) with its open command |
| `fix #12` | opens the fix session, as **Fix now** does |
| `remove #12` / `unwatch #12` | takes the pull request off the menu bar and out of the fix role |
| `snooze 2h` / `resume toasts` | no toasts on this machine until then — the same switch as the toast's "1h" and the menu bar's snooze; the queue keeps running |
| a setting change | saved to `settings.json` |
| start a fresh session for PR 12 | the next trigger on it opens a new session |
| `stop` | stops watching; open review sessions keep running |

## Rate limits

One poll serves both roles. On GitHub it costs three conditional requests: while nothing changed the
host answers `304 Not Modified`, which does not count against the limit; the fix role adds one call per
own pull request updated since the last poll. On GitLab and Bitbucket a poll costs one call plus one per
pull request updated since the last poll, findings included. With no session active and nothing new for
10 minutes, the watcher polls every 10 minutes (never faster than the setting; a machine-wide "Poll
every" choice always holds). When the host reports a rate limit, the watcher doubles its interval (up to
15 minutes) and returns to `poll_interval_seconds` after the next successful poll.

The menu bar shows, under its header, the tightest quota left on the hosts watched, read from the
rate-limit headers of the poll's own requests (no extra request) — e.g. `GitHub API 4,812/5,000 left`,
orange under 30 % left, red under 10 %. Each "Poll every" choice shows the requests per hour it would
cost, from each repo's last poll, and ⚠ when that passes half the host's hourly limit (GitLab's
per-minute limit counted per hour). Bitbucket may only say it is near its limit; a host that sends no
rate-limit headers shows no gauge.

## Settings

Stored in `<data>/<repo>/settings.json` under `watch`. The menu bar's Settings submenu changes them
(and the review options it lists); a change applies from the watcher's next poll and the next review
session — one already running keeps the values it read. A typed trigger login (`@alice`), the numeric
thresholds and everything the doctor detects stay chat changes.

| field | default | meaning |
|---|---|---|
| `max_concurrent` | `5` | sessions active at once, review and fix together (running or waiting for an answer) |
| `poll_interval_seconds` | `180` | how often the pull requests are checked |
| `notify.review_started` | `true` | toast: a review session opened |
| `notify.question` | `true` | toast: a session needs an answer, or failed |
| `notify.draft_ready` | `true` | toast: a draft review waits for your approval |
| `notify.posted` | `true` | toast: a review was posted, or LGTM |
| `notify.re_review` | `true` | toast: an existing session was resumed for a re-review |
| `notify.findings` | `true` | toast: a new review on a pull request in the fix role, with "Fix now" |
| `notify.error` | `true` | toast: something failed (a claim, a session, the poll) — check the watcher's terminal |
| `trigger` | `/open-pr` | what asks for a review: `/open-pr`, or `@me` for a mention of the account the watcher runs as |
