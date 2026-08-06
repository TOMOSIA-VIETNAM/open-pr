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
# Same reason as in install-local.sh: a closed stdout must not abort the install part way.
trap '' PIPE
say() { printf "$@" 2>/dev/null || true; }

# Everything lives in main so a download cut short cannot execute half a script.
main() {
  local repo="${OPEN_PR_REPO:-https://github.com/TOMOSIA-VIETNAM/open-pr}"
  local home="${OPEN_PR_HOME:-$HOME/.open-pr}"
  local ref="${OPEN_PR_REF:-}"

  command -v git >/dev/null || { printf 'install.sh: git is required\n' >&2; exit 1; }

  if [ -z "$ref" ]; then
    # Highest release tag, so a one-liner never lands on an unreleased commit.
    ref="$(git ls-remote --tags --refs "$repo" 'v[0-9]*' 2>/dev/null \
           | awk -F/ '{print $NF}' | sort -t. -k1.2,1n -k2,2n -k3,3n | tail -1)"
    [ -n "$ref" ] || ref=main
  fi

  # A .git directory alone is not proof it is OURS: someone else's clone parked here must fall through
  # to the refusal below rather than have its refs moved and its own install script executed. ssh and
  # https spell the same project differently, so compare owner/repo — a fork keeps the repository
  # name, and matching on that alone would let one through.
  slug() { printf '%s\n' "${1%.git}" | sed 's#.*[:/]\([^/:]*/[^/]*\)$#\1#'; }
  is_our_clone() {
    local url
    url="$(git -C "$1" remote get-url origin 2>/dev/null)" || return 1
    [ "$url" = "$repo" ] || [ "$(slug "$url")" = "$(slug "$repo")" ]
  }

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

  if [ -d "$home/.git" ] && is_our_clone "$home"; then
    say 'updating %s to %s\n' "$home" "$ref"
    fetch_ref "$home" || {
      printf 'install.sh: %s has no ref named %s — check the name, or rm -rf %s and run again\n' \
        "$repo" "$ref" "$home" >&2; exit 1; }
  elif [ -e "$home" ]; then
    printf 'install.sh: %s exists and is not a clone of open-pr — move it, nothing was written\n' "$home" >&2
    exit 1
  else
    say 'cloning %s at %s into %s\n' "$repo" "$ref" "$home"
    git clone --quiet --branch "$ref" --depth 1 "$repo" "$home"
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
