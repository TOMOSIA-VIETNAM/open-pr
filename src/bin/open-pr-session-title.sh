#!/bin/sh
# Claude Code UserPromptSubmit hook (registered by hooks/hooks.json): when the prompt is
# `/open-pr:review|fix <PR URL>...`, names the session "<role> <ref>, <ref>…" so it is easy
# to find later. Every PR URL in the prompt is listed, in prompt order, duplicates dropped:
#   .../<repo>/-/merge_requests/<n>   -> "<repo> !<n>"
#   .../<repo>/pull/<n>               -> "<repo> #<n>"
#   .../<repo>/pull-requests/<n>      -> "<repo> #<n>"   (Bitbucket Cloud and Server)
# A session that already has a custom title (--name, /rename, an earlier run of this hook)
# keeps it: a hook cannot ask, and a name the user chose is never overwritten.
#
# The prompt is data: parsed with jq/grep/sed/awk only, never evaluated. Every failure path
# exits 0 with no output — on this event, stdout is added to the user's context and a
# non-zero exit can block the prompt, so the hook must never be able to stop a command.
exec 2>/dev/null
command -v jq >/dev/null || exit 0

input=$(cat)
[ -z "$(printf '%s' "$input" | jq -r '.session_title // empty')" ] || exit 0
prompt=$(printf '%s' "$input" | jq -r '.prompt // empty') || exit 0

role=$(printf '%s\n' "$prompt" | sed -nE '1s#^/open-pr:(review|fix)([[:space:]].*)?$#\1#p')
[ -n "$role" ] || exit 0

# At most 200 bytes: cut at a ref boundary, ", …" (5 bytes) marking the refs left out; a
# single ref longer than that is cut mid-ref and ends in "…".
title=$(printf '%s\n' "$prompt" \
    | grep -oE '/[^/[:space:]]+/(-/merge_requests|pull|pull-requests)/[0-9]+' \
    | sed -E 's#^/([^/]+)/-/merge_requests/([0-9]+)$#\1 !\2#; s#^/([^/]+)/pull(-requests)?/([0-9]+)$#\1 \#\3#' \
    | tr -d '\000-\011\013-\037\177' \
    | LC_ALL=C awk -v role="$role" -v max=200 '
        seen[$0]++ { next }
        { nt = (t == "") ? role " " $0 : t ", " $0 }
        t != "" && length(nt) > max - 5 { cut = ", \342\200\246"; exit }
        { t = nt }
        END {
            if (t == "") exit
            if (length(t) > max) { t = substr(t, 1, max - 3); cut = "\342\200\246" }
            printf "%s%s", t, cut
        }')
[ -n "$title" ] || exit 0

jq -n --arg t "$title" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", sessionTitle: $t}}'
