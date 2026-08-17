# Kết quả trông như thế nào

[← README](../../README.vi-VN.md)

Một lượt review được post mang **ba phần** gắn với nhau:

1. **Overview** — toàn bộ diff nói lên điều gì, neo vào đúng commit đã đọc, nhóm theo severity. Finding cấp FILE nằm ở đây (không có line cụ thể để bám).
2. **Line comment** — finding cấp LINE, mỗi cái kèm code đã sửa trong block `suggestion` để author commit thẳng từ trang PR.
3. **Reply** — `/open-pr:fix` trả lời đúng thread đó sau khi đã push. Cuộc trao đổi ở lại chỗ vấn đề được nêu, không restart từ đầu PR.

Ảnh dưới là một review thật trên PR của chính repo này, bằng ngôn ngữ mà `settings.json` của repo đó chọn:

![Overview, line comment kèm suggested change, và reply sau khi fix đã push](../images/review-demo-vi.png)

> [!NOTE]
> Ngôn ngữ theo **repo**, không theo user. `shared.output_language` quyết định cái gì được **POST** lên PR — độc lập với ngôn ngữ agent nói chuyện với bạn trong chat.

Cùng một review bằng [English](../demo.md), [日本語](../ja-JP/demo.md) và [简体中文](../zh-Hans/demo.md).

## Cùng một lượt chạy, trên từng vendor

Nguyên một trang PR từ đầu đến cuối, trên mỗi vendor mà `open-pr` hỗ trợ: overview ở trên cùng, line
comment nằm ngay đoạn code nó nói tới, block `suggestion` sẵn sàng apply, và reply sau khi
`/open-pr:fix` đã push. Mỗi ảnh chụp ở ngôn ngữ mà `settings.json` của repo đó chọn.

<details>
<summary><b>GitHub</b> — pull request, review post bằng English</summary>

[![Một pull request trên GitHub được open-pr review, từ overview xuống tới các reply](../images/preview/github.png)](../images/preview/github.png)

</details>

<details>
<summary><b>GitLab</b> — merge request, review post bằng Tiếng Việt</summary>

[![Một merge request trên GitLab được open-pr review, từ overview xuống tới các reply](../images/preview/gitlab.png)](../images/preview/gitlab.png)

</details>

<details>
<summary><b>Bitbucket Cloud</b> — pull request, review post bằng 日本語</summary>

[![Một pull request trên Bitbucket được open-pr review, từ overview xuống tới các reply](../images/preview/bitbucket.png)](../images/preview/bitbucket.png)

</details>

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
