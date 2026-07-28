# Log 1 lesson into memory

The write operation only. WHO may trigger it, and whether the user must confirm first, is the
caller's own rule.

1. `notebooks/review/<repo>/memories/<lesson-slug>.md` — short kebab-case slug, no sequence numbers.
   Minimum content: the convention; a before/after code example if any; stack tag; date; source (link
   to the related PR if any).
2. 1 line into `memory.md`'s index, format per `setup/bootstrap.md`'s skeleton:
   `- [stack-tag] [short label](memories/<lesson-slug>.md) — a 1-line hook`. Several tags if it spans
   stacks. The hook only needs to make the lesson recognizable — detail lives in the lesson file.
3. `core/memory-commit.md`.
