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

  --platform NAME  repeatable, or comma-separated: --platform cursor,shared
                   all          every platform below, Claude Code included
                   claude       Claude Code, through its own `claude plugin` CLI
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
  --all            with --uninstall: sweep every platform above

Skills installed: open-pr-review, open-pr-fix, open-pr-upgrade, open-pr-clean.
Never overwrites a file this script did not create.
EOF
}

# A platform is one directory to write, or a vendor's IDE and CLI taken together.
platform_members() {
  case "$1" in
    all) printf '%s\n' "$ALL_PLATFORMS" ;;
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

ALL_PLATFORMS='claude shared cursor-ide cursor-cli antigravity-cli antigravity-ide'

PLATFORM=
SWEEP=no
TARGET=
MODE=link
ACTION=install

while [ $# -gt 0 ]; do
  case "$1" in
    --platform) [ $# -ge 2 ] || { usage >&2; exit 2; }
                PLATFORM="${PLATFORM:+$PLATFORM }$(printf '%s' "$2" | tr ',' ' ')"; shift 2 ;;
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
if [ -t 0 ]; then ask_on=/dev/stdin
elif { : </dev/tty; } 2>/dev/null; then ask_on=/dev/tty
fi

if [ "$ACTION" != uninstall ] && [ -z "$PLATFORM" ] && [ "$SWEEP" = no ]; then
  if [ -n "$ask_on" ]; then
    say 'Which platform?\n'
    say '  1) Claude Code           its own marketplace, via the claude CLI\n'
    say '  2) Codex or Gemini CLI   skills in ~/.agents/skills\n'
    say '  3) Cursor                IDE and CLI\n'
    say '  4) Antigravity           IDE and CLI\n'
    say '  5) All of them\n'
    say '  6) None of these         exit without writing anything\n'
    printf 'Enter 1-6, several at once (2 3) or empty to exit: '
    read -r choice <"$ask_on" || choice=
    for n in $(printf '%s' "$choice" | tr ',' ' '); do
      case "$n" in
        1) PLATFORM="${PLATFORM:+$PLATFORM }claude" ;;
        2) PLATFORM="${PLATFORM:+$PLATFORM }shared" ;;
        3) PLATFORM="${PLATFORM:+$PLATFORM }cursor" ;;
        4) PLATFORM="${PLATFORM:+$PLATFORM }antigravity" ;;
        5) PLATFORM=all; break ;;
        6) PLATFORM=; break ;;
        *) printf 'install-local.sh: not one of 1-6: %s\n' "$n" >&2; exit 2 ;;
      esac
    done
    [ -n "$PLATFORM" ] || {
      say '\nNothing installed. Re-run when you know which platform, or pass --platform.\n'; exit 0; }
  else
    PLATFORM=shared
    say 'No terminal to ask on — installing the skills for Codex and Gemini CLI.\n'
    say 'Other platforms: --platform claude | cursor | antigravity\n\n'
  fi
fi

resolve_members() {
  MEMBERS=
  if [ "$SWEEP" = yes ]; then
    MEMBERS="$ALL_PLATFORMS"
    return 0
  fi
  local name leaf
  for name in $PLATFORM; do
    for leaf in $(platform_members "$name"); do
      # naming a vendor and one of its halves must not install that half twice
      case " $MEMBERS " in *" $leaf "*) ;; *) MEMBERS="${MEMBERS:+$MEMBERS }$leaf" ;; esac
    done
  done
  if [ -n "$TARGET" ] && [ "$(printf '%s\n' $MEMBERS | wc -w)" -gt 1 ]; then
    printf 'install-local.sh: --target takes one platform; named: %s\n' \
      "$(printf '%s ' $MEMBERS)" >&2
    exit 2
  fi
}

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
  local path="$1" name target
  name="$(basename -- "$path")"
  if [ -L "$path" ]; then
    target="$(readlink -- "$path")"
    case "$target" in
      "$REPO"|"$REPO"/*) return 0 ;;      # into this clone
    esac
    # Into SOME clone of open-pr, laid out the way this script lays one out. Someone who deleted
    # ~/.open-pr by hand still has these links and they are exactly what needs clearing; the shape is
    # specific enough that a link the user made elsewhere does not match it.
    case "$target" in
      */skills/"$name") return 0 ;;
    esac
    # The slot itself is ours by name, so any clone of the project linked into it is ours too — and
    # the default home is ~/.open-pr, whose last segment is not `open-pr`.
    case "$path" in
      */plugins/local/open-pr) case "$target" in *open-pr) return 0 ;; esac ;;
    esac
    return 1
  fi
  [ -f "$path/$STAMP" ] && return 0
  [ -f "$path/SKILL.md" ] && grep -qF -- "$MARKER" "$path/SKILL.md"
}

is_installed() {
  local leaf="$1" kind dir path
  kind="$(platform_kind "$leaf")"
  dir="$(platform_dir "$leaf")"
  if [ "$kind" = marketplace ]; then
    command -v claude >/dev/null || return 1
    # </dev/null: on a terminal the CLI may wait for input, and this only asks a question
    claude plugin list </dev/null 2>/dev/null | grep -q 'open-pr' || return 1
    return 0
  fi
  while IFS= read -r path; do
    { [ -e "$path" ] || [ -L "$path" ]; } && installed_by_us "$path" && return 0
  done <<EOF
$(paths_for "$kind" "$dir")
EOF
  return 1
}

