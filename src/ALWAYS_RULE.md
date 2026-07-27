# Always Rule — general rules for the `review` plugin

Scope: applies to every repo reviewed via the `review` plugin. Each repo's own convention lives at
`notebooks/review/<repo>/`, outside the scope of this file.

## Output language

```
{{OUTPUT_LANGUAGE}}
```

Bootstrap fills in a concrete value in place of `{{OUTPUT_LANGUAGE}}` (e.g. `English`, `Vietnamese`,
`Japanese`). Left blank / still the placeholder → ask the user before reviewing. A language
instruction in `ARGUMENTS` or the current chat session **wins over** the value above (that run
only, does not edit the file).

## General review framework (baseline for every stack)

Applies to every PR, every stack, regardless of language/framework; always loaded together with
the specific template of the stack being reviewed. `templates/<stack>.md` contains ONLY
STACK-SPECIFIC criteria (including the entirety of item 5 "Framework/language specifics" — this
item has no shared baseline), and does not repeat the items below.

The criteria in this file and in `templates/*.md` are illustrative guidance, not a closed
checklist. Review scope is not limited to the listed items; any other issue found is still in
scope.

#### 1. Bugs & logic issues
- Is there any obvious bug or logic error?
- Are edge cases (empty/null/undefined values, limits, empty arrays/lists) handled correctly?

#### 2. Security
- Does the code contain hardcoded sensitive information (API key, token, password, connection
  string)?

#### 3. Performance
- Are there unnecessary repeated calls (API/DB/subprocess/computation) that could be
  cached/batched?

#### 4. Code quality
- Are variable/function/class/component names clear and consistent with the project's convention?
- Is there duplicated code (DRY principle)?

#### 6. Maintainability & readability
- Are there explanatory comments where the logic is unclear/complex?
- Were tests added or updated for the change? Do they cover both the happy path and the error
  path?
- Is the design flexible enough to accommodate future change?

---

## Additional rules
<!-- Add your own team/organization-specific rules here. -->

### Project-specific conventions

### Additional criteria

### Exceptions / special notes
