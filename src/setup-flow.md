# Setup flow — thiết lập lần đầu cho 1 repo

Không phải slash command (nằm ngoài `commands/`); `commands/review-pr.md` nạp bằng `Read` khi repo chưa
thiết lập xong.

Toàn bộ thao tác dưới đây chạy tại **ĐÚNG pwd hiện tại của phiên** — thư mục mà lệnh `/open-code-review:review-pr`
được gọi. TUYỆT ĐỐI KHÔNG `cd` sang thư mục khác, KHÔNG tự dò tìm "git root"/"thư mục repo thật
sự", KHÔNG dùng basename của bất kỳ thư mục nào để suy ra đường dẫn hay tên repo. Tên thư mục memory
`<repo>` LUÔN là segment `<repo>` đã parse từ PR URL (xem block "Ngữ cảnh" của `review-pr.md`), KHÔNG suy
từ pwd/thư mục con/git remote. Đứng ở đâu tạo ở đó — không ngoại lệ.

Công cụ được phép: `Read`/`Write`/`Edit`, `git`/`cp`/`mkdir` (qua Bash), và `Agent` (chỉ ở Phần C —
spawn subagent quét convention song song). Dùng `cp` để copy nguyên bản file (không Read+Write lại
qua context — tốn token); `mkdir -p` để tạo thư mục.

## Phần A — Bootstrap `notebooks/review/<repo>/`

1. Dùng `Write` tạo `notebooks/review/<repo>/memory.md` — khung index RỖNG:
   ```
   <!-- Index. Mỗi dòng 1 entry, ngắn gọn, không lặp từ:
        - [tag] [nhãn ngắn](path) — hook 1 dòng
        `path` trỏ tới memories/<slug>.md (lesson tự học, xem Phần E) HOẶC thẳng path trong repo
        (tham chiếu convention có sẵn của dự án, xem Phần C — doctor; KHÔNG copy nội dung, chỉ trỏ
        path). Nhiều tag nếu áp dụng nhiều stack, vd [rails][ruby]. Giữ mỗi dòng dưới 1 câu, gộp ý
        trùng lặp, không diễn giải lại "xem convention tại..." — bản thân link đã nói điều đó. -->
   ```
2. Dùng `Write` tạo `notebooks/review/<repo>/memories/.gitkeep` (rỗng) — chỉ để vật lý hoá
   thư mục `memories/` (git không track thư mục rỗng).
3. Dùng `Write` tạo `notebooks/review/<repo>/templates/.gitkeep` (rỗng) — thư mục này sẽ chứa
   bản LOCAL copy của (các) template stack đang dùng trong repo (xem Phần B), tạo sẵn thư mục trước.
4. Kiểm `notebooks/review/.gitignore` đã tồn tại chưa (`Read` thử) — file RIÊNG của git nested
   `notebooks/review/.git` (khác `.gitignore` của repo chính ở bước 8 dưới), cần có để worktree
   ephemeral chứa code PR checkout (Bước 1 của `review-pr.md`, dưới
   `notebooks/review/<repo>/worktrees/...`) KHÔNG bao giờ lọt vào git nested này — nested repo chỉ
   nên chứa memory/template/rule, không phải code PR đang review:
   - Chưa tồn tại → `Write` tạo mới `notebooks/review/.gitignore` chỉ chứa đúng 1 dòng `worktrees/`.
   - Tồn tại nhưng CHƯA có dòng `worktrees/` (repo nested có thể đã tạo từ trước Task P11) → `Edit`
     append thêm dòng đó.
   - Đã có đủ → bỏ qua.
5. Copy `ALWAYS_RULE.md` từ plugin vào bản LOCAL của repo bằng `cp` (KHÔNG Read+Write qua context):
   `cp "${CLAUDE_PLUGIN_ROOT}/ALWAYS_RULE.md" "notebooks/review/<repo>/ALWAYS_RULE.md"`. Từ
   đây về sau `review-pr.md` (Bước 5) đọc BẢN LOCAL này — team có thể mở/chỉnh sửa ngay trong repo của họ
   theo dự án, không cần vào tận plugin. Bản trong plugin chỉ là "seed" mặc định lúc bootstrap.
