# Recognizing this plugin's own findings and replies

Every finding and every reply ends with a marker: invisible on the PR page, and this plugin's identity
across runs, independent of prose shape (emoji, layout, description length all drift).

WRITE it via `V§"Finding marker"` / `V§"Reply marker"` — the literal is the vendor's, since what renders
to nothing differs per vendor. READ it as `bot-finding`/`bot-reply` inside EITHER an HTML comment or a
link reference definition: a long-lived PR spans a change of form, and an unrecognized marker means that
finding gets posted again as new.

## A past LINE finding

A TOP-LEVEL comment (no `in_reply_to_id`) whose author == "Fetch account running the command",
matching 1 of 2 patterns — test the marker first, fall back only when it misses, never require both:

- **Marker** (the standard): the body carries a finding marker, either form.
- **Fallback** (pre-marker comments only, a migration bridge, never for new findings): the first line
  opens with 🔴/🟠/🔵/📝 immediately followed by a `**Fix**`/`**Gợi ý**` line. Delete this branch once no
  pre-marker PR remains open.

Account `UNKNOWN` (a credential with no user behind it) ⇒ marker branch ONLY; FORBIDDEN: the fallback
there — with no author to match it would claim a human's severity-emoji comment as ours.

## A past FILE-level finding

Lives inside a review `body` rather than as its own comment: that body carries the finding marker and
splits into blocks, each running from a severity-emoji opening line to the marker, each yielding
path + severity + description. Only the account's MOST RECENT review counts — older ones are superseded.

## Already handled in an earlier run

The finding's own thread carries ≥1 reply with the reply marker from the SAME account. Together with
the thread's resolved flag, that is what stops a second commit or reply on work already done.
