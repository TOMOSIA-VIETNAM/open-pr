# Rails (API + View)

_Additions to the `ALWAYS_RULE.md` baseline; lists only stack-specific criteria, does not repeat
the baseline._

#### 1. Bugs & logic issues

- Is any conditional branch missing?
- Is transaction handling correct (is rollback applied when needed)?

#### 2. Security

- Is there any SQL injection vulnerability (e.g. string interpolation in a `where`)?
- Is there any mass assignment vulnerability (is `permit` configured correctly)?
- Is authentication or authorization checking missing?

#### 3. Performance

- Is there an N+1 query issue?
- Are `includes` / `preload` / `eager_load` used where needed?
- Are `find_each` or `in_batches` used when processing a large dataset?

#### 4. Code quality

- Are method responsibilities properly separated?
- Is the code written in idiomatic Ruby style (`map`, `select`, `each_with_object`, etc.)?
- Is a Rubocop-disable comment explained with a valid reason?

#### 5. Ruby on Rails specifics

- Are ActiveRecord validations appropriate?
- Are scopes and class methods used correctly?
- Are there unintended side effects from callbacks (`before_save`, etc.)?
- Is the split between service classes and concerns reasonable?
- If there's a GraphQL mutation/query, is the type definition correct?
- Were RSpec tests added or updated for the change?

#### 6. Maintainability & readability

- Are constants and mappings defined appropriately?
