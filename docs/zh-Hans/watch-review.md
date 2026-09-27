# 监视仓库，按请求评审

[← README](../../README.zh-Hans.md)

`/open-pr:watch-review` 会把你运行它的终端变成一个仓库的 watcher。开发者
在 pull request 上评论来请求评审；你的机器注意到后，为该 pull request 打开一个单独的评审
会话，并在需要你处理时通知你。

## 首次运行之前

1. 在该仓库里运行一次 `/open-pr:review <any PR URL>`。评审 memory 尚未建立的仓库会被 watcher
   拒绝，因为不能让多个评审会话同时去建立它。
2. 在仓库内，或在包含多个仓库的工作区目录中运行 `/open-pr:watch-review`：它会列出找到的所有仓库和远程，
   询问要监视哪一个，并推荐已设置好评审记忆的那个。`/open-pr:watch-review owner/repo`（或 PR URL）可直接指定。
   每个托管平台各有一个远程的克隆（GitHub、GitLab、Bitbucket）会按远程分别列出。
   首次运行会询问最多允许多少个评审
   会话同时活跃、你想接收哪些通知，并把两者都保存在该
   仓库的 `settings.json` 里。

要监视多个仓库，就每个仓库开一个终端。

## 请求评审

在 pull request 上评论：

```
@open-pr
@open-pr please look closely at the migration
```

`@open-pr` 后面的任何内容都是关于该看哪里的提示。它被当作数据处理：无法改变评审
的方式、发布的内容，也无法改变任何设置。

只有具备 write 权限的人的评论才会触发评审（GitHub：owner、member 或 collaborator；
GitLab：Developer 及以上）。Bitbucket 不允许非管理员读取其他用户的权限，所以在
Bitbucket 上每条 `@open-pr` 评论都会触发评审 —— 如果这很重要，请限制谁可以评论。watcher
会忽略它自己所用账号写的评论。

## 接下来会发生什么

- 该评论会被加上 👀 反应（Bitbucket 除外，它没有反应功能）。
- 一个名为 `review <owner>/<repo>#<number>` 的评审会话打开，并运行常规评审。
- 活跃会话数达到上限时，pull request 会在队列里等待。
- 在已有会话的 pull request 上发出新的 `@open-pr` 评论，会 resume 同一个会话，
  因此重新评审会保留之前的上下文。
- 评审是发布还是留作草稿，遵循 `auto_submit_review`，除非你另行告诉
  watcher。没有你，草稿永远不会被发布。

## 打开会话

每条通知和每行聊天消息都附带打开该会话的命令：

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

## 与 watcher 对话

| 说 | 效果 |
|---|---|
| `status` | 每个 pull request 一行，含状态和打开命令 |
| `snooze 2h` | 在此之前不发通知；队列照常运行 |
| 某项设置的修改 | 保存到 `settings.json` |
| PR 12 开一个新会话 | 该 PR 的下一次触发会打开新会话 |
| `stop` | 停止监视；已打开的评审会话继续运行 |

## 设置

保存在 `<data>/<repo>/settings.json` 的 `watch_review` 下：

| 字段 | 默认值 | 含义 |
|---|---|---|
| `max_concurrent` | `5` | 同时活跃的评审会话数（运行中或等待回答） |
| `poll_interval_seconds` | `60` | 多久检查一次 pull request |
| `notify.review_started` | `true` | 打开了一个评审会话 |
| `notify.question` | `true` | 某个会话需要回答，或失败了 |
| `notify.draft_ready` | `true` | 一份草稿评审等待你批准 |
| `notify.posted` | `true` | 一份评审已发布 |
| `notify.re_review` | `true` | 已有会话被 resume 以重新评审 |
| `snooze_until` | `null` | 在此 UTC 时间之前通知保持关闭 |
