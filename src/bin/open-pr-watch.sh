#!/bin/sh
# open-pr watch runtime: the deterministic half of /open-pr:watch — trigger cursor, the fix-role
# PRs and their new findings, (PR, role) -> session map, slot limit and queue, notifications, and
# how each agent platform opens, resumes and reports a session.
#
#   - usage() is the single source for subcommands, options and exit codes.
#   - stdout is data (JSON lines), stderr is diagnostics.
#   - Vendor data comes ONLY from the sibling open-pr.sh. This is the one file under src/ that
#     invokes an agent platform's CLI; every such command line is in the runner section.
#   - Comment bodies and prompts are DATA (attacker-controlled): prompts travel as one quoted
#     argv element read from a file, notification text as argv, JSON through jq. Nothing
#     fetched is ever evaluated.
#   - Every state write goes to a temp file renamed into place, under a mkdir lock.
#
# Dependencies: jq, and the CLI of the runner in use.
set -eu

# `wait` runs from a private copy of this file (see the dispatch), so SELF_DIR is handed over.
SELF_DIR=${OPEN_PR_WATCH_SELF_DIR:-$(cd "$(dirname "$0")" && pwd)}
RUNNERS="claude codex gemini cursor antigravity"
EVENTS="review_started question draft_ready posted re_review findings error"
# States that end a session's reporting (see `finished` under state).
TERMINAL="posted draft lgtm_chat nothing answered fixed failed stopped"
# A status file's own states.
REPORTED="posted draft lgtm_chat nothing answered fixed failed question"
# Longest rate-limit backoff; the menu bar counts a repo watched while its heartbeat is < 3x this.
BACKOFF_CAP=900

err() { printf '%s\n' "$*" >&2; }
die() { code="$1"; shift; err "$*"; exit "$code"; }
need() {
    command -v "$1" >/dev/null 2>&1 && return 0
    die 1 "open-pr-watch.sh: required tool missing: $1"
}
opr() { sh "$SELF_DIR/open-pr.sh" "$@"; }
now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
# jq `utc`: any ISO-8601 -> UTC `…Z` at second precision, the one form the cursor is stored and
# compared in (vendors print their own zone: self-hosted GitLab gives +09:00).
JQ_UTC='def utc:
    capture("^(?<d>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(\\.[0-9]+)?(?<z>Z|[+-][0-9]{2}:?[0-9]{2})$") as $c
    | ($c.d + "Z" | fromdateiso8601)
      - (if $c.z == "Z" then 0 else ($c.z | capture("(?<s>[+-])(?<h>[0-9]{2}):?(?<m>[0-9]{2})")
            | (if .s == "+" then 1 else -1 end) * ((.h | tonumber) * 3600 + (.m | tonumber) * 60)) end)
    | todate;'
# POSIX sleep only promises integers.
nap() { sleep 0.2 2>/dev/null || sleep 1; }

# ---------------------------------------------------------------- args ----
# --key value -> ARG_<key> (dashes -> _); the key is checked before eval.
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --once) ARG_once=1; shift ;;
            --off) ARG_off=1; shift ;;
            --fresh) ARG_fresh=1; shift ;;
            --close) ARG_close=1; shift ;;
            --*)
                key=$(printf '%s' "${1#--}" | tr '-' '_')
                printf '%s' "$key" | grep -Eq '^[a-z_]+$' || die 1 "open-pr-watch.sh: bad option $1"
                [ $# -ge 2 ] || die 1 "open-pr-watch.sh: $1 needs a value"
                eval "ARG_${key}=\$2"
                shift 2 ;;
            *) die 1 "open-pr-watch.sh: unexpected argument: $1" ;;
        esac
    done
}
arg() { eval "printf '%s' \"\${ARG_$1:-}\""; }
req() { v=$(arg "$1"); [ -n "$v" ] || die 1 "open-pr-watch.sh: --$(printf '%s' "$1" | tr '_' '-') is required"; printf '%s' "$v"; }
check_ident() { printf '%s' "$2" | grep -Eq "$1" || die 4 "open-pr-watch.sh: invalid value: $2"; }
pr_arg() { n=$(req pr); check_ident '^[0-9]+$' "$n"; printf '%s' "$n"; }
role_arg() { r=$(arg role); r=${r:-review}; check_ident '^(review|fix)$' "$r"; printf '%s' "$r"; }
# --roles (default both) -> ROLES, normalized to review | fix | review,fix; SFX = its file suffix.
roles_arg() {
    ROLES=$(arg roles); ROLES=${ROLES:-review,fix}
    check_ident '^(review|fix)(,(review|fix))?$' "$ROLES"
    case ",$ROLES," in *,review,*) case ",$ROLES," in *,fix,*) ROLES=review,fix ;; *) ROLES=review ;; esac ;; *) ROLES=fix ;; esac
    SFX=$(sfx "$ROLES")
}
sfx() { [ "$1" = review,fix ] || printf -- '-%s' "$1"; }
has_role() { case ",$ROLES," in *",$1,"*) return 0 ;; esac; return 1; }

# ---------------------------------------------------------------- repo ----
# D = repo dir, SD = watch state dir, W = where runner CLIs run (spawn sets it per session).
load_repo() {
    D=$(arg repo_dir); [ -n "$D" ] || D=.
    [ -d "$D" ] || die 1 "open-pr-watch.sh: no such directory: $D"
    D=$(cd "$D" && pwd)
    W=$D
    RM=$(arg remote)
    if [ -n "$RM" ]; then rt=$(opr repo-target --repo-dir "$D" --remote "$RM") || exit $?
    else rt=$(opr repo-target --repo-dir "$D") || exit $?; fi
    VENDOR=$(printf '%s\n' "$rt" | sed -n 's/^vendor=//p')
    OWNER=$(printf '%s\n' "$rt" | sed -n 's/^owner=//p')
    REPO=$(printf '%s\n' "$rt" | sed -n 's/^repo=//p')
    HOST=$(printf '%s\n' "$rt" | sed -n 's/^host=//p')
    check_ident '^[A-Za-z0-9_.-]+$' "$REPO"
    data=$(opr data-dir --repo-dir "$D") || exit $?
    SD="$data/$REPO/watch"
    STATE="$SD/state.json"
    mkdir -p "$SD/prompts"
    # Prompts quote PR comments: keep them out of the review-memory repo.
    grep -qx 'watch/' "$data/.gitignore" 2>/dev/null || printf 'watch/\n' >> "$data/.gitignore"
}
# WD = machine-wide state (snooze, menu bar pid), whichever data dirs the repos use.
watch_dir() {
    [ -n "${XDG_CONFIG_HOME:-}${HOME:-}" ] || die 1 "open-pr-watch.sh: neither XDG_CONFIG_HOME nor HOME is set"
    WD="${XDG_CONFIG_HOME:-$HOME/.config}/open-pr/watch"
    mkdir -p "$WD"
}
# A session is keyed "<pr>:<role>"; a review keeps the plain pr-N file names.
stem() { case "$1" in *:fix) printf 'pr-%s-fix' "${1%%:*}" ;; *) printf 'pr-%s' "${1%%:*}" ;; esac; }
status_file() { printf '%s/%s.status.json' "$SD" "$(stem "$1")"; }
log_file() { printf '%s/%s.log' "$SD" "$(stem "$1")"; }

# ------------------------------------------------------------ settings ----
SETTINGS=""
settings() {
    [ -n "$SETTINGS" ] || SETTINGS=$(opr settings --repo "$REPO" --repo-dir "$D") || exit $?
    printf '%s' "$SETTINGS"
}
# The machine's poll choice (menu bar, chat) wins over the repo setting; never below POLL_MIN.
POLL_MIN=15
poll_interval() {   # $1 = the repo setting
    v=$(grep -Ex '[0-9]+' "$WD/poll_seconds" 2>/dev/null | head -n 1 || true)
    if [ -n "$v" ]; then [ "$v" -ge "$POLL_MIN" ] || v=$POLL_MIN; else v=$1; fi
    printf '%s' "$v"
}
cmd_poll() {
    parse_args "$@"
    watch_dir
    if [ -n "$(arg off)" ]; then rm -f "$WD/poll_seconds"; printf '{"poll_seconds":null}\n'; return 0; fi
    n=$(req seconds); check_ident '^[0-9]+$' "$n"
    [ "$n" -ge "$POLL_MIN" ] || n=$POLL_MIN
    printf '%s\n' "$n" > "$WD/poll_seconds.tmp" && mv "$WD/poll_seconds.tmp" "$WD/poll_seconds"
    printf '{"poll_seconds":%s}\n' "$n"
}
setting_int() {
    v=$(settings | jq -r --arg k "$1" '.watch[$k] // empty | select(type == "number" and . >= 1) | floor')
    printf '%s' "${v:-$2}"
}

