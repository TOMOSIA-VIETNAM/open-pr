# Backlog — multi-platform (Cursor / Codex / Gemini CLI / Antigravity)

Spec tại `SPEC.md` cùng thư mục. Backlog chỉ tách task theo spec, không tự thêm quyết định thiết kế.

Luật xuyên suốt mọi task:

- **KHÔNG sửa bất kỳ file nào dưới `src/`.** Task nào thấy "buộc phải sửa `src/`" → DỪNG, báo user,
  vì đó là dấu hiệu adapter đang ăn nghiệp vụ.
- Không viết mã task (`MP1`, `MP2`…), tên file backlog, hay `§` của spec vào bất kỳ file ship được
  (adapter, manifest, README, test). Backlog sẽ bị xoá; file ship phải tự đứng.
- Sau mỗi task chạm file được CI đo: `scripts/check.sh <base-ref>`. `tests/budgets.json` đổi số ⇒ đã
  đụng `src/` ⇒ sai.

## MP1 — Probe thực nghiệm, trả lời hết bảng câu hỏi mở của spec

Làm TRƯỚC mọi task viết file, vì 5 đáp án quyết định layout.

- Acceptance:
  - Cài thật tối thiểu 2 CLI: Gemini CLI + 1 trong (Cursor CLI / Codex CLI). Ghi version đã test.
  - Trả lời được từng dòng bảng "Điều chưa xác nhận" của `SPEC.md`, mỗi câu kèm **bằng chứng** (lệnh
    đã chạy + output, hoặc link docs chính thức của platform), không suy đoán.
  - Probe bằng 1 extension/plugin nháp trong scratchpad, KHÔNG commit rác vào repo.
  - Chốt: `${extensionPath}` có dùng được trong `prompt` TOML hay phải resolve bằng `!{...}`.
  - Chốt: Cursor có nhận `src/commands/*.md` trực tiếp hay cần shim riêng.
  - Kết quả ghi ngược vào `SPEC.md` (biến bảng câu hỏi thành bảng kết luận), không mở file mới.
- Dependency: không.

## MP2 — `adapters/root.md`: nơi DUY NHẤT biết tên platform

- Acceptance:
  - Bảng resolve `ROOT` cho từng platform (đường dẫn cài thật, đã verify ở MP1; platform nào không
    có biến trỏ gốc thì ghi 1 lệnh shell 1 dòng để tự tìm).
  - Bảng map tool: `Read`/`Write`/`Edit`/`Grep`/`Bash` → tool tương ứng; `AskUserQuestion` → hỏi
    thẳng trong chat và CHỜ trả lời (cấm tự chọn hộ user); `Agent` → không có subagent thì làm tuần
    tự, không bỏ bước.
  - Câu chốt: ở đâu file `src/` viết `${CLAUDE_PLUGIN_ROOT}` thì đọc là `ROOT`.
  - Viết theo luật "write for the machine" của `CLAUDE.md`: bảng, không văn xuôi.
  - Test: grep file này KHÔNG có severity, marker, `gh `, `glab `, `worktree`, tên field config.
- Dependency: MP1.

## MP3 — 4 shim `skills/open-pr-<cmd>/SKILL.md`

- Acceptance:
  - Đúng 4 shim, 1 cho mỗi `src/commands/*.md` (`review`, `fix`, `upgrade`, `clean`).
  - Frontmatter chỉ `name` + `description`; `description` phải nêu cả "làm gì" và "khi nào dùng"
    (đây là cơ chế trigger implicit của Codex/Gemini), lấy ý từ `description` của command gốc nhưng
    KHÔNG copy dài dòng.
  - Body: đọc `adapters/root.md` → `Read ROOT/commands/<cmd>.md` → làm theo nguyên văn, cấm tóm
    tắt/bỏ bước/diễn giải lại.
  - Shim của `fix` và `clean` nêu thêm 1 câu cảnh báo mức rủi ro (sửa code thật / xoá worktree) và
    nói rõ luật chi tiết nằm trong command gốc — KHÔNG liệt kê lại luật.
  - Mỗi shim ≤ 12 dòng.
