# Backlog: Bitbucket support — Cloud + Data Center, 2 vendor mới

Mục tiêu: `/open-pr:review` + `/open-pr:fix` chạy được trên Bitbucket Cloud VÀ Bitbucket Data Center
(Server), giữ nguyên mọi tính năng đã có với GitHub/GitLab: comment line-by-line, overview, FILE-level,
re-review, resolve thread, reply.

Khác biệt nền tảng so với 2 vendor cũ: **Bitbucket không có CLI chính thức** ⇒ mọi entry là `curl` +
`jq`, credential phải tự truyền vào. Và Cloud vs Data Center là **2 API khác hẳn nhau** (Cloud
`api.bitbucket.org/2.0` REST 2.0; DC `<host>/rest/api/latest` REST 1.0, path/payload/field khác hoàn
toàn) ⇒ 2 vendor directory riêng, KHÔNG nhồi branch vào cùng 1 bộ file.

## Quyết định đã chốt với user (không tự đổi khi implement)

| # | Quyết định |
|---|---|
| 1 | Hỗ trợ cả Cloud và Data Center. Vendor dir: `bitbucket` (Cloud) + `bitbucket-server` (DC) |
| 2 | Giao 1 PR duy nhất cho cả 2 vendor |
| 3 | Credential qua ENV VAR, hướng dẫn set trong README. Plugin chỉ nhắc TÊN biến, giá trị token không bao giờ vào context |
| 4 | Luồng post/verify/publish giữ đúng semantics như GitHub/GitLab — `auto_submit_review: false` phải thật sự chưa có gì hiện trên PR |
| 5 | Fixture live: user có Bitbucket **Cloud** thật, KHÔNG có instance Data Center ⇒ phần DC chỉ verify được theo OpenAPI spec chính thức, phải ghi rõ caveat trong chính vendor file |

## Ground truth đã verify (dùng lại, đừng suy diễn lại)

Nguồn: OpenAPI spec chính thức `https://api.bitbucket.org/swagger.json` (Cloud) và
`https://developer.atlassian.com/server/bitbucket/10.2.swagger.v3.json` (DC), đối chiếu thêm doc
Atlassian. Mọi path dưới đây có thật trong spec.

**Auth.** App password của Bitbucket Cloud đã bị xoá hoàn toàn (brownout 2026-06-09, removed
2026-07-28) ⇒ chỉ còn 2 đường:
- API token gắn với 1 user: HTTP Basic `email:token` — `/user` gọi được.
- Repository/Workspace Access Token: `Authorization: Bearer <token>` — scope hẹp hơn nhưng `/user`
  trả 401 ⇒ entry "Fetch account running the command" BẮT BUỘC có nhánh không dựa vào `/user`.
- DC dùng HTTP access token (PAT) qua `Authorization: Bearer`, và trả về header `X-AUSERNAME` trên
  mọi request đã auth ⇒ đó là whoami của DC (DC không có endpoint `/user`).

**Cloud — path (prefix `https://api.bitbucket.org/2.0/repositories/<owner>/<repo>`):**

| việc | path |
|---|---|
| PR object (title/description/author/source/destination) | `/pullrequests/<n>` |
| head SHA | cùng object, field `source.commit.hash` |
| file list + số dòng thay đổi | `/pullrequests/<n>/diffstat` (paginated; `status`, `lines_added`, `lines_removed`, `old.path`, `new.path`) |
| unified diff | `/pullrequests/<n>/diff` — LÀ REDIRECT sang `/diff/{spec}` ⇒ cần `-L`; hỗ trợ query `path=` (lặp nhiều lần) để bound theo file |
| commits | `/pullrequests/<n>/commits` |
| comment list (cả inline + overview + reply) | `/pullrequests/<n>/comments` |
| tạo comment | `POST /pullrequests/<n>/comments` — inline: `{"content":{"raw":...},"inline":{"path":...,"to":<line>}}` (`from` = phía old); reply: `{"parent":{"id":<id>}}`; overview: bỏ `inline` |
| resolve | `POST /pullrequests/<n>/comments/<id>/resolve` (DELETE = unresolve); trạng thái đọc ở field `resolution` |
| CI | `/pullrequests/<n>/statuses` |
| permalink của comment | field `links.html.href` trên chính comment |
| projection server-side | query `?fields=` — rẻ hơn jq vì cắt ngay ở network |

