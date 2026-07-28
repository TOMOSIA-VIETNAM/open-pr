# Rails (API + View)

_Additions to the `ALWAYS_RULE.md` baseline; stack-specific criteria only, does not repeat the
baseline._

#### 1. Bugs & logic issues

- Any conditional branch missing?
- Transaction handling correct (rollback applied when needed)?

#### 2. Security

- SQL injection risk (e.g. string interpolation in a `where`)?
- Mass assignment risk (`permit` configured correctly)?
- Authentication or authorization checking missing?

#### 3. Performance

- N+1 query issue?
- `includes` / `preload` / `eager_load` used where needed?
- `find_each` or `in_batches` used when processing a large dataset?

#### 4. Code quality

- Method responsibilities properly separated?
- Idiomatic Ruby style (`map`, `select`, `each_with_object`, etc.)?
- Rubocop-disable comment explained with a valid reason?

#### 5. Ruby on Rails specifics

- ActiveRecord validations appropriate?
- Scopes and class methods used correctly?
- Unintended side effects from callbacks (`before_save`, etc.)?
- Split between service classes and concerns reasonable?
- GraphQL mutation/query present → type definition correct?
- RSpec tests added/updated for the change?

#### 6. Maintainability & readability

- Constants and mappings defined appropriately?
