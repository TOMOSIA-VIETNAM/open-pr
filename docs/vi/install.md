# Cài đặt

[← README](../../README.vi.md)

Cần [`gh`](https://cli.github.com/) (GitHub) hoặc [`glab`](https://gitlab.com/gitlab-org/cli) (GitLab) — đã cài và đã login. Bitbucket không có CLI, nó đọc API token từ `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN` trong biến môi trường. Cách nào thì review cũng post bằng chính account đó — quyền tối thiểu và lệnh tự kiểm tra xem [Lấy token cho từng vendor](./credentials.md).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash
```

[![Install](../images/install.png)](../images/install.png)

Hoặc:

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

Sau khi reload plugin, nếu bản mới đổi nhiều **schema** thì chạy `/open-pr:upgrade` để cập nhật settings của repo.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --uninstall
```

[![Uninstall](../images/uninstall.png)](../images/uninstall.png)

---

[Flow re-review / fix](./how-it-works.md) · [Cấu hình](./configuration.md)