**Cloud — cái KHÔNG có:**
- Không có draft/pending review dùng được: schema `pullrequest_comment` có field `pending` nhưng
  KHÔNG có endpoint publish nào trong spec ⇒ coi như không tồn tại, mọi POST comment là public ngay.
- Không có reactions API (grep spec: 0 path) ⇒ "React to a PR comment" = No equivalent.
- Không có review object gộp ⇒ "Fetch PR reviews (FILE-level findings + review_id)" = No equivalent,
  giống GitLab.
- Không có ref `refs/pull-requests/<n>/from` (khác DC). Checkout phải: đọc `source.branch.name` +
  `source.repository.full_name` + `source.commit.hash`; cùng repo → fetch branch từ `origin`, fork →
  fetch từ URL repo fork; rồi `checkout --detach <hash>`.

**Data Center — path (prefix `<host>/rest/api/latest/projects/<owner>/repos/<repo>`):**

| việc | path |
|---|---|
| PR object | `/pull-requests/<n>` (`fromRef.latestCommit` = head SHA, `author.user.name`) |
| file list | `/pull-requests/<n>/changes` |
| unified diff | `/pull-requests/<n>.diff` (text thật), per-file `/pull-requests/<n>/diff/<path>` |
| commits | `/pull-requests/<n>/commits` |
| comment list | `/pull-requests/<n>/activities` (toàn bộ) hoặc `/pull-requests/<n>/comments?path=` (theo file) |
| tạo comment | `POST /pull-requests/<n>/comments` — line: `anchor{line, lineType, fileType, path, fromHash, toHash, diffType}`; file-level: `anchor` không có `line`; reply: `parent.id`; overview: không có `anchor` |
| resolve | `PUT /pull-requests/<n>/comments/<id>` với `{"state":"RESOLVED","version":<version hiện tại>}` — sai `version` là fail, phải GET trước |
| CI | `<host>/rest/build-status/latest/commits/<sha>` |
| reactions | `PUT <host>/rest/comment-likes/latest/projects/<owner>/repos/<repo>/pull-requests/<n>/comments/<id>/reactions/<emoticon>` |
| draft review | `GET /pull-requests/<n>/review` = các thread PENDING của chính user; `PUT /pull-requests/<n>/review` = complete review (`commentText`, `participantStatus`, `lastReviewedCommit`) |
| checkout | có ref thật: `refs/pull-requests/<n>/from` |

**Điểm DC chưa verify được (không có instance):** cách TẠO một comment pending. Spec có field
`pending`/`state` trên `RestComment` và có `GET/PUT .../review`, nhưng payload để POST ra comment
pending thì spec không mô tả. Vì vậy Task B3 chốt dùng CHUNG một cơ chế staging cho cả 2 vendor
Bitbucket (xem dưới) — không đánh cược vào payload chưa kiểm chứng.

## Cơ chế "review chưa publish" cho cả 2 vendor Bitbucket

Interface yêu cầu: "Post a review" tạo ra kết quả UNPUBLISHED, "Verify" nói nó còn unpublished không,
"Publish" mới làm nó hiện ra. Bitbucket Cloud không có draft API; DC có nhưng cách tạo chưa kiểm
chứng được ⇒ cả 2 dùng **staging file local**:

- "Post a review": ghi TOÀN BỘ payload comment (overview + từng LINE finding) ra 1 file JSON, KHÔNG
  gọi API. Sau bước này chưa có gì trên PR.
- "Verify a posted review's state": GET comment list, đối chiếu không có comment nào của chính account
  đang chạy trên PR này ⇒ vẫn unpublished.
- "Publish the pending review": POST lần lượt từ staging file — overview trước, rồi từng LINE.

Đánh đổi phải ghi rõ trong Post-error notes: publish là N request nên có thể fail giữa đường ⇒ một
phần comment đã hiện. Staging file phải cho phép resume: mỗi payload mang 1 khoá riêng, publish xong
cái nào thì đánh dấu cái đó, retry chỉ POST phần chưa đánh dấu. Tên file phải mang `<pull_number>` để
2 run song song trên 2 PR khác nhau không đè nhau, và vị trí file phải KHÔNG bị commit vào memory
(kiểm tra `core/memory-commit.md` khi implement, chọn chỗ hoặc thêm ignore cho đúng).

