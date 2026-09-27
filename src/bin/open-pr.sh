#!/bin/sh
# open-pr runtime CLI — the deterministic half of the plugin.
#
# The prompt files under src/ decide WHAT to review and WHAT to say; this script
# performs every vendor/git mechanic they used to spell out: fetching PR context,
# checking out the PR head, gating the tree against the head SHA, confirming line
# numbers, and posting through each vendor's own publish flow.
#
# Contract:
#   - usage() below is the single source for subcommands, options and exit codes;
#     src/core/cli.md mirrors it (scripts/cli_doc.py --write regenerates the copy).
#   - stdout is data, stderr is diagnostics; exit codes are part of the interface.
#   - PR content (title/body/diff/comments) passes through as DATA only — this
#     script never evaluates or expands it. All request payloads travel via files
#     or jq-built JSON, never through shell interpolation.
#
# Dependencies: git, jq, curl, and the vendor CLI the target uses (gh or glab).
set -eu

err() { printf '%s\n' "$*" >&2; }
die() { code="$1"; shift; err "$*"; exit "$code"; }
need() {
    command -v "$1" >/dev/null 2>&1 && return 0
    die 1 "open-pr.sh: required tool missing: $1. Install it and call the run again — jq: winget install jqlang.jq (Windows) / brew install jq (macOS) / apt install jq (Debian-Ubuntu); gh: https://cli.github.com; glab: https://gitlab.com/gitlab-org/cli."
}

# ---------------------------------------------------------------- args ----
# Parsed by every subcommand: --key value pairs into ARG_<KEY> (dashes -> _).
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --*)
                key=$(printf '%s' "${1#--}" | tr '-' '_')
                [ $# -ge 2 ] || die 1 "open-pr.sh: $1 needs a value"
                eval "ARG_${key}=\$2"
                shift 2 ;;
            *) die 1 "open-pr.sh: unexpected argument: $1" ;;
        esac
    done
}
arg() { eval "printf '%s' \"\${ARG_$1:-}\""; }
req() { v=$(arg "$1"); [ -n "$v" ] || die 1 "open-pr.sh: --$(printf '%s' "$1" | tr '_' '-') is required"; printf '%s' "$v"; }

# Validated identifier: owner/repo/branch/path fragments that enter commands.
check_ident() { printf '%s' "$2" | grep -Eq "$1" || die 4 "open-pr.sh: invalid value: $2"; }

# ------------------------------------------------------------- bitbucket ----
BB_API=""
BB_AUTH_KIND=""
bb_init() {
    o="$1"; r="$2"
    BB_API="https://api.bitbucket.org/2.0/repositories/$o/$r"
    umask 077
    if [ -n "${BITBUCKET_EMAIL:-}" ] && [ -n "${BITBUCKET_API_TOKEN:-}" ]; then
        printf 'user = "%s:%s"\n' "$BITBUCKET_EMAIL" "$BITBUCKET_API_TOKEN" > "$TMPD/bb.curlrc"
        BB_AUTH_KIND=user
    elif [ -n "${BITBUCKET_TOKEN:-}" ]; then
        printf 'header = "Authorization: Bearer %s"\n' "$BITBUCKET_TOKEN" > "$TMPD/bb.curlrc"
        BB_AUTH_KIND=bearer
    else
        die 6 "Bitbucket credentials missing. Set BITBUCKET_EMAIL + BITBUCKET_API_TOKEN (an Atlassian API token from account settings -> Security -> API tokens, app: Bitbucket, scopes read:pullrequest:bitbucket + write:pullrequest:bitbucket + read:account), or BITBUCKET_TOKEN (a repository/workspace access token). Put them in the env block of ~/.claude/settings.json. Never paste a token into chat."
    fi
}
# The credential travels via curl's own config file, never argv — argv is readable
# through `ps` by any user on the machine.
bb_curl() { curl -sS --fail-with-body --config "$TMPD/bb.curlrc" "$@"; }
# Walk every page of {values,next}. $1=url $2=jq program (run per page, raw out).
bb_paged() {
    next="$1"
    while [ -n "$next" ]; do
        page=$(bb_curl -L "$next") || { err "paged: $page"; return 1; }
        printf '%s' "$page" | jq -r "$2"
        next=$(printf '%s' "$page" | jq -r '.next // empty')
    done
}
# One whole-diff fetch, cached per run: sizes and patch cut it at diff --git.
bb_diff_cached() {
    if [ ! -s "$TMPD/bb.diff" ]; then
        bb_curl -L "$BB_API/pullrequests/$1/diff" > "$TMPD/bb.diff"
    fi
    cat "$TMPD/bb.diff"
}

# ------------------------------------------------------------- gitlab ----
GL_PROJ=""
gl_init() { GL_PROJ="$1%2F$2"; need glab; }
gl_mr_cached() {   # the base MR object, one fetch per run
    if [ ! -s "$TMPD/gl.mr" ]; then
        glab api "projects/$GL_PROJ/merge_requests/$1" > "$TMPD/gl.mr"
    fi
    cat "$TMPD/gl.mr"
}
gl_changes_cached() {
    if [ ! -s "$TMPD/gl.changes" ]; then
        glab api "projects/$GL_PROJ/merge_requests/$1/changes" > "$TMPD/gl.changes"
    fi
    cat "$TMPD/gl.changes"
}
gl_discussions_cached() {
    if [ ! -s "$TMPD/gl.disc" ]; then
        glab api --paginate "projects/$GL_PROJ/merge_requests/$1/discussions" > "$TMPD/gl.disc"
    fi
    cat "$TMPD/gl.disc"
}

# -------------------------------------------------------------- target ----
# target <url> -> vendor/owner/repo/pull_number/host, or exit 4.
cmd_target() {
    url="${1:-}"; [ -n "$url" ] || die 4 "open-pr.sh target: no URL"
    stripped=$(printf '%s' "$url" | sed -E 's~[?#].*$~~; s~/(files|changes)/?$~~; s~/$~~')
    vendor=""; owner=""; repo=""; n=""
    if printf '%s' "$stripped" | grep -Eq '^https://github\.com/[^/]+/[^/]+/pull/[0-9]+$'; then
        vendor=github
        owner=$(printf '%s' "$stripped" | cut -d/ -f4); repo=$(printf '%s' "$stripped" | cut -d/ -f5)
        n=$(printf '%s' "$stripped" | cut -d/ -f7)
    elif printf '%s' "$stripped" | grep -Eq '^https://[^/]+/[^/]+/[^/]+/-/merge_requests/[0-9]+$'; then
        vendor=gitlab
        owner=$(printf '%s' "$stripped" | cut -d/ -f4); repo=$(printf '%s' "$stripped" | cut -d/ -f5)
        n=$(printf '%s' "$stripped" | cut -d/ -f8)
    elif printf '%s' "$stripped" | grep -Eq '^https://bitbucket\.org/[^/]+/[^/]+/pull-requests/[0-9]+$'; then
        vendor=bitbucket
        owner=$(printf '%s' "$stripped" | cut -d/ -f4); repo=$(printf '%s' "$stripped" | cut -d/ -f5)
        n=$(printf '%s' "$stripped" | cut -d/ -f7)
    else
        die 4 "open-pr.sh target: not a recognized PR/MR URL"
    fi
    check_ident '^[A-Za-z0-9_.-]+$' "$owner"; check_ident '^[A-Za-z0-9_.-]+$' "$repo"
    check_ident '^[0-9]+$' "$n"
    host=$(printf '%s' "$stripped" | cut -d/ -f3)
    printf 'vendor=%s\nowner=%s\nrepo=%s\npull_number=%s\nhost=%s\n' "$vendor" "$owner" "$repo" "$n" "$host"
}

# ------------------------------------------------------------- context ----
# Normalized sections, fixed order. Head SHA is fetched BEFORE the diff and the
# size list before the patch — the gate downstream depends on that order.
section() { printf '## %s\n' "$1"; }

