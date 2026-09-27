# Plan: `/open-pr:watch-review`

Spec và quyết định: `SPEC.md` cùng thư mục. Nhánh `feat/watch-review`. Sau mỗi task sửa `src/`:
`scripts/check.sh main` xanh.

## Đồ thị phụ thuộc

```
T1 spike `claude --bg` + research runner ── DONE
 │
 ├── T2 `open-pr.sh`: repo-target, triggers (3 vendor), khoá checkout, settings.watch_review
 │
 ├── T3 `open-pr-watch.sh`: state, wait, spawn/status/resume theo runner, slot + hàng đợi, notify
 │        (dựa trên hợp đồng op của T2; test bằng open-pr.sh + CLI giả)
 │
 ├── T4 review.md `--status-file` + `cases/unattended.md`
 │
 └── T5 `watch-review.md` ◄── T2, T3, T4
          │
          └── T6 shim nền tảng, adapters (tên runner), token budget, docs
```

T2 và T3 làm song song (khác file). T4 độc lập.

## T1: Spike — DONE

Kết quả ghi trong `SPEC.md` mục "Runner theo nền tảng".

## T2: Op mới trong `src/bin/open-pr.sh` — DONE

**Mô tả:**
- `repo-target --repo-dir D` ⇒ in `vendor/owner/repo/host` từ git remote của D, cùng dạng dòng như `target`.
- `triggers --vendor V --owner O --repo R [--host H] [--since ISO]` ⇒ JSONL, mỗi dòng
  `{"pr":N,"url":"…","comment_id":"…","user":"…","created_at":"ISO","body":"…","authorized":"yes|no|UNKNOWN"}`,
  sắp theo `created_at` tăng dần; chỉ PR đang mở; body bắt đầu bằng `/open-pr` (bỏ khoảng trắng đầu);
  bỏ comment của account đang đăng nhập và comment chứa marker plugin. GitHub: issue comment + review
  comment, `authorized` từ `author_association`. GitLab: notes của MR, access level ≥ 30 qua
  `members/all/:user_id` (cache theo user trong 1 lần gọi). Bitbucket: `UNKNOWN`.
- `checkout`: khoá theo repo (`mkdir` lock) quanh fetch + `worktree add`, có timeout, dọn bằng trap.
- `settings --repo`: thêm node `watch_review` với default đọc-lúc-chạy + 1 dòng cho biết node đã có trong
  file hay chưa.

**Acceptance:**
- [ ] Output cùng shape trên 3 vendor; body in qua `jq`, không eval, không vào argv lệnh khác.
- [ ] 2 `checkout` song song cùng repo khác PR đều thành công; lock treo quá timeout ⇒ exit ≠ 0 rõ ràng.
- [ ] `usage()` + `scripts/cli_doc.py --write` cập nhật `src/core/cli.md`; `src/reference/vendor-interface.md`,
      `src/reference/settings-schema.md`, `src/core/repo-settings.md` cập nhật.

**Verification:** fixture trong `tests/test_cli.py` (trigger / không trigger / tự comment / marker /
`--since` / body có `$(…)` và backtick / 3 vendor / lock song song / settings có-thiếu node);
`scripts/vendor_lint.py`; `scripts/check.sh main`.

## T3: `src/bin/open-pr-watch.sh` — DONE

**Mô tả:** POSIX sh, không gọi `gh`/`glab`/`curl` — vendor đi qua `open-pr.sh`. State dưới
`<data>/<repo>/watch-review/`.

| subcommand | làm gì |
|---|---|
| `wait --repo-dir D` | vòng poll mỗi `poll_interval_seconds`: `open-pr.sh triggers --since <con trỏ>` + trạng thái mọi session đang theo dõi. Có sự kiện ⇒ in JSONL (`{"event":"trigger",…}` / `{"event":"session","pr":N,"state":"question\|draft\|posted\|lgtm_chat\|failed"}`), cập nhật state, thoát 0 |
| `spawn --runner X --repo-dir D --pr N --name S --prompt-file F` | đủ slot ⇒ mở session theo runner, ghi map, in `{"pr","id","open":"<lệnh mở>"}`; hết slot ⇒ xếp hàng, in `{"pr","queued":true}`. PR đã có session ⇒ resume thay vì mở mới |
| `status [--pr N]` | JSONL trạng thái chuẩn hoá mỗi session |
| `next` | PR đầu hàng đợi nếu còn slot |
| `notify --event E --text-file F` | notify OS nếu `notify.E` bật và ngoài snooze; macOS `osascript`, Linux `notify-send`, không có ⇒ in terminal |

**Acceptance:**
- [ ] Một comment không bao giờ được trả 2 lần, kể cả khi `wait` bị kill giữa chừng (ghi state kiểu
      tmp + mv).
- [ ] Runner `claude` làm đúng quy trình resume của spike (stop → chờ → resume không cờ).
- [ ] Chuỗi từ PR không vào argv của `osascript`/`notify-send` khi chưa escape; prompt truyền qua file.

