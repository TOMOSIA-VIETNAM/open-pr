# ROOT + tool names — for every platform except Claude Code

Claude Code never reads this file: it sets `${CLAUDE_PLUGIN_ROOT}` itself. Every other platform reads
this FIRST, resolves `ROOT`, then obeys the command file VERBATIM.

This file is the ONLY place that knows a platform's name. FORBIDDEN here: any review/fix/upgrade/clean
step, severity level, finding marker, `gh`/`glab` invocation, config field. Those live under `ROOT`
and have exactly 1 owner.

## 1 — ROOT

`ROOT` ≡ the directory holding both `commands/review.md` and `core/guardrails.md` — the plugin's
`src/`. In ANY file below `ROOT`, `${CLAUDE_PLUGIN_ROOT}` ≡ `ROOT`.

Resolve with the first method that hits:

| # | when | how |
|---|---|---|
| 1 | whatever sent you here states `ROOT:` + an absolute path | use it verbatim, skip the rest |
| 2 | you know the absolute path of ANY file in this bundle — this one included | RESOLVE SYMLINKS first (`readlink -f`; a skill is usually a link into the clone), then walk up its ancestors → first dir containing `src/commands/review.md` → `ROOT` = that `src` |
| 3 | else | shell: `for d in ~/.open-pr ~/.agents/skills/open-pr-*/../.. ~/.cursor/skills/open-pr-*/../.. ~/.gemini/config/skills/open-pr-*/../.. ~/.gemini/antigravity-cli/skills/open-pr-*/../.. ~/.gemini/extensions/open-pr ~/.cursor/plugins/local/open-pr ~/.claude/plugins/*/open-pr*; do [ -f "$d/src/commands/review.md" ] && (cd "$d/src" && pwd -P); done` — collect the output and dedupe it; `pwd -P` first, or one clone reached by four paths counts as four installs |

Method 3's list and `scripts/install-local.sh`'s own target directories are the same set seen from two
sides; `tests/test_prompt_graph.py` fails when one gains a path the other lacks.

| hits | do |
|---|---|
| 1 | proceed |
| 0 | STOP. Print `open-pr: plugin files not found — reinstall (docs/install.md)`. FORBIDDEN: guessing a path, working from memory of what these commands do, running anything anyway |
| ≥2 | ask the user which one, WAIT for the answer |

## 2 — Tool names

Files below `ROOT` name Claude Code's tools. What binds is the CAPABILITY, not the name:

| file says | use | none available ⇒ |
|---|---|---|
| `Read` | your file-read tool | `cat` / `sed -n` via shell |
| `Grep` | your search tool | `grep -rn` |
| `Glob` | your file-match tool | `ls`, `find` |
| `Write`, `Edit` | your file-write / patch tool | shell heredoc — but FORBIDDEN on a file you have not read in full |
| `Bash` | your shell tool | — |
| `AskUserQuestion` | ask in chat: 1 message, plain text, every option + your recommendation, then WAIT | FORBIDDEN: deciding for the user, or continuing unanswered |
| `Agent` (subagent) | your subagent | do the same work yourself, sequentially, covering EVERY file the step names |

A tool you lack NEVER downgrades to a skipped step: substitute the capability or STOP and say which
step you cannot perform.

## 3 — Platform quirks

| platform | quirk |
|---|---|
| all | `gh` (GitHub) / `glab` (GitLab) must be installed + logged in; the review posts as that account |
| Codex | no subagent, no structured question tool ⇒ §2 rows for `Agent` + `AskUserQuestion` always apply |
| Gemini CLI | `${extensionPath}` is substituted in `gemini-extension.json` and `hooks/hooks.json` ONLY, never in `commands/*.toml` ⇒ a TOML command resolves `ROOT` by method 3 |
| Cursor | skills load from `.agents/skills/`, `~/.agents/skills/`, `.cursor/skills/`, `~/.cursor/skills/` — all equal for this plugin |
| Antigravity | a skill becomes `/<skill-name>` in the TUI; the name is the folder name |
