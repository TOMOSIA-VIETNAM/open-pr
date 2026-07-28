# Python

#### 1. Bugs & logic

- Mutable default argument (`def f(x=[])`, `def f(x={})`) misused, causing a side effect shared
  across calls?

#### 2. Security

- Input passed directly into a query/command/eval without being checked?
- Exception handling avoids silently swallowing errors (a bare `except:`) that would lose
  security/debugging information?

#### 3. Performance

- N+1 query via ORM (SQLAlchemy/Django) — `select_related`/`prefetch_related` (Django) or
  `joinedload`/`selectinload` (SQLAlchemy) missing?
- Large data handled memory-wastefully (should use a generator/iterator instead of loading
  everything into a list)?

#### 4. Code quality

- Names follow PEP 8?
- Type hints complete for public functions/methods?
- Exception handling specific (catching the exact exception type needed) instead of a bare
  `except:`? Re-raising uses exception chaining (`raise ... from e`) to preserve the original
  traceback?
- Context manager (`with`) used for resources needing closing (file, DB connection, socket)
  instead of manually managing open/close?

#### 5. Python specifics

- `logging` used instead of `print` in production-running code?
- Python idioms used sensibly (list/dict comprehension, unpacking, `enumerate`, `zip`), avoiding
  code that reads like it was translated from another language?
- Package/module structure (imports) clear, avoiding circular imports?

#### 6. Maintainability & readability

- Docstrings complete for complex functions/public APIs?
- Tests use pytest?
