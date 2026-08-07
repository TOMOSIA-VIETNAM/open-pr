# Backlog: Bitbucket support

Mục tiêu: `/open-pr:review` + `/open-pr:fix` chạy trên Bitbucket Cloud với đủ tính năng như
GitHub/GitLab — comment line-by-line, overview, FILE-level, re-review, resolve thread, reply.

Phạm vi: **1 vendor `bitbucket`** (Cloud). Bitbucket Data Center HOÃN, xem Task B4.

Khác biệt nền tảng so với 2 vendor cũ: **Bitbucket không có CLI** ⇒ mọi entry là `curl` + `jq`,
credential tự truyền vào.

## Quyết định đã chốt với user

| # | Quyết định |
|---|---|
| 1 | Chỉ Bitbucket Cloud. Data Center là API khác hẳn (`/rest/api/1.0`: path, field, payload comment đều khác) nên phải là vendor dir riêng, KHÔNG nhồi branch vào cùng bộ file — và không ship khi chưa có instance để chạy thật |
| 2 | 1 PR duy nhất |
| 3 | Credential qua ENV VAR. Plugin chỉ nhắc TÊN biến, giá trị token không bao giờ vào context. Hướng dẫn set nằm trong vendor `fetch.md` (nơi agent đọc lúc chạy); README hoãn |
| 4 | `auto_submit_review: false` phải thật sự chưa có gì hiện trên PR. Bitbucket không có draft ⇒ tầng "chưa publish" là CHAT |
| 5 | Live verify do user tự chạy trên fixture Cloud của mình; agent KHÔNG tự gọi API thật của user |

## Ground truth — Bitbucket Cloud

Nguồn: OpenAPI spec chính thức `https://api.bitbucket.org/swagger.json`. Mọi path dưới đây có trong spec.

**Auth.** App password đã bị xoá hoàn toàn (brownout 2026-06-09, removed 2026-07-28) ⇒ còn 2 đường:
- API token gắn với 1 user: HTTP Basic `email:token` — `/user` gọi được.
- Repository/Workspace Access Token: `Authorization: Bearer <token>` — scope hẹp hơn, `/user` trả 401 ⇒
  "Fetch account running the command" BẮT BUỘC có nhánh không dựa vào `/user`.

**Path** (prefix `https://api.bitbucket.org/2.0/repositories/<owner>/<repo>`):

| việc | path |
|---|---|
| PR object (title/description/author/source/destination) | `/pullrequests/<n>` |
| head SHA | cùng object, field `source.commit.hash` |
| file list + số dòng thay đổi | `/pullrequests/<n>/diffstat` (paginated; `status`, `lines_added`, `lines_removed`, `old.path`, `new.path`) |
| unified diff | `/pullrequests/<n>/diff` — LÀ REDIRECT sang `/diff/{spec}` ⇒ cần `-L`; hỗ trợ query `path=` (lặp nhiều lần) |
| commits | `/pullrequests/<n>/commits` |
| comment list (inline + overview + reply) | `/pullrequests/<n>/comments` |
| tạo comment | `POST /pullrequests/<n>/comments` — inline: `{"content":{"raw":...},"inline":{"path":...,"to":<line>}}` (`from` = phía old); reply: `{"parent":{"id":<id>}}`; overview: bỏ `inline` |
| resolve | `POST /pullrequests/<n>/comments/<id>/resolve` (DELETE = unresolve); trạng thái ở field `resolution` |
| CI | `/pullrequests/<n>/statuses` |
| permalink của comment | field `links.html.href` trên chính comment |
| projection server-side | query `?fields=` — rẻ hơn jq vì cắt ngay ở network |

**Cái KHÔNG có:**
- Draft/pending review dùng được: schema `pullrequest_comment` có field `pending` nhưng KHÔNG có endpoint
  publish nào trong spec ⇒ mọi POST comment là public ngay.
