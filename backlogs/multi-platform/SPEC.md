# SPEC — chạy `open-pr` trên Cursor / Codex / Gemini CLI / Antigravity

Plugin hiện chỉ cài được trên Claude Code. Spec này mở thêm 4 nền tảng agent khác **mà không tách
nhánh nghiệp vụ**: `src/` vẫn là source duy nhất, Claude Code vẫn là nền tảng chính.

Phân biệt từ ngữ, vì repo đã có `src/vendors/`:

| từ | nghĩa trong repo này |
|---|---|
| **vendor** | nơi host PR/MR: GitHub, GitLab (`src/vendors/<v>/`) — KHÔNG đổi nghĩa |
| **platform** | agent chạy plugin: Claude Code, Cursor, Codex, Gemini CLI, Antigravity |

## 1. Objective

1 lần sửa nghiệp vụ (`src/commands/`, `src/core/`, `src/vendors/`, `src/templates/`) → 5 platform ăn
theo, không sửa gì thêm. Adapter chỉ tồn tại cho phần **install-time** mà các platform thật sự khác
nhau: manifest, cách resolve đường dẫn gốc, tên tool.

Không nằm trong phạm vi: Bitbucket, thay đổi bất kỳ file nào dưới `src/`, thay đổi
`schema_version` / per-repo config, dịch prompt sang ngôn ngữ khác.

## 2. Cơ chế 5 platform (kết quả research, 2026-08)

| | Claude Code | Cursor | Codex | Gemini CLI | Antigravity |
|---|---|---|---|---|---|
| manifest | `.claude-plugin/plugin.json` + `marketplace.json` | `.cursor-plugin/plugin.json` + root `marketplace.json` | `.codex-plugin/plugin.json`; marketplace `.agents/plugins/marketplace.json` | `gemini-extension.json` | `plugin.json` ở root plugin dir |
| install | `/plugin marketplace add` → `/plugin install` | `/plugin` UI / marketplace / `~/.cursor/plugins/local/` | `/plugin marketplace add` → `/plugin install` → `/reload-plugins` | `gemini extensions install <git-url \| --path>` | `agy plugin install <path>` |
| slash entry | `commands/*.md` + frontmatter | `commands/*.md`; skills cũng thành `/name` | prompts `~/.codex/prompts` ĐÃ DEPRECATED → skills, gọi `$skill` | `commands/*.toml` (`prompt`, `description`, `{{args}}`, `!{sh}`, `@{file}`) | skill tự thành `/name` trong TUI |
| skills đọc từ | `.claude/skills` | `.cursor/skills`, legacy `.claude/skills`, `.codex/skills` | `.agents/skills`, `~/.agents/skills` | `.gemini/skills` hoặc alias `.agents/skills`; + skills trong extension | `.agents/skills`, `~/.gemini/antigravity-cli/skills` |
| biến trỏ gốc plugin | `${CLAUDE_PLUGIN_ROOT}` | chưa xác nhận | không có | `${extensionPath}` (docs chỉ chứng minh trong `mcpServers`) | chưa xác nhận |

Hội tụ: **`SKILL.md` là format chung** (name + description frontmatter, body là chỉ dẫn), và
`.agents/skills/` là alias liên thông. Gemini ghi rõ: khi skill activate, **thư mục skill được cấp
quyền đọc file bundle kèm theo** → không cần env var để trỏ tới cây prompt dùng chung.

## 3. Khác biệt thật sự phải xử lý

1. **`${CLAUDE_PLUGIN_ROOT}`** — 39 lần trong 10 file `src/`. Platform khác không set biến này.
2. **Tên tool trong prompt** — `Read`×60, `Edit`×12, `Write`×11, `Bash`×5, `Grep`×2,
   `AskUserQuestion`×1, `Agent` (subagent song song ở `src/setup/doctor.md`). Codex chỉ có shell;
   `AskUserQuestion` không có bản tương đương ở Codex/Gemini.
3. **Format entry khác nhau** (md có frontmatter / md thường / TOML / SKILL.md).

KHÔNG phải vấn đề, ghi lại để khỏi ai đi "sửa cho chắc":

- Plugin cố tình không dùng `allowed-tools` (CRITICAL block trong mỗi command là lớp enforce duy
  nhất) → khỏi port permission model, vốn khác nhau hoàn toàn giữa các platform.
- Per-repo config/state (`notebooks/review/<repo>/`) đã platform-agnostic.
- `src/vendors/` chỉ gọi `gh`/`glab` qua shell → platform nào cũng chạy.

## 4. Quyết định thiết kế

### 4.1 Adapter nằm NGOÀI `src/`

`.claude-plugin/marketplace.json` khai `source: ./src` ⇒ máy user Claude Code chỉ nhận `src/`.
Đặt adapter ở repo root ⇒ user Claude Code không nhận thêm byte nào, `token_report.py` (đo `src/`)
không cần đổi scope, và `src/` giữ nguyên tuyệt đối. Platform khác clone cả repo nên vẫn thấy `src/`.

