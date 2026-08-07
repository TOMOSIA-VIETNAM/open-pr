# Install

[← README](../README.md)

Needs [`gh`](https://cli.github.com/) (GitHub) or [`glab`](https://gitlab.com/gitlab-org/cli) (GitLab) — installed and logged in. Reviews post as that account.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --platform all
```

Installs Claude Code, Cursor, Codex, Gemini CLI, and Antigravity.

### Claude Code

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

### One platform

| Platform | Install | Use |
| -------- | ------- | --- |
| Cursor | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform cursor` | `/open-pr-review <PR_URL>` |
| Codex | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform shared` | `$open-pr-review <PR_URL>` |
| Gemini CLI | `gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr` | `/review <PR_URL>` |
| Antigravity | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform antigravity` | `/open-pr-review <PR_URL>` |

Without the pipe:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
~/.open-pr/scripts/install-local.sh
```

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --uninstall
```

| Platform | Command |
| -------- | ------- |
| Claude Code | `/plugin uninstall open-pr@open-pr` |
| Gemini CLI | `gemini extensions uninstall open-pr` |

## Update

| Platform | Command |
| -------- | ------- |
| Claude Code | `/plugin update open-pr@open-pr` · `/reload-plugins` · `/open-pr:upgrade` |
| Gemini CLI | `gemini extensions update open-pr` |
| Everything else | `~/.open-pr/scripts/install-local.sh --update` |

Every flag: `~/.open-pr/scripts/install-local.sh --help`

---

[How it works](./how-it-works.md) · [Configuration](./configuration.md)
