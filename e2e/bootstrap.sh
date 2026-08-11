#!/usr/bin/env bash
# Put a fixture PR/MR full of planted defects on the e2e repo, so a real
# /open-pr:review run can be checked against e2e/checklist.md.
#
#   e2e/bootstrap.sh --pr <n> [--vendor github|gitlab|bitbucket|all] [--repo ns/name] [--clone-dir DIR]
#   e2e/bootstrap.sh --pr <n> --checkout --clone-dir DIR     # working copy only, no writes
#   e2e/bootstrap.sh --pr <n> --teardown
#
# --vendor omitted on a terminal asks which one; omitted in a pipe or a hook takes every
# vendor whose credentials are present. `all` skips the question.
#
# --checkout exists for the /open-pr:fix flow, which must run from inside a clone of the
# fixture repo standing on the fixture branch. It clones and stops: no commit, no push,
# so a review already posted on that branch keeps its commit anchors. Re-running the
# seeding mode instead would force-push the branch and strand those anchors.
#
# --pr ties the fixture to the PR of THIS project being tested: it names the branch
# and, on GitHub, records the fixture link in that PR's description.
#
# Targets are pre-existing repos (e2e/targets.env) — this script never creates or
# deletes a repo. Teardown closes the fixture PR/MR and deletes its branch, nothing
# else. Needs push access to the target; without it, point --repo at your own fork.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$HERE/targets.env"

VENDOR=""; REPO_OVERRIDE=""; PR_NUM=""; TEARDOWN=false; CLONE_DIR=""; CHECKOUT=false
while [ $# -gt 0 ]; do
  case "$1" in
    --pr) PR_NUM="$2"; shift 2 ;;
    --vendor) VENDOR="$2"; shift 2 ;;
    --repo) REPO_OVERRIDE="$2"; shift 2 ;;
    --clone-dir) CLONE_DIR="$2"; shift 2 ;;
    --checkout) CHECKOUT=true; shift ;;
    --teardown) TEARDOWN=true; shift ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done
