# Recognizing this plugin's own findings and replies

`/open-pr:review` ends every finding with `<!-- bot-finding -->` and every reply with
`<!-- bot-reply -->` — invisible HTML comments on either vendor's PR page, and the stable identity
marker, independent of prose shape (emoji, bullet layout and description length all drift over time).

## A past LINE finding

A TOP-LEVEL comment (no `in_reply_to_id`) whose `user.login` == "Fetch account running the command",
matching 1 of 2 patterns — test the marker first, fall back only when it misses, never require both:

- **Marker** (the standard): the body contains `<!-- bot-finding -->`.
- **Fallback** (pre-marker comments only, a migration bridge, never for new findings): the first line
  opens with 🔴/🟠/🔵/📝 immediately followed by a `**Fix**`/`**Gợi ý**` line. Delete this branch once no
  pre-marker PR remains open.

## A past FILE-level finding

Lives inside a review `body` rather than as its own comment: that body contains `<!-- bot-finding -->`
and splits into blocks, each running from a severity-emoji opening line to the marker, each yielding
path + severity + description. Only the account's MOST RECENT review counts — older ones are superseded.

## Already handled in an earlier run

The finding's own thread carries ≥1 reply with `<!-- bot-reply -->` from the SAME account. Together with
the thread's resolved flag, that is what stops a second commit or reply on work already done.
