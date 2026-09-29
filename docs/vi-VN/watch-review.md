# Theo dõi repo và review khi được yêu cầu

[← README](../../README.vi-VN.md)

`/open-pr:watch-review` biến terminal nơi bạn chạy nó thành watcher cho một hoặc nhiều repo. Developer
yêu cầu review bằng cách comment trên pull request; máy bạn mở một session review riêng cho pull request
đó và báo bạn khi có việc cần bạn.

## Trước lần chạy đầu tiên

1. Chạy `/open-pr:review <any PR URL>` một lần trong từng repo. Watcher từ chối repo chưa thiết lập
   review memory, để không bao giờ có nhiều session cùng thiết lập nó một lúc.
2. Chạy `/open-pr:watch-review` trong một repo, hoặc trong thư mục workspace chứa nhiều repo. Lệnh liệt
   kê mọi repo và remote tìm thấy ở đó (clone có mỗi host một remote được liệt kê theo từng remote) rồi
   hỏi theo dõi những repo nào; repo đã thiết lập review memory được đề xuất.
   `/open-pr:watch-review owner/api owner/web` (hoặc URL của PR) chọn thẳng.
3. Lần chạy đầu trong một repo hỏi tối đa bao nhiêu session review được active cùng lúc, cái gì yêu cầu
   review (`/open-pr` hay một lần mention bạn) và bạn muốn nhận những toast nào, rồi lưu câu trả lời vào
   `settings.json` của repo đó.
4. Session review khởi động trong thư mục nơi bạn chạy watcher, như khi bạn gõ `/open-pr:review` ở đó —
   cùng thư mục dữ liệu, cùng trust. Trên Claude Code, thư mục đó phải là trusted workspace; watcher kiểm
   tra khi khởi động và, nếu chưa, bảo bạn mở `claude` ở đó một lần rồi chấp nhận lời hỏi trust.

Mỗi repo được theo dõi giữ setting riêng, kể cả giới hạn session. Mỗi repo có tối đa một watcher trên một
máy: watcher thứ hai báo tiến trình nào đang giữ repo rồi bỏ qua repo đó. Khi host không kết nối được kéo
dài (mất mạng, login hết hạn), watcher báo cho bạn.

## Yêu cầu review

Comment trên pull request:

```
/open-pr
/open-pr please look closely at the migration
```

Phần chữ sau `/open-pr` là gợi ý nên xem chỗ nào. Nó được coi là dữ liệu: không thể đổi cách review, nội
dung được post, hay bất kỳ setting nào.

Với trigger "một lần mention tôi", comment mở đầu bằng `@<your login>` sẽ yêu cầu review thay thế, nên pull
request không hiện command của tool. Watcher chỉ nhận khi comment thật sự nhờ bạn review pull request
này: `@minh review giúp` được tính, `@minh cảm ơn` thì không.

Chỉ comment của người có quyền write mới kích hoạt review:

| host | ai kích hoạt được |
|---|---|
| GitHub | owner, member hoặc collaborator |
| GitLab | Developer trở lên |
| Bitbucket | bất kỳ ai comment được — người không phải admin không đọc được quyền của user khác, nên hãy giới hạn ai được comment nếu điều đó quan trọng |

Comment do plugin post không bao giờ kích hoạt; comment của chính bạn thì có, nên một người có thể vừa là
developer vừa là reviewer.

## Chuyện gì xảy ra tiếp theo

- Watcher reply vào comment (trong thread của nó; comment thường trên GitHub không có thread, nên reply
  gắn link về comment đó) — "reviewing (commit abc1234)", bằng ngôn ngữ của lời yêu cầu — nêu commit mà
  nó đã nhận. Khi nhiều máy cùng theo dõi một repo, reply đó là khóa: reply đầu tiên thắng, máy nào thấy đã
  có reply thì lùi lại, và máy thua trong một cuộc đua sát nút sẽ xóa reply của chính nó.
- Một session tên `review <owner>/<repo>#<number>` chạy review như bình thường. Khi chạm giới hạn session,
  pull request chờ trong hàng đợi.
- Một yêu cầu mới trên pull request đã có session sẽ resume session đó khi nó nhờ kiểm tra lại các finding
  trước, và mở session mới khi nó nhờ review lại từ đầu (context cũ dễ gây hiểu sai khi pull request đã
  thay đổi). Khi không rõ, watcher hỏi bạn.
- `auto_submit_review` quyết định review được publish hay giữ dạng draft, trừ khi bạn dặn watcher khác đi.
  Draft không bao giờ được publish khi chưa có bạn.
- Khi một session đã báo kết quả, nó thuộc về bạn: watcher im lặng về nó và không bao giờ đọc những gì bạn
  viết ở đó, cho đến yêu cầu tiếp theo trên pull request đó.
- Session review Claude Code để idle 10 phút sau khi có kết quả sẽ được stop để giải phóng bộ nhớ; hội
  thoại vẫn được giữ, nên `claude attach <id>` và lượt re-review sau vẫn dùng được. Watcher không bao giờ
  đụng tới session không do nó mở.

