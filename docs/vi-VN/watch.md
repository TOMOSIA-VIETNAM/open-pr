# Theo dõi repo: review khi được yêu cầu, fix PR của chính bạn

[← README](../../README.vi-VN.md)

`/open-pr:watch` biến terminal nơi bạn chạy nó thành watcher cho một hoặc nhiều repo, đảm nhận cùng lúc
hai vai:

- **review** — developer yêu cầu review bằng cách comment trên pull request; máy bạn mở một session review
  riêng cho pull request đó.
- **fix** — một review mới trên pull request của chính bạn hiện toast các finding kèm nút "Fix now"; một
  click mở một session fix riêng cho pull request đó.

Watcher báo bạn mỗi khi có việc cần bạn. `/open-pr:watch review` hoặc `/open-pr:watch fix` chỉ giữ một
vai.

## Trước lần chạy đầu tiên

1. Chạy `/open-pr:review <any PR URL>` một lần trong từng repo. Watcher từ chối repo chưa thiết lập
   review memory, để không bao giờ có nhiều session cùng thiết lập nó một lúc.
2. Chạy `/open-pr:watch` trong một repo, hoặc trong thư mục workspace chứa nhiều repo. Lệnh liệt
   kê mọi repo và remote tìm thấy ở đó (clone có mỗi host một remote được liệt kê theo từng remote) rồi
   hỏi theo dõi những repo nào; repo đã thiết lập review memory được đề xuất.
   `/open-pr:watch owner/api owner/web` (hoặc URL của PR) chọn thẳng; URL của PR còn giới hạn vai fix vào
   đúng những pull request đó.
3. Lần chạy đầu trong một repo hỏi tối đa bao nhiêu session review được active cùng lúc, cái gì yêu cầu
   review (`/open-pr` hay một lần mention bạn) và bạn muốn nhận những toast nào, rồi lưu câu trả lời vào
   `settings.json` của repo đó.
4. Session review khởi động trong thư mục nơi bạn chạy watcher, như khi bạn gõ `/open-pr:review` ở đó —
   cùng thư mục dữ liệu, cùng trust. Trên Claude Code, thư mục đó phải là trusted workspace; watcher kiểm
   tra khi khởi động và, nếu chưa, bảo bạn mở `claude` ở đó một lần rồi chấp nhận lời hỏi trust.

Mỗi repo được theo dõi giữ setting riêng, kể cả giới hạn session (session review và fix dùng chung). Mỗi
repo có tối đa một watcher cho mỗi vai trên một máy: watcher review và watcher fix (`/open-pr:watch review` ở một tab, `/open-pr:watch fix` ở tab khác) chạy song song, mỗi watcher chỉ nhận việc của vai mình. Watcher thứ hai cho một vai đã có người giữ sẽ báo tiến trình nào đang giữ rồi bỏ qua repo đó. Khi host không kết nối được kéo
dài (mất mạng, login hết hạn), watcher báo cho bạn.

## Yêu cầu review

Comment trên pull request:

```
/open-pr
/open-pr please look closely at the migration
```

Phần chữ sau `/open-pr` là gợi ý nên xem chỗ nào — hoặc một câu hỏi (`/open-pr sao lock này cần thiết?`),
được trả lời ngay trong thread của comment thay vì review. Trigger kiểu mention chỉ nhận yêu cầu review:
câu hỏi gửi tới bạn bằng mention được báo cho bạn qua toast, watcher không tự trả lời. Nó được coi là dữ liệu: không thể đổi cách review, nội
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
  trích dẫn lại comment đó kèm link) — "taking a look (commit abc1234)", bằng ngôn ngữ của lời yêu cầu — nêu commit mà
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
- Pull request đã merge hoặc đã đóng sẽ rời menu bar trong vòng 10 phút, và session của nó được stop khi
  idle (hội thoại vẫn được giữ).

## Fix pull request của chính bạn

Vai fix theo dõi các pull request bạn tạo (tác giả là account mà watcher đang chạy), hoặc chỉ những pull
request bạn nêu tên. Một pull request cũng được thêm vào khi chính bạn yêu cầu review nó — comment
`/open-pr` trên pull request của mình, và finding của nó sẽ quay về với bạn.

1. Một review mới của plugin có finding chưa ai reply: toast hiện "#12: 2 🟠 SHOULD FIX, 4 🔵 SUGGESTION"
   kèm **Fix now**; dòng tương ứng trên menu bar cũng có.
2. Click **Fix now** (hoặc nói `fix #12` với watcher). Một session tên `fix <owner>/<repo>#12` chạy
   `/open-pr:fix` trong worktree riêng của nhánh pull request — cây thư mục bạn đang làm dở không bao giờ
   bị đụng tới. Finding 🔵 và 📝 vẫn hỏi bạn trước; khi `auto_push` tắt, session hỏi trước khi push.
