# Configuration

[← README](../README.md)

Everything the plugin keeps per repo, and where you change it.

## Where to stand

Memory, settings and review worktrees live in **one place per machine**, never inside a project:

```
~/.open-pr/review/
├── .git/            local history of what was learned — no remote, never pushed
├── repo-backend/    memory.md · memories/ · templates/ · ALWAYS_RULE.md · settings.json · worktrees/
└── repo-frontend/
```

So you can type the command anywhere the repo can be found: inside it, or in a workspace holding it (it is matched by `git remote`). Nothing is written into your projects and no `.gitignore` line is added. A workspace with several repos side by side lets one run review **cross-repo** PRs (one after another, not in parallel):

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` works from the same places (the repo must be on the PR's branch) — or from the worktree `review` already made; there the URL is optional because the session already knows which PR.

> [!NOTE]
> Coming from a build that kept `~/.open-pr/review/` in your workspace: nothing is moved for you. To keep what was learned, move it once — `mkdir -p ~/.open-pr && mv notebooks/review ~/.open-pr/review` — then drop the `~/.open-pr/review/` line from `.gitignore`.

## Command

| Command | Where you stand | What it writes |
| --- | --- | --- |
| `/open-pr:review` | inside the repo, or a workspace holding it — finds it by `git remote` | comments on the PR + memory under `~/.open-pr/review/<repo>/` |
| `/open-pr:fix` | in that repo / workspace holding it — but **the repo must be on the PR's branch** | real code in the repo + replies on the PR |
| `/open-pr:upgrade` | anywhere — upgrades every repo set up, or the ones you name | `~/.open-pr/review/<repo>/settings.json` |
| `/open-pr:clean` | anywhere | writes nothing — only deletes `~/.open-pr/review/*/worktrees/*` |
| `/open-pr:feedback` | anywhere | writes nothing locally — one issue on the plugin's own tracker, after you approve the text |

## Setting

Everything learned is indexed in `~/.open-pr/review/<repo>/memory.md` (table of contents — cheap in tokens, still the whole picture). Details live under `~/.open-pr/review/<repo>/memories/*.md`.

> [!NOTE]
> The whole `~/.open-pr/review/` directory is managed by an **independent local git** — no remote, never pushed. You can follow how memory changed from one review to the next.

Team rules go into `ALWAYS_RULE.md` as plain prose (empty by default). Everything else lives in `settings.json`:

| Field | Meaning | Default |
| --- | --- | --- |
| `shared.chat_language` | language used in chat | auto-detected |
| `shared.output_language` | language posted on the PR | asked once, then kept |
| `review.auto_submit_review` | `true` = post straight away, `false` = hold it for you to look over first — a draft on the PR where the vendor has drafts, and in the chat on Bitbucket, which has none, leaving the PR empty | `false` |
| `review.auto_resolve_fixed_findings` | resolve a thread once its finding is fixed | `false` |
| `review.post_lgtm` | post a clean review (nothing to report) on the PR; `false` keeps it in the chat only | `true` |
| `review.doctor_schedule` | how often to re-read convention docs: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"` |
| `review.review_ci_status` | whether to mention failing CI (warn only, never demand a fix) | CI present ⇒ `true` |
| `review.many_files_threshold` | more files than this in a PR ⇒ warn that it's too large | `30` |
| `review.big_file_threshold_kb` | a diffed file larger than this is left out of the first read | `20` |
| `fix.decline_needs_confirmation` | ask before declining a finding | `true` |
| `fix.auto_push` | push automatically after committing | `false` |

---

[Install](./install.md) · [Re-review / fix flow](./how-it-works.md) · [What it reviews](./review-criteria.md)
