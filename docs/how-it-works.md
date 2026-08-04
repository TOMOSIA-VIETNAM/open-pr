# How it works

[← README](../README.md)

`review` checks the PR's code out into its own git worktree, so the branch you're on is never touched —
review and keep coding at the same time. And it doesn't only look at what the PR changed: the logic
around it is in scope too, so deadcode and business-logic bugs outside the diff don't slip past.
Anything out of scope that still matters comes back as advice for you to weigh, not as a finding you
must fix.

Type `/open-pr:review` again on the same PR after the dev has fixed or replied and it doesn't review
from scratch — it picks up where the last run left off:

```mermaid
flowchart LR
  A["/open-pr:review URL<br/>(2nd run onward)"] --> B[Re-read each thread<br/>old finding vs current code]
  B --> C{Fixed?}
  C -- yes --> D["Confirm on that exact thread<br/>· resolve if you enabled it"]
  C -- not yet --> E["Leave the open thread alone<br/>no repeat, no duplicate finding"]
  B --> F{Thread settled<br/>on a convention?}
  F -- yes --> G["Asks you first<br/>→ writes it into the repo's memory"]
  A --> H[Review the new diff]
  H --> I{Anything new?}
  I -- yes --> J["Post a new review,<br/>only about what's new"]
  I -- no, and all clear --> K[LGTM 🌟]
  I -- no, findings still open --> L["Post nothing further<br/>the standing review still holds"]
```

A convention settled inside a thread is always confirmed with you rather than remembered on its own:
anyone can write a rule in a comment.

`/open-pr:fix` runs the other way: it reads the very findings `review` left, then edits real code:

```mermaid
flowchart LR
  A["/open-pr:fix URL"] --> B{"On the PR's branch?<br/>not on main/develop?"}
  B -- no --> C["Stops right there<br/>no file touched yet"]
  B -- yes --> D["Read the findings review left<br/>skip threads resolved · handled · settled by the dev"]
  D --> E{Severity?}
  E -- "🔴 🟠 · fix it" --> F["Fix per the repo's<br/>conventions + memory"]
  E -- "🔵 📝 · or the finding looks wrong" --> G["Every open question in exactly 1 round<br/>nothing is edited until you decide"]
  G --> F
  F --> H["Exactly 1 commit<br/>only the files it edited · no amend, no force-push"]
  H --> I{auto_push?}
  I -- "false (default)" --> J["Stops at local<br/>waits for you to say 'push'"]
  I -- true --> K[Push]
  J --> K
  K --> L["A reply per finding: fixed, or why not<br/>never resolves a thread — that stays yours"]
```

Unlike `review` it uses **no** worktree: it edits the real repo on disk. So before touching any file it
checks the place it's about to edit — wrong branch, on `main`/`develop`, or inside the very worktree
`review` created (that one is detached, no branch) all stop it immediately.

## One run at a time, and what you add to it

Commands run only when you type them, and submodules are covered. Extra words after the URL apply to
that run only:

```bash
/open-pr:review https://github.com/org/repo/pull/123 [instructions]
/open-pr:fix    https://github.com/org/repo/pull/123 [instructions]
```

The first run in a repo asks a short batch of questions — the language to post in, post immediately
or keep a draft, whether to auto-resolve fixed threads, how often to re-read the docs, the too-large
PR and file thresholds — then reads the conventions already in the repo: README, CLAUDE.md,
AGENTS.md, docs, wiki.