6. Hỏi user **6 hoặc 7 câu trong 1 lượt** (tuỳ có CI hay không — xem câu 5), ngay trong chat (câu
   hỏi tự nhiên là đủ, không bắt buộc tool cụ thể): (1) ngôn ngữ output — vi/en/ja; (2)
   `auto_submit_review` true/false (mặc định **false**); (3) `auto_resolve_fixed_findings`
   true/false (mặc định **false**); (4) `doctor_schedule` — chu kỳ doctor lại convention (`{N} days`
   | `{N} weeks` | `{N} months` | `never`; mặc định **`1 months`** nếu user không chọn); (5)
   `review_ci_status` true/false — **CHỈ hỏi nếu mảng "CI checks" ở Ngữ cảnh của PR đang review
   KHÔNG rỗng** (repo/PR này có ít nhất 1 check thật, dù pass hay fail — nghĩa là có cấu hình CI);
   mảng đó RỖNG (không có CI nào chạy trên PR này) → **bỏ qua câu hỏi này hoàn toàn** (hỏi cũng vô
   nghĩa vì chưa có gì để đối chiếu), tự ghi `false`, không cần báo lý do trong chat (hiển nhiên từ
   ngữ cảnh); (6) `many_files_threshold` — số file thay đổi vượt mức thì hỏi chiến lược review
   trước khi làm (mặc định **`30`** nếu user không chọn); (7) `big_file_threshold_kb` — size
   diff/file (KB) vượt mức thì coi là file to/dump, peek có giới hạn thay vì review chi tiết (mặc
   định **`20`** ~ 5.000 token, ước lượng ~4 ký tự/token, nếu user không chọn). Xử lý câu trả lời:
   - **Ngôn ngữ** → `Edit` bản LOCAL vừa copy ở bước 5: thay đúng token `{{OUTPUT_LANGUAGE}}` trong
     khối code fence bằng giá trị cụ thể (`English` / `Vietnamese` / `Japanese`, …). KHÔNG thêm
     field ngôn ngữ vào `meta.json`. "Đã hỏi chưa" = placeholder còn nguyên hay đã được thay.
   - **`auto_submit_review` / `auto_resolve_fixed_findings` / `doctor_schedule` / `review_ci_status`
     / `many_files_threshold` / `big_file_threshold_kb`** → ghi nhớ, đưa vào `meta.json` cùng
     `bootstrapped: true` ở bước 9 (schema Phần D). `doctor_schedule` thiếu hoặc không parse được →
     ghi `"1 months"`; `review_ci_status` KHÔNG hỏi (câu 5 bị bỏ qua vì không có CI) → ghi `false`;
     `many_files_threshold` thiếu/không parse được số → ghi `30`; `big_file_threshold_kb` thiếu/
     không parse được số → ghi `20`.
