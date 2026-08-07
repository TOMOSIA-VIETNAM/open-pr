# ベンダーごとのトークン取得

[← README](../../README.ja.md)

プラグイン自身は認証情報を持ちません。トークンを渡したアカウントとして PR を読み、レビューを投稿するので、
レビューはあなたの名前で表示されます。ベンダーごとの取得手順、最小権限、自分で確認するコマンドを以下に
まとめます。

使うベンダーの節だけ実施してください。1 台につき 1 回で済みます。

## GitHub

`gh` が必要な権限を自分で要求するので、これが最短です。

```bash
brew install gh          # または: https://cli.github.com/
gh auth login            # GitHub.com → HTTPS か SSH → Login with a web browser
gh auth status           # "Logged in to github.com as <あなた>" と出れば成功
```

ブラウザが使えない環境ではトークンを使います。**Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate new token** でレビュー対象のリポジトリを選び、
`gh auth login --with-token < file` を実行します。

| 最小権限（fine-grained） | 用途 |
| ------------------------ | ---- |
| Repository access: レビューするリポジトリ | 範囲を狭く保つため。"All repositories" は選ばない |
| Contents: **Read** | PR のコードを worktree にチェックアウトして読む |
| Pull requests: **Read and write** | PR を読み、レビューを投稿し、コメントに返信する |
| Metadata: **Read** | GitHub が同時に有効化し、外せません |

classic token なら `repo` スコープ 1 つで同等ですが、権限がかなり広くなるため fine-grained が使えない
場合に限ります。

実際の PR で確認します。

```bash
gh pr view <PR の URL>
```

## GitLab

```bash
brew install glab                                  # または: https://gitlab.com/gitlab-org/cli
glab auth login --hostname gitlab.com              # 聞かれたら PAT を貼る
glab auth status
```

PAT は **User settings → Access tokens → Add new token** で作成します。セルフホストでも同じ手順で、
`--hostname` を自分のホストに変えるだけです。

| 最小権限 | 用途 |
| -------- | ---- |
| スコープ `api` | `glab` が MR を読み、ノートを投稿するために必要。`read_api` では投稿できず不足 |
| プロジェクトのロール: **Developer** 以上 | MR にノートを作成できる |

有効期限は短くし、切れたら作り直す運用が、無期限のトークンより安全です。

確認します。

```bash
glab mr view <MR の URL>
```

## Bitbucket

Bitbucket Cloud には CLI がないため、プラグインは REST API を直接呼び、認証情報を環境変数から読みます。
App password は 2026-07-28 に Atlassian が完全に停止したので、API token だけが残る手段です。

**手順 1 — トークンを作る。** [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
を開き、**Create API token with scopes** を選びます。通常の "Create API token" は Jira と Confluence 向けで、
Bitbucket では 401 が返ります。アプリに **Bitbucket** を選び、以下のスコープを付けます。

| 最小権限 | 用途 |
| -------- | ---- |
| `read:pullrequest:bitbucket` | PR、diff、コメントの読み取り |
| `write:pullrequest:bitbucket` | コメント投稿、返信、スレッドの解決 |
| `read:account` | どのアカウントとして動いているかの取得 |
| `read:repository:bitbucket` | `/diff` や `/statuses` が 403 を返す場合に追加 |

トークンは表示されている間にコピーします。ダイアログを閉じると二度と見られません。

**手順 2 — 環境変数を設定する。** 2 つです。`BITBUCKET_EMAIL` はトークンを作成した Atlassian アカウントの
メールアドレス（Bitbucket のユーザー名ではありません）、`BITBUCKET_API_TOKEN` がトークンです。

| 置き場所 | 向いている場合 |
| -------- | -------------- |
| `~/.claude/settings.json` の `env` ブロック | すべての Claude Code セッションで有効、ターミナルの再起動も不要 — 推奨 |
| `~/.zshrc` / `~/.bashrc` | 通常のターミナルでも使いたい |
| リポジトリの `.claude/settings.local.json` | 1 つのプロジェクトだけで必要な場合。このファイルは既に gitignore 済み |

```json
{
  "env": {
    "BITBUCKET_EMAIL": "you@company.com",
    "BITBUCKET_API_TOKEN": "コピーしたトークン"
  }
}
```

`~/.claude/settings.json` を編集したら、新しい Claude Code セッションを開きます。設定は起動時に読まれます。

**手順 3 — 確認する。** どちらのコマンドもトークンを出力しません。

```bash
curl -sS --fail-with-body -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "https://api.bitbucket.org/2.0/user?fields=nickname"

curl -sS --fail-with-body -u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN" \
  "https://api.bitbucket.org/2.0/repositories/<workspace>/<repo>?fields=full_name"
```

| 結果 | 意味 |
| ---- | ---- |
| どちらも JSON が返る | 設定完了 |
| どちらも `401` | トークンの種類が違う（スコープなし）か、メールが Atlassian アカウントのものでない |
| 1 つ目が失敗し 2 つ目は成功 | `read:account` が足りない |
| `403` | トークンは有効だが、そのエンドポイントのスコープが足りない |

プラグインは repository / workspace access token 用に `BITBUCKET_TOKEN` も読みます。こちらは人ではなく
リポジトリに属するため `/user` は 401 を返し、レビューはトークン名で表示されます。自動化向けで、日常の
レビューには上の API token が適しています。

## push にはトークンではなく SSH が必要

`/open-pr:review` は読むだけです。`/open-pr:fix` は commit して push し、3 つのベンダーいずれもトークンでは
push できません。アカウントに SSH 鍵が必要です。

| ベンダー | 鍵の登録先 |
| -------- | ---------- |
| GitHub | [github.com/settings/keys](https://github.com/settings/keys) |
| GitLab | `https://<host>/-/user_settings/ssh_keys` |
| Bitbucket | [bitbucket.org/account/settings/ssh-keys](https://bitbucket.org/account/settings/ssh-keys/) |

## トークンを安全に保つ

トークンは置いたファイルの中で平文のままなので、次を守ります。

- 編集後に `chmod 600 ~/.claude/settings.json`。
- リポジトリの `.claude/settings.json` には置かない（コミットされ得る）。`settings.local.json` を使う。
- チャット、PR、コミットメッセージに貼らない。プラグインが必要なのは変数の**名前**だけで、値は不要です。
- 動く範囲で最も狭い権限にし、有効期限を付ける。漏洩が疑われたら作成したページで revoke して作り直せば
  済み、ほかにやり直す作業はありません。
