# Configuration

[← README](../README.md)

Everything the plugin keeps per repo, and where you change it.

## Where the data lives

Memory, settings and review worktrees for every repo sit in **one data directory** you pick once, outside every repo — no `.gitignore` line, nothing in `git status`.

```
~/workspace/notebooks/review/   ← data directory (your choice)
├── .git                        local history of what it learned
├── repo-backend/               memory + settings + worktrees/
└── repo-frontend/
~/workspace/repo-backend/       ← untouched
```

With no data directory set, the first command asks for one. It recommends `notebooks/review/` in the directory just outside the repo — for `~/workspace/repo-backend`, that is `~/workspace/notebooks/review/` — or takes any path you type. An existing `notebooks/review/` inside the repo is **copied** there (worktrees excluded) and left in place. Later, a repo missing from the data directory gets the same lookup under the directory you stand in, and its `notebooks/review/<repo>/` is offered for import. The choice is stored as `data_dir` in `~/.config/open-pr/config.json` — edit it to point elsewhere.

Where you stand does not change where data goes. A workspace holding several repos still lets you review **cross-repo** PRs in one run (one after another, not in parallel):

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` works from the workspace (it finds the right repo, as long as that repo is on the PR's branch) — or from the worktree `review` already made; there the URL is optional because the session already knows which PR.

## Command

| Command | Where you stand | What it writes |
| --- | --- | --- |
| `/open-pr:review` | workspace holding the repo, or inside the repo — finds it by `git remote` | comments on the PR + memory under `<data>/<repo>/` |
| `/open-pr:fix` | in that repo / workspace holding it — but **the repo must be on the PR's branch** | real code in the repo + replies on the PR |
| `/open-pr:upgrade` | anywhere — every repo in the data directory, or the ones you name | `<data>/<repo>/settings.json` |
| `/open-pr:clean` | anywhere | writes nothing — only deletes `<data>/*/worktrees/*` |
| `/open-pr:feedback` | anywhere | writes nothing locally — one issue on the plugin's own tracker, after you approve the text |

## Setting

`<data>` below is the data directory. Everything learned is indexed in `<data>/<repo>/memory.md` (table of contents — cheap in tokens, still the whole picture). Details live under `<data>/<repo>/memories/*.md`.

> [!NOTE]
> The whole data directory is managed by an **independent local git** — no remote, never pushed. You can follow how memory changed from one review to the next.

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
