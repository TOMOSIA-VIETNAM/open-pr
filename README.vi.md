# /open-pr:review — Agent Review Pull Request Github

[![Latest Release](https://img.shields.io/github/v/release/TOMOSIA-VIETNAM/open-pr?label=release)](https://github.com/TOMOSIA-VIETNAM/open-pr/releases)
[![License: MIT](https://img.shields.io/github/license/TOMOSIA-VIETNAM/open-pr)](./LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-5A32A3)](https://claude.ai/code)

**Tiếng Việt** · [English](./README.md) · [日本語](./README.ja.md)

Plugin dạy Agent review Pull/Merge Request **một cách nhất quán** — càng dùng càng hiểu đúng dự án của bạn. Hỗ trợ **GitHub** (URL dạng `.../pull/<số>`) và **GitLab** (URL dạng `.../-/merge_requests/<số>`, kể cả bản self-hosted) — Bitbucket chưa hỗ trợ.

Lần đầu nó đọc quy ước sẵn có (README, CLAUDE.md, AGENTS.md, docs, wiki…). Các lần sau luôn áp dụng rule đặc thù
của repo đó; bạn gõ thêm quy tắc trong chat thì nó nhớ ngay vào memory đúng repo — sát convention
thật, ít áp luật chung chung.

Nếu góp ý chỉ nằm trên comment PR? Nó sẽ hỏi bạn trước khi nhớ (tránh nhét rule giả qua PR).

Quy ước dự án không đứng yên — mỗi lần `/open-pr:review`, nếu đã đến kỳ thì plugin tự đọc lại tài liệu
convention để memory không lỗi thời. Chi tiết lịch: [Chu kỳ cập nhật quy ước](#chu-kỳ-cập-nhật-quy-ước).

## Cần gì trước

- [Claude Code](https://claude.ai/code) đã cài
- Review PR GitHub → [`gh`](https://cli.github.com/) đã đăng nhập (`gh auth login`) — plugin đăng review qua tài khoản này
- Review MR GitLab → [`glab`](https://gitlab.com/gitlab-org/cli) đã đăng nhập (`glab auth login`) — tương tự, tài khoản GitLab riêng

## Cài đặt

Trong phiên Claude Code:

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@review-pr
```

## Cập nhật lên bản mới nhất

`plugin.json` không khai `version` (dự án đang dev tích cực) — mỗi commit mới trên `main` tự thành
1 bản. Đã cài rồi thì lấy bản mới:

```
/plugin marketplace update review-pr
/plugin update open-pr@review-pr
```

Rồi `/reload-plugins` (hoặc mở phiên Claude Code mới) để nạp lại.

Repo đã setup từ trước? Chạy `/open-pr:update-plugin` ngay trong repo đó — lệnh tự lấy migration
cấu hình mà bản mới cần (nếu có) và áp dụng, để cấu hình repo cũ theo kịp mà không cần đợi lần
review/fix kế tiếp.

## Dùng thế nào

Slash command **chỉ chạy khi bạn gõ đúng lệnh** — Claude không tự gọi `/open-pr:review`

```
/open-pr:review https://github.com/<owner>/<repo>/pull/<number>
/open-pr:review https://gitlab.com/<owner>/<repo>/-/merge_requests/<number>
```

URL có đuôi `/files`, `/changes`, query… vẫn được — chỉ cần chứa link PR/MR hợp lệ. GitLab self-hosted cũng dùng được (hostname bất kỳ, miễn path còn `/-/merge_requests/<number>`).

Thêm chỉ dẫn ngay sau URL cho **lần chạy đó** (không đổi cấu hình đã lưu), ví dụ:

```
/open-pr:review https://github.com/org/repo/pull/123 focus on security
```

**Làm việc song song, không sợ đụng branch.** Mỗi lần review, code PR được checkout vào một
[git worktree](https://git-scm.com/docs/git-worktree) riêng — không đổi branch/working tree repo gốc
bạn đang code. Có thể mở nhiều phiên `/open-pr:review` (nhiều PR cùng lúc) trong khi vẫn commit/
chỉnh sửa bình thường trên nhánh hiện tại.

**Review nhiều PR liên quan trong 1 lần gọi** (vd 1 feature đụng 2 repo) — gõ nhiều URL trong cùng
lệnh, plugin tự xử lý tuần tự từng PR (không song song, để giữ khả năng tự nhận ra liên quan giữa
các PR, vd cùng 1 API contract):

```
/open-pr:review https://github.com/org/repo-a/pull/12 https://github.com/org/repo-b/pull/34
```

**Tự viết prompt giao subagent làm review?** Đừng tóm tắt rule bằng tay — bảo subagent đó đọc thẳng
file lệnh thật (`Read` đường dẫn plugin cache) rồi làm theo. Subagent không có cách nào tự "gõ"
slash command như bạn, nên tóm tắt tay dễ lệch rule/format khi post lên PR thật.

## Lần đầu cho 1 repo chưa từng thiết lập

Plugin hỏi **một lần** (7 hoặc 8 câu, tuỳ repo có CI hay không — xem câu 6):

1. **GitHub hay GitLab?** (`git_remote_type`) — tự điền sẵn từ hình dạng URL PR/MR bạn vừa đưa
   (`.../pull/N` → GitHub, `.../-/merge_requests/N` → GitLab), bạn chỉ cần xác nhận lại
2. **Ngôn ngữ** review (vi / en / ja)
3. **Đăng review ngay hay để nháp?** (`auto_submit_review`) — `true`: mọi người thấy ngay; `false`
   (mặc định): bản nháp/pending, bạn tự bấm Submit
4. **Tự đóng thread khi finding cũ đã fix?** (`auto_resolve_fixed_findings`) — mặc định `false`
5. **Bao lâu quét lại quy ước dự án?** — xem mục [Chu kỳ cập nhật quy ước](#chu-kỳ-cập-nhật-quy-ước)
   bên dưới (mặc định mỗi **1 tháng**)
6. **Có đối chiếu trạng thái CI check thật không?** (`review_ci_status`) — **chỉ hỏi nếu PR này có
   CI check** (repo không có CI → bỏ qua câu này, tự để `false`); mặc định `true` nếu được hỏi; CI
   có check fail thì cảnh báo 1 câu trong tổng quan (không tính lỗi phải fix)
7. **Ngưỡng số file để hỏi chiến lược review?** (`many_files_threshold`) — mặc định **30**; PR đổi
   nhiều file hơn số này thì plugin hỏi bạn muốn review nông toàn bộ, review sâu có chọn lọc, hay
   dừng đề nghị tách PR
8. **Ngưỡng size/file để coi là file to/dump?** (`big_file_threshold_kb`) — mặc định **20** (KB,
   ~5.000 token, ước lượng ~4 ký tự/token); file đổi vượt ngưỡng này (vd `package-lock.json`) chỉ
   lướt qua phân loại, không review chi tiết dòng-by-dòng — độc lập với ngưỡng số file ở câu 7

Tách biệt với các câu trên, plugin còn tự nhận diện ngôn ngữ *chat* với bạn — tự động, chỉ hỏi khi
không đoán được, nhớ theo từng repo. Cái này độc lập với câu 2 (câu 2 chỉ quyết định ngôn ngữ nội
dung review post lên PR).

Sau đó nó đọc tài liệu quy ước sẵn có và nhớ lại cho các lần sau.

**Repo đã dùng lâu, từ trước khi 1 cài đặt nào đó mới xuất hiện?** Lần review kế tiếp vẫn chạy bình
thường — field nào thiếu thì tạm dùng default (`git_remote_type` mặc định `"github"`, vì mọi repo
dùng plugin trước khi có GitLab đều đang review trên GitHub). Muốn file cấu hình cập nhật thật sự thì chạy
`/open-pr:update-plugin` trong repo đó. Muốn đổi lại 1 trong 7 cài
đặt (bất cứ lúc nào, không cần chờ review chạy) — gõ trong chat "đổi cấu hình review" (hoặc "xem
setting hiện tại"), plugin in ra giá trị đang áp dụng và hỏi bạn muốn đổi field nào.

Dữ liệu nhớ nằm trong repo bạn đang review, tại `notebooks/review/<tên-repo>/` (git riêng local,
không push). Nên để thư mục này trong `.gitignore` của dự án — plugin tự thêm nếu thiếu.

## Cách hoạt động (ngắn)

```
/open-pr:review <PR_URL>
        │
        ▼
Checkout code PR vào worktree riêng (không đụng branch bạn đang làm)
        │
        ▼
Review phần thay đổi, theo:
  • quy tắc kỹ thuật chung
  • convention / memory của đúng repo này
        │
        ▼
Đăng 1 review: tổng quan + comment từng dòng (khi cần)
  • mức độ bằng emoji: 🔴 MUST FIX / 🟠 SHOULD FIX / 🔵 SUGGESTION / 📝 NOTE
  • PR sạch → **LGTM 🌟**, không bới lỗi vụn
```

Hỗ trợ nhiều stack: Rails, Vue, React, Python, Node.js, Lambda, PHP, Laravel, WordPress, Shell,
Makefile, và cả file markdown điều khiển AI agent (skill/command/CLAUDE.md/AGENTS.md/cursor rules...)
(và tự mở rộng khi gặp stack mới).

**Chỉ review + comment.** Không close/merge PR, không đổi branch, không sửa code giúp bạn.

## Chu kỳ cập nhật quy ước

Quy ước dự án thay đổi theo thời gian. Plugin có thể **tự đọc lại định kỳ** khi bạn chạy
`/open-pr:review`, để memory không bị lỗi thời.

| Bạn muốn | Điền vào `doctor_schedule` |
|----------|----------------------------|
| Mỗi tuần | `"1 weeks"` hoặc `"7 days"` |
| Mỗi 2 tuần | `"2 weeks"` |
| Mỗi tháng (mặc định) | `"1 months"` |
| Mỗi quý | `"3 months"` |
| Không bao giờ tự đọc lại | `"never"` |

Sửa trong node `review` của `notebooks/review/<repo>/settings.json` — cạnh field có dòng `_comments` giải thích nhanh.
Muốn đọc lại **ngay** (không đợi lịch): trong chat nói **doctor lại** / **quét lại convention**.

## Tuỳ chỉnh sau khi đã dùng

Trong repo đã review ít nhất một lần:

| Muốn đổi | Sửa đâu |
|----------|---------|
| Ngôn ngữ mặc định | `notebooks/review/<repo>/ALWAYS_RULE.md` — khối `Ngôn ngữ output` |
| Đăng ngay / nháp, tự resolve thread, chu kỳ đọc lại quy ước | node `review` của `notebooks/review/<repo>/settings.json` |
| Quy tắc riêng team | `ALWAYS_RULE.md` mục Rule bổ sung, hoặc nói trong chat để ghi lesson |

## Sau khi review xong: `/open-pr:fix`

`/open-pr:review` chỉ review + comment, không sửa code giúp bạn. Cầm PR đã được review xong rồi, gọi
tiếp:

```
/open-pr:fix https://github.com/<owner>/<repo>/pull/<number>
```

Khác `/open-pr:review` ở chỗ **dev-facing, sửa code thật** ngay tại working directory hiện tại của
bạn (không qua worktree riêng) — nó đọc đúng finding bot đã để lại, tự quyết fix/decline theo mức độ
nghiêm trọng (🔵 SUGGESTION/📝 NOTE luôn hỏi bạn trước), sửa code đúng convention dự án đã học, gom
thành 1 commit, rồi reply lại từng finding trên PR. Chạy được ở đâu, làm gì tự động, hỏi gì trước —
xem chi tiết ngay trong lệnh khi gọi lần đầu trên 1 repo (hỏi 2 câu cấu hình, chỉ 1 lần).

Thêm chỉ dẫn để thu hẹp phạm vi cho lượt đó, ví dụ:

```
/open-pr:fix https://github.com/org/repo/pull/123 chỉ fix phần security
```