- Dependency: MP2.

## MP4 — Gemini CLI: `gemini-extension.json` + 4 `commands/<cmd>.toml`

- Acceptance:
  - Manifest: `name`, `version`, `description`, `contextFileName` (nếu cần), không khai custom path
    nếu default `commands/` + `skills/` đã đủ (verify ở MP1).
  - 4 TOML: `description` + `prompt`; `prompt` là shim delegate, dùng `{{args}}` để truyền
    `<PR URL>`/`[repo name...]` đúng `argument-hint` của command gốc.
  - ROOT trong TOML resolve theo đúng cách MP1 đã chốt.
  - Cài thật bằng `gemini extensions install --path <repo>` → `/open-pr:review` xuất hiện, gọi vào
    được `src/commands/review.md` (chứng minh bằng việc agent đọc đúng file).
  - Nếu MP1 kết luận Cursor lỗi khi thấy `commands/*.toml` → chuyển TOML sang dir riêng + khai custom
    path, ghi lý do vào `SPEC.md`.
- Dependency: MP3.

## MP5 — Cursor: `.cursor-plugin/plugin.json` + `.cursor-plugin/marketplace.json`

- Acceptance:
  - Manifest tối thiểu: `name`, `description`, `version`, `author`.
  - `.cursor-plugin/marketplace.json` liệt kê plugin này (schema Cursor, tách biệt hoàn toàn với
    `.claude-plugin/marketplace.json`, không file nào tham chiếu file kia).
  - Verify bằng tài khoản thật xem import team marketplace có bị gate theo plan/quyền admin không;
    nếu có → ghi đường cài dành cho user cá nhân vào `docs/install.md`, không im lặng.
  - Nếu MP1 xác nhận Cursor đọc được `src/commands/*.md` → khai path trỏ `src/commands`, bỏ phụ
    thuộc shim; ngược lại dùng `skills/` của MP3.
  - Cài thật (marketplace hoặc `~/.cursor/plugins/local/`) → 4 entry hiện ra, `review` chạy tới bước
    đọc `src/core/guardrails.md`.
- Dependency: MP3.

## MP6 — Codex: `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json`

- Acceptance:
  - Manifest khai bundle skills (Codex đã deprecate custom prompts — KHÔNG tạo `~/.codex/prompts`).
  - Nếu MP1 kết luận self-host marketplace qua git chưa mở → tài liệu hoá đường cài local
    (`.agents/skills/` của repo user, hoặc `~/.agents/skills/`) và ghi rõ hạn chế đó vào README.
  - Cài thật → `$open-pr-review` (dạng invoke explicit của Codex) hoạt động, đọc đúng file gốc.
  - Kiểm tra riêng cho Codex: không có subagent + không có `AskUserQuestion` ⇒ `review` vẫn phải hỏi
    user và CHỜ ở đúng các bước command gốc yêu cầu; `src/setup/doctor.md` chạy tuần tự không bỏ file.
- Dependency: MP2 (+ MP3 cho phần skills).

## MP7 — Antigravity: `plugin.json`

- Acceptance:
  - Manifest ở root với `name` khớp `^[a-zA-Z0-9-_]+$`, `description`; skills lấy default `skills/`.
  - Cài bằng `agy plugin install <path>` → skill tự thành `/open-pr-review` trong TUI, chạy được.
  - Nếu chưa cài được Antigravity để test → task này ở trạng thái chưa verify, README ghi
    `untested`, KHÔNG ghi supported.
- Dependency: MP3.

## MP7b — `scripts/install-local.sh`: đường cài local cho platform bị nghẽn catalog

1 script cho mọi platform, không phải mỗi platform 1 cái. Gemini không cần (đã install từ git URL).

