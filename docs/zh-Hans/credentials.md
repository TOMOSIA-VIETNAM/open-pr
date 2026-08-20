# 各平台如何取得 token

[← README](../../README.zh-Hans.md)

插件自己不持有任何凭据：它用你给的 token 所属的账号去读 PR、发评审，所以评审会以你的名义出现。下面每个平台都有各自的取得方式、最小权限，以及一条你可以自己验证的命令。

只做你用到的那个平台。每台机器做一次。

## GitHub

`gh` 会自己申请所需权限，所以这是最短的路径：

```bash
brew install gh          # 或者：https://cli.github.com/
gh auth login            # GitHub.com → HTTPS 或 SSH → 用浏览器登录
gh auth status           # 必须显示 "Logged in to github.com as <你>"
```

那台机器上没有浏览器？改用 token：**Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**，选中你要评审的仓库，然后 `gh auth login --with-token < file`。

| 最小权限（fine-grained） | 用途 |
| --------------------------------- | -------------- |
| Repository access：你要评审的那些仓库 | 把范围收窄 —— 不要选 "All repositories" |
| Contents：**Read** | 把 PR 代码检出到 worktree 里读取 |
| Pull requests：**Read and write** | 读 PR、发评审、回复评论 |
| Metadata：**Read** | GitHub 会一并开启，且无法关闭 |

classic token 则需要 `repo` 这一个 scope —— 范围宽得多，只在没有 fine-grained 可用时才用它。

用一个真实的 PR 验证：

```bash
gh pr view <PR URL>
```

## GitLab

```bash
brew install glab                                  # 或者：https://gitlab.com/gitlab-org/cli
glab auth login --hostname gitlab.com              # 提示时粘贴 PAT
glab auth status
```

在 **User settings → Access tokens → Add new token** 创建 PAT。自建实例做法相同，把自己的 host 写进 `--hostname`。

| 最小权限 | 用途 |
| ------------------ | -------------- |
| Scope `api` | `glab` 需要它来读 MR 和发 note。`read_api` 不够 —— 它发不了 |
| 项目角色：**Developer** 或以上 | 才被允许在 MR 上创建 note |

宁可设一个较短的有效期、到期后换新 token，也不要用永不过期的 token。

验证：

```bash
glab mr view <MR URL>
```

## Bitbucket

Bitbucket Cloud 没有 CLI，所以插件直接调用 REST API，并从环境变量读取凭据。Atlassian 已于 2026-07-28 关闭 app password，剩下的就是 API token。

**第 1 步 —— 创建 token。** 打开 [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)，选 **Create API token with scopes** —— 不是普通的 "Create API token"，那个是给 Jira 和 Confluence 用的，会让 Bitbucket 回 401。app 选 **Bitbucket**，然后勾选下面这些 scope。

| 最小权限 | 用途 |
| ------------------ | -------------- |
| `read:pullrequest:bitbucket` | 读 PR、它的 diff 和评论 |
| `write:pullrequest:bitbucket` | 发评论、回复、resolve thread |
| `read:account` | 知道评审是以哪个账号运行的 |
| `read:repository:bitbucket` | 当 `/diff` 或 `/statuses` 返回 403 时补上 |

token 显示在屏幕上时就复制下来 —— 关掉对话框就再也看不到了。

**第 2 步 —— 设置环境变量。** 两个：`BITBUCKET_EMAIL` 是创建该 token 的 Atlassian 账号邮箱（不是 Bitbucket 用户名），`BITBUCKET_API_TOKEN` 就是那个 token。

二选一。

**方式 A —— 在 shell 里 export。** 适用于所有 agent：Claude Code、Codex、Gemini CLI、Antigravity、Cursor。

用编辑器打开 `~/.zshrc`（zsh，macOS 默认）或 `~/.bashrc`（bash），加两行：

```bash
export BITBUCKET_EMAIL="you@company.com"
export BITBUCKET_API_TOKEN="the-token-you-copied"
```

重新加载并检查：

```bash
source ~/.zshrc          # 或 ~/.bashrc
printenv BITBUCKET_EMAIL
```

用编辑器，不要用 `echo ... >> ~/.zshrc` —— 那会把 token 留在 `~/.zsh_history` 里。

**方式 B —— `~/.claude/settings.json`。** 只适用于 Claude Code，但不用重开终端：

```json
{
  "env": {
    "BITBUCKET_EMAIL": "you@company.com",
    "BITBUCKET_API_TOKEN": "the-token-you-copied"
  }
}
```

改完之后开一个新的 Claude Code 会话 —— 设置在启动时读取。如果只有一个项目需要这个 token，就放进该仓库的 `.claude/settings.local.json`，那个文件已经被 gitignore。

**第 3 步 —— 验证。** 两条命令都不会打印 token：

```bash
curl -sS --fail-with-body -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "https://api.bitbucket.org/2.0/user?fields=nickname"

curl -sS --fail-with-body -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>?fields=full_name"
```

| 结果 | 说明 |
| ------ | ----- |
| 两条都返回 JSON | 好了，能用 |
| 两条都 `401` | token 类型不对（没有 scope），或者那个邮箱不是该 Atlassian 账号的 |
| 第一条失败、第二条成功 | 缺 `read:account` |
| `403` | token 有效，但缺少该 endpoint 需要的 scope |

插件也会读 `BITBUCKET_TOKEN`，用于 repository 或 workspace access token。那类 token 属于仓库而不属于个人，所以 `/user` 会返回 401，评审会以该 token 的名义出现 —— 适合自动化；日常评审还是用上面的 API token 更好。

## push 需要 SSH，不是 token

`/open-pr:review` 只读。`/open-pr:fix` 会 commit 并 push，而这三个平台上 token 都无法 push —— 账号需要一把 SSH key：

| 平台 | 在哪里添加 key |
| ------ | -------------- |
| GitHub | [github.com/settings/keys](https://github.com/settings/keys) |
| GitLab | `https://<host>/-/user_settings/ssh_keys` |
| Bitbucket | [bitbucket.org/account/settings/ssh-keys](https://bitbucket.org/account/settings/ssh-keys/) |

## 如何保管 token

token 在你放它的那个文件里是明文，所以：

- 对存放它的文件执行 `chmod 600` —— `~/.zshrc`、`~/.bashrc` 或 `~/.claude/settings.json`。
- 不要放进仓库的 `.claude/settings.json`，那个文件是可提交的 —— 用 `settings.local.json`。
- 绝不要把它粘到聊天、PR 或 commit message 里。插件需要的是变量的 **名字**，永远不是它的值。
- 只授予刚好够用的最小权限，并设置有效期。怀疑泄露就在创建它的同一个页面吊销并重建 —— 其他什么都不用改。