[ -n "$PR_NUM" ] || { echo "--pr <project-pr-number> is required: it names the fixture branch" >&2; exit 2; }
$CHECKOUT && [ -z "$CLONE_DIR" ] && { echo "--checkout needs --clone-dir DIR" >&2; exit 2; }
$CHECKOUT && $TEARDOWN && { echo "--checkout and --teardown are exclusive" >&2; exit 2; }
BRANCH="e2e/pr-$PR_NUM"
case "$BRANCH" in e2e/*) : ;; *) echo "refusing branch '$BRANCH'" >&2; exit 1 ;; esac

ALL_VENDORS="github gitlab bitbucket"

# Bitbucket ships no CLI, so "logged in" there means the env carries a credential —
# src/vendors/bitbucket/fetch.md owns which variables and what they are for.
authed() { case "$1" in
  github) command -v gh >/dev/null && gh auth status >/dev/null 2>&1 ;;
  gitlab) command -v glab >/dev/null && glab auth status >/dev/null 2>&1 ;;
  bitbucket) [ -n "${BITBUCKET_TOKEN:-}" ] ||
             { [ -n "${BITBUCKET_EMAIL:-}" ] && [ -n "${BITBUCKET_API_TOKEN:-}" ]; } ;;
esac }

# `return 0` is load-bearing: a `for` carries the last iteration's status, bitbucket is last, and under
# `set -e` an unauthenticated bitbucket would kill the script before it could say which vendors it found.
available() { for v in $ALL_VENDORS; do authed "$v" && printf '%s ' "$v"; done; return 0; }

# Asking beats guessing when a human is watching: one fixture PR per vendor costs a real
# branch on a real repo, and picking "all" by accident makes three.
choose_vendor() {
  local opts; opts=$(available); set -- $opts
  [ $# -gt 0 ] || { echo "no vendor is authenticated — see e2e/README.md" >&2; exit 1; }
  [ $# -eq 1 ] && { echo "$1"; return; }
  { echo "Which vendor should carry the fixture PR?"
    local i=1; for v in "$@"; do echo "  $i) $v"; i=$((i+1)); done
    echo "  a) all of them"; printf 'choice: '; } >&2
  local pick; read -r pick
  case "$pick" in
    a|A|all) echo "$@" ;;
    ''|*[!0-9]*) echo "not a choice: $pick" >&2; exit 2 ;;
    *) [ "$pick" -ge 1 ] && [ "$pick" -le $# ] || { echo "out of range: $pick" >&2; exit 2; }
       eval "echo \$$pick" ;;
  esac
}

case "$VENDOR" in
  "")  if [ -t 0 ] && ! $TEARDOWN; then VENDOR=$(choose_vendor); else VENDOR=$(available); fi
       [ -n "$VENDOR" ] || { echo "no vendor is authenticated — see e2e/README.md" >&2; exit 1; } ;;
  all) VENDOR="$ALL_VENDORS" ;;
  # No `both`: it used to mean 2 vendors and there are 3, so an old command line would build a third
  # fixture PR on a real repo. An unknown name stops here rather than reaching `run_<name>`.
  *)   for v in $VENDOR; do case " $ALL_VENDORS " in *" $v "*) : ;;
         *) echo "unknown vendor: $v (want: $ALL_VENDORS, or all)" >&2; exit 2 ;; esac; done ;;
esac

# Generated, not committed: a 40KB blob belongs in the fixture branch, not in this
# repo's history.
gen_dump() {
  mkdir -p db
  { echo "-- generated fixture, not real data"
    for i in $(seq 1 900); do
      echo "INSERT INTO products (id, sku, name, price_cents) VALUES ($i, 'SKU-$i', 'Product $i', $((i * 100)));"
    done; } > db/seeds_dump.sql
}

pr_body() {
  cat <<EOF
## What changed

Recalculation helper, prompt tweak, deploy step. Fixture for open-pr PR #$PR_NUM.

## Checklist

- [ ] Tests added or updated
- [ ] Migration is reversible
- [ ] No secret committed
EOF
}

# main must carry the clean state, the branch the defective one — that difference IS
# the diff under review.
seed() {  # $1 = clone dir
  local d="$1"
  ( cd "$d"
    git rev-parse --verify HEAD >/dev/null 2>&1 || git checkout -q -b main
    git checkout -q main 2>/dev/null || git checkout -q -b main
    cp -R "$HERE/fixtures/base/." .
    git add -A
    git diff --cached --quiet || { git commit -qm "chore: fixture baseline"; git push -q origin main; }
    git push -q origin main 2>/dev/null || true
    git checkout -q -B "$BRANCH"
    cp -R "$HERE/fixtures/pr/." .
    gen_dump
    git add -A && git commit -qm "feat: recalculation helper, prompt tweak, deploy step"
    git push -qf origin "$BRANCH" )
}

clone_to() {  # $1 = url -> echoes dir
  local d="${CLONE_DIR:-$(mktemp -d)}"
  [ -e "$d/.git" ] && { git -C "$d" fetch -q origin; echo "$d"; return; }
  mkdir -p "$d"
  git clone -q "$1" "$d" 2>/dev/null || { git init -q "$d"; git -C "$d" remote add origin "$1"; }
  echo "$d"
}

# The fix flow needs a working copy on the fixture branch, and needs the reviewed repo's
# memory to be there if it is to fix in line with a learned convention — that memory sits
# under the pwd the REVIEW ran from, which is this project, not the clone.
checkout_only() {  # $1 = clone url, $2 = repo slug
  local d; d=$(clone_to "$1")
  git -C "$d" fetch -q origin "$BRANCH"
  git -C "$d" checkout -q -B "$BRANCH" "origin/$BRANCH"
  local mem="notebooks/review/${2##*/}"
  if [ -d "$mem" ] && [ ! -d "$d/$mem" ]; then
    mkdir -p "$d/notebooks/review" && cp -R "$mem" "$d/notebooks/review/"
    echo "          copied $mem into the clone, so the fix run sees the learned convention"
  fi
  echo "working copy → $d  (on $BRANCH)"
  echo "          cd $d   then   /open-pr:fix <fixture url>"
}