7. Kiểm `notebooks/review/.git` đã tồn tại chưa (thử `Read` file `notebooks/review/.git/HEAD`):
   - **CHƯA tồn tại** → `git init notebooks/review` — 1 git repo DUY NHẤT, nested, độc lập hoàn
     toàn với git của repo chính đang review, bao trùm MỌI `<repo>/` sẽ có sau này. TUYỆT ĐỐI
     KHÔNG set remote, KHÔNG push — chỉ auto-commit local. Sau đó
     `git -C notebooks/review add <repo>` (kèm `notebooks/review/.gitignore` mới tạo ở bước 4 nếu
     có) rồi `git -C notebooks/review commit -m "chore: init review memory for <repo>"`
     — xem cách xác định `user.name`/`user.email` cho commit này ngay dưới đây.
   - **ĐÃ tồn tại** (đã từng review 1 repo khác trên cùng máy) → KHÔNG init lại. Chỉ
     `git -C notebooks/review add <repo>` (kèm `notebooks/review/.gitignore` nếu bước 4 vừa
     tạo/sửa) rồi `git -C notebooks/review commit -m "chore: add review memory for <repo>"`.

   **Danh tính commit** (áp dụng cho mọi commit vào `notebooks/review/.git`, ở đây và ở Phần B/C/E):
   thử `git config user.name` / `git config user.email` tại pwd (root repo CHÍNH đang review — lệnh
   `git config` không kèm `--local`/`--global` tự resolve local (project) trước rồi global, đúng thứ
   tự ưu tiên cần dùng). Nếu có kết quả → dùng giá trị đó cho commit vào `notebooks/review/.git`
   bằng cờ `-c user.name="<giá trị>" -c user.email="<giá trị>"` NGAY SAU `-C notebooks/review` (tức
   `git -C notebooks/review -c user.name="..." -c user.email="..." commit -m "..."` — giữ đúng thứ
   tự này để khớp `allowed-tools`, KHÔNG đặt `-c` trước `-C`). Nếu CẢ project lẫn global đều không
   có `user.name`/`user.email` nào (commit báo lỗi thiếu identity) → mới dùng fallback
   `-c user.name="review-plugin" -c user.email="review-plugin@local"`. KHÔNG set global config của
   máy trong bất kỳ trường hợp nào.
8. Kiểm `.gitignore` tại pwd hiện tại (dùng `Read` tại `./.gitignore`):
   - Tồn tại và CHƯA có dòng `notebooks/review/` → dùng `Edit` append thêm dòng đó.
   - Chưa có `.gitignore` → dùng `Write` tạo mới chỉ chứa đúng 1 dòng `notebooks/review/`.
9. Ghi nhận vào `notebooks/review/<repo>/meta.json` (tạo file nếu chưa có, giữ nguyên các field
   khác nếu file đã tồn tại từ trước — xem Phần D): `"bootstrapped": true`,
   `"auto_submit_review": <bước 6>`, `"auto_resolve_fixed_findings": <bước 6>`,
   `"doctor_schedule": "<bước 6, default 1 months>"`,
   `"review_ci_status": <bước 6 — PR có CI → hỏi, default true nếu user không chọn; PR không có
   CI → không hỏi, ghi thẳng false>`,
   `"many_files_threshold": <bước 6, default 30>`, `"big_file_threshold_kb": <bước 6, default 20>`,
   và object `_comments` (ít nhất key
   `doctor_schedule` — text gợi ý giá trị hợp lệ để user sửa tay; xem Phần D). Runtime/`review-pr.md`
   **bỏ qua** mọi key trong `_comments` (chỉ là chú thích cho người đọc file).

## Phần B — Copy/tạo local template cho (các) stack hiện có trong PR đang review

Với MỖI stack đã detect được ở Bước 2 của `review-pr.md` mà CHƯA có trong `templates_copied` (mảng trong
`meta.json`, xem Phần D):

