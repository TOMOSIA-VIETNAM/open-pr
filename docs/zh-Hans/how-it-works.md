# 重复评审 / fix 流程

[← README](../../README.zh-Hans.md)

`/open-pr:review` 会把 PR 的代码检出到它自己的 **git worktree** —— 你正在开发的分支完全不受影响。可以一边评审一边继续写代码。

它看的不只是 PR 改动的部分：周边的逻辑也在范围内，所以 diff 之外的死代码和业务逻辑 bug 一样可能被发现。超出范围但仍然重要的内容，会以 **建议** 的形式返回给你权衡 —— 而不是必须修的 finding。

## 重复评审（第 2 次及以后）

如果还在同一个聊天会话里，等开发者修完或回复之后，对同一个 PR 再输入一次 `/open-pr:review` —— 它 **不会** 从头评审，而是接着上一次停下的地方继续：

```mermaid
flowchart LR
  A["/open-pr:review URL<br/>(第 2 次及以后)"] --> B[重读每个 thread<br/>旧 finding 对照当前代码]
  B --> C{修好了吗?}
  C -- 是 --> D["在那个 thread 上确认<br/>· 若你启用了则 resolve"]
  C -- 还没有 --> E["未关闭的 thread 保持原样<br/>不重复、不产生重复 finding"]
  B --> F{thread 上定下了<br/>某条规范吗?}
  F -- 是 --> G["先问过你<br/>→ 写进仓库的 memory"]
  A --> H[评审新的 diff]
  H --> I{有新东西吗?}
  I -- 有 --> J["发一条新评审<br/>只针对新增的部分"]
  I -- 没有，且全部清干净 --> K[LGTM 🌟]
  I -- 没有，但 findings 仍未关闭 --> L["不再发任何内容<br/>既有的评审依然有效"]
```

> [!TIP]
> thread 上定下来的规范，一律 **先问过你**，然后才写进 memory。

## `/open-pr:fix`

方向相反：读取 `review` 留下的那些 findings，然后改动 **真实代码**。

```mermaid
flowchart LR
  A["/open-pr:fix URL"] --> B{"在 PR 的分支上吗?<br/>不是 main/develop 吧?"}
  B -- 不是 --> C["当场停下<br/>还没碰过任何文件"]
  B -- 是 --> D["读取 review 留下的 findings<br/>跳过已 resolve · 已处理 · 开发者已定论的 thread"]
  D --> E{严重程度?}
  E -- "🔴 🟠 · 直接修" --> F["按仓库的<br/>规范 + memory 修复"]
  E -- "🔵 📝 · 或 finding 看起来不对" --> G["所有待决问题一轮问完<br/>你没决定之前不改任何文件"]
  G --> F
  F --> H["恰好 1 个 commit<br/>只包含它改过的文件 · 不 amend、不 force-push"]
  H --> I{auto_push?}
  I -- "false（默认）" --> J["停在本地<br/>等你说 'push'"]
  I -- true --> K[Push]
  J --> K
  K --> L["每条 finding 一条回复：修了，或为什么不修<br/>绝不 resolve thread —— 那是你的权力"]
```

> [!WARNING]
> `fix` 会改动你当前所在仓库里的真实代码。分支不对或 PR 不对 → 立即停下。

## 一次只跑一条

命令只有你输入时才会运行。submodule 也在覆盖范围内。URL 后面多写的话，只对 **那一次运行** 生效：

```bash
/open-pr:review https://github.com/org/repo/pull/123 [附加说明]
/open-pr:fix    https://github.com/org/repo/pull/123 [附加说明]
```

仓库第一次运行时会问一小批问题 —— 发布到 PR 上用什么语言、立即发布还是先留草稿、修好的 thread 要不要自动 resolve、隔多久重读一次文档、PR / 文件多大算过大 —— 然后读取已有的规范：README、CLAUDE.md、AGENTS.md、docs、wiki。

## 在其他平台上的同一套评审

agent 遵循的整套流程只存在于 **一个地方**：`src/` 下面的 markdown。

Cursor、Codex、Gemini CLI、Antigravity 各自需要自己的入口文件才能暴露出一个 slash command —— 所以每个平台只有一个很短的 shim，只做两件事：找到插件装在哪里，然后交给同一份命令文件。任何规则、阈值、严重程度都不会在 shim 里重述。

---

[安装](./install.md) · [配置](./configuration.md) · [实际效果](./demo.md)
