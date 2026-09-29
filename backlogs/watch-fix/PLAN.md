# Plan: `/open-pr:watch` — vai review + fix

Spec: `SPEC.md` cùng thư mục. Nhánh `feat/watch-fix`, tách từ `feat/watch-review` (PR #140). Sau mỗi
task sửa `src/`: `scripts/check.sh main` xanh; checkpoint với user giữa các task.

## Đồ thị phụ thuộc

```
T1 tra quota/ETag docs thật (GitHub/GitLab/Bitbucket) ─┐
T2 đổi tên watch-review → watch (command, state dir, shim, docs)
 │
 ├── T3 open-pr.sh: findings (review mới mang bot-finding, chưa reply) + ETag cache GitHub ◄── T1
 │
 ├── T4 open-pr-watch.sh: vai theo PR, session key "<pr>:<role>", event `findings`, tự nhận PR,
 │        poll thưa khi rảnh ◄── T3
 │
 ├── T5 fix.md nhận --status-file (dùng cases/watch-session.md); session fix trong worktree riêng
 │
 └── T6 command watch.md + cases/watch-fix.md; toast "Fix now"; menu bar tách review/fix ◄── T4, T5
          │
          └── T7 token scenario, docs 4 ngôn ngữ, README, e2e thật trên fixture
```

## T1: Tra quota và ETag (không code)

- Xác nhận số trong bảng quota của SPEC từ docs chính thức; ETag/`If-None-Match` với `gh api`
  (header, exit code khi 304); GitLab/Bitbucket có conditional request không.
- Ghi kết quả vào mục "Kết quả tra cứu" cuối file này.

## T2: Đổi tên watch-review → watch

- `src/commands/watch-review.md` → `watch.md`; skill/toml/token atom/chart line/install-local/README/
  docs; state dir `watch-review/` → `watch/` (script + gitignore line); `cases/watch-session.md`
  giữ tên (dùng chung).
- Acceptance: không còn chuỗi `watch-review` trong src/ docs/ README (trừ lịch sử git); check xanh.

## T3: Nguồn event vai fix trong `open-pr.sh`

- Op `findings --since T [--author A]`: JSONL review mới mang `bot-finding` trên PR mở của A
  (mặc định account), `{pr, review_id, url, counts, created_at}`; GitHub: pull comments sẵn có +
  `pulls/N/reviews` chỉ cho PR của A có `updated_at` > T; GitLab/Bitbucket: từ dữ liệu đã tải.
- Hoặc gộp vào `triggers` (một lượt fetch) — chọn khi làm, ưu tiên ít request.
- ETag cache GitHub cho các GET poll (lưu trong state của watch, truyền qua file).
- Tests 3 vendor, 304 không đổi cursor.

## T4: Watch runtime hai vai

- State: `sessions["<pr>:<role>"]`, `fix_prs`, `seen_reviews`, `idle_since`.
- `wait`: một lượt poll → event `trigger` (review) và `findings` (fix); trigger do chính mình trên PR
  của mình ⇒ thêm PR vào `fix_prs`.
- `spawn --role review|fix`; fix ⇒ worktree riêng (qua `<op> checkout`), prompt `/open-pr:fix`.
- Poll thưa khi rảnh (60 → 180 s).
- Tests: hai vai trên cùng repo, cùng PR hai session, poll gộp đếm request.

## T5: `fix.md` trong session nền

- `--status-file` ⇒ `cases/watch-session.md` (mở rộng cho fix: state `fixed|question|failed`, counts
  reply/decline); fix chạy ở worktree session mở; không ghi `<data>` ngoài phần của nó.
- e2e-loop fix có cờ.

## T6: Command `watch.md`

- Chọn vai; `cases/watch-fix.md` (chỉ nạp khi vai fix bật): event `findings` ⇒ toast "Fix now";
  "Fix now" từ toast/menu bar ⇒ spawn fix; xong ⇒ hỏi gọi re-review.
- Toast: nút "Fix now" (click action mới `fix` gọi `<watch> spawn --role fix` qua argv).
- Menu bar: trong mỗi nhóm watcher, tách review / fix, nhãn vai; "Fix now" trong submenu dòng fix.

## T7: Token, docs, e2e

- Scenario token cho `watch` (review-only, fix-only, cả hai); budget; docs 4 ngôn ngữ; README.
- Chạy thật: một PR của mình, tự gọi review, nhận finding, "Fix now", fix push + reply, hỏi re-review.

## Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Vòng lặp review ↔ fix | Trung bình | re-review luôn qua dev; không tự comment trigger |
| Fix đè working tree dev | Cao | worktree riêng của nhánh PR |
| Quota khi nhiều repo + hai vai | Trung bình | poll gộp, ETag, poll thưa khi rảnh, backoff |
| Hai máy cùng fix một PR | Thấp | claim bằng reply như vai review |

## Kết quả tra cứu

(Điền sau T1.)