## Task B1: URL → vendor cho 2 shape Bitbucket

- File: `src/core/pr-target.md`.
- Acceptance:
  - Bảng regex thêm 2 dòng: `bitbucket` = `https://bitbucket\.org/[^/]+/[^/]+/pull-requests/[0-9]+`
    (host pin cứng `bitbucket.org` vì Cloud chỉ có 1 host); `bitbucket-server` =
    `https://[^/]+/projects/[^/]+/repos/[^/]+/pull-requests/[0-9]+` (host bất kỳ vì self-hosted).
  - Ghi rõ discriminator giữa 4 vendor để không ai đoán: `/pull/` = GitHub, `/-/merge_requests/` =
    GitLab, `/pull-requests/` + host `bitbucket.org` = Cloud, `/pull-requests/` + segment
    `/projects/…/repos/…` = DC. Không có cặp nào chồng nhau.
  - Repo cá nhân của DC có project key dạng `~username` ⇒ guard charset `owner` phải cho phép ký tự
    `~` ở ĐẦU cho riêng shape DC, giữ nguyên các ký tự đang chặn (quote, backtick, `$`, `;`…). Không
    nới lỏng guard cho 3 vendor còn lại.
  - `<repo>` cho memory folder vẫn là segment repo (DC: `repositorySlug`), không phải project key.
- Dependency: không.
- Status: DONE. 2 dòng regex mới + discriminator viết gọn lại (bảng regex tự nói host pin vs `[^/]+`
  nên đoạn prose cũ dài dòng bị cắt). Guard charset nới `~` CHỈ cho `bitbucket-server`.

## Task B2: settings + bootstrap nhận 4 giá trị vendor

- File: `src/setup/bootstrap.md`, `src/reference/settings-schema.md`.
- Acceptance:
  - `shared.git_remote_type` nhận `"github"` | `"gitlab"` | `"bitbucket"` | `"bitbucket-server"`.
    Câu hỏi bootstrap hiện ghi "(no `"bitbucket"` yet)" — xoá hẳn, không để lại dấu vết.
  - KHÔNG bump `schema_version`, KHÔNG thêm `llm-upgrades/vN.md`: thêm giá trị hợp lệ cho một field
    đã tồn tại không cần transform file config của repo cũ (`"github"`/`"gitlab"` vẫn hợp lệ y
    nguyên). Ghi lý do này ở đây, không ghi vào file config.
  - Không thêm field nào cho credential — token là env var, tuyệt đối không nằm trong `settings.json`.
- Dependency: B1 (biết đúng 2 tên vendor).
- Status: DONE, có 1 thay đổi tốt hơn acceptance: câu hỏi bootstrap KHÔNG liệt kê 4 giá trị mà trỏ về
  bảng regex ở `core/pr-target.md` — nếu không, thêm vendor thứ 5 sẽ phải sửa 2 chỗ. `settings-schema.md`
  ghi valid values = tên thư mục dưới `src/vendors/`. KHÔNG bump `schema_version`, KHÔNG thêm
  `llm-upgrades/vN.md` (giá trị mới cho field đã tồn tại, repo cũ không cần transform).

## Task B3: `src/vendors/bitbucket/` — Bitbucket Cloud

