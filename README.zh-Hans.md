<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/images/logo/logo-lockup-dark.svg?v=moth1">
    <img src="./docs/images/logo/logo-lockup.svg?v=moth1" alt="Open PullRequest" width="400">
  </picture>
</p>

<p align="center">
  <strong>AI 代码评审，直接落在你的 PR 上。</strong><br>
  <strong>开源。自托管。</strong><br>
  <sub>支持 <picture><source media="(prefers-color-scheme: dark)" srcset="./docs/images/icon/github-dark.png"><img src="./docs/images/icon/github.png" alt="" height="13"></picture>&nbsp;GitHub · <img src="./docs/images/icon/gitlab.png" alt="" height="13">&nbsp;GitLab · <img src="./docs/images/icon/bitbucket.png" alt="" height="13">&nbsp;Bitbucket</sub><br>
  <code>/open-pr:review</code> · <code>/open-pr:fix</code>
</p>

<p align="center">
  <a href="https://github.com/TOMOSIA-VIETNAM/open-pr/releases"><img alt="Release" src="https://img.shields.io/github/v/release/TOMOSIA-VIETNAM/open-pr?style=flat-square&label=release&color=2ea44f"></a>
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/TOMOSIA-VIETNAM/open-pr?style=flat-square&color=blue"></a>
  <a href="https://github.com/hashgraph-online/awesome-ai-plugins#development--workflow"><img alt="Listed on Awesome AI Plugins" src="https://img.shields.io/badge/Awesome-AI%20Plugins-c5203e?style=flat-square&logo=awesomelists&logoColor=white"></a>
  <a href="#安装"><img alt="GitHub" src="https://img.shields.io/badge/GitHub-supported-181717?style=flat-square&logo=github&logoColor=white"></a>
  <a href="#安装"><img alt="GitLab" src="https://img.shields.io/badge/GitLab-supported-FC6D26?style=flat-square&logo=gitlab&logoColor=white"></a>
  <a href="#安装"><img alt="Bitbucket" src="https://img.shields.io/badge/Bitbucket-supported-0052CC?style=flat-square&logo=bitbucket&logoColor=white"></a>
</p>

<p align="center">
  <a href="#安装"><img alt="Claude Code" src="https://img.shields.io/badge/Claude_Code-supported-D97757?style=flat-square&logo=anthropic&logoColor=white"></a>
  <a href="#安装"><img alt="Cursor" src="https://img.shields.io/badge/Cursor-supported-000000?style=flat-square&logo=cursor&logoColor=white"></a>
  <a href="#安装"><img alt="Codex" src="https://img.shields.io/badge/Codex-supported-412991?style=flat-square&logo=openai&logoColor=white"></a>
  <a href="#安装"><img alt="Gemini CLI" src="https://img.shields.io/badge/Gemini_CLI-supported-4285F4?style=flat-square&logo=google&logoColor=white"></a>
  <a href="#安装"><img alt="Antigravity" src="https://img.shields.io/badge/Antigravity-supported-6E56CF?style=flat-square"></a>
</p>

<p align="center">
  <a href="./README.vi-VN.md">Tiếng Việt</a> · <a href="./README.md">English</a> · <a href="./README.ja-JP.md">日本語</a> · <strong>简体中文</strong>
</p>

AI 编码让 PR 变快了。但评审并没有变快。

**`open-pr` 把第一轮评审跑在 PR 上，而不是你的本地。** 任何打开这个 PR 的人，看到的都是同一份反馈。

<p align="center">
  <a href="./docs/zh-Hans/demo.md"><img src="./docs/images/review-demo-en.png" width="680" alt="总览、带 suggested change 的行级评论，以及 fix 推送后的回复"></a>
</p>

一次运行会产出三个互相关联的部分：**总览**、**行级评论**（附带 suggested change），以及 `/open-pr:fix` 推送之后的 **回复**。 —— [查看演示](./docs/zh-Hans/demo.md)

