# Spec: `/open-pr:watch-review` — review theo lệnh comment trên PR, chạy trên máy reviewer

Nguồn: issue https://github.com/TOMOSIA-VIETNAM/open-pr/issues/138, đã làm rõ lại với người đề xuất.
Phạm vi: 1 chiều (review). Chiều fix (`watch-fix`) là feature sau, dùng lại cùng khung.

## Mục tiêu

Reviewer có 10 PR cần review thì không phải chạy tay `/open-pr:review` 10 lần. Dev gọi review khi cần
bằng một comment trên PR; máy reviewer (đang mở terminal tại repo đó) tự nhận, mở 1 session review riêng
cho PR đó, post theo đúng setting của repo. Reviewer mở được từng session để xem hoặc trả lời.

## Luồng

1. Dev comment trên PR: `/open-pr <nội dung>`. `<nội dung>` là gợi ý phần cần tập trung, có thể rỗng.
2. Reviewer `cd` vào repo, chạy `/open-pr:watch-review`. Session này là **main session**: chỉ trao đổi
   với reviewer và điều phối, không tự review.
3. Main phát hiện trigger → thả reaction ack lên comment → mở 1 **review session** riêng cho PR, tên
   `review <owner>/<repo>#<N>` → notify kèm lệnh mở session.
4. Review session chạy đúng quy trình `/open-pr:review`, cuối cùng ghi 1 file trạng thái.
5. Main đọc trạng thái: cần trả lời / draft / đã post / lỗi → notify reviewer.
6. Trigger mới trên PR đã có session ⇒ **resume đúng session đó** (re-review giữ context lần trước).

## Quyết định đã chốt

| # | Quyết định | Lý do |
|---|---|---|
| 1 | Trigger = comment bắt đầu bằng `/open-pr` (không phải `/open-pr:…`) | `@claude` bị Claude GitHub App và `claude-code-action` bắt; `@open-pr` mention thật một account GitHub trùng tên. `/` không mention ai |
| 2 | Không dùng Claude Code Channels; phát hiện trigger bằng poll qua script | Channels đang research preview, org Team/Enterprise cần admin bật; GitHub không POST được vào localhost nên channel vẫn phải poll |
| 3 | Repo nghe = repo của cwd (git remote). Nhiều repo ⇒ mỗi repo 1 terminal | Không cần config danh sách repo |
| 4 | Chỉ người có quyền write mới trigger. GitHub: `author_association` ∈ OWNER/MEMBER/COLLABORATOR (có sẵn trong comment). GitLab: access level ≥ 30 qua `members/all/:user_id`. Bitbucket: API đòi admin ⇒ `UNKNOWN`, không kiểm tra, README ghi rõ | Chặn người ngoài làm tốn quota; không bắt cấp thêm quyền |
| 5 | `<nội dung>` luôn là dữ liệu (gợi ý trọng tâm), không bao giờ là lệnh | Chặn prompt injection qua comment |
| 6 | Bỏ qua comment mang marker plugin; comment thường của chính account đang đăng nhập vẫn trigger | Mọi comment plugin post đều mang marker nên không tự trigger; một người có thể vừa là dev vừa là reviewer |
| 7 | Post theo lời dặn của reviewer trong session, không có thì theo `.review.auto_submit_review`. Draft ⇒ main báo reviewer, reviewer mở session để duyệt/sửa/publish | Giữ luật sẵn có: cấm publish thay người |
| 8 | Setting trong `settings.json` theo repo, node `watch_review`. Thiếu node ⇒ lần chạy đầu hỏi rồi ghi. Không tăng `schema_version` | 1 chỗ theo repo; `settings.json` đã nằm trong data dir của máy reviewer; node mới không bắt config cũ biến đổi |
| 9 | Giới hạn số review session hoạt động (đang chạy hoặc chờ trả lời), mặc định 5, script đếm | Quota, rate limit; đếm bằng script mới tất định |
| 10 | Notify hệ điều hành theo từng loại sự kiện, bật/tắt từng loại, snooze đến một thời điểm | Reviewer không ngồi nhìn terminal |
| 11 | Command riêng `/open-pr:watch-review` | Vòng đời khác; flag sẽ nhét phần điều phối vào file mọi lần review đều load |
| 12 | `src/bin/open-pr.sh` giữ mọi thao tác vendor (op mới `repo-target`, `triggers`). `src/bin/open-pr-watch.sh` mới giữ điều phối + cách mở session của từng nền tảng | Thao tác vendor chỉ ở `open-pr.sh`; CLI của từng nền tảng chỉ ở `open-pr-watch.sh` — cùng khuôn "một chủ sở hữu" |
| 13 | Mỗi review chạy trong session riêng, không bao giờ trong main | Context nhiều PR trộn vào nhau làm agent mất quan điểm |
| 15 | 👀 trên comment trigger là khoá giữa nhiều máy (`<op> claim`): máy nào có 👀 sớm nhất thì review, máy khác lùi. Cùng account trên 2 máy: lần react thứ hai GitHub trả 200 (đã có) ⇒ lùi. Bitbucket không có reaction ⇒ không khoá được, docs ghi rõ | Tránh cùng một lượt comment bị review song song trên nhiều máy |
| 16 | Thông báo là toast tự vẽ ở góc trên phải màn hình (macOS: cửa sổ JXA `open-pr-toast.js`, không cần quyền Notifications; Linux: `notify-send`), xếp chồng khi có nhiều cái; snooze áp cho toast | Người dùng đang làm việc khác vẫn thấy watcher đang làm gì; notification hệ thống trên macOS đòi quyền và hiện dưới tên Script Editor |
| 14 | Runner theo nền tảng: Claude Code dùng session nền tương tác (`claude --bg`); nền tảng khác chưa có dạng này ⇒ headless + resume | Reviewer mở được session; nền tảng nào có dạng như `--bg` thì thêm runner cùng kiểu |

