# Kết quả trông như thế nào

[← README](../../README.vi.md)

Một review được post mang **ba phần** gắn với nhau:

1. **Overview** — toàn bộ diff nói lên điều gì, neo vào đúng commit đã đọc, nhóm theo severity. Finding cấp FILE nằm ở đây (không có line cụ thể để bám).
2. **Line comment** — finding cấp LINE, mỗi cái kèm code đã sửa trong block `suggestion` để author commit thẳng từ trang PR.
3. **Reply** — `/open-pr:fix` trả lời đúng thread đó sau khi đã push. Cuộc trao đổi ở lại chỗ vấn đề được nêu, không restart từ đầu PR.

Ảnh dưới là một review thật trên PR của chính repo này, bằng ngôn ngữ mà `settings.json` của repo đó chọn:

![Overview, line comment kèm suggested change, và reply sau khi fix đã push](../images/review-demo-vi.png)

> [!NOTE]
> Ngôn ngữ theo **repo**, không theo user. `shared.output_language` quyết định cái gì được **POST** lên PR — độc lập với ngôn ngữ agent nói chuyện với bạn trong chat.

Cùng một review bằng [English](../demo.md) và [日本語](../ja/demo.md).

## Severity

Đây là “hợp đồng” giữa reviewer và author:

| | Mức | `/open-pr:fix` |
| --- | --- | --- |
| 🔴 | MUST FIX | tự xử |
| 🟠 | SHOULD FIX | tự xử |
| 🔵 | SUGGESTION | luôn **ask** trước |
| 📝 | NOTE | luôn **ask** trước |

Diff không có gì để nói → một dòng **LGTM 🌟**, không heading.

---

[Cấu hình](./configuration.md) · [Review những gì](./review-criteria.md)
