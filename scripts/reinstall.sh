#!/usr/bin/env bash
# Reinstall the "open-code-review" Claude Code plugin from this local directory, forcing a
# clean pull of the current plugin.json/commands/ (no stale marketplace/plugin
# registration left over from a previous install).
set -euo pipefail

SCOPE="${SCOPE:-user}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_MANIFEST="$SCRIPT_DIR/src/.claude-plugin/plugin.json"
MARKETPLACE_MANIFEST="$SCRIPT_DIR/.claude-plugin/marketplace.json"

if ! command -v claude >/dev/null 2>&1; then
  echo "❌ 'claude' CLI not found in PATH." >&2
  exit 1
fi

for f in "$PLUGIN_MANIFEST" "$MARKETPLACE_MANIFEST"; do
  if [ ! -f "$f" ]; then
    echo "❌ Missing manifest: $f" >&2
    exit 1
  fi
done

read_json_name() {
  grep -m1 '"name"' "$1" | sed -E 's/.*"name":[[:space:]]*"([^"]+)".*/\1/'
}

PLUGIN_NAME="$(read_json_name "$PLUGIN_MANIFEST")"
MARKETPLACE_NAME="${MARKETPLACE_NAME:-$(read_json_name "$MARKETPLACE_MANIFEST")}"

if [ -z "$PLUGIN_NAME" ] || [ -z "$MARKETPLACE_NAME" ]; then
  echo "❌ Could not read plugin/marketplace name from manifests." >&2
  exit 1
fi

PLUGIN_ID="$PLUGIN_NAME@$MARKETPLACE_NAME"

echo "Plugin dir:   $SCRIPT_DIR"
echo "Plugin id:    $PLUGIN_ID"
echo "Scope:        $SCOPE"
echo

echo "→ Uninstalling existing $PLUGIN_ID (if any)..."
claude plugin uninstall "$PLUGIN_ID" --scope "$SCOPE" >/dev/null 2>&1 || true

echo "→ Removing existing marketplace '$MARKETPLACE_NAME' (if any)..."
claude plugin marketplace remove "$MARKETPLACE_NAME" >/dev/null 2>&1 || true

echo "→ Re-adding marketplace from $SCRIPT_DIR (forces a fresh read of plugin.json)..."
claude plugin marketplace add "$SCRIPT_DIR"

echo "→ Installing $PLUGIN_ID..."
claude plugin install "$PLUGIN_ID" --scope "$SCOPE"

echo "→ Dọn cache cũ (uninstall/update chỉ orphan, không xoá ngay — tự xoá sau 7 ngày theo mặc định
   của Claude Code; ở đây xoá ngay, chỉ giữ đúng bản đang active)..."
CACHE_DIR="$HOME/.claude/plugins/cache/$MARKETPLACE_NAME/$PLUGIN_NAME"
INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
ACTIVE_PATH=""
if [ -f "$INSTALLED_JSON" ]; then
  if command -v jq >/dev/null 2>&1; then
    # Chính xác: đúng key .plugins["$PLUGIN_ID"], đúng entry khớp scope đang cài (không giả định
    # index [0] — 1 plugin có thể có nhiều entry theo scope khác nhau: user/project/local).
    ACTIVE_PATH="$(jq -r --arg id "$PLUGIN_ID" --arg scope "$SCOPE" \
      '(.plugins[$id] // [])[] | select(.scope == $scope) | .installPath' \
      "$INSTALLED_JSON" 2>/dev/null | head -1)"
  else
    # Fallback không cần jq — giả định file pretty-print nhiều dòng (đúng hiện tại), có thể sai nếu
    # file bị minify thành 1 dòng hoặc PLUGIN_ID xuất hiện nhiều nơi trong file.
    ACTIVE_PATH="$(grep -A3 "\"$PLUGIN_ID\"" "$INSTALLED_JSON" | grep -m1 '"installPath"' | sed -E 's/.*"installPath":[[:space:]]*"([^"]+)".*/\1/')"
  fi
fi
if [ -d "$CACHE_DIR" ] && [ -n "$ACTIVE_PATH" ]; then
  for d in "$CACHE_DIR"/*/; do
    d="${d%/}"
    if [ "$d" != "$ACTIVE_PATH" ]; then
      echo "   xoá bản cũ: $d"
      rm -rf "$d"
    fi
  done
else
  echo "   ⚠️  Không xác định được bản đang active — bỏ qua dọn cache (an toàn, không xoá gì)."
fi

echo
echo "✅ Installed. Restart Claude Code (or start a new session) to load /open-code-review:review-pr."
claude plugin list
