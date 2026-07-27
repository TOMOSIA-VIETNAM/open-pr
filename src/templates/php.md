# PHP (shared base, not framework-specific)

_Additions to the `ALWAYS_RULE.md` baseline; lists only stack-specific criteria, does not repeat
the baseline._

#### 1. Bugs & logic issues

- Does dangerous type juggling occur — using `==` instead of `===` where a strict comparison is
  needed (especially string/number comparisons prone to bugs like `"0" == "abc"`)?
- Does error/exception handling avoid using `@` to silently swallow errors?

#### 2. Security

- Is there a SQL injection vulnerability — are PDO prepared statements/parameter binding used
  instead of interpolating strings directly into the query?
- Is output escaped against XSS (`htmlspecialchars` when rendering user data into HTML)?
- Are sessions/cookies configured safely (`httponly`, `secure`, `samesite` flags)?

#### 3. Performance

- Are there unnecessary repeated database queries inside a loop?

#### 4. Code quality

- Does autoloading follow the PSR-4/composer standard (avoiding arbitrary manual
  `require`/`include`)?

#### 5. PHP specifics

- Are parameter/return type hints fully declared (PHP 7+)?
- Is the namespace clearly organized, matching the directory structure (PSR-4)?
- Are language features used sensibly (null coalescing `??`, arrow functions, match expressions)?

#### 6. Maintainability & readability

- Do tests use PHPUnit?
