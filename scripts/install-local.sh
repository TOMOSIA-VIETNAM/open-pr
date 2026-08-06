#!/usr/bin/env bash
# Install open-pr into an agent platform that reads it straight off disk — Cursor, Codex, Gemini CLI,
# Antigravity — or into Claude Code through its own CLI. Use this when a platform's catalog is not an
# option (submission pending, or importing a marketplace is gated by plan/role).
#
# A vendor's IDE and CLI rarely read the same directory, so `--platform cursor` and
# `--platform antigravity` cover both of theirs; the narrower ids exist for anyone who wants one.
# Cursor's IDE takes the whole plugin, since it has a directory for exactly that and then lists it
# with a toggle; everywhere else takes the four skills. Both are links back into this clone by
# default, so `git pull` here updates every platform at once; --copy detaches them, and then a pull
# needs this script run again.
set -euo pipefail
# Piping this into `head` closes stdout early. Progress messages must not be able to abort an
# install half way through, so every one of them tolerates a dead pipe.
trap '' PIPE
say() { printf "$@" 2>/dev/null || true; }

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER='<!-- installed by open-pr scripts/install-local.sh — safe to delete -->'
STAMP=".open-pr-local-install"
MARKETPLACE='TOMOSIA-VIETNAM/open-pr'

usage() {
  cat <<'EOF'
Usage: scripts/install-local.sh [--platform NAME] [--target DIR] [--copy]
                                [--update | --uninstall [--all]]

  --platform NAME  claude       Claude Code, through its own `claude plugin` CLI
                   shared       Codex + Gemini CLI       ~/.agents/skills
                   cursor       the IDE and the CLI      both directories below
                     cursor-ide     the plugin           ~/.cursor/plugins/local/open-pr
                     cursor-cli     skills               ~/.cursor/skills
                   antigravity  the IDE and the CLI      both directories below
                     antigravity-cli  skills             ~/.gemini/antigravity-cli/skills
                     antigravity-ide  skills             ~/.gemini/config/skills
                   Omit it and the script asks.
  --target DIR     install somewhere else; one platform at a time, wins over its path
  --copy           copy instead of linking (needed if your platform will not follow symlinks);
                   afterwards a `git pull` requires re-running this script
  --update         git pull in this clone, then reinstall with the same options
  --uninstall      remove only what this script installed, then exit
  --all            with --uninstall: sweep every file-based platform above. Claude Code keeps its
                   own plugin state, so remove it with --platform claude --uninstall

Skills installed: open-pr-review, open-pr-fix, open-pr-upgrade, open-pr-clean.
Never overwrites a file this script did not create.
EOF
}

# A platform is one directory to write, or a vendor's IDE and CLI taken together.
platform_members() {
  case "$1" in
    cursor) printf 'cursor-ide cursor-cli\n' ;;
    antigravity) printf 'antigravity-cli antigravity-ide\n' ;;
    claude|shared|cursor-ide|cursor-cli|antigravity-cli|antigravity-ide) printf '%s\n' "$1" ;;
    *) printf 'install-local.sh: unknown platform %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
}

# Three layouts: `skills` drops the four skill directories in, `plugin` puts the whole plugin under
# one directory the platform reserves for locally installed plugins, `marketplace` hands the work to
# a CLI that keeps its own state.
platform_kind() {
  case "$1" in
    claude) printf 'marketplace\n' ;;
    cursor-ide) printf 'plugin\n' ;;
    *) printf 'skills\n' ;;
  esac
}

platform_dir() {
  case "$1" in
    claude) printf '%s\n' "$HOME/.claude/plugins" ;;
    shared) printf '%s\n' "$HOME/.agents/skills" ;;
    cursor-ide) printf '%s\n' "$HOME/.cursor/plugins/local/open-pr" ;;
    cursor-cli) printf '%s\n' "$HOME/.cursor/skills" ;;
    antigravity-cli) printf '%s\n' "$HOME/.gemini/antigravity-cli/skills" ;;
    antigravity-ide) printf '%s\n' "$HOME/.gemini/config/skills" ;;
  esac
}

SWEEP_PLATFORMS='shared cursor-ide cursor-cli antigravity-cli antigravity-ide'

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
    say '  1) Claude Code           its own marketplace, via the claude CLI\n'
    say '  2) Codex or Gemini CLI   skills in ~/.agents/skills\n'
    say '  3) Cursor                IDE and CLI\n'
    say '  4) Antigravity           IDE and CLI\n'
    say '  5) None of these         exit without writing anything\n'
    printf 'Enter 1-5 (empty to exit): '
    read -r choice <"$ask_on" || choice=
    case "$choice" in
      1) PLATFORM=claude ;;
      2) PLATFORM=shared ;;
      3) PLATFORM=cursor ;;
      4) PLATFORM=antigravity ;;
      5|"") say '\nNothing installed. Re-run when you know which platform, or pass --platform.\n'; exit 0 ;;
      *) printf 'install-local.sh: not one of 1-5\n' >&2; exit 2 ;;
    esac
  else
    PLATFORM=shared
    say 'No terminal to ask on — installing the skills for Codex and Gemini CLI.\n'
    say 'Other platforms: --platform claude | cursor | antigravity\n\n'
  fi