- Reactions API (grep spec: 0 path) ⇒ "React to a PR comment" = No equivalent.
- Review object gộp ⇒ "Fetch PR reviews (FILE-level findings + review_id)" = No equivalent, như GitLab.
- Ref `refs/pull-requests/<n>/from`. Checkout phải đọc `source.branch.name` +
  `source.repository.full_name` + `source.commit.hash`; cùng repo → fetch branch từ `origin`, fork →
  fetch từ URL repo fork; rồi `checkout --detach <hash>`.

## Cơ chế "review chưa publish"

Interface yêu cầu: "Post a review" cho ra kết quả UNPUBLISHED, "Verify" nói nó còn unpublished không,
"Publish" mới làm nó hiện ra. Không có draft API ⇒ map vào chat, không thêm file nào:

- "Post a review": soạn review + payload từng finding TRONG CHAT, không gọi API. Sau bước này PR sạch.
- "Verify a posted review's state": đếm comment trên PR có marker của plugin (`core/finding-markers.md`).
  `0` = chưa publish gì; khác 0 = đã publish đúng số đó.
- "Publish the pending review": 1 POST/finding, overview trước.
- Publish fail giữa đường: chạy lại Verify, chỉ POST finding còn thiếu. CẤM POST lại cái đã có —
  Bitbucket không có bulk undo, trùng thì phải xoá tay từng comment.

`review.md` Bước 9 vốn trung lập ("stop at whatever the vendor calls pending/draft") nên chỉ cần thêm
nhánh "hoặc review đã soạn trong chat, với vendor không có draft".

## Task B1: URL → vendor

- File: `src/core/pr-target.md`.
- Acceptance:
  - Bảng regex thêm 1 dòng: `bitbucket` = `https://bitbucket\.org/[^/]+/[^/]+/pull-requests/[0-9]+` —
    host pin cứng vì Cloud chỉ có 1 host.
  - Discriminator không được để ai đoán: `/pull/` = GitHub, `/-/merge_requests/` = GitLab,
    `/pull-requests/` = Bitbucket. Không cặp nào chồng nhau.
  - Guard charset `owner`/`repo`/`pull_number` GIỮ NGUYÊN — workspace/repo slug của Bitbucket nằm trong
    bộ ký tự đang cho phép, không cần nới.
- Dependency: không.
- Status: DONE. Đoạn prose discriminator viết gọn vì bảng regex tự nói host pin vs `[^/]+`.

## Task B2: settings + bootstrap nhận giá trị vendor mới

- File: `src/setup/bootstrap.md`, `src/reference/settings-schema.md`.
- Acceptance:
  - `shared.git_remote_type` nhận thêm `"bitbucket"`.
  - KHÔNG bump `schema_version`, KHÔNG thêm `llm-upgrades/vN.md`: thêm giá trị hợp lệ cho field đã tồn
    tại không cần transform config repo cũ (`"github"`/`"gitlab"` vẫn hợp lệ y nguyên).
  - Không thêm field nào cho credential — token là env var, tuyệt đối không nằm trong `settings.json`.
- Dependency: B1.
- Status: DONE. Câu hỏi bootstrap KHÔNG liệt kê giá trị mà trỏ về bảng regex `core/pr-target.md`; nếu
  liệt kê thì vendor sau phải sửa 2 chỗ. `settings-schema.md` ghi valid values = tên thư mục dưới
  `src/vendors/`.

## Task B3: `src/vendors/bitbucket/`