# --------------------------------------------------------------- state ----
# state.json:
#   cursor    newest processed comment created_at, UTC, second precision — of the wait serving
#             both roles; a wait serving one role keeps its own under cursors.<role>, with its seen
#   seen      comment ids at exactly that created_at (ties the cursor cannot order)
#   sessions  { "<pr>:<role>": {pr,role,runner,id,session_id,name,repo,url,open,cwd,pid,started_at,
#                        last_state,last_state_at,finished[,closed]} }   role = review | fix
#             last_state_at = when last_state last changed (the menu bar weighs it against the feed)
#             cwd = where it was opened; a resume runs there again
#             finished = `wait` delivered its result (a TERMINAL state): the session is the
#             user's now, reports nothing more and holds no slot until spawn resumes it
#             closed = the PR was merged or closed (see check_open)
#   hidden    PR numbers the menu bar leaves out (`hide`, or merged/closed); spawn takes N out
#   open_checked_at  last check_open
#   queue     [ {key,pr,role,runner,name,prompt_file,queued_at[,cwd][,url][,fresh]} ] waiting for a slot
#   fix_prs   { "<pr>": "enrolled" | "off" } — enrolled: the user asked for a review of their own PR;
#             off: `hide` took it out of the fix role (wins over authorship until a spawn for it)
#   findings  { "<pr>": {review_id,counts,url,comment_id,thread_id,user,repo,at} } the newest findings
#             event per PR, until a fix session opens for it (the menu bar offers "Fix now")
#   seen_reviews  "<pr>:<review id>" already delivered (the newest 200)
# etags/ (GitHub ETag cache, open-pr.sh triggers), fix_now/<pr> (a "Fix now" click, see fix-now).
# One wait per repo and role: wait-<role>.pid. Per role set a wait serves (file suffix SFX: none
# for both roles, else -review | -fix): heartbeat, watcher.json, stop.
LOCKED=""
lock() {   # $1 lock dir, default the repo's state lock
    lk="${1:-$SD/.lock}"; i=0; nopid=0
    while ! mkdir "$lk" 2>/dev/null; do
        holder=$(cat "$lk/pid" 2>/dev/null || true)
        if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then rm -rf "$lk"; continue; fi
        # a holder killed between its mkdir and its pid write leaves no pid: reclaimed after 5 s
        if [ -z "$holder" ]; then nopid=$((nopid + 1)); [ "$nopid" -lt 25 ] || { rm -rf "$lk"; nopid=0; continue; }; fi
        i=$((i + 1))
        [ "$i" -lt 600 ] || die 1 "open-pr-watch.sh: lock $lk held for over 2 minutes by pid ${holder:-?}"
        nap
    done
    printf '%s\n' "$$" > "$lk/pid"
    LOCKED="$lk"
}
unlock() { if [ -n "$LOCKED" ]; then rm -rf "$LOCKED"; LOCKED=""; fi; }

state_json() {
    if [ -s "$STATE" ]; then cat "$STATE"
    else printf '{"cursor":null,"seen":[],"sessions":{},"queue":[]}'; fi
}
# state_update <jq args…> <program>: via a temp file, so a failed jq never truncates the state.
state_update() {
    state_json > "$TMPD/state.in"
    jq "$@" "$TMPD/state.in" > "$STATE.tmp" || die 1 "open-pr-watch.sh: state update failed"
    mv "$STATE.tmp" "$STATE"
}
session_field() { state_json | jq -r --arg key "$1" --arg k "$2" '.sessions[$key][$k] // empty'; }

# ------------------------------------------------------------- runners ----
# Every platform CLI invocation in the plugin is below, run in W.
open_cmd() {   # $1 runner, $2 id → the command a reviewer runs to open the session
    [ -n "$2" ] || { printf ''; return 0; }
    case "$1" in
        claude)      printf 'claude attach %s' "$2" ;;
        codex)       printf 'codex resume %s' "$2" ;;
        gemini)      printf 'gemini -r %s' "$2" ;;
        cursor)      printf 'agent --resume %s' "$2" ;;
        antigravity) printf 'agy --conversation %s' "$2" ;;
    esac
}
# The only shape open_cmd prints; the toast and the menu bar write nothing else into a .command file.
OPEN_CMD_RE='[a-z-]+ (attach|resume|-r|--resume|--conversation) [A-Za-z0-9._-]+'
check_runner() {
    case " $RUNNERS " in *" $1 "*) ;; *) die 1 "open-pr-watch.sh: unknown runner: $1 (valid: $RUNNERS)" ;; esac
}
new_uuid() {
    if command -v uuidgen >/dev/null 2>&1; then uuidgen | tr 'A-Z' 'a-z'
    else od -An -N16 -tx1 /dev/urandom | tr -d ' \n' \
        | sed -E 's/^(.{8})(.{4})(.{4})(.{4})(.{12})$/\1-\2-\3-\4-\5/'; fi
}

# exec chain, so $! is the CLI's own pid.
bg() {   # $1 log, rest = command
    lg="$1"; shift
    ( cd "$W" || exit 1; exec nohup "$@" ) >> "$lg" 2>&1 < /dev/null &
    PID=$!
}
# The first JSON line whose "type" is $2 carries the id in field $3.
id_from_log() {
    [ -f "$1" ] || return 0
    jq -R -r --arg t "$2" --arg f "$3" 'fromjson? | select(type == "object" and .type == $t) | .[$f] // empty' "$1" 2>/dev/null | head -n 1
}
lazy_id() {   # $1 runner, $2 session key → the id a headless CLI reports in its output
    case "$1" in
        codex)       id_from_log "$(log_file "$2")" thread.started thread_id ;;
        antigravity) id_from_log "$(log_file "$2")" init conversation_id ;;
    esac
}
headless_launch() {   # sets RID, PID; $1 runner, $2 session key, $3 prompt
    lg=$(log_file "$2"); : > "$lg"; RID=""
    case "$1" in
        codex)       bg "$lg" codex exec --json -C "$W" "$3" ;;
        gemini)      RID=$(new_uuid); bg "$lg" gemini -p "$3" --session-id "$RID" -o json ;;
        cursor)
            RID=$( (cd "$W" && agent create-chat) | tr -d '[:space:]') \
                || die 1 "open-pr-watch.sh: agent create-chat failed"
            check_ident '^[A-Za-z0-9_-]+$' "$RID"
            cursor_run "$lg" "$RID" "$3" ;;
        antigravity) bg "$lg" agy -p "$3" --output-format stream-json ;;
    esac
}
cursor_run() { bg "$1" agent -p --resume "$2" --output-format json "$3"; }
headless_resume() {   # sets PID; $1 runner, $2 session key, $3 id, $4 prompt
    lg=$(log_file "$2")
    printf '\n' >> "$lg"
    case "$1" in
        codex)       bg "$lg" codex exec resume "$3" "$4" ;;
        gemini)      bg "$lg" gemini -r "$3" -p "$4" ;;
        cursor)      cursor_run "$lg" "$3" "$4" ;;
        antigravity) bg "$lg" agy -p "$4" --conversation "$3" ;;
    esac
}
pid_alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }

