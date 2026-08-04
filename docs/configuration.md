# Configuration

[← README](../README.md)

Everything the plugin keeps per repo, and where you change it.

## Where to stand

```
✅ standing in the workspace                 ❌ standing inside the repo
─────────────────────────                    ─────────────────────────
workspace/            ← type here            repo-backend/         ← type here
├── notebooks/review/  memory + worktree     ├── notebooks/review/  memory sits INSIDE the project
│   ├── repo-backend/  outside every repo    ├── .gitignore         +1 line — a real change
│   └── repo-frontend/                       └── src/
├── repo-backend/     ← clean, 0 stray files
└── repo-frontend/    ← clean, 0 stray files (repo-frontend? out of sight)
```

`notebooks/review/` — memory + worktree — is always created right where you type the command. Inside
the repo it lands in your project; the plugin does add one line to `.gitignore` so `git status` stays
clean, but that line is a real change in your repo.

From the workspace the repo is never touched, and because the repos sit side by side it can review
across them — several PRs of one feature in a single run, one after another rather than in parallel.
From inside `repo-backend`, `repo-frontend` is invisible:

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` works from the workspace too — it locates the right repo and edits inside it, as long as
that repo is on the PR's branch.

Everything it remembers is indexed like a table of contents in `notebooks/review/<repo>/memory.md`:
cheap in tokens because no detail has to be loaded, while still giving the whole picture of what has
been learned. The details sit one file at a time under `notebooks/review/<repo>/memories/*.md`. The
whole `notebooks/review/` directory is tracked by its own independent local git — no remote, never
pushed — so you can follow how memory changed from one review to the next.

Your team's own rules go into `ALWAYS_RULE.md` as plain prose (empty by default); everything else
lives in `settings.json`:


| Field                                | Meaning                                                                                | Default              |
| ------------------------------------ | -------------------------------------------------------------------------------------- | -------------------- |
| `shared.chat_language`               | language used in chat                                                                  | auto-detected        |
| `shared.output_language`             | language posted on the PR                                                              | asked once, then kept |
| `review.auto_submit_review`          | `true` = post straight away, `false` = keep a draft for you to look over               | `false`              |
| `review.auto_resolve_fixed_findings` | resolve a thread once its finding is fixed                                             | `false`              |
| `review.doctor_schedule`             | how often the convention docs are re-read: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"` |
| `review.review_ci_status`            | whether to mention failing CI (a warning only, never a demand to fix)                  | CI present ⇒ `true`  |
| `review.many_files_threshold`        | more files than this in a PR ⇒ warn that it's too large                                | `30`                 |
| `review.big_file_threshold_kb`       | a diffed file larger than this is left out of the first read                           | `20`                 |
| `fix.decline_needs_confirmation`     | ask you before declining a finding                                                     | `true`               |
| `fix.auto_push`                      | push automatically after committing                                                    | `false`              |

## What each command writes

| Command | Where you stand when you type it | What it writes |
| ------- | -------------------------------- | -------------- |
| `/open-pr:review` | in the workspace holding the repo (preferred), or in the repo itself — it finds the repo by `git remote` | comments on the PR + memory in `notebooks/review/<repo>/` |
| `/open-pr:fix` | in that repo, or in the workspace holding it — but **the repo must be on the PR's branch** | real code in that repo + replies on the PR |
| `/open-pr:upgrade` | in a workspace or a repo already set up — with several repos it lets you pick | `notebooks/review/<repo>/settings.json` |
| `/open-pr:clean` | anywhere above the `notebooks/review/` it should clean | nothing — it only deletes `notebooks/review/*/worktrees/*` |
