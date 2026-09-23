# Cấu hình

[← README](../../README.vi-VN.md)

Những gì plugin ghi nhớ cho từng repo, và chỗ bạn sửa khi cần.

## Đứng ở đâu

Memory, setting và worktree review nằm ở **một chỗ duy nhất trên máy**, không bao giờ trong dự án:

```
~/.open-pr/review/
├── .git/            lịch sử local của những gì đã học — không remote, không push
├── repo-backend/    memory.md · memories/ · templates/ · ALWAYS_RULE.md · settings.json · worktrees/
└── repo-frontend/
```

Vì vậy gõ command ở bất kỳ đâu tìm được repo: trong repo, hoặc workspace chứa nó (khớp theo `git remote`). Không ghi gì vào dự án, không thêm dòng `.gitignore`. Workspace có nhiều repo nằm cạnh nhau → review được PR **chéo repo** trong một lượt (lần lượt, không song song):

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` gọi được từ cùng những chỗ đó (repo phải đang ở branch của PR) — hoặc từ chính worktree mà `review` đã tạo; ở đó URL không bắt buộc vì session đã biết PR nào.

> [!NOTE]
> Chuyển từ bản cũ để `~/.open-pr/review/` trong workspace: plugin không tự chuyển. Muốn giữ những gì đã học, chuyển một lần — `mkdir -p ~/.open-pr && mv notebooks/review ~/.open-pr/review` — rồi xoá dòng `~/.open-pr/review/` trong `.gitignore`.

## Command

| Command | Bạn đứng ở đâu | Nó ghi gì |
| --- | --- | --- |
| `/open-pr:review` | trong repo, hoặc workspace chứa nó — tự tìm theo `git remote` | comment trên PR + memory ở `~/.open-pr/review/<repo>/` |
| `/open-pr:fix` | trong repo đó / workspace chứa nó — nhưng **repo phải đang ở branch của PR** | code thật trong repo + reply trên PR |
| `/open-pr:upgrade` | bất kỳ đâu — nâng mọi repo đã setup, hoặc các repo bạn nêu tên | `~/.open-pr/review/<repo>/settings.json` |
| `/open-pr:clean` | bất kỳ đâu | không ghi gì — chỉ xóa `~/.open-pr/review/*/worktrees/*` |
| `/open-pr:feedback` | bất kỳ đâu | không ghi gì ở máy — một issue trên tracker của plugin, sau khi bạn duyệt nội dung |

## Setting

Mọi thứ đã học được index trong `~/.open-pr/review/<repo>/memory.md` (mục lục — tiết kiệm token, vẫn nắm toàn cảnh). Chi tiết nằm ở `~/.open-pr/review/<repo>/memories/*.md`.

> [!NOTE]
> Cả thư mục `~/.open-pr/review/` do một **git local độc lập** quản lý — không remote, không push. Bạn theo dõi được memory đổi qua từng lần review.

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
