# Always Rule — general rules for the `review` plugin

Scope: every repo reviewed via the `review` plugin. Each repo's own convention lives at
`notebooks/review/<repo>/`, outside this file's scope.

## Output language

```
{{OUTPUT_LANGUAGE}}
```

Bootstrap fills in a concrete value in place of `{{OUTPUT_LANGUAGE}}` (e.g. `English`,
`Vietnamese`, `Japanese`). Blank / still the placeholder → ask the user before reviewing. A
language instruction in `ARGUMENTS`/the current chat session WINS over the value above (that run
only, never edits the file).

## General review framework (baseline for every stack)

Applies to every PR, every stack, regardless of language/framework — ALWAYS loaded together with
the stack's own template. `templates/<stack>.md` contains ONLY STACK-SPECIFIC criteria (including
the entirety of item 5 "Framework/language specifics" — no shared baseline for that item), never
repeats the items below.

Illustrative guidance, not a closed checklist — review scope isn't limited to the listed items;
any other issue found is still in scope.

#### 1. Bugs & logic issues
- Obvious bug or logic error?
- Edge cases (empty/null/undefined, limits, empty arrays/lists) handled correctly?

#### 2. Security
- Hardcoded sensitive info (API key, token, password, connection string)?

#### 3. Performance
- Unnecessary repeated calls (API/DB/subprocess/computation) that could be cached/batched?

#### 4. Code quality
- Variable/function/class/component names clear + consistent with the project's convention?
- Duplicated code (DRY)?

#### 6. Maintainability & readability
- Explanatory comments where the logic is unclear/complex?
- Tests added/updated for the change? Cover both the happy path && the error path?
- Design flexible enough for future change?

---

## Additional rules
<!-- Add your own team/organization-specific rules here. -->

### Project-specific conventions

### Additional criteria

### Exceptions / special notes
