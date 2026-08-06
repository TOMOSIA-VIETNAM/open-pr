# Cài đặt

Cần [`gh`](https://cli.github.com/) (GitHub) hoặc [`glab`](https://gitlab.com/gitlab-org/cli)
(GitLab), đã cài và đã login — review được post bằng chính account đó.

| Nền tảng | Cài | Dùng | Trạng thái |
| -------- | --- | ---- | ---------- |
| Claude Code | `/plugin marketplace add TOMOSIA-VIETNAM/open-pr`<br>`/plugin install open-pr@open-pr` | `/open-pr:review <PR URL>` | đã test |
| Cursor | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform cursor` | `/open-pr-review <PR URL>` | chưa test |
| Codex | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform shared` | `$open-pr-review <PR URL>` | chưa test |
| Gemini CLI | `gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr` | `/review <PR URL>` | chưa test |
| Antigravity | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform antigravity` | `/open-pr-review <PR URL>` | chưa test |
| Tất cả | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform all` | như trên | — |

`chưa test` = cài được, nhưng chưa ai chạy một review thật qua nền tảng đó.

Không dùng pipe:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
~/.open-pr/scripts/install-local.sh
```

## Gỡ

| Nền tảng | Lệnh |
| -------- | ---- |
| Claude Code | `/plugin uninstall open-pr@open-pr` |
| Gemini CLI | `gemini extensions uninstall open-pr` |
| Còn lại | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --uninstall` |

## Cập nhật

| Nền tảng | Lệnh |
| -------- | ---- |
| Claude Code | `/plugin update open-pr@open-pr` · `/reload-plugins` · `/open-pr:upgrade` |
| Gemini CLI | `gemini extensions update open-pr` |
| Còn lại | `git -C ~/.open-pr pull` |

Mọi cờ: `~/.open-pr/scripts/install-local.sh --help` · [Cách hoạt động](./how-it-works.md) ·
[Cấu hình](./configuration.md)