1. Kiểm `${CLAUDE_PLUGIN_ROOT}/templates/<stack>.md` có tồn tại không (plugin có sẵn template cho
   stack này chưa).
   - **Có sẵn** → copy nguyên bản bằng `cp` (KHÔNG Read+Write qua context — tốn token với file dài):
     `cp "${CLAUDE_PLUGIN_ROOT}/templates/<stack>.md" "notebooks/review/<repo>/templates/<stack>.md"`
     (bản LOCAL, repo có thể tự chỉnh sửa riêng sau này mà không ảnh hưởng plugin dùng chung cho
     repo khác).
   - **CHƯA có sẵn** (plugin chưa cover stack này) → tự soạn 1 template MỚI theo đúng khung 6 mục
     (1.Lỗi&logic 2.Bảo mật 3.Hiệu suất 4.Chất lượng code 5.Đặc thù framework/ngôn ngữ 6.Bảo trì&dễ
     đọc — tham khảo các file trong `${CLAUDE_PLUGIN_ROOT}/templates/` để giữ văn phong/độ chi tiết
     nhất quán, KHÔNG lặp tiêu chí đã có trong baseline `ALWAYS_RULE.md`, chỉ viết phần đặc thù),
     lưu vào `notebooks/review/<repo>/templates/<stack>.md`. Báo cho user biết trong chat là
     đã tự tạo template mới cho stack này, kèm gợi ý: user có thể tự copy file này vào
     `${CLAUDE_PLUGIN_ROOT}/templates/` để dùng chung cho repo khác — plugin KHÔNG tự động làm (tránh
     mutate file dùng chung từ 1 phiên review của 1 repo cụ thể).
2. Thêm `<stack>` vào mảng `templates_copied` trong `meta.json`.
3. `git -C notebooks/review add <repo>` + commit (local only) phần thay đổi này.

## Phần C — Doctor: khám phá convention có sẵn của dự án

Mục tiêu: nếu dự án đang review đã tự định nghĩa convention/coding rule riêng ở đâu đó (README,
CLAUDE.md, AGENTS.md, docs/, wiki, cursor/copilot rules...), review phải THAM CHIẾU tới đúng nguồn
đó thay vì đoán mò hoặc áp đặt rule ngoài không phù hợp.

Doctor chạy khi `doctored` chưa `true`, **hoặc** lịch `doctor_schedule` đã hết hạn so với
`doctored_at` (xem `review-pr.md` Bước 3), **hoặc** user chủ động "doctor lại". Mỗi lần chạy phải
làm THẬT KỸ: quét TOÀN BỘ repo, không giới hạn theo stack/tính năng PR hiện tại.

1. **Quét ĐỆ QUY toàn bộ cây thư mục repo tại pwd** (KHÔNG chỉ root) để tìm HẾT mọi nguồn convention
   — dự án thật thường rải nhiều file ở subfolder, vd `app/operation/AGENTS.md`,
   `app/serializers/AGENTS.md`, không chỉ 1 file gốc. Tìm: `README.md`, `CLAUDE.md`, `AGENTS.md`,
   `GEMINI.md` (và biến thể tương tự như `.md` hướng-dẫn-agent khác), thư mục `docs/`, `wiki/`,
   `.cursorrules` / `.cursor/rules/`, `.github/copilot-instructions.md` — bất kể nằm ở subfolder
   nào. Bỏ qua nguồn không tồn tại, không coi là lỗi.
   **Dùng `Agent` để chạy SONG SONG cho nhanh trên repo lớn** (đã có trong `allowed-tools` của
   `review-pr.md`): 1 subagent quét toàn cây thư mục (glob/grep) trả về DANH SÁCH path các file convention;
   rồi spawn NHIỀU subagent song song (mỗi subagent 1 file hoặc 1 nhóm file) để đọc + tóm tắt +
   phát hiện convention/mâu thuẫn — thay vì main agent đọc tuần tự từng file (chậm). Không giới hạn
   loại subagent cụ thể (portable qua các môi trường team cấu hình tên subagent khác nhau).

   **Cùng lượt quét này (KHÔNG thêm bước riêng), kiểm tra thêm sự tồn tại của PR template của dự
   án** — khác `project_docs_found` ở trên (nguồn convention chung), đây là 1 field riêng dùng ở
   `review-pr.md` Bước 7 để đối chiếu checklist PR template với description thật của PR. Kiểm các path phổ
   biến: `.github/PULL_REQUEST_TEMPLATE.md`, `.github/pull_request_template.md`,
   `.github/PULL_REQUEST_TEMPLATE/*.md` (GitHub hỗ trợ 1 thư mục nhiều template, chọn qua query
   param), `PULL_REQUEST_TEMPLATE.md` (root), `docs/PULL_REQUEST_TEMPLATE.md`. Giữ lại danh sách
   path THỰC SỰ tồn tại (mảng rỗng nếu không path nào có) để ghi vào `meta.json` ở bước 6 dưới đây.
