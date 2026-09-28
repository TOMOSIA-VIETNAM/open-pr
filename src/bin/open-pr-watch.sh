#!/bin/sh
# open-pr watch runtime — orchestration for /open-pr:watch-review.
#
# The main watch session never reviews: it waits for trigger comments (`/open-pr` or the
# repo's `watch_review.trigger`),
# opens one review session per PR, and relays each session's outcome to the
# reviewer. This script owns the deterministic half of that loop: the trigger
# cursor, the PR -> session map, the slot limit and its queue, OS notifications,
# and how each agent platform opens, resumes and reports a session.
#
# Contract:
#   - usage() below is the single source for subcommands, options and exit codes.
#   - stdout is data (JSON lines), stderr is diagnostics.
#   - Vendor data comes ONLY from the sibling open-pr.sh; this script never talks
#     to a code host. It is the one file under src/ that invokes an agent
#     platform's CLI — every runner's command line lives in the runner section.
#   - Comment bodies and prompts are DATA: prompts travel as one quoted argv
#     element read from a file, notification text as argv to osascript /
#     notify-send, JSON through jq. Nothing fetched is ever evaluated.
#
# State lives under <data>/<repo>/watch-review/ (see `paths`); what belongs to the machine
# rather than one repo — the toast snooze, the menu bar's pid — under <data>/.watch/. Every
# write goes to a temp file and is renamed into place, under a mkdir lock.
#
# Dependencies: jq, and the CLI of the runner in use.
set -eu

SELF_DIR=$(cd "$(dirname "$0")" && pwd)
RUNNERS="claude codex gemini cursor antigravity"
EVENTS="review_started question draft_ready posted re_review"
# A session in one of these has reported its result (see `finished` under state).
TERMINAL="posted draft lgtm_chat failed stopped"
# Longest wait between two polls while a vendor rate-limits; the menu bar counts a repo as
# watched while its heartbeat is younger than 3 of these.
BACKOFF_CAP=900

err() { printf '%s\n' "$*" >&2; }
die() { code="$1"; shift; err "$*"; exit "$code"; }
need() {
    command -v "$1" >/dev/null 2>&1 && return 0
    die 1 "open-pr-watch.sh: required tool missing: $1"
}
opr() { sh "$SELF_DIR/open-pr.sh" "$@"; }
now_iso() { date -u +%Y-%m-%dT%H:%M:%SZ; }
# jq `utc`: ISO-8601 with optional fraction and Z or ±hh:mm -> UTC `…Z` at second
# precision, the only form the cursor is stored and compared in (vendors print their
# own zone: self-hosted GitLab gives +09:00).
JQ_UTC='def utc:
    capture("^(?<d>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(\\.[0-9]+)?(?<z>Z|[+-][0-9]{2}:?[0-9]{2})$") as $c
    | ($c.d + "Z" | fromdateiso8601)
      - (if $c.z == "Z" then 0 else ($c.z | capture("(?<s>[+-])(?<h>[0-9]{2}):?(?<m>[0-9]{2})")
            | (if .s == "+" then 1 else -1 end) * ((.h | tonumber) * 3600 + (.m | tonumber) * 60)) end)
    | todate;'
# Sub-second sleep where the platform has it; POSIX only promises integers.
nap() { sleep 0.2 2>/dev/null || sleep 1; }

# ---------------------------------------------------------------- args ----
# --key value pairs into ARG_<KEY> (dashes -> _); --once and --off are the bare flags.
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --once) ARG_once=1; shift ;;
            --off) ARG_off=1; shift ;;
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
# D = repo dir (default cwd), REPO/OWNER/VENDOR/HOST from its git remote,
# SD = the watch state directory. `<data>` unset ⇒ exit 7 passes through.
load_repo() {
    D=$(arg repo_dir); [ -n "$D" ] || D=.
    [ -d "$D" ] || die 1 "open-pr-watch.sh: no such directory: $D"
    D=$(cd "$D" && pwd)
    RM=$(arg remote)
    if [ -n "$RM" ]; then rt=$(opr repo-target --repo-dir "$D" --remote "$RM") || exit $?
    else rt=$(opr repo-target --repo-dir "$D") || exit $?; fi
    VENDOR=$(printf '%s\n' "$rt" | sed -n 's/^vendor=//p')
    OWNER=$(printf '%s\n' "$rt" | sed -n 's/^owner=//p')
    REPO=$(printf '%s\n' "$rt" | sed -n 's/^repo=//p')
    HOST=$(printf '%s\n' "$rt" | sed -n 's/^host=//p')
    check_ident '^[A-Za-z0-9_.-]+$' "$REPO"
    data=$(opr data-dir) || exit $?
    SD="$data/$REPO/watch-review"
    STATE="$SD/state.json"
    mkdir -p "$SD/prompts"
    # Watch state and prompts (they quote PR comments) stay out of the review-memory repo.
    grep -qx 'watch-review/' "$data/.gitignore" 2>/dev/null || printf 'watch-review/\n' >> "$data/.gitignore"
}
# WD = <data>/.watch, the machine-wide half of the state; DATA = <data>.
watch_dir() {
    DATA=$(opr data-dir) || exit $?
    WD="$DATA/.watch"
    mkdir -p "$WD"
    grep -qx '.watch/' "$DATA/.gitignore" 2>/dev/null || printf '.watch/\n' >> "$DATA/.gitignore"
}
status_file() { printf '%s/pr-%s.status.json' "$SD" "$1"; }
log_file() { printf '%s/pr-%s.log' "$SD" "$1"; }

