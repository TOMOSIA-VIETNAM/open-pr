# Lấy token cho từng vendor

[← README](../../README.vi.md)

Plugin không có credential riêng: nó đọc PR và post review bằng chính account bạn cấp token, nên review
xuất hiện dưới tên bạn. Mỗi vendor một cách lấy, quyền tối thiểu và lệnh tự kiểm tra nằm ngay dưới.

Chỉ cần làm phần của vendor bạn dùng. Làm một lần cho mỗi máy.

## GitHub

`gh` tự xin đúng quyền, nên đây là đường ngắn nhất:

```bash
brew install gh          # hoặc: https://cli.github.com/
gh auth login            # chọn GitHub.com → HTTPS hoặc SSH → Login with a web browser
gh auth status           # phải thấy "Logged in to github.com as <bạn>"
```

Máy không mở được browser thì dùng token: **Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate new token**, chọn repo cần review, rồi `gh auth login --with-token < file`.

| Quyền tối thiểu (fine-grained) | Để làm gì |
| ------------------------------ | --------- |
| Repository access: các repo bạn review | giới hạn phạm vi, đừng chọn "All repositories" |
| Contents: **Read** | checkout code PR ra worktree để đọc |
| Pull requests: **Read and write** | đọc PR, post review, reply comment |
| Metadata: **Read** | GitHub tự bật kèm, không bỏ được |

Classic token thì tương đương một scope `repo` — rộng hơn nhiều, chỉ nên dùng khi fine-grained không
khả dụng.

Kiểm tra bằng một PR thật:

```bash
gh pr view <URL PR>
```

## GitLab

```bash
brew install glab                                  # hoặc: https://gitlab.com/gitlab-org/cli
glab auth login --hostname gitlab.com              # dán PAT khi được hỏi
glab auth status
```

Tạo PAT: **User settings → Access tokens → Add new token**. Self-hosted thì đổi `--hostname` thành host
của bạn, cùng đường dẫn.

| Quyền tối thiểu | Để làm gì |
| --------------- | --------- |
| Scope `api` | `glab` cần scope này để đọc MR và post note. `read_api` không đủ vì không post được |
| Role trên project: **Developer** trở lên | tạo được note trên MR |

Nên đặt ngày hết hạn ngắn và tạo lại khi cần, thay vì token vĩnh viễn.

Kiểm tra:

```bash
glab mr view <URL MR>
```

## Bitbucket

Bitbucket Cloud không có CLI, nên plugin gọi thẳng REST API và đọc credential từ biến môi trường.
App password đã bị Atlassian tắt hoàn toàn từ 28/07/2026 — chỉ còn đường API token.

**Bước 1 — tạo token.** Vào [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens),
chọn **Create API token with scopes** (không phải "Create API token" thường — loại đó dùng cho
Jira/Confluence và Bitbucket sẽ trả 401), app chọn **Bitbucket**, rồi tick các scope dưới đây.

| Quyền tối thiểu | Để làm gì |
| --------------- | --------- |
| `read:pullrequest:bitbucket` | đọc PR, diff, comment |
| `write:pullrequest:bitbucket` | post comment, reply, resolve thread |
| `read:account` | biết review đang chạy dưới account nào |
| `read:repository:bitbucket` | thêm khi `/diff` hoặc `/statuses` trả 403 |

Copy token ngay khi hiện — đóng cửa sổ là không xem lại được.

**Bước 2 — đặt biến môi trường.** Hai biến: `BITBUCKET_EMAIL` là email của account Atlassian vừa tạo
token (không phải username Bitbucket), `BITBUCKET_API_TOKEN` là token.

Chọn một trong hai cách.

**Cách A — export ở shell.** Dùng được với mọi agent: Claude Code, Codex, Gemini CLI, Antigravity, Cursor.

Mở `~/.zshrc` (zsh, mặc định trên macOS) hoặc `~/.bashrc` (bash) bằng editor, thêm 2 dòng:

```bash
export BITBUCKET_EMAIL="ban@congty.com"
export BITBUCKET_API_TOKEN="token-vua-copy"
```

Nạp lại và kiểm tra:

```bash
source ~/.zshrc          # hoặc ~/.bashrc
printenv BITBUCKET_EMAIL
```

Sửa bằng editor, đừng `echo ... >> ~/.zshrc` — token sẽ nằm lại trong `~/.zsh_history`.

**Cách B — `~/.claude/settings.json`.** Chỉ Claude Code, nhưng không cần mở lại terminal:

```json
{
  "env": {
    "BITBUCKET_EMAIL": "ban@congty.com",
    "BITBUCKET_API_TOKEN": "token-vua-copy"
  }
}
```

Sửa xong thì mở session Claude Code mới, vì settings chỉ đọc lúc khởi động. Chỉ một dự án cần thì đặt vào
`.claude/settings.local.json` của repo đó — file này đã được gitignore.

**Bước 3 — kiểm tra.** Hai lệnh này không in token ra:

```bash
curl -sS --fail-with-body -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "https://api.bitbucket.org/2.0/user?fields=nickname"

curl -sS --fail-with-body -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>?fields=full_name"
```

| Kết quả | Nghĩa |
| ------- | ----- |
| Cả hai trả JSON | xong, dùng được |
| Cả hai `401` | token sai loại (thiếu scope) hoặc email không phải email của Atlassian account |
| Lệnh 1 lỗi, lệnh 2 chạy | thiếu `read:account` |
| `403` | token đúng nhưng thiếu scope cho endpoint đó |

Ngoài ra plugin còn đọc `BITBUCKET_TOKEN` cho repository/workspace access token — loại này gắn với repo
chứ không gắn với người, nên `/user` trả 401 và review hiển thị dưới tên token. Dùng cho tự động hoá;
review hằng ngày nên dùng API token ở trên.

## Push code cần SSH, không phải token

`/open-pr:review` chỉ đọc. `/open-pr:fix` commit rồi push, và trên cả ba vendor token không push được —
cần SSH key trên account:

| Vendor | Thêm key ở |
| ------ | ---------- |
| GitHub | [github.com/settings/keys](https://github.com/settings/keys) |
| GitLab | `https://<host>/-/user_settings/ssh_keys` |
| Bitbucket | [bitbucket.org/account/settings/ssh-keys](https://bitbucket.org/account/settings/ssh-keys/) |

## Giữ token an toàn

Token nằm dạng plaintext ở bất cứ file nào bạn đặt vào, nên:

- `chmod 600` file nào đang giữ token — `~/.zshrc`, `~/.bashrc` hay `~/.claude/settings.json`.
- Đừng đặt token vào `.claude/settings.json` của repo — file đó commit được; dùng bản `settings.local.json`.
- Đừng dán token vào chat, PR hay commit message. Plugin chỉ cần **tên biến**, không cần giá trị.
- Cấp quyền hẹp nhất chạy được và đặt ngày hết hạn. Nghi token bị lộ thì revoke ngay ở đúng trang đã tạo
  nó, rồi tạo cái mới — không có bước nào khác cần làm lại.
