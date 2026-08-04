#!/usr/bin/env bash
# Publish a context-cost report on the PR that produced it.
#
#   scripts/ci_token_comment.sh <report-file>
#
# Always writes the job summary. Additionally upserts ONE PR comment, matched by a
# hidden marker so re-runs edit it rather than pile up. A fork PR has a read-only
# token, so CAN_COMMENT is false there and the summary is the whole output.
set -euo pipefail
REPORT="${1:?usage: ci_token_comment.sh <report-file>}"
MARKER="<!-- open-pr-token-report -->"

BODY=$(printf '%s\n### Context cost vs base\n\n```\n%s\n```\n\nA scenario that got cheaper wants its ceiling lowered (`token_report.py --update-budgets`). One that got more expensive needs a reason in the PR description.\n' \
  "$MARKER" "$(cat "$REPORT")")

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  printf '%s\n' "$BODY" >> "$GITHUB_STEP_SUMMARY"
fi

if [ "${CAN_COMMENT:-false}" != "true" ]; then
  echo "read-only token (fork PR) — numbers left in the job summary"
  exit 0
fi

REPO="${GITHUB_REPOSITORY:?}"
EXISTING=$(gh api --paginate "repos/$REPO/issues/${PR_NUMBER:?}/comments" \
  --jq "map(select(.body | startswith(\"$MARKER\"))) | .[0].id // empty")

if [ -n "$EXISTING" ]; then
  gh api -X PATCH "repos/$REPO/issues/comments/$EXISTING" -f body="$BODY" >/dev/null
  echo "updated comment $EXISTING"
else
  gh api -X POST "repos/$REPO/issues/$PR_NUMBER/comments" -f body="$BODY" >/dev/null
  echo "posted a new comment"
fi