- Acceptance:
  - 4 file `fetch.md`/`worktree.md`/`post.md`/`thread.md`, bộ heading `## <entry>` khớp TUYỆT ĐỐI với
    `src/vendors/github/` (cùng entry, cùng thứ tự từng group) — test parity bắt nếu lệch.
  - `fetch.md` mở đầu bằng phần vendor-wide (đúng chỗ interface quy định): thuật ngữ, base URL, và luật
    của vendor không-CLI dùng cho MỌI group — `fetch.md` luôn load trước nên post/thread dùng lại được,
    không cần file trung gian:
    - `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN` → `-u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN"`; hoặc
      `BITBUCKET_TOKEN` → `-H "Authorization: Bearer $BITBUCKET_TOKEN"`. Thiếu cả 2 → STOP, in hướng
      dẫn tạo token.
    - FORBIDDEN: in giá trị biến, `curl -v`/`-i`, nhét token vào URL, hỏi token qua chat.
    - `curl -sS --fail-with-body` (exit non-zero khi HTTP lỗi NHƯNG vẫn in body — chỗ duy nhất
      Atlassian nói lỗi gì); FORBIDDEN `-f` trơn.
    - JSON payload viết ra file rồi `--data @file`/`--data @-`; FORBIDDEN heredoc/`echo`/`-d` có nội
      dung nội suy — text finding là dữ liệu do PR kiểm soát.
  - Mỗi entry TỰ bound output: `?fields=` và/hoặc `jq` projection nằm TRONG lệnh, không lọc sau.
  - 2 entry diff dùng chung 1 response text (không có endpoint patch theo file), cắt tại `diff --git`;
    2 pipeline awk đặt tên `<patch_pipe>`/`<size_pipe>` trong bảng shorthand để không lặp lệnh:
    - patch: chỉ in chunk dưới `<max_patch_bytes>`.
    - size: byte thật từng chunk; path có trong diffstat mà không có chunk (binary / bị cắt) ⇒
      `UNKNOWN`, TUYỆT ĐỐI không phải 0.
  - Pagination: `values[]` + `next` ⇒ entry nào có thể vượt 1 trang phải lặp tới hết `next`.
  - `post.md` theo cơ chế chat ở trên; Post-error notes ghi rủi ro publish nửa vời + cách recover, và
    FORBIDDEN POST comment trong lúc soạn.
  - `thread.md`: "React to a PR comment" = **No equivalent**; "Finding permalink" = `links.html.href`.
  - "Fetch account running the command": `/user` cho API token; 401 dưới access token là ĐÁP ÁN
    (`UNKNOWN`), không phải lỗi auth để retry.
- Dependency: B1, B2.
- Status: DONE, đúng 4 file. 19/19 heading khớp `src/vendors/github/`.
  Ngoài acceptance, bắt buộc phải có: `core/finding-markers.md` thêm rule account `UNKNOWN` ⇒ CHỈ nhánh
  marker, cấm nhánh fallback (không có author để so thì fallback nhận vơ comment của người thật). Đây là
  caller-side ⇒ rule "vendor mới = 4 file, nothing else" trong `CLAUDE.md` không đúng, xem B8.

## Task B4 (HOÃN): Bitbucket Data Center

- Điều kiện khởi động: có instance DC để chạy `vendor_lint.py --url <PR_DC>`. Không có instance thì bộ
  lệnh chỉ đối chiếu được với spec, tức chưa ai chạy — không ship.
- Acceptance khi làm:
  - Vendor dir riêng `src/vendors/bitbucket-server/`, cùng bộ heading và cùng luật bound/auth/payload
    như B3, nhưng REST 1.0.
  - 1 dòng regex mới ở `core/pr-target.md`:
    `https://[^/]+/projects/[^/]+/repos/[^/]+/pull-requests/[0-9]+` — host bất kỳ vì self-hosted,
    `/projects/…/repos/…` là discriminator so với Cloud.
  - Repo cá nhân có project key `~username` ⇒ guard charset `owner` phải cho phép `~` ở ĐẦU cho riêng
    shape này, giữ nguyên các ký tự đang chặn, không nới cho vendor khác.
  - Auth `BITBUCKET_SERVER_TOKEN` (HTTP access token) → `Authorization: Bearer`. `<host>` lấy từ chính
    host của PR URL, không hardcode.
  - "Fetch account running the command": đọc header `X-AUSERNAME` (không có endpoint `/user`).
  - "React to a PR comment": có endpoint thật ⇒ implement, không phải No equivalent.
  - "Resolve a review thread": GET comment lấy `version` rồi mới PUT — sai `version` là fail.
  - Checkout dùng `refs/pull-requests/<n>/from`, detached.
