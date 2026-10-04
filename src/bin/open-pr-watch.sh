#!/bin/sh
# open-pr watch runtime: the deterministic half of /open-pr:watch-review — trigger cursor,
# PR -> session map, slot limit and queue, notifications, and how each agent platform opens,
# resumes and reports a session.
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
EVENTS="review_started question draft_ready posted re_review error"
# States that end a session's reporting (see `finished` under state).
TERMINAL="posted draft lgtm_chat nothing failed stopped"
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
    SD="$data/$REPO/watch-review"
    STATE="$SD/state.json"
    mkdir -p "$SD/prompts"
    # Prompts quote PR comments: keep them out of the review-memory repo.
    grep -qx 'watch-review/' "$data/.gitignore" 2>/dev/null || printf 'watch-review/\n' >> "$data/.gitignore"
}
# WD = machine-wide state (snooze, menu bar pid), whichever data dirs the repos use.
watch_dir() {
    [ -n "${XDG_CONFIG_HOME:-}${HOME:-}" ] || die 1 "open-pr-watch.sh: neither XDG_CONFIG_HOME nor HOME is set"
    WD="${XDG_CONFIG_HOME:-$HOME/.config}/open-pr/watch"
    mkdir -p "$WD"
}
status_file() { printf '%s/pr-%s.status.json' "$SD" "$1"; }
log_file() { printf '%s/pr-%s.log' "$SD" "$1"; }

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
    v=$(settings | jq -r --arg k "$1" '.watch_review[$k] // empty | select(type == "number" and . >= 1) | floor')
    printf '%s' "${v:-$2}"
}

