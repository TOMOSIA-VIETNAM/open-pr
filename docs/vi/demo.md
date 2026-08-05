# Một review trông như thế nào

Một review được post mang ba thứ cùng lúc, và chúng gắn với nhau:

1. **Overview** — toàn bộ diff nói lên điều gì, gắn vào đúng commit đã đọc, nhóm theo severity. Finding
   cấp FILE nằm ở đây, vì chúng không có dòng cụ thể nào để bám vào.
2. **Comment trên đúng dòng** — finding cấp LINE, mỗi cái kèm code đã sửa trong block `suggestion` để
   tác giả commit thẳng từ trang PR.
3. **Reply** — `/open-pr:fix` trả lời ngay trên thread đó sau khi đã push, nên cuộc trao đổi ở lại đúng
   nơi vấn đề được nêu, không phải bắt đầu lại từ đầu PR.

Ảnh dưới đây là một review thật, trên một pull request của chính repo này, bằng ngôn ngữ mà
`settings.json` của repo đó chọn.

![Overview, comment trên dòng kèm suggested change, và reply để lại sau khi fix đã được push](../images/review-demo-vi.png)

Ngôn ngữ là theo repo, không theo người dùng: `shared.output_language` quyết định cái gì được POST, và
nó độc lập với ngôn ngữ agent nói chuyện với bạn. Cùng review đó bằng
[tiếng Anh](../demo.md) và [tiếng Nhật](../ja/demo.md).

Severity là cam kết giữa reviewer và tác giả: 🔴 MUST FIX · 🟠 SHOULD FIX · 🔵 SUGGESTION · 📝 NOTE.
`/open-pr:fix` tự xử 🔴 và 🟠, còn 🔵 hay 📝 thì luôn hỏi trước. Diff không có gì để nói thì chỉ một dòng
— **LGTM 🌟** — không heading nào cả.

Về [README](../../README.vi.md) · [Cấu hình](./configuration.md) ·
[Review những gì](./review-criteria.md)
