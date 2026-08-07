# What it reviews

[← README](../README.md)

Six axes. **Team rules always beat** all six.

| # | Criterion | What it looks at |
| --- | --- | --- |
| 1 | **Bugs & logic** | visible logic errors, edge cases (empty / null / boundary), whether conditional branches and error paths are handled |
| 2 | **Security** | hardcoded secrets, unvalidated input going straight into a query / command / render, missing permission checks on sensitive actions |
| 3 | **Performance** | repeated API / DB / computation worth caching or batching, loading a whole large dataset instead of streaming |
| 4 | **Code quality** | naming against the project's convention, duplicated code, one unit doing too much, dead leftovers (commented-out blocks, unused flags / imports, a TODO pointing at a deleted task) |
| 5 | **Maintainability & readability** | comments where the logic isn't obvious and stating what is true now (no recounting the past), tests covering both happy and error paths, a design that leaves room for the next change |
| 6 | **Framework / language-specific** | per-stack templates: Rails, Vue, React, Python, Node.js, Lambda, PHP, Laravel, WordPress, Shell, Makefile, and markdown written as instructions for an AI agent. Unknown stack → writes the template on the spot |

> [!IMPORTANT]
> Priority when they **conflict**: team rules → learned memory → the stack's template → the 5 criteria above. Team rules always win.

---

[What it looks like](./demo.md) · [Configuration](./configuration.md)
