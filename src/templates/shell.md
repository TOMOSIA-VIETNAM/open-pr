# Shell script (bash/sh)

_Additions to the `ALWAYS_RULE.md` baseline; stack-specific criteria only, does not repeat the
baseline._

#### 1. Bugs & logic issues

- `set -euo pipefail` at the top (stops immediately on a failing command, an undeclared variable,
  or a failure inside a pipeline)?
- Exit code of important subcommands checked properly (not ignoring `$?` when it matters whether
  the previous command succeeded)?
- Any conditional branch missing (file doesn't exist, an empty variable)?

#### 2. Security

- External input (an argument, env var, another command's output) passed directly into an executed
  command (`eval`, `bash -c`) without being checked?
- Uses `sudo`/runs with more privilege than necessary?

#### 3. Performance

- Subcommands called repeatedly and unnecessarily inside a loop (should be batched)?
- Large file handled resource-wastefully (reading it entirely into a variable instead of
  streaming)?

#### 4. Code quality

- Variable quoting correct (`"$var"` instead of a bare `$var`, avoiding unintended word
  splitting/glob expansion)?
- `[[ ]]` used instead of `[ ]` where possible (bash) to avoid unintended parsing/comparison
  errors?
- Avoids parsing `ls` output (should use a glob or `find` directly instead)?
- Should a function be extracted when logic repeats?

#### 5. Shell specifics

- shellcheck-clean (no serious warnings)?
- Paths with spaces/special characters handled correctly (quoting, `IFS`, `find ... -print0` +
  `xargs -0` when needed)?
- Idempotency guaranteed when run multiple times (no duplicated errors/side effects if run twice)?

#### 6. Maintainability & readability

(no additional criteria beyond the shared baseline — see `ALWAYS_RULE.md`)