## Runner theo nền tảng

`open-pr-watch.sh` là nơi DUY NHẤT dưới `src/` gọi CLI của một nền tảng. Main session truyền
`--runner <tên>`; tên runner lấy từ `adapters/root.md` (Claude Code không đọc adapter ⇒ mặc định
`claude`).

| runner | kiểu | mở session | trạng thái | resume | tên session |
|---|---|---|---|---|---|
| `claude` | nền, tương tác | `claude --bg -n "<tên>" "<prompt>"` (cwd = repo). id lấy từ dòng `backgrounded · <id> · <tên>` | `claude agents --json --all`: `working` / `blocked` (chờ trả lời) / `done` / `failed` / `stopped` | `claude stop <id>`, chờ id rời `claude agents --json`, rồi `claude --bg --resume <sessionId> "<prompt>"` KHÔNG thêm cờ nào | `-n`, giữ qua resume |
| `codex` | headless | `codex exec --json -C <repo> "<prompt>"`; id = `thread_id` của event `thread.started` | pid còn sống ⇒ đang chạy; thoát ⇒ file trạng thái | `codex exec resume <id> "<prompt>"` | không có cờ |
| `gemini` | headless | `gemini -p "<prompt>" --session-id <uuid> -o json` (cwd = repo); id gán trước | như trên | `gemini -r <uuid> -p "<prompt>"` | không có |
| `cursor` | headless | `agent create-chat` ⇒ id; `agent -p --resume <id> --output-format json "<prompt>"` | như trên | `agent -p --resume <id> "<prompt>"` | không có cờ |
| `antigravity` | headless | `agy -p "<prompt>" --output-format stream-json`; id = `conversation_id` của event `init` | như trên | `agy -p "<prompt>" --conversation <id>` | không có cờ |

Lệnh mở lại để reviewer tự vào xem:

| runner | lệnh |
|---|---|
| `claude` | `claude attach <id>` (đúng ở mọi trạng thái; `claude --resume <sessionId>` khi session đang chạy sẽ tạo bản sao) |
| `codex` | `codex resume <id>` |
| `gemini` | `gemini -r <uuid>` |
| `cursor` | `agent --resume <id>` |
| `antigravity` | `agy --conversation <id>` |

Kết quả spike `claude --bg` (CLI 2.1.283), làm căn cứ cho bảng trên:

