# 监视仓库，按请求评审

[← README](../../README.zh-Hans.md)

`/open-pr:watch-review` 会把你运行它的终端变成一个仓库的 watcher。开发者
在 pull request 上评论来请求评审；你的机器注意到后，为该 pull request 打开一个单独的评审
会话，并在需要你处理时通知你。

## 首次运行之前

1. 在该仓库里运行一次 `/open-pr:review <any PR URL>`。评审 memory 尚未建立的仓库会被 watcher
   拒绝，因为不能让多个评审会话同时去建立它。
2. 在仓库内，或在包含多个仓库的工作区目录中运行 `/open-pr:watch-review`：它会列出找到的所有仓库和远程，
   询问要监视哪些（api、web、job 等，可多选），并推荐已设置好评审记忆的仓库。`/open-pr:watch-review owner/api owner/web`（或 PR URL）可直接指定。
   每个托管平台各有一个远程的克隆（GitHub、GitLab、Bitbucket）会按远程分别列出。
   首次运行会询问最多允许多少个评审
   会话同时活跃、用什么来请求评审（`/open-pr` 或提及你）以及你想接收哪些 toast，并把这些都保存在该
   仓库的 `settings.json` 里。
3. 在 Claude Code 上，每个仓库都必须是 trusted workspace，否则它的评审会话无法启动。
   信任不会从父文件夹传递给其中的仓库。watcher 启动时会检查这一点，并逐一列出需要打开一次
   `claude` 的仓库（`cd <repo> && claude`，接受信任提示）。

一个监视器会跟踪你选择的所有仓库；每个仓库保留自己的设置，包括各自的活跃会话上限。

## 请求评审

在 pull request 上评论：

```
/open-pr
/open-pr please look closely at the migration
```

`/open-pr` 后面的任何内容都是关于该看哪里的提示。它被当作数据处理：无法改变评审
的方式、发布的内容，也无法改变任何设置。

不希望在 pull request 上显示工具命令的项目，可以改选“提及我”：以 `@<your login>` 开头的评论
就会请求评审，就像请同事帮忙一样 —— `@minh 帮忙评审一下`。watcher 会读取这样的评论，只有当它确实
是请你评审这个 pull request 时才接手；`@minh 谢谢` 会被忽略。

只有具备 write 权限的人的评论才会触发评审（GitHub：owner、member 或 collaborator；
GitLab：Developer 及以上）。Bitbucket 不允许非管理员读取其他用户的权限，所以在
Bitbucket 上每条 `/open-pr` 评论都会触发评审 —— 如果这很重要，请限制谁可以评论。
插件发布的评论不会触发；你自己的评论会触发，因此一个人可以同时是开发者和评审者。

## 接下来会发生什么

- watcher 会回复该评论 —— "reviewing (commit abc1234)"，使用请求所用的语言 —— 写明它接手请求时
  pull request 所在的提交。当多台机器监视同一个仓库时，这条回复也充当锁：第一条回复获胜，发现已有回复的
  机器会退出，在势均力敌的竞争中落败的机器会删除自己的回复。这在 GitHub、GitLab 和 Bitbucket 上都一样。
- 一个名为 `review <owner>/<repo>#<number>` 的评审会话打开，并运行常规评审。
- 活跃会话数达到上限时，pull request 会在队列里等待。
- 在已有会话的 pull request 上发出新的请求，会 resume 同一个会话，
  因此重新评审会保留之前的上下文。
- 评审是发布还是留作草稿，遵循 `auto_submit_review`，除非你另行告诉
  watcher。没有你，草稿永远不会被发布。
- 会话一旦报告了结果，就归你了：你在其中继续对话时，watcher 不会再就它说任何话，也永远不会读取你在
  那里写的内容。该 pull request 上的下一次请求会把它交还给 watcher。

## 打开会话

