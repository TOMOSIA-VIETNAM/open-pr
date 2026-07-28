# Makefile

_Additions to the `ALWAYS_RULE.md` baseline; stack-specific criteria only, does not repeat the
baseline._

#### 1. Bugs & logic issues

- Dependencies between targets in the correct order (no missing prerequisite causing a target to
  run before it should)?
- Default target (first target in the file, run by a bare `make`) avoids an unintended hidden side
  effect (e.g. accidentally running `deploy`/`clean` instead of `build`/`help`)?

#### 2. Security

- Downloads a file/script from an external source and executes it immediately without any
  verification?

#### 3. Performance

- Target redoes unnecessary work even when the output is already up-to-date (missing correct file
  target/prerequisite declarations)?
- Good use of parallel builds (`-j`) when targets are independent?

#### 4. Code quality

- Variables (`$(VAR)`) used instead of hardcoding repeated paths/values across multiple targets?
- Duplicated logic between targets avoided — a pattern rule or a shared `include` file for DRY?
- Subcommand exit codes in the recipe checked correctly (not silently swallowing errors with a
  leading `-` before the command, or chaining with a misplaced `;` that lets errors slip through)?

#### 5. Makefile specifics

- `.PHONY` declared for every target that doesn't produce a real file matching the target's name
  (`build`, `test`, `clean`, `deploy`...)?
- Tab/indentation in the recipe correct per Makefile convention (tabs, not spaces)?
- Environment variables/overrides (`?=`, `:=`, `=`) used with the correct semantics?

#### 6. Maintainability & readability

- Target names clear, accurately describing the action?
- Comment explaining complex targets/logic?
- A `help` target listing available commands (helps newcomers use it easily)?