ctx_info() {
    case "$V" in
        github) gh pr view "$URL" -R "$OWNER/$REPO" --json number,title,body,author,baseRefName,headRefName \
                  | jq '{number,title,body,author: .author.login,baseRefName,headRefName}' ;;
        gitlab) gl_mr_cached "$N" | jq '{number: .iid, title, body: .description, author: .author.username, baseRefName: .target_branch, headRefName: .source_branch}' ;;
        bitbucket) bb_curl "$BB_API/pullrequests/$N?fields=id,title,description,author.nickname,source.branch.name,destination.branch.name" \
                  | jq '{number: .id, title, body: .description, author: .author.nickname, baseRefName: .destination.branch.name, headRefName: .source.branch.name}' ;;
    esac
}
ctx_head() {
    case "$V" in
        github) gh pr view "$URL" -R "$OWNER/$REPO" --json headRefOid --jq .headRefOid ;;
        gitlab) gl_mr_cached "$N" | jq -r '.diff_refs.head_sha' ;;
        bitbucket) bb_curl "$BB_API/pullrequests/$N?fields=source.commit.hash" | jq -r '.source.commit.hash' ;;
    esac
}
ctx_files() {
    case "$V" in
        github) gh pr diff "$URL" -R "$OWNER/$REPO" --name-only ;;
        gitlab) gl_changes_cached "$N" | jq -r '.changes[] | if .old_path == .new_path then .new_path else (.old_path // empty), (.new_path // empty) end' | sort -u ;;
        bitbucket) bb_paged "$BB_API/pullrequests/$N/diffstat?pagelen=100&fields=next,values.old.path,values.new.path" \
                  '.values[] | if .old.path == .new.path then .new.path else (.old.path // empty), (.new.path // empty) end' ;;
    esac
}
ctx_sizes() {
    case "$V" in
        github) gh api --paginate "repos/$OWNER/$REPO/pulls/$N/files" --jq '.[] | if .patch == null then "UNKNOWN(no patch — too large/binary/rename) \(.filename)" else "\(.patch|length) \(.filename)" end' ;;
        gitlab) gl_changes_cached "$N" | jq -r '.changes[] | if (.collapsed // false) or (.too_large // false) then "UNKNOWN(collapsed or too large — no patch returned) \(.new_path)" else "\((.diff // "") | length) \(.new_path)" end' ;;
        bitbucket)
            # A binary file, or a diff Bitbucket declines to generate, has NO chunk at all —
            # reading that absence as 0 bytes would slip the largest file under every
            # threshold, so every diffstat path missing from the diff prints UNKNOWN.
            bb_diff_cached "$N" | LC_ALL=C awk '/^diff --git /{if(n)print s" "p; p=substr($0,index($0," b/")+3); s=0; n=1} n{s+=length($0)+1} END{if(n)print s" "p}' > "$TMPD/bb.sizes"
            cat "$TMPD/bb.sizes"
            ctx_files | while IFS= read -r f; do
                grep -qF " $f" "$TMPD/bb.sizes" || printf 'UNKNOWN(no diff chunk — binary or declined) %s\n' "$f"
            done ;;
    esac
}
ctx_diff() {
    m="$MAXPATCH"
    case "$V" in
        github) gh api --paginate "repos/$OWNER/$REPO/pulls/$N/files" --jq ".[] | select((.patch // \"\" | length) < $m) | \"diff --git a/\(.filename) b/\(.filename)\n\(.patch)\"" ;;
        gitlab) gl_changes_cached "$N" | jq -r --argjson m "$m" '.changes[] | select(((.diff // "") | length) < $m and (.diff // "") != "") | "diff --git a/\(.new_path) b/\(.new_path)\n\(.diff)"' ;;
        bitbucket) bb_diff_cached "$N" | LC_ALL=C awk -v m="$m" '/^diff --git /{if(n&&s<m)printf "%s",b; b=""; s=0; n=1} n{b=b $0 "\n"; s+=length($0)+1} END{if(n&&s<m)printf "%s",b}' ;;
    esac
}
ctx_commits() {
    case "$V" in
        github) gh pr view "$URL" -R "$OWNER/$REPO" --json commits --jq '.commits[].messageHeadline' ;;
        gitlab) glab api "projects/$GL_PROJ/merge_requests/$N/commits" | jq -r '.[].title' ;;
        bitbucket) bb_paged "$BB_API/pullrequests/$N/commits?pagelen=100&fields=next,values.message" '.values[].message | split("\n")[0]' ;;
    esac
}
# One line of JSON per LINE-level comment, the same shape on every vendor:
# {id, body, user, path, line, side, in_reply_to}
ctx_comments() {
    case "$V" in
        github) gh api --paginate "repos/$OWNER/$REPO/pulls/$N/comments" \
                  | jq -c '.[] | {id, body, user: .user.login, path, line: (.line // .original_line), side: (.side // "RIGHT"), in_reply_to: (.in_reply_to_id // null)}' ;;
        gitlab) gl_discussions_cached "$N" | jq -c '.[] | .notes as $ns | $ns[0].id as $root | $ns[] | select(.position != null) | {id, body, user: .author.username, path: (.position.new_path // .position.old_path), line: (.position.new_line // .position.old_line), side: (if .position.new_line then "RIGHT" else "LEFT" end), in_reply_to: (if .id == $root then null else $root end)}' ;;
        bitbucket) bb_paged "$BB_API/pullrequests/$N/comments?pagelen=100&fields=next,values.id,values.content.raw,values.user.nickname,values.inline,values.parent.id,values.deleted" \
                  '.values[] | select(.deleted != true and .inline != null) | {id, body: .content.raw, user: .user.nickname, path: .inline.path, line: (.inline.to // .inline.from), side: (if .inline.to then "RIGHT" else "LEFT" end), in_reply_to: (.parent.id // null)} | @json' ;;
    esac
}
ctx_ci() {
    case "$V" in
        github) gh pr checks "$URL" -R "$OWNER/$REPO" --json bucket,name,link --jq '.[] | "\(.bucket) \(.name) — \(.link)"' || true ;;
        gitlab) glab api "projects/$GL_PROJ/merge_requests/$N/pipelines" | jq -r '.[] | "\(if .status == "failed" or .status == "canceled" then "fail" elif .status == "success" then "pass" else "pending" end) pipeline #\(.id) — \(.web_url)"' || true ;;
        bitbucket) bb_paged "$BB_API/pullrequests/$N/statuses?pagelen=100&fields=next,values.state,values.name,values.url" \
                  '.values[] | "\(if .state == "SUCCESSFUL" then "pass" elif .state == "FAILED" or .state == "STOPPED" then "fail" else "pending" end) \(.name) — \(.url)"' || true ;;
    esac
}
# FILE-level findings live in a review object on GitHub; on GitLab/Bitbucket the
# overview is a TOP-LEVEL note/comment — returned here in the same row shape, or
# fix.md could never see a FILE finding on those vendors.
ctx_reviews() {
    case "$V" in
        github) gh api --paginate "repos/$OWNER/$REPO/pulls/$N/reviews" | jq -c '.[] | {id, body, user: .user.login, state}' ;;
        gitlab) gl_discussions_cached "$N" | jq -c '.[] | .notes[0] | select(.position == null and .system != true) | {id, body, user: .author.username, state: "COMMENTED"}' ;;
        bitbucket) bb_paged "$BB_API/pullrequests/$N/comments?pagelen=100&fields=next,values.id,values.content.raw,values.user.nickname,values.inline,values.parent.id,values.deleted" \
                  '.values[] | select(.deleted != true and .inline == null and .parent == null) | {id, body: .content.raw, user: .user.nickname, state: "COMMENTED"} | @json' ;;
    esac
}
ctx_account() {
    case "$V" in
        github) gh api user --jq .login ;;
        gitlab) glab api user | jq -r .username ;;
        bitbucket) if [ "$BB_AUTH_KIND" = bearer ]; then printf 'UNKNOWN\n'; else bb_curl "https://api.bitbucket.org/2.0/user?fields=nickname" | jq -r .nickname; fi ;;
    esac
}
# {thread_id, resolved, comment_ids:[...]} per thread, same shape everywhere.
ctx_threads() {
    case "$V" in
        github) gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id isResolved comments(first:100){nodes{databaseId}}}}}}}' \
                  -f o="$OWNER" -f r="$REPO" -F n="$N" \
                  | jq -c '.data.repository.pullRequest.reviewThreads.nodes[] | {thread_id: .id, resolved: .isResolved, comment_ids: [.comments.nodes[].databaseId]}' ;;
        gitlab) gl_discussions_cached "$N" | jq -c '.[] | {thread_id: .id, resolved: (.resolved // false), comment_ids: [.notes[].id]}' ;;
        bitbucket) bb_paged "$BB_API/pullrequests/$N/comments?pagelen=100&fields=next,values.id,values.parent.id,values.resolution,values.deleted" \
                  '.values[] | select(.deleted != true) | {id, parent: (.parent.id // null), resolved: (.resolution != null)} | @json' \
                  | jq -c -s '. as $all | $all[] | select(.parent == null) as $r | {thread_id: $r.id, resolved: $r.resolved, comment_ids: ([$r.id] + [$all[] | select(.parent == $r.id) | .id])}' ;;
    esac
}