# ------------------------------------------------------------ settings ----
SETTINGS=""
settings() {
    [ -n "$SETTINGS" ] || SETTINGS=$(opr settings --repo "$REPO") || exit $?
    printf '%s' "$SETTINGS"
}
# A positive integer from .watch_review.<key>, else the default.
setting_int() {
    v=$(settings | jq -r --arg k "$1" '.watch_review[$k] // empty | select(type == "number" and . >= 1) | floor')
    printf '%s' "${v:-$2}"
}

# --------------------------------------------------------------- state ----
# state.json:
#   cursor    newest processed comment created_at, normalized to second precision
#   seen      comment ids at exactly that created_at (ties the cursor cannot order)
#   sessions  { "<pr>": {runner,id,session_id,name,repo,url,open,pid,started_at,last_state,finished} }
#             finished = its result (a TERMINAL state) was delivered by `wait`: the session is
#             the user's now, reports nothing more and holds no slot until spawn resumes it
#   queue     [ {pr,runner,name,prompt_file} ] waiting for a free slot
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
# state_update <jq args…> <program>: rewrite state.json atomically. jq output
# lands in a temp file first — a failed jq never truncates the state.
state_update() {
    state_json > "$TMPD/state.in"
    jq "$@" "$TMPD/state.in" > "$STATE.tmp" || die 1 "open-pr-watch.sh: state update failed"
    mv "$STATE.tmp" "$STATE"
}
session_field() { state_json | jq -r --arg pr "$1" --arg k "$2" '.sessions[$pr][$k] // empty'; }

# ------------------------------------------------------------- runners ----
# Every platform CLI invocation in the plugin is below. cwd = the repo dir.
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
check_runner() {
    case " $RUNNERS " in *" $1 "*) ;; *) die 1 "open-pr-watch.sh: unknown runner: $1 (valid: $RUNNERS)" ;; esac
}
new_uuid() {
    if command -v uuidgen >/dev/null 2>&1; then uuidgen | tr 'A-Z' 'a-z'
    else od -An -N16 -tx1 /dev/urandom | tr -d ' \n' \
        | sed -E 's/^(.{8})(.{4})(.{4})(.{4})(.{12})$/\1-\2-\3-\4-\5/'; fi
}

# Headless runners: detached, output to pr-<N>.log, PID recorded. The subshell
# execs nohup which execs the CLI, so $! is the CLI's own pid.
bg() {   # $1 log, rest = command
    lg="$1"; shift
    ( cd "$D" || exit 1; exec nohup "$@" ) >> "$lg" 2>&1 < /dev/null &
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
        codex)       bg "$lg" codex exec --json -C "$D" "$3" ;;
        gemini)      RID=$(new_uuid); bg "$lg" gemini -p "$3" --session-id "$RID" -o json ;;
        cursor)
            RID=$( (cd "$D" && agent create-chat) | tr -d '[:space:]') \
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

