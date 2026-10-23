#!/usr/bin/env bash
# Everything that must pass before calling an edit under src/ done.
#
#   scripts/check.sh [base-ref] [pr]  base-ref defaults to main
#
# Pass the project PR number as well and it also runs the vendor lint against that PR's
# open e2e fixture — the cheap check that every documented Fetch command actually runs.
# Left out by default so the common case stays offline and instant.
#
# Exits non-zero if the test suite fails. The token report is informational: read
# it. A scenario that got cheaper wants its ceiling lowered
# (`token_report.py --update-budgets`); one that got more expensive needs a stated
# reason, or reverting.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="${1:-main}"
PR="${2:-}"

echo "== tests =="
python3 -m pytest tests/ -q

echo
echo "== duplication (near-verbatim only; a reworded restatement still needs a human) =="
python3 scripts/dup_scan.py

if [ -n "$PR" ]; then
  echo
  echo "== vendor commands, against the fixture of PR #${PR} =="
  python3 scripts/vendor_lint.py --pr "$PR"
fi

echo
echo "== context cost vs ${BASE} =="
python3 scripts/token_report.py --base "$BASE"
