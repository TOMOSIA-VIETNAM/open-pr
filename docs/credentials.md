# Getting a token per vendor

[← README](../README.md)

The plugin holds no credential of its own: it reads the PR and posts the review through the account whose
token you give it, so the review shows up under your name. Each vendor below has its own way to get one,
its minimum permissions, and a command to check it yourself.

Do only the vendor you use. Once per machine.

## GitHub

`gh` asks for the right permissions itself, so this is the shortest path:

```bash
brew install gh          # or: https://cli.github.com/
gh auth login            # GitHub.com → HTTPS or SSH → Login with a web browser
gh auth status           # must say "Logged in to github.com as <you>"
```

No browser on that machine? Use a token instead: **Settings → Developer settings → Personal access
tokens → Fine-grained tokens → Generate new token**, pick the repos you review, then
`gh auth login --with-token < file`.

| Minimum permission (fine-grained) | What it is for |
| --------------------------------- | -------------- |
| Repository access: the repos you review | keeps the scope narrow — do not pick "All repositories" |
| Contents: **Read** | check the PR code out into a worktree to read it |
| Pull requests: **Read and write** | read the PR, post the review, reply to comments |
| Metadata: **Read** | GitHub enables it alongside and it cannot be turned off |

A classic token needs the single `repo` scope instead — far broader, so keep it for when fine-grained is
not available.

Check it against a real PR:

```bash
gh pr view <PR URL>
```

## GitLab

```bash
brew install glab                                  # or: https://gitlab.com/gitlab-org/cli
glab auth login --hostname gitlab.com              # paste the PAT when asked
glab auth status
```

Create the PAT under **User settings → Access tokens → Add new token**. Self-hosted works the same way
with your own host in `--hostname`.

| Minimum permission | What it is for |
| ------------------ | -------------- |
| Scope `api` | `glab` needs it to read MRs and post notes. `read_api` is not enough — it cannot post |
| Role on the project: **Developer** or above | allowed to create notes on an MR |

Prefer a short expiry and a fresh token when it runs out, over a token that never expires.

Check it:

```bash
glab mr view <MR URL>
```

## Bitbucket

Bitbucket Cloud has no CLI, so the plugin calls the REST API directly and reads the credential from the
environment. App passwords were switched off by Atlassian on 2026-07-28, which leaves the API token.

**Step 1 — create the token.** Go to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
and choose **Create API token with scopes** — not plain "Create API token", which is for Jira and
Confluence and makes Bitbucket answer 401. Pick **Bitbucket** as the app, then tick the scopes below.

| Minimum permission | What it is for |
| ------------------ | -------------- |
| `read:pullrequest:bitbucket` | read the PR, its diff and its comments |
| `write:pullrequest:bitbucket` | post comments, reply, resolve a thread |
| `read:account` | know which account the review runs as |
| `read:repository:bitbucket` | add it when `/diff` or `/statuses` answers 403 |

Copy the token while it is on screen — closing the dialog is final.

**Step 2 — set the environment variables.** Two of them: `BITBUCKET_EMAIL` is the email of the Atlassian
account that created the token (not the Bitbucket username), `BITBUCKET_API_TOKEN` is the token.

| Where | Suits |
| ----- | ----- |
| `~/.claude/settings.json`, `env` block | every Claude Code session, no terminal to reopen — the one to prefer |
| `~/.zshrc` / `~/.bashrc` | you want it in an ordinary terminal too |
| a repo's `.claude/settings.local.json` | only one project needs it, and that file is already gitignored |

```json
{
  "env": {
    "BITBUCKET_EMAIL": "you@company.com",
    "BITBUCKET_API_TOKEN": "the-token-you-copied"
  }
}
```

After editing `~/.claude/settings.json`, start a new Claude Code session — settings are read at startup.

**Step 3 — check it.** Neither command prints the token:

```bash
curl -sS --fail-with-body -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "https://api.bitbucket.org/2.0/user?fields=nickname"

curl -sS --fail-with-body -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>?fields=full_name"
```

| Result | Means |
| ------ | ----- |
| Both return JSON | done, it works |
| Both `401` | wrong kind of token (no scopes), or that email is not the Atlassian account's |
| First fails, second works | `read:account` is missing |
| `403` | the token is valid but lacks the scope for that endpoint |

The plugin also reads `BITBUCKET_TOKEN`, for a repository or workspace access token. That kind belongs to
a repo rather than a person, so `/user` answers 401 and the review appears under the token's name — good
for automation, while day-to-day reviews are better off with the API token above.

## Pushing needs SSH, not a token

`/open-pr:review` only reads. `/open-pr:fix` commits and pushes, and on all three vendors a token cannot
push — the account needs an SSH key:

| Vendor | Add the key at |
| ------ | -------------- |
| GitHub | [github.com/settings/keys](https://github.com/settings/keys) |
| GitLab | `https://<host>/-/user_settings/ssh_keys` |
| Bitbucket | [bitbucket.org/account/settings/ssh-keys](https://bitbucket.org/account/settings/ssh-keys/) |

## Keeping a token safe

A token sits in plaintext in whichever file you put it in, so:

- `chmod 600 ~/.claude/settings.json` after editing it.
- Keep it out of a repo's `.claude/settings.json`, which is committable — use `settings.local.json`.
- Never paste it into a chat, a PR or a commit message. The plugin needs the variable's **name**, never
  its value.
- Grant the narrowest set that works and give it an expiry. If you suspect a leak, revoke it on the same
  page that created it and make a new one — nothing else needs redoing.
