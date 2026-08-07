# Recognizing this plugin's own findings and replies

`/open-pr:review` ends every finding with `[bot-finding]: #` and every reply with `[bot-reply]: #` — a
link reference definition, which every vendor's markdown drops from the rendered page, and the stable
identity marker, independent of prose shape (emoji, bullet layout and description length all drift).

A marker MUST be the LAST line of its body and MUST have a BLANK LINE before it. A definition cannot
interrupt a paragraph: pressed against the text above it, GitHub renders `[bot-finding]: #` as a visible
broken link instead of dropping it.

Recognize EITHER form when reading a PR back: `[bot-finding]: #` or an `<!-- bot-finding -->` HTML comment,
same for the reply marker. FORBIDDEN: writing the HTML-comment form — Bitbucket escapes raw HTML, so it
shows up verbatim on the page.

## A past LINE finding

A TOP-LEVEL comment (no `in_reply_to_id`) whose author == "Fetch account running the command",
matching 1 of 2 patterns — test the marker first, fall back only when it misses, never require both:

- **Marker** (the standard): the body contains a finding marker in EITHER form above.
- **Fallback** (pre-marker comments only, a migration bridge, never for new findings): the first line
  opens with 🔴/🟠/🔵/📝 immediately followed by a `**Fix**`/`**Gợi ý**` line. Delete this branch once no
  pre-marker PR remains open.

Account `UNKNOWN` (a credential with no user behind it) ⇒ marker branch ONLY; FORBIDDEN: the fallback
there — with no author to match, it would claim a human's severity-emoji comment as ours.

## A past FILE-level finding

Lives inside a review `body` rather than as its own comment: that body carries the finding marker and
splits into blocks, each running from a severity-emoji opening line to the marker, each yielding
path + severity + description. Only the account's MOST RECENT review counts — older ones are superseded.

## Already handled in an earlier run

The finding's own thread carries ≥1 reply with the reply marker from the SAME account. Together with
the thread's resolved flag, that is what stops a second commit or reply on work already done.