- Ground truth đã verify theo spec `https://developer.atlassian.com/server/bitbucket/10.2.swagger.v3.json`
  (prefix `<host>/rest/api/latest/projects/<owner>/repos/<repo>`) — dùng lại, đừng research lại:

| việc | path |
|---|---|
| PR object | `/pull-requests/<n>` (`fromRef.latestCommit` = head SHA, `author.user.name`, `toRef.displayId` = base branch) |
| file list | `/pull-requests/<n>/changes` (`path.toString`, `srcPath.toString` khi rename) |
| unified diff | `/pull-requests/<n>.diff` (text), per-file `/pull-requests/<n>/diff/<path>` (JSON hunks, to hơn) |
| commits | `/pull-requests/<n>/commits` |
| comment list | `/pull-requests/<n>/activities` — `/comments` BẮT BUỘC query `path` nên không trả được cả PR |
| tạo comment | `POST /pull-requests/<n>/comments` — line: `anchor{diffType, line, lineType, fileType, path}`; reply: `parent.id`; overview: không có `anchor` |
| resolve | `PUT /pull-requests/<n>/comments/<id>` với `{"state":"RESOLVED","version":<version>}` |
| CI | `<host>/rest/build-status/latest/commits/<sha>` |
| reactions | `PUT <host>/rest/comment-likes/latest/projects/<owner>/repos/<repo>/pull-requests/<n>/comments/<id>/reactions/<emoticon>` |
| pagination | `isLastPage` + `nextPageStart` (khác Cloud dùng `next`) |
| draft review | `GET /pull-requests/<n>/review` = thread PENDING của chính user; `PUT` = complete review |

- 2 chỗ rủi ro cao nhất, soi trước khi tin: payload `anchor` khi tạo line comment, và `version` khi
  resolve. Spec KHÔNG mô tả cách TẠO một comment pending (chỉ có đọc/complete) ⇒ dùng cơ chế chat như
  B3, không đánh cược vào payload chưa kiểm chứng.
- Tên emoticon cho reactions: spec không khai enum ⇒ phải xác nhận trên instance thật.

## Task B5: `scripts/vendor_lint.py` lint được vendor không-CLI

- Acceptance:
  - Parser nhận thêm lệnh bắt đầu bằng `curl` (trước đó chỉ `gh`/`glab`/`git` ⇒ entry curl bị coi là
    "no command parsed" và FAIL).
  - Chế độ offline (chạy CI, không cần credential) thêm luật tĩnh cho entry `curl`: có
    `--fail-with-body`; URL cùng host với `<api>` của chính vendor đó; auth chỉ qua tên biến; KHÔNG
    credential literal; KHÔNG `-v`/`-i`/`-f` trơn; shorthand nào tự ghi flag MANDATORY thì phải có flag đó.
  - Chế độ live: chạy được các entry `Fetch` read-only với fixture thật + credential từ env. `parse_url`
    nhận shape URL mới; bỏ giả định "vendor nào cũng có 1 CLI để `command -v`".
  - Live mode TUYỆT ĐỐI không chạy entry `post`/`thread`.
- Dependency: B3.
- Status: DONE. Lint tự phát hiện vendor từ thư mục (không hardcode danh sách) và expand shorthand đọc
  từ chính bảng trong `fetch.md`, nên entry diff (`<diff_cmd> | <patch_pipe>`) chạy được ở live mode.
  Negative-test trên bản copy: cả 4 luật tĩnh đều bắt lỗi khi cố tình phá — không phải test rỗng.

## Task B6: test suite

- File: `tests/test_prompt_graph.py`.
- Acceptance:
  - Parity/reachability/interface-doc test tự quét `src/vendors/` ⇒ phải xanh với vendor mới, không sửa
    test. Đỏ thì lỗi ở vendor file, không phải ở test.
  - 2 guard cũ chỉ được nới đúng bản chất, không nới nghĩa: threshold `<max_patch_bytes>` được filter
    bởi `awk` khi diff về dạng 1 khối text (không chỉ `jq select`); `fields=` là marker bound hợp lệ
    (projection server-side). Test "description phải nêu mọi vendor" so khớp sau khi phẳng hoá `-`.
  - THÊM guard: không entry `curl` nào rò credential (`-v`/`-i`/literal); vendor `curl` phải báo lỗi
    HTTP kèm body.