# `claude --bg` started inside Claude Code's Bash sandbox hangs at "starting…": bound each call
# so the hang surfaces as an error.
run_bounded() {   # $1 seconds, $2 output file, rest = command (cwd = W)
    secs="$1"; out="$2"; shift 2
    ( cd "$W" || exit 1; exec "$@" ) > "$out" 2>&1 < /dev/null &
    p=$!; i=0
    while kill -0 "$p" 2>/dev/null; do
        if [ "$i" -ge $((secs * 5)) ]; then kill "$p" 2>/dev/null || true; wait "$p" 2>/dev/null || true; return 124; fi
        nap; i=$((i + 1))
    done
    wait "$p"
}
claude_list() { (cd "$W" && claude agents --json "$@") 2>/dev/null || printf '[]'; }
claude_sid() {   # id → sessionId; a fresh session may take a moment to list
    i=0
    while [ "$i" -lt 10 ]; do
        s=$(claude_list --all | jq -r --arg id "$1" '.[]? | select(.id == $id) | .sessionId // empty' | head -n 1)
        [ -n "$s" ] && { printf '%s' "$s"; return 0; }
        i=$((i + 1)); nap
    done
}
# `backgrounded · <id> · <name>` → id.
claude_bg_id() {
    esc=$(printf '\033')
    sed "s/${esc}\[[0-9;]*[A-Za-z]//g" "$1" | LC_ALL=C sed -n 's/.*backgrounded · \([A-Za-z0-9_-]*\).*/\1/p' | tail -n 1
}
CLAUDE_HANG="claude --bg did not return within 30s. Started from inside Claude Code's Bash sandbox a background session hangs at starting… — run open-pr-watch.sh outside that sandbox."
# Trust is per exact directory (a trusted parent does not count); exit 8 names the fix.
claude_untrusted() {   # $1 output file
    grep -q 'Workspace not trusted' "$1" || return 0
    die 8 "workspace not trusted: run \`cd $W && claude\` once and accept the trust prompt"
}
claude_launch() {   # sets RID SID; $1 name, $2 prompt
    rc=0; run_bounded 30 "$TMPD/claude.out" claude --bg -n "$1" "$2" || rc=$?
    [ "$rc" != 124 ] || die 1 "$CLAUDE_HANG"
    claude_untrusted "$TMPD/claude.out"
    RID=$(claude_bg_id "$TMPD/claude.out")
    [ "$rc" = 0 ] && [ -n "$RID" ] || die 1 "claude --bg failed (exit $rc): $(cat "$TMPD/claude.out")"
    SID=$(claude_sid "$RID")
}
# Resume keeps id, name and context only as stop → gone from the active list →
# `--bg --resume <sessionId> <prompt>` with no other flag; a live session or any extra flag
# makes the CLI start a copy under a new id.
claude_resume() {   # sets RID SID WARNING; $1 id, $2 session id, $3 prompt
    RID="$1"; SID="$2"
    [ -n "$SID" ] || SID=$(claude_sid "$RID")
    [ -n "$SID" ] || die 1 "no sessionId known for claude session $RID — cannot resume it; forget the PR to start fresh"
    # The worker outlives its listing after `claude stop`; resuming before it exits starts a
    # copy. Wait for both, and on a copy anyway drop it and retry once.
    for attempt in 1 2; do
        pid=$(claude_list | jq -r --arg id "$RID" 'first(.[]? | select(.id == $id) | .pid // empty) // empty')
        (cd "$W" && claude stop "$RID") > /dev/null 2>&1 || true
        i=0
        while claude_list | jq -e --arg id "$RID" 'any(.[]?; .id == $id)' > /dev/null \
            || { [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; }; do
            i=$((i + 1))
            [ "$i" -lt 150 ] || die 1 "claude session $RID still running 30s after claude stop — not resuming (a resume now would start a copy)"
            nap
        done
        rc=0; run_bounded 30 "$TMPD/claude.out" claude --bg --resume "$SID" "$3" || rc=$?
        [ "$rc" != 124 ] || die 1 "$CLAUDE_HANG"
        claude_untrusted "$TMPD/claude.out"
        [ "$rc" = 0 ] || die 1 "claude --bg --resume failed (exit $rc): $(cat "$TMPD/claude.out")"
        grep -q 'started a copy' "$TMPD/claude.out" || return 0
        [ "$attempt" = 1 ] || break
        copy=$(claude_bg_id "$TMPD/claude.out")
        [ -z "$copy" ] || { (cd "$W" && claude stop "$copy" && claude rm "$copy") > /dev/null 2>&1 || true; }
        sleep 2
    done
    if grep -q 'started a copy' "$TMPD/claude.out"; then
        new=$(claude_bg_id "$TMPD/claude.out")
        WARNING="claude started a copy instead of resuming $RID; the review now runs in ${new:-an unlisted session}"
        [ -z "$new" ] || { RID="$new"; SID=$(claude_sid "$RID"); }
    fi
}

# -------------------------------------------------------------- status ----
# A finished session reads as the result in its status file, whatever its live state.
from_status_file() {   # $1 session key
    f=$(status_file "$1")
    s=$(jq -r '.state // empty' "$f" 2>/dev/null || true)
    case " $REPORTED " in *" $s "*) [ -n "$s" ] && printf '%s' "$s" && return 0 ;; esac
    printf 'failed'
}
status_note() {   # why from_status_file said failed without the file saying so
    f=$(status_file "$1")
    [ -s "$f" ] || { printf 'session ended without writing %s' "$f"; return 0; }
    s=$(jq -r '.state // empty' "$f" 2>/dev/null || true)
    case " $REPORTED " in *" $s "*) [ -n "$s" ] && return 0 ;; esac
    printf 'status file holds no known state'
}
CLAUDE_AGENTS=""
# `claude agents` state of the entry with id $1. A resumed or attached session that finished its
# turn stays "working" with status "idle" (waiting at its prompt), never "done": read as done.
claude_state() {
    printf '%s' "$CLAUDE_AGENTS" | jq -r --arg id "$1" '[.[]? | select(.id == $id)][0] // {}
        | if .state == "working" and .status == "idle" then "done" else .state // empty end' 2>/dev/null || true
}
status_one() {   # $1 session key
    key="$1"; pr=${key%%:*}; role=${key#*:}
    row=$(state_json | jq -r --arg key "$key" --argjson pr "$pr" '(.hidden // []) as $h | .sessions[$key]
        | [.runner, .id, .session_id, .pid, (.finished == true), .last_state, ($h | index([$pr]) != null)]
        | map(. // "" | tostring) | join("\u001f")')
    # not whitespace: IFS whitespace would merge the empty fields
    us=$(printf '\037')
    IFS="$us" read -r runner id sid pid fin last hid <<EOF
$row
EOF
    note=""; inuse=""
    if [ "$fin" = true ]; then
        [ -n "$id" ] || id=$(lazy_id "$runner" "$key")
        st="$last"
        # Its live state stays unread, but a result the user reached there (a draft they
        # published) is rewritten to the status file: that one is reported.
        fs=$(jq -r '.state // empty' "$(status_file "$key")" 2>/dev/null || true)
        case " $TERMINAL " in *" $fs "*) [ -z "$fs" ] || st="$fs" ;; esac
        # The user may still be talking in it: a new request waits rather than stops it.
        if [ "$runner" = claude ]; then
            [ -n "$CLAUDE_AGENTS" ] || CLAUDE_AGENTS=$(claude_list --all)
            cs=$(claude_state "$id")
            case "$cs" in working|blocked) inuse=$cs ;; esac
        elif pid_alive "$pid"; then inuse=working; fi
    elif [ "$runner" = claude ]; then
        [ -n "$CLAUDE_AGENTS" ] || CLAUDE_AGENTS=$(claude_list --all)
        entry=$(printf '%s' "$CLAUDE_AGENTS" | jq -c --arg id "$id" '[.[]? | select(.id == $id)][0] // empty')
        [ -n "$sid" ] || sid=$(printf '%s' "$entry" | jq -r '.sessionId // empty' 2>/dev/null || true)
        cs=$(claude_state "$id")
        case "$cs" in
            working) st=working ;;
            blocked) st=question ;;
            failed)  st=failed ;;
            stopped) st=stopped ;;
            done)    st=$(from_status_file "$key"); note=$(status_note "$key") ;;
            "")
                if [ -s "$(status_file "$key")" ]; then st=$(from_status_file "$key"); note=$(status_note "$key")
                else st=stopped; note="claude agents does not list session $id"; fi ;;
            *) st=working ;;
        esac
    else
        [ -n "$id" ] || id=$(lazy_id "$runner" "$key")
        if pid_alive "$pid"; then st=working
        else st=$(from_status_file "$key"); note=$(status_note "$key"); fi
    fi
    jq -n -c --argjson pr "$pr" --arg role "$role" --arg key "$key" --arg runner "$runner" --arg id "$id" --arg sid "$sid" \
        --arg state "$st" --arg open "$(open_cmd "$runner" "$id")" --arg note "$note" --arg fin "$fin" \
        --arg inuse "$inuse" --arg hid "$hid" \
        '{pr: $pr, role: $role, key: $key, runner: $runner, id: (if $id == "" then null else $id end),
          session_id: (if $sid == "" then null else $sid end), state: $state,
          open: (if $open == "" then null else $open end)}
         + (if $note == "" then {} else {note: $note} end)
         + (if $fin == "true" then {finished: true} else {} end)
         + (if $inuse == "" then {} else {in_use: $inuse} end)
         + (if $hid == "true" then {hidden: true} else {} end)'
}
status_all() {   # every tracked session, or those of PR $1 (role $2 when given)
    CLAUDE_AGENTS=""   # `wait` polls many times in one process: re-list each pass
    for k in $(state_json | jq -r --arg p "${1:-}" --arg r "${2:-}" '.sessions | keys[]
            | select(($p == "" or startswith($p + ":")) and ($r == "" or endswith(":" + $r)))' | sort -t: -k1,1n -k2); do
        check_ident '^[0-9]+:(review|fix)$' "$k"
        status_one "$k"
    done
}
# Ids a headless CLI only reports once it runs are folded back into the map.
remember_ids() {   # $1 = status JSONL file
    [ -s "$1" ] || return 0
    state_update --slurpfile st "$1" \
        'reduce $st[] as $s (.; if .sessions[$s.key] then
            .sessions[$s.key] |= (.id = (.id // $s.id) | .session_id = (.session_id // $s.session_id)
                                  | .open = (.open // $s.open))
         else . end)'
}
active_count() {   # $1 status JSONL, $2 session key to leave out
    jq -s --arg skip "${2:-}" '[.[] | select(.key != $skip and (.state == "working" or .state == "question"))] | length' "$1"
}

cmd_status() {
    parse_args "$@"
    N=$(arg pr); [ -z "$N" ] || check_ident '^[0-9]+$' "$N"
    R=$(arg role); [ -z "$R" ] || R=$(role_arg)
    load_repo; lock
    status_all "$N" "$R" > "$TMPD/status"
    remember_ids "$TMPD/status"
    state_json > "$TMPD/state.in"
    jq -c --slurpfile st "$TMPD/state.in" '{pr, role, runner, id, state, open}
        + ($st[0].sessions[.key].findings | if . then {findings: .} else {} end) + (if .note then {note} else {} end) + (if .finished then {finished} else {} end)
        + (if .hidden then {hidden} else {} end)' "$TMPD/status"
}

# --------------------------------------------------------------- spawn ----
# A finished session left `blocked` (a prompt nobody answers) holds a request back for
# IN_USE_GRACE seconds, then yields (stop + resume keeps the conversation). `working` is never cut.
IN_USE_GRACE=600
# A claude session this watcher opened, finished and idle this long, is stopped: an idle
# background session holds ~140 MB. Stop keeps the conversation (attach and resume still work).
# Sessions the watcher did not open are never touched — only those in state.json. A closed PR's
# session is stopped without the idle wait.
IDLE_PARK=600
park_idle() {   # $1 status JSONL; only sessions of the roles this wait serves
    state_json | jq -r --slurpfile s "$1" --argjson idle "$IDLE_PARK" --arg roles "$ROLES" '
        .sessions | to_entries[] | .key as $key | .value
        | select(.role as $r | $roles | split(",") | index([$r]))
        | select(.runner == "claude" and .finished == true and .parked != true and .id != null
                 and (.closed == true or ((.finished_at // null) != null
                                           and (now - (.finished_at | fromdateiso8601)) >= $idle)))
        | select([$s[] | select(.key == $key) | .in_use // empty] | length == 0)
        | "\($key) \(.id)"' | while read -r key id; do
        check_ident '^[0-9a-f]+$' "$id"
        (cd "$D" && claude stop "$id") > /dev/null 2>&1 || true
        state_update --arg key "$key" '.sessions[$key].parked = true'
    done
}
# jq: session keys a queued request must still wait for — $s = status rows, $q = queue, $now epoch.
JQ_BUSY='def busy($s; $q; $now):
    [$s[] | . as $r
     | select(.state == "working" or .in_use == "working"
              or (.in_use == "blocked"
                  and (([$q[]? | select(.key == $r.key) | .queued_at // empty][0] // null) as $at
                       | $at == null or ($now - ($at | fromdateiso8601)) < '"$IN_USE_GRACE"')))
     | .key];'
enqueue() {   # $1 reason
    state_update --arg key "$KEY" --argjson pr "$N" --arg role "$ROLE" --arg runner "$RUNNER" --arg name "$NAME" \
        --arg f "$PF" --arg at "$(now_iso)" --arg cwd "$CW" --arg url "$URL" --arg fresh "$FRESH" \
        '(([.queue[] | select(.key == $key) | .queued_at][0]) // $at) as $since
         | .queue = ([.queue[] | select(.key != $key)]
                     + [{key: $key, pr: $pr, role: $role, runner: $runner, name: $name, prompt_file: $f, queued_at: $since}
                        + (if $cwd == "" then {} else {cwd: $cwd} end)
                        + (if $url == "" then {} else {url: $url} end)
                        + (if $fresh == "" then {} else {fresh: true} end)])'
    jq -n -c --argjson pr "$N" --arg role "$ROLE" --arg why "$1" '{pr: $pr, role: $role, queued: true, reason: $why}'
}
cmd_spawn() {
    parse_args "$@"
    RUNNER=$(req runner); check_runner "$RUNNER"
    N=$(pr_arg); ROLE=$(role_arg); KEY="$N:$ROLE"; NAME=$(req name); PF=$(req prompt_file); URL=$(arg url)
    [ -r "$PF" ] || die 1 "open-pr-watch.sh: prompt file not readable: $PF"
    PF=$(cd "$(dirname "$PF")" && printf '%s/%s' "$(pwd)" "$(basename "$PF")")
    CW=$(arg cwd); FRESH=$(arg fresh)
    if [ -n "$CW" ]; then
        [ -d "$CW" ] || die 1 "open-pr-watch.sh: no such directory: $CW"
        CW=$(cd "$CW" && pwd)
    fi
    load_repo
    case "$RUNNER" in claude) need claude ;; codex) need codex ;; gemini) need gemini ;; cursor) need agent ;; antigravity) need agy ;; esac
    lock
    state_update --argjson pr "$N" --arg role "$ROLE" '.hidden = [(.hidden // [])[] | select(. != $pr)]
        | if $role == "fix" then del(.fix_prs[$pr | tostring] | select(. == "off")) else . end'
    max=$(setting_int max_concurrent 5)
    status_all > "$TMPD/status"
    remember_ids "$TMPD/status"
    # --fresh waits for a running review: both would write the same status file.
    if [ -n "$FRESH" ] && [ "$(jq -r --arg key "$KEY" 'select(.key == $key) | .state' "$TMPD/status")" = working ]; then
        enqueue "session still running"; return 0
    fi
    have=""; [ -n "$FRESH" ] || have=$(session_field "$KEY" runner)
    if [ -n "$have" ] && [ "$have" != "$RUNNER" ]; then
        die 1 "open-pr-watch.sh: PR $N already has a $have $ROLE session; forget it first to open one under $RUNNER"
    fi
    if [ -n "$have" ]; then
        cur=$(jq -r --arg key "$KEY" 'select(.key == $key) | .state' "$TMPD/status")
        [ "$cur" != working ] || { enqueue "session still running"; return 0; }
        busy=$(state_json | jq -r --slurpfile s "$TMPD/status" --arg key "$KEY" "$JQ_BUSY"' busy($s; .queue; now) | index([$key]) != null')
        [ "$busy" != true ] || { enqueue "session in use"; return 0; }
    fi
    [ "$(active_count "$TMPD/status" "$KEY")" -lt "$max" ] || { enqueue "all $max slots busy"; return 0; }

    PROMPT=$(cat "$PF")
    rm -f "$(status_file "$KEY")"
    RID=""; SID=""; PID=""; WARNING=""; resumed=false
    if [ -n "$have" ]; then
        resumed=true
        RID=$(session_field "$KEY" id); SID=$(session_field "$KEY" session_id)
        W=$(session_field "$KEY" cwd); [ -n "$W" ] || W=${CW:-$D}
        if [ "$RUNNER" = claude ]; then
            claude_resume "$RID" "$SID" "$PROMPT"
        else
            [ -n "$RID" ] || RID=$(lazy_id "$RUNNER" "$KEY")
            [ -n "$RID" ] || die 1 "open-pr-watch.sh: no $RUNNER session id recorded for PR $N ($ROLE) — forget it to start fresh"
            headless_resume "$RUNNER" "$KEY" "$RID" "$PROMPT"
        fi
    else
        W=${CW:-$D}
        if [ "$RUNNER" = claude ]; then claude_launch "$NAME" "$PROMPT"
        else headless_launch "$RUNNER" "$KEY" "$PROMPT"; fi
    fi
    state_update --arg key "$KEY" --argjson pr "$N" --arg role "$ROLE" --arg runner "$RUNNER" --arg id "$RID" --arg sid "$SID" \
        --arg name "$NAME" --arg pid "$PID" --arg at "$(now_iso)" --arg repo "$OWNER/$REPO" \
        --arg url "$URL" --arg open "$(open_cmd "$RUNNER" "$RID")" --arg cwd "$W" \
        'def nul: if . == "" then null else . end;
         .sessions[$key] = {pr: $pr, role: $role, runner: $runner, id: ($id | nul), session_id: ($sid | nul),
                            name: $name, repo: $repo, url: (($url | nul) // .sessions[$key].url), open: ($open | nul),
                            cwd: $cwd, pid: ($pid | nul | if . then tonumber else . end), started_at: $at,
                            last_state: "working", last_state_at: $at, finished: false}
                           + (if $role == "fix" then {findings: (.findings[$pr | tostring] // .sessions[$key].findings)} else {} end)
         | del(.findings[if $role == "fix" then ($pr | tostring) else "" end])
         | .queue = [.queue[] | select(.key != $key)]'
    jq -n -c --argjson pr "$N" --arg role "$ROLE" --arg id "$RID" --arg open "$(open_cmd "$RUNNER" "$RID")" \
        --argjson resumed "$resumed" --arg warn "$WARNING" \
        '{pr: $pr, role: $role, id: (if $id == "" then null else $id end), open: (if $open == "" then null else $open end)}
         + (if $resumed then {resumed: true} else {} end)
         + (if $warn == "" then {} else {warning: $warn} end)'
}

# ---------------------------------------------------------- next/forget ----
cmd_next() {
    parse_args "$@"
    roles_arg
    load_repo; lock
    max=$(setting_int max_concurrent 5)
    status_all > "$TMPD/status"
    remember_ids "$TMPD/status"
    [ "$(active_count "$TMPD/status")" -lt "$max" ] || return 0
    pick=$(state_json | jq -c --slurpfile s "$TMPD/status" --arg roles "$ROLES" "$JQ_BUSY"'
        busy($s; .queue; now) as $busy
        | [.queue[] | select((.key as $k | $busy | index([$k]) | not) and (.role as $r | $roles | split(",") | index([$r])))][0]
        // empty')
    [ -n "$pick" ] || return 0
    state_update --argjson pick "$pick" '.queue = [.queue[] | select(.key != $pick.key)]'
    printf '%s\n' "$pick" | jq -c 'del(.key)'
}
cmd_forget() {
    parse_args "$@"
    N=$(pr_arg); ROLE=$(role_arg)
    load_repo; lock
    state_update --arg key "$N:$ROLE" 'del(.sessions[$key])'
    rm -f "$(status_file "$N:$ROLE")"
    jq -n -c --argjson pr "$N" --arg role "$ROLE" '{pr: $pr, role: $role, forgotten: true}'
}
# Both roles: off the menu bar, out of the fix role, its pending findings dropped.
cmd_hide() {
    parse_args "$@"
    N=$(pr_arg)
    load_repo; lock
    state_update --argjson pr "$N" '.hidden = ((.hidden // []) + [$pr] | unique)
        | .fix_prs[$pr | tostring] = "off" | del(.findings[$pr | tostring])'
    rm -f "$SD/fix_now/$N"
    jq -n -c --argjson pr "$N" '{pr: $pr, hidden: true}'
}
# A "Fix now" click (toast, menu bar): the running wait delivers it as a fix_now event.
cmd_fix_now() {
    parse_args "$@"
    N=$(pr_arg)
    load_repo
    mkdir -p "$SD/fix_now"
    : > "$SD/fix_now/$N"
    jq -n -c --argjson pr "$N" '{pr: $pr, fix_now: true}'
}
cmd_paths() {
    parse_args "$@"
    N=$(arg pr); [ -z "$N" ] || check_ident '^[0-9]+$' "$N"
    ROLE=$(role_arg)
    load_repo
    printf 'dir=%s\nprompts=%s/prompts\n' "$SD" "$SD"
    [ -z "$N" ] || printf 'status_file=%s\nlog=%s\n' "$(status_file "$N:$ROLE")" "$(log_file "$N:$ROLE")"
}

# ---------------------------------------------------------------- wait ----
# open-pr.sh triggers validates whatever this returns.
TOKEN=""
# The login this machine posts as, kept an hour: `wait` restarts after every event.
account() {
    f="$SD/account"
    if [ ! -s "$f" ] || [ -n "$(find "$f" -mmin +60 2>/dev/null)" ]; then
        opr account --vendor "$VENDOR" --owner "$OWNER" --repo "$REPO" ${HOST:+--host "$HOST"} > "$f.$$" || exit $?
        mv "$f.$$" "$f"
    fi
    v=$(head -n 1 "$f")
    printf '%s' "$v" | grep -Eqx '[A-Za-z0-9][A-Za-z0-9_.-]*' && [ "$v" != UNKNOWN ] && printf '%s' "$v" || true
}
trigger_token() {
    t=$(settings | jq -r '.watch.trigger // "/open-pr"')
    [ "$t" = "@me" ] || { printf '%s' "$t"; return 0; }
    who=$(account)
    case "$who" in
        "") die 1 "open-pr-watch.sh: watch.trigger is @me, but the account this machine is logged in as cannot be read (Bitbucket under a workspace token has no identity) — use a user credential, or set the trigger to @<login> or a /word" ;;
    esac
    printf '@%s' "$who"
}
# A merged or closed PR leaves the menu bar: every OPEN_CHECK s, each PR tracked here (a session
# not yet closed, or a feed line not yet hidden) that the vendor no longer lists open is hidden and
# its session marked closed. A failed check waits for the next slot.
OPEN_CHECK=600
check_open() {
    last=$(state_json | jq -r '.open_checked_at // empty')
    if [ -n "$last" ] && jq -e -n --arg t "$last" --argjson w "$OPEN_CHECK" \
        '(try ($t | fromdateiso8601) catch 0) > now - $w' > /dev/null; then return 0; fi
    state_json > "$TMPD/open.st"
    cat "$SD/feed.jsonl" > "$TMPD/open.feed" 2>/dev/null || : > "$TMPD/open.feed"
    jq -n -c --slurpfile st "$TMPD/open.st" --rawfile f "$TMPD/open.feed" '$st[0] as $s | ($s.hidden // []) as $h
        | [($s.sessions // {} | to_entries[] | select(.value.closed != true) | .key | split(":")[0] | tonumber),
           ($f | split("\n")[] | fromjson? | .pr? | numbers | select(. as $p | $h | index([$p]) | not))]
        | unique' > "$TMPD/open.cand"
    [ "$(cat "$TMPD/open.cand")" != "[]" ] || return 0
    rc=0
    opr open-prs --vendor "$VENDOR" --owner "$OWNER" --repo "$REPO" ${HOST:+--host "$HOST"} \
        > "$TMPD/open.prs" 2> "$TMPD/open.err" || rc=$?
    lock
    if [ "$rc" = 0 ]; then
        grep -Ex '[0-9]+' "$TMPD/open.prs" | jq -s -c . > "$TMPD/open.now"
        state_update --slurpfile c "$TMPD/open.cand" --slurpfile o "$TMPD/open.now" --arg at "$(now_iso)" '
            ($c[0] - $o[0]) as $gone
            | .open_checked_at = $at
            | .hidden = ((.hidden // []) + $gone | unique)
            | .queue = [.queue[]? | select(.pr as $p | $gone | index($p) | not)]
            | ($gone | map(tostring)) as $g
            | .findings = ((.findings // {}) | with_entries(select(.key as $k | $g | index([$k]) | not)))
            | .fix_prs = ((.fix_prs // {}) | with_entries(select(.key as $k | $g | index([$k]) | not)))
            | .sessions |= with_entries(if (.key | split(":")[0]) as $k | $g | index([$k]) then .value.closed = true else . end)'
    else
        state_update --arg at "$(now_iso)" '.open_checked_at = $at'
        if [ "$rc" = 9 ]; then LIMITED=1
        else err "open-pr-watch.sh: open-prs failed (exit $rc), next check in ${OPEN_CHECK}s: $(tail -n 1 "$TMPD/open.err")"; fi
    fi
    unlock
}
# Delivery: print the batch, then rename the state that marks it processed, then exit 0.
# Killed before the rename, the next `wait` reprints it; the caller acts only on exit 0, so a
# comment is neither lost nor handled twice.
# ROLES = the roles this wait serves; FIX_LISTED = the PRs `--fix-prs` names (else the user's own).
poll_once() {   # sets GOT (events committed), LIMITED (vendor rate-limited), ACTIVE (sessions active)
    GOT=""; LIMITED=""; : "${FAILS:=0}" "${ACTIVE:=0}"
    touch "$SD/heartbeat$SFX"   # read by the menu bar
    lock
    cursor=$(state_json | jq -r --argjson p "$CP" "$JQ_UTC"' getpath($p + ["cursor"]) // empty | utc')
    if [ -z "$cursor" ]; then
        # First run of this role set: no replay of history.
        state_update --argjson p "$CP" --arg c "$(now_iso)" 'setpath($p + ["cursor"]; $c) | setpath($p + ["seen"]; [])'
        unlock; return 0
    fi
    # A cursor stored with an offset is rewritten in UTC: comparisons below are string compares.
    [ "$cursor" = "$(state_json | jq -r --argjson p "$CP" 'getpath($p + ["cursor"])')" ] \
        || state_update --argjson p "$CP" --arg c "$cursor" 'setpath($p + ["cursor"]; $c)'
    unlock
    check_open
    # --since is strict and the cursor has second precision: ask from 1s earlier; `seen` drops repeats.
    since=$(jq -n -r --arg c "$cursor" '$c | fromdateiso8601 - 1 | todateiso8601')
    [ -n "$TOKEN" ] || TOKEN=$(trigger_token)
    set -- --since "$since" --mark-file "$TMPD/mark" --token "$TOKEN" --cache-dir "$SD/etags"
    : > "$TMPD/findings"
    if has_role fix; then
        prs=$(state_json | jq -r --arg l "$FIX_LISTED" '[($l | split(",")[] | select(. != "")),
            ((.fix_prs // {}) | to_entries[] | select(.value == "enrolled") | .key)] | unique | join(",")')
        who=""; [ -n "$FIX_LISTED" ] || who=$(account)
        set -- "$@" --findings-file "$TMPD/findings" ${who:+--fix-author "$who"} ${prs:+--fix-prs "$prs"}
    fi
    rc=0
    opr triggers --vendor "$VENDOR" --owner "$OWNER" --repo "$REPO" ${HOST:+--host "$HOST"} "$@" \
        > "$TMPD/triggers" 2> "$TMPD/triggers.err" || rc=$?
    if [ "$rc" = 9 ] && [ -z "$(arg once)" ]; then LIMITED=1; return 0; fi
    cat "$TMPD/triggers.err" >&2
    if [ "$rc" != 0 ]; then
        [ -z "$(arg once)" ] || exit "$rc"
        # A persistent failure (no network, sandbox, expired login) must reach the user, not look idle.
        FAILS=$((FAILS + 1))
        [ "$FAILS" -lt 3 ] || die 1 "open-pr-watch.sh: $OWNER/$REPO: triggers failed $FAILS polls in a row (exit $rc): $(tail -n 1 "$TMPD/triggers.err")"
        err "open-pr-watch.sh: triggers failed (exit $rc); retrying next poll"
        return 0
    fi
    FAILS=0
    me=""; ! has_role fix || me=$(account)
    lock
    state_json > "$TMPD/state.in"
    jq -c -s --slurpfile st "$TMPD/state.in" --argjson p "$CP" "$JQ_UTC"'
        ($st[0] | getpath($p + ["cursor"])) as $cur | ($st[0] | getpath($p + ["seen"]) // []) as $seen
        | map(select(type == "object") | . + {_k: (.created_at | utc)})
        | map(select(._k > $cur or (._k == $cur and ((.comment_id | tostring) as $c | $seen | index([$c]) | not))))
        | reduce .[] as $t ([]; if any(.[]; .comment_id == $t.comment_id) then . else . + [$t] end)
        | sort_by(._k)[]' "$TMPD/triggers" > "$TMPD/new"
    # The user asking for a review of their own PR puts it in the fix role.
    jq -r --arg me "$me" 'select($me != "" and (.user | ascii_downcase) == ($me | ascii_downcase)
        and ((.pr_author // "") | ascii_downcase) == ($me | ascii_downcase)) | .pr' "$TMPD/new" | sort -u > "$TMPD/enroll"
    # A fix-only watcher still moves the cursor past review requests: it just does not deliver them.
    if has_role review; then cp "$TMPD/new" "$TMPD/new.ev"; else : > "$TMPD/new.ev"; fi
    jq -c -s --slurpfile st "$TMPD/state.in" '($st[0].seen_reviews // []) as $seen | ($st[0].fix_prs // {}) as $fp
        | .[] | "\(.pr):\(.review_id)" as $k
        | select(($fp[.pr | tostring] // "") != "off" and ($seen | index([$k]) | not))
        | {event: "findings", pr, review_id, counts, url, comment_id, thread_id, user}' "$TMPD/findings" > "$TMPD/fnd"
    : > "$TMPD/fixnow"
    ! has_role fix || ls "$SD/fix_now" 2>/dev/null | grep -Ex '[0-9]+' > "$TMPD/fixnow" || :
    jq -c -R --slurpfile st "$TMPD/state.in" 'tonumber as $pr | ($st[0].findings // {})[$pr | tostring] as $f
        | {event: "fix_now", pr: $pr} + (if $f then {url: $f.url, review_id: $f.review_id, counts: $f.counts,
                                                       comment_id: $f.comment_id, thread_id: $f.thread_id, user: $f.user}
                                          else {} end)' "$TMPD/fixnow" > "$TMPD/fixev"
    # Session events, their reduce, `ready` and parking concern this wait's roles only: another
    # role's wait on this repo delivers its own. The slot count spans both roles.
    status_all > "$TMPD/status"
    jq -c --arg roles "$ROLES" 'select(.role as $r | $roles | split(",") | index([$r]))' "$TMPD/status" > "$TMPD/own"
    ACTIVE=$(active_count "$TMPD/own")
    # A click while that PR's fix session runs (a second click, or the toast's after the menu
    # bar's) opens nothing: the click is used up here.
    jq -c --slurpfile own "$TMPD/own" '.pr as $p
        | select([$own[] | select(.role == "fix" and .pr == $p and .finished != true
                                  and (.state == "working" or .state == "question"))] | length == 0)' \
        "$TMPD/fixev" > "$TMPD/fixev.ok"
    jq -r '.pr' "$TMPD/fixev" | while IFS= read -r n; do
        jq -e --argjson p "$n" 'select(.pr == $p)' "$TMPD/fixev.ok" > /dev/null || rm -f "$SD/fix_now/$n"
    done
    mv "$TMPD/fixev.ok" "$TMPD/fixev"
    jq -c -s --slurpfile st "$TMPD/state.in" '
        .[] | select(.state != ($st[0].sessions[.key].last_state // null))
        | {event: "session", pr, role, state, open} + (if .note then {note} else {} end)' "$TMPD/own" > "$TMPD/sess"
    # `ready`: nothing else wakes the watcher to run `next`.
    max=$(setting_int max_concurrent 5)
    jq -c -s --slurpfile st "$TMPD/state.in" --argjson max "$max" --arg roles "$ROLES" "$JQ_BUSY"'
        . as $s
        | ([$s[] | select(.finished != true and (.state == "working" or .state == "question"))] | length) as $active
        | busy($s; $st[0].queue; now) as $busy
        | if $active < $max then
              ([$st[0].queue[]? | select((.key as $k | $busy | index([$k]) | not)
                                          and (.role as $r | $roles | split(",") | index([$r])))][0] // empty)
              | {event: "ready", pr, role}
          else empty end' "$TMPD/status" > "$TMPD/ready"
    # The cursor follows every comment fetched, trigger or not: else a quiet repo re-fetches
    # everything since start, every poll.
    mark=$(cat "$TMPD/mark" 2>/dev/null || true)
    jq -R -s 'split("\n") | map(select(. != ""))' "$TMPD/enroll" > "$TMPD/enroll.json"
    if [ ! -s "$TMPD/new.ev" ] && [ ! -s "$TMPD/sess" ] && [ ! -s "$TMPD/ready" ] && [ ! -s "$TMPD/fnd" ] \
        && [ ! -s "$TMPD/fixev" ]; then
        remember_ids "$TMPD/status"
        jq -r '._k' "$TMPD/new" | sort | tail -n 1 > "$TMPD/newest"
        state_update --arg m "$mark" --arg n "$(cat "$TMPD/newest")" --slurpfile en "$TMPD/enroll.json" --argjson p "$CP" \
            '([$m, $n] | map(select(. != "")) | max) as $c
             | (if $c != null and $c > getpath($p + ["cursor"]) then setpath($p + ["cursor"]; $c) | setpath($p + ["seen"]; []) else . end)
             | reduce $en[0][] as $p (.; .fix_prs[$p] = "enrolled")'
        park_idle "$TMPD/status"
        unlock; return 0
    fi
    jq -c --slurpfile new "$TMPD/new" --slurpfile status "$TMPD/own" --slurpfile fnd "$TMPD/fnd" \
        --slurpfile en "$TMPD/enroll.json" --arg m "$mark" --arg terminal "$TERMINAL" --arg at "$(now_iso)" \
        --arg repo "$OWNER/$REPO" --argjson p "$CP" '
        getpath($p + ["cursor"]) as $cur
        | ([$cur, $m] + [$new[]._k] | map(select(. != "")) | max) as $c
        | setpath($p + ["seen"]; if $c == $cur then (getpath($p + ["seen"]) // []) else [] end
                   + [$new[] | select(._k == $c) | .comment_id | tostring] | unique)
        | setpath($p + ["cursor"]; $c)
        | reduce $en[0][] as $p (.; .fix_prs[$p] = "enrolled")
        | .seen_reviews = (((.seen_reviews // []) + [$fnd[] | "\(.pr):\(.review_id)"]) | .[-200:])
        | reduce $fnd[] as $f (.; .findings[$f.pr | tostring] = ($f | del(.event, .pr) + {repo: $repo, at: $at}))
        | ($terminal | split(" ")) as $done
        | reduce $status[] as $s (.; if .sessions[$s.key] then
              .sessions[$s.key] |= ((if .last_state != $s.state then .last_state_at = $at else . end)
                                    | .last_state = $s.state | .id = (.id // $s.id)
                                    | .session_id = (.session_id // $s.session_id)
                                    | .open = (.open // $s.open)
                                    | if any($done[]; . == $s.state) then .finished = true | .finished_at = (.finished_at // $at) else . end)
          else . end)' "$TMPD/state.in" > "$STATE.tmp" || die 1 "open-pr-watch.sh: state update failed"
    { jq -c '{event: "trigger"} + del(._k, .pr_author)' "$TMPD/new.ev"; cat "$TMPD/fnd" "$TMPD/fixev" "$TMPD/sess" "$TMPD/ready"; } \
        | jq -c --arg r "$OWNER/$REPO" '{event, repo: $r} + del(.event)' > "$TMPD/events"
    cat "$TMPD/events"
    mv "$STATE.tmp" "$STATE"
    while IFS= read -r n; do rm -f "$SD/fix_now/$n"; done < "$TMPD/fixnow"
    park_idle "$TMPD/status"
    unlock
    GOT=1
}
# watcher$SFX.json: which terminal tab runs this watcher, for the menu bar to group its repos and
# focus that tab. Env values are data: a value outside its pattern is recorded as "".
NL='
'
TERM_RE='[A-Za-z0-9._-]{1,64}'
TERM_SESSION_RE='[A-Za-z0-9:._-]{1,128}'
TTY_RE='[A-Za-z0-9/]{1,32}'
# The Claude Code session running this watcher: once the user quits `claude` it keeps running in the
# background, and `claude attach <its first 8 chars>` brings it back into a tab.
SESSION_ID_RE='[0-9a-f-]{8,64}'
fit() {   # $1 value, $2 ERE it must match whole
    printf '%s' "$1" | LC_ALL=C grep -Eqx "$2" 2>/dev/null || return 0
    case "$1" in *"$NL"*) return 0 ;; esac   # grep matches per line
    printf '%s' "$1"
}
# The watcher's own shell runs without a terminal (an agent's Bash tool): the tab is the
# nearest ancestor that has one.
ancestor_tty() {
    p=$$; i=0
    while [ "$i" -lt 15 ] && [ "${p:-0}" -gt 1 ]; do
        row=$(ps -o ppid=,tty= -p "$p" 2>/dev/null || true)
        read -r pp tt <<EOF
$row
EOF
        [ -n "${tt:-}" ] || return 0
        case "$tt" in '?'|'??'|-) ;; *) fit "$tt" "$TTY_RE"; return 0 ;; esac
        p=$pp; i=$((i + 1))
    done
}
# A watcher session that went to the background has no terminal env: its next wait keeps the
# terminal app recorded before (not the tab id or tty — that tab is gone).
write_watcher() {
    cwd=$(pwd)
    # no control characters (a newline would pass grep line by line)
    [ "$cwd" = "$(printf '%s' "$cwd" | LC_ALL=C tr -d '\000-\037\177')" ] && [ ${#cwd} -le 1024 ] || cwd=""
    rd=$D; [ "$rd" = "$(printf '%s' "$rd" | LC_ALL=C tr -d '\000-\037\177')" ] && [ ${#rd} -le 1024 ] || rd=""
    jq -n -c --argjson pid "$$" --arg cwd "$cwd" --arg rd "$rd" --arg rm "$(fit "$RM" '[A-Za-z0-9._-]{1,128}')" \
        --arg term "$(t=$(fit "${TERM_PROGRAM:-}" "$TERM_RE"); [ -n "$t" ] || t=$(watcher_field term "$TERM_RE"); printf '%s' "$t")" \
        --arg ts "$(fit "${ITERM_SESSION_ID:-${TERM_SESSION_ID:-}}" "$TERM_SESSION_RE")" \
        --arg tty "$(ancestor_tty)" --arg sid "$(fit "${CLAUDE_CODE_SESSION_ID:-}" "$SESSION_ID_RE")" \
        '{pid: $pid, cwd: $cwd, term: $term, term_session: $ts, tty: $tty, session_id: $sid, repo_dir: $rd, remote: $rm}' > "$WF.tmp"
    mv "$WF.tmp" "$WF"
}
watcher_field() {   # $1 key of the watcher record WF, $2 ERE → its value, or "" when it does not match
    fit "$(jq -r --arg k "$1" '.[$k] // "" | strings' "$WF" 2>/dev/null || true)" "$2"
}
stop_requested() {
    [ -e "$SD/stop$SFX" ] || return 0
    rm -f "$SD/stop$SFX"
    die 11 "open-pr-watch.sh: stopped from the menu bar"
}
# A repo with nothing active and no event for IDLE_AFTER s polls every IDLE_POLL s — unless the
# setting is slower, or this machine chose an interval (`poll`), which always holds.
IDLE_AFTER=600
IDLE_POLL=180
next_interval() {   # $1 = the repo setting
    v=$(poll_interval "$1")
    if [ ! -s "$WD/poll_seconds" ] && [ "${ACTIVE:-0}" = 0 ] && [ $(($(date +%s) - STARTED)) -ge "$IDLE_AFTER" ] \
        && [ "$v" -lt "$IDLE_POLL" ]; then v=$IDLE_POLL; fi
    printf '%s' "$v"
}
fix_now_pending() { has_role fix && [ -n "$(ls "$SD/fix_now" 2>/dev/null | grep -Ex '[0-9]+' || true)" ]; }
cmd_wait() {
    parse_args "$@"
    roles_arg; CP='[]'; [ "$ROLES" = review,fix ] || CP="[\"cursors\",\"$ROLES\"]"
    FIX_LISTED=$(arg fix_prs); [ -z "$FIX_LISTED" ] || check_ident '^[0-9]+(,[0-9]+)*$' "$FIX_LISTED"
    load_repo
    WF="$SD/watcher$SFX.json"
    # Written by the menu bar's "Stop"; one left from an earlier run must not stop this one.
    rm -f "$SD/stop$SFX"
    # Two waits serving one role on one repo would split its events between them; a review and a
    # fix wait run side by side. Checked and claimed under the state lock.
    lock
    for r in review fix; do
        has_role "$r" || continue
        old=$(cat "$SD/wait-$r.pid" 2>/dev/null || true)
        if [ -n "$old" ] && [ "$old" != "$$" ] && kill -0 "$old" 2>/dev/null \
            && ps -o command= -p "$old" 2>/dev/null | grep -q 'open-pr-watch.sh wait'; then
            die 10 "open-pr-watch.sh: $OWNER/$REPO is already watched for $r on this machine (wait pid $old) — stop that watcher first"
        fi
    done
    for r in review fix; do ! has_role "$r" || printf '%s\n' "$$" > "$SD/wait-$r.pid"; done
    # The records of a role set sharing a role with this one belong to a wait no longer running.
    for x in review,fix review fix; do
        [ "$x" != "$ROLES" ] && { [ "$x" = review,fix ] || has_role "$x"; } || continue
        rm -f "$SD/watcher$(sfx "$x").json" "$SD/heartbeat$(sfx "$x")" "$SD/stop$(sfx "$x")"
    done
    unlock
    write_watcher
    watch_dir
    STARTED=$(date +%s)
    base=$(setting_int poll_interval_seconds 60)
    interval=$(next_interval "$base"); delay=$interval
    while :; do
        stop_requested
        # Not an `if` condition: set -e must still apply inside.
        poll_once
        [ -z "$GOT" ] || return 0
        [ -z "$(arg once)" ] || return 0
        if [ -n "$LIMITED" ]; then
            delay=$((delay * 2))
            [ "$delay" -le "$BACKOFF_CAP" ] || delay=$BACKOFF_CAP
            [ "$delay" -ge "$interval" ] || delay=$interval
            err "rate limited — next poll in ${delay}s"
        else
            interval=$(next_interval "$base"); delay=$interval
        fi
        # Slept in slices so a faster poll chosen meanwhile, or a "Fix now" click, applies within seconds.
        waited=0; slice=5; [ "$delay" -ge "$slice" ] || slice=$delay
        while [ "$waited" -lt "$delay" ]; do
            sleep "$slice"; waited=$((waited + slice))
            stop_requested
            ! fix_now_pending || break
            [ -n "$LIMITED" ] || [ "$waited" -lt "$(next_interval "$base")" ] || break
        done
    done
}

# -------------------------------------------------------------- notify ----
cmd_notify() {
    parse_args "$@"
    E=$(req event); F=$(req text_file)
    case " $EVENTS " in *" $E "*) ;; *) die 1 "open-pr-watch.sh: unknown event: $E (valid: $EVENTS)" ;; esac
    [ -r "$F" ] || die 1 "open-pr-watch.sh: text file not readable: $F"
    P=$(arg pr); [ -z "$P" ] || check_ident '^[0-9]+$' "$P"
    ROLE=$(role_arg)
    FOCUS=$(arg focus); FOCUS=${FOCUS:-pr}
    case "$FOCUS" in pr|watcher|session) ;; *) die 1 "open-pr-watch.sh: unknown focus: $FOCUS (valid: pr watcher session)" ;; esac
    load_repo; watch_dir
    # the watcher serving ROLE: its own role set's record, else the one serving both
    WF="$SD/watcher-$ROLE.json"; [ -s "$WF" ] || WF="$SD/watcher.json"
    off=$(settings | jq -r --arg e "$E" '(.watch.notify // {}) as $n
        | if ($n | has($e)) and $n[$e] == false then "yes" else "" end')
    if [ -n "$off" ]; then
        jq -n -c --arg e "$E" '{event: $e, sent: false, reason: "event disabled"}'
        return 0
    fi
    title="open-pr · $OWNER/$REPO"
    summary=$(sed -n 1p "$F"); detail=$(sed -n 2p "$F")
    feed_add
    if snoozed; then
        jq -n -c --arg e "$E" '{event: $e, sent: false, reason: "snoozed"}'
        return 0
    fi
    # Text reaches the notifier as argv only — never spliced into source or a shell string.
    if command -v osascript >/dev/null 2>&1; then
        # A slot dir per showing toast, so a new one never covers one still showing.
        via=toast
        sd="${TMPDIR:-/tmp}/open-pr-toast"; mkdir -p "$sd"; slot=0
        while [ "$slot" -lt 8 ]; do
            if mkdir "$sd/$slot" 2>/dev/null; then break; fi
            pid=$(cat "$sd/$slot/pid" 2>/dev/null || true)
            # stale: toast exited, or a notify died before writing the pid
            if { [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; } \
                || { [ -z "$pid" ] && [ -n "$(find "$sd/$slot" -maxdepth 0 -mmin +1 2>/dev/null)" ]; }; then
                rm -rf "$sd/$slot"; mkdir "$sd/$slot" 2>/dev/null && break
            fi
            slot=$((slot + 1))
        done
        [ "$slot" -lt 8 ] || slot=0
        # Where a click goes: values outside their pattern travel as "" (the toast checks again).
        open=""; [ -z "$P" ] || open=$(fit "$(session_field "$P:$ROLE" open)" "$OPEN_CMD_RE")
        # "Fix now" on a findings toast runs `fix-now` for this repo
        fx=""; [ "$E" != findings ] || [ -z "$P" ] || fx="$SELF_DIR/open-pr-watch.sh"
        nohup osascript -l JavaScript "$SELF_DIR/open-pr-toast.js" "$title" "$summary" "$detail" \
            "$E" "$slot" 8 "$(arg url)" "$WD/snooze_until" "$FOCUS" "$open" \
            "$(watcher_field term "$TERM_RE")" "$(watcher_field term_session "$TERM_SESSION_RE")" \
            "$(watcher_field tty "$TTY_RE")" "$(watcher_field session_id "$SESSION_ID_RE")" \
            "$fx" "${fx:+$D}" "${fx:+$(fit "$RM" '[A-Za-z0-9._-]{1,128}')}" "${fx:+$P}" \
            > "$WD/toast.log" 2>&1 &
        printf '%s\n' "$!" > "$sd/$slot/pid"
    elif command -v notify-send >/dev/null 2>&1; then
        via=notify-send
        notify-send -- "$title" "$summary${detail:+
$detail}"
    else
        via=stderr
        printf '[%s] %s%s\n' "$title" "$summary" "${detail:+ — $detail}" >&2
    fi
    jq -n -c --arg e "$E" --arg via "$via" '{event: $e, sent: true, via: $via}'
}
snoozed() {
    su=$(head -n 1 "$WD/snooze_until" 2>/dev/null || true)
    [ -n "$su" ] && jq -e -n --arg s "$su" "$JQ_UTC"'(try ($s | utc | fromdateiso8601) catch 0) > now' > /dev/null
}
# feed.jsonl: read by the menu bar; renamed into place so it never sees half a file.
FEED_MAX=50
feed_add() {
    lock
    { tail -n $((FEED_MAX - 1)) "$SD/feed.jsonl" 2>/dev/null || true
      jq -n -c --arg at "$(now_iso)" --arg repo "$OWNER/$REPO" --arg pr "$P" --arg e "$E" \
          --arg s "$summary" --arg d "$detail" --arg u "$(arg url)" --arg role "$ROLE" \
          '{at: $at, repo: $repo, pr: (if $pr == "" then null else ($pr | tonumber) end), role: $role, event: $e,
            summary: $s, detail: $d, url: (if $u == "" then null else $u end)}'
    } > "$SD/feed.jsonl.tmp"
    mv "$SD/feed.jsonl.tmp" "$SD/feed.jsonl"
    unlock
}

# -------------------------------------------------------------- snooze ----
cmd_snooze() {
    parse_args "$@"
    FOR=$(arg for); UNTIL=$(arg until); OFF=$(arg off)
    [ "$(printf '%s' "${FOR:+1}${UNTIL:+1}${OFF:+1}")" = 1 ] \
        || die 1 "open-pr-watch.sh: snooze takes exactly one of --for D, --until T, --off"
    watch_dir
    f="$WD/snooze_until"
    if [ -n "$OFF" ]; then
        rm -f "$f"
        printf '{"snooze_until":null}\n'
        return 0
    fi
    if [ -n "$FOR" ]; then
        secs=$(jq -n -r --arg d "$FOR" '$d | capture("^((?<d>[0-9]+)d)?((?<h>[0-9]+)h)?((?<m>[0-9]+)m)?$")
            | (.d // "0" | tonumber) * 86400 + (.h // "0" | tonumber) * 3600 + (.m // "0" | tonumber) * 60' 2>/dev/null || true)
        case "$secs" in ""|0) die 4 "open-pr-watch.sh: invalid value: $FOR (a duration like 30m, 1h, 2h30m)" ;; esac
        t=$(jq -n -r --argjson s "$secs" 'now + $s | floor | todate')
    else
        t=$(jq -n -r --arg s "$UNTIL" "$JQ_UTC"'$s | utc' 2>/dev/null || true)
        [ -n "$t" ] || die 4 "open-pr-watch.sh: invalid value: $UNTIL (ISO-8601, e.g. 2026-01-31T09:00:00Z)"
    fi
    printf '%s\n' "$t" > "$f.tmp"
    mv "$f.tmp" "$f"
    jq -n -c --arg t "$t" '{snooze_until: $t}'
}

# ------------------------------------------------------------- menubar ----
cmd_menubar() {
    parse_args "$@"
    command -v osascript >/dev/null 2>&1 || { printf 'NO-EQUIVALENT\n'; return 0; }
    dirs=$(opr data-dir --all) || exit $?
    watch_dir
    lock "$WD/.lock"
    pf="$WD/menubar.pid"
    pid=$(cat "$pf" 2>/dev/null || true)
    # pids get reused
    live=""
    if printf '%s' "$pid" | grep -Eq '^[0-9]+$' && kill -0 "$pid" 2>/dev/null \
        && ps -p "$pid" -o command= 2>/dev/null | grep -q 'open-pr-menubar\.js'; then live=1; fi
    if [ -n "$(arg close)" ]; then
        [ -n "$live" ] || { rm -f "$pf"; printf 'not running\n'; return 0; }
        kill "$pid" 2>/dev/null || true; rm -f "$pf"; printf 'closed\n'; return 0
    fi
    # It reads the data dirs it was started with: a mapping added since (`data-dir --add-root`)
    # restarts it, else the repos under that mapping never show.
    if [ -n "$live" ]; then
        [ "$dirs" != "$(cat "$WD/menubar.dirs" 2>/dev/null || true)" ] || { printf 'running\n'; return 0; }
        kill "$pid" 2>/dev/null || true
    fi
    printf '%s\n' "$dirs" > "$WD/menubar.dirs"
    # one data dir per argv element (a path holding a newline is not supported)
    nl='
'
    old_ifs=$IFS; IFS=$nl; set -f
    set -- $dirs
    IFS=$old_ifs; set +f
    nohup osascript -l JavaScript "$SELF_DIR/open-pr-menubar.js" "$WD/snooze_until" "$pf" \
        "$((3 * BACKOFF_CAP))" "$@" "$SELF_DIR/open-pr-watch.sh" > "$WD/menubar.log" 2>&1 < /dev/null &
    pid=$!
    printf '%s\n' "$pid" > "$pf"
    # Inside a shell sandbox it cannot reach the window server and exits at once: say so, never
    # `started` for an item that is not there.
    sleep 2
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$pf" "$WD/menubar.dirs"
        die 1 "open-pr-watch.sh menubar: the menu bar exited at start — run it with the shell sandbox off (log: $WD/menubar.log)"
    fi
    printf 'started\n'
}

# --------------------------------------------------------------- trust ----
# Read-only: the trust prompt is the user's to accept, never this script's to write.
cmd_trust() {
    parse_args "$@"
    RUNNER=$(req runner); check_runner "$RUNNER"
    D=$(arg cwd); [ -n "$D" ] || D=$(arg repo_dir); [ -n "$D" ] || D=.
    [ -d "$D" ] || die 1 "open-pr-watch.sh: no such directory: $D"
    D=$(cd "$D" && pwd)
    [ "$RUNNER" = claude ] || { printf 'n/a\n'; return 0; }
    cf="${OPEN_PR_CLAUDE_CONFIG:-${HOME:-}/.claude.json}"
    # some jq builds exit 0 on a parse error, printing nothing
    v=$(jq -r --arg d "$D" '.projects[$d].hasTrustDialogAccepted // false | tostring' "$cf" 2>/dev/null || true)
    case "$v" in
        true)  printf 'trusted\n' ;;
        false) printf 'untrusted\nrun: cd %s && claude\n' "$D" ;;
        *)     printf 'unknown\n' ;;
    esac
}

# ---------------------------------------------------------------- usage ----
usage() {
    cat <<'EOF'
usage: open-pr-watch.sh <subcommand> [--option value ...]
       open-pr-watch.sh --help

Common options:
  `--repo-dir D` (default: the cwd) names the watched repo; its git remote (`--remote R`, default
  origin, else the only one) picks vendor and `<repo>`, and state lives in
  `<data>/<repo>/watch/`, `<data>` resolved for D (`snooze`, `menubar`: no repo; machine state
  in `${XDG_CONFIG_HOME:-~/.config}/open-pr/watch/`).
  Output is JSON lines unless stated.

Subcommands:
  wait [--once] [--roles review,fix] [--fix-prs N,N…]
      poll every `watch.poll_interval_seconds` until something happens, print it, exit 0; `repo` =
      owner/repo in every event. `--roles` (default both) picks what is delivered; one wait per repo
      and role on a machine, so a review wait and a fix wait run side by side:
      review: `{"event":"trigger","repo",<trigger fields>}` per new comment starting with the trigger
      (`watch.trigger`, default `/open-pr`; `@me` = a mention of this machine's own account,
      exit 1 when that account cannot be read).
      fix: `{"event":"findings","repo","pr","review_id","counts","url","comment_id","thread_id",
      "user"}` once per review the plugin posted on a fix-role PR — the user's own open PRs
      (author = this machine's account), or only those `--fix-prs` names — plus each PR whose
      author asked for its review (a trigger by that author): it joins the fix role. `hide` takes a
      PR out.
      `{"event":"fix_now","repo","pr"[,"url","review_id","counts","comment_id","thread_id","user"]}`
      per `fix-now` since (with the PR's latest findings), within 5 s while waiting.
      `{"event":"session","repo","pr","role","state","open"}` per session of its roles whose state changed.
      Once a session's result (draft|posted|lgtm_chat|nothing|answered|fixed|failed|stopped) is
      delivered the session is finished: no slot held, and no more events from it until spawn resumes
      it, except a new result its status file is rewritten to (a draft the user published there).
      `{"event":"ready","repo","pr","role"}` = a queued session of its roles has its turn (run `next`
      with the same `--roles`). The first run of a role set starts its cursor at now (no replay). Events count as delivered only when wait exits
      0 — act on no other output. GitHub requests are conditional on the ETags kept in `etags/`.
      Nothing active and no event for 600 s ⇒ polls every 180 s, unless the setting is slower or
      `poll` set this machine's interval. A vendor rate limit doubles the wait (up to 900 s, one
      stderr line each time) until a poll succeeds. At most every 600 s, a tracked PR no longer
      open (merged or closed) is hidden and its sessions marked closed, then stopped once not in use;
      a failed check prints one stderr line and waits for the next. Every poll touches `heartbeat`;
      each start writes `watcher.json` {pid, cwd, term, term_session, tty, session_id, repo_dir,
      remote} (the terminal tab it runs in, its Claude Code session, and the repo, for the menu bar).
      A wait serving one role names these and `stop` with a suffix: `heartbeat-fix`,
      `watcher-fix.json`, `stop-fix`.
      `--once`: one poll, exit 0 with nothing printed when nothing happened
  spawn --runner R --pr N --name S --prompt-file F [--role review|fix] [--url U] [--cwd W] [--fresh]
      open PR N's session for that role (default review) with the prompt read from F →
      `{"pr","role","id","open"}`; it has one ⇒ resume it (`"resumed":true`; a `"warning"` when the
      platform started a copy); all `max_concurrent` slots busy (both roles share them), or that
      session still running ⇒ `{"pr","role","queued":true,"reason"}`. The session runs in W (default
      the repo dir), recorded so a resume runs there again. `--fresh`: open a new session even when
      there is one; the old one is left untouched and untracked. U (the PR URL) is kept for the menu
      bar. Takes N off the hidden list; a fix session takes over the PR's pending findings
  status [--pr N] [--role R]
      per session `{"pr","role","runner","id","state","open"[,"findings"]}` (a fix session: the
      findings it was opened for, as `findings` events carry them), state one of working|question|draft|
      posted|lgtm_chat|nothing|answered|fixed|failed|stopped (`"note"` says why when the session left
      no status file); a finished session shows its result with `"finished":true`, a hidden one
      `"hidden":true`
  next [--roles review,fix]
      a slot is free ⇒ pop the first queued session of those roles (default both) not running → `{"pr","role","runner","name",
      "prompt_file","queued_at"[,"cwd"][,"url"][,"fresh"]}`, to pass back to spawn; else nothing
  forget --pr N [--role R]
      drop that session (default review), so the next spawn opens a fresh one
  hide --pr N
      both roles: leave PR N out of the menu bar until the next spawn for it, out of the fix role,
      its pending findings dropped → `{"pr","hidden":true}`
  fix-now --pr N
      a "Fix now" click: the running wait delivers it as `fix_now` → `{"pr","fix_now":true}`; repeat
      clicks before then are one, and a click while that PR's fix session runs is dropped
  paths [--pr N] [--role R]
      `dir=…` `prompts=…` lines; with `--pr` also `status_file=…` (that session writes it) and `log=…`
  notify --event E --text-file F [--pr N] [--role R] [--url U] [--focus pr|watcher|session]
      toast titled `open-pr · <owner>/<repo>`: F line 1 = summary, line 2 = detail; E one of
      review_started|question|draft_ready|posted|re_review|findings|error. Skipped (`"sent":false` +
      reason) when `watch.notify.E` is false, or while snoozed (see snooze). Each one not disabled
      joins `feed.jsonl` (last 50, with R). macOS: drawn by open-pr-toast.js (no Notifications
      permission; hover holds it, toasts stack, `1h` snoozes; a `findings` toast with N adds "Fix
      now", which runs `fix-now`), else notify-send, else stderr. A click goes where `--focus` says:
      `pr` (default) opens U; `watcher` brings the watcher's terminal tab forward; `session` opens
      PR N's session of role R in the watcher's terminal app (no valid open command ⇒ as
      `watcher`); a watcher in an unknown terminal ⇒ opens U. The watcher = the wait serving R
  snooze --for D | --until T | --off
      no toasts on this machine, every repo, for D (30m, 1h, 2h30m) or until T (ISO-8601);
      `--off` resumes → `{"snooze_until"}` (UTC, or null). Shared with the toast and the menu bar
  poll --seconds N | --off
      this machine's poll interval, every repo, min 15 s, over `poll_interval_seconds`; a running
      wait applies it within 5 s. `--off` returns to the setting → `{"poll_seconds"}`. Menu bar too
  menubar [--close]
      macOS: start the menu bar item (review and fix rows grouped by the watcher serving their role,
      recent toasts, snooze; "Remove from list" on a PR runs `hide`, "Fix now" runs `fix-now`) unless it runs →
      `started` | `running` (exit 1 when it exits at start, e.g. inside a shell sandbox; its
      stderr is `menubar.log`); one running on other data dirs than `data-dir --all` now prints is
      restarted (`started`); it stays until closed. `--close` → `closed` | `not running`. Elsewhere
      `NO-EQUIVALENT`. Plain lines
  trust --runner R [--cwd W]
      will R open a session in W (default the repo dir) without a prompt? claude: `trusted` | `untrusted` plus
      a `run: cd <dir> && claude` line (trust is per exact directory, a trusted parent does not
      count) | `unknown` (its config unreadable); other runners: `n/a`. Plain lines, read-only

Runners (`--runner`): claude, codex, gemini, cursor, antigravity.

Exit codes:
  0  ok
  1  other
  4  invalid value
  7  `<data>` not set
  8  the runner refuses the session's directory as untrusted — the message names the command to run once
  9  `wait --once` hit a vendor rate limit
  10 another `wait` already watches this repo for one of these roles on this machine — the message
     names the role and its pid
  11 `wait` found its `stop` in the repo's state dir (the menu bar's "Stop"); it consumes the
     file and prints no events. A `wait` start clears one left from before
     (`wait` also exits 1 once triggers has failed 3 polls in a row, naming the last error)
EOF
}

case "${1:-}" in -h|--help) usage; exit 0 ;; esac
need jq

TMPD=$(mktemp -d "${TMPDIR:-/tmp}/open-pr-watch.XXXXXX")
trap 'unlock; rm -rf "$TMPD" ${OPEN_PR_WATCH_COPY:+"$OPEN_PR_WATCH_COPY"}' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

sub="${1:-}"; [ -n "$sub" ] && shift || die 1 "open-pr-watch.sh: no subcommand (see --help)"
case "$sub" in
    wait)
        # sh reads a script as it runs: an update under an hours-long `wait` would mix two files.
        if [ -z "${OPEN_PR_WATCH_COPY:-}" ]; then
            cp "$0" "$TMPD/open-pr-watch.sh"
            OPEN_PR_WATCH_COPY="$TMPD"; OPEN_PR_WATCH_SELF_DIR="$SELF_DIR"
            export OPEN_PR_WATCH_COPY OPEN_PR_WATCH_SELF_DIR
            exec sh "$TMPD/open-pr-watch.sh" wait "$@"
        fi
        cmd_wait "$@" ;;
    spawn)   cmd_spawn "$@" ;;
    status)  cmd_status "$@" ;;
    next)    cmd_next "$@" ;;
    forget)  cmd_forget "$@" ;;
    hide)    cmd_hide "$@" ;;
    fix-now) cmd_fix_now "$@" ;;
    paths)   cmd_paths "$@" ;;
    notify)  cmd_notify "$@" ;;
    trust)   cmd_trust "$@" ;;
    snooze)  cmd_snooze "$@" ;;
    poll)    cmd_poll "$@" ;;
    menubar) cmd_menubar "$@" ;;
    *) die 1 "open-pr-watch.sh: unknown subcommand: $sub (see --help)" ;;
esac