cmd_context() {
    parse_args "$@"
    V=$(req vendor); OWNER=$(req owner); REPO=$(req repo); N=$(req pr)
    HOST=$(arg host); MAXPATCH=$(arg max_patch_bytes)
    check_ident '^[A-Za-z0-9_.-]+$' "$OWNER"; check_ident '^[A-Za-z0-9_.-]+$' "$REPO"; check_ident '^[0-9]+$' "$N"
    sections=$(arg sections); [ -n "$sections" ] || sections="info,head,files,sizes,diff,commits,comments,ci"
    case "$V" in
        github) need gh; URL="https://${HOST:-github.com}/$OWNER/$REPO/pull/$N" ;;
        gitlab) gl_init "$OWNER" "$REPO" ;;
        bitbucket) bb_init "$OWNER" "$REPO" ;;
        *) die 1 "open-pr.sh: unknown vendor: $V" ;;
    esac
    case ",$sections," in *,diff,*) [ -n "$MAXPATCH" ] || die 1 "open-pr.sh context: --max-patch-bytes is required with the diff section";; esac
    # Fixed order regardless of the order given: head before diff, sizes before patch.
    for s in info head files sizes diff commits comments ci reviews account threads; do
        case ",$sections," in *,"$s",*) ;; *) continue ;; esac
        case "$s" in
            info)     section "PR info";           ctx_info ;;
            head)     section "Head SHA";          ctx_head ;;
            files)    section "Files";             ctx_files ;;
            sizes)    section "Diff size per file"; ctx_sizes ;;
            diff)     section "Diff";              ctx_diff ;;
            commits)  section "Commits";           ctx_commits ;;
            comments) section "Old comments";      ctx_comments ;;
            ci)       section "CI checks";         ctx_ci ;;
            reviews)  section "Reviews";           ctx_reviews ;;
            account)  section "Account";           ctx_account ;;
            threads)  section "Review threads";    ctx_threads ;;
        esac
    done
}

# ---------------------------------------------------------- locate-repo ----
cmd_locate_repo() {
    parse_args "$@"
    OWNER=$(req owner); REPO=$(req repo); HOST=$(req host)
    pat=$(printf '%s/%s' "$OWNER" "$REPO" | tr 'A-Z' 'a-z')
    matches_remote() {
        git -C "$1" remote -v 2>/dev/null | tr 'A-Z' 'a-z' \
            | grep -Eq "(https://$HOST/|git@$HOST:)$pat(\.git)?( |\$)"
    }
    if matches_remote .; then printf '.\n'; return 0; fi
    found=""
    for d in $(find . -maxdepth 4 -type d -iname "$REPO" 2>/dev/null | grep -Ev '/(node_modules|notebooks/review)/' || true); do
        if matches_remote "$d"; then found="$found$d\n"; fi
    done
    count=$(printf '%b' "$found" | grep -c . || true)
    case "$count" in
        1) printf '%b' "$found" ;;
        0) die 5 "no directory here has a git remote matching $OWNER/$REPO" ;;
        *) err "multiple candidates:"; printf '%b' "$found" >&2; exit 5 ;;
    esac
}

# ---------------------------------------------------------- repo-target ----
# The git remote of --repo-dir -> vendor/owner/repo/host, the lines target
# prints minus pull_number. origin first, else the only remote there is.
cmd_repo_target() {
    parse_args "$@"
    D=$(req repo_dir)
    url=$(git -C "$D" remote get-url origin 2>/dev/null) || {
        rs=$(git -C "$D" remote 2>/dev/null) || rs=""
        [ -n "$rs" ] && [ "$(printf '%s\n' "$rs" | grep -c .)" = 1 ] \
            || die 5 "open-pr.sh repo-target: $D has no origin remote and not exactly one other"
        url=$(git -C "$D" remote get-url "$rs")
    }
    # https://[user@]host[:port]/o/r · ssh://[user@]host[:port]/o/r · [user@]host:o/r
    case "$url" in
        https://*|http://*) hp=${url#*://}; auth=${hp%%/*}; path=${hp#*/}; host=${auth##*@} ;;
        ssh://*) hp=${url#ssh://}; auth=${hp%%/*}; path=${hp#*/}; host=${auth##*@}; host=${host%%:*} ;;
        *://*) die 5 "open-pr.sh repo-target: unsupported remote URL scheme: $url" ;;
        *:*) auth=${url%%:*}; path=${url#*:}; host=${auth##*@} ;;
        *) die 5 "open-pr.sh repo-target: the remote is not a hosted URL: $url" ;;
    esac
    path=$(printf '%s' "$path" | sed -E 's~^/+~~; s~/+$~~; s~\.git$~~')
    # owner/repo exactly — the only shape target and every other subcommand take
    printf '%s' "$path" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' \
        || die 5 "open-pr.sh repo-target: remote path is not owner/repo: $path"
    printf '%s' "$host" | grep -Eq '^[A-Za-z0-9.-]+(:[0-9]+)?$' \
        || die 5 "open-pr.sh repo-target: invalid remote host: $host"
    case "$(printf '%s' "$host" | tr 'A-Z' 'a-z')" in
        github.com) vendor=github ;;
        bitbucket.org) vendor=bitbucket ;;
        *) vendor=gitlab ;;
    esac
    printf 'vendor=%s\nowner=%s\nrepo=%s\nhost=%s\n' "$vendor" "${path%%/*}" "${path#*/}" "$host"
}

# ------------------------------------------------------------ checkout ----
# The remote whose URL matches the PR's host + owner/repo; falls back to origin.
# A clone can carry one remote per vendor — fetching the PR ref or the base from
# a blind `origin` hits the wrong host there, and the gate then rejects the tree.
find_remote() {   # $1 = git dir, $2 = host, $3 = owner/repo
    h=$(printf '%s' "$2" | tr 'A-Z' 'a-z'); p=$(printf '%s' "$3" | tr 'A-Z' 'a-z')
    # host then ':' or '/' then owner/repo — covers https://host/o/r, ssh://git@host/o/r,
    # the scp form git@host:o/r, and a local mirror path ending /host/o/r.
    git -C "$1" remote -v 2>/dev/null | tr 'A-Z' 'a-z' \
        | awk -v h="$h" -v p="$p" '$2 ~ ("(https://|@|/)" h "[:/]" p "(\\.git)?$") {print $1; exit}' \
        | grep . || printf 'origin'
}

# Vendor checkout into an existing directory (worktree or submodule checkout).
vendor_checkout() {   # $1 = directory
    d="$1"
    case "$V" in
        github)
            git -C "$d" fetch "$REMOTE" "refs/pull/$N/head" && git -C "$d" checkout --detach FETCH_HEAD ;;
        gitlab)
            git -C "$d" fetch "$REMOTE" "refs/merge-requests/$N/head:refs/remotes/$REMOTE/merge-requests/$N" \
                && git -C "$d" checkout --detach "refs/remotes/$REMOTE/merge-requests/$N" ;;
        bitbucket)
            src=$(bb_curl "$BB_API/pullrequests/$N?fields=source.repository.full_name,source.branch.name,source.commit.hash")
            s_repo=$(printf '%s' "$src" | jq -r '.source.repository.full_name')
            s_branch=$(printf '%s' "$src" | jq -r '.source.branch.name')
            s_commit=$(printf '%s' "$src" | jq -r '.source.commit.hash')
            if [ "$(printf '%s' "$s_repo" | tr 'A-Z' 'a-z')" = "$(printf '%s/%s' "$OWNER" "$REPO" | tr 'A-Z' 'a-z')" ]; then
                git -C "$d" fetch "$REMOTE" "$s_branch"
            else
                git -C "$d" fetch "https://bitbucket.org/$s_repo.git" "$s_branch"
            fi
            git -C "$d" checkout --detach "$s_commit" \
                || die 3 "the source branch was force-pushed since the PR data was read — $s_commit is unreachable. Call the run again." ;;
    esac
}