- Acceptance:
  - 4 file `fetch.md`/`worktree.md`/`post.md`/`thread.md`, bộ heading `## <entry>` khớp TUYỆT ĐỐI với
    `src/vendors/github/` (cùng entry, cùng thứ tự trong từng group) — test parity sẽ bắt nếu lệch.
  - `fetch.md` mở đầu bằng phần vendor-wide (theo đúng chỗ interface quy định): thuật ngữ ("PR" =
    Pull Request; `<owner>` = workspace, `<repo>` = repo slug), base URL, và AUTH:
    - `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN` → `curl -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN"`.
    - Hoặc `BITBUCKET_TOKEN` (repo/workspace access token) → `-H "Authorization: Bearer
      $BITBUCKET_TOKEN"`.
    - Thiếu cả 2 → STOP, in hướng dẫn tạo token, FORBIDDEN: đoán/hỏi token qua chat.
    - FORBIDDEN: in giá trị biến ra output, `curl -v`, `echo $BITBUCKET_*`, hay nhét token vào URL.
    - Mọi lệnh dùng `curl -sS --fail-with-body` (exit non-zero khi HTTP lỗi NHƯNG vẫn in body để đọc
      được message lỗi của Atlassian).
  - Mỗi entry TỰ bound output theo đúng luật interface: `?fields=` và/hoặc `jq` projection nằm TRONG
    lệnh, không lọc sau. Riêng 2 entry diff:
    - "Fetch PR diff — patch, omitting oversized files": 1 request tới `/diff` (nhớ `-L`), tách theo
      `diff --git`, chỉ in chunk dưới `<max_patch_bytes>`.
    - "Fetch PR diff size per file": byte thật của từng chunk; file có trong diffstat nhưng không có
      chunk trong diff (binary / bị cắt) ⇒ `UNKNOWN`, TUYỆT ĐỐI không phải 0.
  - Pagination: Cloud trả `values[]` + `next` ⇒ entry nào có thể vượt 1 trang (comments, diffstat)
    phải lặp tới hết `next`, không lấy 1 trang rồi coi là đủ.
  - `post.md` theo cơ chế staging file ở trên; Post-error notes ghi rõ rủi ro publish nửa vời + cách
    resume, và FORBIDDEN các shortcut publish thẳng bỏ qua staging.
  - `thread.md`: "React to a PR comment" = **No equivalent** (Cloud không có API). "Finding
    permalink" = `links.html.href` của comment (Cloud CÓ, khác GitLab).
  - `fetch.md` "Fetch PR reviews (FILE-level findings + review_id)" = **No equivalent**.
  - "Fetch account running the command": `/user` cho API token; nhánh cho access token (401 ở `/user`)
    không được dựa vào `/user`.
- Dependency: B1, B2.
- Status: DONE. 19/19 heading khớp `src/vendors/github/`. PHÁT SINH ngoài acceptance, cần thiết:
  - 2 atom dùng chung ra đời vì 2 vendor Bitbucket lặp nhau y hệt (dup scan bắt thật, không phải giả
    định): `core/raw-http-vendor.md` (curl flags, secret hygiene, payload-không-qua-shell, 2 pipeline
    tách diff theo file) + `core/pending-review-staging.md` (staging file, marks, resume, verify).
  - `core/finding-markers.md` thêm rule: account `UNKNOWN` ⇒ CHỈ dùng nhánh marker, cấm nhánh fallback
    (không có author để so thì fallback sẽ nhận vơ comment của người thật). Đây là caller-side, tức
    "vendor mới = 4 file" KHÔNG đúng với vendor không có CLI — đã sửa lại rule đó trong `CLAUDE.md`.
  - `/user` 401 dưới access token được coi là ĐÁP ÁN (`UNKNOWN`), không phải lỗi auth để retry.

## Task B4: `src/vendors/bitbucket-server/` — Bitbucket Data Center

- Acceptance:
  - Cùng bộ heading, cùng luật bound/auth/secret như B3, nhưng theo REST 1.0 (bảng path ở trên).
  - Auth: `BITBUCKET_SERVER_TOKEN` (HTTP access token) → `Authorization: Bearer`. Host lấy từ CHÍNH
    host của PR URL, không hardcode.
  - "Fetch account running the command": đọc header `X-AUSERNAME` (DC không có `/user`).
  - "React to a PR comment": DC CÓ endpoint reactions ⇒ implement thật, không phải No equivalent.
  - "Resolve a review thread": phải GET comment lấy `version` rồi mới PUT — ghi rõ vì sai version là
    fail, đây là điểm khác biệt duy nhất cần 2 request.
  - Checkout dùng `refs/pull-requests/<n>/from`, detached, cho cả entry worktree thường và entry
    submodule.
  - Đầu `fetch.md` ghi caveat: bộ lệnh này verify theo OpenAPI spec chính thức của Bitbucket Data
    Center, CHƯA chạy trên instance thật; nêu tên đúng 2 chỗ rủi ro cao nhất (payload `anchor` khi
    tạo line comment, và `version` khi resolve) để người dùng đầu tiên biết soi ở đâu.
