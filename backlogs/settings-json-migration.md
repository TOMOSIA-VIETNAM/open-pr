# Backlog: Gộp `meta.json` + `fix-meta.json` → `settings.json`

Mục tiêu: 1 file config duy nhất, mỗi feature 1 node riêng, xoá tận gốc bug-class dual-write
`chat_language` (đã fix tạm ở PR #19, giờ làm cho bất khả thi về cấu trúc). Phụ thuộc cơ chế
`llm-upgrades/` từ `update-plugin-mechanism.md` (migration này chính là `llm-upgrades/v2.md` đầu
tiên).

Schema đã chốt với user, không suy diễn lại:

```json
{
  "schema_version": 2,
  "shared": { "chat_language": "vi" },
  "review": { "bootstrapped": true, "doctored": true, "doctored_at": "...",
              "doctor_schedule": "...", "project_docs_found": [...], "templates_copied": [...],
              "auto_submit_review": false, "auto_resolve_fixed_findings": false,
              "pr_template_paths": [...], "review_ci_status": false,
              "many_files_threshold": 30, "big_file_threshold_kb": 20, "_comments": {...} },
  "fix": { "decline_needs_confirmation": true, "auto_push": false }
}
```

Mapping field (cơ học, không phải quyết định cần bàn lại): mọi field hiện có trong `meta.json` trừ
`chat_language` → node `review` nguyên vẹn; mọi field trong `fix-meta.json` trừ `chat_language` →
node `fix` nguyên vẹn; `chat_language` (chỉ 1 bản, không còn dual-write) → node `shared`.

## Task M1: Rewrite `setup-flow.md` Phần A để bootstrap `settings.json`
- Acceptance:
  - Repo mới bootstrap thẳng vào schema mới (`schema_version` = giá trị mới nhất hiện tại, node
    `shared`/`review`/`fix`) — không đụng tới hình dạng 2-file cũ.
  - Bảng phân loại field ở Phần D (3 nhóm: User config / Doctor-detected / Internal) viết lại theo
    node (`shared`/`review`/`fix`) thay vì "thuộc file nào trong 2 file".
- Dependency: checkpoint của `update-plugin-mechanism.md` đã qua.
- Status: DONE.

## Task M2: Rewrite `review.md` Bước 3 + `fix.md` Bước 2 dùng `settings.json`
- Acceptance:
  - Cả 2 đọc/ghi CHUNG 1 file `settings.json`, đúng node của mình (`review.md` → `.review` +
    `.shared`; `fix.md` → `.fix` + `.shared`).
  - Logic detect/ghi `chat_language` CHỈ đụng `.shared.chat_language` trong `settings.json` — không
    còn cross-file write ở đâu nữa (bug-class PR #19 giờ bất khả thi về cấu trúc, không phải patch
    tạm).
- Dependency: M1.
- Status: DONE. (Cũng tiện sửa luôn các mention `meta.json` còn sót ở `src/cases/re-review.md`,
  `src/cases/pr-template-checklist.md`, `src/cases/submodule-review.md`, và `review.md` Bước 10 —
  bắt buộc để đạt checkpoint "không còn tham chiếu meta.json/fix-meta.json sót trong src/".)

## Task M3: Cập nhật `CLAUDE.md` Rules cho convention file mới
- Acceptance:
  - Dòng "Per-repo settings live in `meta.json` (review.md) và `fix-meta.json` (fix.md) — hai file
    riêng, không share field" thay bằng rule mô tả 1 `settings.json`, tách node theo feature
    (`shared`/`review`/`fix`), và invariant: chỉ code sở hữu node đó mới được ghi (`review.md`
    không bao giờ ghi `.fix`, `fix.md` không bao giờ ghi `.review`).
- Dependency: M2.
- Status: DONE.

## Task M4: Soạn `llm-upgrades/v2.md` (migration thật đầu tiên)
- Acceptance:
  - Dùng format ADDED/MODIFIED/REMOVED cảm hứng OpenSpec (convention đã chốt ở task U1 của
    `update-plugin-mechanism.md`).
  - Nội dung: repo đã có `meta.json`+`fix-meta.json` cũ → đọc cả 2, áp mapping field ở trên, ghi
    `settings.json`, xoá 2 file cũ, commit vào `notebooks/review/.git` nested (tái dùng logic
    fallback commit-identity đã có sẵn trong `setup-flow.md`).
  - `llm-upgrades/index.md` có entry thật đầu tiên trỏ về file này.
- Dependency: M3 (cần chốt xong schema đích bằng prose trước khi viết migration tạo ra nó).
- Status: DONE.

## Checkpoint (trước khi qua P1 — delta-style-rewrite.md)
- Tên field khớp byte-for-byte giữa `setup-flow.md`, `review.md`, `fix.md`, `llm-upgrades/v2.md` —
  grep từng tên field (`chat_language`, `bootstrapped`, `decline_needs_confirmation`...) qua cả 4
  file, xác nhận không còn tham chiếu `meta.json`/`fix-meta.json` cũ nào sót lại trong `src/`.

## Thứ tự: M1 → M2 → M3 → M4
