# PHP (shared base, not framework-specific)

_Additions to the `ALWAYS_RULE.md` baseline; stack-specific criteria only, does not repeat the
baseline._

#### 1. Bugs & logic issues

- Dangerous type juggling — `==` used instead of `===` where strict comparison is needed
  (especially string/number comparisons prone to bugs like `"0" == "abc"`)?
- Error/exception handling avoids using `@` to silently swallow errors?

#### 2. Security

- SQL injection risk — PDO prepared statements/parameter binding used instead of interpolating
  strings directly into the query?
- Output escaped against XSS (`htmlspecialchars` when rendering user data into HTML)?
- Sessions/cookies configured safely (`httponly`, `secure`, `samesite` flags)?

#### 3. Performance

- Unnecessary repeated database queries inside a loop?

#### 4. Code quality

- Autoloading follows the PSR-4/composer standard (avoiding arbitrary manual
  `require`/`include`)?

#### 5. PHP specifics

- Parameter/return type hints fully declared (PHP 7+)?
- Namespace clearly organized, matching the directory structure (PSR-4)?
- Language features used sensibly (null coalescing `??`, arrow functions, match expressions)?

#### 6. Maintainability & readability

- Tests use PHPUnit?
