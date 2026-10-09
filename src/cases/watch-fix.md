# Fix role of `/open-pr:watch`

Read by `commands/watch.md` when `<roles>` holds `fix`; its rules, `<op>`, `<watch>`, `<runner>`,
"notify" all hold here. A fix session edits code and pushes: it opens only on the user's go — "Fix
now" (toast, menu bar) or `fix #N` in chat. FORBIDDEN: opening one on a `findings` event alone.
Every notify below adds `--role fix`.

Per `{"event":"findings",…}`: notify `findings` — line 1 `#N: ` + `counts` with each severity's label
(`2 🟠 SHOULD FIX, 4 🔵 SUGGESTION`), line 2 the PR title — `--pr N --url <url>`; the toast carries
"Fix now". 1 chat line: the same + how to start (`fix #N`, or "Fix now" on the toast or menu bar).

Per `{"event":"fix_now",…}`, or `fix #N` in chat (`<url>` = the event's `url`, else the PR's URL you
hold; none ⇒ ask the user):

1. `<watch> paths --pr N --role fix` → `prompts=`, `status_file=`. `<watch> status --pr N --role fix`
   lists a session ⇒ resume it, else a new one; that session `working`/`question` and not `finished`
   ⇒ 1 chat line (already fixing #N, its `open`), nothing else.
2. `Write` `<prompts>/pr-N-fix.md`:
   - resumed: `New findings on <url>: act on them as before. --status-file <status_file>`
   - new, `claude`: `/open-pr:fix <url> --status-file <status_file>`
   - new, other runner: `ROOT: <ROOT>. Read <ROOT>/../adapters/root.md, then <ROOT>/commands/fix.md and obey it VERBATIM. ARGUMENTS: <url> --status-file <status_file>`
     — `<ROOT>` absolute

   Non-`claude` runner: append ` --unattended`.
3. `<watch> spawn --runner <runner> --role fix --pr N --name "fix <owner>/<repo>#N" --prompt-file
   <it> --url <url> --cwd <pwd>`; its output as `commands/watch.md` step 7.

Per `{"event":"session","role":"fix",…}`: `fixed` ⇒ below; any other state as `commands/watch.md`'s
table.

`fixed`: notify `posted` (`fixed #N` + the status file's `counts` + `note`), then ask — notify
`question` first — `Ask for a re-review (Recommended)` · `Not now`. Only on that yes, with
`findings` = `<watch> status --pr N --role fix`'s: `Write` `<prompts>/pr-N-rereview.md` = this repo's
`trigger` when it is a `/word`, else `@<findings.user>`, then ` re-review` — no marker, or it never
triggers — and `<op> reply --vendor … --owner … --repo … --pr N --comment-id <findings.comment_id>
--kind top --body-file <it>` (+ `--thread-id <findings.thread_id>` when set). FORBIDDEN: posting it
without that yes.
