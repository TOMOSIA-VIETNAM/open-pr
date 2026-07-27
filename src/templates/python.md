# Python

_Additions to the `ALWAYS_RULE.md` baseline; lists only stack-specific criteria, does not repeat
the baseline._

#### 1. Bugs & logic issues

- Is a mutable default argument (`def f(x=[])`, `def f(x={})`) misused, causing a side effect
  shared across calls?
- Is any conditional branch/exception left unhandled?

#### 2. Security

- Secrets should be configured via environment variables instead of hardcoded.
- Is any input passed directly into a query/command/eval without being checked?
- Does exception handling avoid silently swallowing errors (a bare `except:`) that would lose
  security/debugging information?

#### 3. Performance

- Is there an N+1 query issue when using an ORM (SQLAlchemy/Django) — is
  `select_related`/`prefetch_related` (Django) or `joinedload`/`selectinload` (SQLAlchemy)
  missing?
- Is large data handled in a memory-wasteful way (should use a generator/iterator instead of
  loading everything into a list)?
- Is there unnecessary repeated computation that could be cached (`functools.lru_cache`)?

#### 4. Code quality

- Are type hints complete for public functions/methods?
- Is exception handling specific (catching the exact exception type needed) instead of a bare
  `except:`? When re-raising, is exception chaining used (`raise ... from e`) to preserve the
  original traceback?
- Is a context manager (`with`) used for resources that need closing (file, DB connection, socket)
  instead of manually managing open/close?

#### 5. Python specifics

- Is `logging` used instead of `print` in production-running code?
- Are docstrings complete for complex functions/public APIs?
- Are Python idioms used sensibly (list/dict comprehension, unpacking, `enumerate`, `zip`),
  avoiding code that reads like it was translated from another language?
- Is the package/module structure (imports) clear, avoiding circular imports?

#### 6. Maintainability & readability

- Do variable/function/class names follow PEP 8?
- Do tests use pytest?
