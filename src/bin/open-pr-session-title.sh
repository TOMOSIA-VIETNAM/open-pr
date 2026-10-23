#!/bin/sh
# Claude Code UserPromptSubmit hook (registered by hooks/hooks.json): when the prompt is
# `/open-pr:review|fix <PR URL>...`, names the session "<role> <ref>, <ref>…" so it is easy
# to find later. Each URL becomes a ref through `open-pr.sh pr-ref` (the owner of every
# vendor's URL shape); refs keep prompt order, duplicates dropped, and show the bare repo
# name unless two refs in one title share it under different owners.
#
# A session that already has a title keeps it, except one this hook gave for the same role:
# that one gets the new refs appended. A hook cannot ask, so a name the user chose, or one
# for the other role, is never touched.
#
# The prompt is data: parsed with jq/grep/awk only, never evaluated. Every failure path exits
# 0 with no output — on this event, stdout is added to the user's context and a non-zero exit
# can block the prompt, so the hook must never be able to stop a command.
exec 2>/dev/null
command -v jq >/dev/null || exit 0
OPR="$(dirname "$0")/open-pr.sh"

input=$(cat)
prompt=$(printf '%s' "$input" | jq -r '.prompt // empty') || exit 0
existing=$(printf '%s' "$input" | jq -r '.session_title // empty') || exit 0

role=$(printf '%s\n' "$prompt" | sed -nE '1s#^/open-pr:(review|fix)([[:space:]].*)?$#\1#p')
[ -n "$role" ] || exit 0

# The refs of a title this hook gave for $role, one per line; any other title ends the run.
REF='[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)* [!#][0-9]+'
old=""
if [ -n "$existing" ]; then
    old=$(printf '%s\n' "$existing" | grep -xE "$role $REF(, $REF)*(, …)?") || exit 0
    old=$(printf '%s\n' "${old#"$role "}" | sed 's/, …$//' | tr ',' '\n' | sed 's/^ //')
fi

# ponytail: 20 URLs at ~60 ms each (one open-pr.sh start per URL) stays well inside the 5 s
# hook timeout, which the prompt waits on; a 200-byte title rarely shows more refs than that.
new=$(printf '%s\n' "$prompt" | grep -oE 'https?://[^[:space:]]+' | awk '!seen[$0]++' | head -n 20 \
    | while IFS= read -r url; do sh "$OPR" pr-ref "$url"; done)
[ -n "$new" ] || exit 0

# Input: "O <old ref>" lines, then "N <namespace>/<repo> <!|#n>" lines. At most 200 bytes: cut
# at a ref boundary, ", …" (5 bytes) marking the refs left out.
# ponytail: an old bare ref carries no owner, so it counts as the same PR as a new ref with
# that repo and number, and never makes a new ref show its owner; keeping the namespace in
# every title would lift that, at the cost of longer titles.
title=$( { printf '%s\n' "$old" | sed '/^$/d; s/^/O /'; printf '%s\n' "$new" | sed 's/^/N /'; } \
    | LC_ALL=C awk -v role="$role" -v max=200 '
        $1 == "O" { r = substr($0, 3); if (!(r in has)) { has[r] = 1; out[++k] = r }; next }
        {
            path = $2; num = $3; if (seen[path " " num]++) next
            repo = path; sub(/.*\//, "", repo)
            if ((repo in ns) && ns[repo] != path) clash[repo] = 1
            ns[repo] = path
            np++; p[np] = path; rp[np] = repo; n[np] = num
        }
        END {
            for (i = 1; i <= np; i++) {
                bare = rp[i] " " n[i]; full = p[i] " " n[i]
                if ((bare in has) || (full in has)) continue
                r = (rp[i] in clash) ? full : bare
                has[r] = 1; out[++k] = r; added++
            }
            if (!added) exit
            for (i = 1; i <= k; i++) {
                nt = (t == "") ? role " " out[i] : t ", " out[i]
                if (t != "" && length(nt) > max - 5) { cut = ", \342\200\246"; break }
                t = nt
            }
            if (length(t) > max) { t = substr(t, 1, max - 3); cut = "\342\200\246" }
            printf "%s%s", t, cut
        }')
[ -n "$title" ] || exit 0

jq -n --arg t "$title" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", sessionTitle: $t}}'
