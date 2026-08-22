# Install

[← README](../README.md)

Needs `git`, [`jq`](https://jqlang.org/) and [`gh`](https://cli.github.com/) (GitHub) or [`glab`](https://gitlab.com/gitlab-org/cli) (GitLab) — installed and logged in. On Windows everything runs in Git Bash (Claude Code already requires Git for Windows); install `jq` with `winget install jqlang.jq`. Bitbucket ships no CLI: it reads an API token from `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN` in the environment. Either way the review is posted through that account — see [Getting a token per vendor](./credentials.md) for the minimum permissions and a command to check them.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash
```

[![Install](./images/install.png)](./images/install.png)

Or:

| Platform | Install | Use |
| -------- | ------- | --- |
| Claude Code | `/plugin marketplace add TOMOSIA-VIETNAM/open-pr`<br>`/plugin install open-pr@open-pr` | `/open-pr:review <PR_URL>` |
| Codex | `codex plugin marketplace add TOMOSIA-VIETNAM/open-pr`<br>`codex plugin add open-pr@open-pr` | `$open-pr-review <PR_URL>` |
| Gemini CLI | `gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr --auto-update` | `/open-pr-review <PR_URL>` |
| Cursor | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform cursor` | `/open-pr-review <PR_URL>` |
| Antigravity | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform antigravity` | `/open-pr-review <PR_URL>` |

## Update

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --update
```

After you reload the plugin, if the new build changes the **schema** a lot, run `/open-pr:upgrade` to bring that repo's settings up to date.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --uninstall
```

[![Uninstall](./images/uninstall.png)](./images/uninstall.png)

---

[Re-review / fix flow](./how-it-works.md) · [Configuration](./configuration.md)