- Dependency: B3 (copy khung + luật chung, chỉ đổi API).
- Status: DONE ở mức doc-verified. Reactions CÓ thật (khác Cloud), ref `refs/pull-requests/<n>/from`
  CÓ thật nên checkout đơn giản hơn Cloud. Caveat ghi ngay đầu `fetch.md` + nêu đúng 2 chỗ rủi ro
  (`anchor` khi tạo line comment, `version` khi resolve). Draft native (`GET/PUT .../review`) CÓ trong
  spec nhưng KHÔNG có cách tạo comment pending ⇒ không dùng, đi chung staging với Cloud.

## Task B5: `scripts/vendor_lint.py` phải lint được vendor không-CLI

- Acceptance:
  - Parser hiện chỉ nhận lệnh bắt đầu bằng `gh`/`glab`/`git` ⇒ entry `curl` bị coi là "no command
    parsed" và FAIL. Mở rộng để nhận `curl`.
  - Chế độ offline (chạy trong CI, không cần credential) thêm luật tĩnh cho entry `curl`:
    có `--fail-with-body`; host đúng (`api.bitbucket.org` cho Cloud, `/rest/api/` cho DC); auth chỉ
    qua tên biến `$BITBUCKET_*`; KHÔNG có token/email literal; KHÔNG có `-v`; entry nào gọi endpoint
    redirect (`/pullrequests/<n>/diff`) phải có `-L`.
  - Chế độ live: chạy được các entry `Fetch` read-only của Cloud với fixture thật + credential từ env.
    `parse_url` nhận 2 shape URL mới; bỏ giả định "vendor nào cũng có 1 CLI để `command -v`".
  - Live mode TUYỆT ĐỐI không chạy entry `post`/`thread` (đang là luật của script, giữ nguyên).
- Dependency: B3, B4.
- Status: DONE. Lint tự phát hiện vendor từ thư mục (không hardcode danh sách), expand shorthand đọc
  từ chính bảng trong `fetch.md`, và dựng lại pipeline của atom để entry diff vẫn chạy được ở live mode.
  Luật tĩnh cho curl: `--fail-with-body` bắt buộc, cấm `-f`/`-v`/`-i`, cấm credential literal, URL phải
  cùng host với `<api>`, và shorthand nào tự ghi "`-X` MANDATORY" thì phải thật sự có flag đó.
  ĐÃ NEGATIVE-TEST trên bản copy: cả 4 luật đều bắt lỗi khi cố tình phá (không phải test rỗng).

## Task B6: test suite

- File: `tests/test_prompt_graph.py`.
- Acceptance:
  - Parity/reachability/interface-doc test đang tự quét thư mục `src/vendors/` ⇒ phải xanh với 4
    vendor, không sửa gì. Nếu đỏ thì lỗi ở vendor file, không phải ở test — sửa vendor file.
  - Test "description phải nêu mọi vendor" so khớp tên thư mục với text ⇒ chuẩn hoá `-` để
    "Bitbucket Server" trong prose khớp thư mục `bitbucket-server`. Không đổi bản chất luật.
  - Test "mọi fetch entry phải bound" đang nhận marker `select` / `jq '{` / `--json` / No equivalent ⇒
    thêm `fields=` (projection server-side của Bitbucket) là marker hợp lệ. Không nới thêm gì khác.
  - THÊM guard mới: không file nào trong `src/` chứa token/email literal của Bitbucket; mọi lệnh
    `curl` trong `src/vendors/` đều có `--fail-with-body` và không có `-v`.
- Dependency: B3, B4.
- Status: DONE. 2 guard cũ được nới ĐÚNG bản chất, không nới nghĩa: threshold có thể được filter bởi
  pipeline dùng chung (chấp nhận ref tới atom), và `fields=` là marker bound hợp lệ (projection
  server-side). Test tên vendor trong description so khớp sau khi phẳng hoá `-`. 2 test MỚI: không
  entry curl nào rò credential (`-v`/`-i`/literal), và vendor curl phải báo lỗi HTTP kèm body.

## Task B7: token budget

- File: `scripts/token_report.py`, `tests/budgets.json`.
- Acceptance:
  - Thêm atom cho 8 file vendor mới; thêm scenario review + fix cho Bitbucket Cloud và DC (đủ để đo
    load set thật, không phải cho đẹp).
  - Ceiling trong `budgets.json` phải là số ĐO ĐƯỢC bằng `token_report.py`, không phải số đoán.
  - Vendor Bitbucket đắt hơn `gh`/`glab` là điều tất yếu (curl + jq dài hơn CLI wrapper). Nếu scenario
    của GitHub/GitLab bị đắt lên thì đó là regression thật ⇒ phải điều tra, không được `--update-budgets`
    cho qua.
