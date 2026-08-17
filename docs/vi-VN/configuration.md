# Cấu hình

[← README](../../README.vi-VN.md)

Những gì plugin ghi nhớ cho từng repo, và chỗ bạn sửa khi cần.

## Đứng ở đâu

```
✅ đứng ở workspace                          ❌ đứng trong repo
─────────────────────────                    ─────────────────────────
workspace/            ← gõ ở đây             repo-backend/         ← gõ ở đây
├── notebooks/review/  memory + worktree     ├── notebooks/review/  memory nằm TRONG dự án
│   ├── repo-backend/  ngoài mọi repo        ├── .gitignore         +1 dòng — thay đổi thật
│   └── repo-frontend/                       └── src/
├── repo-backend/     ← sạch, 0 file lạ
└── repo-frontend/    ← sạch, 0 file lạ      (repo-frontend? không thấy)
```

`notebooks/review/` (memory + worktree) luôn sinh ra **ngay chỗ bạn gõ command**.

| Đứng ở | Hệ quả |
| --- | --- |
| **Workspace** (khuyến nghị) | Repo không bị chạm. Các repo nằm cạnh nhau → review được PR **chéo repo** trong một lượt (lần lượt, không song song) |
| **Trong repo** | `notebooks/review/` nằm trong dự án. Plugin tự thêm 1 dòng `.gitignore` nên `git status` sạch — nhưng dòng đó vẫn là thay đổi thật trong repo |

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` gọi được từ workspace (nó tự tìm đúng repo, miễn repo đang ở branch của PR) — hoặc từ chính worktree mà `review` đã tạo; ở đó URL không bắt buộc vì session đã biết PR nào.

## Command

| Command | Bạn đứng ở đâu | Nó ghi gì |
| --- | --- | --- |
| `/open-pr:review` | workspace chứa repo (nên vậy), hoặc trong repo — tự tìm theo `git remote` | comment trên PR + memory ở `notebooks/review/<repo>/` |
| `/open-pr:fix` | trong repo đó / workspace chứa nó — nhưng **repo phải đang ở branch của PR** | code thật trong repo + reply trên PR |
| `/open-pr:upgrade` | workspace hoặc repo đã setup — nhiều repo thì cho bạn chọn | `notebooks/review/<repo>/settings.json` |
| `/open-pr:clean` | bất kỳ đâu phía trên `notebooks/review/` cần dọn | không ghi gì — chỉ xóa `notebooks/review/*/worktrees/*` |
| `/open-pr:feedback` | bất kỳ đâu | không ghi gì ở máy — một issue trên tracker của plugin, sau khi bạn duyệt nội dung |

## Setting

Mọi thứ đã học được index trong `notebooks/review/<repo>/memory.md` (mục lục — tiết kiệm token, vẫn nắm toàn cảnh). Chi tiết nằm ở `notebooks/review/<repo>/memories/*.md`.

> [!NOTE]
> Cả thư mục `notebooks/review/` do một **git local độc lập** quản lý — không remote, không push. Bạn theo dõi được memory đổi qua từng lần review.

Team rule viết văn xuôi bình thường vào `ALWAYS_RULE.md` (mặc định rỗng). Phần còn lại nằm ở `settings.json`:

| Field | Nghĩa | Default |
| --- | --- | --- |
| `shared.chat_language` | ngôn ngữ nói chuyện trong chat | tự nhận |
| `shared.output_language` | ngôn ngữ post lên PR | hỏi một lần rồi lưu |
| `review.auto_submit_review` | `true` = post luôn, `false` = giữ lại cho bạn xem trước — dạng draft trên PR ở vendor có draft, còn Bitbucket không có draft nên review nằm trong chat và PR vẫn trống | `false` |
| `review.auto_resolve_fixed_findings` | tự resolve thread khi finding đã được sửa | `false` |
| `review.doctor_schedule` | chu kỳ đọc lại docs quy ước: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"` |
| `review.review_ci_status` | có nhắc CI đang fail không (chỉ warn, không bắt sửa) | có CI ⇒ `true` |
| `review.many_files_threshold` | PR nhiều hơn bấy nhiêu file thì cảnh báo quá lớn | `30` |
| `review.big_file_threshold_kb` | file diff to hơn ngưỡng này bị bỏ khỏi lần đọc đầu | `20` |
| `fix.decline_needs_confirmation` | hỏi trước khi bỏ qua một finding | `true` |
| `fix.auto_push` | tự push sau khi commit | `false` |

---

[Cài đặt](./install.md) · [Flow re-review / fix](./how-it-works.md) · [Review những gì](./review-criteria.md)
