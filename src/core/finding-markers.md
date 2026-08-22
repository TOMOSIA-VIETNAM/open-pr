# Recognizing this plugin's own findings and replies

A marker ends every finding and reply this plugin posts — its identity across runs, independent of prose
shape (emoji, layout, length all drift). Match `bot-finding`/`bot-reply` inside EITHER an HTML comment or
a link reference definition — the literal is the vendor's, and a long-lived PR spans a change of form.

## A past LINE finding

A TOP-LEVEL comment (`in_reply_to: null`) whose `user` == the "Account" section — `UNKNOWN` there means there is no author to test, so the Marker branch below is the ONLY test
and the Fallback is FORBIDDEN, or a human's severity-emoji comment gets claimed as ours. Otherwise test
the marker first, fall back only when it misses, never require both:

- **Marker** (the standard): the body carries a finding marker, either form.
- **Fallback** (pre-marker comments only, a migration bridge, never for new findings): the first line
  opens with 🔴/🟠/🔵/📝 then a bolded label line, any language. Delete once no pre-marker PR stays open.

## A past FILE-level finding

Lives inside a review `body` rather than as its own comment: that body carries the finding marker and
splits into blocks, each running from a severity-emoji opening line to the marker, each yielding
path + severity + description. Only the account's MOST RECENT review counts — older ones are superseded.

## Already handled in an earlier run

The finding's own thread carries ≥1 reply with the reply marker from the SAME account. Together with
the thread's resolved flag, that is what stops a second commit or reply on work already done.