- `--bg` đòi workspace đã trust (repo reviewer đang mở là đã trust).
- Chạy từ trong sandbox Bash của Claude Code thì session kẹt ở `starting…`; phải chạy ngoài sandbox.
- `--session-id` bị bỏ qua khi có `--bg`; id thật in ở stdout và có trong `claude agents --json`.
- Session `done` vẫn sống (idle). Resume khi còn sống, hoặc resume có thêm cờ ⇒ CLI tạo bản sao với id
  mới và mất tên. Phải `stop` → chờ rời danh sách active → resume không cờ ⇒ giữ id, tên, context.
- `blocked` kèm `waitingFor: "input needed"` khi session hỏi (AskUserQuestion) hoặc chờ duyệt quyền.
- `claude logs` là output TUI, không parse được ⇒ kết quả lấy từ file trạng thái.

Nguồn cho các runner headless (đã kiểm `--help` trên máy: codex 0.147.0, gemini 0.54.4,
cursor-agent 2026.08.04, agy 1.1.10): Codex https://learn.chatgpt.com/docs/non-interactive-mode ·
Gemini https://geminicli.com/docs/cli/headless/ · Cursor https://cursor.com/docs/cli/headless ·
Antigravity https://antigravity.google/docs/cli/headless.

## Review session: prompt và file trạng thái

- Main viết prompt vào file rồi truyền `--prompt-file`. Prompt gọi review theo cách nền tảng đó gọi
  command (Claude: `/open-pr:review <url> --status-file <F>`), kèm `<nội dung>` đánh dấu là gợi ý trọng
  tâm lấy từ comment (dữ liệu).
- `review.md` nhận `--status-file <F>` trong ARGUMENTS ⇒ cuối Step 9 ghi 1 JSON:
  `{"state":"posted|draft|lgtm_chat|failed","url":"…","counts":{…},"note":"…"}`.
- Runner headless: review chạy chế độ unattended (`cases/unattended.md`): không hỏi được ⇒ ghi
  `{"state":"question","question":"…"}` vào file trạng thái rồi dừng; main hỏi reviewer và resume
  session với câu trả lời. Runner `claude` hỏi bình thường, reviewer `attach` vào trả lời.
- File trạng thái: `<data>/<repo>/watch-review/pr-<N>.status.json`.

## Setting: node `watch_review`

```json
"watch_review": {
  "max_concurrent": 5,
  "poll_interval_seconds": 60,
  "notify": {
    "review_started": true,
    "question": true,
    "draft_ready": true,
    "posted": true,
    "re_review": true
  },
  "snooze_until": null
}
```

- Nhóm "User config" trong `src/reference/settings-schema.md`, nhưng `watch-review` ghi node ở lần chạy
  đầu (giống bootstrap ghi `.review`), không chờ `/open-pr:upgrade`.
- `snooze_until`: ISO-8601 UTC hoặc `null`. Trong snooze, notify tắt; hàng đợi vẫn chạy.

## State của watch (không phải setting)

`<data>/<repo>/watch-review/`: `state.json` (con trỏ comment đã xử lý, map PR → runner/id/sessionId/tên,
hàng đợi), `pr-<N>.status.json`, `pr-<N>.log` (stdout của runner headless), `prompts/`.

## Ràng buộc từ code hiện tại

- Các worktree dùng chung `.git` của repo gốc. `checkout` trong `open-pr.sh` fetch
  `+<base>:refs/remotes/origin/<base>` và chạy `git worktree add` ⇒ 2 review cùng lúc tranh ref lock.
  Khoá đúng đoạn đó theo repo; phần còn lại song song.
- Review thường không ghi gì dưới `<data>` ngoài payload/worktree; bootstrap/doctor mới ghi và commit
  vào `<data>/.git`. Main chạy chúng 1 lần, tuần tự, trước khi mở session nào; repo chưa bootstrap ⇒
  main dừng, bảo reviewer chạy `/open-pr:review` 1 lần.
- `review.md` vẫn cấm song song khi chạy tay nhiều PR trong 1 session — không đổi.

## Không làm trong feature này

- Chiều fix tự động (`watch-fix`).
- Webhook/Channels/tunnel; máy chủ CI.
- Allowlist login riêng trong config.
- Runner headless tự cấp quyền: dùng cấu hình quyền sẵn có của nền tảng, README hướng dẫn.
