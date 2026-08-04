# What a review looks like

A posted review carries three things at once, and they belong to one another:

1. **The overview** — what the whole diff amounts to, anchored to the commit it was read at, grouped by
   severity. FILE-level findings live here, because they have no single line to sit on.
2. **A comment on the exact line** — LINE-level findings, each with the corrected code in a
   `suggestion` block so the author can commit it from the page.
3. **The reply** — `/open-pr:fix` answers on that same thread once the fix is pushed, so the
   conversation stays where the problem was raised rather than restarting at the top of the PR.

The screenshot below is one review, on a pull request in this repository, in the language that repo's
`settings.json` selected.

![An overview, a line comment with a suggested change, and the reply left after the fix was pushed](./images/review-demo-en.png)

The language is per repo, not per user: `shared.output_language` decides what gets POSTED, and it is
independent of the language the agent talks to you in. The same review in
[Vietnamese](./vi/demo.md) and [Japanese](./ja/demo.md).

Severity is the author's contract with the reviewer: 🔴 MUST FIX · 🟠 SHOULD FIX · 🔵 SUGGESTION ·
📝 NOTE. `/open-pr:fix` acts on 🔴 and 🟠 on its own and always asks before touching a 🔵 or a 📝. A diff
with nothing to say gets one line — **LGTM 🌟** — and no headings at all.

Back to [the README](../README.md) · [Configuration](./configuration.md) ·
[What it reviews](./review-criteria.md)
