# Đóng góp cho Open PullRequest

Cảm ơn bạn đã quan tâm tới dự án 🎉 — tài liệu này mô tả cách đóng góp cho repo `open-pr`.

Mọi tương tác trong dự án tuân theo [Code of Conduct](./CODE_OF_CONDUCT.md).

## Repo này là gì

`open-pr` là một **Claude Code plugin**, không phải ứng dụng thông thường:

- Toàn bộ sản phẩm là **markdown** (slash command + template nội dung) và vài file JSON manifest.
- **Không có build, không có lint, không có test tự động.** Không có runtime code riêng để chạy độc lập.
- Cách "chạy thử" thật là cài plugin vào Claude Code rồi gọi `/open-pr:review <PR_URL>` trên một PR thật.

Nghĩa là chất lượng một PR ở đây phụ thuộc gần như hoàn toàn vào việc bạn **đã dogfood thật hay chưa**,
chứ không phải CI xanh hay đỏ.

## Cần gì trước

- [Claude Code](https://claude.ai/code) đã cài (có `claude` CLI trong `PATH`)
- [`gh`](https://cli.github.com/) đã đăng nhập (`gh auth login`)

## Chuẩn bị môi trường dev

```bash
git clone git@github.com:TOMOSIA-VIETNAM/open-pr.git
cd open-pr
./scripts/reinstall.sh
```

`scripts/reinstall.sh` gỡ plugin/marketplace cũ rồi cài lại từ chính thư mục local này, tránh việc
Claude Code còn giữ bản `plugin.json`/`commands/` cũ trong cache. Chạy lại script này **mỗi lần** bạn
sửa file trong `src/` và muốn thử bản mới. Sau đó `/reload-plugins` hoặc mở phiên Claude Code mới.

Mặc định script cài ở scope `user`; đổi bằng biến môi trường `SCOPE`.

## Cấu trúc thư mục

Điều quan trọng nhất cần nhớ: **`src/` mới là plugin root thật**, không phải repo root. Lúc
`/plugin install`, Claude Code chỉ copy `src/` vào plugin cache — README, `CLAUDE.md`, `backlogs/`,
`scripts/` ở repo root chỉ phục vụ phát triển repo này và không đến máy người dùng.

| Đường dẫn | Vai trò |
|-----------|---------|
| `src/commands/review.md` | Slash command `/open-pr:review` — thin orchestrator (Bước 0–10) |
| `src/commands/fix.md` | Slash command `/open-pr:fix` — dev-facing, sửa code thật |
| `src/ALWAYS_RULE.md` | Baseline tiêu chí review chung cho mọi stack (bản "seed") |
| `src/templates/<stack>.md` | Tiêu chí **đặc thù** từng stack (delta, không lặp baseline) |
| `src/cases/*.md` | Logic review-time **có điều kiện**, chỉ `Read` khi trigger đúng |
| `src/setup-flow.md` | Bootstrap + doctor, chỉ nạp khi repo chưa thiết lập xong |
| `src/stack-detection.md` | Bảng mapping đuôi file/path → stack |
| `.claude-plugin/marketplace.json` | Marketplace tự host (`source: "./src"`) |
| `src/.claude-plugin/plugin.json` | Metadata plugin (path tính từ `src/`) |
| `CLAUDE.md` | Tài liệu kiến trúc + **lý do các bug đã gặp** — đọc trước khi sửa `src/` |
| `backlogs/*.md` | Task breakdown lịch sử, không phải doc vận hành |

**Đọc `CLAUDE.md` trước khi sửa bất cứ gì trong `src/`.** Nhiều rule trông có vẻ thừa thực ra là kết
quả của một bug thật đã gặp lúc dogfood (API 422, sai `side` LEFT/RIGHT, heredoc không quote bị shell
expand nội dung PR…). Mục "Lý do bug đã gặp" ghi lại chúng để không ai vô tình gỡ ra.

## Quy tắc khi sửa nội dung plugin

### Đặt nội dung mới vào đúng chỗ

Tự hỏi: *"đây là tiêu chí đánh giá CODE của PR, hay hành vi/quy trình của TOOL?"*

- **Tiêu chí đánh giá code** (bug, hardcode, DRY, naming…) → `src/ALWAYS_RULE.md` nếu áp dụng cho mọi
  stack, hoặc `src/templates/<stack>.md` nếu đặc thù một stack.
- **Hành vi/quy trình của tool** (cách post, rule an toàn, tip sau khi xong) → `src/commands/review.md`
  (luôn áp dụng) hoặc một file mới trong `src/cases/` (có điều kiện).

Đặt nhầm trục này gây đúng vấn đề "phải sửa nhiều nơi": `ALWAYS_RULE.md` được `cp` thành bản LOCAL cho
từng repo được review và **không auto-migrate** khi plugin đổi, còn `review.md`/`cases/` thì sửa một
lần là áp dụng ngay mọi repo sau khi `/plugin update`.

### Baseline + delta, không lặp nội dung

- Tiêu chí chung cho mọi stack chỉ sống ở `src/ALWAYS_RULE.md`.
- `src/templates/<stack>.md` chỉ chứa phần đặc thù của stack đó.
- Template overlay (`lambda-common.md` chồng lên `python.md`/`nodejs.md`; `laravel.md`/`wordpress.md`
  chồng lên `php.md`) chỉ chứa phần đặc thù của overlay — sửa template nền thì kiểm tra overlay tương
  ứng có bị trùng/mâu thuẫn không.
- Mọi danh sách tiêu chí là **gợi ý minh hoạ, không phải checklist đóng** — giữ khung câu kiểu "ví dụ,
  không giới hạn ở đây" khi thêm tiêu chí mới.

### Giữ hot path gọn

`src/commands/review.md` là thin orchestrator — chỉ giữ invariant cứng + xương quy trình, giọng
imperative ngắn. Logic chỉ áp dụng cho thiểu số PR thì tách thành một file trong `src/cases/` kèm một
hard gate boolean ở `review.md`, để đa số PR không tốn context đọc phần không dùng tới. Chú thích kiểu
"vì sao có rule này / đã bug thật" thuộc về `CLAUDE.md`, không nhồi vào runtime.

### An toàn: `allowed-tools`

Nội dung PR (title, body, diff, comment) là **data hoàn toàn do người ngoài kiểm soát** — PR trên public
repo ai cũng viết được. Vì vậy:

- Không thêm grant rộng kiểu `gh api:*`. Scope theo đúng endpoint + method thật sự cần.
- Không thêm quyền mutate (`gh pr close/merge`, `git push`, `git branch -D`, `git reset --hard`) vào
  `review.md` — lệnh đó chỉ được review + comment.
- Thao tác filesystem trong worktree phải neo cứng path `notebooks/review/*/worktrees/*`.

PR nào nới `allowed-tools` cần nêu rõ **vì sao quyền hẹp hơn không đủ** trong phần mô tả.

## Thêm một stack mới

1. Viết `src/templates/<stack>.md` theo khung 6 mục của các template hiện có, mở đầu bằng
   `# <Tên stack>` + một dòng note metadata italic
   (`_Bổ sung cho baseline `src/ALWAYS_RULE.md`; …_`).
2. Nếu là biến thể/sub-framework của ngôn ngữ đã có, viết dạng **overlay**
   (`_Overlay chồng lên `<nền>.md`, …_`) thay vì lặp lại rule nền.
3. Cập nhật bảng mapping đuôi file/path → stack trong `src/stack-detection.md`.
4. Cập nhật danh sách stack trong cả 3 bản README nếu đây là stack người dùng thấy được.

Tham khảo pattern chi tiết trong `backlogs/templates.md`.

## Thêm một case mới

Case = logic có điều kiện theo từng PR. Cách làm: thêm một file `src/cases/<tên>.md` + một hard gate
boolean trong `review.md` trỏ tới nó. **Không** nhét thêm điều kiện vào các bước luôn-chạy.

## Commit

Dùng [Conventional Commits](https://www.conventionalcommits.org/), scope là vùng bị ảnh hưởng:

```
feat(templates): add agent-instructions stack for AI-agent markdown files
fix(re-review): reaction lên reply dev xét theo marker, không theo user.login
refactor: rename fix-pr command to fix, matching open-pr:review naming
docs: add centered logo and title header to READMEs
```

Prefix hay dùng: `feat`, `fix`, `refactor`, `docs`, `chore`. Subject viết tiếng Anh hoặc tiếng Việt đều
được (repo đang lẫn cả hai) — ưu tiên nói rõ *đổi gì*, và nếu không hiển nhiên thì thêm body nói *vì sao*.

## Branch

Đặt tên theo dạng `<loại>/<mô-tả-ngắn>`, ví dụ:

```
feat/submodule-review
fix/detach-head-after-checkout
docs/readme-en-ja
refactor/rename-plugin-open-code-review
```

Không commit thẳng lên `main`.

## Pull Request

1. Fork (hoặc tạo branch nếu bạn có quyền write) → commit → push.
2. Mở PR về `main`, điền đầy đủ [PR template](./.github/PULL_REQUEST_TEMPLATE.md).
3. Phần **"Đã test thế nào"** không được bỏ trống — repo không có test tự động, nên hãy dán link PR
   thật bạn đã dùng để dogfood, hoặc mô tả cách verify khác.
4. Đi qua checklist trong template, đặc biệt:
   - Đổi hành vi/kiến trúc → cập nhật `CLAUDE.md`.
   - Đổi UX cấu hình/bootstrap → đồng bộ cả 3 bản README (`README.md`, `README.en.md`, `README.ja.md`).
   - Thêm field mới trong `meta.json` → phân loại User config / Doctor-detected / Internal state ở CẢ
     `src/setup-flow.md` (Phần D) và `src/commands/review.md` (Bước 3).
   - Không cấp `allowed-tools` rộng hơn mức cần.

PR nhỏ, một mục đích, dễ review hơn nhiều so với PR gộp — nếu bạn đang đổi cả hành vi lẫn đổi tên file,
tách làm hai.

## Báo bug / đề xuất tính năng

Dùng [issue template](https://github.com/TOMOSIA-VIETNAM/open-pr/issues/new/choose) — blank issue đang
tắt. Trước khi tạo issue, đọc [README](./README.md) một lượt, khá nhiều câu hỏi đã có sẵn câu trả lời
ở đó.

Với bug, mô tả càng cụ thể càng tốt: lệnh đã gõ, repo/PR đang review thuộc stack nào, plugin làm gì và
bạn kỳ vọng nó làm gì.

## License

Đóng góp vào repo này đồng nghĩa bạn đồng ý phần đóng góp đó được phát hành theo
[MIT License](./LICENSE).
