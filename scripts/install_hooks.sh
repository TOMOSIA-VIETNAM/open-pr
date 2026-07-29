#!/usr/bin/env bash
# Install a pre-push hook that runs the same checks CI would.
#
#   scripts/install_hooks.sh
#
# GitHub Actions is disabled on this repository by the organisation, so nothing runs
# server-side yet. Until an org admin enables it, this is what keeps unchecked prompt
# changes from leaving a machine. Harmless to keep afterwards.
set -euo pipefail
cd "$(dirname "$0")/.."
HOOK=.git/hooks/pre-push
cat > "$HOOK" <<'HOOK_BODY'
#!/usr/bin/env bash
set -euo pipefail
echo "pre-push: prompt-graph invariants + duplication + vendor flags"
python3 -m pytest tests/ -q
python3 scripts/dup_scan.py
python3 scripts/vendor_lint.py
HOOK_BODY
chmod +x "$HOOK"
echo "installed $HOOK — bypass a one-off with: git push --no-verify"
