# Backlog: Tách vendor layer (chỉ GitHub, chưa build dispatch)

Mục tiêu: gom ~50 call site `gh api`/`gh pr` rải rác vào 1 file tham chiếu, để sau này thêm vendor
khác (GitLab/Bitbucket) không phải sửa rải rác khắp `review.md`/`fix.md`/`cases/*.md`. KHÔNG xây
detect-vendor-từ-remote, KHÔNG tạo placeholder gitlab.md/bitbucket.md — chưa có vendor thứ 2 thật để
thiết kế abstraction theo (premature-abstraction, user tự nêu rủi ro này).

## Task V1: Soạn `src/vendors/github.md`
- Acceptance:
  - Liệt kê từng thao tác GitHub riêng biệt đang hardcode inline rải rác trong
    `review.md`/`fix.md`/`cases/*.md` (fetch context PR, checkout, post review, reply, resolve
    thread qua GraphQL, reaction...) thành 1 entry tham chiếu mỗi thao tác.
  - Viết theo đúng style DELTA đã chốt ở P1 (file này MỚI, viết thẳng theo convention đó, không
    phải leftover từ trước P1).
- Dependency: checkpoint của `delta-style-rewrite.md` đã qua.
- Status: DONE.

## Task V2: Trỏ `review.md`/`fix.md`/`cases/*.md` về file mới
- Acceptance:
  - Mỗi file command/case `Read` `src/vendors/github.md` tại đúng điểm cần thao tác GitHub, thay
    block lệnh inline bằng tham chiếu + chỉ giữ tham số riêng của điểm gọi (số PR, path...).
  - `allowed-tools` frontmatter trong `review.md`/`fix.md` GIỮ NGUYÊN — chuyển nội dung lệnh sang 1
    file `Read` riêng không đổi quyền tool cần cấp cho lệnh gọi; file vendors không mang frontmatter,
    không phải ranh giới permission riêng.
- Dependency: V1.
- Status: DONE. `allowed-tools` dòng 2 của `review.md`/`fix.md` verify BYTE-IDENTICAL với bản
  trước khi sửa (diff rỗng). 3 lệnh ngắn/dùng đúng 1 nơi (`gh api user --jq .login` trong
  `re-review.md`, reaction trong `re-review.md`, và các lệnh nằm trong block auto-exec `!`...``
  của Context ở `review.md`/`fix.md`) CỐ Ý để inline, không trỏ về vendors/github.md — xem lý do
  trong chính file đó ở từng entry tương ứng.

## Task V3: Bỏ `allowed-tools` — chỉ dùng prose CRITICAL/FORBIDDEN làm lớp chặn
- Quyết định ĐẢO NGƯỢC acceptance của V2 (dòng "allowed-tools GIỮ NGUYÊN" ở trên — giữ lại nguyên
  văn làm lịch sử, không xoá, vì đúng tại thời điểm đó): user tự cân nhắc, chấp nhận đổi rủi ro bảo
  mật (prose-only yếu hơn harness-enforced trước prompt injection) lấy khả năng mở rộng nhiều
  vendor — `allowed-tools` là frontmatter tĩnh, không tham chiếu được sang file khác, nên mỗi vendor
  mới đều phải sửa tay frontmatter `review.md`/`fix.md`, phình dần không giới hạn.
- Acceptance:
  - Xoá dòng `allowed-tools:` khỏi frontmatter `review.md`, `fix.md`, `update-plugin.md`.
  - `CLAUDE.md` Rules cập nhật: rule "gh api scoped, never blanket gh api:*" thay bằng rule mới ghi
    rõ quyết định đảo ngược + WHY + risk accepted, đồng thời nêu rõ 2 rule FORBIDDEN hiện có
    (review.md không close/merge/reopen/branch/push/edit-code; fix.md không --amend/force-push/
    git add -A) giờ là lớp chặn DUY NHẤT, không còn allowed-tools backing.
  - Không đổi nội dung CRITICAL block/FORBIDDEN prose hiện có trong review.md/fix.md — chúng đã đủ
    rõ ràng từ P1, chỉ cần xác nhận còn nguyên vẹn (đã verify).
- Dependency: V2.
- Status: DONE.

## Task V4: Chuyển "Context" từ khối bash tự-exec (`!`...``) sang Step do AGENT tự làm
- Lý do: user chỉ ra khối Context (fetch PR info/diff/comments/CI checks) vẫn còn `gh` hardcode
  inline, vì nó chạy bằng bash tự-exec TRƯỚC KHI agent bắt đầu reasoning — kỹ thuật không cho
  `Read` file khác ở đó được, bất kể có build detect-vendor hay không. User quyết định: đổi hẳn cơ
  chế (chấp nhận tốn thêm vài lượt tool-call/token mỗi lần chạy) để đúng tinh thần "skill cho agent
  làm việc" thay vì rigid tool — agent tự gọi `Bash` cho từng lệnh fetch, y hệt cách Step 1/8/9 đã
  tách vendor thành công trước đó.
- Acceptance:
  - `review.md`/`fix.md` Bước 0: extract `owner`/`repo`/`pull_number` VẪN qua reasoning của agent
    (không dùng bash/heredoc nữa) — CỘNG thêm validate charset `^[A-Za-z0-9_.-]+$` (owner/repo) và
    `^[0-9]+$` (pull_number) NGAY sau khi extract, trước khi dùng bất kỳ giá trị nào trong 1 lệnh
    Bash — vì `[^/]+` của regex URL gốc không tự loại trừ ký tự shell-metachar (backtick, `$`,
    dấu nháy...), nên phải tự chặn thêm lớp này (bù đắp đúng phần bảo vệ mà cơ chế heredoc-quote cũ
    từng làm, giờ không còn heredoc nữa).
  - Mục "## Context" viết lại: fetch qua `Bash` tool thật (không còn khối ```! nào), mỗi lệnh `Read`
    đúng entry tương ứng trong `src/vendors/github.md`.
  - `src/vendors/github.md`: mọi entry trước đây "Catalog only (auto-exec)" cho Context của
    `review.md`/`fix.md` giờ có "Referenced from" thật. Header đầu file xoá đoạn giải thích cơ chế
    auto-exec cũ (không còn đúng).
  - Dọn sạch mọi câu văn còn mô tả Context như đang tự-exec (CLAUDE.md, `submodule-review.md` Step
    D — vốn so sánh với Context CŨ của `review.md`).
  - Marker `ARGUMENTS: $ARGUMENTS` cuối file (`review.md`/`fix.md`) GIỮ NGUYÊN — đây là cách agent
    vẫn nhìn thấy raw arguments để tự extract ở Bước 0, không phụ thuộc khối bash đã xoá.
- Dependency: V3.
- Status: DONE.

## Checkpoint cuối (trước khi merge)
- User tự chạy `/open-pr:review` + `/open-pr:fix` thật trên 1 PR test (A/B tự làm, không tự động
  hoá ở đây) trước khi merge `feat/prompt-architecture-refactor` về `feat/convert_vietnamese_to_english`.

## Thứ tự: V1 → V2 → V3 → V4