# --------------------------------------------------------------- state ----
# state.json:
#   cursor    newest processed comment created_at, UTC, second precision
#   seen      comment ids at exactly that created_at (ties the cursor cannot order)
#   sessions  { "<pr>": {runner,id,session_id,name,repo,url,open,cwd,pid,started_at,last_state,
#                        last_state_at,finished[,closed]} }
#             last_state_at = when last_state last changed (the menu bar weighs it against the feed)
#             cwd = where it was opened; a resume runs there again
#             finished = `wait` delivered its result (a TERMINAL state): the session is the
#             user's now, reports nothing more and holds no slot until spawn resumes it
#             closed = the PR was merged or closed (see check_open)
#   hidden    PR numbers the menu bar leaves out (`hide`, or merged/closed); spawn takes N out
#   open_checked_at  last check_open
#   queue     [ {pr,runner,name,prompt_file,queued_at[,cwd][,fresh]} ] waiting for a free slot
LOCKED=""
lock() {   # $1 lock dir, default the repo's state lock
    lk="${1:-$SD/.lock}"; i=0
    while ! mkdir "$lk" 2>/dev/null; do
        holder=$(cat "$lk/pid" 2>/dev/null || true)
        if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then rm -rf "$lk"; continue; fi
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
session_field() { state_json | jq -r --arg pr "$1" --arg k "$2" '.sessions[$pr][$k] // empty'; }

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
lazy_id() {   # $1 runner, $2 pr → the id a headless CLI reports in its output
    case "$1" in
        codex)       id_from_log "$(log_file "$2")" thread.started thread_id ;;
        antigravity) id_from_log "$(log_file "$2")" init conversation_id ;;
    esac
}
headless_launch() {   # sets RID, PID; $1 runner, $2 pr, $3 prompt
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
headless_resume() {   # sets PID; $1 runner, $2 pr, $3 id, $4 prompt
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
# A finished session reads as the result it reported, whatever the user does in it since.
from_status_file() {   # $1 pr
    f=$(status_file "$1")
    s=$(jq -r '.state // empty' "$f" 2>/dev/null || true)
    case "$s" in
        posted|draft|lgtm_chat|nothing|failed|question) printf '%s' "$s" ;;
        *) printf 'failed' ;;
    esac
}
status_note() {   # why from_status_file said failed without the file saying so
    f=$(status_file "$1")
    [ -s "$f" ] || { printf 'session ended without writing %s' "$f"; return 0; }
    s=$(jq -r '.state // empty' "$f" 2>/dev/null || true)
    case "$s" in
        posted|draft|lgtm_chat|nothing|failed|question) printf '' ;;
        *) printf 'status file holds no known state' ;;
    esac
}
CLAUDE_AGENTS=""
# `claude agents` state of the entry with id $1. A resumed or attached session that finished its
# turn stays "working" with status "idle" (waiting at its prompt), never "done": read as done.
claude_state() {
    printf '%s' "$CLAUDE_AGENTS" | jq -r --arg id "$1" '[.[]? | select(.id == $id)][0] // {}
        | if .state == "working" and .status == "idle" then "done" else .state // empty end' 2>/dev/null || true
}
status_one() {   # $1 pr
    pr="$1"
    row=$(state_json | jq -r --arg pr "$pr" '(.hidden // []) as $h | .sessions[$pr]
        | [.runner, .id, .session_id, .pid, (.finished == true), .last_state, ($h | index([$pr | tonumber]) != null)]
        | map(. // "" | tostring) | join("\u001f")')
    # not whitespace: IFS whitespace would merge the empty fields
    us=$(printf '\037')
    IFS="$us" read -r runner id sid pid fin last hid <<EOF
$row
EOF
    note=""; inuse=""
    if [ "$fin" = true ]; then
        [ -n "$id" ] || id=$(lazy_id "$runner" "$pr")
        st="$last"
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
            done)    st=$(from_status_file "$pr"); note=$(status_note "$pr") ;;
            "")
                if [ -s "$(status_file "$pr")" ]; then st=$(from_status_file "$pr"); note=$(status_note "$pr")
                else st=stopped; note="claude agents does not list session $id"; fi ;;
            *) st=working ;;
        esac
    else
        [ -n "$id" ] || id=$(lazy_id "$runner" "$pr")
        if pid_alive "$pid"; then st=working
        else st=$(from_status_file "$pr"); note=$(status_note "$pr"); fi
    fi
    jq -n -c --argjson pr "$pr" --arg runner "$runner" --arg id "$id" --arg sid "$sid" \
        --arg state "$st" --arg open "$(open_cmd "$runner" "$id")" --arg note "$note" --arg fin "$fin" \
        --arg inuse "$inuse" --arg hid "$hid" \
        '{pr: $pr, runner: $runner, id: (if $id == "" then null else $id end),
          session_id: (if $sid == "" then null else $sid end), state: $state,
          open: (if $open == "" then null else $open end)}
         + (if $note == "" then {} else {note: $note} end)
         + (if $fin == "true" then {finished: true} else {} end)
         + (if $inuse == "" then {} else {in_use: $inuse} end)
         + (if $hid == "true" then {hidden: true} else {} end)'
}
status_all() {   # every tracked session, or just $1
    CLAUDE_AGENTS=""   # `wait` polls many times in one process: re-list each pass
    if [ -n "${1:-}" ]; then
        [ -n "$(session_field "$1" runner)" ] && status_one "$1"
        return 0
    fi
    for p in $(state_json | jq -r '.sessions | keys[]' | sort -n); do status_one "$p"; done
}
# Ids a headless CLI only reports once it runs are folded back into the map.
remember_ids() {   # $1 = status JSONL file
    [ -s "$1" ] || return 0
    state_update --slurpfile st "$1" \
        'reduce $st[] as $s (.; if .sessions[($s.pr | tostring)] then
            .sessions[($s.pr | tostring)] |= (.id = (.id // $s.id) | .session_id = (.session_id // $s.session_id)
                                              | .open = (.open // $s.open))
         else . end)'
}
active_count() {   # $1 status JSONL, $2 pr to leave out
    jq -s --arg skip "${2:-}" '[.[] | select((.pr | tostring) != $skip and (.state == "working" or .state == "question"))] | length' "$1"
}

cmd_status() {
    parse_args "$@"
    N=$(arg pr); [ -z "$N" ] || check_ident '^[0-9]+$' "$N"
    load_repo; lock
    status_all "$N" > "$TMPD/status"
    remember_ids "$TMPD/status"
    jq -c '{pr, runner, id, state, open} + (if .note then {note} else {} end) + (if .finished then {finished} else {} end)
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
park_idle() {   # $1 status JSONL
    state_json | jq -r --slurpfile s "$1" --argjson idle "$IDLE_PARK" '
        .sessions | to_entries[] | .key as $pr | .value
        | select(.runner == "claude" and .finished == true and .parked != true and .id != null
                 and (.closed == true or ((.finished_at // null) != null
                                           and (now - (.finished_at | fromdateiso8601)) >= $idle)))
        | select([$s[] | select((.pr | tostring) == $pr) | .in_use // empty] | length == 0)
        | "\($pr) \(.id)"' | while read -r pr id; do
        check_ident '^[0-9a-f]+$' "$id"
        (cd "$D" && claude stop "$id") > /dev/null 2>&1 || true
        state_update --arg pr "$pr" '.sessions[$pr].parked = true'
    done
}
# jq: PRs a queued request must still wait for — $s = status rows, $q = queue, $now epoch.
JQ_BUSY='def busy($s; $q; $now):
    [$s[] | . as $r
     | select(.state == "working" or .in_use == "working"
              or (.in_use == "blocked"
                  and (([$q[]? | select(.pr == $r.pr) | .queued_at // empty][0] // null) as $at
                       | $at == null or ($now - ($at | fromdateiso8601)) < '"$IN_USE_GRACE"')))
     | .pr];'
enqueue() {   # $1 pr, $2 reason
    state_update --argjson pr "$1" --arg runner "$RUNNER" --arg name "$NAME" --arg f "$PF" --arg at "$(now_iso)" \
        --arg cwd "$CW" --arg fresh "$FRESH" \
        '(([.queue[] | select(.pr == $pr) | .queued_at][0]) // $at) as $since
         | .queue = ([.queue[] | select(.pr != $pr)]
                     + [{pr: $pr, runner: $runner, name: $name, prompt_file: $f, queued_at: $since}
                        + (if $cwd == "" then {} else {cwd: $cwd} end)
                        + (if $fresh == "" then {} else {fresh: true} end)])'
    jq -n -c --argjson pr "$1" --arg why "$2" '{pr: $pr, queued: true, reason: $why}'
}
cmd_spawn() {
    parse_args "$@"
    RUNNER=$(req runner); check_runner "$RUNNER"
    N=$(pr_arg); NAME=$(req name); PF=$(req prompt_file); URL=$(arg url)
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
    state_update --argjson pr "$N" '.hidden = [(.hidden // [])[] | select(. != $pr)]'
    max=$(setting_int max_concurrent 5)
    status_all > "$TMPD/status"
    remember_ids "$TMPD/status"
    # --fresh waits for a running review: both would write the same status file.
    if [ -n "$FRESH" ] && [ "$(jq -r --argjson pr "$N" 'select(.pr == $pr) | .state' "$TMPD/status")" = working ]; then
        enqueue "$N" "session still running"; return 0
    fi
    have=""; [ -n "$FRESH" ] || have=$(session_field "$N" runner)
    if [ -n "$have" ] && [ "$have" != "$RUNNER" ]; then
        die 1 "open-pr-watch.sh: PR $N already has a $have session; forget it first to open one under $RUNNER"
    fi
    if [ -n "$have" ]; then
        cur=$(jq -r --argjson pr "$N" 'select(.pr == $pr) | .state' "$TMPD/status")
        [ "$cur" != working ] || { enqueue "$N" "session still running"; return 0; }
        busy=$(state_json | jq -r --slurpfile s "$TMPD/status" "$JQ_BUSY"' busy($s; .queue; now) | index('"$N"') != null')
        [ "$busy" != true ] || { enqueue "$N" "session in use"; return 0; }
    fi
    [ "$(active_count "$TMPD/status" "$N")" -lt "$max" ] || { enqueue "$N" "all $max slots busy"; return 0; }

    PROMPT=$(cat "$PF")
    rm -f "$(status_file "$N")"
    RID=""; SID=""; PID=""; WARNING=""; resumed=false
    if [ -n "$have" ]; then
        resumed=true
        RID=$(session_field "$N" id); SID=$(session_field "$N" session_id)
        W=$(session_field "$N" cwd); [ -n "$W" ] || W=${CW:-$D}
        if [ "$RUNNER" = claude ]; then
            claude_resume "$RID" "$SID" "$PROMPT"
        else
            [ -n "$RID" ] || RID=$(lazy_id "$RUNNER" "$N")
            [ -n "$RID" ] || die 1 "open-pr-watch.sh: no $RUNNER session id recorded for PR $N — forget it to start fresh"
            headless_resume "$RUNNER" "$N" "$RID" "$PROMPT"
        fi
    else
        W=${CW:-$D}
        if [ "$RUNNER" = claude ]; then claude_launch "$NAME" "$PROMPT"
        else headless_launch "$RUNNER" "$N" "$PROMPT"; fi
    fi
    state_update --arg pr "$N" --arg runner "$RUNNER" --arg id "$RID" --arg sid "$SID" \
        --arg name "$NAME" --arg pid "$PID" --arg at "$(now_iso)" --arg repo "$OWNER/$REPO" \
        --arg url "$URL" --arg open "$(open_cmd "$RUNNER" "$RID")" --arg cwd "$W" \
        'def nul: if . == "" then null else . end;
         .sessions[$pr] = {runner: $runner, id: ($id | nul), session_id: ($sid | nul), name: $name,
                           repo: $repo, url: (($url | nul) // .sessions[$pr].url), open: ($open | nul), cwd: $cwd,
                           pid: ($pid | nul | if . then tonumber else . end), started_at: $at,
                           last_state: "working", last_state_at: $at, finished: false}
         | .queue = [.queue[] | select(.pr != ($pr | tonumber))]'
    jq -n -c --argjson pr "$N" --arg id "$RID" --arg open "$(open_cmd "$RUNNER" "$RID")" \
        --argjson resumed "$resumed" --arg warn "$WARNING" \
        '{pr: $pr, id: (if $id == "" then null else $id end), open: (if $open == "" then null else $open end)}
         + (if $resumed then {resumed: true} else {} end)
         + (if $warn == "" then {} else {warning: $warn} end)'
}

# ---------------------------------------------------------- next/forget ----
cmd_next() {
    parse_args "$@"
    load_repo; lock
    max=$(setting_int max_concurrent 5)
    status_all > "$TMPD/status"
    remember_ids "$TMPD/status"
    [ "$(active_count "$TMPD/status")" -lt "$max" ] || return 0
    pick=$(state_json | jq -c --slurpfile s "$TMPD/status" "$JQ_BUSY"'
        busy($s; .queue; now) as $busy | [.queue[] | select(.pr as $p | $busy | index($p) | not)][0] // empty')
    [ -n "$pick" ] || return 0
    state_update --argjson pick "$pick" '.queue = [.queue[] | select(.pr != $pick.pr)]'
    printf '%s\n' "$pick"
}
cmd_forget() {
    parse_args "$@"
    N=$(pr_arg)
    load_repo; lock
    state_update --arg pr "$N" 'del(.sessions[$pr])'
    rm -f "$(status_file "$N")"
    jq -n -c --argjson pr "$N" '{pr: $pr, forgotten: true}'
}
cmd_hide() {
    parse_args "$@"
    N=$(pr_arg)
    load_repo; lock
    state_update --argjson pr "$N" '.hidden = ((.hidden // []) + [$pr] | unique)'
    jq -n -c --argjson pr "$N" '{pr: $pr, hidden: true}'
}
cmd_paths() {
    parse_args "$@"
    N=$(arg pr); [ -z "$N" ] || check_ident '^[0-9]+$' "$N"
    load_repo
    printf 'dir=%s\nprompts=%s/prompts\n' "$SD" "$SD"
    [ -z "$N" ] || printf 'status_file=%s\nlog=%s\n' "$(status_file "$N")" "$(log_file "$N")"
}

# ---------------------------------------------------------------- wait ----
# open-pr.sh triggers validates whatever this returns.
TOKEN=""
trigger_token() {
    t=$(settings | jq -r '.watch_review.trigger // "/open-pr"')
    [ "$t" = "@me" ] || { printf '%s' "$t"; return 0; }
    who=$(opr account --vendor "$VENDOR" --owner "$OWNER" --repo "$REPO" ${HOST:+--host "$HOST"}) || exit $?
    case "$who" in
        ""|UNKNOWN) die 1 "open-pr-watch.sh: watch_review.trigger is @me, but the account this machine is logged in as cannot be read (Bitbucket under a workspace token has no identity) — use a user credential, or set the trigger to @<login> or a /word" ;;
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
        | [($s.sessions // {} | to_entries[] | select(.value.closed != true) | .key | tonumber),
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
            | reduce ($gone[] | tostring) as $k (.; if .sessions[$k] then .sessions[$k].closed = true else . end)'
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
poll_once() {   # sets GOT (events committed), LIMITED (vendor rate-limited)
    GOT=""; LIMITED=""; : "${FAILS:=0}"
    touch "$SD/heartbeat"   # read by the menu bar
    lock
    cursor=$(state_json | jq -r "$JQ_UTC"' .cursor // empty | utc')
    if [ -z "$cursor" ]; then
        # First run: no replay of history.
        state_update --arg c "$(now_iso)" '.cursor = $c | .seen = []'
        unlock; return 0
    fi
    # A cursor stored with an offset is rewritten in UTC: comparisons below are string compares.
    [ "$cursor" = "$(state_json | jq -r '.cursor')" ] || state_update --arg c "$cursor" '.cursor = $c'
    unlock
    check_open
    # --since is strict and the cursor has second precision: ask from 1s earlier; `seen` drops repeats.
    since=$(jq -n -r --arg c "$cursor" '$c | fromdateiso8601 - 1 | todateiso8601')
    [ -n "$TOKEN" ] || TOKEN=$(trigger_token)
    rc=0
    opr triggers --vendor "$VENDOR" --owner "$OWNER" --repo "$REPO" ${HOST:+--host "$HOST"} \
        --since "$since" --mark-file "$TMPD/mark" --token "$TOKEN" > "$TMPD/triggers" 2> "$TMPD/triggers.err" || rc=$?
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
    lock
    state_json > "$TMPD/state.in"
    jq -c -s --slurpfile st "$TMPD/state.in" "$JQ_UTC"'
        ($st[0].cursor) as $cur | ($st[0].seen // []) as $seen
        | map(select(type == "object") | . + {_k: (.created_at | utc)})
        | map(select(._k > $cur or (._k == $cur and ((.comment_id | tostring) as $c | $seen | index([$c]) | not))))
        | reduce .[] as $t ([]; if any(.[]; .comment_id == $t.comment_id) then . else . + [$t] end)
        | sort_by(._k)[]' "$TMPD/triggers" > "$TMPD/new"
    status_all > "$TMPD/status"
    jq -c -s --slurpfile st "$TMPD/state.in" '
        .[] | select(.state != ($st[0].sessions[(.pr | tostring)].last_state // null))
        | {event: "session", pr, state, open} + (if .note then {note} else {} end)' "$TMPD/status" > "$TMPD/sess"
    # `ready`: nothing else wakes the watcher to run `next`.
    max=$(setting_int max_concurrent 5)
    jq -c -s --slurpfile st "$TMPD/state.in" --argjson max "$max" "$JQ_BUSY"'
        . as $s
        | ([$s[] | select(.finished != true and (.state == "working" or .state == "question"))] | length) as $active
        | busy($s; $st[0].queue; now) as $busy
        | if $active < $max then
              ([$st[0].queue[]? | select(.pr as $p | $busy | index($p) | not)][0] // empty)
              | {event: "ready", pr}
          else empty end' "$TMPD/status" > "$TMPD/ready"
    # The cursor follows every comment fetched, trigger or not: else a quiet repo re-fetches
    # everything since start, every poll.
    mark=$(cat "$TMPD/mark" 2>/dev/null || true)
    if [ ! -s "$TMPD/new" ] && [ ! -s "$TMPD/sess" ] && [ ! -s "$TMPD/ready" ]; then
        remember_ids "$TMPD/status"
        [ -z "$mark" ] || state_update --arg m "$mark" \
            'if $m > .cursor then .cursor = $m | .seen = [] else . end'
        park_idle "$TMPD/status"
        unlock; return 0
    fi
    jq -c --slurpfile new "$TMPD/new" --slurpfile status "$TMPD/status" --arg m "$mark" --arg terminal "$TERMINAL" \
        --arg at "$(now_iso)" '
        ([.cursor, $m] + [$new[]._k] | map(select(. != "")) | max) as $c
        | .seen = (if $c == .cursor then (.seen // []) else [] end
                   + [$new[] | select(._k == $c) | .comment_id | tostring] | unique)
        | .cursor = $c
        | ($terminal | split(" ")) as $done
        | reduce $status[] as $s (.; if .sessions[($s.pr | tostring)] then
              .sessions[($s.pr | tostring)] |= ((if .last_state != $s.state then .last_state_at = $at else . end)
                                                | .last_state = $s.state | .id = (.id // $s.id)
                                                | .session_id = (.session_id // $s.session_id)
                                                | .open = (.open // $s.open)
                                                | if any($done[]; . == $s.state) then .finished = true | .finished_at = (.finished_at // $at) else . end)
          else . end)' "$TMPD/state.in" > "$STATE.tmp" || die 1 "open-pr-watch.sh: state update failed"
    # One watcher may run a `wait` per repo.
    { jq -c '{event: "trigger"} + del(._k)' "$TMPD/new"; cat "$TMPD/sess" "$TMPD/ready"; } \
        | jq -c --arg r "$OWNER/$REPO" '{event, repo: $r} + del(.event)' > "$TMPD/events"
    cat "$TMPD/events"
    mv "$STATE.tmp" "$STATE"
    park_idle "$TMPD/status"
    unlock
    GOT=1
}
# watcher.json: which terminal tab runs this watcher, for the menu bar to group its repos and
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
        '{pid: $pid, cwd: $cwd, term: $term, term_session: $ts, tty: $tty, session_id: $sid, repo_dir: $rd, remote: $rm}' > "$SD/watcher.json.tmp"
    mv "$SD/watcher.json.tmp" "$SD/watcher.json"
}
watcher_field() {   # $1 key of watcher.json, $2 ERE → its value, or "" when it does not match
    fit "$(jq -r --arg k "$1" '.[$k] // "" | strings' "$SD/watcher.json" 2>/dev/null || true)" "$2"
}
stop_requested() {
    [ -e "$SD/stop" ] || return 0
    rm -f "$SD/stop"
    die 11 "open-pr-watch.sh: stopped from the menu bar"
}
cmd_wait() {
    parse_args "$@"
    load_repo
    # Two waits on one repo would share state.json and split the events between them.
    wp="$SD/wait.pid"
    old=$(cat "$wp" 2>/dev/null || true)
    if [ -n "$old" ] && [ "$old" != "$$" ] && kill -0 "$old" 2>/dev/null \
        && ps -o command= -p "$old" 2>/dev/null | grep -q 'open-pr-watch.sh wait'; then
        die 10 "open-pr-watch.sh: $OWNER/$REPO is already watched on this machine (wait pid $old) — stop that watcher first"
    fi
    # Written by the menu bar's "Stop watcher"; one left from an earlier run must not stop this one.
    rm -f "$SD/stop"
    printf '%s\n' "$$" > "$wp"
    write_watcher
    watch_dir
    base=$(setting_int poll_interval_seconds 60)
    interval=$(poll_interval "$base"); delay=$interval
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
            interval=$(poll_interval "$base"); delay=$interval
        fi
        # Slept in slices so a faster poll chosen meanwhile applies within seconds.
        waited=0; slice=5; [ "$delay" -ge "$slice" ] || slice=$delay
        while [ "$waited" -lt "$delay" ]; do
            sleep "$slice"; waited=$((waited + slice))
            stop_requested
            [ -n "$LIMITED" ] || [ "$waited" -lt "$(poll_interval "$base")" ] || break
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
    FOCUS=$(arg focus); FOCUS=${FOCUS:-pr}
    case "$FOCUS" in pr|watcher|session) ;; *) die 1 "open-pr-watch.sh: unknown focus: $FOCUS (valid: pr watcher session)" ;; esac
    load_repo; watch_dir
    off=$(settings | jq -r --arg e "$E" '(.watch_review.notify // {}) as $n
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
        open=""; [ -z "$P" ] || open=$(fit "$(session_field "$P" open)" "$OPEN_CMD_RE")
        nohup osascript -l JavaScript "$SELF_DIR/open-pr-toast.js" "$title" "$summary" "$detail" \
            "$E" "$slot" 8 "$(arg url)" "$WD/snooze_until" "$FOCUS" "$open" \
            "$(watcher_field term "$TERM_RE")" "$(watcher_field term_session "$TERM_SESSION_RE")" \
            "$(watcher_field tty "$TTY_RE")" "$(watcher_field session_id "$SESSION_ID_RE")" \
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
          --arg s "$summary" --arg d "$detail" --arg u "$(arg url)" \
          '{at: $at, repo: $repo, pr: (if $pr == "" then null else ($pr | tonumber) end), event: $e,
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
    [ -z "$live" ] || { printf 'running\n'; return 0; }
    # one data dir per argv element (a path holding a newline is not supported)
    nl='
'
    old_ifs=$IFS; IFS=$nl; set -f
    set -- $dirs
    IFS=$old_ifs; set +f
    nohup osascript -l JavaScript "$SELF_DIR/open-pr-menubar.js" "$WD/snooze_until" "$pf" \
        "$((3 * BACKOFF_CAP))" "$@" "$SELF_DIR/open-pr-watch.sh" > /dev/null 2>&1 < /dev/null &
    printf '%s\n' "$!" > "$pf"
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
  `<data>/<repo>/watch-review/`, `<data>` resolved for D (`snooze`, `menubar`: no repo; machine state
  in `${XDG_CONFIG_HOME:-~/.config}/open-pr/watch/`).
  Output is JSON lines unless stated.

Subcommands:
  wait [--once]
      poll every `watch_review.poll_interval_seconds` until something happens, print it, exit 0:
      `{"event":"trigger","repo",<trigger fields>}` per new comment starting with the trigger
      (`watch_review.trigger`, default `/open-pr`; `@me` = a mention of this machine's own account,
      exit 1 when that account cannot be read),
      `{"event":"session","repo","pr","state","open"}` per session whose state changed; `repo` =
      owner/repo. Once a session's result (draft|posted|lgtm_chat|failed|stopped) is delivered the
      session is finished: no more events from it, no slot held, until spawn resumes it.
      `{"event":"ready","repo","pr"}` = a queued PR's turn has come (run `next`). The first
      run starts the cursor at now (no replay). Events count as delivered only when wait exits 0 —
      act on no other output. A vendor rate limit doubles the wait (up to 900 s, one stderr line
      each time) until a poll succeeds. At most every 600 s, a tracked PR no longer open (merged or
      closed) is hidden and its session marked closed, then stopped once not in use; a failed check
      prints one stderr line and waits for the next. Every poll touches `heartbeat`; each start writes
      `watcher.json` {pid, cwd, term, term_session, tty, session_id, repo_dir, remote} (the terminal tab
      it runs in, its Claude Code session, and the repo, for the menu bar). `--once`: one poll, exit 0 with nothing printed when
      nothing happened
  spawn --runner R --pr N --name S --prompt-file F [--url U] [--cwd W] [--fresh]
      open a review session for PR N with the prompt read from F → `{"pr","id","open"}`; the PR
      already has one ⇒ resume it (`"resumed":true`; a `"warning"` when the platform started a copy);
      all `max_concurrent` slots busy, or that PR's session still running ⇒ `{"pr","queued":true}`.
      The session runs in W (default the repo dir), recorded so a resume runs there again.
      `--fresh`: open a new session even when the PR has one; the old one is left untouched and
      untracked. U (the PR URL) is kept for the menu bar. Takes N off the hidden list
  status [--pr N]
      per session `{"pr","runner","id","state","open"}`, state one of working|question|draft|posted|
      lgtm_chat|failed|stopped (`"note"` says why when the session left no status file); a finished
      session shows its result with `"finished":true`, a hidden one `"hidden":true`
  next
      a slot is free ⇒ pop the first queued PR whose session is not running → `{"pr","runner",
      "name","prompt_file"[,"cwd"][,"fresh"]}`, to pass back to spawn; else nothing
  forget --pr N
      drop the PR's session, so the next spawn opens a fresh one
  hide --pr N
      leave PR N out of the menu bar until the next spawn for it → `{"pr","hidden":true}`
  paths [--pr N]
      `dir=…` `prompts=…` lines; with `--pr` also `status_file=…` (the review session writes it)
      and `log=…`
  notify --event E --text-file F [--pr N] [--url U] [--focus pr|watcher|session]
      toast titled `open-pr · <owner>/<repo>`: F line 1 = summary, line 2 = detail; E one of
      review_started|question|draft_ready|posted|re_review|error. Skipped (`"sent":false` + reason) when
      `watch_review.notify.E` is false, or while snoozed (see snooze). Each one not disabled joins
      `feed.jsonl` (last 50). macOS: drawn by open-pr-toast.js (no Notifications permission; hover
      holds it, toasts stack, `1h` snoozes), else notify-send, else stderr. A click goes where
      `--focus` says: `pr` (default) opens U; `watcher` brings the watcher's terminal tab forward;
      `session` opens PR N's session in the watcher's terminal app (no valid open command ⇒ as
      `watcher`); a watcher in an unknown terminal ⇒ opens U
  snooze --for D | --until T | --off
      no toasts on this machine, every repo, for D (30m, 1h, 2h30m) or until T (ISO-8601);
      `--off` resumes → `{"snooze_until"}` (UTC, or null). Shared with the toast and the menu bar
  poll --seconds N | --off
      this machine's poll interval, every repo, min 15 s, over `poll_interval_seconds`; a running
      wait applies it within 5 s. `--off` returns to the setting → `{"poll_seconds"}`. Menu bar too
  menubar [--close]
      macOS: start the menu bar item (active reviews grouped by watcher tab, recent toasts, snooze;
      "Remove from list" on a PR runs `hide`) unless it runs →
      `started` | `running`; it stays until closed. `--close` → `closed` | `not running`. Elsewhere
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
  10 another `wait` already watches this repo on this machine — the message names its pid
  11 `wait` found `stop` in the repo's state dir (the menu bar's "Stop watcher"); it consumes the
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
    paths)   cmd_paths "$@" ;;
    notify)  cmd_notify "$@" ;;
    trust)   cmd_trust "$@" ;;
    snooze)  cmd_snooze "$@" ;;
    poll)    cmd_poll "$@" ;;
    menubar) cmd_menubar "$@" ;;
    *) die 1 "open-pr-watch.sh: unknown subcommand: $sub (see --help)" ;;
esac
