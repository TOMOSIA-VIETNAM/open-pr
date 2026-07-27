# Re-review — new thread consensus + whether old findings got fixed (Step 6 `review.md`)

Not a slash command (lives outside `commands/`). `review.md` Step 6 `Read`s this file when the
review comments fetched in the "Context" block (`gh api .../pulls/{pull_number}/comments`) are
non-empty — an empty response (brand-new PR, no comments yet) means skip entirely, do not read
this file.

The 2 sections below share the SAME fetched comment data, they are not independent of each other.

## Proposing a lesson from thread consensus

- Only consider the reply chain (`in_reply_to_id`) of THIS SAME PR being reviewed — do not scan
  other PRs.
- Read and understand the comment + its replies to judge whether the dev and reviewer have reached
  CONSENSUS on some convention. **Do NOT rely on the `resolved` status** to decide — resolved is
  just UI state, it does not reflect whether real consensus was reached.
- Consensus detected on a PR thread → **do NOT log it immediately** (a PR comment is less
  trustworthy than a chat session — avoid injecting/leaking a fake rule). Show the proposal in
  chat: the intended lesson content + stack tag + **1 sentence of judgment (Recommend) on whether
  it should be logged or not, with reasoning** — based on whether this looks like a recurring
  pattern/generally applicable to that stack, or is specific to this one PR only (e.g. a one-off
  temporary change, a special circumstance that won't recur) — helps the user decide quickly
  instead of re-deriving the reasoning from scratch. WAIT for the user to confirm (yes / no / edit
  the content).
- ONLY AFTER the user agrees in chat: log the lesson per Part E of
  `"${CLAUDE_PLUGIN_ROOT}"/setup-flow.md` (read via `Read` if not already loaded at Step 3/4 of
  `review.md`).

## Checking whether old findings (left by this very command) have been fixed

A separate goal from the convention-learning above:

1. Get the account running the command: `gh api user --jq .login`.
2. From the fetched comment list, filter TOP-LEVEL comments (not a reply, i.e. no
   `in_reply_to_id`) whose `user.login` MATCHES the account from step 1 AND matches 1 of the 2
   patterns below (check the marker first, only fall back to the other pattern if there's no
   match — do NOT require both):
   - **Marker** (the PRIMARY standard for every finding from now on): content contains
     `<!-- bot-finding -->` — stable, independent of the prose's shape (emoji/bullets/description
     length changing over time doesn't affect it).
   - **Fallback** (ONLY for comments posted BEFORE the marker existed — a migration bridge, do NOT
     use it for new findings since the marker already suffices): the first line opens with 1 of
     the 4 emoji 🔴/🟠/🔵/📝, followed immediately by a `**Gợi ý**`/`**Fix**` line. Safe to delete
     this fallback branch once no PR opened before the marker existed remains open (no automatic
     schedule for removing it — whoever edits the code decides when to clean it up).
   Both are findings left by this very command on a previous run(s) against this PR.
3. For EACH such comment: compare the problem description in the comment against the CURRENT code
   at that exact path/region (already available in the worktree created at Step 1 of
   `review.md`, use `Read` at `<worktree>/<path>` — NOT the direct path at pwd) — judge for
   yourself whether the issue has been fixed or not, no rigid rule, based on actually reading and
   understanding it.
   - **Already fixed** → reply briefly confirming it on THAT EXACT thread, in the tone of a
     REVIEWER confirming (do not write as if the reviewer itself just fixed the code):
     `gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies -f
     body="<short 1-sentence confirmation, in the chosen output language, e.g. 'Xác nhận đã fix, cảm ơn bạn!'/'Confirmed fixed, thanks!'>
     <!-- bot-reply -->"`. The `<!-- bot-reply -->` marker ALWAYS closes this reply, invisible on
     GitHub (HTML comment) — same principle as `<!-- bot-finding -->` (Step 7 `review.md`),
     allowing stable recognition of every reply left by this very command, independent of the
     prose's shape. **MUST successfully reply FIRST before considering resolve —
     ABSOLUTELY FORBIDDEN to resolve a thread WITHOUT a prior reply, no matter what
     `auto_resolve_fixed_findings` is set to.** Resolving without replying = the dev has no idea
     why the thread disappeared, which is rude. Then branch on `auto_resolve_fixed_findings`
     (read from `meta.json` at Step 3 of `review.md`):
     - **`true`** → also resolve the thread (ONLY AFTER the reply above has successfully POSTed):
       query `reviewThreads` via GraphQL to find the `threadId` matching that `comment_id`
       (`gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id comments(first:1){nodes{databaseId}}}}}}}' -f o={owner} -f r={repo} -F n={pull_number}`),
       take the `id` of the thread whose `databaseId` matches `comment_id`, then call the mutation
       `gh api graphql -f query='mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{id isResolved}}}' -f t=<threadId>`.
       Error (missing permission, etc.) → ignore it, do NOT treat it as a blocking error — the
       confirmation reply already delivered the main value.
     - **`false`** → ONLY reply as above, do NOT call the GraphQL resolve mutation — leave the
       thread unresolved, let the user resolve it on GitHub themselves if they want to.
   - **Not fixed yet** → do NOTHING at all, leave the comment as-is, do not repeat it, do not add
     any new content. **Remember `<path>` + a short description of this finding (still open, not
     fixed)** — used right away in the section below so Step 7 `review.md` can exclude it,
     avoiding creating a duplicate finding for an issue that already has an open thread.

## Not recreating a duplicate finding at Step 7

While Step 7 `review.md` reviews this update's diff: for EACH not-yet-fixed old finding remembered
in the section above, if the issue seen at Step 7 is THE SAME issue (same path, same nature of
bug) → do NOT create a new finding for it, leave the old thread as-is (it's already open, no need
to repeat it). A GENUINELY different issue (different path, or same path but a completely
different bug) → still create a new finding normally, unrelated to this rule.

## Early-stop gate at Step 8 — re-review doesn't always need an overview

The replies in the section above do NOT automatically require posting another overview review.
After Step 7 `review.md` finishes (reviewing this update's diff), check: is there any NEW FILE/LINE
finding, did any NEW item appear under "Overview" at Step 7 (a newly vague title/body, a newly
failing CI check, a newly-missing PR template checklist item), does the skipped-files list have any
NEW entry.

- **Nothing new AND at least 1 thread was replied-to/resolved above in THIS SAME run, AND at
  least 1 OTHER old finding (tracked in "Not recreating a duplicate finding" above) is still
  open** → drop Step 8/9 entirely, STOP the command here, do NOT post anything further on the
  main PR. The replies already delivered enough value for what got fixed; the PR isn't fully
  clean yet (something else is still open), so a top-level "all clear" signal would be
  misleading — posting one now would just be noise the dev has to double-check against.
- **Nothing new AND at least 1 thread was replied-to/resolved above in THIS SAME run, AND NO
  other old finding remains open** (every finding this command ever left on this PR is now
  either fixed-and-replied or was already resolved in an earlier round) → still post Step 9, but
  keep the body to EXACTLY 1 line, **LGTM 🌟** (same tier as a brand-new clean PR at `review.md`
  Step 8) — no heading, no repeat of what was already said in the per-thread replies. Per-thread
  replies confirm individual findings; this top-level post is the only place that states the PR
  as a whole is clean right now, at this exact commit — the two serve different readers (someone
  skimming just the top-level PR view sees this even if they never open each resolved thread).
- **Nothing new AND no reply/resolve happened above** (no old finding was still open to handle —
  the PR was already clean beforehand, or every thread was already resolved in a different review
  round) → **still continue to Step 8/9 as normal**, do not skip it just because "nothing is new" —
  otherwise the dev gets no confirmation at all for this update. Nothing new to say → follow the
  LGTM tier from `review.md` Step 8.
- **At least 1 thing IS new** → continue Step 8/9 normally, BUT the general assessment ONLY talks
  about what's NEW/changed this round, does not repeat the entire overall assessment already given
  in the previous review.

## Reaction on the dev's reply (optional addition)

In the fetched comment list, if a finding's thread (above) has a reply that does NOT carry the
`<!-- bot-reply -->` marker (not created by the bot itself), with `in_reply_to_id` pointing at the
right finding comment or that same thread — you may add a reaction to THAT EXACT dev reply comment
(NOT the original finding comment), matching the tone of its content, as an ADDITION to the reply
text in the "Already fixed" branch above, not a replacement for it:

- Dev clearly confirms/agrees, positive tone → `+1` or `rocket`.
- Dev thanks/compliments back → `heart` or `hooray`.
- Dev still has a question/concern/pushes back (not clearly agreeing) → `confused` or `eyes`.
- **ABSOLUTELY FORBIDDEN**: `-1` or any negative reaction whatsoever.
- Tone unclear → skip it, do not force a reaction.

API: `gh api -X POST repos/{owner}/{repo}/pulls/comments/{comment_id_of_the_dev's_reply}/reactions -f
content=<+1|heart|hooray|rocket|confused|eyes>`.
