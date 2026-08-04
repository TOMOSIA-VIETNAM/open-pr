# Backlog: Multi-vendor support — add GitLab (Bitbucket deferred)

Mục tiêu: xoá bỏ hẳn việc `review.md`/`fix.md`/`cases/*.md` nhắc cứng "GitHub"/`gh` trong PROSE
(vendor file `src/vendors/github.md` đã tách xong lệnh cụ thể ở backlog trước — task ở đây là làm
cho phần PROSE gọi tới nó cũng hết cứng-GitHub). Thêm GitLab làm vendor thứ 2 thật. Mục tiêu cuối:
thêm vendor thứ 3 trở đi sau này = thêm 1 file `src/vendors/<tên>.md`, KHÔNG sửa `review.md`/
`fix.md`/`cases/*.md` nữa.

**Bitbucket KHÔNG làm ở backlog này** — quyết định hoãn có lý do rõ (xem research trước khi viết
backlog): không có CLI chính thức (mọi thao tác phải tự `curl`/REST), không có khái niệm "review
object" ở tầng API (batched comment chỉ là tính năng UI, mỗi comment POST public ngay), và đúng
thời điểm viết backlog này Bitbucket đang giữa đợt khai tử App Password (chuyển sang API Token) —
chờ ổn định + làm riêng sau, không gộp chung rủi ro auth-migration vào đợt này.

**Phát hiện quan trọng nhất từ research, MỌI task dưới đây phải tôn trọng:** khái niệm "review"
kiểu GitHub (1 object gộp overview + nhiều inline comment, trạng thái PENDING→SUBMITTED, có
`review_id`) KHÔNG tồn tại nguyên vẹn ở GitLab. GitLab dùng Draft Notes (nhiều note riêng lẻ, publish
hàng loạt qua `bulk_publish`, không có `review_id`/state tường minh). Thao tác "post/verify/submit
review" (3 mục trong `vendors/github.md`) PHẢI được coi là **composite operation mỗi vendor tự mô tả
số bước + cơ chế riêng của mình** — TUYỆT ĐỐI không ép GitLab đi qua đúng 3 bước post→verify→submit
y hệt GitHub. `review.md` Bước 9 phải viết đủ trung lập để chấp nhận điều này (xem Task G6).

## Task G1: Thêm field `git_remote_type` vào `settings.json`
- Acceptance:
  - `shared` node thêm field `git_remote_type`: `"github"` | `"gitlab"` (giá trị hợp lệ CHỈ 2 cái
    này ở giai đoạn này — chưa có `"bitbucket"`).
  - `src/setup-flow.md` Phần A: câu hỏi bootstrap MỚI hỏi `git_remote_type`. Auto-suggest default
    bằng cách soi hostname của PR URL đã nhập (`github.com` → recommend `"github"`; `gitlab.com` →
    recommend `"gitlab"`; hostname khác (self-hosted GitLab/GitHub Enterprise...) → KHÔNG có default
    tin cậy, hỏi thẳng không gợi ý — vì instance tự host không suy được từ hostname).
  - `src/setup-flow.md` Phần D: phân loại field này vào nhóm "User config" (giống
    `auto_submit_review` — hỏi 1 lần lúc bootstrap, đổi được qua "reconfigure review").
  - `llm-upgrades/index.md` + `llm-upgrades/v3.md` MỚI: migration cho repo đã bootstrap trước khi
    field này tồn tại — mặc định `git_remote_type: "github"` (100% repo đã dùng plugin tới giờ đều
    là GitHub, an toàn giả định vậy cho dữ liệu cũ). Bump `schema_version` lên 3.