# The CLI failing — not installed, not logged in — must not decide the fate of the other platforms
# in a sweep. Named on its own, the same failure is the answer the user asked for.
claude_failed() {
  if [ "$(printf '%s\n' $MEMBERS | wc -w)" -gt 1 ]; then
    say 'skipped  Claude Code — `claude plugin %s` did not succeed\n' "$1"
    return 0
  fi
  printf 'install-local.sh: `claude plugin %s` failed\n' "$1" >&2
  exit 1
}

# Named on its own, a missing CLI is an error; swept up with everything else, it is a line to skip.
claude_or_skip() {
  command -v claude >/dev/null && return 0
  if [ "$(printf '%s\n' $MEMBERS | wc -w)" -gt 1 ]; then
    say 'skipped  Claude Code — its CLI is not on PATH\n'
    return 1
  fi
  printf 'install-local.sh: the claude CLI is not on PATH — see https://claude.ai/code\n' >&2
  exit 1
}

removed=0

uninstall_one() {
  local member="$1" kind="$2" dir="$3" path
  if [ "$kind" = marketplace ]; then
    claude_or_skip || return 0
    claude plugin uninstall "open-pr@open-pr" || { claude_failed uninstall; return 0; }
    removed=$((removed + 1))
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
    claude_or_skip || return 0
    claude plugin marketplace add "$MARKETPLACE" || { claude_failed "marketplace add"; return 0; }
    claude plugin install "open-pr@open-pr" || { claude_failed install; return 0; }
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
      # Tracked AND checked out: no .git, nothing untracked, and nothing a sparse clone deliberately
      # left out — `git archive HEAD` would put the whole repository back.
      git -C "$REPO" ls-files -z \
        | while IFS= read -r -d '' f; do [ -e "$REPO/$f" ] && printf '%s\0' "$f"; done \
        | tar -C "$REPO" --null -T - -cf - \
        | tar -x -C "$dir"
      say 'installed by open-pr scripts/install-local.sh from %s — safe to delete\n' "$REPO" >"$dir/$STAMP"
      say 'copied  %s\n' "$dir"
    fi
  fi
  say 'ready   %s\n' "$dir"
}

if [ "$ACTION" = uninstall ] && [ -z "$PLATFORM" ] && [ "$SWEEP" = no ]; then
  found=
  for leaf in $ALL_PLATFORMS; do
    is_installed "$leaf" && found="${found:+$found }$leaf"
  done
  [ -n "$found" ] || { say 'open-pr is not installed anywhere this script can see.\n'; exit 0; }

  # Offered the same way the install question offers them: by vendor, not by directory. A vendor
  # whose IDE and CLI are both installed is one line, and picking it removes both.
  labels= ; groups=
  for vendor in claude shared cursor antigravity; do
    members=
    for leaf in $(platform_members "$vendor"); do
      case " $found " in *" $leaf "*) members="${members:+$members }$leaf" ;; esac
    done
    [ -n "$members" ] || continue
    case "$vendor" in
      claude)      label='Claude Code' ;;
      shared)      label='Codex or Gemini CLI' ;;
      cursor)      label='Cursor' ;;
      antigravity) label='Antigravity' ;;
    esac
    where=
    for leaf in $members; do where="${where:+$where, }$(platform_dir "$leaf")"; done
    labels="${labels}${label}|${where}
"
    groups="${groups}${members}
"
  done

  count="$(printf '%s' "$labels" | grep -c '')"
  if [ -n "$ask_on" ]; then
    say 'open-pr is installed here:\n'
    i=0
    while IFS='|' read -r label where; do
      [ -n "$label" ] || continue
      i=$((i + 1))
      say '  %d) %-22s %s\n' "$i" "$label" "$where"
    done <<EOF
$labels
EOF
    say '  %d) All of them\n' "$((count + 1))"
    say '  %d) None of these         exit without removing anything\n' "$((count + 2))"
    printf 'Remove which? (numbers, several at once, empty to exit): '
    read -r choice <"$ask_on" || choice=
    [ -n "$choice" ] || choice="$((count + 2))"
    for n in $(printf '%s' "$choice" | tr ',' ' '); do
      case "$n" in
        ''|*[!0-9]*) printf 'install-local.sh: not a number: %s\n' "$n" >&2; exit 2 ;;
      esac
      if [ "$n" -eq $((count + 2)) ]; then
        say '\nNothing removed.\n'; exit 0
      elif [ "$n" -eq $((count + 1)) ]; then
        PLATFORM="$found"; break
      elif [ "$n" -ge 1 ] && [ "$n" -le "$count" ]; then
        PLATFORM="${PLATFORM:+$PLATFORM }$(printf '%s' "$groups" | sed -n "${n}p")"
      else
        printf 'install-local.sh: not one of 1-%d\n' "$((count + 2))" >&2; exit 2
      fi
    done
  else
    PLATFORM="$found"
    say 'Removing every install found: %s\n' "$found"
  fi
fi

resolve_members
WHERE="--platform $(printf '%s' "$PLATFORM" | tr ' ' ',')"
[ -z "$TARGET" ] || WHERE="$WHERE --target $TARGET"

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
