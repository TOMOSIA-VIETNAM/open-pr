#!/usr/bin/env bash
# Install open-pr's skills into an agent platform that reads them straight off disk — Cursor, Codex,
# Gemini CLI, Antigravity. Use this when the platform's catalog is not an option (submission pending,
# or importing a marketplace is gated by plan/role). Claude Code does not need this script: it
# installs open-pr as a plugin from its own marketplace.
#
# The skills are links back into this clone by default, so `git pull` here updates every platform at
# once. --copy detaches them, and then a pull needs this script run again.
set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER='<!-- installed by open-pr scripts/install-local.sh — safe to delete -->'

usage() {
  cat <<'EOF'
Usage: scripts/install-local.sh [--platform NAME] [--target DIR] [--copy] [--uninstall]

  --platform NAME  shared      ~/.agents/skills        Cursor, Codex, Gemini CLI  (default)
                   cursor      ~/.cursor/skills
                   antigravity ~/.gemini/antigravity-cli/skills
  --target DIR     install somewhere else entirely; wins over --platform
  --copy           copy the skills instead of linking them (needed if your platform will not
                   follow symlinks); afterwards a `git pull` requires re-running this script
  --uninstall      remove only what this script installed, then exit

Installs: open-pr-review, open-pr-fix, open-pr-upgrade, open-pr-clean.
Never overwrites a file this script did not create.
EOF
}

platform_dir() {
  case "$1" in
    shared) printf '%s\n' "$HOME/.agents/skills" ;;
    cursor) printf '%s\n' "$HOME/.cursor/skills" ;;
    antigravity) printf '%s\n' "$HOME/.gemini/antigravity-cli/skills" ;;
    *) printf 'install-local.sh: unknown platform %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
}

PLATFORM=shared
TARGET=
MODE=link
ACTION=install

while [ $# -gt 0 ]; do
  case "$1" in
    --platform) [ $# -ge 2 ] || { usage >&2; exit 2; }; PLATFORM="$2"; shift 2 ;;
    --target) [ $# -ge 2 ] || { usage >&2; exit 2; }; TARGET="$2"; shift 2 ;;
    --copy) MODE=copy; shift ;;
    --uninstall) ACTION=uninstall; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'install-local.sh: unexpected argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

[ -n "$TARGET" ] || TARGET="$(platform_dir "$PLATFORM")"

SKILLS=()
for dir in "$REPO"/skills/open-pr-*; do
  [ -d "$dir" ] || continue
  SKILLS+=("$(basename -- "$dir")")
done
[ ${#SKILLS[@]} -gt 0 ] || { printf 'install-local.sh: no skills found under %s/skills\n' "$REPO" >&2; exit 1; }

# Ours = a symlink into this clone, or a copy carrying the marker. Anything else is the user's.
installed_by_us() {
  local path="$1"
  if [ -L "$path" ]; then
    case "$(readlink -- "$path")" in "$REPO"/*) return 0 ;; *) return 1 ;; esac
  fi
  [ -f "$path/SKILL.md" ] && grep -qF -- "$MARKER" "$path/SKILL.md"
}

if [ "$ACTION" = uninstall ]; then
  removed=0
  for name in "${SKILLS[@]}"; do
    path="$TARGET/$name"
    [ -e "$path" ] || [ -L "$path" ] || continue
    if installed_by_us "$path"; then
      printf 'removing %s\n' "$path"
      rm -rf -- "$path"
      removed=$((removed + 1))
    else
      printf 'kept     %s — not installed by this script\n' "$path"
    fi
  done
  printf '\n%d removed from %s\n' "$removed" "$TARGET"
  exit 0
fi

mkdir -p -- "$TARGET"

for name in "${SKILLS[@]}"; do
  path="$TARGET/$name"
  if { [ -e "$path" ] || [ -L "$path" ]; } && ! installed_by_us "$path"; then
    printf 'install-local.sh: %s already exists and was not installed by this script — remove it yourself, nothing was written\n' "$path" >&2
    exit 1
  fi
done

for name in "${SKILLS[@]}"; do
  path="$TARGET/$name"
  rm -rf -- "$path"
  if [ "$MODE" = link ]; then
    ln -s -- "$REPO/skills/$name" "$path"
    printf 'linked  %s -> %s\n' "$path" "$REPO/skills/$name"
  else
    cp -R -- "$REPO/skills/$name" "$path"
    # A copy sits outside the clone, so the relative hop to the adapter no longer resolves: bake in
    # absolute paths, and hand ROOT over directly.
    tmp="$path/SKILL.md.tmp"
    sed -e "s#\`../../adapters/root.md\` (relative to this file)#\`$REPO/adapters/root.md\`#" \
        "$path/SKILL.md" \
      | awk -v root="ROOT: $REPO/src" '
          /^---$/ { print; if (++fence == 2) print "\n" root; next } { print }
        ' >"$tmp"
    mv -- "$tmp" "$path/SKILL.md"
    printf '\n%s\n' "$MARKER" >>"$path/SKILL.md"
    printf 'copied  %s\n' "$path"
  fi
done

cat <<EOF

Installed ${#SKILLS[@]} skills into $TARGET
Invoke them as /open-pr-review, /open-pr-fix, /open-pr-upgrade, /open-pr-clean (Codex: \$open-pr-review).
Also needed: gh (GitHub) or glab (GitLab), installed and logged in — reviews post as that account.
EOF

if [ "$MODE" = link ]; then
  printf 'Update:    git -C %s pull\n' "$REPO"
else
  printf 'Update:    git -C %s pull && %s --copy%s\n' "$REPO" "$0" \
    "$([ "$TARGET" = "$(platform_dir "$PLATFORM")" ] && printf ' --platform %s' "$PLATFORM" || printf ' --target %s' "$TARGET")"
fi
printf 'Uninstall: %s --uninstall%s\n' "$0" \
  "$([ "$TARGET" = "$(platform_dir "$PLATFORM")" ] && printf ' --platform %s' "$PLATFORM" || printf ' --target %s' "$TARGET")"
