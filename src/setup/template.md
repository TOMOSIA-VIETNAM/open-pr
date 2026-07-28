# Local template for a stack

For EACH stack absent from `.review.templates_copied`:

1. `${CLAUDE_PLUGIN_ROOT}/templates/<stack>.md` exists?
   - **Yes** → `cp "${CLAUDE_PLUGIN_ROOT}/templates/<stack>.md"
     "notebooks/review/<repo>/templates/<stack>.md"` — verbatim copy, FORBIDDEN: Read+Write through
     context. The repo may edit its own copy later without touching the plugin's.
   - **No** (plugin doesn't cover this stack) → author a new one yourself against the 6 axes in
     `core/review-criteria.md`: EVERY bullet must name a concrete API, idiom or tool of THAT stack — a
     bullet merely rephrasing a baseline question belongs to the baseline, not here. Axis 5 is wholly
     yours; drop any axis you have nothing concrete for. Match the tone/detail of
     `${CLAUDE_PLUGIN_ROOT}/templates/`. Save to the
     same local path, then tell the user it was authored and that copying it into
     `${CLAUDE_PLUGIN_ROOT}/templates/` would share it with other repos — the plugin never does that
     itself (no mutating a shared file from one repo's session).
2. Append `<stack>` to `.review.templates_copied`.
3. `core/memory-commit.md`.
