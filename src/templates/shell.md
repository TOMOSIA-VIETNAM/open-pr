# Shell script (bash/sh)

_Additions to the `ALWAYS_RULE.md` baseline; lists only stack-specific criteria, does not repeat
the baseline._

#### 1. Bugs & logic issues

- Does the script have `set -euo pipefail` at the top (stopping immediately on a failing command,
  an undeclared variable, or a failure inside a pipeline)?
- Is the exit code of important subcommands checked properly (not ignoring `$?` when it matters
  whether the previous command succeeded)?
- Is any conditional branch missing (file doesn't exist, an empty variable)?

#### 2. Security

- Is external input (an argument, env var, another command's output) passed directly into an
  executed command (`eval`, `bash -c`) without being checked?
- Does it use `sudo`/run with more privilege than necessary?

#### 3. Performance

- Are subcommands called repeatedly and unnecessarily inside a loop (should be batched)?
- Is a large file handled in a resource-wasteful way (reading it entirely into a variable instead
  of streaming)?

#### 4. Code quality

- Is variable quoting correct (`"$var"` instead of a bare `$var`, avoiding unintended word
  splitting/glob expansion)?
- Is `[[ ]]` used instead of `[ ]` where possible (bash) to avoid unintended parsing/comparison
  errors?
- Does it avoid parsing `ls` output (should use a glob or `find` directly instead)?
- Should a function be extracted when logic repeats?

#### 5. Shell specifics

- Is the script shellcheck-clean (no serious warnings)?
- Is handling of paths with spaces/special characters correct (quoting, `IFS`,
  `find ... -print0` + `xargs -0` when needed)?
- Is idempotency guaranteed when the script is run multiple times (no duplicated errors/side
  effects if run twice)?

#### 6. Maintainability & readability

(no additional criteria beyond the shared baseline — see `ALWAYS_RULE.md`)
