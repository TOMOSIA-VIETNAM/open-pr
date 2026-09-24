# Cấu hình

[← README](../../README.vi-VN.md)

Những gì plugin ghi nhớ cho từng repo, và chỗ bạn sửa khi cần.

## Dữ liệu nằm ở đâu

Memory, settings và worktree review của mọi repo nằm trong **một thư mục dữ liệu** bạn chọn một lần, ngoài mọi repo — không thêm dòng `.gitignore`, không hiện trong `git status`.

```
~/workspace/notebooks/review/   ← thư mục dữ liệu (bạn chọn)
├── .git                        lịch sử local những gì đã học
├── repo-backend/               memory + settings + worktrees/
└── repo-frontend/
~/workspace/repo-backend/       ← không bị chạm
```

Khi chưa có thư mục dữ liệu, command đầu tiên sẽ hỏi. Khuyến nghị là `notebooks/review/` ở thư mục ngay bên ngoài repo — với `~/workspace/repo-backend` thì là `~/workspace/notebooks/review/` — hoặc đường dẫn bất kỳ bạn gõ. `notebooks/review/` có sẵn trong repo được **copy** sang đó (trừ worktree) và giữ nguyên tại chỗ. Về sau, repo nào chưa có trong thư mục dữ liệu cũng được tìm như vậy dưới chỗ bạn đứng, và `notebooks/review/<repo>/` của nó được đề nghị import. Lựa chọn lưu ở `data_dir` trong `~/.config/open-pr/config.json` — sửa file đó để đổi chỗ.

Chỗ bạn đứng không ảnh hưởng tới nơi lưu dữ liệu. Đứng ở workspace chứa nhiều repo vẫn review được PR **chéo repo** trong một lượt (lần lượt, không song song):

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` gọi được từ workspace (nó tự tìm đúng repo, miễn repo đang ở branch của PR) — hoặc từ chính worktree mà `review` đã tạo; ở đó URL không bắt buộc vì session đã biết PR nào.

## Command

| Command | Bạn đứng ở đâu | Nó ghi gì |
| --- | --- | --- |
| `/open-pr:review` | workspace chứa repo, hoặc trong repo — tự tìm theo `git remote` | comment trên PR + memory ở `<data>/<repo>/` |
| `/open-pr:fix` | trong repo đó / workspace chứa nó — nhưng **repo phải đang ở branch của PR** | code thật trong repo + reply trên PR |
| `/open-pr:upgrade` | bất kỳ đâu — mọi repo trong thư mục dữ liệu, hoặc các repo bạn nêu tên | `<data>/<repo>/settings.json` |
| `/open-pr:clean` | bất kỳ đâu | không ghi gì — chỉ xóa `<data>/*/worktrees/*` |
| `/open-pr:feedback` | bất kỳ đâu | không ghi gì ở máy — một issue trên tracker của plugin, sau khi bạn duyệt nội dung |

## Setting

`<data>` bên dưới là thư mục dữ liệu. Mọi thứ đã học được index trong `<data>/<repo>/memory.md` (mục lục — tiết kiệm token, vẫn nắm toàn cảnh). Chi tiết nằm ở `<data>/<repo>/memories/*.md`.

> [!NOTE]
> Cả thư mục dữ liệu do một **git local độc lập** quản lý — không remote, không push. Bạn theo dõi được memory đổi qua từng lần review.

Team rule viết văn xuôi bình thường vào `ALWAYS_RULE.md` (mặc định rỗng). Phần còn lại nằm ở `settings.json`:

| Field | Nghĩa | Default |
| --- | --- | --- |
| `shared.chat_language` | ngôn ngữ nói chuyện trong chat | tự nhận |
| `shared.output_language` | ngôn ngữ post lên PR | hỏi một lần rồi lưu |
| `review.auto_submit_review` | `true` = post luôn, `false` = giữ lại cho bạn xem trước — dạng draft trên PR ở vendor có draft, còn Bitbucket không có draft nên review nằm trong chat và PR vẫn trống | `false` |
| `review.auto_resolve_fixed_findings` | tự resolve thread khi finding đã được sửa | `false` |
| `review.post_lgtm` | post kết quả sạch (không có finding nào) lên PR; `false` thì chỉ hiện trong chat | `true` |
| `review.doctor_schedule` | chu kỳ đọc lại docs quy ước: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"` |
| `review.review_ci_status` | có nhắc CI đang fail không (chỉ warn, không bắt sửa) | có CI ⇒ `true` |
| `review.many_files_threshold` | PR nhiều hơn bấy nhiêu file thì cảnh báo quá lớn | `30` |
| `review.big_file_threshold_kb` | file diff to hơn ngưỡng này bị bỏ khỏi lần đọc đầu | `20` |
| `fix.decline_needs_confirmation` | hỏi trước khi bỏ qua một finding | `true` |
| `fix.auto_push` | tự push sau khi commit | `false` |

---

[Cài đặt](./install.md) · [Flow re-review / fix](./how-it-works.md) · [Review những gì](./review-criteria.md)
