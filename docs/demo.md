# What it looks like

[← README](../README.md)

A posted review carries **three parts** that belong together:

1. **Overview** — what the whole diff amounts to, anchored to the commit it was read at, grouped by severity. FILE-level findings live here (no specific line to sit on).
2. **Line comment** — LINE-level findings, each with the corrected code in a `suggestion` block so the author can commit it straight from the PR page.
3. **Reply** — `/open-pr:fix` answers on that same thread once the fix is pushed. The conversation stays where the problem was raised, instead of restarting at the top of the PR.

The image below is a real review on a PR in this repository, in the language that repo's `settings.json` selected:

![Overview, line comment with a suggested change, and the reply after the fix was pushed](./images/review-demo-en.png)

> [!NOTE]
> Language follows the **repo**, not the user. `shared.output_language` decides what gets **POSTED** on the PR — independent of the language the agent talks to you in chat. Either way it applies to prose only: identifiers the code itself names (`UserChildDivision`, a column, a config key) are quoted verbatim, never translated, so you can grep for what a finding names.

The same review in [Vietnamese](./vi/demo.md) and [Japanese](./ja/demo.md).

## Severity

This is the “contract” between reviewer and author:

| | Level | `/open-pr:fix` |
| --- | --- | --- |
| 🔴 | MUST FIX | handles on its own |
| 🟠 | SHOULD FIX | handles on its own |
| 🔵 | SUGGESTION | always **asks** first |
| 📝 | NOTE | always **asks** first |

Nothing to say about the diff → one line **LGTM 🌟**, no headings.

---

[Configuration](./configuration.md) · [What it reviews](./review-criteria.md)