run_github() {
  local repo="${REPO_OVERRIDE:-$GITHUB_REPO}"
  $CHECKOUT && { checkout_only "git@github.com:$repo.git" "$repo"; return; }
  [ "$(gh api "repos/$repo" --jq '.permissions.push // false')" = true ] \
    || { echo "github: no push access to $repo — fork it and pass --repo <your-fork>" >&2; return 1; }
  local d; d=$(clone_to "git@github.com:$repo.git")
  seed "$d"
  local url
  url=$(gh pr create -R "$repo" --title "e2e: planted defects (open-pr #$PR_NUM)" \
          --body "$(pr_body)" --base main --head "$BRANCH" 2>/dev/null) \
    || url=$(gh pr list -R "$repo" --head "$BRANCH" --json url --jq '.[0].url')
  echo "github  → $url"
  echo "          /open-pr:review $url"
  record_link "$url"
}

run_gitlab() {
  local repo="${REPO_OVERRIDE:-$GITLAB_REPO}"
  $CHECKOUT && { checkout_only "git@$GITLAB_HOST:$repo.git" "$repo"; return; }
  # `glab api` has no --jq (that is gh's flag) — pipe instead. A personal-namespace owner
  # can report project_access null, hence taking the max across both access fields.
  local lvl; lvl=$(glab api "projects/${repo//\//%2F}" 2>/dev/null \
    | jq -r '[.permissions.project_access.access_level, .permissions.group_access.access_level, 0]
             | map(select(. != null)) | max' 2>/dev/null || echo 0)
  [ "${lvl:-0}" -ge 30 ] \
    || { echo "gitlab: need Developer or above on $repo — fork it and pass --repo <your-fork>" >&2; return 1; }
  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -T "git@$GITLAB_HOST" 2>&1 | grep -qi welcome \
    || { echo "gitlab: SSH to git@$GITLAB_HOST is not working — add a key at" >&2
         echo "        https://$GITLAB_HOST/-/user_settings/ssh_keys (the PAT alone cannot push)" >&2; return 1; }
  local d; d=$(clone_to "git@$GITLAB_HOST:$repo.git")
  seed "$d"
  ( cd "$d" && glab mr create --title "e2e: planted defects (open-pr #$PR_NUM)" \
      --description "$(pr_body)" --target-branch main --source-branch "$BRANCH" --yes >/dev/null 2>&1 || true )
  local iid; iid=$(glab api "projects/${repo//\//%2F}/merge_requests?source_branch=$BRANCH&state=opened" | jq -r '.[0].iid')
  local url="https://$GITLAB_HOST/$repo/-/merge_requests/$iid"
  echo "gitlab  → $url"
  echo "          /open-pr:review $url"
  record_link "$url"
}

# Bitbucket Cloud, over plain HTTP: no CLI exists. Credentials come from the environment and
# only their NAMES appear here — the same rule the vendor file states for the plugin itself.
bb() {
  local auth
  if [ -n "${BITBUCKET_EMAIL:-}" ] && [ -n "${BITBUCKET_API_TOKEN:-}" ]; then
    auth=(-u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN")
  else
    auth=(-H "Authorization: Bearer $BITBUCKET_TOKEN")
  fi
  curl -sS --fail-with-body "${auth[@]}" "$@"
}

BB_API=https://api.bitbucket.org/2.0

# The open PR whose source is the fixture branch, filtered client-side: Bitbucket's own `q`
# wants quotes inside the query string, and one mis-encoded quote reads as "no PR" here.
bb_pr_id() {  # $1 = repo
  bb "$BB_API/repositories/$1/pullrequests?state=OPEN&pagelen=50&fields=values.id,values.source.branch.name" \
    | jq -r --arg b "$BRANCH" '.values[] | select(.source.branch.name == $b) | .id' | head -1
}

run_bitbucket() {
  local repo="${REPO_OVERRIDE:-$BITBUCKET_REPO}"
  $CHECKOUT && { checkout_only "git@bitbucket.org:$repo.git" "$repo"; return; }
  bb "$BB_API/repositories/$repo?fields=full_name" >/dev/null \
    || { echo "bitbucket: cannot read $repo — check the token's scopes, or pass --repo <your-fork>" >&2; return 1; }
  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -T git@bitbucket.org 2>&1 | grep -qi 'logged in as' \
    || { echo "bitbucket: SSH to git@bitbucket.org is not working — add a key at" >&2
         echo "        https://bitbucket.org/account/settings/ssh-keys/ (the API token cannot push)" >&2; return 1; }
  local d; d=$(clone_to "git@bitbucket.org:$repo.git")
  seed "$d"
  local id; id=$(bb_pr_id "$repo")
  if [ -z "$id" ]; then
    id=$(jq -n --arg t "e2e: planted defects (open-pr #$PR_NUM)" --arg b "$(pr_body)" --arg s "$BRANCH" \
           '{title:$t, description:$b, source:{branch:{name:$s}}, destination:{branch:{name:"main"}}}' \
         | bb -X POST -H "Content-Type: application/json" \
              "$BB_API/repositories/$repo/pullrequests?fields=id" --data @- | jq -r .id)
  fi
  local url="https://bitbucket.org/$repo/pull-requests/$id"
  echo "bitbucket → $url"
  echo "          /open-pr:review $url"
  echo "          auto_submit_review=false holds the review in CHAT here — this vendor has no draft"
  record_link "$url"
}

teardown_bitbucket() {
  local repo="${REPO_OVERRIDE:-$BITBUCKET_REPO}"
  local id; id=$(bb_pr_id "$repo")
  [ -n "$id" ] || { echo "bitbucket: no open fixture PR on $BRANCH"; return 0; }
  bb -X POST "$BB_API/repositories/$repo/pullrequests/$id/decline?fields=id" >/dev/null
  bb -X DELETE "$BB_API/repositories/$repo/refs/branches/$BRANCH" >/dev/null 2>&1 || true
  echo "bitbucket: declined PR #$id and deleted $BRANCH"
}

# The project PR keeps the evidence: which fixture PRs its e2e run used. Upserted by
# marker so re-running edits the same block.
record_link() {
  local link="$1" marker="<!-- e2e-fixtures -->"
  local this; this=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null) || return 0
  local body; body=$(gh pr view "$PR_NUM" -R "$this" --json body --jq .body 2>/dev/null) || return 0
  case "$body" in *"$link"*) return 0 ;; esac
  case "$body" in
    *"$marker"*) body="${body%$'\n'}"$'\n'"- $link" ;;
    # Single-quoted: a backtick inside double quotes would run as a command.
    *) body="${body%$'\n'}"$'\n\n'"$marker"$'\n''**e2e fixture PRs verified against `e2e/checklist.md`:**'$'\n'"- $link" ;;
  esac
  gh pr edit "$PR_NUM" -R "$this" --body "$body" >/dev/null && echo "          recorded on $this#$PR_NUM"
}

teardown_github() {
  local repo="${REPO_OVERRIDE:-$GITHUB_REPO}"
  gh pr close "$BRANCH" -R "$repo" --delete-branch --comment "e2e run finished" 2>/dev/null \
    && echo "github: closed the fixture PR and deleted $BRANCH" \
    || echo "github: no open fixture PR on $BRANCH"
}

teardown_gitlab() {
  local repo="${REPO_OVERRIDE:-$GITLAB_REPO}" p; p="${repo//\//%2F}"
  local iid; iid=$(glab api "projects/$p/merge_requests?source_branch=$BRANCH&state=opened" | jq -r '.[0].iid // empty')
  [ -n "$iid" ] || { echo "gitlab: no open fixture MR on $BRANCH"; return 0; }
  glab api -X PUT "projects/$p/merge_requests/$iid?state_event=close" >/dev/null
  glab api -X DELETE "projects/$p/repository/branches/${BRANCH//\//%2F}" >/dev/null 2>&1 || true
  echo "gitlab: closed MR !$iid and deleted $BRANCH"
}

for v in $VENDOR; do
  authed "$v" || { echo "$v: CLI not logged in, skipped"; continue; }
  if $TEARDOWN; then "teardown_$v"; else "run_$v" || true; fi
done