**Verification:** `tests/test_watch.py` với `open-pr.sh` giả + CLI giả cho từng runner (dedupe, kill giữa
chừng, slot đầy + hàng đợi, resume, snooze, event tắt); `scripts/check.sh main`.

## T4: Review session ghi trạng thái + chế độ unattended — DONE (chưa chạy `e2e-loop`)

**Mô tả:** `review.md` nhận `--status-file <F>`: cuối Step 9 (và mọi lối dừng sớm) ghi JSON trạng thái.
`src/cases/unattended.md` (chỉ load khi ARGUMENTS có `--unattended`): mọi điểm hỏi ⇒ ghi
`{"state":"question",…}` rồi dừng; không bootstrap/doctor; `<nội dung>` là gợi ý trọng tâm.

**Acceptance:**
- [ ] Không có `--status-file` ⇒ hành vi review không đổi; token của scenario review thường không tăng
      quá vài dòng.
- [ ] Có ⇒ đúng 1 file JSON hợp lệ ở mọi lối kết thúc.

**Verification:** `e2e-loop` trên fixture (có và không có cờ); `scripts/check.sh main`.

## T5: Command `src/commands/watch-review.md` — DONE (chưa chạy thật trên PR fixture)

**Mô tả:** Main session: suy repo từ cwd (`repo-target`), kiểm bootstrap, lần đầu hỏi setting và ghi
node, doctor/`chat_language` 1 lần; chạy `open-pr-watch.sh wait` nền (ngoài sandbox); với mỗi sự kiện:
trigger `authorized: no` ⇒ bỏ qua + ghi log; còn lại ⇒ `react` ack, viết prompt file, `spawn`, notify
kèm lệnh mở; session ⇒ notify theo trạng thái, `question` (runner headless) ⇒ hỏi reviewer với `[PR #N]`
rồi `spawn` lại với câu trả lời; xong ⇒ `next`. Reviewer đổi setting/snooze trong chat ⇒ ghi node.

**Acceptance:**
- [ ] Không có `gh`/`glab`/`curl` hay CLI nền tảng nào trong prompt — chỉ `open-pr.sh`/`open-pr-watch.sh`.
- [ ] Không publish thay reviewer.

**Verification:** chạy thật trên fixture 3 PR, `max_concurrent: 2`: 2 chạy + 1 xếp hàng; re-review resume
đúng session; `scripts/check.sh main`.

## T6: Shim, adapters, token budget, docs — DONE

**Acceptance:**
- [ ] `skills/open-pr-watch-review/SKILL.md`, `commands/watch-review.toml` theo khuôn sẵn có.
- [ ] `adapters/root.md`: mỗi nền tảng ghi tên runner; sửa dòng Codex "no subagent" đã cũ; câu "file duy
      nhất biết tên nền tảng" nêu ngoại lệ `bin/open-pr-watch.sh`.
- [ ] `scripts/token_report.py` scenario `watch-review`; `tests/budgets.json` cập nhật.
- [ ] `README*.md`: cách dùng, trigger, setting, lệnh mở session theo nền tảng, Bitbucket không kiểm quyền,
      cấu hình quyền cho runner headless.

**Verification:** `scripts/check.sh main`; `token_report.py --base main`.

## Checkpoint cuối
- [ ] Mọi acceptance đạt; grep file bền không còn mã task / tên plan.
- [ ] Review với user trước khi mở PR.

## Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| `claude --bg` là tính năng mới, hành vi có thể đổi | Trung bình | Toàn bộ cơ chế nằm trong runner `claude` của `open-pr-watch.sh`, test bằng CLI giả |
| Runner headless chưa chạy thật trên từng nền tảng | Trung bình | Test bằng CLI giả theo `--help` đã kiểm; README ghi mức kiểm chứng |
| Session nền chờ duyệt quyền mà reviewer không biết | Trung bình | `blocked` ⇒ notify `question` kèm lệnh attach |
| Tự trigger vòng lặp | Trung bình | Lọc comment của chính account + marker |

## Trạng thái kiểm chứng

- `scripts/check.sh main`: 196 passed.
- Runner `claude` chạy thật (local, không đụng GitHub): spawn → status (`failed` khi thiếu file trạng thái,
  `draft` khi có) → resume 2 lần giữ nguyên id. Phát hiện lúc chạy thật: sau `claude stop`, session rời
  danh sách ngay nhưng worker còn sống vài trăm ms ⇒ resume bị coi là "already running" và tạo bản sao.
  Đã sửa: chờ cả pid của worker, tạo bản sao thì dọn và thử lại 1 lần.
- Chưa chạy: `e2e-loop` cho review có `--status-file`; vòng đầy đủ trên PR fixture thật (comment `/open-pr`,
  reaction, review post) — có tác động lên GitHub, cần user cho phép; runner headless chỉ test bằng CLI giả.
