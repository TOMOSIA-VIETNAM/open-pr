# Backlog: CLI runtime — tách cơ học ra script, prompt chỉ giữ phán đoán

Mục tiêu: giảm ≥30% context/run cho `review` và `fix` mà không mất quy trình, không giảm chất
lượng review. Số đo gốc (cl100k, tại v1.4.1): ~61% một run review là văn bản dạy LLM làm việc
deterministic — `pr-target`+`locate-repo`+`repo-settings`+`stack-detection` = 2.806 tokens, vendor
GitHub (fetch/worktree/post) = 1.429, phần cơ học trong `review.md` ≈ 1.800/4.559. `fix` cùng tỷ lệ
(~63%). Mỗi guard mới hiện nay = thêm chữ vào file always-loaded → chart tăng đều là hệ quả kiến
trúc. Guard trong code còn đúng hơn guard bằng văn bản: LLM không thể quên/bỏ qua nó (lớp lỗi
#59/#69 biến mất thay vì phải trả token phòng ngừa).

Quyết định kiến trúc:

- 1 script POSIX sh: `src/bin/open-pr.sh`, ship trong `src/` như mọi file plugin. Dependency đúng
  bằng những gì plugin đã yêu cầu: `git`, `gh`/`glab`, `curl`, `jq` (đường Bitbucket vốn dùng
  curl+jq). KHÔNG thêm python vào runtime người dùng.
- Vendor là branch nội bộ trong script, output chuẩn hoá 1 format cho cả 3 vendor → vendor parity
  theo cấu trúc; thêm vendor mới = code + unit test, 0 token.
- Script KHÔNG BAO GIỜ diễn giải nội dung PR (title/body/diff/comment chỉ đi qua như dữ liệu,
  quote chặt mọi arg). KHÔNG được `Read` script vào context — nó là code, không phải prompt.
- Prompt giữ nguyên vẹn phần phán đoán: criteria, templates, FILE/LINE, severity, finding format,
  body shapes, re-review consensus, trust-check link submodule, bootstrap Q&A.
- Exit code + stderr là contract; `src/core/cli.md` (~400 tokens) là file duy nhất mô tả interface
  cho prompt.

## Task C1: `src/bin/open-pr.sh`
- Acceptance:
  - `context <pr-url>`: resolve vendor từ URL + settings, fetch đủ bảng Context của `review.md`
    (Head SHA TRƯỚC Diff, size list trước patch, omit oversized ngay trong call), in block chuẩn
    hoá; old comments là JSON gọn.
  - `checkout <pr-url> --repo-dir <d> --worktree <w> [--submodule <path> --pr <n> --repo <o/r>]`:
    worktree add / PR-ref fetch / detach; gate SHA + retry đúng 1 lần + STOP in cả 2 SHA; fetch
    refspec `+<base>:refs/remotes/origin/<base>` (submodule: vào checkout của submodule).
  - `verify-line --worktree <w> --path <p> --line <n> --side LEFT|RIGHT --base <ref>`: 3 outcome
    (match / mismatch kèm nội dung dòng / unconfirmable) — LEFT từ merge-base blob, cấm SHA rỗng.
  - `post --vendor <v> --repo <o/r> --pr <n> --payload <json> [--submit]`: compose → verify →
    publish theo đúng flow từng vendor, map lỗi đã biết (422 shape, commit_id bị reject =
    force-push), retry đúng 1 lần.
  - `reply|resolve|react|account`: các entry của `thread.md` ×3 vendor.
  - `settings --dir notebooks/review/<repo>`: in JSON đã resolve read-time default.
  - `stacks <file>...`: mapping file→stack của `stack-detection.md`.
- Status: TODO.

## Task C2: `src/core/cli.md` + viết lại `review.md`, `fix.md`, `cases/{submodule-review,re-review,post-review}.md`
- Acceptance: mọi bước cơ học thành 1 lệnh CLI; toàn bộ phán đoán giữ nguyên nghĩa; đánh số Step
  giữ ổn định ở những chỗ file khác trỏ tới; không còn ref treo (suite bắt).
- Dependency: C1.
- Status: TODO.

## Task C3: rút/xoá file cơ học
- Acceptance: `vendors/*/{fetch,worktree,post,thread}.md` xoá phần CLI đã nuốt (giữ marker literal
  và caveat còn là phán đoán); `stack-detection.md`, `locate-repo.md` xoá; `pr-target.md` còn phần
  gate + judgment; `repo-settings.md` còn nghĩa của field, mất bảng default.
- Dependency: C2.
- Status: TODO.

## Task C4: test + budgets
- Acceptance: `tests/test_cli.py` chạy script với shim `gh`/`glab`/`curl`/`git` giả trên PATH —
  phủ gate retry/STOP, 3 outcome verify-line, map lỗi post, thứ tự fetch của context, default của
  settings, mapping stacks. Prompt-graph test trỏ lại invariant còn sống, bỏ test pin văn bản đã
  xoá; thêm test cấm prompt `Read` `bin/`. `token_report.py` atoms/scenarios cập nhật; ceilings hạ
  tay theo delta đo được. `scripts/check.sh main` xanh.
- Dependency: C3.
- Status: TODO.

## Task C5: docs + PR (KHÔNG merge)
- Acceptance: `CLAUDE.md` (layout + hard edge mới: script không diễn giải nội dung PR, cấm Read
  bin/), `CONTRIBUTING.md`, README các ngôn ngữ + trang docs sở hữu chi tiết (requirement line).
  Commit theo conventional, push `feat/cli-runtime`, mở PR đánh dấu MAJOR (`feat!:`) kèm bảng
  before/after đo thật. PR để mở cho e2e + soak, không merge.
- Dependency: C4.
- Status: TODO.

## Ngoài phạm vi (ghi để khỏi trôi)
- Gộp bullet trùng giữa `templates/*.md` về `core/review-criteria.md` (~100–200 tokens/run, làm
  sau, PR riêng).
- Compile-time specialization per vendor: bị loại — trần ~15–18%, không đạt mục tiêu, thêm bước
  build mà vẫn giữ cơ học bằng chữ.
