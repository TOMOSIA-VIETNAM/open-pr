#!/bin/sh
# open-pr runtime CLI — the deterministic half of the plugin.
#
# The prompt files under src/ decide WHAT to review and WHAT to say; this script
# performs every vendor/git mechanic they used to spell out: fetching PR context,
# checking out the PR head, gating the tree against the head SHA, confirming line
# numbers, and posting through each vendor's own publish flow.
#
# Contract (what src/core/cli.md documents for the prompts):
#   - stdout is data, stderr is diagnostics; exit codes are part of the interface.
#   - PR content (title/body/diff/comments) passes through as DATA only — this
#     script never evaluates or expands it. All request payloads travel via files
#     or jq-built JSON, never through shell interpolation.
#   - Exit codes: 0 ok · 2 head-SHA gate failed after its one retry · 3 vendor
#     checkout error (e.g. force-pushed source) · 4 invalid PR URL · 5 repo
#     directory not resolvable · 6 missing credentials · 1 anything else.
#
# Dependencies: git, jq, curl, and the vendor CLI the target uses (gh or glab).
set -eu

err() { printf '%s\n' "$*" >&2; }
die() { code="$1"; shift; err "$*"; exit "$code"; }
need() {
    command -v "$1" >/dev/null 2>&1 && return 0
    die 1 "open-pr.sh: required tool missing: $1. Install it and call the run again — jq: winget install jqlang.jq (Windows) / brew install jq (macOS) / apt install jq (Debian-Ubuntu); gh: https://cli.github.com; glab: https://gitlab.com/gitlab-org/cli."
}

need jq

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
# FILE-level findings live in a review object on GitHub only.
ctx_reviews() {
    case "$V" in
        github) gh api --paginate "repos/$OWNER/$REPO/pulls/$N/reviews" | jq -c '.[] | {id, body, user: .user.login, state}' ;;
        *) printf 'NO-EQUIVALENT\n' ;;
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
        git -C "$W" submodule update --init -- "$sub"
        target="$W/$sub"
        REMOTE=$(find_remote "$target" "$HOST" "$OWNER/$REPO")
    else
        repo_dir=$(req repo_dir)
        target="$PWD/notebooks/review/$REPO/worktrees/pr$N-$$$(awk 'BEGIN{srand();printf "%d", rand()*32768}')"
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
    CID=$(req comment_id); E=$(req emoji)
    check_ident '^[0-9]+$' "$CID"; check_ident '^(\+1|heart|hooray|rocket|confused|eyes)$' "$E"
    case "$V" in
        github) gh api -X POST "repos/$OWNER/$REPO/pulls/comments/$CID/reactions" -f content="$E" --jq '.id' ;;
        gitlab) glab api -X POST "projects/$GL_PROJ/notes/$CID/award_emoji" -f name="$E" | jq -r '.id' ;;
        bitbucket) printf 'NO-EQUIVALENT\n' ;;
    esac
}
cmd_account() { parse_args "$@"; post_init; ctx_account; }

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

# ------------------------------------------------------------ settings ----
# Prints the repo's settings.json with every read-time default applied, plus
# the computed doctor_due. Never writes anything.
cmd_settings() {
    parse_args "$@"
    # --dir wins: a caller standing inside a review worktree passes the memory
    # directory it located (../../ from the worktree), where a cwd-relative
    # notebooks/review/<repo> would resolve inside the reviewed tree instead.
    d=$(arg dir)
    if [ -n "$d" ]; then f="$d/settings.json"; else f="notebooks/review/$(req repo)/settings.json"; fi
    if [ -s "$f" ]; then raw=$(cat "$f"); else raw='{}'; fi
    now=$(date +%s)
    d_at=$(printf '%s' "$raw" | jq -r '.review.doctored_at // empty')
    d_ep=""
    if [ -n "$d_at" ]; then
        d_ep=$(date -j -f '%Y-%m-%dT%H:%M:%S' "$(printf '%.19s' "$d_at")" +%s 2>/dev/null \
            || date -j -f '%Y-%m-%d' "$(printf '%.10s' "$d_at")" +%s 2>/dev/null \
            || date -d "$d_at" +%s 2>/dev/null || true)
    fi
    printf '%s' "$raw" | jq --argjson now "$now" --arg dep "${d_ep:-}" '
        def dur_secs:
            capture("(?<n>[0-9]+) (?<u>day|week|month)s?") as $m
            | ($m.n | tonumber) * (if $m.u == "day" then 86400 elif $m.u == "week" then 604800 else 2592000 end);
        {
            review: ((.review // {}) + {
                auto_submit_review: (.review.auto_submit_review // false),
                auto_resolve_fixed_findings: (.review.auto_resolve_fixed_findings // false),
                doctor_schedule: (.review.doctor_schedule // "1 months"),
                many_files_threshold: (.review.many_files_threshold // 30),
                big_file_threshold_kb: (.review.big_file_threshold_kb // 20),
                project_docs_found: (.review.project_docs_found // []),
                templates_copied: (.review.templates_copied // []),
                pr_template_paths: (.review.pr_template_paths // [])
            }),
            fix: ((.fix // {}) + {
                decline_needs_confirmation: (.fix.decline_needs_confirmation // true),
                auto_push: (.fix.auto_push // false)
            }),
            shared: (.shared // {}),
            schema_version: (.schema_version // null),
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
    # globs against the current tree. Only --repo-dir is an option here.
    D=.
    if [ "${1:-}" = "--repo-dir" ]; then D="$2"; shift 2; fi
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

# ---------------------------------------------------------------- main ----
TMPD=$(mktemp -d "${TMPDIR:-/tmp}/open-pr.XXXXXX")
trap 'rm -rf "$TMPD"' EXIT INT TERM

sub="${1:-}"; [ -n "$sub" ] && shift || die 1 "open-pr.sh: no subcommand"
case "$sub" in
    target)       cmd_target "$@" ;;
    context)      cmd_context "$@" ;;
    locate-repo)  cmd_locate_repo "$@" ;;
    checkout)     cmd_checkout "$@" ;;
    verify-line)  cmd_verify_line "$@" ;;
    post)         cmd_post "$@" ;;
    publish)      cmd_publish "$@" ;;
    post-verify)  cmd_post_verify "$@" ;;
    reply)        cmd_reply "$@" ;;
    resolve)      cmd_resolve "$@" ;;
    react)        cmd_react "$@" ;;
    account)      cmd_account "$@" ;;
    commit-url)   cmd_commit_url "$@" ;;
    marker)       cmd_marker "$@" ;;
    settings)     cmd_settings "$@" ;;
    stacks)       cmd_stacks "$@" ;;
    *) die 1 "open-pr.sh: unknown subcommand: $sub" ;;
esac