# claude: an interactive background session the reviewer can attach to.
# `claude --bg` must run OUTSIDE Claude Code's Bash sandbox — started from inside
# it, the session hangs at "starting…". Each call is bounded so a hang surfaces
# as an error instead of a stuck spawn.
run_bounded() {   # $1 seconds, $2 output file, rest = command (cwd = repo dir)
    secs="$1"; out="$2"; shift 2
    ( cd "$D" || exit 1; exec "$@" ) > "$out" 2>&1 < /dev/null &
    p=$!; i=0
    while kill -0 "$p" 2>/dev/null; do
        if [ "$i" -ge $((secs * 5)) ]; then kill "$p" 2>/dev/null || true; wait "$p" 2>/dev/null || true; return 124; fi
        nap; i=$((i + 1))
    done
    wait "$p"
}
claude_list() { (cd "$D" && claude agents --json "$@") 2>/dev/null || printf '[]'; }
claude_sid() {   # id → sessionId; a fresh session may take a moment to list
    i=0
    while [ "$i" -lt 10 ]; do
        s=$(claude_list --all | jq -r --arg id "$1" '.[]? | select(.id == $id) | .sessionId // empty' | head -n 1)
        [ -n "$s" ] && { printf '%s' "$s"; return 0; }
        i=$((i + 1)); nap
    done
}
# `backgrounded · <id> · <name>` → id, colour codes stripped first.
claude_bg_id() {
    esc=$(printf '\033')
    sed "s/${esc}\[[0-9;]*[A-Za-z]//g" "$1" | LC_ALL=C sed -n 's/.*backgrounded · \([A-Za-z0-9_-]*\).*/\1/p' | tail -n 1
}
CLAUDE_HANG="claude --bg did not return within 30s. Started from inside Claude Code's Bash sandbox a background session hangs at starting… — run open-pr-watch.sh outside that sandbox."
# claude refuses a directory whose trust prompt was never accepted THERE — a trusted parent
# does not count. Exit 8, so the caller can tell the reviewer the one command that fixes it.
claude_untrusted() {   # $1 output file
    grep -q 'Workspace not trusted' "$1" || return 0
    die 8 "workspace not trusted: run \`cd $D && claude\` once and accept the trust prompt"
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
# `--bg --resume <sessionId> <prompt>` with no other flag. Resuming a live
# session, or adding a flag, makes the CLI start a copy under a new id.
claude_resume() {   # sets RID SID WARNING; $1 id, $2 session id, $3 prompt
    RID="$1"; SID="$2"
    [ -n "$SID" ] || SID=$(claude_sid "$RID")
    [ -n "$SID" ] || die 1 "no sessionId known for claude session $RID — cannot resume it; forget the PR to start fresh"
    # The session leaves `claude agents --json` the moment `claude stop` returns, but its worker
    # process lingers a little; a resume before that process exits counts as "already running"
    # and starts a copy. So: wait for the listing, then for the pid, and on a copy anyway drop it
    # and retry once.
    for attempt in 1 2; do
        pid=$(claude_list | jq -r --arg id "$RID" 'first(.[]? | select(.id == $id) | .pid // empty) // empty')
        (cd "$D" && claude stop "$RID") > /dev/null 2>&1 || true
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
        [ -z "$copy" ] || { (cd "$D" && claude stop "$copy" && claude rm "$copy") > /dev/null 2>&1 || true; }
        sleep 2
    done
    if grep -q 'started a copy' "$TMPD/claude.out"; then
        new=$(claude_bg_id "$TMPD/claude.out")
        WARNING="claude started a copy instead of resuming $RID; the review now runs in ${new:-an unlisted session}"
        [ -z "$new" ] || { RID="$new"; SID=$(claude_sid "$RID"); }
    fi
}

# -------------------------------------------------------------- status ----
# One JSON line per tracked session: {pr,runner,id,session_id,state,open[,note][,finished]},
# state ∈ working|question|draft|posted|lgtm_chat|failed|stopped. A finished session reads as
# the result it reported, whatever the user does in it since.
from_status_file() {   # $1 pr → the state a review session wrote, else failed
    f=$(status_file "$1")
    s=$(jq -r '.state // empty' "$f" 2>/dev/null || true)
    case "$s" in
        posted|draft|lgtm_chat|failed|question) printf '%s' "$s" ;;
        *) printf 'failed' ;;
    esac
}
status_note() {   # why from_status_file said failed without the file saying so
    f=$(status_file "$1")
    [ -s "$f" ] || { printf 'session ended without writing %s' "$f"; return 0; }
    s=$(jq -r '.state // empty' "$f" 2>/dev/null || true)
    case "$s" in
        posted|draft|lgtm_chat|failed|question) printf '' ;;
        *) printf 'status file holds no known state' ;;
    esac
}
CLAUDE_AGENTS=""
status_one() {   # $1 pr
    pr="$1"
    row=$(state_json | jq -r --arg pr "$pr" '.sessions[$pr] | [.runner, .id, .session_id, .pid, (.finished == true), .last_state] | map(. // "" | tostring) | join("\u001f")')
    # a non-whitespace separator: IFS whitespace would merge the empty fields
    us=$(printf '\037')
    IFS="$us" read -r runner id sid pid fin last <<EOF
$row
EOF
    note=""; inuse=""
    if [ "$fin" = true ]; then
        [ -n "$id" ] || id=$(lazy_id "$runner" "$pr")
        st="$last"
        # Its result is reported, but the user may still be talking in it: a new request
        # must wait for that conversation rather than stop it.
        if [ "$runner" = claude ]; then
            [ -n "$CLAUDE_AGENTS" ] || CLAUDE_AGENTS=$(claude_list --all)
            cs=$(printf '%s' "$CLAUDE_AGENTS" | jq -r --arg id "$id" '[.[]? | select(.id == $id)][0].state // empty' 2>/dev/null || true)
            case "$cs" in working|blocked) inuse=true ;; esac
        elif pid_alive "$pid"; then inuse=true; fi
    elif [ "$runner" = claude ]; then
        [ -n "$CLAUDE_AGENTS" ] || CLAUDE_AGENTS=$(claude_list --all)
        entry=$(printf '%s' "$CLAUDE_AGENTS" | jq -c --arg id "$id" '[.[]? | select(.id == $id)][0] // empty')
        [ -n "$sid" ] || sid=$(printf '%s' "$entry" | jq -r '.sessionId // empty' 2>/dev/null || true)
        cs=$(printf '%s' "$entry" | jq -r '.state // empty' 2>/dev/null || true)
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
        --arg inuse "$inuse" \
        '{pr: $pr, runner: $runner, id: (if $id == "" then null else $id end),
          session_id: (if $sid == "" then null else $sid end), state: $state,
          open: (if $open == "" then null else $open end)}
         + (if $note == "" then {} else {note: $note} end)
         + (if $fin == "true" then {finished: true} else {} end)
         + (if $inuse == "true" then {in_use: true} else {} end)'
}
status_all() {   # JSONL for every tracked session (or just $1)
    CLAUDE_AGENTS=""   # one listing per pass: `wait` polls many times in one process
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
active_count() {   # $1 status JSONL, $2 pr to leave out → sessions holding a slot (a finished one reads terminal)
    jq -s --arg skip "${2:-}" '[.[] | select((.pr | tostring) != $skip and (.state == "working" or .state == "question"))] | length' "$1"
}

cmd_status() {
    parse_args "$@"
    N=$(arg pr); [ -z "$N" ] || check_ident '^[0-9]+$' "$N"
    load_repo; lock
    status_all "$N" > "$TMPD/status"
    remember_ids "$TMPD/status"
    jq -c '{pr, runner, id, state, open} + (if .note then {note} else {} end) + (if .finished then {finished} else {} end)' "$TMPD/status"
}

# --------------------------------------------------------------- spawn ----
enqueue() {   # $1 pr, $2 reason
    state_update --argjson pr "$1" --arg runner "$RUNNER" --arg name "$NAME" --arg f "$PF" \
        '.queue = ([.queue[] | select(.pr != $pr)] + [{pr: $pr, runner: $runner, name: $name, prompt_file: $f}])'
    jq -n -c --argjson pr "$1" --arg why "$2" '{pr: $pr, queued: true, reason: $why}'
}
cmd_spawn() {
    parse_args "$@"
    RUNNER=$(req runner); check_runner "$RUNNER"
    N=$(pr_arg); NAME=$(req name); PF=$(req prompt_file); URL=$(arg url)
    [ -r "$PF" ] || die 1 "open-pr-watch.sh: prompt file not readable: $PF"
    PF=$(cd "$(dirname "$PF")" && printf '%s/%s' "$(pwd)" "$(basename "$PF")")
    load_repo
    case "$RUNNER" in claude) need claude ;; codex) need codex ;; gemini) need gemini ;; cursor) need agent ;; antigravity) need agy ;; esac
    lock
    max=$(setting_int max_concurrent 5)
    status_all > "$TMPD/status"
    remember_ids "$TMPD/status"
    have=$(session_field "$N" runner)
    if [ -n "$have" ] && [ "$have" != "$RUNNER" ]; then
        die 1 "open-pr-watch.sh: PR $N already has a $have session; forget it first to open one under $RUNNER"
    fi
    if [ -n "$have" ]; then
        cur=$(jq -r --argjson pr "$N" 'select(.pr == $pr) | .state' "$TMPD/status")
        inuse=$(jq -r --argjson pr "$N" 'select(.pr == $pr) | .in_use // false' "$TMPD/status")
        # A review still running finishes first, and a conversation the user is having in
        # a finished session is never cut: the re-review waits its turn (`wait` says `ready`).
        [ "$cur" != working ] || { enqueue "$N" "session still running"; return 0; }
        [ "$inuse" != true ] || { enqueue "$N" "session in use"; return 0; }
    fi
    [ "$(active_count "$TMPD/status" "$N")" -lt "$max" ] || { enqueue "$N" "all $max slots busy"; return 0; }

    PROMPT=$(cat "$PF")
    rm -f "$(status_file "$N")"
    RID=""; SID=""; PID=""; WARNING=""; resumed=false
    if [ -n "$have" ]; then
        resumed=true
        RID=$(session_field "$N" id); SID=$(session_field "$N" session_id)
        if [ "$RUNNER" = claude ]; then
            claude_resume "$RID" "$SID" "$PROMPT"
        else
            [ -n "$RID" ] || RID=$(lazy_id "$RUNNER" "$N")
            [ -n "$RID" ] || die 1 "open-pr-watch.sh: no $RUNNER session id recorded for PR $N — forget it to start fresh"
            headless_resume "$RUNNER" "$N" "$RID" "$PROMPT"
        fi
    else
        if [ "$RUNNER" = claude ]; then claude_launch "$NAME" "$PROMPT"
        else headless_launch "$RUNNER" "$N" "$PROMPT"; fi
    fi
    state_update --arg pr "$N" --arg runner "$RUNNER" --arg id "$RID" --arg sid "$SID" \
        --arg name "$NAME" --arg pid "$PID" --arg at "$(now_iso)" --arg repo "$OWNER/$REPO" \
        --arg url "$URL" --arg open "$(open_cmd "$RUNNER" "$RID")" \
        'def nul: if . == "" then null else . end;
         .sessions[$pr] = {runner: $runner, id: ($id | nul), session_id: ($sid | nul), name: $name,
                           repo: $repo, url: (($url | nul) // .sessions[$pr].url), open: ($open | nul),
                           pid: ($pid | nul | if . then tonumber else . end), started_at: $at,
                           last_state: "working", finished: false}
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
    # First entry whose PR has no session still running — that one keeps its place.
    busy=$(jq -s -c '[.[] | select(.state == "working" or .in_use == true) | .pr]' "$TMPD/status")
    pick=$(state_json | jq -c --argjson busy "$busy" '[.queue[] | select(.pr as $p | $busy | index($p) | not)][0] // empty')
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
cmd_paths() {
    parse_args "$@"
    N=$(arg pr); [ -z "$N" ] || check_ident '^[0-9]+$' "$N"
    load_repo
    printf 'dir=%s\nprompts=%s/prompts\n' "$SD" "$SD"
    [ -z "$N" ] || printf 'status_file=%s\nlog=%s\n' "$(status_file "$N")" "$(log_file "$N")"
}

# ---------------------------------------------------------------- wait ----
# The trigger token from `watch_review.trigger`; "@me" = a mention of the account the
# watcher is logged in as. open-pr.sh triggers validates whatever this returns.
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
# Delivery rule: a batch of events counts as delivered only when `wait` exits 0.
# The batch is printed first and the state that marks it processed (cursor,
# seen ids, last session states) is renamed into place right after, then the
# process exits. Killed before that rename, the next `wait` prints the same
# batch again — the caller acts only on a `wait` that exited 0, so a comment is
# neither lost nor handled twice.
poll_once() {   # GOT=1 when events were printed and committed; LIMITED=1 when the vendor rate-limited
    GOT=""; LIMITED=""
    touch "$SD/heartbeat"   # the menu bar's proof that this repo is still watched
    lock
    cursor=$(state_json | jq -r "$JQ_UTC"' .cursor // empty | utc')
    if [ -z "$cursor" ]; then
        # First run: history before now is never replayed.
        state_update --arg c "$(now_iso)" '.cursor = $c | .seen = []'
        unlock; return 0
    fi
    # A cursor stored with an offset is rewritten in UTC, so every step below compares like with like.
    [ "$cursor" = "$(state_json | jq -r '.cursor')" ] || state_update --arg c "$cursor" '.cursor = $c'
    unlock
    # triggers' --since is strict and the cursor has second precision: ask from
    # one second earlier so a comment in the cursor's own second still arrives;
    # the filter below drops the ones already processed.
    since=$(jq -n -r --arg c "$cursor" '$c | fromdateiso8601 - 1 | todateiso8601')
    [ -n "$TOKEN" ] || TOKEN=$(trigger_token)
    rc=0
    opr triggers --vendor "$VENDOR" --owner "$OWNER" --repo "$REPO" ${HOST:+--host "$HOST"} \
        --since "$since" --mark-file "$TMPD/mark" --token "$TOKEN" > "$TMPD/triggers" 2> "$TMPD/triggers.err" || rc=$?
    if [ "$rc" = 9 ] && [ -z "$(arg once)" ]; then LIMITED=1; return 0; fi
    cat "$TMPD/triggers.err" >&2
    if [ "$rc" != 0 ]; then
        err "open-pr-watch.sh: triggers failed (exit $rc); retrying next poll"
        [ -z "$(arg once)" ] || exit "$rc"
        return 0
    fi
    lock
    state_json > "$TMPD/state.in"
    # Vendors print created_at with or without fractions; compare at second
    # precision and let `seen` order the ties.
    jq -c -s --slurpfile st "$TMPD/state.in" "$JQ_UTC"'
        ($st[0].cursor) as $cur | ($st[0].seen // []) as $seen
        | map(select(type == "object") | . + {_k: (.created_at | utc)})
        | map(select(._k > $cur or (._k == $cur and ((.comment_id | tostring) as $c | $seen | index([$c]) | not))))
        | reduce .[] as $t ([]; if any(.[]; .comment_id == $t.comment_id) then . else . + [$t] end)
        | sort_by(._k)[]' "$TMPD/triggers" > "$TMPD/new"
    status_all > "$TMPD/status"
    # Session events: state changed since the last one delivered.
    jq -c -s --slurpfile st "$TMPD/state.in" '
        .[] | select(.state != ($st[0].sessions[(.pr | tostring)].last_state // null))
        | {event: "session", pr, state, open} + (if .note then {note} else {} end)' "$TMPD/status" > "$TMPD/sess"
    # A queued PR whose turn has come (a slot free, its session neither running nor in
    # use): `ready`, so the watcher runs `next` — nothing else would wake it.
    max=$(setting_int max_concurrent 5)
    jq -c -s --slurpfile st "$TMPD/state.in" --argjson max "$max" '
        . as $s
        | ([$s[] | select(.finished != true and (.state == "working" or .state == "question"))] | length) as $active
        | [$s[] | select(.state == "working" or .in_use == true) | .pr] as $busy
        | if $active < $max then
              ([$st[0].queue[]? | select(.pr as $p | $busy | index($p) | not)][0] // empty)
              | {event: "ready", pr}
          else empty end' "$TMPD/status" > "$TMPD/ready"
    # The cursor also moves to the newest comment fetched, trigger or not: a quiet repo
    # would otherwise re-fetch everything since the watcher started, every poll.
    mark=$(cat "$TMPD/mark" 2>/dev/null || true)
    if [ ! -s "$TMPD/new" ] && [ ! -s "$TMPD/sess" ] && [ ! -s "$TMPD/ready" ]; then
        remember_ids "$TMPD/status"
        [ -z "$mark" ] || state_update --arg m "$mark" \
            'if $m > .cursor then .cursor = $m | .seen = [] else . end'
        unlock; return 0
    fi
    jq -c --slurpfile new "$TMPD/new" --slurpfile status "$TMPD/status" --arg m "$mark" --arg terminal "$TERMINAL" '
        ([.cursor, $m] + [$new[]._k] | map(select(. != "")) | max) as $c
        | .seen = (if $c == .cursor then (.seen // []) else [] end
                   + [$new[] | select(._k == $c) | .comment_id | tostring] | unique)
        | .cursor = $c
        | ($terminal | split(" ")) as $done
        | reduce $status[] as $s (.; if .sessions[($s.pr | tostring)] then
              .sessions[($s.pr | tostring)] |= (.last_state = $s.state | .id = (.id // $s.id)
                                                | .session_id = (.session_id // $s.session_id)
                                                | .open = (.open // $s.open)
                                                | if any($done[]; . == $s.state) then .finished = true else . end)
          else . end)' "$TMPD/state.in" > "$STATE.tmp" || die 1 "open-pr-watch.sh: state update failed"
    # `repo` names the watched repo: one watcher may run a `wait` per repo.
    { jq -c '{event: "trigger"} + del(._k)' "$TMPD/new"; cat "$TMPD/sess" "$TMPD/ready"; } \
        | jq -c --arg r "$OWNER/$REPO" '{event, repo: $r} + del(.event)' > "$TMPD/events"
    cat "$TMPD/events"
    mv "$STATE.tmp" "$STATE"
    unlock
    GOT=1
}
cmd_wait() {
    parse_args "$@"
    load_repo
    interval=$(setting_int poll_interval_seconds 60); delay=$interval
    while :; do
        # Not an `if` condition: set -e must still stop on a failed step inside.
        poll_once
        [ -z "$GOT" ] || return 0
        [ -z "$(arg once)" ] || return 0
        # A rate limit doubles the wait (up to BACKOFF_CAP); the next good poll resets it.
        if [ -n "$LIMITED" ]; then
            delay=$((delay * 2))
            [ "$delay" -le "$BACKOFF_CAP" ] || delay=$BACKOFF_CAP
            [ "$delay" -ge "$interval" ] || delay=$interval
            err "rate limited — next poll in ${delay}s"
        else
            delay=$interval
        fi
        sleep "$delay"
    done
}

# -------------------------------------------------------------- notify ----
cmd_notify() {
    parse_args "$@"
    E=$(req event); F=$(req text_file)
    case " $EVENTS " in *" $E "*) ;; *) die 1 "open-pr-watch.sh: unknown event: $E (valid: $EVENTS)" ;; esac
    [ -r "$F" ] || die 1 "open-pr-watch.sh: text file not readable: $F"
    P=$(arg pr); [ -z "$P" ] || check_ident '^[0-9]+$' "$P"
    load_repo; watch_dir
    off=$(settings | jq -r --arg e "$E" '(.watch_review.notify // {}) as $n
        | if ($n | has($e)) and $n[$e] == false then "yes" else "" end')
    if [ -n "$off" ]; then
        jq -n -c --arg e "$E" '{event: $e, sent: false, reason: "event disabled"}'
        return 0
    fi
    # F: line 1 = the summary ("Reviewing PR #12"), line 2 = a detail (the open command).
    title="open-pr · $OWNER/$REPO"
    summary=$(sed -n 1p "$F"); detail=$(sed -n 2p "$F")
    feed_add
    if snoozed; then
        jq -n -c --arg e "$E" '{event: $e, sent: false, reason: "snoozed"}'
        return 0
    fi
    # Title and text reach the notifier as argv only — never spliced into source or a shell string.
    if command -v osascript >/dev/null 2>&1; then
        # macOS: a toast this plugin draws itself (open-pr-toast.js), detached so the watcher
        # never waits on it. Each toast holds a slot (a directory naming its pid) until it
        # exits, so a new one takes the first free place in the stack and never covers a
        # toast still showing.
        via=toast
        sd="${TMPDIR:-/tmp}/open-pr-toast"; mkdir -p "$sd"; slot=0
        while [ "$slot" -lt 8 ]; do
            if mkdir "$sd/$slot" 2>/dev/null; then break; fi
            pid=$(cat "$sd/$slot/pid" 2>/dev/null || true)
            # stale: its toast exited, or a notify died before writing the pid (> 1 min ago)
            if { [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; } \
                || { [ -z "$pid" ] && [ -n "$(find "$sd/$slot" -maxdepth 0 -mmin +1 2>/dev/null)" ]; }; then
                rm -rf "$sd/$slot"; mkdir "$sd/$slot" 2>/dev/null && break
            fi
            slot=$((slot + 1))
        done
        [ "$slot" -lt 8 ] || slot=0
        nohup osascript -l JavaScript "$SELF_DIR/open-pr-toast.js" "$title" "$summary" "$detail" \
            "$E" "$slot" 8 "$(arg url)" "$WD/snooze_until" > /dev/null 2>&1 &
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
# <data>/.watch/snooze_until: one ISO-8601 line; absent, unreadable or past = not snoozed.
snoozed() {
    su=$(head -n 1 "$WD/snooze_until" 2>/dev/null || true)
    [ -n "$su" ] && jq -e -n --arg s "$su" "$JQ_UTC"'(try ($s | utc | fromdateiso8601) catch 0) > now' > /dev/null
}
# feed.jsonl: the last FEED_MAX notifications of this repo, sent or snoozed, oldest first —
# what the menu bar lists as recent. Rewritten whole and renamed, so a reader never sees half.
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
# macOS menu bar item (open-pr-menubar.js), one per machine: it reads every repo's state
# files itself and leaves once no repo has been watched for a while, removing its pid file.
cmd_menubar() {
    parse_args "$@"
    command -v osascript >/dev/null 2>&1 || { printf 'NO-EQUIVALENT\n'; return 0; }
    watch_dir
    lock "$WD/.lock"
    pf="$WD/menubar.pid"
    pid=$(cat "$pf" 2>/dev/null || true)
    # a live pid counts only while it is still the menu bar: pids get reused
    if printf '%s' "$pid" | grep -Eq '^[0-9]+$' && kill -0 "$pid" 2>/dev/null \
        && ps -p "$pid" -o command= 2>/dev/null | grep -q 'open-pr-menubar\.js'; then
        printf 'running\n'
        return 0
    fi
    nohup osascript -l JavaScript "$SELF_DIR/open-pr-menubar.js" "$DATA" "$WD/snooze_until" "$pf" \
        "$((3 * BACKOFF_CAP))" > /dev/null 2>&1 < /dev/null &
    printf '%s\n' "$!" > "$pf"
    printf 'started\n'
}

# --------------------------------------------------------------- trust ----
# Whether the runner will open a session in the repo dir without asking first. Read-only:
# the trust prompt is the user's to accept, never this script's to write.
cmd_trust() {
    parse_args "$@"
    RUNNER=$(req runner); check_runner "$RUNNER"
    D=$(arg repo_dir); [ -n "$D" ] || D=.
    [ -d "$D" ] || die 1 "open-pr-watch.sh: no such directory: $D"
    D=$(cd "$D" && pwd)
    [ "$RUNNER" = claude ] || { printf 'n/a\n'; return 0; }
    # trust is recorded per exact directory: a trusted parent does not cover its children
    cf="${OPEN_PR_CLAUDE_CONFIG:-${HOME:-}/.claude.json}"
    # judged by what jq printed: some jq builds exit 0 on a parse error, printing nothing
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
  `<data>/<repo>/watch-review/` (`snooze`, `menubar`: no repo; machine state in `<data>/.watch/`).
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
      each time) until a poll succeeds. Every poll touches `heartbeat`. `--once`: one poll, exit 0
      with nothing printed when nothing happened
  spawn --runner R --pr N --name S --prompt-file F [--url U]
      open a review session for PR N with the prompt read from F → `{"pr","id","open"}`; the PR
      already has one ⇒ resume it (`"resumed":true`; a `"warning"` when the platform started a copy);
      all `max_concurrent` slots busy, or that PR's session still running ⇒ `{"pr","queued":true}`.
      U (the PR URL) is kept for the menu bar
  status [--pr N]
      per session `{"pr","runner","id","state","open"}`, state one of working|question|draft|posted|
      lgtm_chat|failed|stopped (`"note"` says why when the session left no status file); a finished
      session shows its result with `"finished":true`
  next
      a slot is free ⇒ pop the first queued PR whose session is not running → `{"pr","runner",
      "name","prompt_file"}`, to pass back to spawn; else nothing
  forget --pr N
      drop the PR's session, so the next spawn opens a fresh one
  paths [--pr N]
      `dir=…` `prompts=…` lines; with `--pr` also `status_file=…` (the review session writes it)
      and `log=…`
  notify --event E --text-file F [--pr N] [--url U]
      toast titled `open-pr · <owner>/<repo>`: F line 1 = summary, line 2 = detail; E one of
      review_started|question|draft_ready|posted|re_review. Skipped (`"sent":false` + reason) when
      `watch_review.notify.E` is false, or while snoozed (see snooze). Each one not disabled joins
      `feed.jsonl` (last 50). macOS: drawn by open-pr-toast.js (no Notifications permission; click
      opens U, hover holds it, toasts stack, `1h` snoozes), else notify-send, else stderr
  snooze --for D | --until T | --off
      no toasts on this machine, every repo, for D (30m, 1h, 2h30m) or until T (ISO-8601);
      `--off` resumes → `{"snooze_until"}` (UTC, or null). Shared with the toast and the menu bar
  menubar
      macOS: start the menu bar item (active reviews, recent toasts, snooze) unless it runs →
      `started` | `running`; it leaves by itself 5 min after the last watched repo stops. Elsewhere
      `NO-EQUIVALENT`. Plain lines
  trust --runner R
      will R open a session in the repo dir without a prompt? claude: `trusted` | `untrusted` plus
      a `run: cd <dir> && claude` line (trust is per exact directory, a trusted parent does not
      count) | `unknown` (its config unreadable); other runners: `n/a`. Plain lines, read-only

Runners (`--runner`): claude, codex, gemini, cursor, antigravity.

Exit codes:
  0  ok
  1  other
  4  invalid value
  7  `<data>` not set
  8  the runner refuses the repo dir as untrusted — the message names the command to run once
  9  `wait --once` hit a vendor rate limit
EOF
}

case "${1:-}" in -h|--help) usage; exit 0 ;; esac
need jq

TMPD=$(mktemp -d "${TMPDIR:-/tmp}/open-pr-watch.XXXXXX")
trap 'unlock; rm -rf "$TMPD"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

sub="${1:-}"; [ -n "$sub" ] && shift || die 1 "open-pr-watch.sh: no subcommand (see --help)"
case "$sub" in
    wait)    cmd_wait "$@" ;;
    spawn)   cmd_spawn "$@" ;;
    status)  cmd_status "$@" ;;
    next)    cmd_next "$@" ;;
    forget)  cmd_forget "$@" ;;
    paths)   cmd_paths "$@" ;;
    notify)  cmd_notify "$@" ;;
    trust)   cmd_trust "$@" ;;
    snooze)  cmd_snooze "$@" ;;
    menubar) cmd_menubar "$@" ;;
    *) die 1 "open-pr-watch.sh: unknown subcommand: $sub (see --help)" ;;
esac
