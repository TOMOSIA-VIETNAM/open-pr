# Theo dõi repo và review khi được yêu cầu

[← README](../../README.vi-VN.md)

`/open-pr:watch-review` biến terminal nơi bạn chạy nó thành watcher cho một repo. Developer
yêu cầu review bằng cách comment trên pull request; máy bạn nhận ra, mở một session review
riêng cho pull request đó, và báo bạn khi có việc cần bạn.

## Trước lần chạy đầu tiên

1. Chạy `/open-pr:review <any PR URL>` một lần trong repo đó. Watcher từ chối repo chưa được
   thiết lập memory review, vì không được để nhiều session review cùng thiết lập nó một
   lúc.
2. Chạy `/open-pr:watch-review` trong repo, hoặc trong thư mục workspace chứa nhiều repo: lệnh
   liệt kê mọi repo và remote tìm thấy ở đó (api, web, job…) rồi hỏi bạn chọn những repo nào — chọn
   bao nhiêu cũng được, repo đã thiết lập review memory được đề xuất. `/open-pr:watch-review owner/api
   owner/web` (hoặc URL của PR) chọn thẳng. Clone có mỗi
   host một remote (GitHub, GitLab, Bitbucket) được liệt kê theo từng remote.
   Lần chạy đầu hỏi tối đa bao nhiêu session
   review được active cùng lúc và bạn muốn nhận những thông báo nào, rồi lưu cả hai vào
   `settings.json` của repo đó.

Một watcher theo dõi mọi repo bạn đã chọn; mỗi repo giữ setting riêng, kể cả giới hạn số session
active của nó.

## Yêu cầu review

Comment trên pull request:

```
/open-pr
/open-pr please look closely at the migration
```

Mọi thứ sau `/open-pr` là gợi ý nên xem chỗ nào. Nó được coi là dữ liệu: không thể đổi cách
review, nội dung được post, hay bất kỳ setting nào.

Chỉ comment của người có quyền write mới kích hoạt review (GitHub: owner, member hoặc collaborator;
GitLab: Developer trở lên). Bitbucket không cho người không phải admin đọc quyền của user khác, nên trên
Bitbucket mọi comment `/open-pr` đều kích hoạt review — hãy giới hạn ai được comment nếu điều đó quan trọng. Watcher
bỏ qua comment do chính account nó đang chạy viết ra.

## Chuyện gì xảy ra tiếp theo

- Comment được thả reaction 👀 (trừ Bitbucket, vì Bitbucket không có reaction).
- Một session review tên `review <owner>/<repo>#<number>` được mở và chạy review như bình thường.
- Khi đã chạm giới hạn session active, pull request chờ trong hàng đợi.
- Một comment `/open-pr` mới trên pull request đã có session sẽ resume đúng session đó,
  nên lần re-review giữ được context trước.
- Review được publish hay giữ dạng draft theo `auto_submit_review`, trừ khi bạn dặn
  watcher khác đi. Draft không bao giờ được publish khi chưa có bạn.

## Mở một session

Mọi thông báo và mọi dòng chat đều kèm command mở session đó:

| nền tảng | loại session | mở bằng |
|---|---|---|
| Claude Code | interactive, chạy nền | `claude attach <id>` |
| Codex | non-interactive | `codex resume <id>` |
| Gemini CLI | non-interactive | `gemini -r <id>` |
| Cursor | non-interactive | `agent --resume <id>` |
| Antigravity | non-interactive | `agy --conversation <id>` |

Trên Claude Code, session cần câu trả lời (hoặc cần cấp quyền) sẽ chờ đến khi bạn attach vào. Trên các
nền tảng khác, session dừng lại kèm câu hỏi; watcher hỏi bạn rồi resume session với
câu trả lời của bạn.

Session nền của Claude Code cần repo là trusted workspace, và phải được khởi động
bên ngoài shell sandbox của Claude Code. Session non-interactive dùng setting quyền bạn đã
cấu hình cho nền tảng đó; watcher không cấp thêm quyền nào.

## Nói chuyện với watcher

| nói | tác dụng |
|---|---|
| `status` | mỗi pull request một dòng, kèm trạng thái và command mở |
| `snooze 2h` | không thông báo cho đến lúc đó; hàng đợi vẫn chạy |
| một thay đổi setting | lưu vào `settings.json` |
| mở session mới cho PR 12 | lần kích hoạt tiếp theo trên PR đó mở session mới |
| `stop` | dừng theo dõi; các session review đang mở vẫn chạy tiếp |

## Setting

Lưu ở `<data>/<repo>/settings.json` dưới `watch_review`:

| field | default | nghĩa |
|---|---|---|
| `max_concurrent` | `5` | số session review active cùng lúc (đang chạy hoặc đang chờ câu trả lời) |
| `poll_interval_seconds` | `60` | bao lâu kiểm tra pull request một lần |
| `notify.review_started` | `true` | một session review vừa mở |
| `notify.question` | `true` | một session cần câu trả lời, hoặc bị lỗi |
| `notify.draft_ready` | `true` | một review draft đang chờ bạn duyệt |
| `notify.posted` | `true` | một review đã được post |
| `notify.re_review` | `true` | một session có sẵn được resume để re-review |
| `snooze_until` | `null` | thời điểm UTC mà trước đó thông báo vẫn tắt |