- Acceptance:
  - `scripts/install-local.sh <cursor|codex|antigravity> [--uninstall]`. Không tham số → in usage +
    danh sách platform, exit khác 0.
  - Đích ghi = thư mục platform tự công bố (`~/.cursor/plugins/local/`, `~/.agents/skills/`,
    `~/.gemini/antigravity-cli/plugins/`), lấy theo đáp án MP1. Không tự bịa đường dẫn.
  - Sinh shim với **đường dẫn tuyệt đối** tới cây `src/` đã clone (bake ROOT), không để agent resolve
    lúc chạy. Nội dung shim vẫn sinh từ đúng 4 shim của MP3 — script KHÔNG chứa bản sao nội dung nào,
    chỉ thay chỗ giữ đường dẫn.
  - Idempotent: chạy 2 lần cho cùng kết quả, không nhân bản.
  - **Không sửa/xoá file mà nó không tạo ra.** Gặp file lạ ở đích → dừng, in đường dẫn, không ghi đè.
  - `--uninstall` chỉ xoá đúng những gì nó đã tạo; in ra từng đường dẫn trước khi xoá.
  - Kết thúc in: đã ghi gì ở đâu + cách update (`git pull` + chạy lại) + cách gỡ.
  - Test: `shellcheck` sạch; chạy thật với `HOME` trỏ thư mục tạm (scratchpad) rồi verify cây file;
    test `--uninstall` trả về trạng thái ban đầu; test gặp file lạ thì dừng không ghi đè.
  - FORBIDDEN trong script và trong docs của nó: `curl ... | bash`, `sudo`, ghi ra ngoài các đích đã
    khai, `git clone` từ `main` khi có tag release.
- Dependency: MP1, MP3.

## MP8 — Test chống trôi (đây là cái giữ cam kết "không duplicate")

- Acceptance, thêm vào `tests/test_prompt_graph.py`:
  - **parity**: mỗi `src/commands/*.md` có đúng 1 shim skill (và 1 TOML nếu MP4 giữ layout đó); shim
    thừa/thiếu → đỏ.
  - **ref integrity**: mọi đường dẫn `src/...` xuất hiện trong adapter/manifest phải tồn tại.
  - **anti-drift**: file trong `adapters/`, `skills/`, `commands/` mà chứa từ khoá nghiệp vụ
    (`🔴`/`🟠`/`🔵`/`📝`, `worktree`, `severity`, `gh pr`, `glab mr`, `schema_version`,
    `notebooks/review`) → đỏ, trừ `adapters/root.md` và ngoại lệ ghi rõ lý do trong test.
  - **giới hạn dòng** cho shim (ngưỡng theo MP3).
  - `scripts/dup_scan.py`: thêm adapter vào `--scope dev` (giống `CLAUDE.md`) để duplicate giữa 4
    shim bị bắt.
  - Test chứng minh chiều ngược: sửa 1 rule trong `src/core/` mà không chạm adapter → suite vẫn xanh.
- Dependency: MP3 (và MP4–MP7 nếu layout của chúng đã chốt).

## MP9 — e2e từng platform

- Acceptance:
  - Chạy `e2e/checklist.md` trên PR fixture bằng từng platform đã cài được, chấm điểm bằng đúng
    checklist đó (không tự nới tiêu chí).
  - Ghi lại: platform nào đạt tương đương Claude Code, platform nào lệch ở bước nào (thường sẽ là
    chuỗi `Read` sâu, worktree, kỷ luật 1 post/PR).
  - Kết quả là đầu vào duy nhất cho nhãn supported/experimental ở MP10.
- Dependency: MP4–MP7 (mỗi platform xong thì e2e platform đó, không chờ đủ cả 4).

## MP10 — `docs/install.md`: 1 nơi duy nhất chứa cách cài mọi platform