3. Xong việc, watcher báo kết quả bằng toast và hỏi có yêu cầu re-review không. Chỉ khi bạn đồng ý, nó mới
   reply trên pull request bằng trigger (`/open-pr re-review`, hoặc mention reviewer khi repo dùng
   mention) — nó không bao giờ tự yêu cầu. Yêu cầu đó nằm trong thread của yêu cầu review ban đầu, để
   yêu cầu, lời nhận review và re-review ở cùng một chỗ; comment hội thoại trên GitHub không có thread,
   nên ở đó nó là một comment mới.

Không có gì được fix nếu bạn chưa click. `remove #12` (hoặc "Remove from list" trên dòng đó) đưa pull
request ra khỏi cả hai vai.

## Mở một session

Một toast ở góc trên bên phải cho biết chuyện gì đang diễn ra — "Reviewing PR #12", "Posted review on PR
#12 — 1 🔴 2 🟠", "LGTM on PR #12", một draft đang chờ, một session cần câu trả lời. Click để tới đúng chỗ cần xử lý: câu
hỏi của session review thì mở session đó trong terminal của bạn, câu hỏi của chính watcher hoặc lỗi thì
đưa tab watcher lên trước, còn lại thì mở pull request; rê chuột vào để giữ toast lại và hiện nút đóng cùng nút "1h" (tắt toast trong một giờ). Khi bạn cần làm gì
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

Watcher đưa con bướm lên menu bar khi nó khởi động, kèm số session đang chạy. Cả máy chỉ có một, bao quát
mọi watcher; nó ở lại cho đến khi bạn gõ `/open-pr:menubar close` (hoặc chọn Quit trong menu), và
`/open-pr:menubar` đưa nó trở lại. Menu của nó liệt kê:

- mỗi pull request và vai một dòng, nhóm theo watcher (tiêu đề là các repo nó watch; bên dưới là vai nó phục vụ, terminal, thư mục nó chạy khi khác tên repo duy nhất của nó, và lần poll gần nhất — `no poll for …` màu cam khi đã lỡ hai lượt poll; mỗi dòng nằm dưới watcher của vai nó); watcher chưa có dòng nào ghi "No pull requests yet"; dòng review trước rồi
  tới dòng fix, mỗi dòng gắn nhãn `· review` hoặc `· fix` — mục "Go to watcher tab" của nhóm đưa
  tab terminal đó lên trước (iTerm và Terminal chọn đúng tab sau khi macOS hỏi xin quyền Automation một
  lần; nếu không thì ứng dụng terminal được đưa lên trước; watcher đã bị đóng tab được mở lại bằng
  `claude attach`), còn "Stop" của nhóm dừng theo dõi mọi repo của watcher đó, watcher của vai kia vẫn chạy; mỗi dòng hiện trạng thái mới nhất ngay tại
  chỗ (đang review, đã post kèm số finding, LGTM, draft, cần trả lời, có finding mới, đang fix, đã fix,
  lỗi) và luôn có: **Fix now** trên dòng có finding mới, mở pull request,
  mở session trong terminal mà watcher đó đang chạy (tab mới của iTerm, Terminal, Ghostty hoặc WezTerm;
  terminal khác thì mở Terminal), copy command;
- rê chuột vào dòng watcher là mở panel setting của repo đó (watcher có nhiều repo thì liệt kê các repo
  trước, mỗi repo mở panel riêng): số session cùng lúc (1, 2, 3, 5, 8, 10), poll mỗi (1, 2, 3, 5 hoặc
  10 phút, bên dưới là số request mỗi giờ của lựa chọn hiện tại), trigger (`/open-pr` hoặc `@me`), mỗi
  event toast một checkbox, và các tuỳ chọn review: post review không qua draft, post LGTM khi không có
  finding, tự resolve finding đã fix, cảnh báo CI lỗi, doctor mỗi (1 tuần, 2 tuần, 1 tháng, 3 tháng,
  không bao giờ). Bên dưới là lần doctor chạy cuối và lần tới: `Doctor: Sep 20, 2026 · next in 11 days`,
  `· due now`, `· not scheduled`, hoặc `Doctor: never run`; và **Show settings file**, đóng menu rồi mở
  Finder chọn sẵn `settings.json` của repo đó;
- poll mỗi 15 giây, 30 giây, 1, 2, 3, 5 hoặc 10 phút, hoặc theo setting của từng repo — có hiệu lực sau vài giây,
  mỗi lựa chọn kèm số request ước tính mỗi giờ (xem Giới hạn rate);
- snooze: 30 phút, 1 giờ, đến 9:00 sáng mai, hoặc bật lại toast.