- Dependency: B3.
- Status: DONE.

## Task B7: token budget

- File: `scripts/token_report.py`, `tests/budgets.json`.
- Acceptance:
  - Thêm atom cho 4 file vendor mới + scenario đo được load set thật (review, re-review, fix).
  - Ceiling trong `budgets.json` phải là số ĐO bằng `token_report.py`, không phải số đoán.
  - Bitbucket đắt hơn `gh`/`glab` là tất yếu (curl + jq dài hơn CLI wrapper). Scenario GitHub/GitLab đắt
    lên thì phải điều tra + nói rõ, không `--update-budgets` cho qua.
- Dependency: B3.
- Status: DONE, số đo thật. CẢNH BÁO GHI NHẬN: scenario GitHub/GitLab đắt thêm **+44 tok (+0.4%)**,
  scenario có re-review/fix **+71 tok (+0.8–0.9%)**. Nguyên nhân: `core/pr-target.md` +44 (luôn load, do
  1 dòng regex) và `core/finding-markers.md` +27 (rule `UNKNOWN`). Đã cắt hết chỗ cắt được; còn lại là
  giá của việc nhận thêm 1 vendor. Ceiling `upgrade`/`clean` giữ nguyên vì 2 scenario đó không đổi.

## Task B8: tài liệu dev

- Acceptance:
  - `CLAUDE.md`: Mission nêu đúng số vendor. Rule "một vendor mới = 4 file, không sửa gì khác" KHÔNG
    đúng (kéo theo regex row, scenario budget, và với vendor không CLI thì cả lint) → viết lại rule,
    không bolt câu ngoại lệ cạnh câu cũ.
  - Hướng dẫn credential cho user cuối KHÔNG vào `README*.md` đợt này (user chốt để sau). Tên biến +
    cách xử lý khi thiếu biến vẫn phải đủ TRONG vendor file — đó là nơi agent đọc lúc chạy, nên user
    cuối không bị kẹt vì thiếu README.
  - `e2e/` không thêm fixture Bitbucket đợt này (user tự test bằng repo của mình).
- Dependency: B3.
- Status: DONE trong phạm vi user chốt. README×3 + fixture e2e còn nợ.

## Task B9: cổng verify cuối + PR

- Acceptance:
  - `scripts/check.sh <base-ref>` xanh (suite + duplication + context-cost).
  - `vendor_lint.py` offline xanh mọi vendor. Live mode: user tự chạy trên fixture Cloud của mình —
    cung cấp đúng lệnh, KHÔNG tự gọi API thật của user.
  - Grep gate: không file bền nào (`src/`, `scripts/`, `tests/`, `CLAUDE.md`) chứa mã task của backlog
    này (`B1`…`B9`) trong tên biến / tên resource / comment, không chứa `§` lạ, `Phase `, hay tham chiếu
    tới chính file backlog này.
  - Rule-coverage: không `MUST`/`FORBIDDEN`/`NEVER` nào của file bị sửa mất so với `main`.
  - Commit theo path đã sửa (không `git add -A`), push CHỈ branch `feat/bitbucket-support`, 1 PR, không
    đụng `main`.
- Dependency: B1 → B8.
- Status: gate offline XANH — `check.sh main`: 53/53 test pass, duplication scan sạch, context-cost đo
  xong; `vendor_lint.py` offline sạch 3 vendor (15 lệnh curl + 32 flag CLI). Grep self-containment sạch.
  CÒN LẠI, chưa có bằng chứng nên KHÔNG tính là verified: live lint trên fixture Cloud thật, user tự
  chạy `python3 scripts/vendor_lint.py --url <PR_URL>`.

## Thứ tự: B1 → B2 → B3 → B5 → B6 → B7 → B8 → B9 (B4 hoãn, độc lập)
