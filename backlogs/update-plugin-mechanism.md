# Backlog: `/open-pr:update-plugin` + `llm-upgrades/` mechanism

Mục tiêu: chuyển logic migrate config (hiện đang backfill inline mỗi lần review, gây phình
`review.md` Step 3) ra 1 slash command riêng, chạy khi user chủ động biết plugin đã update. Nền
tảng cho Phase P3 (settings.json merge dùng lại đúng cơ chế này).

## Task U1: `llm-upgrades/index.md` skeleton + doc trong `CLAUDE.md`
- Acceptance:
  - `llm-upgrades/index.md` tạo ở ROOT repo (ngang hàng `src/`, KHÔNG nằm trong `src/`) — định dạng
    mỗi dòng 1 version có migration, lấy cảm hứng OpenSpec ADDED/MODIFIED/REMOVED/RENAMED (chọn vì
    đúng hình dạng `/open-pr:update-plugin` cần để diff theo `schema_version`). Version không cần
    migrate → không tạo entry (hoặc entry tự ghi rõ no-op, tuỳ lúc viết) — phải nói rõ CHÍNH XÁC 1
    lần, không mơ hồ, trong file này.
  - `CLAUDE.md` mục "Project structure" thêm dòng cho `llm-upgrades/`: KHÔNG thuộc `src/`, KHÔNG
    đóng gói lúc `/plugin install`, fetch live qua `gh api` từ `TOMOSIA-VIETNAM/open-pr` — khác hẳn
    changelog người đọc của `release-now.md`.
- Dependency: không (task đầu).
- Status: DONE.

## Task U2: Soạn `src/commands/update-plugin.md`
- Acceptance:
  - Theo đúng convention cấu trúc như `review.md`/`fix.md`: frontmatter `allowed-tools` scope đúng
    `gh api --paginate repos/TOMOSIA-VIETNAM/open-pr/contents/llm-upgrades/*` (chỉ GET) + `Read`/
    `Write`/`Edit` cho file config local, CRITICAL block nói rõ lệnh này CHỈ sửa
    `notebooks/review/<repo>/settings.json` (hoặc `meta.json`/`fix-meta.json` trước P3) của repo
    HIỆN TẠI, không đụng gì khác.
  - Bước 1: đọc `schema_version` checkpoint hiện tại của repo local.
  - Bước 2: fetch `llm-upgrades/index.md` mới nhất qua `gh api`; xác định mọi version MỚI HƠN
    checkpoint.
  - Bước 3: fetch TOÀN BỘ file `vN.md` khớp điều kiện CÙNG 1 lúc (không hỏi từng version, không làm
    tuần tự) — version sau có thể đè version trước, làm tuần tự lãng phí theo đúng lý do user đã nêu.
  - Bước 4: áp dụng migration tích luỹ từ các file đó vào config local; ghi `schema_version` mới.
  - Bước 5: báo user trong chat tóm tắt đã đổi gì (không dump raw diff).
  - KHÔNG thêm field/logic nào tái tạo lại việc check version mỗi lần review — lệnh này là NƠI DUY
    NHẤT có nhận thức về schema/version.
- Dependency: U1 (cần format index.md để parse theo).
- Status: DONE.

## Task U3: Xoá logic backfill-mỗi-lần-review
- Acceptance:
  - `src/commands/review.md` Bước 3, đoạn "field User config nào MISSING → Edit backfill NGAY +
    báo" xoá HẲN, không rút gọn — thay bằng 1 dòng: đọc file config as-is, không diff theo field kỳ
    vọng.
  - `src/setup-flow.md` Phần D, đoạn mô tả song song hành vi backfill này xoá tương tự.
  - `CLAUDE.md` mục Rules thêm 1 dòng: nâng cấp schema cho repo đã bootstrap chỉ xử lý qua
    `/open-pr:update-plugin`, không bao giờ âm thầm inline lúc review.
  - Grep "backfill" trong `src/` → 0 hit sau task này.
- Dependency: U2 (cơ chế thay thế phải có trước khi xoá cơ chế cũ).
- Status: DONE.

## Task U4: Ghi chú lệnh mới vào README
- Acceptance:
  - `README.md` / `README.vi.md` / `README.ja.md` mỗi bản thêm 1 dòng ngắn giới thiệu
    `/open-pr:update-plugin` — mục đích, cùng tone/độ dài với `/open-pr:review`/`/open-pr:fix` đã có.
- Dependency: U2.
- Status: DONE.

## Checkpoint (trước khi qua P3 — settings-json-migration.md)
- `update-plugin.md` frontmatter hợp lệ (pattern allowed-tools khớp style scope hiện có của dự án —
  không cấp quyền chung chung).
- Grep xác nhận không còn logic "backfill" trong `review.md`/`setup-flow.md`.
- `llm-upgrades/index.md` + các chỗ doc tham chiếu nó nhất quán với nhau.

## Thứ tự: U1 → U2 → U3, U4 (song song sau U2)