## Mở một session

Một toast ở góc trên bên phải cho biết chuyện gì đang diễn ra — "Reviewing PR #12", "Posted review on PR
#12 — 1 🔴 2 🟠", "LGTM on PR #12", một draft đang chờ, một session cần câu trả lời. Click để tới đúng chỗ cần xử lý: câu
hỏi của session review thì mở session đó trong terminal của bạn, câu hỏi của chính watcher hoặc lỗi thì
đưa tab watcher lên trước, còn lại thì mở pull request; rê chuột vào để giữ toast lại; nút "1h" trên toast tắt toast trong một giờ. Khi bạn cần làm gì
đó, toast hiện command mở session. Trên macOS watcher tự vẽ toast (không cần quyền thông báo); trên
Linux nó dùng `notify-send`.

Mọi dòng chat đều kèm command mở session:

| nền tảng | loại session | mở bằng |
|---|---|---|
| Claude Code | interactive, chạy nền | `claude attach <id>` |
| Codex | non-interactive | `codex resume <id>` |
| Gemini CLI | non-interactive | `gemini -r <id>` |
| Cursor | non-interactive | `agent --resume <id>` |
| Antigravity | non-interactive | `agy --conversation <id>` |

Trên Claude Code, session cần câu trả lời (hoặc cần cấp quyền) sẽ chờ đến khi bạn attach vào. Trên các nền
tảng khác, session dừng lại kèm câu hỏi; watcher hỏi bạn rồi resume session với câu trả lời của bạn.

Watcher chạy bên ngoài shell sandbox: bên trong sandbox, việc poll không tới được host và session nền của
Claude Code treo ở bước khởi động. Session non-interactive dùng setting quyền bạn đã cấu hình cho nền tảng
đó; watcher không cấp quyền nào.

## Menu bar (macOS)

Watcher đưa con bướm lên menu bar khi nó khởi động, kèm số review đang chạy. Cả máy chỉ có một, bao quát
mọi watcher; nó ở lại cho đến khi bạn gõ `/open-pr:menubar close` (hoặc chọn Quit trong menu), và
`/open-pr:menubar` đưa nó trở lại. Menu của nó liệt kê:

- mỗi pull request một dòng, nhóm theo watcher (`<folder> · <terminal>`) — mục "Go to watcher tab" của nhóm đưa
  tab terminal đó lên trước (iTerm và Terminal chọn đúng tab sau khi macOS hỏi xin quyền Automation một
  lần; nếu không thì ứng dụng terminal được đưa lên trước); mỗi dòng hiện trạng thái mới nhất ngay tại
  chỗ (đang review, đã post kèm số finding, LGTM, draft, cần trả lời, lỗi) và luôn có: mở pull request,
  mở session trong terminal mà watcher đó đang chạy, copy command;
- snooze: 30 phút, 1 giờ, đến 9:00 sáng mai, hoặc bật lại toast.

Trên Windows và Linux, hãy nhắn watcher trong chat (`status`, `snooze 1h`).

## Nói chuyện với watcher

| nói | tác dụng |
|---|---|
| `status` | mỗi pull request một dòng, kèm trạng thái và command mở |
| `snooze 2h` / `resume toasts` | không hiện toast trên máy này cho đến lúc đó — cùng một công tắc với nút "1h" trên toast và snooze trên menu bar; hàng đợi vẫn chạy |
| một thay đổi setting | lưu vào `settings.json` |
| mở session mới cho PR 12 | lần kích hoạt tiếp theo trên PR đó mở session mới |
| `stop` | dừng theo dõi; các session review đang mở vẫn chạy tiếp |

## Giới hạn rate

Mỗi lần poll tốn ba API call trên GitHub; trên GitLab và Bitbucket là một, cộng thêm một cho mỗi pull
request được cập nhật kể từ lần poll trước. Khi host báo bị giới hạn rate, watcher tăng gấp đôi khoảng
thời gian poll (tối đa 15 phút) và quay về `poll_interval_seconds` sau lần poll thành công tiếp theo.

## Setting

Lưu ở `<data>/<repo>/settings.json` dưới `watch_review`:

| field | default | nghĩa |
|---|---|---|
| `max_concurrent` | `5` | số session review active cùng lúc (đang chạy hoặc đang chờ câu trả lời) |
| `poll_interval_seconds` | `60` | bao lâu kiểm tra pull request một lần |
| `notify.review_started` | `true` | toast: một session review vừa mở |
| `notify.question` | `true` | toast: một session cần câu trả lời, hoặc bị lỗi |
| `notify.draft_ready` | `true` | toast: một review draft đang chờ bạn duyệt |
| `notify.posted` | `true` | toast: một review đã được post, hoặc LGTM |
| `notify.re_review` | `true` | toast: một session có sẵn được resume để re-review |
| `notify.error` | `true` | toast: có lỗi (claim, session, poll) — quay lại terminal của watcher để xem |
| `trigger` | `/open-pr` | cái gì yêu cầu review: `/open-pr`, hoặc `@me` cho một lần mention account mà watcher đang chạy |
