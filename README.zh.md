# /open-pr:review — Agent Review Pull Request Github

[![Latest Release](https://img.shields.io/github/v/release/TOMOSIA-VIETNAM/open-pr?label=release)](https://github.com/TOMOSIA-VIETNAM/open-pr/releases)
[![License: MIT](https://img.shields.io/github/license/TOMOSIA-VIETNAM/open-pr)](./LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-5A32A3)](https://claude.ai/code)

[Tiếng Việt](./README.md) · [English](./README.en.md) · [日本語](./README.ja.md) · **简体中文**

一个教 Agent **按统一标准**评审 GitHub Pull Request 的插件 —— 用得越久，越懂你的项目。

第一次运行时它会读取项目已有的约定（README、CLAUDE.md、AGENTS.md、docs、wiki……）。之后每次都会应用该仓库特有的
规则；你在对话里补充规则，它会立刻记进对应仓库的 memory —— 贴近真实约定，不硬套通用规则。

如果某条建议只出现在 PR 评论里呢？它会先问你再记（避免通过 PR 混入假规则）。

项目约定不是一成不变的 —— 每次 `/open-pr:review` 时，若已到期，插件会重新读取约定文档，让 memory 不过时。
周期详情见[约定更新周期](#约定更新周期)。

## 前置条件

- 已安装 [Claude Code](https://claude.ai/code)
- 已登录 [`gh`](https://cli.github.com/)（`gh auth login`）—— 插件用这个账号发布评审

## 安装

在 Claude Code 会话中：

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@review-pr
```

## 更新到最新版

`plugin.json` 没有声明 `version`（项目正在活跃开发）—— `main` 上每个新提交都算一个版本。已安装过的话这样取最新版：

```
/plugin marketplace update review-pr
/plugin update open-pr@review-pr
```

然后 `/reload-plugins`（或新开一个 Claude Code 会话）重新加载。

对已经配置过的仓库，想按新版本检查／更新配置（若有新增配置项会立即补齐，不用等下一次评审）—— 在该仓库的
对话里说「刷新配置」（或「修改评审配置」）。

## 怎么用

斜杠命令**只在你亲自输入时才执行** —— Claude 不会自己调用 `/open-pr:review`

```
/open-pr:review https://github.com/<owner>/<repo>/pull/<number>
```

带 `/files`、`/changes`、query 参数的 URL 都可以 —— 只要包含合法的 PR 链接即可。

在 URL 后面追加指令，只对**这一次运行**生效（不改动已保存的配置），例如：

```
/open-pr:review https://github.com/org/repo/pull/123 focus on security
```

**并行工作也不怕动到分支。** 每次评审，PR 的代码都会被 checkout 到独立的
[git worktree](https://git-scm.com/docs/git-worktree) —— 不改动你正在开发的仓库的分支／工作区。可以同时开多个
`/open-pr:review` 会话（多个 PR 一起），同时照常在当前分支提交／改代码。

**一次调用评审多个相关 PR**（例如一个功能改动了 2 个仓库）—— 在同一条命令里给多个 URL，插件会逐个顺序处理
（不并行，为的是保留发现 PR 之间关联的能力，例如同一个 API contract）：

```
/open-pr:review https://github.com/org/repo-a/pull/12 https://github.com/org/repo-b/pull/34
```

**想自己写 prompt 把评审交给 subagent？** 别手写摘要规则 —— 让那个 subagent 直接 `Read` 真正的命令文件
（插件缓存路径）再照做。Subagent 没法像你一样「输入」斜杠命令，手写摘要在真实发布到 PR 时容易偏离规则/格式。

## 对尚未配置过的仓库首次运行

插件只问**一次**（6 或 7 个问题，取决于仓库有没有 CI —— 见第 5 问）：

1. 评审输出的**语言**（vi / en / ja）
2. **立刻发布评审还是留草稿？**（`auto_submit_review`）—— `true`：所有人马上看到；`false`（默认）：留在 GitHub
   上的草稿，你自己点 Submit
3. **旧的指摘已修复时自动关闭 thread 吗？**（`auto_resolve_fixed_findings`）—— 默认 `false`
4. **多久重新扫描一次项目约定？** —— 见下面的[约定更新周期](#约定更新周期)（默认每 **1 个月**）
5. **要不要核对 CI check 的真实状态？**（`review_ci_status`）—— **仅当这个 PR 至少有 1 个 CI check 时才问**
   （仓库没有 CI → 跳过此问，自动设为 `false`）；被问到时默认 `true`；有 check 失败时在总览里给一句提醒
   （不计入必须修复的问题）
6. **多少个文件就询问评审策略？**（`many_files_threshold`）—— 默认 **30**；PR 改动的文件数超过这个值时，插件会问
   你是要整体粗看、挑重点深看，还是中止并建议拆分 PR
7. **单文件多大算大文件/dump 文件？**（`big_file_threshold_kb`）—— 默认 **20**（KB，约 5,000 token，按约
   4 字符/token 粗估）；改动超过这个阈值的文件（例如 `package-lock.json`）只做粗略分类，不逐行细看 —— 与第 6 问的
   文件数阈值相互独立

之后它会读取已有的约定文档并记下来，供后续使用。

**仓库用了很久，某个配置项是后来才有的？** 什么都不用做 —— 下次评审时插件会自动发现，暂用默认值，并在对话里说一句。
想改这 7 个配置里的任何一个（随时都行，不用等评审运行）—— 在对话里说「修改评审配置」（或「查看当前设置」），插件会
打印当前生效的值并问你要改哪一项。

记忆数据存在你正在评审的仓库内，位置是 `notebooks/review/<仓库名>/`（本地独立 git，不会 push）。建议把这个目录
写进项目的 `.gitignore` —— 缺少时插件会自动添加。

## 工作原理（简述）

```
/open-pr:review <PR_URL>
        │
        ▼
把 PR 代码 checkout 到独立 worktree（不碰你正在做的分支）
        │
        ▼
评审改动部分，依据：
  • 通用技术规则
  • 这个仓库自己的 convention / memory
        │
        ▼
发布 1 条评审：总览 + 按行评论（需要时）
  • 严重程度用 emoji 表示：🔴 MUST FIX / 🟠 SHOULD FIX / 🔵 SUGGESTION / 📝 NOTE
  • PR 很干净 → **LGTM 🌟**，不挑无关紧要的毛病
```

支持多种技术栈：Rails、Vue、React、Python、Node.js、Lambda、PHP、Laravel、WordPress、Shell、Makefile，以及用来
指挥 AI agent 的 markdown 文件（skill/command/CLAUDE.md/AGENTS.md/cursor rules 等）（遇到新栈会自动扩展）。

**只做评审 + 评论。** 不会 close/merge PR，不会切分支，不会替你改代码。

## 约定更新周期

项目约定会随时间变化。插件可以在你运行 `/open-pr:review` 时**定期重新读取**，让 memory 不过时。

| 你想要 | 填进 `doctor_schedule` |
|--------|------------------------|
| 每周 | `"1 weeks"` 或 `"7 days"` |
| 每 2 周 | `"2 weeks"` |
| 每月（默认） | `"1 months"` |
| 每季度 | `"3 months"` |
| 永不自动重读 | `"never"` |

在 `notebooks/review/<repo>/meta.json` 里改 —— 字段旁边有 `_comments` 行做简要说明。想**立刻**重读（不等排期）：
在对话里说 **doctor lại** / **重新扫描 convention**。

## 用起来之后的自定义

在至少评审过一次的仓库里：

| 想改什么 | 改哪里 |
|----------|--------|
| 默认语言 | `notebooks/review/<repo>/ALWAYS_RULE.md` —— `Output language` 块 |
| 立刻发布／草稿、自动 resolve thread、约定重读周期 | `notebooks/review/<repo>/meta.json` |
| 团队自有规则 | `ALWAYS_RULE.md` 的补充规则一节，或在对话里说出来记成 lesson |

## 评审之后：`/open-pr:fix`

`/open-pr:review` 只评审 + 评论，不替你改代码。拿到已经评审过的 PR，接着调用：

```
/open-pr:fix https://github.com/<owner>/<repo>/pull/<number>
```

和 `/open-pr:review` 的区别是它**面向开发者、真的会改代码**，就在你当前的工作目录里直接执行（不走独立 worktree）
—— 它读取 bot 留下的指摘，按严重程度自行决定修还是不修（🔵 SUGGESTION／📝 NOTE 一定先问你），按已学到的项目
约定改代码，合成 1 个 commit，然后逐条回复 PR 上的指摘。它能在哪运行、哪些事自动做、哪些事会先问你 —— 首次在
某个仓库调用时命令内会说明（只问 2 个配置问题，一次性）。

想只针对这一次收窄范围，追加指令即可，例如：

```
/open-pr:fix https://github.com/org/repo/pull/123 只修 security 部分
```
