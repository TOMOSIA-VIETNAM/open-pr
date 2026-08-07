# Cài đặt

[← README](../../README.vi.md)

Cần [`gh`](https://cli.github.com/) (GitHub) hoặc [`glab`](https://gitlab.com/gitlab-org/cli) (GitLab) — đã cài và đã login. Review post bằng chính account đó.

## Khuyến nghị: cài All

Một lệnh — cài đủ platform (Claude Code, Cursor, Codex, Gemini CLI, Antigravity):

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --platform all
```

> [!TIP]
> Nên dùng **All**. Chỉ xuống bảng dưới khi bạn cố ý muốn đúng một platform.

## Claude Code

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

## Theo từng platform (tuỳ chọn)

| Platform | Install | Use |
| -------- | ------- | --- |
| Cursor | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform cursor` | `/open-pr-review <PR_URL>` |
| Codex | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform shared` | `$open-pr-review <PR_URL>` |
| Gemini CLI | `gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr` | `/review <PR_URL>` |
| Antigravity | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform antigravity` | `/open-pr-review <PR_URL>` |

Không thích pipe? Clone rồi chạy local:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
~/.open-pr/scripts/install-local.sh
```

## Uninstall

Ưu tiên một lệnh curl (gỡ các bản đã cài qua `install.sh`):

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --uninstall
```

| Platform | Command riêng (nếu cần) |
| -------- | ----------------------- |
| Claude Code | `/plugin uninstall open-pr@open-pr` |
| Gemini CLI | `gemini extensions uninstall open-pr` |

## Update

| Platform | Command |
| -------- | ------- |
| Claude Code | `/plugin update open-pr@open-pr` · `/reload-plugins` · `/open-pr:upgrade` |
| Gemini CLI | `gemini extensions update open-pr` |
| Còn lại | `~/.open-pr/scripts/install-local.sh --update` |

Mọi flag: `~/.open-pr/scripts/install-local.sh --help`

---

[Flow re-review / fix](./how-it-works.md) · [Cấu hình](./configuration.md)