# Every checkout of one repo shares its .git: two at once race on ref locks in
# fetch and on the worktree list. mkdir is the atomic test-and-set; the lock
# holds the owner's pid so a lock left by a killed run is reclaimed, and the
# EXIT/INT/TERM trap below releases it on every way out.
LOCK_DIR=""
repo_lock() {   # $1 = any directory inside the repo
    common=$(git -C "$1" rev-parse --git-common-dir) || die 1 "open-pr.sh checkout: $1 is not a git repository"
    case "$common" in /*|[A-Za-z]:[\\/]*) ;; *) common="$(cd "$1" && pwd)/$common" ;; esac
    lock="$common/open-pr-checkout.lock"
    wait_max=$(arg lock_timeout); [ -n "$wait_max" ] || wait_max=120
    check_ident '^[0-9]+$' "$wait_max"
    waited=0
    until mkdir "$lock" 2>/dev/null; do
        owner=$(cat "$lock/pid" 2>/dev/null || true)
        if [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; then
            # rename first: of two waiters reclaiming the same stale lock, one wins
            mv "$lock" "$lock.stale.$$" 2>/dev/null && rm -rf "$lock.stale.$$"
            continue
        fi
        [ "$waited" -lt "$wait_max" ] \
            || die 1 "open-pr.sh checkout: another checkout of this repo still holds $lock after ${wait_max}s. If no review is running, delete that directory and call the run again."
        sleep 1; waited=$((waited + 1))
    done
    LOCK_DIR="$lock"
    printf '%s\n' "$$" > "$lock/pid"
}
repo_unlock() { [ -z "$LOCK_DIR" ] || rm -rf "$LOCK_DIR"; LOCK_DIR=""; }

cmd_checkout() {
    parse_args "$@"
    V=$(req vendor); OWNER=$(req owner); REPO=$(req repo); N=$(req pr)
    HEAD_SHA=$(req head_sha); BASE=$(req base)
    check_ident '^[A-Za-z0-9_.-]+$' "$OWNER"; check_ident '^[A-Za-z0-9_.-]+$' "$REPO"; check_ident '^[0-9]+$' "$N"
    check_ident '^[0-9a-fA-F]+$' "$HEAD_SHA"
    case "$V" in github) need gh ;; gitlab) : ;; bitbucket) bb_init "$OWNER" "$REPO" ;; esac

    HOST=$(arg host)
    if [ -z "$HOST" ]; then
        case "$V" in github) HOST=github.com ;; gitlab) HOST=gitlab.com ;; bitbucket) HOST=bitbucket.org ;; esac
    fi
    sub=$(arg submodule_path)
    if [ -n "$sub" ]; then
        # Submodule variant: init the bumped path, check the submodule PR out
        # into it, gate it, and fetch ITS base ref. Runs inside --worktree.
        W=$(req worktree)
        repo_lock "$W"
        git -C "$W" submodule update --init -- "$sub"
        target="$W/$sub"
        REMOTE=$(find_remote "$target" "$HOST" "$OWNER/$REPO")
    else
        repo_dir=$(req repo_dir)
        data=$(data_dir)
        target="$data/$REPO/worktrees/pr$N-$$$(awk 'BEGIN{srand();printf "%d", rand()*32768}')"
        repo_lock "$repo_dir"
        git -C "$repo_dir" worktree add "$target" --detach >&2
        REMOTE=$(find_remote "$repo_dir" "$HOST" "$OWNER/$REPO")
    fi

    # The head SHA is content-addressed: already present locally (any earlier
    # fetch) ⇒ detach straight to it — the checkout must not depend on a
    # git-network credential the API path never needed.
    if git -C "$target" rev-parse --verify --quiet "$HEAD_SHA^{commit}" >/dev/null 2>&1; then
        git -C "$target" checkout --detach "$HEAD_SHA" >&2
    else
        vendor_checkout "$target" >&2 || true
    fi
    # Head-SHA gate: the tree on disk must be the commit the diff was read at.
    # One retry re-runs the checkout (a ref that had not caught up resolves on
    # the second fetch; an errored checkout stays put). A third attempt would
    # only hide the mismatch, so there is none.
    gate_ok=""
    for attempt in 1 2; do
        have=$(git -C "$target" rev-parse HEAD 2>/dev/null || printf 'NONE')
        case "$have" in "$HEAD_SHA"*) gate_ok=1; break ;; esac
        [ "$attempt" = 1 ] && vendor_checkout "$target" >&2 || true
    done
    if [ -z "$gate_ok" ]; then
        err "head-SHA gate failed: worktree HEAD $have does not match the PR head $HEAD_SHA."
        err "tree left at: $target"
        exit 2
    fi
    # The explicit refspec is what creates origin/<base> — a single-branch or
    # shallow clone otherwise lands FETCH_HEAD alone and merge-base dies later.
    # A failure (e.g. an SSH remote with no key) must not kill the gated tree,
    # but it may not stay silent either: LEFT confirmation degrades without it.
    git -C "$target" fetch "$REMOTE" "+$BASE:refs/remotes/origin/$BASE" >&2 \
        || err "warning: could not fetch $REMOTE/$BASE — LEFT line confirmation will be UNCONFIRMABLE"
    repo_unlock
    printf 'worktree=%s\nhead=%s\n' "$target" "$(git -C "$target" rev-parse HEAD)"
}

# ---------------------------------------------------------- verify-line ----
# Prints the real content of the target line so the caller can judge the match.
# LEFT reads the merge base — never the base tip, a different blob once the
# base branch moved — and an empty merge-base result is caught before git show
# would silently read the index.
cmd_verify_line() {
    parse_args "$@"
    W=$(req worktree); P=$(req path); L=$(req line); SIDE=$(req side); BASE=$(req base)
    check_ident '^[0-9]+$' "$L"
    case "$SIDE" in
        RIGHT)
            [ -f "$W/$P" ] || { printf 'UNCONFIRMABLE no such file in the worktree\n'; return 0; }
            total=$(grep -c '' < "$W/$P") || total=0
            out=$(sed -n "${L}p" "$W/$P") ;;
        LEFT)
            mb=$(git -C "$W" merge-base "origin/$BASE" HEAD 2>/dev/null || true)
            if [ -z "$mb" ]; then printf 'UNCONFIRMABLE no merge base (shallow clone or unresolvable origin/%s)\n' "$BASE"; return 0; fi
            blob=$(git -C "$W" show "$mb:$P" 2>/dev/null) \
                || { printf 'UNCONFIRMABLE path not in the merge-base tree\n'; return 0; }
            total=$(printf '%s\n' "$blob" | grep -c '')
            out=$(printf '%s\n' "$blob" | sed -n "${L}p") ;;
        *) die 1 "open-pr.sh verify-line: --side must be LEFT or RIGHT" ;;
    esac
    # Judged by the real line count — an empty result alone cannot distinguish a
    # blank line inside the file (a valid anchor) from a line past EOF.
    [ "$L" -le "$total" ] || { printf 'UNCONFIRMABLE line %s is past the end of the file (%s lines)\n' "$L" "$total"; return 0; }
    printf '%s\n' "$out"
}

# ---------------------------------------------------------------- post ----
# One payload shape on every vendor:
#   {"body": "<overview>", "commit_id": "<sha>",
#    "comments": [{"path","line","side","body"}, ...]}
# post   -> create the vendor's unpublished stage (GitHub: pending review;
#           GitLab: draft notes; Bitbucket has none — the payload file IS the
#           unpublished stage, nothing reaches the PR).
# publish-> make it visible (GitHub: event=COMMENT; GitLab: bulk_publish;
#           Bitbucket: one POST per part, overview first).
# verify -> report what the PR actually shows.
post_init() {
    V=$(req vendor); OWNER=$(req owner); REPO=$(req repo); N=$(req pr)
    check_ident '^[A-Za-z0-9_.-]+$' "$OWNER"; check_ident '^[A-Za-z0-9_.-]+$' "$REPO"; check_ident '^[0-9]+$' "$N"
    case "$V" in github) need gh ;; gitlab) gl_init "$OWNER" "$REPO" ;; bitbucket) bb_init "$OWNER" "$REPO" ;; esac
}
post_error_hint() {
    case "$V" in
        github) err "hint: 422 = a comments[] entry off the diff (missing line, line outside every hunk, or wrong side). commit_id rejected = force-pushed since the diff was read — no payload fix exists, the run must be called again." ;;
        gitlab) err "hint: a rejected draft note is usually a bad position (wrong sha triple, or a new_line/old_line the diff never touches)." ;;
        bitbucket) err "hint: a 400 naming inline is a bad anchor — a path this PR did not change, or a to/from line the diff never touches. Re-post only the parts verify shows missing; a duplicate has no bulk undo." ;;
    esac
}
cmd_post() {
    parse_args "$@"; post_init
    F=$(req payload); [ -s "$F" ] || die 1 "open-pr.sh post: payload file missing/empty"
    jq -e '.body and .commit_id and (.comments | type == "array")' "$F" >/dev/null \
        || die 1 "open-pr.sh post: payload must carry body, commit_id, comments[]"
    case "$V" in
        github)
            id=$(gh api -X POST "repos/$OWNER/$REPO/pulls/$N/reviews" --input "$F" --jq '.id') \
                || { post_error_hint; exit 1; }
            printf 'review_id=%s\nstate=PENDING\n' "$id" ;;
        gitlab)
            refs=$(gl_mr_cached "$N" | jq '.diff_refs')
            total=$(jq '.comments | length' "$F")
            i=0
            while [ "$i" -lt "$total" ]; do
                jq -c --argjson i "$i" --argjson refs "$refs" \
                   '.comments[$i] | {note: .body, position: ({position_type: "text", base_sha: $refs.base_sha, start_sha: $refs.start_sha, head_sha: $refs.head_sha, new_path: .path, old_path: .path} + (if .side == "RIGHT" then {new_line: .line} else {old_line: .line} end))}' \
                   "$F" > "$TMPD/gl.note.json"
                glab api -X POST -H "Content-Type: application/json" \
                    "projects/$GL_PROJ/merge_requests/$N/draft_notes" --input "$TMPD/gl.note.json" >/dev/null \
                    || { post_error_hint; exit 1; }
                i=$((i + 1))
            done
            jq -c '{note: .body}' "$F" > "$TMPD/gl.note.json"
            glab api -X POST -H "Content-Type: application/json" \
                "projects/$GL_PROJ/merge_requests/$N/draft_notes" --input "$TMPD/gl.note.json" >/dev/null \
                || { post_error_hint; exit 1; }
            printf 'state=DRAFT_NOTES\n' ;;
        bitbucket)
            # No draft stage exists: nothing reaches the PR here. The payload
            # file is the unpublished review; publish sends it.
            printf 'state=UNPUBLISHED_LOCAL\n' ;;
    esac
}
cmd_publish() {
    parse_args "$@"; post_init
    case "$V" in
        github)
            RID=$(req review_id); check_ident '^[0-9]+$' "$RID"
            gh api -X POST "repos/$OWNER/$REPO/pulls/$N/reviews/$RID/events" -f event="COMMENT" --jq '.state' ;;
        gitlab)
            glab api -X POST "projects/$GL_PROJ/merge_requests/$N/draft_notes/bulk_publish" >/dev/null && printf 'PUBLISHED\n' ;;
        bitbucket)
            F=$(req payload)
            jq -c '{content: {raw: .body}}' "$F" > "$TMPD/bb.part.json"
            bb_curl -X POST -H "Content-Type: application/json" \
                "$BB_API/pullrequests/$N/comments" --data @"$TMPD/bb.part.json" | jq -r '"posted overview id=\(.id)"' \
                || { post_error_hint; exit 1; }
            total=$(jq '.comments | length' "$F")
            i=0
            while [ "$i" -lt "$total" ]; do
                jq -c --argjson i "$i" '.comments[$i] | {content: {raw: .body}, inline: ({path: .path} + (if .side == "RIGHT" then {to: .line} else {from: .line} end))}' \
                   "$F" > "$TMPD/bb.part.json"
                bb_curl -X POST -H "Content-Type: application/json" \
                    "$BB_API/pullrequests/$N/comments" --data @"$TMPD/bb.part.json" | jq -r '"posted line-comment id=\(.id)"' \
                    || { post_error_hint; err "publishing is one request per part and failed part-way: run verify, re-post only what is missing."; exit 1; }
                i=$((i + 1))
            done
            printf 'PUBLISHED\n' ;;
    esac
}
cmd_post_verify() {
    parse_args "$@"; post_init
    case "$V" in
        github)
            RID=$(req review_id); check_ident '^[0-9]+$' "$RID"
            gh api "repos/$OWNER/$REPO/pulls/$N/reviews/$RID" --jq '{id, state}' ;;
        gitlab)
            left=$(glab api "projects/$GL_PROJ/merge_requests/$N/draft_notes" | jq 'length')
            if [ "$left" = 0 ]; then printf 'PUBLISHED\n'; else printf 'UNPUBLISHED draft_notes=%s\n' "$left"; fi ;;
        bitbucket)
            M=$(req marker)
            found=$(bb_paged "$BB_API/pullrequests/$N/comments?pagelen=100&fields=next,values.id,values.content.raw,values.inline,values.deleted" \
                ".values[] | select(.deleted != true and (.content.raw | contains(\"$M\"))) | {id, path: .inline.path, line: .inline.to} | @json")
            if [ -n "$found" ]; then printf '%s\n' "$found"; else printf 'NOTHING-POSTED (no comment carries the marker)\n'; fi ;;
    esac
}

# -------------------------------------------------------------- thread ----
cmd_reply() {
    parse_args "$@"; post_init
    F=$(req body_file); [ -s "$F" ] || die 1 "open-pr.sh reply: body file missing/empty"
    CID=$(arg comment_id); KIND=$(arg kind); [ -n "$KIND" ] || KIND=line
    case "$V" in
        github)
            if [ "$KIND" = line ]; then
                check_ident '^[0-9]+$' "$CID"
                jq -Rs '{body: .}' "$F" | gh api -X POST "repos/$OWNER/$REPO/pulls/$N/comments/$CID/replies" --input - --jq '.id'
            else
                jq -Rs '{body: .}' "$F" | gh api -X POST "repos/$OWNER/$REPO/issues/$N/comments" --input - --jq '.id'
            fi ;;
        gitlab)
            # The reply lands in the DISCUSSION (not on a note id) — the caller maps
            # the comment to its thread via the "Review threads" section. Body via
            # --input: argv is readable through `ps`, and the text quotes the PR.
            T=$(req thread_id)
            jq -Rs '{body: .}' "$F" > "$TMPD/gl.reply.json"
            glab api -X POST -H "Content-Type: application/json" \
                "projects/$GL_PROJ/merge_requests/$N/discussions/$T/notes" --input "$TMPD/gl.reply.json" | jq -r '.id' ;;
        bitbucket)
            check_ident '^[0-9]+$' "$CID"
            jq -Rs -c '{content: {raw: .}, parent: {id: '"$CID"'}}' "$F" > "$TMPD/bb.reply.json"
            bb_curl -X POST -H "Content-Type: application/json" \
                "$BB_API/pullrequests/$N/comments" --data @"$TMPD/bb.reply.json" | jq -r '.id' ;;
    esac
}
cmd_resolve() {
    parse_args "$@"; post_init
    T=$(req thread_id)
    case "$V" in
        github) gh api graphql -f query='mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{id isResolved}}}' -f t="$T" --jq '.data.resolveReviewThread.thread.isResolved' ;;
        gitlab) glab api -X PUT "projects/$GL_PROJ/merge_requests/$N/discussions/$T?resolved=true" >/dev/null && printf 'true\n' ;;
        bitbucket) check_ident '^[0-9]+$' "$T"; bb_curl -X POST "$BB_API/pullrequests/$N/comments/$T/resolve" >/dev/null && printf 'true\n' ;;
    esac
}
cmd_react() {
    parse_args "$@"; post_init
    CID=$(req comment_id); E=$(req emoji); KIND=$(arg kind); [ -n "$KIND" ] || KIND=line
    check_ident '^[0-9]+$' "$CID"; check_ident '^(\+1|heart|hooray|rocket|confused|eyes)$' "$E"
    check_ident '^(line|top)$' "$KIND"
    case "$V" in
        github)
            # a diff comment and a conversation comment are separate id spaces
            if [ "$KIND" = line ]; then
                gh api -X POST "repos/$OWNER/$REPO/pulls/comments/$CID/reactions" -f content="$E" --jq '.id'
            else
                gh api -X POST "repos/$OWNER/$REPO/issues/comments/$CID/reactions" -f content="$E" --jq '.id'
            fi ;;
        gitlab) glab api -X POST "projects/$GL_PROJ/merge_requests/$N/notes/$CID/award_emoji" -f name="$E" | jq -r '.id' ;;
        bitbucket) printf 'NO-EQUIVALENT\n' ;;
    esac
}
cmd_account() { parse_args "$@"; post_init; ctx_account; }

# ------------------------------------------------------------ triggers ----
# Every `@open-pr` comment on an open PR/MR, 1 JSON line each, oldest first:
# {pr, url, comment_id, kind, user, created_at, body, authorized}. Bodies are
# attacker-controlled and never leave jq — no shell variable ever holds one.
# ISO-8601 with optional fraction and Z or ±hh:mm -> epoch seconds (fraction kept:
# the strict --since comparison must not drop a comment inside the same second).
JQ_EPOCH='def epoch:
    capture("^(?<d>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?<f>\\.[0-9]+)?(?<z>Z|[+-][0-9]{2}:?[0-9]{2})$") as $c
    | ($c.d + "Z" | fromdateiso8601)
      + (if $c.f then ("0" + $c.f | tonumber) else 0 end)
      - (if $c.z == "Z" then 0 else ($c.z | capture("(?<s>[+-])(?<h>[0-9]{2}):?(?<m>[0-9]{2})")
            | (if .s == "+" then 1 else -1 end) * ((.h | tonumber) * 3600 + (.m | tonumber) * 60)) end);'
# Open PRs -> $TMPD/tr.prs ({pr, url} lines); their comments -> stdout as
# {pr, comment_id, kind, user, created_at, body, authorized, uid}. $SINCE_Z only
# narrows the fetch (the vendors filter on update time, a superset).
trg_fetch() {
    case "$V" in
        github)
            gh api --paginate "repos/$OWNER/$REPO/pulls?state=open&per_page=100" > "$TMPD/tr.page"
            jq -c '.[] | {pr: .number, url: .html_url}' "$TMPD/tr.page" > "$TMPD/tr.prs"
            q="per_page=100"; [ -z "$SINCE_Z" ] || q="$q&since=$SINCE_Z"
            auth='(if .author_association == "OWNER" or .author_association == "MEMBER" or .author_association == "COLLABORATOR" then "yes" else "no" end)'
            gh api --paginate "repos/$OWNER/$REPO/issues/comments?$q" > "$TMPD/tr.page"
            jq -c ".[] | select(.issue_url | test(\"/issues/[0-9]+\$\")) | {pr: (.issue_url | split(\"/\") | last | tonumber), comment_id: (.id | tostring), kind: \"top\", user: .user.login, created_at, body: (.body // \"\"), authorized: $auth, uid: null}" "$TMPD/tr.page"
            gh api --paginate "repos/$OWNER/$REPO/pulls/comments?$q" > "$TMPD/tr.page"
            jq -c ".[] | {pr: (.pull_request_url | split(\"/\") | last | tonumber), comment_id: (.id | tostring), kind: \"line\", user: .user.login, created_at, body: (.body // \"\"), authorized: $auth, uid: null}" "$TMPD/tr.page" ;;
        gitlab)
            q="state=opened&per_page=100"; [ -z "$SINCE_Z" ] || q="$q&updated_after=$SINCE_Z"
            glab api --paginate "projects/$GL_PROJ/merge_requests?$q" > "$TMPD/tr.page"
            jq -c '.[] | {pr: .iid, url: .web_url}' "$TMPD/tr.page" > "$TMPD/tr.prs"
            jq -r '.pr' "$TMPD/tr.prs" | while IFS= read -r iid; do
                check_ident '^[0-9]+$' "$iid"
                glab api --paginate "projects/$GL_PROJ/merge_requests/$iid/notes?per_page=100" > "$TMPD/tr.page"
                jq -c --argjson pr "$iid" '.[] | select(.system != true) | {pr: $pr, comment_id: (.id | tostring), kind: (if .type == "DiffNote" or .position != null then "line" else "top" end), user: .author.username, created_at, body: (.body // ""), authorized: "UNKNOWN", uid: .author.id}' "$TMPD/tr.page"
            done ;;
        bitbucket)
            bb_paged "$BB_API/pullrequests?state=OPEN&pagelen=50&fields=next,values.id,values.links.html.href" \
                '.values[] | {pr: .id, url: .links.html.href} | @json' > "$TMPD/tr.prs"
            jq -r '.pr' "$TMPD/tr.prs" | while IFS= read -r id; do
                check_ident '^[0-9]+$' "$id"
                bb_paged "$BB_API/pullrequests/$id/comments?pagelen=100&fields=next,values.id,values.content.raw,values.user.nickname,values.created_on,values.inline,values.deleted" \
                    ".values[] | select(.deleted != true) | {pr: $id, comment_id: (.id | tostring), kind: (if .inline != null then \"line\" else \"top\" end), user: .user.nickname, created_at: .created_on, body: (.content.raw // \"\"), authorized: \"UNKNOWN\", uid: null} | @json"
            done ;;
    esac
}
cmd_triggers() {
    parse_args "$@"
    V=$(req vendor); OWNER=$(req owner); REPO=$(req repo); SINCE=$(arg since)
    check_ident '^[A-Za-z0-9_.-]+$' "$OWNER"; check_ident '^[A-Za-z0-9_.-]+$' "$REPO"
    case "$V" in
        github) need gh ;; gitlab) gl_init "$OWNER" "$REPO" ;; bitbucket) bb_init "$OWNER" "$REPO" ;;
        *) die 1 "open-pr.sh: unknown vendor: $V" ;;
    esac
    SINCE_Z=""
    if [ -n "$SINCE" ]; then
        SINCE_Z=$(jq -rn --arg s "$SINCE" "$JQ_EPOCH"' $s | epoch | floor | todate' 2>/dev/null) && [ -n "$SINCE_Z" ] \
            || die 1 "open-pr.sh triggers: --since must be ISO-8601 (e.g. 2026-01-31T09:00:00Z): $SINCE"
    fi
    me=$(ctx_account) || die 1 "open-pr.sh triggers: could not read the logged-in account"
    [ "$me" != UNKNOWN ] || me=""
    mf=$(cmd_marker --vendor "$V" --kind finding); mr=$(cmd_marker --vendor "$V" --kind reply)
    trg_fetch > "$TMPD/tr.all"
    # plugin-authored comments (own account, or carrying a marker) quote `@open-pr`
    # themselves — excluded, or a posted review would trigger the next one
    jq -c -s --slurpfile prs "$TMPD/tr.prs" --arg me "$me" --arg since "$SINCE" --arg mf "$mf" --arg mr "$mr" "$JQ_EPOCH"'
        ($prs | map({key: (.pr | tostring), value: .url}) | from_entries) as $open
        | ($since | if . == "" then null else epoch end) as $after
        | [ .[] | select($open[.pr | tostring] != null)
            | select(.body | test("\\A\\s*@open-pr(\\s|\\z)"))
            | select($me == "" or .user != $me)
            | select((.body | contains($mf)) or (.body | contains($mr)) | not)
            | select($after == null or (.created_at | epoch) > $after)
            | . + {url: $open[.pr | tostring]} ]
        | sort_by(.created_at | epoch) | .[]' "$TMPD/tr.all" > "$TMPD/tr.cand"
    printf '{}\n' > "$TMPD/tr.auth"
    if [ "$V" = gitlab ]; then
        # write access = Developer (30) or above; 404 = not a member. One call per
        # distinct author; any other failure stops the run so no trigger is misjudged.
        jq -r '.uid // empty' "$TMPD/tr.cand" | sort -u | while IFS= read -r uid; do
            check_ident '^[0-9]+$' "$uid"
            if glab api "projects/$GL_PROJ/members/all/$uid" > "$TMPD/gl.member" 2> "$TMPD/gl.member.err"; then
                a=$(jq -r 'if (.access_level // 0) >= 30 then "yes" else "no" end' "$TMPD/gl.member")
            elif grep -q '404' "$TMPD/gl.member.err"; then
                a=no
            else
                cat "$TMPD/gl.member.err" >&2
                die 1 "open-pr.sh triggers: could not read the membership of GitLab user $uid"
            fi
            jq -nc --arg u "$uid" --arg a "$a" '{($u): $a}'
        done > "$TMPD/tr.auth.l"
        jq -s 'add // {}' "$TMPD/tr.auth.l" > "$TMPD/tr.auth"
    fi
    jq -c --slurpfile a "$TMPD/tr.auth" '
        (if .uid != null then ($a[0][.uid | tostring] // "no") else .authorized end) as $auth
        | {pr, url, comment_id, kind, user, created_at, body, authorized: $auth}' "$TMPD/tr.cand"
}

cmd_commit_url() {
    parse_args "$@"
    V=$(req vendor); OWNER=$(req owner); REPO=$(req repo); SHA=$(req sha)
    check_ident '^[0-9a-fA-F]+$' "$SHA"
    short=$(printf '%.7s' "$SHA")
    case "$V" in
        github)    printf '[%s](https://github.com/%s/%s/commit/%s)\n' "$short" "$OWNER" "$REPO" "$SHA" ;;
        gitlab)    printf '[%s](https://%s/%s/%s/-/commit/%s)\n' "$short" "$(req host)" "$OWNER" "$REPO" "$SHA" ;;
        bitbucket) printf '[%s](https://bitbucket.org/%s/%s/commits/%s)\n' "$short" "$OWNER" "$REPO" "$SHA" ;;
    esac
}
cmd_marker() {
    parse_args "$@"
    V=$(req vendor); K=$(req kind)
    case "$V/$K" in
        github/finding|gitlab/finding) printf '<!-- bot-finding -->\n' ;;
        github/reply|gitlab/reply)     printf '<!-- bot-reply -->\n' ;;
        bitbucket/finding)             printf '[bot-finding]: #\n' ;;
        bitbucket/reply)               printf '[bot-reply]: #\n' ;;
        *) die 1 "open-pr.sh marker: --kind finding|reply" ;;
    esac
}

# ------------------------------------------------------------ data-dir ----
# Review memory and worktrees live under ONE directory the user picks, recorded
# in the user-level config — never inside a reviewed repo, so no repo has to
# .gitignore it. Unset ⇒ exit 7: the caller asks the user, then --set.
data_conf() {
    [ -n "${XDG_CONFIG_HOME:-}${HOME:-}" ] || die 1 "open-pr: neither XDG_CONFIG_HOME nor HOME is set"
    printf '%s' "${XDG_CONFIG_HOME:-$HOME/.config}/open-pr/config.json"
}
# The config as JSON; absent or empty ⇒ {}. Anything else that is not a JSON
# object stops the run — read as "unset", a later --set would overwrite it.
conf_json() {
    f=$(data_conf)
    [ -s "$f" ] || { printf '{}'; return 0; }
    jq -e 'type == "object"' "$f" >/dev/null 2>&1 \
        || die 1 "open-pr: $f is not a JSON object — fix it or delete it"
    cat "$f"
}
data_dir() {
    c=$(conf_json)
    v=$(printf '%s' "$c" | jq -r '.data_dir // empty')
    [ -n "$v" ] || die 7 "open-pr: data directory not set ($(data_conf) has no data_dir)"
    printf '%s' "$v"
}
cmd_data_dir() {
    parse_args "$@"
    s=$(arg set)
    conf_f=$(data_conf)
    if [ -n "$s" ]; then
        conf=$(conf_json)
        case "$s" in
            "~"|"~/"*) s="${HOME:?HOME is not set}${s#\~}" ;;
            /*|[A-Za-z]:[\\/]*) ;;
            *) s="$PWD/$s" ;;
        esac
        mkdir -p "$s" "$(dirname "$conf_f")"
        s=$(cd "$s" && pwd)
        printf '%s' "$conf" | jq --arg d "$s" '.data_dir = $d' > "$TMPD/config.json"
        mv "$TMPD/config.json" "$conf_f"
    fi
    d=$(data_dir)
    printf '%s\n' "$d"
}

# --------------------------------------------------------- find-memory ----
# Existing notebooks/review/ memory below the cwd, for the data-dir cases to
# offer as an import. No --repo: a suggested data directory (notebooks/review
# beside the repo, or at the cwd outside any repo) plus each notebooks/review/
# up to one repo deep. --repo R: each notebooks/review/R. Paths are absolute.
cmd_find_memory() {
    parse_args "$@"
    r=$(arg repo)
    if [ -n "$r" ]; then
        check_ident '^[A-Za-z0-9_.-]+$' "$r"
        pat="*/notebooks/review/$r"; depth=4
    else
        if top=$(git rev-parse --show-toplevel 2>/dev/null); then base=$(dirname "$top"); else base=$PWD; fi
        printf 'suggest=%s/notebooks/review\n' "$base"
        pat="*/notebooks/review"; depth=3
    fi
    find . -maxdepth "$depth" -type d -path "$pat" 2>/dev/null \
        | grep -Ev '/(node_modules|worktrees)/' \
        | while IFS= read -r d; do printf 'found=%s\n' "$PWD/${d#./}"; done
}

