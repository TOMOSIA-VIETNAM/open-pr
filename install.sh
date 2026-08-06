#!/usr/bin/env bash
# One command to install open-pr on Claude Code, Cursor, Codex, Gemini CLI or Antigravity:
#
#   curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash
#
# All this does is put a clone in ~/.open-pr at the latest release tag and hand over to that clone's
# scripts/install-local.sh, which is what actually installs and is the only place that knows a
# platform's directories. Read it there afterwards; it is the code that ran.
#
# Env: OPEN_PR_HOME (default ~/.open-pr) · OPEN_PR_REF (default: latest release tag; `main` for the
# development branch) · OPEN_PR_REPO (default: this project on GitHub).
#
# Claude Code can also install without any of this: `/plugin marketplace add TOMOSIA-VIETNAM/open-pr`.
#
# This file itself is fetched from the default branch; the tag pinning below applies to the clone it
# leaves behind, which is what actually runs.
set -euo pipefail
# Exactly what a running install needs, and nothing else. The rest of the repository — tests,
# backlogs, the e2e fixture, the docs images, the tooling under scripts/, and CLAUDE.md, which
# instructs an agent editing THIS project — has no business on the disk of someone using the plugin.
# Cursor's IDE is handed this clone as a plugin directory and would index every word of it.
# An include list, not an exclude list: a file added to the repository stays out until named here.
SHIP='/src/ /skills/ /adapters/ /commands/ /.agents/ /.codex-plugin/ /.cursor-plugin/
      /scripts/install-local.sh /gemini-extension.json /plugin.json /LICENSE /README.md'

# Same reason as in install-local.sh: a closed stdout must not abort the install part way.
trap '' PIPE
say() { printf "$@" 2>/dev/null || true; }

# A .git directory alone is not proof it is OURS: someone else's clone parked at ~/.open-pr must be
# refused rather than have its refs moved and its own install script executed. ssh and https spell the
# same project differently, so compare owner/repo — a fork keeps the repository name, and matching on
# that alone would let one through.
slug() { printf '%s\n' "${1%.git}" | sed 's#.*[:/]\([^/:]*/[^/]*\)$#\1#'; }
is_our_clone() {
  local url repo="$2"
  url="$(git -C "$1" remote get-url origin 2>/dev/null)" || return 1
  [ "$url" = "$repo" ] || [ "$(slug "$url")" = "$(slug "$repo")" ]
}

# Everything lives in main so a download cut short cannot execute half a script.
main() {
  local repo="${OPEN_PR_REPO:-https://github.com/TOMOSIA-VIETNAM/open-pr}"
  local home="${OPEN_PR_HOME:-$HOME/.open-pr}"
  local ref="${OPEN_PR_REF:-}"
  local uninstalling=no targeted=no arg tmp=

  for arg in "$@"; do
    case "$arg" in
      --uninstall) uninstalling=yes ;;
      --platform|--all|--target) targeted=yes ;;
    esac
  done

  command -v git >/dev/null || { printf 'install.sh: git is required\n' >&2; exit 1; }

  # Removing needs no update and no particular version: run the installer already on disk, and only
  # borrow a throwaway clone when there is none — someone who deleted ~/.open-pr by hand still has
  # skills pointing at nothing, and this is how they get rid of them.
  if [ "$uninstalling" = yes ]; then
    local runner=
    if [ -d "$home/.git" ] && is_our_clone "$home" "$repo"; then
      runner="$home/scripts/install-local.sh"
    else
      tmp="$(mktemp -d)"
      say 'fetching the uninstaller\n'
      git clone --quiet --depth 1 --sparse --filter=blob:none "$repo" "$tmp/open-pr" 2>/dev/null \
        || git clone --quiet --depth 1 "$repo" "$tmp/open-pr"
      # shellcheck disable=SC2086
      git -C "$tmp/open-pr" sparse-checkout set --no-cone $SHIP 2>/dev/null || true
      runner="$tmp/open-pr/scripts/install-local.sh"
    fi
    "$runner" "$@"
    local rc=$?
    [ -z "$tmp" ] || rm -rf "$tmp"
    # A run that named no platform meant all of it, so the clone goes too. One that named a platform
    # leaves the rest installed, and they need this clone to keep working.
    if [ "$rc" -eq 0 ] && [ "$targeted" = no ] && [ -d "$home/.git" ]; then
      rm -rf "$home"
      say 'removed %s\n' "$home"
    fi
    exit "$rc"
  fi

  if [ -z "$ref" ]; then
    # Highest release tag, so a one-liner never lands on an unreleased commit.
    ref="$(git ls-remote --tags --refs "$repo" 'v[0-9]*' 2>/dev/null \
           | awk -F/ '{print $NF}' | sort -t. -k1.2,1n -k2,2n -k3,3n | tail -1)"
    [ -n "$ref" ] || ref=main
  fi

  # Ask the remote for THIS ref by name and take what came back. `git clone --branch X --depth 1`
  # narrows the clone's fetch refspec to X, so a plain fetch never learns about any other branch or
  # tag, and checking one out fails with "did not match any file(s) known to git". Detaching onto
  # FETCH_HEAD also spares us guessing whether the ref is a tag or needs an origin/ prefix.
  fetch_ref() {
    git -C "$1" fetch --quiet --depth 1 origin "$ref" 2>/dev/null \
      || git -C "$1" fetch --quiet --tags origin "$ref" \
      || return 1
    git -C "$1" checkout --quiet --detach FETCH_HEAD
  }

  if [ -d "$home/.git" ] && is_our_clone "$home" "$repo"; then
    say 'updating %s to %s\n' "$home" "$ref"
    fetch_ref "$home" || {
      printf 'install.sh: %s has no ref named %s — check the name, or rm -rf %s and run again\n' \
        "$repo" "$ref" "$home" >&2; exit 1; }
  elif [ -e "$home" ]; then
    printf 'install.sh: %s exists and is not a clone of open-pr — move it, nothing was written\n' "$home" >&2
    exit 1
  else
    say 'cloning %s at %s into %s\n' "$repo" "$ref" "$home"
    # blob:none leaves the objects behind everything else unfetched until something asks for them.
    # Both flags need a newer git and the filter needs a server offering it, so fall back in order.
    git clone --quiet --branch "$ref" --depth 1 --sparse --filter=blob:none "$repo" "$home" 2>/dev/null \
      || git clone --quiet --branch "$ref" --depth 1 --sparse "$repo" "$home" 2>/dev/null \
      || git clone --quiet --branch "$ref" --depth 1 "$repo" "$home"
    if [ -d "$home/.git" ]; then
      # shellcheck disable=SC2086
      git -C "$home" sparse-checkout set --no-cone $SHIP 2>/dev/null || true
    fi
  fi

  if [ ! -x "$home/scripts/install-local.sh" ]; then
    # The newest release predates this installer. Say so rather than failing on a missing path.
    say 'release %s has no local installer yet — switching to the development branch\n' "$ref"
    git -C "$home" fetch --quiet origin main
    git -C "$home" checkout --quiet FETCH_HEAD
    [ -x "$home/scripts/install-local.sh" ] || {
      printf 'install.sh: %s/scripts/install-local.sh is missing\n' "$home" >&2; exit 1; }
  fi

  say '\nInstalled the plugin files. Next, the platform you run it on.\n'
  say 'Read what does the rest: %s/scripts/install-local.sh\n\n' "$home"
  exec "$home/scripts/install-local.sh" "$@"
}

main "$@"