fi

MEMBERS=
if [ "$SWEEP" = yes ]; then
  MEMBERS="$SWEEP_PLATFORMS"
else
  MEMBERS="$(platform_members "$PLATFORM")"
  if [ -n "$TARGET" ] && [ "$(printf '%s\n' $MEMBERS | wc -w)" -gt 1 ]; then
    printf 'install-local.sh: --target takes one platform; use %s\n' \
      "$(printf '%s ' $MEMBERS)" >&2
    exit 2
  fi
fi
WHERE="--platform $PLATFORM"
[ -z "$TARGET" ] || WHERE="--platform $PLATFORM --target $TARGET"

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

require_claude_cli() {
  command -v claude >/dev/null || {
    printf 'install-local.sh: the claude CLI is not on PATH — see https://claude.ai/code\n' >&2; exit 1; }
}

removed=0

uninstall_one() {
  local member="$1" kind="$2" dir="$3" path
  if [ "$kind" = marketplace ]; then
    require_claude_cli
    claude plugin uninstall "open-pr@open-pr"
    say '\nRemoved open-pr from Claude Code. The marketplace entry stays; drop it with:\n'
    say '  claude plugin marketplace remove open-pr\n'
    return 0
  fi
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
$(paths_for "$kind" "$dir")
EOF
}

install_one() {
  local member="$1" kind="$2" dir="$3" path name tmp

  if [ "$kind" = marketplace ]; then
    require_claude_cli
    claude plugin marketplace add "$MARKETPLACE"
    claude plugin install "open-pr@open-pr"
    say '\nInstalled into Claude Code. Commands: /open-pr:review /open-pr:fix /open-pr:upgrade /open-pr:clean\n'
    say 'Update:    claude plugin update open-pr@open-pr\n'
    return 0
  fi

  while IFS= read -r path; do
    if { [ -e "$path" ] || [ -L "$path" ]; } && ! installed_by_us "$path"; then
      printf 'install-local.sh: %s already exists and was not installed by this script — remove it yourself, nothing was written\n' "$path" >&2
      exit 1
    fi
  done <<EOF
$(paths_for "$kind" "$dir")
EOF

  if [ "$kind" = skills ]; then
    mkdir -p -- "$dir"
    for name in "${SKILLS[@]}"; do
      path="$dir/$name"
      rm -rf -- "$path"
      if [ "$MODE" = link ]; then
        ln -s -- "$REPO/skills/$name" "$path"
        say 'linked  %s -> %s\n' "$path" "$REPO/skills/$name"
      else
        cp -R -- "$REPO/skills/$name" "$path"
        # A copy sits outside the clone, so the relative hop to the adapter no longer resolves: bake
        # in the absolute path, and hand ROOT over directly.
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
    mkdir -p -- "$(dirname -- "$dir")"
    rm -rf -- "$dir"
    if [ "$MODE" = link ]; then
      ln -s -- "$REPO" "$dir"
      say 'linked  %s -> %s\n' "$dir" "$REPO"
    else
      mkdir -p -- "$dir"
      # Tracked files only: no .git, no local scratch, nothing the platform has no business reading.
      git -C "$REPO" archive HEAD | tar -x -C "$dir"
      say 'installed by open-pr scripts/install-local.sh from %s — safe to delete\n' "$REPO" >"$dir/$STAMP"
      say 'copied  %s\n' "$dir"
    fi
  fi
  say 'ready   %s\n' "$dir"
}

for member in $MEMBERS; do
  kind="$(platform_kind "$member")"
  dir="${TARGET:-$(platform_dir "$member")}"
  if [ "$ACTION" = uninstall ]; then
    uninstall_one "$member" "$kind" "$dir"
  else
    install_one "$member" "$kind" "$dir"
  fi
done

if [ "$ACTION" = uninstall ]; then
  [ "$SWEEP" = no ] && say '\n%d removed\n' "$removed" || say '\n%d removed across every platform\n' "$removed"
  exit 0
fi

case " $MEMBERS " in
  *" claude "*) ;;
  *)
    say '\nInvoke as /open-pr-review, /open-pr-fix, /open-pr-upgrade, /open-pr-clean (Codex: $open-pr-review).\n'
    if [ "$MODE" = link ]; then
      say 'Update:    git -C %s pull\n' "$REPO"
    else
      say 'Update:    git -C %s pull && %s --copy %s\n' "$REPO" "$0" "$WHERE"
    fi
    say 'Uninstall: %s --uninstall %s\n' "$0" "$WHERE"
    ;;
esac
say 'Also needed: gh (GitHub) or glab (GitLab), installed and logged in — reviews post as that account.\n'
