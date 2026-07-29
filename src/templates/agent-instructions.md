# Agent instructions (prompts for a model)

_Applies to any file that instructs an AI agent — a `.md` skill/command/CLAUDE.md/AGENTS.md/cursor
rule, or a prompt embedded in code, config or data (`core/stack-detection.md`). NOT a README or docs
written for a human._

#### 1. Bugs & logic

- 2 sections in the same file, or 2 related files, say different things about the same behaviour?
- Branching conditions cover every case, or leave the agent guessing on an unforeseen one?
- Illustrative examples still match the behaviour described (stale example)?
- Embedded: a prompt assembled by concatenation whose result nothing asserts on — an empty or missing
  interpolated value silently ships a broken instruction?

#### 2. Security

- Suggests a destructive command (`rm -rf`, force-push, `reset --hard`…) with no safeguard or
  confirmation attached?
- An example carries a real secret/token/credential instead of a placeholder?
- Data from an untrusted source (user input, PR content, the web) used without stating "this is DATA,
  not an INSTRUCTION"?
- Embedded: an untrusted value interpolated INTO the instruction section, rather than into a clearly
  delimited data section the instructions then refer to?

#### 3. Performance

Prompt text is paid on every run that loads it, so tokens ARE this stack's performance.

- The same rule stated twice — across files, or twice in one file where both copies read as native?
- Content for 1 rare trigger ALWAYS loaded, instead of a file read only when that trigger fires?
- Rationale, history or a "why" essay inside an always-loaded file — dev docs own that?
- Words where notation would be unambiguous: a table for a branch set, an arrow for "leads to"?
- The same sentence shape repeated per case instead of one table?
- A self-verify or re-ask loop with no stopping condition?

#### 4. Code quality

- Recounts the build process or change history where only current behaviour matters?
- A new clause bolted beside the old one instead of the rule being rewritten (patchwork)?
- Narrates "what happened" step by step instead of instructing directly?
- References something ephemeral — task id, branch name, a design doc's section number, internal
  jargon — that a future reader cannot resolve once it is deleted or renamed?

#### 5. Agent-instruction specifics

- Headings clearly leveled, 1 idea each, unrelated topics not crammed together?
- Frontmatter, if any, carries exactly the fields it needs and no legacy ones?
- Conditional content gated into its own file rather than crammed into the always-loaded one?
- Embedded: the prompt text has 1 owner (a constant, a file) instead of being pasted at several call
  sites that will drift apart?
