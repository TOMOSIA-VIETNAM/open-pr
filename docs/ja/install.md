# インストール

[← README](../../README.ja.md)

[`gh`](https://cli.github.com/)（GitHub）または [`glab`](https://gitlab.com/gitlab-org/cli)（GitLab）がインストール済み・ログイン済みであること。レビューはそのアカウントで投稿されます。

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash
```

[![Install](../images/install.png)](../images/install.png)

または:

| プラットフォーム | インストール | 使い方 |
| -------- | ------- | --- |
| Claude Code | `/plugin marketplace add TOMOSIA-VIETNAM/open-pr`<br>`/plugin install open-pr@open-pr` | `/open-pr:review <PR_URL>` |
| Codex | `codex plugin marketplace add TOMOSIA-VIETNAM/open-pr`<br>`codex plugin add open-pr@open-pr` | `$open-pr-review <PR_URL>` |
| Gemini CLI | `gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr --auto-update` | `/open-pr-review <PR_URL>` |
| Cursor | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform cursor` | `/open-pr-review <PR_URL>` |
| Antigravity | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform antigravity` | `/open-pr-review <PR_URL>` |

## Update

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --update
```

プラグインを reload したあと、新しいビルドで **schema** が大きく変わっていれば `/open-pr:upgrade` でそのリポジトリの settings を更新します。

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --uninstall
```

[![Uninstall](../images/uninstall.png)](../images/uninstall.png)

---

[再レビュー / fix のフロー](./how-it-works.md) · [設定](./configuration.md)
