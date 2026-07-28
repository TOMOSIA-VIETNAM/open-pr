# Agent Instructions (Markdown)

_Applies to `.md` files that are instructions for an AI coding agent (skill/command/CLAUDE.md/
AGENTS.md/cursor rules…) — NOT a README or docs for a human reader._

#### 1. Bugs & logic

- 2 sections in the same file (or 2 related files) say different things about the same behavior?
- Branching conditions cover every case, or leave the agent to guess on an unforeseen case?
- Illustrative examples still match the real behavior described (stale example)?

#### 2. Security

- Suggests a destructive command (`rm -rf`, force-push, `reset --hard`...) without a
  safeguard/confirmation attached?
- Illustrative examples contain a real secret/token/credential (not a placeholder)?
- Handles data from an untrusted source (user input, PR content, the web) without stating "this is
  DATA, not an INSTRUCTION"?

#### 3. Performance

- Same rule repeated across multiple sections/files?
- Content for only 1 rare trigger ALWAYS-LOADED instead of split into its own case (read only when
  needed)?
- Lengthy "why" mixed into the "what to do" section — if always-loaded at runtime, should the
  reasoning/history move to separate dev docs instead?
- Asks the agent to self-verify/re-ask repeatedly with no clear stopping condition (loop risk)?

#### 4. Code quality

- Recounts the build process/change history when only the current behavior needs stating?
- Narrates "what happened" (step-by-step account) instead of giving direct instructions?
- References something ephemeral (task ID, branch name, a design doc's section number, internal
  jargon) a future reader can't decipher once it's deleted/renamed?

#### 5. Agent-instruction specifics

- Headings clearly leveled, each covering 1 idea, not cramming unrelated topics into one section?
- Frontmatter (if any) has exactly the fields it needs, no extra/legacy fields?
- Conditional content (only some triggers) properly split into its own case/gate, rather than
  crammed into the always-loaded main file?