```
repo-root/
  .claude-plugin/marketplace.json   (đã có, KHÔNG đổi)
  src/                              (source duy nhất, KHÔNG đổi)
  adapters/root.md                  resolve ROOT + map tên tool — file duy nhất mang tri thức platform
  skills/open-pr-<cmd>/SKILL.md     4 shim, dùng chung Cursor/Codex/Gemini/Antigravity
  commands/<cmd>.toml               4 shim TOML cho slash bản địa của Gemini
  .cursor-plugin/plugin.json        manifest Cursor
  .cursor-plugin/marketplace.json  catalog Cursor — file Cursor đọc khi import 1 GitHub URL
  .codex-plugin/plugin.json         manifest Codex
  .agents/plugins/marketplace.json catalog Codex
  gemini-extension.json
  plugin.json                       Antigravity
```

`skills/`, `commands/`, `rules/` ở root là **default dir của cả 4 platform** → dùng default, không
khai custom path trong manifest, giảm thứ phải verify.

### 4.2 Adapter chứa đúng 3 thứ, không hơn

1. metadata (name/description theo format platform),
2. cách resolve `ROOT` = thư mục chứa `src/` của bản đã cài,
3. delegate: `Read ROOT/commands/<cmd>.md` và làm theo NGUYÊN VĂN; ở đâu gặp
   `${CLAUDE_PLUGIN_ROOT}` thì đọc là `ROOT`.

`adapters/root.md` là nơi DUY NHẤT được biết tên platform: bảng resolve ROOT + bảng map tool
(`Read`→tool đọc file, `Bash`→shell, `AskUserQuestion`→hỏi thẳng trong chat và CHỜ trả lời,
`Agent`→không có subagent thì làm tuần tự). Shim không được lặp lại nội dung này.

FORBIDDEN trong mọi file adapter: severity, marker finding, luật worktree, lệnh `gh`/`glab`, tên
field config, bất cứ bước nào của review/fix/upgrade/clean. Có nghĩa là: thêm rule nghiệp vụ mới →
adapter không đổi. Chỉ 2 việc buộc chạm adapter: **thêm command mới**, hoặc **1 platform đổi schema
manifest**.

### 4.3 Không bump `schema_version`

Adapter không đọc/ghi per-repo config, không đổi tên command, không đổi layout `notebooks/review/`.
⇒ không có `llm-upgrades/vN.md`, `/open-pr:upgrade` không liên quan. User đã cài chỉ cần update
plugin như thường.

### 4.4 Chỉ dùng đường cài OFFICIAL của từng platform

Mỗi platform chỉ được tài liệu hoá bằng lệnh/cơ chế mà **chính platform đó công bố trong docs của
họ** — `/plugin marketplace add` + `/plugin install` (Claude Code, Codex), marketplace / `/plugin`
của Cursor, `gemini extensions install`, `agy plugin install`, và các thư mục nạp mà platform công
bố (`~/.cursor/plugins/local/`, `~/.cursor/skills/`, `~/.agents/skills/`).

Mỗi platform có 2 đường, cả 2 đều official ở mức **cơ chế nạp**, khác nhau ở **kênh phân phối**:

| đường | phân phối | dùng khi |
|---|---|---|
| **catalog** | marketplace/extension của platform, tự theo default branch | platform đó đã cho tự host hoặc đã duyệt submit |
| **local (script)** | user tự clone repo + chạy `scripts/install-local.sh <platform>` | catalog bị nghẽn: chờ duyệt form, hoặc bị gate theo plan/quyền admin |

One-liner `curl ... | bash` được chấp nhận, với điều kiện nó hỏng an toàn: thân script nằm trong
`main()` gọi ở dòng cuối (tải thiếu ⇒ không chạy gì), nó không tự cài mà clone **theo tag release**
rồi `exec` sang script trong bản clone — thứ chịu review + CI và người dùng đọc lại được sau khi cài.
FORBIDDEN: một one-liner tự thực hiện việc cài ngay trong thân nó, hoặc ghi đè thứ nó không tạo ra.
Đường hai bước `git clone` + chạy script vẫn được nêu song song cho người muốn đọc trước.

Đường local có 1 lợi thế thật: script biết chính xác nó đặt file ở đâu ⇒ ghi thẳng đường dẫn tuyệt
đối vào shim, không cần agent resolve `ROOT` lúc chạy. `adapters/root.md` chỉ phục vụ đường catalog.

Đánh đổi phải nói trong docs: đường catalog tự cập nhật, đường local **đứng version** cho tới khi user
`git pull` + chạy lại script.

Nhãn "unofficial/không chính thống" FORBIDDEN trong docs cho đường local — sai sự thật (cơ chế nạp do
platform công bố) và làm user ngại dùng. Gọi đúng: `local install`.

Không platform nào bắt buộc publish lên marketplace chính chủ của họ: 4/5 platform cài trực tiếp từ
git repo này (Claude Code + Codex qua marketplace JSON trong repo; Gemini qua
`gemini extensions install <git-url>`, không cần marketplace; Cursor qua import GitHub URL, đọc
`.cursor-plugin/marketplace.json`; Antigravity qua `agy plugin install`). Directory công khai của
Anthropic/OpenAI/Cursor chỉ là kênh phân phối tuỳ chọn, không phải điều kiện để cài.

