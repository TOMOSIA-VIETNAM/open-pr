#!/usr/bin/env bash
# Install open-pr into an agent platform that reads it straight off disk — Cursor, Codex, Gemini CLI,
# Antigravity. Use this when the platform's catalog is not an option (submission pending, or importing
# a marketplace is gated by plan/role). Claude Code does not need this script: it installs open-pr as
# a plugin from its own marketplace.
#
# Cursor gets the whole plugin, since it has a directory for exactly that and then shows it in the
# plugin list. Everywhere else gets the four skills. Both are links back into this clone by default,
# so `git pull` here updates every platform at once; --copy detaches them, and then a pull needs this
# script run again.
set -euo pipefail
# Piping this into `head` closes stdout early. Progress messages must not be able to abort an
# install half way through, so every one of them tolerates a dead pipe.
trap '' PIPE
say() { printf "$@" 2>/dev/null || true; }

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER='<!-- installed by open-pr scripts/install-local.sh — safe to delete -->'
STAMP=".open-pr-local-install"

usage() {
  cat <<'EOF'
Usage: scripts/install-local.sh [--platform NAME] [--target DIR] [--copy]
                                [--update | --uninstall]

  --platform NAME  shared          skills  ~/.agents/skills                   Codex, Gemini CLI
                   cursor          plugin  ~/.cursor/plugins/local/open-pr    the Cursor IDE
                   cursor-cli      skills  ~/.cursor/skills                   cursor-agent
                   antigravity     skills  ~/.gemini/antigravity-cli/skills   the agy CLI
                   antigravity-ide skills  ~/.gemini/config/skills            the IDE
                   Omit it and the script asks.
  --target DIR     install somewhere else; keeps the --platform layout, wins over its path
  --copy           copy instead of linking (needed if your platform will not follow symlinks);
                   afterwards a `git pull` requires re-running this script
  --update         git pull in this clone, then reinstall with the same options
  --uninstall      remove only what this script installed, then exit
  --all            with --uninstall: sweep every platform above, not just one

Skills installed: open-pr-review, open-pr-fix, open-pr-upgrade, open-pr-clean.
Never overwrites a file this script did not create.
EOF
}

# Two layouts: `skills` drops the four skill directories in, `plugin` puts the whole plugin under one
# directory the platform already reserves for locally installed plugins.
platform_kind() {
  case "$1" in
    cursor) printf 'plugin\n' ;;
    shared|cursor-cli|antigravity|antigravity-ide) printf 'skills\n' ;;
    *) printf 'install-local.sh: unknown platform %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
}

ALL_PLATFORMS='shared cursor cursor-cli antigravity antigravity-ide'

platform_dir() {
  case "$1" in
    shared) printf '%s\n' "$HOME/.agents/skills" ;;
    cursor) printf '%s\n' "$HOME/.cursor/plugins/local/open-pr" ;;
    cursor-cli) printf '%s\n' "$HOME/.cursor/skills" ;;
    antigravity) printf '%s\n' "$HOME/.gemini/antigravity-cli/skills" ;;
    antigravity-ide) printf '%s\n' "$HOME/.gemini/config/skills" ;;
  esac
}

PLATFORM=
SWEEP=no
TARGET=
MODE=link
ACTION=install

while [ $# -gt 0 ]; do
  case "$1" in
    --platform) [ $# -ge 2 ] || { usage >&2; exit 2; }; PLATFORM="$2"; shift 2 ;;
    --target) [ $# -ge 2 ] || { usage >&2; exit 2; }; TARGET="$2"; shift 2 ;;
    --copy) MODE=copy; shift ;;
    --uninstall) ACTION=uninstall; shift ;;
    --all) SWEEP=yes; shift ;;
    --update) ACTION=update; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'install-local.sh: unexpected argument %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ "$SWEEP" = yes ]; then
  [ "$ACTION" = uninstall ] || { printf 'install-local.sh: --all only applies to --uninstall\n' >&2; exit 2; }
  [ -z "$TARGET" ] || { printf 'install-local.sh: --all and --target are mutually exclusive\n' >&2; exit 2; }
fi

# No platform given: ask, rather than guess on the user's behalf which agent they run. Piped into a
# shell (`curl ... | bash`) stdin is the pipe, so the question goes to the terminal directly.
ask_on=
if [ -t 0 ]; then ask_on=/dev/stdin; elif [ -r /dev/tty ]; then ask_on=/dev/tty; fi

if [ -z "$PLATFORM" ] && [ "$SWEEP" = no ]; then
  if [ -n "$ask_on" ]; then
    say 'Which platform?\n'
    say '  1) Codex or Gemini CLI   skills in ~/.agents/skills\n'
    say '  2) Cursor IDE            the plugin in ~/.cursor/plugins/local\n'
    say '  3) cursor-agent (CLI)    skills in ~/.cursor/skills\n'
    say '  4) Antigravity CLI       skills in ~/.gemini/antigravity-cli/skills\n'
    say '  5) Antigravity IDE       skills in ~/.gemini/config/skills\n'
    printf 'Enter 1-5: '
    read -r choice <"$ask_on" || { printf '\ninstall-local.sh: no answer, nothing was written\n' >&2; exit 2; }
    case "$choice" in
      1) PLATFORM=shared ;;
      2) PLATFORM=cursor ;;
      3) PLATFORM=cursor-cli ;;
      4) PLATFORM=antigravity ;;
      5) PLATFORM=antigravity-ide ;;
      *) printf 'install-local.sh: not one of 1-5\n' >&2; exit 2 ;;
    esac
  else
    PLATFORM=shared
    say 'No terminal to ask on — installing the skills for Codex and Gemini CLI.\n'
    say 'Other platforms: --platform cursor | cursor-cli | antigravity | antigravity-ide\n\n'
  fi
