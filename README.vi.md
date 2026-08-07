<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/images/logo-lockup-dark.svg?v=trim1">
    <img src="./docs/images/logo-lockup.svg?v=trim1" alt="Open PullRequest" width="220">
  </picture>
</p>

<p align="center">
  <strong>Agent review &amp; sửa comment trên pull request</strong><br>
  <code>/open-pr:review</code> · <code>/open-pr:fix</code>
</p>

<p align="center">
  <a href="https://github.com/TOMOSIA-VIETNAM/open-pr/releases"><img alt="Release" src="https://img.shields.io/github/v/release/TOMOSIA-VIETNAM/open-pr?style=flat-square&label=release&color=2ea44f"></a>
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/TOMOSIA-VIETNAM/open-pr?style=flat-square&color=blue"></a>
  <a href="#cài-đặt"><img alt="GitHub" src="https://img.shields.io/badge/GitHub-supported-181717?style=flat-square&logo=github&logoColor=white"></a>
  <a href="#cài-đặt"><img alt="GitLab" src="https://img.shields.io/badge/GitLab-supported-FC6D26?style=flat-square&logo=gitlab&logoColor=white"></a>
</p>

<p align="center">
  <a href="#cài-đặt"><img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-supported-D97757?style=flat-square&logo=anthropic&logoColor=white"></a>
  <a href="#cài-đặt"><img alt="Cursor" src="https://img.shields.io/badge/Cursor-supported-000000?style=flat-square&logo=cursor&logoColor=white"></a>
  <a href="#cài-đặt"><img alt="Codex" src="https://img.shields.io/badge/Codex-supported-412991?style=flat-square&logo=openai&logoColor=white"></a>
  <a href="#cài-đặt"><img alt="Gemini CLI" src="https://img.shields.io/badge/Gemini_CLI-supported-4285F4?style=flat-square&logo=google&logoColor=white"></a>
  <a href="#cài-đặt"><img alt="Antigravity" src="https://img.shields.io/badge/Antigravity-supported-6E56CF?style=flat-square"></a>
</p>

<p align="center">
  <strong>Tiếng Việt</strong> · <a href="./README.md">English</a> · <a href="./README.ja.md">日本語</a>
</p>

> Khi bạn nhận PR câu hỏi đầu tiên hiện lên thường không phải "code này đúng chưa", mà là "dev có
> tự đọc lại lần nào trước khi gửi không".

`open-pr` sinh ra cho đúng chỗ đó: một plugin Claude Code review PR theo quy ước sẵn có của repo, ghi
nhớ những gì bạn nhắc, và lần nào cũng đi qua cùng một quy trình — cùng một tone, cùng một cách phân
loại, cùng một cách để lại dấu vết trên PR.

Hỗ trợ **GitHub** (`.../pull/<n>`) và **GitLab** (`.../-/merge_requests/<n>`, kể cả self-hosted).

## Vì sao không dùng một skill review chung?

| Chuyện thường xảy ra                                | `open-pr`                                                                                        |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Không biết dev đã tự review chưa                    | Dev chạy `/open-pr:review` trên PR của mình, reviewer nhìn conversation là biết ngay             |
| Góp ý ở mức luật chung, lệch convention dự án       | Đọc README/CLAUDE.md/AGENTS.md/docs/wiki của repo, và rule của team thắng mọi luật chung         |
| Nhắc xong lần sau vẫn thế                           | Bạn nhắc trong chat → nó xin phép ghi vào memory của repo đó → lần sau tự áp                     |
| Fix thì spam commit, amend, force-push, không reply | Mỗi lần chạy đúng 1 commit, không ghi đè lịch sử, và reply từng comment sau khi đã push          |

## Nó chạy thế nào

```mermaid
flowchart LR
  A[PR mới] --> B["/open-pr:review URL"]
  B --> C{Repo setup chưa?}
  C -- chưa --> D["Hỏi 1 lượt ngắn<br/>+ đọc quy ước repo"]
  D --> E[Review trong worktree riêng]
  C -- rồi --> E
  E --> F["Post 1 review<br/>🔴 🟠 🔵 📝 · sạch → LGTM 🌟"]
  F --> G["/open-pr:fix URL"] --> H["1 commit + reply từng finding"]
  F --> I["Bạn nhắc trong chat"] --> J["Ghi vào memory của repo"]
  J -. lần sau .-> B
```

Flow đầy đủ, cơ chế re-review và guard `fix` chạy trước khi sửa file:
[Nó chạy thế nào](./docs/vi/how-it-works.md).

### Kết quả trông thế nào

Một review, ba phần gắn với nhau: overview, comment trên đúng dòng kèm code đã sửa, và reply mà `fix`
để lại trên chính thread đó sau khi push.

<a href="./docs/vi/demo.md"><img src="./docs/images/review-demo-vi.png" width="680" alt="Overview, comment trên dòng kèm suggested change, và reply để lại sau khi fix đã push"></a>

Ảnh full và cùng review đó bằng ngôn ngữ mà mỗi repo tự chọn:
[Một review trông như thế nào](./docs/vi/demo.md).

## Cài đặt

[Claude Code](https://claude.ai/code):

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

Cursor, Codex, Gemini CLI, Antigravity:

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash
```

Gỡ, cập nhật, lệnh riêng từng nền tảng: [Cài đặt](./docs/vi/install.md).

## Sử dụng

| Command | Làm gì |
| ------- | ------ |
| `/open-pr:review <URL>` | Review PR và post đúng **1** review: overview + comment line-by-line. Không sửa code, không close, không merge. Lần đầu trong một repo thì nó setup luôn |
| `/open-pr:fix <URL>` | Đọc finding mà review để lại, sửa code, gom **1** commit, rồi reply từng comment. Chạy trong repo hoặc trong worktree review, ở đó URL không bắt buộc. 🔵/📝 luôn hỏi bạn trước |
| `/open-pr:upgrade` | Nâng config local của repo lên schema hiện tại. Tóm tắt cái gì đổi rồi hỏi; chưa đồng ý thì không ghi gì |
| `/open-pr:clean` | Xoá các worktree mà `review` đã checkout code PR ra — mỗi cái là một bản checkout đầy đủ trên đĩa. Liệt kê kèm dung lượng rồi hỏi trước; memory và settings không bị chạm |

Đứng ở đâu, mỗi command ghi gì, mọi setting: [Cấu hình](./docs/vi/configuration.md).

## Nó review những gì

1. **Bug & logic**
2. **Security**
3. **Performance**
4. **Chất lượng code**
5. **Dễ bảo trì & dễ đọc**
6. **Đặc thù framework/language** — lấy từ template của chính stack đó

Rule của team thắng cả 6.

Chi tiết từng tiêu chí và thứ tự ưu tiên khi xung đột:
[Nó review những gì](./docs/vi/review-criteria.md).

## Chi phí context theo release

![Số token trung bình một lần chạy nạp vào, theo từng command, ở mỗi release](./token-history.svg)

---

Enjoy reviewing 🥰