2. Với mỗi nguồn tìm được, đọc phần nội dung liên quan tới coding convention/tiêu chí review (bỏ qua
   phần không liên quan như giới thiệu sản phẩm, hướng dẫn cài đặt/deploy).
3. **KHÔNG copy nội dung đã đọc vào memory.** Với mỗi nguồn có convention rõ ràng, không mâu thuẫn
   với gì khác, chỉ thêm 1 dòng THAM CHIẾU vào `memory.md`, đúng format đã ghi ở khung comment Phần
   A: `- [tag nếu xác định được stack liên quan] [nhãn ngắn](path) — hook 1 dòng tóm tắt convention`
   — vd `- [rails] [Controllers](app/controllers/AGENTS.md) — mỏng, không params.permit`. Hook phải
   NGẮN, cô đọng đúng ý chính, không lặp lại cụm "xem convention dự án tại" (bản thân link đã trỏ
   rồi). Khi review, agent tự đọc lại đúng file tại path đó lúc cần — không dựa vào bản copy có thể
   đã lỗi thời.
4. **Nếu phát hiện mâu thuẫn** — 2 nguồn nói khác nhau về cùng 1 vấn đề, HOẶC 1 nguồn tự mâu
   thuẫn/mơ hồ, HOẶC nguồn đó xung đột với baseline/template của plugin (`ALWAYS_RULE.md`/template):
   tự phán đoán cách reconcile hợp lý nhất (ưu tiên nguồn viết riêng cho convention/AI-agent như
   `CLAUDE.md`/`AGENTS.md` hơn `README.md` giới thiệu chung; ưu tiên nguồn cụ thể/chi tiết hơn nguồn
   chung chung). Ghi bản đã reconcile thành 1 lesson theo Phần E (nội dung do agent tự soạn để giải
   quyết mâu thuẫn, không copy nguyên văn 1 nguồn nào), nêu rõ nguồn nào mâu thuẫn với nguồn nào và
   vì sao chọn hướng này. Đây là trường hợp DUY NHẤT ghi lesson mà không cần xác nhận user (agent tự
   soạn trong lúc doctor).
5. Ghi nhận vào `meta.json`: `"doctored": true`, `"doctored_at": "<ngày giờ hiện tại>"`,
   `"project_docs_found": [<danh sách path đã tìm thấy ở bước 1, mảng rỗng nếu không có>]`,
   `"pr_template_paths": [<danh sách path PR template đã tìm thấy ở bước 1, mảng rỗng nếu không có>]`.
   (Submodule KHÔNG detect ở đây — `review-pr.md` Bước 1 mục 5 tự kiểm `.gitmodules` trực tiếp mỗi
   lần, không cache qua `meta.json`.)
6. `git -C notebooks/review add <repo>` + commit (local only) phần thay đổi này.

## Phần D — Schema `meta.json`

```json
{
  "bootstrapped": true,
  "doctored": true,
  "doctored_at": "2026-07-13T10:00:00Z",
  "doctor_schedule": "1 months",
  "project_docs_found": ["README.md", "CLAUDE.md"],
  "templates_copied": ["rails", "vue"],
  "auto_submit_review": false,
  "auto_resolve_fixed_findings": false,
  "pr_template_paths": [".github/PULL_REQUEST_TEMPLATE.md"],
  "review_ci_status": true,
  "many_files_threshold": 30,
  "big_file_threshold_kb": 20,
  "_comments": {
    "doctor_schedule": "Allowed: \"{N} days\" | \"{N} weeks\" | \"{N} months\" | \"never\". Examples: \"7 days\", \"2 weeks\", \"1 months\". Default: \"1 months\"."
  }
}
```

