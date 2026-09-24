# 配置

[← README](../../README.zh-Hans.md)

插件为每个仓库保存的全部内容，以及在哪里修改它们。

## 数据放在哪里

所有仓库的 memory、settings 和评审用 worktree 都放在你只需选一次的 **一个数据目录** 里，位于所有仓库之外 —— 不用加 `.gitignore`，`git status` 里也看不到。

```
~/workspace/notebooks/review/   ← 数据目录（你来选）
├── .git                        学到内容的本地历史
├── repo-backend/               memory + settings + worktrees/
└── repo-frontend/
~/workspace/repo-backend/       ← 不受影响
```

尚未设置数据目录时，第一条命令会询问路径。推荐的是仓库外面紧邻那一层目录里的 `notebooks/review/` —— 对 `~/workspace/repo-backend` 来说就是 `~/workspace/notebooks/review/` —— 也可以输入任意路径。仓库里已有的 `notebooks/review/` 会被 **复制** 过去（不含 worktree），原目录保持不动。选择保存在 `~/.config/open-pr/config.json` 的 `data_dir` 里 —— 想换位置就编辑这个文件。

你站在哪里不影响数据放在哪里。站在装着多个仓库的 workspace 里，仍然可以一次运行评审 **跨仓库** 的 PR（一个接一个，不是并行）：

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` 可以从 workspace 运行（只要那个仓库处在 PR 的分支上，它就能找到）—— 也可以从 `review` 已经建好的 worktree 里运行；在那里 URL 是可选的，因为会话已经知道是哪个 PR。

## 命令

| 命令 | 你站在哪里 | 它写什么 |
| --- | --- | --- |
| `/open-pr:review` | 装着该仓库的 workspace，或仓库里面 —— 靠 `git remote` 找到它 | PR 上的评论 + `<data>/<repo>/` 下的 memory |
| `/open-pr:fix` | 在该仓库里 / 装着它的 workspace 里 —— 但 **仓库必须处在 PR 的分支上** | 仓库里的真实代码 + PR 上的回复 |
| `/open-pr:upgrade` | 任意位置 —— 数据目录里的所有仓库，或你点名的那些 | `<data>/<repo>/settings.json` |
| `/open-pr:clean` | 任意位置 | 什么都不写 —— 只删除 `<data>/*/worktrees/*` |
| `/open-pr:feedback` | 任意位置 | 本地什么都不写 —— 在你批准文本之后，往插件自己的 tracker 发一条 issue |

## 设置

下文的 `<data>` 指数据目录。学到的一切都索引在 `<data>/<repo>/memory.md` 里（目录式 —— token 便宜，但全貌仍在）。细节存放在 `<data>/<repo>/memories/*.md`。

> [!NOTE]
> 整个数据目录由一个 **独立的本地 git** 管理 —— 没有 remote，永远不会被 push。你可以追溯 memory 从上一次评审到这一次是怎么变的。

团队规则以普通文字写进 `ALWAYS_RULE.md`（默认为空）。其余一切都在 `settings.json` 里：

| 字段 | 含义 | 默认值 |
| --- | --- | --- |
| `shared.chat_language` | 聊天中使用的语言 | 自动判别 |
| `shared.output_language` | 发布到 PR 上的语言 | 初次询问后保存 |
| `review.auto_submit_review` | `true` = 立即发布，`false` = 先留给你过目 —— 平台有草稿功能时是 PR 上的草稿；Bitbucket 没有草稿，就留在聊天里，PR 上保持空白 | `false` |
| `review.auto_resolve_fixed_findings` | finding 修好后自动 resolve 对应 thread | `false` |
| `review.post_lgtm` | 没有任何 finding 的干净结果也发到 PR 上；`false` 则只在聊天里显示 | `true` |
| `review.doctor_schedule` | 隔多久重读一次规范文档：`"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"` |
| `review.review_ci_status` | 是否提及失败的 CI（只提醒，绝不要求你修） | 存在 CI ⇒ `true` |
| `review.many_files_threshold` | PR 文件数超过这个值 ⇒ 提醒过大 | `30` |
| `review.big_file_threshold_kb` | diff 大于这个值的文件不纳入第一次读取 | `20` |
| `fix.decline_needs_confirmation` | 拒绝一条 finding 之前先询问 | `true` |
| `fix.auto_push` | commit 之后自动 push | `false` |

---

[安装](./install.md) · [重复评审 / fix 流程](./how-it-works.md) · [评审哪些方面](./review-criteria.md)