- Acceptance:
  - File mới `docs/install.md`, prose người đọc (README/`docs/` được miễn luật nén token của
    `CLAUDE.md`). Bảng đầu file: platform | lệnh cài | lệnh update | nhãn
    supported/experimental/untested (nhãn lấy từ kết quả e2e, không tự phong).
  - Mỗi platform 1 mục ngắn, **2 đường song song** (catalog / local install), nêu rõ chọn đường nào
    khi nào + lệnh update của TỪNG đường (catalog tự theo default branch; local phải `git pull` +
    chạy lại script, nếu không sẽ đứng version).
  - Cursor: nếu MP5 xác nhận import marketplace bị gate theo plan/quyền admin, hoặc form submit lên
    marketplace công khai còn đang chờ duyệt → local install là đường được nêu TRƯỚC cho user cá nhân.
  - Cấm chữ "unofficial"/"không chính thống" cho local install — cơ chế nạp do platform công bố.
  - Lệnh clone trong docs phải là `git clone --branch <tag>` (không `main` HEAD) và tuyệt đối không
    `curl ... | bash`.
  - Codex: ghi đúng trạng thái publish lên Plugin Directory và cơ chế marketplace repo official thay
    thế. Không trình bày workaround như đường chuẩn.
  - Prereq viết 1 lần cho mọi platform: `gh` (GitHub) / `glab` (GitLab) đã login — review post bằng
    account đó.
  - Nêu rõ: `/open-pr:upgrade` là chuyện per-repo config, **không** liên quan tới việc chuyển/thêm
    platform (không có migration nào cần chạy khi cài thêm platform).
  - Mọi lệnh trong file phải là lệnh đã chạy thật ở MP4–MP7; platform chưa chạy được → nhãn
    `untested` + nói rõ chưa verify, KHÔNG chép lệnh từ docs rồi khẳng định là được.
- Dependency: MP9.

## MP11 — README 3 ngôn ngữ + `docs/how-it-works.md` + `CLAUDE.md`

- Acceptance:
  - `README.md`, `README.ja.md`, `README.vi.md`: mục `Install` giữ đúng đường Claude Code như hiện
    tại + đúng 1 dòng "platform khác (Cursor, Codex, Gemini CLI, Antigravity) → `docs/install.md`".
    Số dòng mục Install KHÔNG tăng. Cấm liệt kê lệnh của platform khác trong README.
  - 3 README nói cùng một điều, dịch sát nhau; không file nào có thông tin platform mà file kia thiếu.
  - `docs/how-it-works.md` thêm 1 đoạn ngắn: adapter là lớp install, `src/` là source duy nhất, sửa
    nghiệp vụ không cần chạm adapter.
  - `CLAUDE.md` thêm 1 dòng luật: adapter cấm chứa nghiệp vụ, chỉ 2 lý do được sửa (thêm command,
    platform đổi schema manifest). Đặt đúng 1 chỗ, không lặp nội dung spec.
  - Không nêu `schema_version` mới ở đâu cả (feature này không bump).
  - `dup_scan.py` không mọc hit mới giữa README ↔ `docs/install.md` (mô tả platform chỉ có 1 chủ).
- Dependency: MP10.

## MP12 — Chốt cửa cuối

- Acceptance:
  - `scripts/check.sh <base-ref>` xanh; `tests/budgets.json` diff rỗng.
  - `scripts/vendor_lint.py` vẫn xanh (không đụng `src/vendors/`).
  - Grep toàn repo: không còn mã task (`MP[0-9]`), `§`, tên file backlog trong file ship được.
  - Mọi lệnh install trong `docs/install.md` là lệnh official, và mỗi lệnh đều có 1 platform đã chạy
    thật hoặc nhãn `untested` đi kèm.
  - `shellcheck scripts/install-local.sh` sạch; grep toàn repo không có `curl` nào nối vào `bash`/`sh`.
  - Khi form submit marketplace của Cursor được duyệt sau này: đổi nhãn trong `docs/install.md` là
    ĐỦ, không phải viết lại mục hay sửa script — kiểm tra điều này bằng cách đọc lại file.
  - PR mở lên nhánh được user chỉ định, không push `main`.
- Dependency: MP8, MP11.