`_comments` (object string): chú thích cho người sửa `meta.json` tay — **không** phải config runtime.
`review-pr.md` / doctor / bootstrap bỏ qua toàn bộ keys trong đây. Bootstrap (Phần A bước 9) LUÔN
ghi (hoặc bổ sung nếu thiếu) `_comments.doctor_schedule` đúng text mẫu trên. Khi Phần C/`Edit`
`meta.json`, giữ nguyên `_comments` nếu đã có.

**3 nhóm field — phân loại rõ để không nhầm khi thêm field mới:**
- **User config** (Phần A hỏi user lúc bootstrap, đổi lại được qua "đổi cấu hình review"):
  `auto_submit_review`, `auto_resolve_fixed_findings`, `doctor_schedule`, `review_ci_status`,
  `many_files_threshold`, `big_file_threshold_kb`. Thiếu ở repo đã bootstrap từ trước →
  `review-pr.md` Bước 3 tự backfill
  default + báo 1 lần (chi tiết đầy đủ nằm ở Bước 3 đó, không lặp lại ở đây).
- **Doctor-detected** (Phần C tự dò lại theo lịch, không phải setting user chọn): `project_docs_found`,
  `templates_copied`, `pr_template_paths`. Thiếu vì doctor chưa từng chạy/đang due → chờ Phần C chạy
  lại bình thường, KHÔNG áp dụng backfill của nhóm User config.
- **Internal/system state** (cờ trạng thái nội bộ của chính plugin — không phải setting, không có
  khái niệm "thiếu vì outdate"): `bootstrapped`, `doctored`, `doctored_at`, `_comments`. KHÔNG áp
  dụng backfill/notify gì cả — luôn được Phần A/C ghi đúng lúc cần.

**Khi thêm field mới vào schema này**: xếp NGAY vào đúng 1 trong 3 nhóm trên tại chính đoạn này. Nếu
là **User config** → PHẢI thêm luôn vào câu "Giữ từ meta" ở Bước 3 `review-pr.md` (đó là nơi DUY
NHẤT quyết định backfill/notify cho repo cũ) — 2 chỗ phải khớp, thêm ở đây mà quên bên đó thì field
mới sẽ không bao giờ được backfill cho repo đã golive.

`review-pr.md` coi bootstrap xong khi `bootstrapped: true`. Doctor: `doctored: true` **và** lịch
chưa hết hạn (`doctor_schedule` + `doctored_at`). `templates_copied` kiểm riêng mỗi lần (Phần B) —
stack mới vẫn copy được sau khi bootstrap/doctor xong.

`doctor_schedule` (string): `{N} days` | `{N} weeks` | `{N} months` | `never`. Hỏi lúc bootstrap
(Phần A bước 6), mặc định `"1 months"`. Thiếu field (repo cũ) → coi `"1 months"`. `never` → không
tự doctor lại theo lịch (vẫn chạy khi user "doctor lại" hoặc `doctored: false`). Hết hạn khi
`now > doctored_at + schedule` (parse N + đơn vị; thiếu/`invalid` `doctored_at` mà `doctored: true`
→ coi hết hạn, chạy lại Phần C). Sau mỗi Phần C thành công: cập nhật `doctored_at` (và
`doctored: true`).

Submodule KHÔNG có field riêng trong `meta.json` — `review-pr.md` Bước 1 mục 5 tự `Read` thử
`<worktree>/.gitmodules` trực tiếp mỗi lần (không cache), tránh gap "PR đầu tiên của repo mới luôn
bị bỏ qua submodule vì doctor chưa từng chạy".

`auto_submit_review`/`auto_resolve_fixed_findings`/`doctor_schedule` hỏi + ghi lúc bootstrap (Phần A
bước 6/9). `review-pr.md` Bước 3 đọc lại; dùng ở Bước 6/9 và gate doctor lịch.

