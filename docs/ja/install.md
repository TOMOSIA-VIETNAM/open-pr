# インストール

[`gh`](https://cli.github.com/)（GitHub）または [`glab`](https://gitlab.com/gitlab-org/cli)（GitLab）
がインストール済み・ログイン済みであること — レビューはそのアカウントで投稿されます。

| プラットフォーム | インストール | 使い方 | 状態 |
| ---------------- | ------------ | ------ | ---- |
| Claude Code | `/plugin marketplace add TOMOSIA-VIETNAM/open-pr`<br>`/plugin install open-pr@open-pr` | `/open-pr:review <PR URL>` | テスト済み |
| Cursor | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform cursor` | `/open-pr-review <PR URL>` | 未テスト |
| Codex | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform shared` | `$open-pr-review <PR URL>` | 未テスト |
| Gemini CLI | `gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr` | `/review <PR URL>` | 未テスト |
| Antigravity | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform antigravity` | `/open-pr-review <PR URL>` | 未テスト |
| すべて | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform all` | 上記と同じ | — |

`未テスト` = インストールはできるが、まだ誰も実際のレビューを流していない。

パイプを使わない場合:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
~/.open-pr/scripts/install-local.sh
```

## アンインストール

| プラットフォーム | コマンド |
| ---------------- | -------- |
| Claude Code | `/plugin uninstall open-pr@open-pr` |
| Gemini CLI | `gemini extensions uninstall open-pr` |
| それ以外 | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --uninstall` |

## 更新

| プラットフォーム | コマンド |
| ---------------- | -------- |
| Claude Code | `/plugin update open-pr@open-pr` · `/reload-plugins` · `/open-pr:upgrade` |
| Gemini CLI | `gemini extensions update open-pr` |
| それ以外 | `git -C ~/.open-pr pull` |

全フラグ: `~/.open-pr/scripts/install-local.sh --help` · [仕組み](./how-it-works.md) ·
[設定](./configuration.md)
