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

Tra ngày 2026-10-05, chỉ docs chính thức + mã nguồn `gh`.

| Vendor | Giới hạn | Nguồn |
|---|---|---|
| GitHub REST | 5.000 req/giờ cho user đã xác thực; app/OAuth app thuộc org Enterprise Cloud 15.000. Request của app giới hạn cao trừ vào cùng ngân sách của user. Giới hạn phụ: ≤100 request đồng thời, ≤900 điểm/phút cho REST (GET = 1 điểm, ghi = 5), ≤80 request tạo nội dung/phút và ≤500/giờ | https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api |
| GitHub conditional | Lưu `etag` (hoặc `last-modified`), gửi lại trong `if-none-match` (`if-modified-since`); dữ liệu không đổi ⇒ `304 Not Modified`, **không trừ primary rate limit** khi request có header `Authorization` hợp lệ (`gh` luôn gửi) | https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api |
| `gh api` khi 304 | status > 299 ⇒ in `HTTP 304` ra stderr, exit 1 (`cmdutil.SilentError`); `-i` in dòng status + header (tên header kiểu Go: `Etag`) ra stdout; `--paginate` dừng (không có `Link: next`) | https://github.com/cli/cli/blob/trunk/pkg/cmd/api/api.go |
| GitLab.com | Authenticated API: 2.000 req/phút mỗi user (hiện tại); đề xuất theo gói: Free 100, Premium 1.250, Ultimate 2.000/phút. Tạo note trên MR: 60/phút. Không nói gì về 304 | https://docs.gitlab.com/user/gitlab_com/rate_limits/ |
| GitLab conditional | API v4 có `Rack::ConditionalGet` (304 với `If-None-Match`), nhưng rate limit đếm ở tầng request — 304 vẫn tính; docs không hứa miễn quota | như trên + https://gitlab.com/gitlab-org/gitlab-foss/issues/26926 |
| Bitbucket Cloud | `/2.0/repositories/*`: 1.000 req/giờ, tính theo user ID; scaled tới 10.000/giờ chỉ với access token workspace/project/repo trên Standard/Premium ≥100 user trả phí (+10 req/giờ mỗi user). Header `X-RateLimit-Limit`, `X-RateLimit-NearLimit`. Không có conditional request trong docs | https://support.atlassian.com/bitbucket-cloud/docs/api-request-limits/ |

Điều chỉnh thiết kế theo kết quả:
- ETag chỉ cho GitHub (đúng spec). `gh api -i -H "If-None-Match: …"` một trang: 304 ⇒ dùng lại body đã lưu (cursor không đổi vì cùng dữ liệu); trang có `Link: rel="next"` ⇒ lấy đủ bằng `--paginate`, không cache. Giá trị ETag là dữ liệu vendor ⇒ kiểm dạng `(W/)?"…"` trước khi vào argv.
- GitLab/Bitbucket không có lợi từ ETag ⇒ tiết kiệm bằng poll thưa khi rảnh (Bitbucket cần nhất: 1.000/giờ).
- Bitbucket với workspace token: account `UNKNOWN` ⇒ vai fix tự nhận "PR của mình" không được; chỉ PR liệt kê.
