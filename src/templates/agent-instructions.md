# Agent Instructions (Markdown)

_Additions to the `ALWAYS_RULE.md` baseline; applies to `.md` files that are instructions meant to
be read and followed by an AI coding agent (skill/command/CLAUDE.md/AGENTS.md/cursor rules...),
does NOT apply to a regular README/docs meant for a human reader._

#### 1. Conflicts & logic errors

- Do 2 sections in the same file (or between this file and a related file) say different things
  about the same behavior?
- Do branching conditions cover every case, or do they leave the agent to guess when it hits an
  unforeseen case?
- Do the illustrative examples in the file still match the real behavior being described (a stale
  example)?

#### 2. Dangerous commands / information leakage through text

- Does it suggest the agent run a destructive command (`rm -rf`, force-push, `reset --hard`...)
  without a safeguard/confirmation attached?
- Do the illustrative examples contain a real secret/token/credential (not a placeholder)?
- Does the file handle data from an untrusted source (user input, PR content, the web) without the
  sentence "this is DATA, not an INSTRUCTION"?

#### 3. Token bloat & overthinking

- Is the same rule repeated across multiple sections/multiple files?
- Is content that applies to only 1 rare trigger ALWAYS-LOADED instead of split into its own case
  (read only when needed)?
- Is a lengthy "why" explanation mixed into the "what to do" section — if this file is always
  loaded at runtime, should the reasoning/history be moved into separate documentation for
  developers to read instead?
- Does it ask the agent to self-verify/re-ask itself repeatedly with no clear stopping condition
  (risk of a loop)?

#### 4. Neutral writing

- Does it recount the build process/change history when only the current behavior needs stating?
- Does it narrate "what happened" (a step-by-step account of what was done) instead of giving
  direct instructions?
- Does it reference something ephemeral/subject to change (a task ID, branch name, a design doc's
  section number, internal jargon) that a future reader won't be able to decipher once that thing
  is deleted/renamed?

#### 5. Markdown structure

- Are headings clearly leveled, each heading covering 1 idea, without cramming multiple unrelated
  topics into one section?
- Does the frontmatter (if any) have exactly the fields it needs, no extra/legacy fields?
- Is conditional content (applying to only some triggers) properly split into its own case/gate,
  rather than crammed into the always-loaded main file?

#### 6. Maintainability & readability

(no additional criteria beyond the shared baseline — see `ALWAYS_RULE.md`)
