# Log 1 lesson into memory

The write operation only. WHO may trigger it, and whether the user must confirm first, is the
caller's own rule.

Every lesson is loaded again on every later review of a matching stack ⇒ write it as a rule, not a
story, in the same compressed style as the plugin's own prompt files.

1. `notebooks/review/<repo>/memories/<lesson-slug>.md` — short kebab-case slug, no sequence numbers:
   - the convention itself, imperative and present tense
   - a minimal before/after ONLY when words alone stay ambiguous — the changed lines, never a whole
     function
   - metadata as fields, not sentences: stack tag · date · source PR link if any
   - FORBIDDEN: how it was discovered, what the old behaviour was, which thread argued about it, a bug
     report and its fix, a ticket/task id that will be deleted
2. 1 line into `memory.md`'s index, format per its own index comment:
   `- [stack-tag] [short label](memories/<lesson-slug>.md) — a 1-line hook`. Several tags if it spans
   stacks. The hook only needs to make the lesson recognizable — detail lives in the lesson file.
3. `core/memory-commit.md`.