fi

if [ "$SWEEP" = no ]; then
  KIND="$(platform_kind "$PLATFORM")"
  [ -n "$TARGET" ] || TARGET="$(platform_dir "$PLATFORM")"
  WHERE="--platform $PLATFORM"
  [ "$TARGET" = "$(platform_dir "$PLATFORM")" ] || WHERE="--platform $PLATFORM --target $TARGET"
fi

if [ "$ACTION" = update ]; then
  say 'updating %s\n' "$REPO"
  git -C "$REPO" pull --ff-only
  ACTION=install
fi

SKILLS=()
for dir in "$REPO"/skills/open-pr-*; do
  [ -d "$dir" ] || continue
  SKILLS+=("$(basename -- "$dir")")
done
[ ${#SKILLS[@]} -gt 0 ] || { printf 'install-local.sh: no skills found under %s/skills\n' "$REPO" >&2; exit 1; }

# What gets written for a platform: one path per skill, or the single plugin directory.
paths_for() {
  local kind="$1" target="$2" name
  if [ "$kind" = skills ]; then
    for name in "${SKILLS[@]}"; do printf '%s\n' "$target/$name"; done
  else
    printf '%s\n' "$target"
  fi
}

# Ours = a symlink into this clone, or a copy carrying the marker line / stamp file. Anything else
# belongs to the user and is never touched.
installed_by_us() {
  local path="$1"
  if [ -L "$path" ]; then
    case "$(readlink -- "$path")" in "$REPO"|"$REPO"/*) return 0 ;; *) return 1 ;; esac
  fi
  [ -f "$path/$STAMP" ] && return 0
  [ -f "$path/SKILL.md" ] && grep -qF -- "$MARKER" "$path/SKILL.md"
}

if [ "$ACTION" = uninstall ]; then
  targets="$PLATFORM"
  [ "$SWEEP" = no ] || targets="$ALL_PLATFORMS"
  removed=0
  for name in $targets; do
    dir="$TARGET"
    [ "$SWEEP" = no ] || dir="$(platform_dir "$name")"
    while IFS= read -r path; do
      [ -e "$path" ] || [ -L "$path" ] || continue
      if installed_by_us "$path"; then
        say 'removing %s\n' "$path"
        rm -rf -- "$path"
        removed=$((removed + 1))
      else
        say 'kept     %s — not installed by this script\n' "$path"
      fi
    done <<EOF
$(paths_for "$(platform_kind "$name")" "$dir")
EOF
  done
  [ "$SWEEP" = no ] && say '\n%d removed from %s\n' "$removed" "$TARGET" \
                    || say '\n%d removed across every platform\n' "$removed"
  exit 0
fi

while IFS= read -r path; do
  if { [ -e "$path" ] || [ -L "$path" ]; } && ! installed_by_us "$path"; then
    printf 'install-local.sh: %s already exists and was not installed by this script — remove it yourself, nothing was written\n' "$path" >&2
    exit 1
  fi
done <<EOF
$(paths_for "$KIND" "$TARGET")
EOF

if [ "$KIND" = skills ]; then
  mkdir -p -- "$TARGET"
  for name in "${SKILLS[@]}"; do
    path="$TARGET/$name"
    rm -rf -- "$path"
    if [ "$MODE" = link ]; then
      ln -s -- "$REPO/skills/$name" "$path"
      say 'linked  %s -> %s\n' "$path" "$REPO/skills/$name"
    else
      cp -R -- "$REPO/skills/$name" "$path"
      # A copy sits outside the clone, so the relative hop to the adapter no longer resolves: bake in
      # the absolute path, and hand ROOT over directly.
      tmp="$path/SKILL.md.tmp"
      sed -e "s#\`../../adapters/root.md\` (relative to this file)#\`$REPO/adapters/root.md\`#" \
          "$path/SKILL.md" \
        | awk -v root="ROOT: $REPO/src" '
            /^---$/ { print; if (++fence == 2) print "\n" root; next } { print }
          ' >"$tmp"
      mv -- "$tmp" "$path/SKILL.md"
      say '\n%s\n' "$MARKER" >>"$path/SKILL.md"
      say 'copied  %s\n' "$path"
    fi
  done
else
  mkdir -p -- "$(dirname -- "$TARGET")"
  rm -rf -- "$TARGET"
  if [ "$MODE" = link ]; then
    ln -s -- "$REPO" "$TARGET"
    say 'linked  %s -> %s\n' "$TARGET" "$REPO"
  else
    mkdir -p -- "$TARGET"
    # Tracked files only: no .git, no local scratch, nothing the platform has no business reading.
    git -C "$REPO" archive HEAD | tar -x -C "$TARGET"
    say 'installed by open-pr scripts/install-local.sh from %s — safe to delete\n' "$REPO" >"$TARGET/$STAMP"
    say 'copied  %s\n' "$TARGET"
  fi
fi

say '\nInstalled into %s\n' "$TARGET"
say 'Invoke as /open-pr-review, /open-pr-fix, /open-pr-upgrade, /open-pr-clean (Codex: $open-pr-review).\n'
say 'Also needed: gh (GitHub) or glab (GitLab), installed and logged in — reviews post as that account.\n'

if [ "$MODE" = link ]; then
  say 'Update:    git -C %s pull\n' "$REPO"
else
  say 'Update:    git -C %s pull && %s --copy %s\n' "$REPO" "$0" "$WHERE"
fi
say 'Uninstall: %s --uninstall %s\n' "$0" "$WHERE"
