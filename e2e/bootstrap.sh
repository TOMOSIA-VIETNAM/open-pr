#!/usr/bin/env bash
# Create the throwaway fixture repo the e2e run reviews, in YOUR OWN namespace.
#
#   e2e/bootstrap.sh [--vendor github|gitlab|both] [--name open-pr-test]
#   e2e/bootstrap.sh --teardown [--vendor …] [--name …]
#
# Nothing is shared between contributors: the repo is created wherever your `gh` /
# `glab` is logged in, so anyone can run this with their own PAT. Default vendor is
# whichever CLI is actually authenticated.
#
# It creates a REAL private repo and a REAL PR in your account, and --teardown
# deletes them. Read e2e/README.md before the first run.
set -euo pipefail

VENDOR=""
NAME="open-pr-test"
TEARDOWN=false
RECREATE=false
BRANCH="e2e/planted-defects"
FIX="$(cd "$(dirname "$0")" && pwd)/fixtures"

while [ $# -gt 0 ]; do
  case "$1" in
    --vendor) VENDOR="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --teardown) TEARDOWN=true; shift ;;
    --recreate) RECREATE=true; shift ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

authed() { case "$1" in
  github) gh auth status >/dev/null 2>&1 ;;
  gitlab) glab auth status >/dev/null 2>&1 ;;
esac }

if [ -z "$VENDOR" ]; then
  for v in github gitlab; do authed "$v" && VENDOR="${VENDOR:+$VENDOR }$v"; done
  [ -n "$VENDOR" ] || { echo "neither gh nor glab is logged in — see e2e/README.md" >&2; exit 1; }
  echo "auto-detected vendor(s): $VENDOR"
elif [ "$VENDOR" = both ]; then
  VENDOR="github gitlab"
fi

# A generated dump keeps a 40KB blob out of git history while still tripping the
# large/dump-file guard in the review.
gen_dump() {
  mkdir -p db
  { echo "-- generated fixture, not real data";
    for i in $(seq 1 900); do
      echo "INSERT INTO products (id, sku, name, price_cents) VALUES ($i, 'SKU-$i', 'Product $i', $((i * 100)));"
    done; } > db/seeds_dump.sql
}

pr_body() {
  cat <<'EOF'
## What changed

Recalculation helper, prompt tweak, deploy step.

## Checklist

- [ ] Tests added or updated
- [ ] Migration is reversible
- [ ] No secret committed
EOF
}

seed_repo() {  # $1 = clone dir
  local d="$1"
  ( cd "$d"
    cp -R "$FIX/base/." .
    git add -A && git commit -qm "chore: fixture baseline"
    git push -q origin HEAD
    git checkout -qb "$BRANCH"
    cp -R "$FIX/pr/." .
    gen_dump
    git add -A && git commit -qm "feat: recalculation helper, prompt tweak, deploy step"
    git push -q -u origin "$BRANCH" )
}

run_github() {
  local ns; ns=$(gh api user --jq .login)
  if gh repo view "$ns/$NAME" >/dev/null 2>&1; then
    $RECREATE || { echo "github: $ns/$NAME already exists — pass --recreate or --teardown" >&2; return 1; }
    gh repo delete "$ns/$NAME" --yes
  fi
  local d; d=$(mktemp -d)
  gh repo create "$ns/$NAME" --private --clone --description "open-pr e2e fixture (throwaway)" -- "$d" >/dev/null 2>&1 \
    || { gh repo create "$ns/$NAME" --private --description "open-pr e2e fixture (throwaway)" >/dev/null
         git clone -q "https://github.com/$ns/$NAME.git" "$d"; }
  ( cd "$d"; git checkout -qb main 2>/dev/null || true )
  seed_repo "$d"
  local url; url=$(cd "$d" && gh pr create --title "e2e: planted defects" --body "$(pr_body)" --base main --head "$BRANCH" 2>/dev/null || true)
  [ -n "$url" ] || url=$(gh pr list -R "$ns/$NAME" --head "$BRANCH" --json url --jq '.[0].url')
  echo "github PR ready → $url"
  echo "   /open-pr:review $url"
}

run_gitlab() {
  local ns; ns=$(glab api user --jq .username)
  local d; d=$(mktemp -d)
  glab repo create "$NAME" --private --description "open-pr e2e fixture (throwaway)" >/dev/null 2>&1 || true
  local host; host=$(glab config get host 2>/dev/null || echo gitlab.com)
  git clone -q "https://$host/$ns/$NAME.git" "$d"
  ( cd "$d"; git checkout -qb main 2>/dev/null || true )
  seed_repo "$d"
  ( cd "$d" && glab mr create --title "e2e: planted defects" --description "$(pr_body)" \
      --target-branch main --source-branch "$BRANCH" --yes >/dev/null 2>&1 || true )
  local iid; iid=$(glab api "projects/$ns%2F$NAME/merge_requests?source_branch=$BRANCH" --jq '.[0].iid')
  echo "gitlab MR ready → https://$host/$ns/$NAME/-/merge_requests/$iid"
  echo "   /open-pr:review https://$host/$ns/$NAME/-/merge_requests/$iid"
}

teardown() {
  case "$1" in
    github) local ns; ns=$(gh api user --jq .login)
      gh repo delete "$ns/$NAME" --yes && echo "deleted github $ns/$NAME" ;;
    gitlab) local ns; ns=$(glab api user --jq .username)
      glab repo delete "$ns/$NAME" --yes && echo "deleted gitlab $ns/$NAME" ;;
  esac
}

for v in $VENDOR; do
  authed "$v" || { echo "$v: CLI not logged in, skipped"; continue; }
  case "$NAME" in *open-pr-test*) : ;; *) echo "refusing to touch '$NAME' — the fixture name must contain open-pr-test" >&2; exit 1 ;; esac
  if $TEARDOWN; then teardown "$v"; else "run_$v"; fi
done