- 🔍 **每次运行恰好 1 条评审** —— 只发一条，不是源源不断的 bot 评论
- 🧠 **学习你的仓库** —— 读 README / CLAUDE.md / AGENTS.md / docs / wiki；**团队规范优先于通用规则**
- 💬 **记住团队说过的话** —— 这次 PR 上的一句纠正，下次运行就会应用
- 🔧 **`/open-pr:fix` 有纪律** —— 恰好 **1** 个 commit，不 force-push，每个 thread 一条回复
- 🔓 **开源，无需 `open-pr` 服务** —— MIT 许可，不需要 `open-pr` 的服务器、也不需要 bot 账号；就跑在你已经在用的 agent CLI 里

## 已收录于 Awesome AI Plugins

`open-pr` 已收录于 Hashgraph Online 维护的跨平台目录 [Awesome AI Plugins](https://github.com/hashgraph-online/awesome-ai-plugins#development--workflow) 的 *Community Plugins → Development & Workflow* 分类，并被 [HOL Plugin Registry](https://hol.org/registry/plugins) 收录——该 registry 会扫描所有上榜项目并公布 trust score。

收录的门槛正是这次扫描：**score ≥ 80，且没有 high 或 critical 级别的 finding**。扫描由目录方自己针对本仓库的默认分支运行，结果不是我们自报的。扫描是信任信号，不是安全保证。

## 安装

**1. 先登录对应平台的 CLI。** 插件本身不持有任何 credential —— 它用*你的*账号读取 PR、发表评审：

```bash
# GitHub
brew install gh          # 或 https://cli.github.com/
gh auth login            # GitHub.com → HTTPS → Login with a web browser
gh auth status           # 应显示 "Logged in to github.com as <you>"
```

GitLab：`brew install glab && glab auth login --hostname gitlab.com`。Bitbucket 没有 CLI —— 它从环境变量读取 `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN`。各平台的最小权限与自查方法：[各平台如何取得 token](./docs/zh-Hans/credentials.md)。

**2. 插件。** [Claude Code](https://claude.ai/code)：

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

**在 Cursor、Codex、Gemini CLI、Antigravity 上安装：**

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash
```

完整指南：[安装](./docs/zh-Hans/install.md) · [各平台如何取得 token](./docs/zh-Hans/credentials.md)。

PR URL 格式：GitHub `.../pull/<n>` · GitLab `.../-/merge_requests/<n>`（含自建实例）· Bitbucket Cloud `.../pull-requests/<n>`。

## 为什么评审成了瓶颈

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/images/bottleneck/zh-dark.svg">
    <img src="./docs/images/bottleneck/zh.svg" width="760" alt="AI 之前：每天 10 个 PR，评审跟得上。AI 之后：每天 30 个 PR，评审成为瓶颈。AI 之后 + Open-pr：每天 30 个 PR，Open-pr 让评审更快，评审跟得上。">
  </picture>
</p>

在 AI 编码的时代，PR 提交的速度远远快过评审的速度。瓶颈已经不在写代码，而在 **评审**。评审者既要检查项目规范 / 安全 / 性能，*还要* 覆盖业务逻辑 —— 随着 PR 数量增长，这种方式并不 scale。

本地评审很难取信于人。谁都可以说 *"我已经审过了"*。所以 `open-pr` 把这一步搬到 **远端**，让它透明 —— 评论就留在 PR 上，任何打开这个 PR 的人都看得见。

> [!NOTE]
> **评审轮次**（给团队的一个建议）：
> 1. **第 1 轮** —— 开发者自己在 PR 上跑一次 AI 评审。还没有评审评论 → 评审者 **直接退回**，不去碰它。
> 2. **第 2 轮** —— 评审者再跑一次（AI）。干净 → **LGTM**。
> 3. **第 3 轮** —— 评审者评审业务领域的部分。

> [!IMPORTANT]
> AI 减轻的是流程负担，但 **最终责任仍然在你身上**。

## 与普通评审 skill 的差别

很多评审 skill 只是一份 `SKILL.md` 说明。每次运行结果都不一样 —— 措辞不同、松紧不同，很容易偏离项目自己的规范。

| 普通 skill 常见情况 | 用 `open-pr` |
| --- | --- |
| 建议停留在通用规则，脱离项目 | 读取 README / CLAUDE.md / AGENTS.md / docs / wiki；**团队规则优先于** 通用规则 |
| 提醒过一次，下次又忘 | 在聊天里提到 → 询问是否写进仓库的 memory → 下次运行就会应用 |
| 让它修就照评论修 —— 哪怕评论是错的 → 正确的代码被改错 | `/open-pr:fix` 会判断评论是否站得住脚；站不住 → **回复 + 依据**，不改代码 |
| 修复变成一堆 commit、amend、force push，也没有回复 | 每次 `fix` 恰好 **1 个 commit**，不重写历史，推送后每条评论都有回复 |

> [!TIP]
> 最值得留下的一点：不论什么时候运行，流程都一样 —— 先建立规范、按仓库选定输出语言，再记住团队提醒过的事。不会今天一个 AI 腔调，明天又换一个。

## 评审流程

```mermaid
flowchart LR
  A[新 PR] --> B["第 1 轮 · /open-pr:review"]
  B --> C{远端有评审了吗?}
  C -- 还没有 --> D[评审者退回]
  C -- 有 --> E[开发者修 / /open-pr:fix]
  E --> F["第 2 轮 · 再评审一次"]
  F --> G{干净了吗?}
  G -- 是 --> H[LGTM]
  G -- 还没有 --> E
  H --> I[第 3 轮 · 人工领域评审]
```

关于重复评审、worktree，以及 `fix` 之前的守卫：[重复评审 / fix 流程](./docs/zh-Hans/how-it-works.md)。

## 命令

| 命令 | 作用 |
| --- | --- |
| `/open-pr:review <PR_URL>` | 发布恰好 **1** 条评审。不改代码、不 close、不 merge。仓库第一次运行时会顺带完成初始化 |
| `/open-pr:fix <PR_URL>` | 读取 findings → 判断对错 → 修复 → **1** 个 commit → 回复。🔵 / 📝 一律先问过你 |
| `/open-pr:upgrade` | 把本地配置升到当前 schema —— 先给出摘要再询问；你不同意就什么都不写 |
| `/open-pr:clean` | 删除 `review` 检出的 worktree（会先询问）。memory / 设置不受影响 |
| `/open-pr:feedback` | 把 **本插件** 的问题报到它自己的 issue tracker —— 会剥掉一切能识别你仓库的信息，并在发出前先给你看 |

> [!WARNING]
> `fix` 会改动仓库（或 review worktree）里的 **真实代码**。只有当你确实想让它处理这些评论时才运行它。

完整配置：[配置](./docs/zh-Hans/configuration.md)。

## 评审哪些方面

1. **Bug 与逻辑**
2. **安全**
3. **性能**
4. **代码质量**
5. **可维护性与可读性**
6. **框架 / 语言相关** —— 来自该技术栈的模板

详细标准，以及互相冲突时的优先级：[评审哪些方面](./docs/zh-Hans/review-criteria.md)。

## Prompt token 图表

每次运行的平均 token —— 同时覆盖 *happy-case* 与 *bad-case*：

![每次运行的平均 token，按命令 / release 划分](./token-history.svg)

---

想参与贡献？[CONTRIBUTING.md](./CONTRIBUTING.md)。

评审愉快 🥰

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./docs/images/logo/logo-dark.svg?v=moth1">
    <img src="./docs/images/logo/logo.svg?v=moth1" alt="" width="44">
  </picture>
</p>

<p align="center">
  <sub>Logo 文件: <a href="./docs/zh-Hans/logo.md">docs/zh-Hans/logo.md</a></sub>
</p>