- Dependency: B3, B4.
- Status: DONE, số ĐO thật: 8 atom vendor + 2 atom core + 3 scenario mới (review Cloud, re-review DC,
  fix Cloud). CẢNH BÁO ĐÃ GHI NHẬN: scenario của GitHub/GitLab ĐẮT THÊM +81 tok (+0.7–1.1%), riêng
  scenario có re-review/fix +124 tok (+1.3–1.5%). Nguyên nhân: `core/pr-target.md` (+81, luôn load) do
  2 dòng regex mới, và `core/finding-markers.md` (+43) do rule `UNKNOWN`. Đã cắt hết chỗ cắt được
  (prose discriminator + charset + rule UNKNOWN viết gọn) — phần còn lại là giá không tránh được của
  việc nhận thêm 2 vendor. Ceiling của `upgrade`/`clean` giữ nguyên vì 2 scenario đó không đổi.

## Task B8: tài liệu dev

- Acceptance:
  - `CLAUDE.md`: Mission đang ghi "GitHub + GitLab (no Bitbucket yet)" → cập nhật đúng thực tế 4
    vendor. Rule "một vendor mới = 4 file, không sửa gì khác" đang KHÔNG đúng cho vendor không có CLI
    (Bitbucket kéo theo regex, bootstrap, lint, budget) → viết lại rule cho đúng, không bolt thêm câu
    ngoại lệ bên cạnh câu cũ.
  - Hướng dẫn credential cho user cuối KHÔNG viết vào `README*.md` ở đợt này (user chốt để sau). Phần
    tên biến + cách xử lý khi thiếu biến vẫn phải đủ TRONG vendor file, vì đó là nơi agent đọc lúc
    chạy — không được để user cuối kẹt vì thiếu README.
  - `e2e/` không thêm fixture Bitbucket ở đợt này (user tự test bằng repo của mình).
- Dependency: B3, B4.
- Status: DONE trong phạm vi user chốt. `CLAUDE.md`: Mission 4 vendor, rule "vendor mới = 4 file"
  viết lại cho đúng (kèm regex row + budget + 2 atom cho vendor không CLI), "flag lint" → "vendor lint".
  README×3 và fixture e2e KHÔNG làm ở đợt này theo yêu cầu user.

## Task B9: cổng verify cuối + PR

- Acceptance:
  - `scripts/check.sh <base-ref>` xanh (suite + duplication + context-cost).
  - `vendor_lint.py` offline xanh cho cả 4 vendor. Live mode: user tự chạy trên fixture Cloud của
    mình — cung cấp đúng lệnh, KHÔNG tự gọi API thật của user.
  - Grep gate: không file bền nào (`src/`, `scripts/`, `tests/`, `CLAUDE.md`, README) chứa mã task của
    backlog này (`B1`…`B9`) trong tên biến / tên resource / comment, không chứa `§`, `Phase `, hay
    tham chiếu tới chính file backlog này. Tên đặt theo chức năng thật.
  - Rule-coverage: không `MUST`/`FORBIDDEN`/`NEVER` nào của file bị sửa (B1, B2, B6, B8) bị mất so
    với `main`.
  - Commit theo path đã sửa (không `git add -A`), push CHỈ branch `feat/bitbucket-support`, mở 1 PR.
    Không đụng `main`.
- Dependency: B1 → B8.
- Status: gate offline XANH — `scripts/check.sh main`: 53/53 test pass, duplication scan sạch,
  context-cost đo xong; `vendor_lint.py` offline sạch cả 4 vendor (31 lệnh curl + 32 flag CLI).
  Grep self-containment sạch: không mã task `B1..B9`, không `Phase`, không trỏ về file backlog này.
  CÒN LẠI: live lint trên fixture Cloud thật do USER tự chạy — chưa có bằng chứng chạy thật, không
  được coi là đã verify. Lệnh: `python3 scripts/vendor_lint.py --url <PR_URL_Cloud>`.

## Thứ tự: B1 → B2 → B3 → B4 → B5 → B6 → B7 → B8 → B9
