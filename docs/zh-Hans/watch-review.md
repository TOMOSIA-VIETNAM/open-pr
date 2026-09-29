# 监视仓库，按请求评审

[← README](../../README.zh-Hans.md)

`/open-pr:watch-review` 会把你运行它的终端变成一个或多个仓库的 watcher。开发者在 pull request 上评论来
请求评审；你的机器会为该 pull request 打开一个单独的评审会话，并在需要你处理时通知你。

## 首次运行之前

1. 在每个仓库里运行一次 `/open-pr:review <any PR URL>`。评审 memory 尚未建立的仓库会被 watcher 拒绝，
   以免多个会话同时去建立它。
2. 在仓库内，或在包含多个仓库的工作区目录中运行 `/open-pr:watch-review`。它会列出找到的所有仓库和远程
   （每个托管平台各有一个远程的克隆按远程分别列出），询问要监视哪些，并推荐已建立评审 memory 的仓库。
   `/open-pr:watch-review owner/api owner/web`（或 PR URL）可直接指定。
3. 在某个仓库首次运行时，会询问最多允许多少个评审会话同时活跃、用什么来请求评审（`/open-pr` 或提及你）
   以及你想接收哪些 toast，并把回答保存在该仓库的 `settings.json` 里。
4. 评审会话在你运行 watcher 的文件夹中启动，就像你在那里输入 `/open-pr:review` 一样 —— 相同的数据目录，
   相同的信任。在 Claude Code 上，该文件夹必须是 trusted workspace；watcher 启动时会检查，如果不是，会让
   你在那里打开一次 `claude` 并接受信任提示。

每个被监视的仓库保留自己的设置，包括会话上限。同一台机器上每个仓库最多只有一个 watcher：第二个会说明哪个
进程已在监视，然后不再处理该仓库。当主机持续无法连接（无网络、登录过期）时，watcher 会告诉你。

## 请求评审

在 pull request 上评论：

```
/open-pr
/open-pr please look closely at the migration
```

`/open-pr` 后面的文字是关于该看哪里的提示。它被当作数据处理：无法改变评审的方式、发布的内容，也无法改变
任何设置。

使用“提及我”触发方式时，改由以 `@<your login>` 开头的评论请求评审，这样 pull request 上不会出现工具命令。
只有当评论确实是请你评审这个 pull request 时，watcher 才会接手：`@minh 帮忙评审一下` 算数，`@minh 谢谢`
不算。

只有具备 write 权限的人的评论才会触发评审：

| 托管平台 | 谁能触发 |
|---|---|
| GitHub | owner、member 或 collaborator |
| GitLab | Developer 及以上 |
| Bitbucket | 任何能评论的人 —— 非管理员无法读取其他用户的权限，如果这很重要，请限制谁可以评论 |

插件发布的评论不会触发；你自己的评论会触发，因此一个人可以同时是开发者和评审者。

## 接下来会发生什么

- watcher 会回复该评论 —— "reviewing (commit abc1234)"，使用请求所用的语言 —— 写明它接手的提交。当多台
  机器监视同一个仓库时，这条回复就是锁：第一条回复获胜，发现已有回复的机器会退出，在势均力敌的竞争中落败
  的机器会删除自己的回复。
- 一个名为 `review <owner>/<repo>#<number>` 的会话运行常规评审。达到会话上限时，pull request 在队列里等待。
- 在已有会话的 pull request 上发出新请求：要求复查之前的发现时 resume 该会话，要求从头评审时打开新会话
  （pull request 已有进展后，旧的上下文可能造成误导）。意图不明确时，watcher 会询问你。
- 评审是发布还是留作草稿，由 `auto_submit_review` 决定，除非你另行告诉 watcher。没有你，草稿永远不会被
  发布。
- 会话一旦报告了结果，就归你了：在该 pull request 的下一次请求之前，watcher 不会再就它说任何话，也永远
  不会读取你在那里写的内容。