Click vào một control ghi đúng key đó vào `settings.json` (xem Setting bên dưới) và panel vẫn mở, hiện
giá trị đọc lại từ file; click ra ngoài mới đóng. Giá trị đặt trong chat mà panel không có sẵn thì hiện
thành một lựa chọn thêm, đang chọn và bị làm mờ.

"Remove from list" trên một dòng sẽ ẩn pull request đó và đưa nó ra khỏi vai fix, pull request đã merge
hoặc đã đóng tự rời danh sách trong vòng 10 phút, và một yêu cầu mới trên pull request đó sẽ đưa dòng trở lại.

Trên Windows và Linux, hãy nhắn watcher trong chat (`status`, `snooze 1h`).

## Nói chuyện với watcher

| nói | tác dụng |
|---|---|
| `status` | mỗi session một dòng (pull request, vai, trạng thái), kèm command mở |
| `fix #12` | mở session fix, giống **Fix now** |
| `remove #12` / `unwatch #12` | đưa pull request ra khỏi menu bar và khỏi vai fix |
| `snooze 2h` / `resume toasts` | không hiện toast trên máy này cho đến lúc đó — cùng một công tắc với nút "1h" trên toast và snooze trên menu bar; hàng đợi vẫn chạy |
| một thay đổi setting | lưu vào `settings.json` |
| mở session mới cho PR 12 | lần kích hoạt tiếp theo trên PR đó mở session mới |
| `stop` | dừng theo dõi; các session đang mở vẫn chạy tiếp |

## Giới hạn rate

Một lượt poll phục vụ cả hai vai. Trên GitHub nó tốn ba request có điều kiện: khi không có gì thay đổi,
host trả `304 Not Modified`, không bị tính vào giới hạn; vai fix thêm một call cho mỗi pull request của bạn
được cập nhật kể từ lần poll trước. Trên GitLab và Bitbucket, một lượt poll tốn một call, cộng thêm một cho
mỗi pull request được cập nhật kể từ lần poll trước, đã gồm cả finding. Khi không có session nào active và
không có gì mới trong 10 phút, watcher poll mỗi 10 phút (không bao giờ nhanh hơn setting; lựa chọn "Poll
every" cho cả máy luôn được giữ). Khi host báo bị giới hạn rate, watcher tăng gấp đôi khoảng thời gian poll
(tối đa 15 phút) và quay về `poll_interval_seconds` sau lần poll thành công tiếp theo.

Menu bar hiện, dưới phần header, quota còn lại thấp nhất trong các host đang watch, đọc từ header rate-limit
của chính các request poll (không thêm request nào) — vd `GitHub API 4,812/5,000 left`, màu cam khi còn dưới
30 %, đỏ khi dưới 10 %. Mỗi lựa chọn "Poll every" hiện số request mỗi giờ nó sẽ tốn, tính từ lần poll gần
nhất của từng repo, kèm ⚠ khi vượt một nửa giới hạn mỗi giờ của host (giới hạn theo phút của GitLab được quy
ra theo giờ). Bitbucket có thể chỉ báo là sắp chạm giới hạn; host không gửi header rate-limit thì không hiện
gauge.

## Setting

Lưu ở `<data>/<repo>/settings.json` dưới `watch`. Panel setting trên menu bar đổi được các field
này (và các tuỳ chọn review nó liệt kê); thay đổi có hiệu lực từ lượt poll kế tiếp của watcher và
session review kế tiếp — session đang chạy giữ giá trị nó đã đọc. Trigger là một login gõ tay
(`@alice`), các ngưỡng số và mọi thứ doctor tự phát hiện vẫn đổi qua chat.

| field | default | nghĩa |
|---|---|---|
| `max_concurrent` | `5` | số session active cùng lúc, tính chung review và fix (đang chạy hoặc đang chờ câu trả lời) |
| `poll_interval_seconds` | `180` | bao lâu kiểm tra pull request một lần |
| `notify.review_started` | `true` | toast: một session review vừa mở |
| `notify.question` | `true` | toast: một session cần câu trả lời, hoặc bị lỗi |
| `notify.draft_ready` | `true` | toast: một review draft đang chờ bạn duyệt |
| `notify.posted` | `true` | toast: một review đã được post, hoặc LGTM |
| `notify.re_review` | `true` | toast: một session có sẵn được resume để re-review |
| `notify.findings` | `true` | toast: review mới trên một pull request thuộc vai fix, kèm "Fix now" |
| `notify.error` | `true` | toast: có lỗi (claim, session, poll) — quay lại terminal của watcher để xem |
| `trigger` | `/open-pr` | cái gì yêu cầu review: `/open-pr`, hoặc `@me` cho một lần mention account mà watcher đang chạy |