屏幕右上角的 toast 会告诉你正在发生什么 —— "Reviewing PR #12"、
"Posted review on PR #12 — 1 🔴 2 🟠"、"LGTM on PR #12"、一份等待中的草稿、一个需要回答的会话 ——
点击 toast 会打开 pull request；鼠标悬停时 toast 保持显示；多个 toast 会依次堆叠；toast 上的 "1h" 按钮会关闭 toast 一小时。
需要你处理时，toast 会显示打开会话的命令。在 macOS 上 watcher 自己绘制 toast，因此不需要通知权限；
在 Linux 上它使用 `notify-send`。每行聊天消息都附带打开会话的命令：

| 平台 | 会话类型 | 打开方式 |
|---|---|---|
| Claude Code | interactive，在后台运行 | `claude attach <id>` |
| Codex | non-interactive | `codex resume <id>` |
| Gemini CLI | non-interactive | `gemini -r <id>` |
| Cursor | non-interactive | `agent --resume <id>` |
| Antigravity | non-interactive | `agy --conversation <id>` |

在 Claude Code 上，需要回答（或需要授权）的会话会一直等到你 attach 进去。在
其他平台上，会话带着问题停下；watcher 问你，然后用
你的回答 resume 该会话。

Claude Code 后台会话要求仓库是 trusted workspace，并且必须在
Claude Code 的 shell sandbox 之外启动。non-interactive 会话使用你为该平台配置的
权限设置；watcher 不授予任何权限。

## 菜单栏（macOS）

watcher 运行期间，macOS 菜单栏上会有一个 `open-pr` 项，并显示进行中的评审数（`open-pr ·2`）。
它的菜单列出：

- 进行中的评审 —— 点击一项打开 pull request，或复制打开其会话的命令；
- 最近十条 toast，这样多条同时到达时也不会遗漏 —— 点击一项打开其 pull request；
- 暂停提醒：30 分钟、1 小时、直到明天 9:00，或重新开启 toast。

最后一个 watcher 停止几分钟后，它会自行消失。Windows 和 Linux 上没有菜单栏：
在聊天中向 watcher 请求同样的操作（`status`、`snooze 1h`）。

## 与 watcher 对话

| 说 | 效果 |
|---|---|
| `status` | 每个 pull request 一行，含状态和打开命令 |
| `snooze 2h` / `resume toasts` | 在此之前本机不显示 toast —— 与 toast 的 "1h" 和菜单栏的暂停提醒是同一个开关；队列照常运行 |
| 某项设置的修改 | 保存到 `settings.json` |
| PR 12 开一个新会话 | 该 PR 的下一次触发会打开新会话 |
| `stop` | 停止监视；已打开的评审会话继续运行 |

## 速率限制

每次轮询会消耗几次 API 调用：GitHub 上是三次；GitLab 和 Bitbucket 上是一次，外加自上次轮询以来每个有更新的
pull request 一次。当托管平台回复该账号已被限速时，watcher 会把轮询间隔加倍（最多 15 分钟），并在下一次
轮询成功后恢复为 `poll_interval_seconds`。

## 设置

保存在 `<data>/<repo>/settings.json` 的 `watch_review` 下：

| 字段 | 默认值 | 含义 |
|---|---|---|
| `max_concurrent` | `5` | 同时活跃的评审会话数（运行中或等待回答） |
| `poll_interval_seconds` | `60` | 多久检查一次 pull request |
| `notify.review_started` | `true` | toast：打开了一个评审会话 |
| `notify.question` | `true` | toast：某个会话需要回答，或失败了 |
| `notify.draft_ready` | `true` | toast：一份草稿评审等待你批准 |
| `notify.posted` | `true` | toast：一份评审已发布，或 LGTM |
| `notify.re_review` | `true` | toast：已有会话被 resume 以重新评审 |
| `trigger` | `/open-pr` | 用什么来请求评审：`/open-pr`，或 `@me` 表示提及 watcher 运行所用的账号 |
