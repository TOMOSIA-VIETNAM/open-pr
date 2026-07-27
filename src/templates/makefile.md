# Makefile

_Additions to the `ALWAYS_RULE.md` baseline; lists only stack-specific criteria, does not repeat
the baseline._

#### 1. Bugs & logic issues

- Are dependencies between targets in the correct order (no missing prerequisite causing a target
  to run before it should)?
- Does the default target (the first target in the file, run by a bare `make`) avoid an unintended
  hidden side effect (e.g. accidentally running `deploy`/`clean` instead of `build`/`help`)?

#### 2. Security

- Does it download a file/script from an external source and execute it immediately without any
  verification?

#### 3. Performance

- Does a target redo unnecessary work even when the output is already up-to-date (missing correct
  file target/prerequisite declarations)?
- Does it make good use of parallel builds (`-j`) when targets are independent?

#### 4. Code quality

- Are variables (`$(VAR)`) used instead of hardcoding repeated paths/values across multiple
  targets?
- Is duplicated logic between targets avoided — should a pattern rule or a shared `include` file
  be used for DRY?
- Are subcommand exit codes in the recipe checked correctly (not silently swallowing errors with a
  leading `-` before the command, or chaining commands with a misplaced `;` that causes errors to
  be ignored)?

#### 5. Makefile specifics

- Is `.PHONY` declared for every target that doesn't produce a real file matching the target's name
  (`build`, `test`, `clean`, `deploy`...)?
- Is the tab/indentation in the recipe correct per Makefile convention (tabs, not spaces)?
- Are environment variables/overrides (`?=`, `:=`, `=`) used with the correct semantics?

#### 6. Maintainability & readability

- Are target names clear, accurately describing the action?
- Is there a comment explaining complex targets/logic?
- Is there a `help` target listing the available commands (helping newcomers use it easily)?
