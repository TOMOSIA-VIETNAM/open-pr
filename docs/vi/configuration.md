# Cấu hình

[← README](../../README.vi.md)

Những gì plugin ghi nhớ cho từng repo, và chỗ để bạn sửa.

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

`notebooks/review/` — memory + worktree — luôn sinh ra ngay tại chỗ bạn gõ command. Đứng trong repo thì
nó nằm trong dự án; plugin có tự thêm 1 dòng vào `.gitignore` nên `git status` vẫn sạch, nhưng dòng đó
là một thay đổi thật trong repo của bạn.

Đứng ở workspace thì repo không hề bị chạm, và vì các repo nằm cạnh nhau nên nó review được PR chéo
repo — nhiều PR của cùng một tính năng trong một lượt, chạy lần lượt chứ không song song. Đứng trong
`repo-backend` thì `repo-frontend` là vô hình:

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` cũng gọi được từ workspace — nó tự tìm đúng repo rồi vào đó sửa, miễn repo ấy đang đứng
ở branch của PR.

Mọi thứ nó ghi nhớ được index như một mục lục trong `notebooks/review/<repo>/memory.md`: vừa tiết kiệm
token vì không phải nạp chi tiết, vừa nắm được toàn cảnh những gì đã học. Chi tiết nằm rời từng file
trong `notebooks/review/<repo>/memories/*.md`. Cả thư mục `notebooks/review/` do một git local độc lập
quản lý — không remote, không push — nên bạn theo dõi được memory thay đổi qua từng lần review.

Rule riêng của team thì viết văn xuôi bình thường vào `ALWAYS_RULE.md` (mặc định rỗng), còn lại nằm ở
`settings.json`:


| Field                                | Nghĩa                                                                                     | Mặc định            |
| ------------------------------------ | ----------------------------------------------------------------------------------------- | ------------------- |
| `shared.chat_language`               | ngôn ngữ nói chuyện trong chat                                                            | tự nhận             |
| `shared.output_language`             | ngôn ngữ post lên PR                                                                      | hỏi một lần rồi lưu |
| `review.auto_submit_review`          | `true` = post luôn, `false` = để draft cho bạn xem lại                                    | `false`             |
| `review.auto_resolve_fixed_findings` | tự resolve thread khi finding đã được sửa                                                 | `false`             |
| `review.doctor_schedule`             | chu kỳ đọc lại tài liệu quy ước: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"`     |
| `review.review_ci_status`            | có nhắc CI đang fail hay không (chỉ cảnh báo, không bắt sửa)                              | có CI ⇒ `true`      |
| `review.many_files_threshold`        | PR nhiều hơn bấy nhiêu file thì cảnh báo quá lớn                                          | `30`                |
| `review.big_file_threshold_kb`       | file diff to hơn ngưỡng này bị bỏ khỏi lần đọc đầu                                        | `20`                |
| `fix.decline_needs_confirmation`     | hỏi bạn trước khi bỏ qua một finding                                                      | `true`              |
| `fix.auto_push`                      | tự push sau khi commit                                                                    | `false`             |

## Mỗi command ghi gì

| Command | Lúc gõ bạn đứng ở đâu | Nó ghi gì |
| ------- | --------------------- | --------- |
| `/open-pr:review` | ở workspace chứa repo (nên vậy), hoặc trong chính repo — nó tự tìm theo `git remote` | comment trên PR + memory ở `notebooks/review/<repo>/` |
| `/open-pr:fix` | trong repo đó, hoặc workspace chứa nó — nhưng **repo phải đang ở branch của PR** | code thật trong repo đó + reply trên PR |
| `/open-pr:upgrade` | ở workspace hoặc repo đã setup — nhiều repo thì nó cho bạn chọn | `notebooks/review/<repo>/settings.json` |
