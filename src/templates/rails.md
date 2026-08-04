# Rails (API + View)

#### 1. Bugs & logic

- Transaction handling correct (rollback applied when needed)?

#### 2. Security

- SQL injection risk (e.g. string interpolation in a `where`)?
- Mass assignment risk (`permit` configured correctly)?
- Authentication or authorization checking missing?

#### 3. Performance

- N+1 query — `includes`/`preload`/`eager_load` missing where needed?
- `find_each` or `in_batches` used when processing a large dataset?

#### 4. Code quality

- Idiomatic Ruby style (`map`, `select`, `each_with_object`, etc.)?
- Rubocop-disable comment explained with a valid reason?

#### 5. Ruby on Rails specifics

- ActiveRecord validations appropriate?
- Scopes and class methods used correctly?
- Unintended side effects from callbacks (`before_save`, etc.)?
- Split between service classes and concerns reasonable?
- GraphQL mutation/query present → type definition correct?

#### 6. Maintainability & readability

- Constants and mappings defined appropriately?
- Tests use RSpec?
