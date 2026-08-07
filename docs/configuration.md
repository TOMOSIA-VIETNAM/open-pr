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

`notebooks/review/` (memory + worktree) is always created **right where you type the command**.

| Where you stand | Consequence |
| --- | --- |
| **Workspace** (recommended) | Repo untouched. Repos sit side by side → can review **cross-repo** PRs in one run (one after another, not in parallel) |
| **Inside the repo** | `notebooks/review/` lands in the project. Plugin adds 1 line to `.gitignore` so `git status` stays clean — but that line is still a real change in the repo |

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` works from the workspace (it finds the right repo, as long as that repo is on the PR's branch) — or from the worktree `review` already made; there the URL is optional because the session already knows which PR.

## Command

| Command | Where you stand | What it writes |
| --- | --- | --- |
| `/open-pr:review` | workspace holding the repo (preferred), or inside the repo — finds it by `git remote` | comments on the PR + memory under `notebooks/review/<repo>/` |
| `/open-pr:fix` | in that repo / workspace holding it — but **the repo must be on the PR's branch** | real code in the repo + replies on the PR |
| `/open-pr:upgrade` | workspace or repo already set up — several repos → lets you pick | `notebooks/review/<repo>/settings.json` |
| `/open-pr:clean` | anywhere above the `notebooks/review/` to clean | writes nothing — only deletes `notebooks/review/*/worktrees/*` |

## Setting

Everything learned is indexed in `notebooks/review/<repo>/memory.md` (table of contents — cheap in tokens, still the whole picture). Details live under `notebooks/review/<repo>/memories/*.md`.

> [!NOTE]
> The whole `notebooks/review/` directory is managed by an **independent local git** — no remote, never pushed. You can follow how memory changed from one review to the next.

Team rules go into `ALWAYS_RULE.md` as plain prose (empty by default). Everything else lives in `settings.json`:

| Field | Meaning | Default |
| --- | --- | --- |
| `shared.chat_language` | language used in chat | auto-detected |
| `shared.output_language` | language posted on the PR | asked once, then kept |
| `review.auto_submit_review` | `true` = post straight away, `false` = keep a draft for you to look over | `false` |
| `review.auto_resolve_fixed_findings` | resolve a thread once its finding is fixed | `false` |
| `review.doctor_schedule` | how often to re-read convention docs: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"` |
| `review.review_ci_status` | whether to mention failing CI (warn only, never demand a fix) | CI present ⇒ `true` |
| `review.many_files_threshold` | more files than this in a PR ⇒ warn that it's too large | `30` |
| `review.big_file_threshold_kb` | a diffed file larger than this is left out of the first read | `20` |
| `fix.decline_needs_confirmation` | ask before declining a finding | `true` |
| `fix.auto_push` | push automatically after committing | `false` |

---

[Install](./install.md) · [Re-review / fix flow](./how-it-works.md) · [What it reviews](./review-criteria.md)
