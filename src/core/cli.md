# CLI — the plugin's deterministic runtime

`<op>` ≡ `"${CLAUDE_PLUGIN_ROOT}"/bin/open-pr.sh`, via the `Bash` tool. It performs every vendor/git
mechanic; commands judge. stdout = data, stderr = diagnostics. FORBIDDEN: `Read`ing the script,
re-implementing a subcommand with raw `gh`/`glab`/`curl`/`git`, or PR-content text as an argument —
bodies travel via files, written with a file-writing tool (never heredoc/echo: they quote
attacker-controlled diff).

Exit ≠ 0 ⇒ act on stderr: 2 = head-SHA gate failed after its one retry (both SHAs + tree path printed) ·
3 = vendor checkout error (e.g. force-pushed source) · 4 = invalid PR URL · 5 = repo dir unresolvable
(candidates on stderr) · 6 = missing credentials (relay the printed setup instructions, STOP) · 1 =
other, with a `hint:` line on post errors.

Common args, elided from the table: `--vendor V --owner O --repo R --pr N` on every networked
subcommand; `--host H` where the vendor is self-hostable.

| subcommand | does |
|---|---|
| `target <url>` | validate + parse → `vendor/owner/repo/pull_number/host` lines |
| `context [--max-patch-bytes B] [--sections s,…]` | fetch in safe order (Head SHA before Diff, sizes before patch), print `## <label>` sections. Default `info,head,files,sizes,diff,commits,comments,ci`; also `reviews,account,threads`. `--max-patch-bytes` required with `diff` — omission happens inside the call |
| `locate-repo --owner O --repo R --host H` | print `<repo_dir>` whose git remote matches |
| `checkout --head-sha S --base B (--repo-dir D \| --worktree W --submodule-path P)` | main: worktree add + PR checkout; submodule: init THAT path + checkout into it. Gates the tree against S (one retry), fetches `origin/<B>` by explicit refspec. Prints `worktree=…` |
| `verify-line --worktree W --path P --line N --side LEFT\|RIGHT --base B` | print that line's REAL content (LEFT = merge-base blob) or `UNCONFIRMABLE <reason>` — the caller judges the match |
| `post --payload F` | create the vendor's unpublished stage. Payload, ONE shape everywhere: `{"body","commit_id","comments":[{"path","line","side","body"}]}`. GitHub prints `review_id=…` |
| `publish [--review-id I] [--payload F]` | make it visible (GitHub needs `--review-id`; Bitbucket re-takes `--payload`, posts overview first) |
| `post-verify [--review-id I] [--marker M]` | what the PR actually shows (Bitbucket needs `--marker` = the finding marker) |
| `reply --comment-id C --body-file F [--kind line\|top] [--thread-id T]` | reply on a thread (`top` = overview-level). GitLab replies into the DISCUSSION — also pass the thread holding C |
| `resolve --thread-id T` | resolve a review thread |
| `react --comment-id C --emoji E` | `NO-EQUIVALENT` on Bitbucket |
| `account` | login name, or `UNKNOWN` (marker-only detection) |
| `commit-url --sha S` | markdown commit link for the overview anchor |
| `marker --kind finding\|reply` | the marker literal — end every finding/reply with it |
| `settings --repo <repo>` | `notebooks/review/<repo>/settings.json` with read-time defaults applied + computed `doctor_due`. Read-only; missing file ⇒ pure defaults |
| `stacks [--repo-dir D] <path>…` | `path<TAB>stack` per file, overlays applied. An `.md` is the caller's judgment: agent-instructions ⇔ the CONTENT instructs an AI agent; prompt text inside code files adds `agent-instructions` on top of the base stack |

Normalized shapes, identical on every vendor: "Old comments" = 1 JSON/line
`{id, body, user, path, line, side, in_reply_to}`; "Review threads" =
`{thread_id, resolved, comment_ids}`; "Reviews" = `NO-EQUIVALENT` where the vendor has no FILE-level
review object — that category then does not apply, LINE handling unaffected.
