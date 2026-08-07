# Cài đặt

[← README](../../README.vi.md)

Cần [`gh`](https://cli.github.com/) (GitHub) hoặc [`glab`](https://gitlab.com/gitlab-org/cli) (GitLab) — đã cài và đã login. Review post bằng chính account đó.

> [!NOTE]
> Một lệnh `curl … | bash` trên README cài nhanh cho Cursor / Codex / Gemini CLI / Antigravity. Bảng dưới là lệnh **theo từng platform** nếu muốn chọn riêng.

| Platform | Install | Use | Status |
| -------- | ------- | --- | ------ |
| Claude Code | `/plugin marketplace add TOMOSIA-VIETNAM/open-pr`<br>`/plugin install open-pr@open-pr` | `/open-pr:review <PR_URL>` | tested |
| Cursor | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform cursor` | `/open-pr-review <PR_URL>` | untested |
| Codex | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform shared` | `$open-pr-review <PR_URL>` | untested |
| Gemini CLI | `gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr` | `/review <PR_URL>` | untested |
| Antigravity | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform antigravity` | `/open-pr-review <PR_URL>` | untested |
| All | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform all` | như trên | — |

`untested` = cài được, nhưng chưa ai chạy một review thật qua platform đó.

Không thích pipe? Clone rồi chạy local:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
~/.open-pr/scripts/install-local.sh
```

## Uninstall

| Platform | Command |
| -------- | ------- |
| Claude Code | `/plugin uninstall open-pr@open-pr` |
| Gemini CLI | `gemini extensions uninstall open-pr` |
| Còn lại | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --uninstall` |

## Update

| Platform | Command |
| -------- | ------- |
| Claude Code | `/plugin update open-pr@open-pr` · `/reload-plugins` · `/open-pr:upgrade` |
| Gemini CLI | `gemini extensions update open-pr` |
| Còn lại | `~/.open-pr/scripts/install-local.sh --update` |

Mọi flag: `~/.open-pr/scripts/install-local.sh --help`

Tiếp theo: [Flow re-review / fix](./how-it-works.md) · [Cấu hình](./configuration.md)