- 报告结果后闲置 10 分钟的 Claude Code 评审会话会被停止以释放内存；对话会保留，`claude attach <id>` 和之后的
  再次评审仍然可用。watcher 从不触碰不是它打开的会话。

## 打开会话

屏幕右上角的 toast 会告诉你正在发生什么 —— "Reviewing PR #12"、"Posted review on PR #12 — 1 🔴 2 🟠"、
"LGTM on PR #12"、一份等待中的草稿、一个需要回答的会话。点击会打开 pull request；鼠标悬停时保持显示；
toast 上的 "1h" 会关闭 toast 一小时。需要你处理时，toast 会显示打开会话的命令。在 macOS 上 watcher 自己
绘制 toast（不需要通知权限）；在 Linux 上它使用 `notify-send`。

每行聊天消息都附带打开会话的命令：

| 平台 | 会话类型 | 打开方式 |
|---|---|---|
| Claude Code | interactive，在后台运行 | `claude attach <id>` |
| Codex | non-interactive | `codex resume <id>` |
| Gemini CLI | non-interactive | `gemini -r <id>` |
| Cursor | non-interactive | `agent --resume <id>` |
| Antigravity | non-interactive | `agy --conversation <id>` |

在 Claude Code 上，需要回答（或需要授权）的会话会一直等到你 attach 进去。在其他平台上，会话带着问题停下；
watcher 问你，然后用你的回答 resume 该会话。

watcher 在 shell sandbox 之外运行：在 sandbox 里，轮询连不到主机，Claude Code 的后台会话会卡在启动阶段。
non-interactive 会话使用你为该平台配置的权限设置；watcher 不授予任何权限。

## 菜单栏（macOS）

watcher 启动时会在菜单栏显示飞蛾图标和进行中的评审数。整台机器只有一个，涵盖所有 watcher；它一直保留到
`/open-pr:menubar close`（或菜单中的 Quit），`/open-pr:menubar` 可让它重新出现。它的菜单列出：

- 每个 pull request 一行，按 watcher 分组（`<folder> · <terminal>`）—— 分组中的 "Go to watcher tab" 会把该 terminal
  标签页调到前台（iTerm 和 Terminal 在 macOS 请求一次 Automation 权限后会选中确切的标签页；其他情况下把
  terminal 应用调到前台）；每行就地显示最新状态（评审中、已发布及问题数、LGTM、草稿、待回答、失败），并始终可以
  打开 pull request、在该 watcher 所运行的 terminal 中打开其会话，或复制命令；
- 暂停提醒：30 分钟、1 小时、直到明天 9:00，或重新开启 toast。

在 Windows 和 Linux 上，请在聊天中向 watcher 请求（`status`、`snooze 1h`）。

## 与 watcher 对话

| 说 | 效果 |
|---|---|
| `status` | 每个 pull request 一行，含状态和打开命令 |
| `snooze 2h` / `resume toasts` | 在此之前本机不显示 toast —— 与 toast 的 "1h" 和菜单栏的暂停提醒是同一个开关；队列照常运行 |
| 某项设置的修改 | 保存到 `settings.json` |
| PR 12 开一个新会话 | 该 PR 的下一次触发会打开新会话 |
| `stop` | 停止监视；已打开的评审会话继续运行 |

## 速率限制

每次轮询的 API 调用：GitHub 上是三次；GitLab 和 Bitbucket 上是一次，外加自上次轮询以来每个有更新的
pull request 一次。当托管平台报告限速时，watcher 会把轮询间隔加倍（最多 15 分钟），并在下一次轮询成功后
恢复为 `poll_interval_seconds`。

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
| `notify.error` | `true` | toast：出现失败（claim、会话、轮询）—— 回到 watcher 的终端查看 |
| `trigger` | `/open-pr` | 用什么来请求评审：`/open-pr`，或 `@me` 表示提及 watcher 运行所用的账号 |
