#!/usr/bin/env bash
# Everything that must pass before calling an edit under src/ done.
#
#   scripts/check.sh [base-ref]      base-ref defaults to main
#
# Exits non-zero if the test suite fails. The token report is informational: read
# it. A scenario that got cheaper wants its ceiling lowered
# (`token_report.py --update-budgets`); one that got more expensive needs a stated
# reason, or reverting.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="${1:-main}"

echo "== tests =="
python3 -m pytest tests/ -q

echo
echo "== duplication (near-verbatim only; a reworded restatement still needs a human) =="
python3 scripts/dup_scan.py

echo
echo "== context cost vs ${BASE} =="
python3 scripts/token_report.py --base "$BASE"
