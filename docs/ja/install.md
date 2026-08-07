# インストール

[← README](../../README.ja.md)

[`gh`](https://cli.github.com/)（GitHub）または [`glab`](https://gitlab.com/gitlab-org/cli)（GitLab）がインストール済み・ログイン済みであること。レビューはそのアカウントで投稿されます。

## 推奨: All で入れる

1 本のコマンド — 全プラットフォームへ入れます（Claude Code / Cursor / Codex / Gemini CLI / Antigravity）:

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --platform all
```

> [!TIP]
> **All** を使う。1 プラットフォームだけにしたいときだけ下の表へ。

## Claude Code

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

## プラットフォーム別（任意）

| プラットフォーム | インストール | 使い方 |
| ---------------- | ------------ | ------ |
| Cursor | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform cursor` | `/open-pr-review <PR_URL>` |
| Codex | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform shared` | `$open-pr-review <PR_URL>` |
| Gemini CLI | `gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr` | `/review <PR_URL>` |
| Antigravity | `curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh \| bash -s -- --platform antigravity` | `/open-pr-review <PR_URL>` |

パイプを使わない場合:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
~/.open-pr/scripts/install-local.sh
```

## アンインストール

まず curl のアンインストーラ（`install.sh` が入れたものを外す）:

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --uninstall
```

| プラットフォーム | 個別コマンド（必要なとき） |
| ---------------- | -------------------------- |
| Claude Code | `/plugin uninstall open-pr@open-pr` |
| Gemini CLI | `gemini extensions uninstall open-pr` |

## 更新

| プラットフォーム | コマンド |
| ---------------- | -------- |
| Claude Code | `/plugin update open-pr@open-pr` · `/reload-plugins` · `/open-pr:upgrade` |
| Gemini CLI | `gemini extensions update open-pr` |
| それ以外 | `~/.open-pr/scripts/install-local.sh --update` |

全フラグ: `~/.open-pr/scripts/install-local.sh --help`

---

[仕組み](./how-it-works.md) · [設定](./configuration.md)
