# 实际效果

[← README](../../README.zh-Hans.md)

一条发布出来的评审包含互相关联的 **三个部分**：

1. **总览** —— 整个 diff 的结论，锚定在读取它时的那个 commit 上，按严重程度分组。FILE 级别的 findings 放在这里（没有具体某一行可依附）。
2. **行级评论** —— LINE 级别的 findings，每条都把修正后的代码放进 `suggestion` 块，作者可以直接在 PR 页面上提交。
3. **回复** —— 修复推送之后，`/open-pr:fix` 会在同一个 thread 里作答。对话留在问题被提出的地方，而不是回到 PR 顶部重新开始。

下面这张图是本仓库某个 PR 上的真实评审，使用的是该仓库 `settings.json` 选定的语言：

![总览、带 suggested change 的行级评论，以及 fix 推送后的回复](../images/review-demo-en.png)

> [!NOTE]
> 语言跟着 **仓库** 走，不跟着用户走。`shared.output_language` 决定 **发布** 到 PR 上的内容用什么语言 —— 与 agent 在聊天中跟你说话的语言相互独立。

同一条评审的 [英文](../demo.md) · [越南语](../vi-VN/demo.md) · [日语](../ja-JP/demo.md) 版本。

## 同一次运行，在各个平台上

`open-pr` 支持的每个平台上，一整页 PR 从头到尾的样子：顶部是总览，行级评论贴在它们所指的代码上，`suggestion` 块可以直接应用，以及 `/open-pr:fix` 推送之后的回复。每张截图都使用该仓库 `settings.json` 选定的语言。

<details>
<summary><b>GitHub</b> —— pull request，评审以英文发布</summary>

[![GitHub 上一个由 open-pr 评审的 pull request，从总览一直到回复](../images/preview/github.png)](../images/preview/github.png)

</details>

<details>
<summary><b>GitLab</b> —— merge request，评审以越南语发布</summary>

[![GitLab 上一个由 open-pr 评审的 merge request，从总览一直到回复](../images/preview/gitlab.png)](../images/preview/gitlab.png)

</details>

<details>
<summary><b>Bitbucket Cloud</b> —— pull request，评审以日语发布</summary>

[![Bitbucket 上一个由 open-pr 评审的 pull request，从总览一直到回复](../images/preview/bitbucket.png)](../images/preview/bitbucket.png)

</details>

## 严重程度

这是评审者与作者之间的"约定"：

| | 级别 | `/open-pr:fix` |
| --- | --- | --- |
| 🔴 | MUST FIX | 自行处理 |
| 🟠 | SHOULD FIX | 自行处理 |
| 🔵 | SUGGESTION | 一律先 **询问** |
| 📝 | NOTE | 一律先 **询问** |

对这个 diff 没什么可说的 → 只有一行 **LGTM 🌟**，不带任何标题。

---

[配置](./configuration.md) · [评审哪些方面](./review-criteria.md)