- Dependency: không (task đầu).
- Status: DONE. `shared.git_remote_type` thêm vào Part A (câu hỏi bootstrap MỚI, đặt làm câu #1,
  đẩy tổng số câu hỏi bootstrap từ "6 hoặc 7" → "7 hoặc 8") + Part D (schema JSON, field-groups —
  thêm nhóm thứ 6 "User config, `.shared` node"). `llm-upgrades/v3.md` MỚI tạo (default `"github"`
  cho repo cũ) + `llm-upgrades/index.md` thêm dòng `v3`. Lưu ý: phần "bump schema_version" sau đó
  đã được nâng cấp thêm (không phải do task này, xảy ra song song trong lúc làm) thành cơ chế
  DYNAMIC — `setup-flow.md`/`fix.md` giờ tự fetch `llm-upgrades/index.md` live và lấy `N` cao nhất,
  không còn literal `3` hard-code trong instruction (chỉ còn literal trong JSON schema VÍ DỤ minh
  hoạ ở Part D) — tốt hơn dự tính ban đầu, tránh đúng lỗi "con số sẽ lỗi thời" nêu trong nguyên tắc
  chung của user.
  **Lệch nhỏ so với acceptance gốc (cố ý, đã cân nhắc):** acceptance viết default suy từ HOSTNAME
  literal (`github.com`/`gitlab.com`, self-hosted → không default). Bản final dùng PATH-SHAPE guess
  (từ Task G2's Step 0, `/pull/` vs `/-/merge_requests/`) làm default thay vì hostname — vì
  path-shape LUÔN suy được kể cả self-hosted (hostname không suy được), giải quyết đúng gap mà
  acceptance gốc còn để hở ("self-hosted → hỏi thẳng không gợi ý"). Coi đây là superseded bởi
  cơ chế Task G3 mô tả ("dùng preliminary guess làm default, không hỏi 2 lần") — không còn case
  "không có default" nữa. Nếu user muốn giữ đúng hostname-only literal, cần chỉnh lại.

## Task G2: Generic hoá URL pattern ở Step 0 (`review.md`/`fix.md`)
- Acceptance:
  - Regex validate URL ở Bước 0 đổi từ CHỈ-GitHub (`https://github\.com/.../pull/[0-9]+`) sang
    UNION nhận diện được CẢ 2 dạng: GitHub PR (`https://github\.com/[^/]+/[^/]+/pull/[0-9]+`) VÀ
    GitLab MR (`https://[^/]+/[^/]+/[^/]+/-/merge_requests/[0-9]+` — hostname bất kỳ vì self-hosted
    phổ biến với GitLab, path luôn có `/-/merge_requests/`).
  - Match được → suy ra `owner`/`repo`/`pull_number` (đổi tên khái niệm nội bộ nếu cần — "PR" vẫn
    dùng làm nhãn chung xuyên suốt code, theo đúng quyết định đã chốt) + 1 "preliminary vendor guess"
    từ CHÍNH hình dạng URL (`/pull/` → guess `github`; `/-/merge_requests/` → guess `gitlab`).
  - Validate charset `owner`/`repo`/`pull_number` GIỮ NGUYÊN (đã có từ backlog trước) — áp dụng cho
    CẢ 2 dạng URL như nhau.
  - `argument-hint` + mọi thông báo lỗi/ví dụ dùng "PR URL" chung (không còn "GitHub PR URL") — ví
    dụ lỗi nên có cả 2 ví dụ (1 dòng GitHub, 1 dòng GitLab) để user biết cả 2 dạng được chấp nhận.
- Dependency: G1.
- Status: DONE. Union regex áp vào `review.md` + `fix.md` Step 0, đúng 2 shape backlog ghi (GitHub
  literal `github\.com`, GitLab hostname bất kỳ). Preliminary vendor guess (`<vendor_guess>`) suy từ
  chính nhánh regex khớp. `argument-hint`/usage/example đổi sang "PR URL" chung, mỗi lỗi kèm 2 ví dụ
  (GitHub + GitLab). Grep "GitHub PR URL" toàn `src/` = 0 hit (xem Task G8).

## Task G3: Đối chiếu preliminary vendor guess với `git_remote_type` đã lưu
- Acceptance:
  - Sau khi Bước 3 đọc được `settings.json` (`.shared.git_remote_type`), MUST đối chiếu với
    preliminary guess từ Bước 0 (Task G2). Khớp → dùng luôn giá trị đã lưu, không hỏi lại. LỆCH
    (vd repo lưu `"github"` nhưng URL đưa vào lại có hình dạng GitLab MR) → MUST dừng, hỏi user xác
    nhận giá trị nào đúng trước khi tiếp tục — KHÔNG tự ý chọn 1 trong 2.
  - Repo MỚI (chưa bootstrap) → preliminary guess từ Bước 0 dùng làm default cho câu hỏi bootstrap
    ở Task G1, không hỏi 2 lần trùng ý.
- Dependency: G2.
- Status: DONE, nhưng có 1 LỆCH KIẾN TRÚC cố ý so với chữ acceptance, cần user xác nhận lại: logic
  đối chiếu KHÔNG đặt ở đúng "Bước 3" như acceptance viết — đặt ở **Context** (`review.md`, ngay sau
  Step 0, TRƯỚC Step 1) vì Context đã cần gọi vendor file (`Read vendors/<type>.md`) SỚM HƠN Bước 3
  chạy — để Bước 3 làm việc đối chiếu thì Context đã lỡ dùng sai vendor file trước đó rồi. Đã dời
  toàn bộ substance của rule này lên Context, Bước 3 giờ chỉ còn việc PERSIST giá trị đã resolve
  (ghi `.shared.git_remote_type`). `fix.md` KHÔNG có bước tương đương Bước 3 của `review.md` (không
  có bootstrap review) → cố ý ĐƠN GIẢN HOÁ: `fix.md` luôn dùng preliminary guess trực tiếp, KHÔNG
  đối chiếu với `settings.json` (lý do: URL shape tự nó đã đủ tin cậy để chọn đúng vendor cho ĐÚNG
  PR này, và `settings.json` có thể chưa tồn tại ở lần `/open-pr:fix` đầu tiên). Đây là quyết định
  tự đưa ra, ngoài phạm vi chữ acceptance gốc — nói rõ trong báo cáo cuối, user nên xác nhận có OK
  không.

## Task G4: Generic hoá đường dẫn vendor file — thay MỌI chỗ hardcode `vendors/github.md`
- Acceptance:
  - Từng chỗ hiện đang viết cứng `Read "${CLAUDE_PLUGIN_ROOT}"/vendors/github.md` (trong
    `review.md`, `fix.md`, `src/cases/re-review.md`, `src/cases/post-review.md`,
    `src/cases/submodule-review.md`) đổi thành: `Read` file tại đường dẫn
    `"${CLAUDE_PLUGIN_ROOT}"/vendors/<git_remote_type>.md`, với `<git_remote_type>` = giá trị đã
    xác nhận ở Task G3 (agent tự thay thế bằng giá trị thật khi đọc, không phải cú pháp template
    của harness).
  - KHÔNG đổi TÊN entry được tham chiếu bên trong (vd "Fetch PR basic info" vẫn giữ y hệt tên đó) —
    chỉ đổi đường dẫn FILE, tên entry là interface chung xuyên vendor (quyết định đã chốt: giữ "PR"
    làm nhãn chung, mỗi vendor file tự map thuật ngữ riêng bên trong).
- Dependency: G1 (cần field tồn tại để tham chiếu).
- Status: DONE cho cả 5 file liệt kê + thêm `large-diff-guards.md` (2 mention "GitHub" lọt ngoài
  danh sách G4 nhưng bị Task G8's grep gate bắt, đã sửa luôn cho nhất quán). Không TÊN entry nào bị
  đổi (đối chiếu xác nhận). 1 trường hợp phát sinh ngoài acceptance: `re-review.md`'s "React to a PR
  comment" trước đây INLINE thẳng lệnh `gh api` (theo đúng ghi chú cũ của `vendors/github.md`: "1
  caller, Read không đáng") — giờ có vendor thứ 2 với lệnh khác hẳn (`glab api .../award_emoji`) nên
  BẮT BUỘC đổi thành `Read` generic path + cập nhật lại ghi chú "Referenced from" trong CHÍNH
  `vendors/github.md` (1 sửa nhỏ ngoài phạm vi 5 file liệt kê, nhưng cần thiết để kiến trúc nhất
  quán — nếu không sửa, `re-review.md` vẫn hardcode lệnh `gh api` cho GitLab).

## Task G5: Soạn `src/vendors/gitlab.md`
- Acceptance:
  - Copy CHÍNH XÁC bộ 19 heading `## <tên thao tác>` từ `src/vendors/github.md` (không thêm/bớt/đổi
    tên heading nào) — đây là interface chung bắt buộc giữa các vendor file.
  - Đầu file: 1 đoạn ghi rõ "PR" trong tên các entry = "Merge Request (MR)" theo thuật ngữ GitLab —
    tên entry giữ nguyên "PR" cho nhất quán interface, nhưng lệnh bên trong dùng đúng khái niệm
    `glab mr ...`/field `merge_request_iid` của GitLab.
  - Nội dung từng entry theo đúng mapping đã research (dùng lại, đừng suy diễn lại):
    - Fetch PR basic info → `glab mr view` hoặc `glab api projects/:id/merge_requests/:iid`.
    - Fetch PR head commit SHA → field `diff_refs.head_sha` từ `glab mr view --output json` /
      `glab api .../merge_requests/:iid`.
    - Fetch PR diff — file list → `glab api .../merge_requests/:iid/changes`, lấy
      `old_path`/`new_path`.
    - Fetch PR diff — full patch → `glab mr diff`.
    - Fetch PR commits headlines → `glab api .../merge_requests/:iid/commits`.
    - Fetch PR review comments (LINE-level) → `glab api .../merge_requests/:iid/discussions`, lọc
      note có `position` (DiffNote).
    - Fetch PR diff size per file → KHÔNG có field byte-size thật (giống GitHub) — tự tính từ patch
      text theo file, ghi rõ giới hạn này giống hệt cách `vendors/github.md` đã ghi.
    - Fetch CI checks → `glab ci status --merge-request` (pipeline-level) hoặc
      `glab api .../pipelines/:id/jobs` (job-level).
    - Fetch PR reviews (FILE-level + review_id) → **KHÔNG CÓ tương đương trực tiếp** (xem đoạn
      composite operation dưới) — ghi rõ đây là nơi khác biệt cấu trúc lớn nhất, trỏ sang cách xử
      lý ở entry "Post a review" bên dưới.
    - Fetch account running the command → `glab auth status` / `glab api user`.
    - Fetch review threads (id + isResolved...) → REST ĐÃ ĐỦ, không cần GraphQL:
      `GET .../merge_requests/:iid/discussions` (đã trả sẵn `id`, `resolved`, list `notes`).
    - Checkout PR vào worktree mới → `glab mr checkout` CHƯA có `--worktree` native (glab issue
      #8217 còn mở) — phải tự `git worktree add` + fetch `refs/merge-requests/:iid/head` thủ công,
      ghi rõ lý do khác với GitHub's `gh pr checkout` 1 lệnh.
    - Checkout vào thư mục đã tồn tại → tương tự, cảnh báo bug đã biết của `glab mr checkout
      --repo` cross-repo (glab issue #7972) nếu dùng flag đó.
    - **Post a review (composite, KHÁC HẲN GitHub — đọc kỹ):** GitLab dùng Draft Notes API — POST
      từng `draft_notes` riêng lẻ (không có batch-create 1 lần như GitHub), rồi
      `POST .../draft_notes/bulk_publish` để submit hàng loạt 1 lúc. Không có `review_id`/`state`
      tường minh như GitHub.
    - Verify state review → GET `draft_notes`: còn tồn tại = pending; đã biến mất (đã thành
      discussion note thật) = submitted. KHÔNG có field `state` như GitHub.
    - Submit review pending → `POST .../draft_notes/bulk_publish`.
    - Reply LINE-level & FILE/overview-level → `glab mr note create --file --line` (line-level),
      `glab mr note create -m` (overview); `--reply <id>` để reply vào thread có sẵn.
    - Resolve review thread → REST, KHÔNG cần GraphQL: `PUT
      .../merge_requests/:iid/discussions/:discussion_id?resolved=true` (hoặc `glab mr note resolve
      <mr> <note_id>`).
    - React emoji → `POST .../notes/:id/award_emoji` (Emoji Reactions API — `glab` không wrap sẵn,
      dùng `glab api` trực tiếp).
  - Auth: `glab auth status`/`glab api` tự lấy credential qua `glab auth login` đã cấu hình sẵn —
    không cần cơ chế riêng như Bitbucket sẽ cần sau này.
- Dependency: G1 (biết field tồn tại trước khi vendor file tham chiếu ngược lại nó nếu cần).
- Status: DONE. `diff <(grep '^## ' github.md) <(grep '^## ' gitlab.md)` → RỖNG, đúng 19/19 heading
  khớp tuyệt đối (verify thật, xem Task G8). Toàn bộ mapping copy đúng theo backlog (không suy diễn
  thêm cú pháp `glab` nào ngoài những gì đã ghi ở đây). 2 điểm KHÔNG tự tin 100%, đã ghi caveat ngay
  trong file:
  - **"Reply on a PR"**: backlog ghi `glab mr note create --file --line` (line) /
    `glab mr note create -m` (overview) + `--reply <id>`. File đã viết dùng CHUNG 1 dạng
    `glab mr note create <n> --reply <id> -m "..."` cho cả 2 kind (lý do: usage thật của entry này
    luôn là REPLY vào thread có sẵn, không phải tạo note định vị mới — nên có lẽ không cần
    `--file`/`--line` khi đã có `--reply`). Đã ghi rõ "Confidence note" ngay trong file: đây là suy
    luận, CHƯA verify bằng `glab mr note --help` thật — user nên tự kiểm tra trước khi dùng production.
  - **Draft Notes API payload fields** (`base_sha`/`start_sha`/`head_sha`/`new_line`/`old_path`...)
    ở "Post a review": tái hiện từ hiểu biết chung về schema Position object của GitLab Discussions/
    Draft Notes API, KHÔNG phải trích trực tiếp từ backlog (backlog chỉ ghi ở mức khái niệm "POST
    từng draft_notes riêng lẻ... rồi bulk_publish", không có field-level detail) — tên field CÓ THỂ
    lệch nhẹ so với API version thật, nên test thật trước khi tin tuyệt đối.
  - Còn lại (checkout ref `refs/merge-requests/:iid/head`, `projects/<owner>%2F<repo>/...` URL
    pattern, `award_emoji` endpoint, discussions/resolved REST...) tự tin cao — đều là hành vi
    GitLab REST API đã document rõ, không phải suy đoán.

## Task G6: Viết lại Bước 9 `review.md` (post/verify/submit review) trung lập vendor
- Acceptance:
  - Prose Bước 9 KHÔNG còn giả định "1 lần POST tạo 1 review object có ID, verify bằng GET đúng ID
    đó, submit bằng 1 lệnh events" — đây là hình dạng RIÊNG của GitHub. Đổi thành: `Read` đúng
    entry "Post a review" trong `"${CLAUDE_PLUGIN_ROOT}"/vendors/<git_remote_type>.md`, làm ĐÚNG
    theo các bước file đó mô tả (số bước/cơ chế có thể khác nhau hẳn mỗi vendor — GitHub 1 object,
    GitLab nhiều draft note + bulk-publish).
  - Bất biến PHẢI giữ dù vendor nào (viết thành rule chung, không phụ thuộc cơ chế): kết quả cuối
    cùng luôn là ĐÚNG 1 review/MR-note-batch cho PR/MR chính (không tạo nhiều review rời rạc); LINE
    finding luôn gắn đúng dòng diff; FILE finding luôn nằm trong phần overview/thân tổng quan, không
    lẫn vào LINE.
  - `auto_submit_review` (setting đã có) vẫn chi phối hành vi: `true` → làm tới bước "submit" của
    đúng vendor đó; `false` → dừng ở trạng thái pending/draft của đúng vendor đó (GitHub: PENDING
    review; GitLab: draft notes chưa `bulk_publish`).
- Dependency: G4, G5 (cần cả đường dẫn generic lẫn nội dung GitLab thật để viết prose tham chiếu
  đúng).
- Status: DONE. Bước 9 hết giả định 3-bước post→verify→submit y hệt GitHub — đổi thành `Read` entry
  "Post a review" của đúng vendor + làm theo cơ chế file đó mô tả. 3 bất biến (đúng 1 kết quả cho PR
  chính; LINE gắn đúng dòng; FILE nằm trong overview không lẫn LINE) viết thành rule chung tách khỏi
  cơ chế. `auto_submit_review` vẫn chi phối true/false như cũ, chỉ đổi cách diễn đạt "PENDING
  review"/"draft notes" theo đúng vendor. `post-review.md` (case file xử lý lỗi cho đúng Bước 9 này)
  cũng viết lại trung lập tương ứng (ngoài phạm vi acceptance gốc nhưng bắt buộc để nhất quán —
  không thì case file vẫn giả định review_id/PENDING kiểu GitHub).

## Task G7: Cập nhật tài liệu (CLAUDE.md, README×3)
- Acceptance:
  - `CLAUDE.md` Project structure: thêm dòng `src/vendors/gitlab.md`. Rules: ghi 1 dòng plugin hỗ
    trợ GitHub + GitLab, Bitbucket chưa hỗ trợ (tránh user tưởng đã có).
  - `README.md`/`.vi`/`.ja`: nhắc plugin giờ hỗ trợ cả GitLab (URL dạng `/-/merge_requests/N`),
    Bitbucket chưa hỗ trợ.
- Dependency: G5.
- Status: DONE. `CLAUDE.md`: thêm dòng `src/vendors/gitlab.md` vào Project structure (giải thích
  19-heading interface + cách thêm vendor thứ 3), Mission + Features đổi "GitHub PR" → "GitHub or
  GitLab PR", "via gh api" → "via vendor's own CLI/API". Cả 3 README (en/vi/ja): thêm dòng hỗ trợ
  GitLab ngay đoạn mở đầu, Prerequisites tách 2 dòng (`gh`/`glab`), "How to use" thêm ví dụ URL
  GitLab + note self-hosted, bootstrap-questions list renumber theo đúng "7 hoặc 8 câu" (khớp
  `setup-flow.md` sau Task G1).

## Task G8: Kiểm tra nhất quán cuối (cổng validate)
- Acceptance:
  - `diff <(grep '^## ' src/vendors/github.md) <(grep '^## ' src/vendors/gitlab.md)` → RỖNG (đúng 19
    heading khớp nhau tuyệt đối, chỉ khác nội dung bên trong).
  - Grep `github\.com` VÀ `gh ` (literal GitHub CLI invocation) trong `review.md`/`fix.md`/
    `cases/*.md` → 0 hit NGOÀI 2 trường hợp hợp lệ: (1) trong chính `vendors/github.md` (nội dung
    vendor, đúng chỗ), (2) trong Task G2's union-regex nếu nó cần literal "github.com" cho 1 nhánh
    của pattern (hợp lệ, đó là 1 trong 2 dạng URL được nhận diện).
  - Grep "GitHub PR URL" (cụm cứng) trong toàn bộ `src/` → 0 hit — mọi nơi phải là "PR URL" chung.
  - Rule-coverage diff (kỹ thuật đã dùng ở backlog `delta-style-rewrite.md`) cho MỌI file bị sửa ở
    G2-G7: không rule MUST/SHOULD/FORBIDDEN nào bị mất so với bản trước khi bắt đầu backlog này.
- Dependency: G1 → G7 tất cả.
- Status: DONE. Snapshot 12 file TRƯỚC khi sửa lưu ở `/tmp/gitlab-baseline/` (đối chiếu khớp
  `git show HEAD:...` xác nhận đúng baseline thật). Số liệu verify:
  - **Heading diff**: `diff <(grep '^## ' github.md) <(grep '^## ' gitlab.md)` → RỖNG (exit 0),
    19/19 heading khớp tuyệt đối.
  - **Grep `github\.com`** trong `review.md`/`fix.md`/`cases/*.md`: 6 hit còn lại. 4/6 nằm ĐÚNG
    trong phạm vi exception 2 (mô tả/ví dụ trực tiếp của chính union-regex ở Bước 0: dòng mô tả regex
    "contains github.com", 2 dòng ví dụ lỗi "Example (GitHub): .../github.com/..." ở `review.md` +
    `fix.md`). 2/6 RỘNG HƠN chữ acceptance gốc (không nằm trong chính union-regex): (a) `fix.md` Step
    1a — ví dụ minh hoạ dạng URL git remote "not just `github.com`/`gitlab.com`"; (b) `review.md`
    Step 8 — link render vendor-conditional `github` branch
    `https://github.com/<owner>/<repo>/commit/...`. Cả 2 đều giữ literal vì CÙNG LÝ DO với exception
    2: GitHub branch của Step 0 vốn đã cố định `github\.com` theo đúng quyết định Task G2 (không hỗ
    trợ self-hosted GitHub Enterprise, khác GitLab), nên 2 chỗ này tự nhiên cũng cần literal đó —
    không phải sót lại chưa generic hoá. Ghi rõ ở đây, KHÔNG tự ý coi là "pass sạch không cần xem".
  - **Grep literal `` `gh <lệnh>` `` (word-boundary)**: 0 hit trong `review.md`/`fix.md`/`cases/*.md`
    tại thời điểm Task G4 hoàn tất. Phát sinh THÊM 1 hit ngoài dự tính SAU ĐÓ do 1 thay đổi song song
    (không phải do agent này) nâng cấp cơ chế `schema_version` trong `fix.md` thành dynamic-fetch
    (`` `gh api --paginate repos/TOMOSIA-VIETNAM/open-pr/contents/llm-upgrades/index.md` ``) — ĐÂY
    LÀ TRƯỜNG HỢP HỢP LỆ THỨ 3 ngoài 2 cái acceptance gốc liệt kê: lệnh này fetch chính file migration
    của PLUGIN từ repo GitHub thật của plugin (`TOMOSIA-VIETNAM/open-pr`, hạ tầng cố định, không liên
    quan vendor của PR đang review) — cùng bản chất với `CLAUDE.md`/`update-plugin.md` đã có sẵn
    trước giờ. Không sửa (đúng bản chất, không phải lỗi generic hoá thiếu).
  - **Grep "GitHub PR URL"** toàn `src/`: 0 hit.
  - **Rule-coverage diff**: dùng kỹ thuật backtick-token diff (`comm -23` giữa baseline/current) +
    đếm MUST/SHOULD/FORBIDDEN mỗi file, đối chiếu TỪNG token bị "mất" xem có bị dời xuống đúng vendor
    file (được phép) hay bị mất thật. Kết quả: KHÔNG file nào có MUST/FORBIDDEN/SHOULD giảm so với
    baseline (`setup-flow.md` 2/7/0→2/7/0, `review.md` 27/19/2→29/22/2, `fix.md` 17/21/4→17/22/4,
    `re-review.md` 2/7/0→2/7/0, `post-review.md` 7/3/0→7/4/0, `submodule-review.md` 1/5/0→1/5/0,
    `large-diff-guards.md` 1/4/0→1/4/0, `vendors/github.md` 0 token mất). Mọi token backtick "biến
    mất" đều truy được: hoặc dời xuống đúng vendor file tương ứng (vd `<review_id>`, `databaseId`,
    `threadId`, endpoint literal của "Post a review"/"Reply on a PR" — vẫn còn nguyên trong
    `vendors/github.md`, đã grep xác nhận), hoặc đổi format diễn đạt (`auto_submit_review: true` →
    "`true` →") không đổi nghĩa rule. 2 lỗi tự phát hiện + tự sửa trong lúc làm rule-coverage: (1)
    FORBIDDEN "gh pr review --comment / standalone POST .../comments" bị xoá khỏi cả
    `review.md` Step 9 (do rewrite G6) LẪN `post-review.md` (do generic hoá) mà chưa dời đi đâu — đã
    bổ sung lại đúng rule này vào `vendors/github.md`'s "Post a review" entry (nơi hợp lý nhất, vì
    rule này thuộc semantics riêng GitHub); (2) `vendors/github.md`'s "React to a PR comment" note
    cũ ghi "Left INLINE... không cần Read" — sai sau khi `re-review.md` đổi sang `Read` thật (Task
    G4's hệ quả) — đã sửa lại note khớp thực tế. Sau 2 sửa trên: không còn rule nào bị mất trên toàn
    bộ phạm vi G2-G7.
  - Không grep/diff nào tự động hoá được 100% "backlog's glab syntax đúng hay sai" — phần đó do
    chính agent tự đánh giá độ tin cậy, đã ghi caveat cụ thể ở Task G5's status ở trên.

## Thứ tự: G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8