`pr_template_paths` ghi lúc doctor (Phần C bước 1/5). `review-pr.md` Bước 3 đọc, Bước 7 dùng.

`review_ci_status` (boolean): chỉ HỎI lúc bootstrap (Phần A bước 6/9) khi PR đang review có ít nhất
1 CI check (mảng "CI checks" ở Ngữ cảnh không rỗng) — default `true` nếu user không chọn; PR không
có CI nào → KHÔNG hỏi, ghi thẳng `false` (hỏi cũng vô nghĩa). Thiếu field (repo cũ, backfill ở
`review-pr.md` Bước 3) → coi theo tín hiệu CI checks của LẦN REVIEW HIỆN TẠI (không mặc định cứng
`true`). `review-pr.md` Bước 3 đọc lại; Bước 7 dùng để quyết định có nêu cảnh báo CI check fail (đã
fetch ở Ngữ cảnh) trong overview hay bỏ qua hoàn toàn.

`many_files_threshold` (number): hỏi + ghi lúc bootstrap (Phần A bước 6/9), mặc định `30`. Thiếu
field hoặc không phải số hợp lệ (repo cũ) → coi `30`. `review-pr.md` Bước 3 đọc lại; Bước 7 dùng ở
guard số lượng file (PR đổi nhiều hơn ngưỡng này → hỏi chiến lược review, trừ khi ARGUMENTS/chat đã
chỉ định sẵn).

`big_file_threshold_kb` (number): hỏi + ghi lúc bootstrap (Phần A bước 6/9), mặc định `20` (~5.000
token, ước lượng ~4 ký tự/token — chỉ là quy đổi tham khảo, không chính xác tuyệt đối vì phụ thuộc
tokenizer/ngôn ngữ thật). Thiếu field hoặc không phải số hợp lệ (repo cũ) → coi `20`. `review-pr.md`
Bước 3 đọc lại; Bước 7 dùng ở guard size/dump (file có diff vượt ngưỡng này, tính bằng KB, hoặc
`UNKNOWN` → peek có giới hạn để phân loại data/dump thay vì review chi tiết dòng-by-dòng).

## Phần E — Ghi 1 lesson vào memory

Quy trình mechanical dùng chung cho: đồng thuận thread (Bước 6 / `re-review.md` — **sau** user
xác nhận trong chat), góp ý convention user gõ trong chat (`review-pr.md` Bước 10 — ghi ngay, không
hỏi lại), và mâu thuẫn reconcile ở Phần C (không hỏi). Phần E chỉ mô tả thao tác ghi.

1. Tạo `notebooks/review/<repo>/memories/<lesson-slug>.md` (slug kebab-case ngắn gọn, không
   dùng số thứ tự vô nghĩa). Nội dung tối thiểu: mô tả convention; ví dụ code trước/sau (nếu có);
   tag stack; ngày ghi nhận; nguồn (link PR liên quan nếu có).
2. Thêm 1 dòng vào index `notebooks/review/<repo>/memory.md`, đúng format đã ghi ở khung comment
   Phần A: `- [tag-stack] [nhãn ngắn](memories/<lesson-slug>.md) — hook 1 dòng` (nhiều tag nếu áp
   dụng nhiều stack). Hook ngắn gọn, không lặp từ, không diễn giải dài dòng — chi tiết đã có trong
   file `memories/<lesson-slug>.md`, index chỉ cần đủ để nhận ra lesson là gì.
3. `git -C notebooks/review add <repo>` + commit (local only, không push; nếu commit lỗi thiếu
   `user.name`/`user.email`, dùng cờ `-c` như Phần A).

## Khi user yêu cầu "doctor lại" / "quét lại convention dự án"

Sửa `doctored` trong `meta.json` thành `false` (hoặc xoá hẳn field đó) rồi thực hiện lại Phần C.
Có thể làm ngay trong chat, không cần đợi lần `/open-code-review:review-pr` kế tiếp.
