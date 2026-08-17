# GitLab — thread interaction

## Reply on a PR

`glab mr note create <pull_number> -R "<owner>/<repo>" --reply <comment_id> -m "<content>"` for BOTH
kinds — `--reply <id>` anchors into the right discussion whether or not it carried a `position`, so
GitLab needs no LINE/FILE distinction here (and unlike GitHub it does have a real
reply-to-overview-note path). `--file`/`--line` are only for CREATING a positioned note, not for a
reply — that last point is unverified against a live `glab`; check `glab mr note --help` if a reply is
rejected.

## Resolve a review thread

`glab api -X PUT
"projects/<owner>%2F<repo>/merge_requests/<pull_number>/discussions/<discussion_id>?resolved=true"` —
`<discussion_id>` from "Fetch review threads", matched to the finding's `comment_id` via that
discussion's `notes[].id`. CLI wrapper: `glab mr note resolve <pull_number> <comment_id> -R
"<owner>/<repo>"`.

## React to a PR comment

`glab api -X POST "projects/<owner>%2F<repo>/notes/<comment_id>/award_emoji" -f
name=<+1|heart|hooray|rocket|confused|eyes>` — GitLab's param is `name`, and `glab` has no dedicated
wrapper for the Emoji Reactions API.

## Finding permalink

**None exists** for a FILE-level finding: there is no review object to anchor to (see "Fetch PR
reviews"). A caller references the finding by file path + short description instead.

## Reply marker

`<!-- bot-reply -->` — an HTML comment, dropped from the rendered page here.
