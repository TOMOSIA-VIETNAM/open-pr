# Spec: `/open-pr:watch` — một watcher, hai vai: review và fix

Nền: `/open-pr:watch-review` (PR #140) đã có watcher cho vai review — trigger trên PR, session review
nền, toast, menu bar, claim bằng reply, rate-limit backoff. Spec này thêm vai **fix** và gộp hai vai
vào một watcher. Chưa release ⇒ đổi tên `watch-review` → `watch`, không giữ alias.

## Vấn đề

Review post finding xong, dev chỉ biết qua notification của vendor (dễ trôi); thực tế người review
vẫn phải nhắc dev đi fix. Một người thường vừa review PR người khác vừa fix PR của mình, trên cùng
repo — không được giới hạn.

## Luồng

1. Dev chạy `/open-pr:watch [review|fix] [PR…]` (mặc định cả hai vai) — chọn repo như hiện tại.
2. **Vai review**: như `watch-review` hiện tại (trigger `/open-pr` hoặc `@me`).
3. **Vai fix**: theo dõi PR **do chính mình tạo**:
   - không truyền PR ⇒ mọi PR đang mở của mình trong repo đã chọn;
   - truyền PR ⇒ chỉ những PR đó;
   - tự nhận thêm PR khi **chính mình** comment trigger gọi review trên **PR của mình**.
4. PR đang theo dõi (vai fix) nhận review mới mang `bot-finding` chưa được reply ⇒ toast
   "#N có 2 🟠 SHOULD FIX, 4 🔵" kèm nút "Fix now".
5. User bấm "Fix now" (toast hoặc menu bar) ⇒ mở session fix nền chạy `/open-pr:fix <url>` trong
   **worktree riêng của nhánh PR** (không đụng working tree dev đang code dở) ⇒ fix commit/push/reply
   theo luật `fix.md` (🔵/📝 vẫn hỏi) ⇒ câu hỏi ⇒ toast `question`, focus session.
6. Fix xong ⇒ toast `posted`-tương đương ("Đã fix #N, 3 reply") + hỏi dev có gọi re-review không
   (AskUserQuestion + toast) — không tự comment `/open-pr`.
7. `unwatch #N` (chat) hoặc "Remove from list" (menu bar) bỏ một PR ở cả hai vai; PR merge/đóng tự gỡ
   (kiểm 10 phút một lần — đã có từ PR #140).

## Quyết định đã chốt

| # | Quyết định | Lý do |
|---|---|---|
| 1 | Một command `/open-pr:watch [review\|fix] [PR…]`, mặc định cả hai | Một người thường làm cả hai vai; một lệnh, ít shim; không ai nghĩ đó là hai watcher |
| 2 | Một watcher, một `wait` mỗi repo mỗi máy (khoá exit 10 giữ nguyên) | Hai watcher cùng repo chia nhau event; một `wait` poll một lần cho cả hai vai |
| 3 | Mỗi PR mang vai `review` và/hoặc `fix`; mỗi vai một session riêng (review đọc, fix sửa code — không chung context) | PR của mình tự gọi review ⇒ review xong rồi mới tới fix |
| 4 | Vai fix: toast kèm **"Fix now"**, bấm mới mở session fix | Fix sửa code thật và push — rủi ro cao hơn review; người giữ cổng |
| 5 | Session fix chạy trong worktree riêng của nhánh PR | Không đè lên code dev đang viết dở |
| 6 | Chỉ finding có marker `bot-finding` (của plugin) | Review "changes requested" của người thật: để sau (fix.md cần đọc được dạng đó) |
| 7 | Re-review sau fix: hỏi dev, không tự comment trigger | Comment là hành động lộ ra trên PR; tránh vòng lặp bot ↔ bot |
| 8 | "Của mình" = author PR = account vendor đang đăng nhập (`<op> account`) | Không cần config |
| 9 | Menu bar: nhóm theo watcher, trong nhóm tách **review** và **fix** (không trộn), nhãn vai trên dòng | Dễ nhìn khi một người có cả hai loại |
| 10 | Chi phí token: phần vai fix ở `cases/watch-fix.md`, chỉ nạp khi vai fix bật | Người chỉ review không trả thêm |

## Poll gộp và quota

Quota (cần tra lại docs mới nhất trước khi làm):

| Vendor | Giới hạn chính | Tính theo | Ghi chú |
|---|---|---|---|
| GitHub REST | 5.000 req/giờ (Enterprise Cloud 15.000) | user — chung mọi token của user (`gh`, IDE, CI dùng token cá nhân) | request có điều kiện trả **304 không trừ quota**; giới hạn phụ: 100 request đồng thời, ~900 điểm/phút/endpoint, tạo nội dung ~80/phút, 500/giờ |
| GitLab.com | ~2.000 req/phút | user | self-managed: admin đặt |
| Bitbucket Cloud | 1.000 req/giờ cho dữ liệu repo | user | chặt nhất |

Một lượt poll phục vụ cả hai vai:

| Vendor | Review cần | Fix cần thêm |
|---|---|---|
| GitHub | issue comments + pull comments từ cursor (đã có) | finding LINE: có sẵn trong pull comments đã tải. Finding FILE nằm trong review body ⇒ `pulls/N/reviews` **chỉ cho PR của mình có `updated_at` > cursor** (thường 0–1) |
| GitLab | discussions của MR cập nhật từ cursor (đã có) | nằm sẵn trong các discussion đó — 0 request thêm |
| Bitbucket | comments của PR cập nhật từ cursor (đã có) | nằm sẵn — 0 request thêm |

Tiết kiệm thêm (áp cho mọi vai):

1. **ETag (GitHub)**: lưu ETag từng endpoint trong state; gửi `If-None-Match`; 304 ⇒ không trừ quota,
   không có dữ liệu mới. Poll khi repo yên gần như miễn phí.
2. **Poll thưa khi rảnh**: không session active và không event trong N phút ⇒ chu kỳ 60 s → 180 s; có
   event ⇒ về 60 s. Mọi vendor (Bitbucket cần nhất).
3. Rate-limit backoff: giữ nguyên.

## Event mới từ `wait`

- `{"event":"findings","repo","pr","review_id","counts":{…},"url"}` — PR vai fix có review mới mang
  `bot-finding`, chưa được reply. Mỗi review_id chỉ một lần (state: `seen_reviews`).
- Trigger trên PR của mình do chính mình comment ⇒ ngoài event `trigger` (vai review), PR được ghi vào
  danh sách vai fix (không claim).

## State

`<data>/<repo>/watch-review/` đổi thành `<data>/<repo>/watch/` (chưa release — không cần migrate):
- `sessions` key theo `"<pr>:<role>"` (`review` | `fix`), cùng các field hiện có.
- `fix_prs`: PR vai fix đang theo dõi (`auto` = PR của mình | `listed` | `enrolled`).
- `seen_reviews`, `etags`, `idle_since`.
- `.hidden`, `open_checked_at` (đã có từ PR #140).

## Command và prompt

- `src/commands/watch.md` (đổi tên từ `watch-review.md`): Step 1 chọn repo + vai; Step 2 setting
  (thêm `roles` mặc định); Step 3 xử lý event theo vai; vai fix trong `cases/watch-fix.md`.
- `cases/watch-session.md` phục vụ cả session fix (status file, không ghi `<data>` ngoài phần của nó);
  `fix.md` nhận `--status-file` giống `review.md`.
- Shim, toml, token scenario, chart line, README, docs: đổi tên + thêm vai fix.

## Không làm

- Tự fix không qua "Fix now" (có thể là setting sau).
- Review của người thật (không marker).
- Tự gọi re-review.
