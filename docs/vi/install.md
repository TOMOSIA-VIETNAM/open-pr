# Cài đặt

Claude Code là nền tảng plugin này được xây và test trên đó. Cursor, Codex, Gemini CLI và Antigravity
chạy đúng cùng một review từ cùng những file đó — chỉ khác cái cửa để đi vào, và đó là nội dung trang
này.

Dù dùng nền tảng nào, bạn vẫn cần [`gh`](https://cli.github.com/) cho PR GitHub hoặc
[`glab`](https://gitlab.com/gitlab-org/cli) cho MR GitLab, đã cài và đã login. Review được post bằng
chính account đó.

## Chọn cửa nào

Mỗi nền tảng có hai cửa, và cả hai đều dùng cơ chế nạp do chính nền tảng đó công bố. Khác nhau ở chỗ
file đến máy bạn bằng đường nào:

- **Catalog** — dùng trình cài plugin/extension của nền tảng, trỏ vào repository này. Nó theo default
  branch, nên cập nhật chỉ là một lệnh trong nền tảng đó.
- **Local** — bạn clone repository này rồi chạy `scripts/install-local.sh`. Dùng khi đường catalog
  đang khép với bạn: form submit còn chờ duyệt, hoặc account của bạn không có quyền import. Bản cài
  đứng ở release bạn đã clone cho tới khi bạn pull.

| Nền tảng | Catalog | Local | Trạng thái |
| -------- | ------- | ----- | ---------- |
| Claude Code | `/plugin marketplace add` + `/plugin install` | không cần | đã test |
| Cursor | import repo này làm team marketplace (admin, plan Teams/Enterprise) | `scripts/install-local.sh` | chưa test |
| Codex | `codex plugin marketplace add` + `/plugins` | `scripts/install-local.sh` | chưa test |
| Gemini CLI | `gemini extensions install <URL repo>` | `scripts/install-local.sh` | chưa test |
| Antigravity | `agy plugin install <path>` (chỉ CLI) | `scripts/install-local.sh` | chưa test |

`đã test` nghĩa là một review thật đã chạy trọn vẹn và được chấm theo `e2e/checklist.md`. `chưa test`
nghĩa là file và manifest đã đúng chỗ, khớp với những gì nền tảng đó công bố, nhưng chưa ai chạy review
thật qua nền tảng ấy — hãy coi là thử nghiệm và đọc lại review nó post trước khi tin. Nếu bạn có chạy,
kết quả nào cũng đáng mở một issue.

## Claude Code

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

Cập nhật:

```bash
/plugin marketplace update open-pr
/plugin update open-pr@open-pr
/reload-plugins
/open-pr:upgrade
```

Command vào máy có namespace: `/open-pr:review`, `/open-pr:fix`, `/open-pr:upgrade`, `/open-pr:clean`.

## Cursor

Catalog: trong dashboard Cursor, vào Settings → Plugins → Team Marketplaces → Import rồi dán URL của
repository này. Cursor đọc `.cursor-plugin/marketplace.json` và từ đó theo default branch. Tạo team
marketplace là hành động của admin trên plan Teams và Enterprise, nên với account cá nhân hãy dùng
đường local bên dưới.

Local: `scripts/install-local.sh --platform cursor` đặt nguyên plugin vào
`~/.cursor/plugins/local/open-pr`, đúng thư mục Cursor dành riêng cho việc này, nên nó hiện trong danh
sách plugin kèm nút bật/tắt như mọi plugin khác. Xong thì reload cửa sổ (`Developer: Reload Window`).

Cách nào thì bốn command cũng hiện ra dưới dạng `/open-pr-review`, `/open-pr-fix`, `/open-pr-upgrade`,
`/open-pr-clean`.

## Codex

Từ shell:

```bash
codex plugin marketplace add TOMOSIA-VIETNAM/open-pr
codex
```

Rồi gõ `/plugins` trong Codex để cài và bật. Nếu đang ở trong session sẵn thì có dạng slash tương
đương:

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr
/reload-plugins
```

Codex đọc catalog từ `.agents/plugins/marketplace.json` trong repository này. Việc publish lên plugin
directory của OpenAI là một kênh riêng, tuỳ chọn, không bắt buộc để cài.

Codex gọi skill tường minh bằng `$`: `$open-pr-review <PR URL>`.

## Gemini CLI

```bash
gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr
```

Cập nhật:

```bash
gemini extensions update open-pr
```

Đây là nền tảng duy nhất cài trực tiếp từ một git repository, không cần catalog ở giữa. Nó nhận cả
command (`/review`, `/fix`, `/upgrade`, `/clean`, có namespace theo extension) và cùng bốn skill đó.

## Antigravity

CLI và IDE đọc skill ở hai chỗ khác nhau, nên bạn dùng bản nào thì đi đường đó.

CLI (`agy`) — cài dạng plugin:

```bash
git clone --branch v1.0.0 https://github.com/TOMOSIA-VIETNAM/open-pr ~/open-pr
agy plugin install ~/open-pr
```

IDE — không có trình cài plugin, nên dùng đường local, script ghi vào đúng thư mục IDE đọc ở mức
global (`~/.gemini/config/skills`):

```bash
~/open-pr/scripts/install-local.sh --platform antigravity-ide
```

Cách nào thì skill cũng thành slash command: `/open-pr-review` và ba cái còn lại.

## Cài local

Dành cho Cursor, Codex, Gemini CLI và Antigravity, khi đường catalog không mở với bạn:

```bash
git clone --branch v1.0.0 https://github.com/TOMOSIA-VIETNAM/open-pr ~/open-pr
~/open-pr/scripts/install-local.sh
```

Clone theo tag release chứ không phải default branch, để bạn nhận đúng một bản đã được cắt có chủ đích.
Hãy đọc script trước khi chạy — nó nằm trong repository bạn vừa clone, chính vì lý do đó. Không có chỗ
nào ở đây đổ một file tải về thẳng vào shell.

Mặc định script cài bốn skill vào `~/.agents/skills/`, nơi Codex và Gemini CLI đều đọc, nên một lần
chạy phục vụ cả hai. Hai nền tảng còn lại có chỗ riêng:

```bash
~/open-pr/scripts/install-local.sh --platform cursor            # nguyên plugin, vào thư mục local plugin của Cursor
~/open-pr/scripts/install-local.sh --platform antigravity       # skill, vào ~/.gemini/antigravity-cli/skills
~/open-pr/scripts/install-local.sh --platform antigravity-ide   # skill, vào ~/.gemini/config/skills
```

Bỏ `--platform` thì script tự hỏi. Cờ khác: `--target DIR` cài vào chỗ bất kỳ, `--copy` nếu nền tảng
của bạn không đi theo symlink, `--update` để pull bản clone rồi cài lại trong một bước, `--uninstall`
để xoá đúng những gì nó đã cài.

Chỉ chạy trên macOS và Linux: script tạo symlink, mà trên Windows symlink cần developer mode hoặc
shell chạy quyền cao.

Thứ được đặt vào là symlink trỏ về bản clone, nên cập nhật mọi nền tảng cùng lúc chỉ là:

```bash
git -C ~/open-pr pull
```

Với `--copy` thì không có link, nên pull xong phải chạy lại script. Cách nào thì script cũng không bao
giờ đụng file nó không tạo ra: nếu đã có gì nằm sẵn ở chỗ một skill hoặc plugin sắp vào, nó dừng và
nói cho bạn biết, và `--uninstall` cũng để nguyên file đó. Bản `--copy` của nguyên plugin chỉ mang
file đã tracked — không có `.git`, không có file untracked.

## Thêm nền tảng không đổi gì trong repo của bạn

`/open-pr:upgrade` (hoặc `$open-pr-upgrade`, `/open-pr-upgrade`) nói về config per-repo mà review ghi
dưới `notebooks/review/`. Cài thêm nền tảng thứ hai không migrate, không di chuyển, không nhân bản gì
trong đó: mọi nền tảng đọc cùng một config, và không có migration nào phải chạy. Xem
[Cấu hình](./configuration.md) để biết config đó giữ những gì.