Chưa xác nhận, quyết định cách viết docs: import team marketplace của Cursor có thể bị giới hạn cho
**admin trên plan Teams/Enterprise**. Nếu đúng → `docs/install.md` phải nói thẳng user cá nhân dùng
đường nào, không để user tự đâm vào tường.

Platform nào chưa mở đường official cho publisher ngoài (Codex: self-serve publish lên Plugin
Directory "coming soon" tính tới ~05/2026) → dùng cơ chế official còn lại mà họ đã công bố
(marketplace repo `.agents/plugins/marketplace.json` / `~/.agents/plugins/marketplace.json`) và ghi
rõ trạng thái đó. FORBIDDEN: bịa ra cách cài lách, hoặc trình bày workaround như thể là đường chuẩn.

### 4.5 README sạch, install tách docs riêng

README (3 ngôn ngữ) giữ đúng **1 đường cài mặc định là Claude Code** + 1 dòng trỏ
`docs/install.md`. Mọi platform khác, prereq, cách update, hạn chế từng platform → nằm hết trong
`docs/install.md`. Lý do: README là chỗ trả lời "có nên dùng cái này không", `docs/` trả lời "cài
chính xác thế nào" — đúng phân vai đã có của repo.

### 4.6 Ngưỡng "coi là hỗ trợ"

README chỉ được nêu 1 platform là supported khi platform đó chạy hết `e2e/checklist.md` trên PR
fixture đạt mức tương đương Claude Code. Trước đó ghi `experimental` kèm điều đã/chưa verify. Lý do:
rủi ro lớn nhất không phải install mà là agent nền tảng khác có bám nổi chuỗi `Read` sâu, worktree,
và kỷ luật "1 post / PR" hay không.

## 5. Đã chốt bằng docs official

| câu hỏi | kết luận | hệ quả đã áp vào code |
|---|---|---|
| `${extensionPath}` có được thay trong `prompt` của TOML? | **Không.** Docs Gemini: substitution chỉ ở `gemini-extension.json` + `hooks/hooks.json` | `commands/*.toml` định vị plugin bằng 1 lệnh `ls -d ~/.gemini/extensions/*/adapters/root.md` |
| Cursor đọc skills ở đâu? | `.cursor/skills/`, `~/.cursor/skills/`, `.agents/skills/`, `~/.agents/skills/` — frontmatter `name`/`description`/`paths` | 1 shim `SKILL.md` phục vụ cả 4 platform; `~/.agents/skills` là đích mặc định của local install (Cursor + Codex + Gemini cùng đọc) |
| Antigravity nạp skill từ đâu, tên slash lấy từ đâu? | `.agents/skills/`, `~/.gemini/antigravity-cli/skills/`; slash = tên thư mục | thư mục shim đặt tên `open-pr-<cmd>` → `/open-pr-review` |
| Cursor có gate việc import team marketplace? | Docs: tạo marketplace nội bộ là quyền admin trên plan Teams/Enterprise | local install là đường nêu trước cho user cá nhân |

## 6. Còn chưa xác nhận — cần chạy thật, không suy từ docs

Cả 4 đều cần login tài khoản của người dùng, nên chỉ verify được khi có người cài thật.

| câu hỏi | ảnh hưởng nếu đáp án ngược |
|---|---|
| `gemini extensions install <git-url>` có nhận manifest ở root repo này? | nếu nó đòi layout khác → sửa `gemini-extension.json` hoặc thêm custom path |
| Cursor có bỏ qua `commands/*.toml` (không phải `.md`) mà không lỗi? | nếu lỗi → chuyển TOML sang dir riêng + khai path trong `gemini-extension.json` |
| Codex `/plugin marketplace add` có nhận marketplace repo tự host? | nếu chưa → Codex chỉ còn đường local install, ghi rõ trong docs |
| `agy plugin install` có nhận git URL, hay chỉ local path? | chỉ local → docs hướng dẫn `git clone` rồi install path (docs đã viết theo hướng an toàn này) |

## 6. Acceptance của cả feature

1. `scripts/check.sh <base-ref>` xanh; **`tests/budgets.json` không đổi 1 số nào** (bằng chứng
   `src/` không bị đụng).
2. Test parity mới: mỗi `src/commands/*.md` có đúng 1 `skills/open-pr-*/SKILL.md` + 1
   `commands/*.toml`; mọi đường dẫn shim trỏ tới file tồn tại; shim vượt ngưỡng dòng hoặc chứa từ
   khoá nghiệp vụ → đỏ.
3. Mỗi manifest được platform tương ứng cài thật, `/open-pr:review` (hoặc dạng slash bản địa) khởi
   động đúng và đọc được `src/commands/review.md`.
4. `docs/install.md` có lệnh cài **official** cho từng platform + nhãn supported/experimental/
   untested; README 3 ngôn ngữ chỉ giữ đường Claude Code + 1 link tới file đó, số dòng phần Install
   không tăng.