# ------------------------------------------------------------ settings ----
# Prints the repo's settings.json with every read-time default applied, plus
# the computed doctor_due. Never writes anything.
cmd_settings() {
    parse_args "$@"
    data=$(data_dir)
    # memory_dir rides along: "never bootstrapped" and "memory kept somewhere
    # else" print byte-identical defaults otherwise.
    mem_dir="$data/$(req repo)"
    f="$mem_dir/settings.json"
    if [ -s "$f" ]; then raw=$(cat "$f"); found=true; else raw='{}'; found=false; fi
    now=$(date +%s)
    d_at=$(printf '%s' "$raw" | jq -r '.review.doctored_at // empty')
    d_ep=""
    if [ -n "$d_at" ]; then
        d_ep=$(date -j -f '%Y-%m-%dT%H:%M:%S' "$(printf '%.19s' "$d_at")" +%s 2>/dev/null \
            || date -j -f '%Y-%m-%d' "$(printf '%.10s' "$d_at")" +%s 2>/dev/null \
            || date -d "$d_at" +%s 2>/dev/null || true)
    fi
    printf '%s' "$raw" | jq --argjson now "$now" --arg dep "${d_ep:-}" --arg memdir "$mem_dir" --argjson found "$found" '
        # A boolean defaulting to true needs has(): the // operator treats an explicit
        # false as absent and would flip a stored false back to the default.
        def default_bool($node; $key; $fallback):
            if ($node // {}) | has($key) then $node[$key] else $fallback end;
        def dur_secs:
            capture("(?<n>[0-9]+) (?<u>day|week|month)s?") as $m
            | ($m.n | tonumber) * (if $m.u == "day" then 86400 elif $m.u == "week" then 604800 else 2592000 end);
        {
            review: ((.review // {}) + {
                auto_submit_review: (.review.auto_submit_review // false),
                auto_resolve_fixed_findings: (.review.auto_resolve_fixed_findings // false),
                post_lgtm: default_bool(.review; "post_lgtm"; true),
                doctor_schedule: (.review.doctor_schedule // "1 months"),
                many_files_threshold: (.review.many_files_threshold // 30),
                big_file_threshold_kb: (.review.big_file_threshold_kb // 20),
                project_docs_found: (.review.project_docs_found // []),
                templates_copied: (.review.templates_copied // []),
                pr_template_paths: (.review.pr_template_paths // [])
            }),
            fix: ((.fix // {}) + {
                decline_needs_confirmation: default_bool(.fix; "decline_needs_confirmation"; true),
                auto_push: (.fix.auto_push // false)
            }),
            shared: (.shared // {}),
            watch_review: ((.watch_review // {}) + {
                max_concurrent: (.watch_review.max_concurrent // 5),
                poll_interval_seconds: (.watch_review.poll_interval_seconds // 60),
                notify: ((.watch_review.notify // {}) + {
                    review_started: default_bool(.watch_review.notify; "review_started"; true),
                    question: default_bool(.watch_review.notify; "question"; true),
                    draft_ready: default_bool(.watch_review.notify; "draft_ready"; true),
                    posted: default_bool(.watch_review.notify; "posted"; true),
                    re_review: default_bool(.watch_review.notify; "re_review"; true)
                }),
                snooze_until: (.watch_review.snooze_until // null)
            }),
            watch_review_configured: has("watch_review"),
            schema_version: (.schema_version // null),
            memory_dir: $memdir,
            memory_found: $found,
            doctor_due: (
                if (.review.doctored // false) != true then true
                elif (.review.doctor_schedule // "1 months") == "never" then false
                elif ($dep == "") then true
                else ($now > (($dep | tonumber) + ((.review.doctor_schedule // "1 months") | dur_secs)))
                end
            )
        }'
}

# -------------------------------------------------------------- stacks ----
# path<TAB>stacks per diff file. Overlays are added from repo signals; the one
# judgment call (is this .md instructing an agent?) is printed as a question
# for the caller to decide, never guessed here.
cmd_stacks() {
    # Paths stay in "$@" — flattening them into one string splits on spaces and
    # globs against the current tree. Only --repo-dir is an option here; any other
    # option must die loudly instead of being fed to basename as a path.
    D=.
    while [ $# -gt 0 ]; do
        case "$1" in
            --repo-dir) D="$2"; shift 2 ;;
            --*) die 1 "open-pr.sh stacks: unknown option $1 — stacks takes only --repo-dir" ;;
            *) break ;;
        esac
    done
    has() { [ -e "$D/$1" ]; }
    lambda_repo=""; { has serverless.yml || has template.yaml || has sam.yaml; } && lambda_repo=1
    laravel_repo=""; { has artisan || { [ -f "$D/composer.json" ] && grep -q 'laravel/framework' "$D/composer.json"; }; } && laravel_repo=1
    wp_repo=""; has wp-config.php && wp_repo=1
    for p in "$@"; do
        base=$(basename "$p")
        stack=""
        case "$base" in
            *.rb|*.erb|*.haml) stack=rails ;;
            *.vue) stack=vue ;;
            *.jsx|*.tsx) stack=react ;;
            *.py) stack=python ;;
            *.js|*.ts) stack=nodejs ;;
            *.sh|*.bash) stack=shell ;;
            Makefile|makefile|*.mk) stack=makefile ;;
            *.php) stack=php ;;
            *.md) stack='-(judge: agent-instructions if the content instructs an AI agent)' ;;
            *) stack=- ;;
        esac
        case "$stack" in
            python|nodejs)
                if [ -n "$lambda_repo" ] || printf '%s' "$p" | grep -Eq '(^|/)(lambda|lambdas|functions)/'; then
                    stack="$stack,lambda-common"
                fi ;;
            php)
                if [ -n "$laravel_repo" ] || printf '%s' "$p" | grep -Eq 'app/Http/Controllers|resources/views/.*\.blade\.php'; then
                    stack="laravel"
                elif [ -n "$wp_repo" ] || printf '%s' "$p" | grep -Eq 'wp-content/(plugins|themes)/'; then
                    stack="wordpress"
                fi ;;
        esac
        printf '%s\t%s\n' "$p" "$stack"
    done
}

# ---------------------------------------------------------------- push ----
# HEAD:branch to the remote matching the PR's host — a blind `origin` on a
# multi-remote clone pushes one vendor's PR to another vendor's repository.
cmd_push() {
    parse_args "$@"
    V=$(req vendor); OWNER=$(req owner); REPO=$(req repo); BRANCH=$(req branch)
    check_ident '^[A-Za-z0-9._/-]+$' "$BRANCH"
    D=$(arg dir); [ -n "$D" ] || D=.
    HOST=$(arg host)
    if [ -z "$HOST" ]; then
        case "$V" in github) HOST=github.com ;; gitlab) HOST=gitlab.com ;; bitbucket) HOST=bitbucket.org ;; esac
    fi
    REMOTE=$(find_remote "$D" "$HOST" "$OWNER/$REPO")
    git -C "$D" push "$REMOTE" "HEAD:$BRANCH" \
        || die 1 "push to remote '$REMOTE' ($(git -C "$D" remote get-url "$REMOTE" 2>/dev/null)) failed — surface this to the user as printed; the plugin never works around credentials or forces."
}

# ---------------------------------------------------------------- main ----
# ---------------------------------------------------------------- usage ----
# Layout is parsed by scripts/cli_doc.py: a section header ends in ":", a
# subcommand line is indented 2 spaces, its description 6 (wrapped lines join
# with one space), an exit code line is "  <code>  <meaning>".
usage() {
    cat <<'EOF'
usage: open-pr.sh <subcommand> [--option value ...]
       open-pr.sh --help

Common options:
  `--vendor V` on every vendor-shaped subcommand (`marker` and `commit-url` included — NOT
  `target`/`locate-repo`/`repo-target`/`data-dir`/`find-memory`/`settings`/`stacks`/`verify-line`);
  `--owner O --repo R --pr N` on every networked one (`triggers`: no `--pr`); `--host H` where
  self-hostable.

Subcommands:
  target <url>
      validate + parse → `vendor/owner/repo/pull_number/host` lines
  context [--max-patch-bytes B] [--sections s,…]
      fetch in safe order (Head SHA before Diff, sizes before patch), print `## <label>` sections.
      Default `info,head,files,sizes,diff,commits,comments,ci`; also `reviews,account,threads`.
      `--max-patch-bytes` required with `diff` — omission happens inside the call, never post-hoc
  locate-repo --owner O --repo R --host H
      `<repo_dir>` whose git remote matches
  repo-target --repo-dir D
      D's git remote (origin, else the only one) → `vendor/owner/repo/host` lines
  triggers [--since T]
      `@open-pr` comments on open PRs, JSONL, oldest first — read by open-pr-watch.sh; shape in
      reference/vendor-interface.md
  checkout --head-sha S --base B (--repo-dir D | --worktree W --submodule-path P)
      main: worktree add + PR checkout; submodule: init THAT path + checkout into it. Gates the tree
      against S (one retry), fetches `origin/<B>` by explicit refspec. Prints `worktree=…`. One per
      repo at a time: waits `--lock-timeout` s (120), then exit 1
  verify-line --worktree W --path P --line N --side LEFT|RIGHT --base B
      print that line's REAL content (LEFT = merge-base blob) or `UNCONFIRMABLE <reason>` — the
      caller judges the match
  post --payload F
      create the vendor's unpublished stage. Payload, ONE shape everywhere:
      `{"body","commit_id","comments":[{"path","line","side","body"}]}`. GitHub prints `review_id=…`
  publish [--review-id I] [--payload F]
      make it visible (GitHub needs `--review-id`; Bitbucket re-takes `--payload`, posts overview
      first)
  post-verify [--review-id I] [--marker M]
      what the PR actually shows (Bitbucket: `--marker` = the finding marker)
  reply --comment-id C --body-file F [--kind line|top] [--thread-id T]
      reply on a thread (`top` = overview-level). GitLab replies into the DISCUSSION — also pass the
      thread holding C
  resolve --thread-id T
      resolve a review thread
  push --branch B [--dir D]
      `HEAD:B` to the remote matching the PR's host — never a blind `origin`. Failure is printed and
      STOPS the flow; the plugin never works around credentials
  react --comment-id C --emoji E [--kind line|top]
      `top` = conversation comment. `NO-EQUIVALENT` on Bitbucket
  account
      login name, or `UNKNOWN` (marker-only detection)
  commit-url --sha S
      markdown commit link, for the anchor
  marker --kind finding|reply
      the marker literal — end every finding/reply with it
  data-dir [--set P]
      print `<data>`, absolute; `--set` records P (`~` and relative expanded, directory created) in
      the user-level config first. A config that is not a JSON object stops with exit 1
  find-memory [--repo R]
      memory below the cwd, absolute. Bare: `suggest=<path>` (`notebooks/review` beside the repo, or
      at a non-repo cwd), then `found=<path>` per `notebooks/review` up to one repo deep. `--repo R`:
      `found=<path>` per `notebooks/review/R`
  settings --repo <repo>
      `<data>/<repo>/settings.json` with read-time defaults applied + computed `doctor_due`.
      Read-only; missing file ⇒ pure defaults, and `memory_dir` + `memory_found` say which directory
      was read and whether its `settings.json` was there; `watch_review_configured` = node in the file
  stacks [--repo-dir D] <path>…
      `path<TAB>stack` per file, overlays applied. `.md` = the caller's judgment: agent-instructions
      ⇔ the CONTENT instructs an AI agent; prompt text inside code files adds `agent-instructions`
      onto the base stack

Exit codes:
  0  ok
  1  other — post errors add a `hint:` line
  2  head-SHA gate failed after its one retry
  3  vendor checkout error (e.g. force-push)
  4  invalid PR URL
  5  repo dir unresolvable
  6  missing credentials
  7  `<data>` not set
EOF
}

case "${1:-}" in -h|--help) usage; exit 0 ;; esac
need jq

TMPD=$(mktemp -d "${TMPDIR:-/tmp}/open-pr.XXXXXX")
cleanup() { repo_unlock; rm -rf "$TMPD"; }
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

sub="${1:-}"; [ -n "$sub" ] && shift || die 1 "open-pr.sh: no subcommand (see --help)"
case "$sub" in
    target)       cmd_target "$@" ;;
    context)      cmd_context "$@" ;;
    locate-repo)  cmd_locate_repo "$@" ;;
    repo-target)  cmd_repo_target "$@" ;;
    triggers)     cmd_triggers "$@" ;;
    checkout)     cmd_checkout "$@" ;;
    verify-line)  cmd_verify_line "$@" ;;
    post)         cmd_post "$@" ;;
    publish)      cmd_publish "$@" ;;
    post-verify)  cmd_post_verify "$@" ;;
    push)         cmd_push "$@" ;;
    reply)        cmd_reply "$@" ;;
    resolve)      cmd_resolve "$@" ;;
    react)        cmd_react "$@" ;;
    account)      cmd_account "$@" ;;
    commit-url)   cmd_commit_url "$@" ;;
    marker)       cmd_marker "$@" ;;
    data-dir)     cmd_data_dir "$@" ;;
    find-memory)  cmd_find_memory "$@" ;;
    settings)     cmd_settings "$@" ;;
    stacks)       cmd_stacks "$@" ;;
    *) die 1 "open-pr.sh: unknown subcommand: $sub (see --help)" ;;
esac
