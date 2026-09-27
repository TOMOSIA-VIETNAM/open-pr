# リポジトリを監視し、依頼があればレビューする

[← README](../../README.ja-JP.md)

`/open-pr:watch-review` は、実行したターミナルを 1 つのリポジトリの watcher にします。開発者は
pull request にコメントしてレビューを依頼します。あなたのマシンがそれに気づき、その pull request
専用のレビューセッションを開き、あなたの対応が必要なときに知らせます。

## 初回実行の前に

1. そのリポジトリで一度 `/open-pr:review <any PR URL>` を実行します。レビュー memory が
   まだセットアップされていないリポジトリを watcher は拒否します。複数のレビューセッションが
   同時にセットアップしてはいけないためです。
2. リポジトリ内、または複数のリポジトリを含むワークスペースで `/open-pr:watch-review` を実行します。
   見つかったリポジトリとリモート（api、web、job など）を一覧にして、監視するものを尋ねます。いくつでも選べ、
   レビューメモリ設定済みのものが推奨されます。`/open-pr:watch-review owner/api owner/web`（または PR の URL）で直接指定もできます。ホストごとにリモートを持つ
   クローン（GitHub、GitLab、Bitbucket）はリモートごとに表示されます。
   初回は、同時にアクティブにできる
   レビューセッションの数と、受け取りたい通知を尋ね、両方をそのリポジトリの
   `settings.json` に保存します。

1 つのウォッチャーが選んだすべてのリポジトリを監視します。各リポジトリは自分の設定（アクティブなセッション数の上限を含む）を持ちます。

## レビューを依頼する

pull request にコメントします:

```
/open-pr
/open-pr please look closely at the migration
```

`/open-pr` の後に書いたものは、どこを見るべきかのヒントです。データとして扱われるため、
レビューのやり方、投稿される内容、どの設定も変えられません。

レビューを起動するのは write 権限を持つ人のコメントだけです（GitHub: owner・member・collaborator、
GitLab: Developer 以上）。Bitbucket では管理者以外が他ユーザーの権限を読めないため、
Bitbucket ではすべての `/open-pr` コメントがレビューを起動します — 問題になるならコメントできる人を制限してください。
watcher は自身が動いているアカウントが書いたコメントを無視します。

## その後に起きること

- コメントに 👀 リアクションが付きます（リアクションのない Bitbucket を除く）。
- `review <owner>/<repo>#<number>` という名前のレビューセッションが開き、通常のレビューを実行します。
- アクティブなセッション数が上限に達すると、pull request はキューで待ちます。
- すでにセッションがある pull request に新しい `/open-pr` コメントが付くと、その同じセッションを resume します。
  そのため再レビューは前回のコンテキストを引き継ぎます。
- レビューを公開するかドラフトのままにするかは、watcher に別の指示をしない限り
  `auto_submit_review` に従います。ドラフトがあなた抜きで公開されることはありません。

## セッションを開く

すべての通知とすべてのチャット行に、そのセッションを開くコマンドが付きます:

| プラットフォーム | セッションの種類 | 開き方 |
|---|---|---|
| Claude Code | interactive、バックグラウンドで実行 | `claude attach <id>` |
| Codex | non-interactive | `codex resume <id>` |
| Gemini CLI | non-interactive | `gemini -r <id>` |
| Cursor | non-interactive | `agent --resume <id>` |
| Antigravity | non-interactive | `agy --conversation <id>` |

Claude Code では、回答（または権限の許可）が必要なセッションは、あなたが attach するまで待ちます。
他のプラットフォームでは、セッションは質問を残して停止します。watcher があなたに尋ね、
その回答でセッションを resume します。

Claude Code のバックグラウンドセッションには、リポジトリが trusted workspace であることが必要で、
Claude Code の shell sandbox の外で起動しなければなりません。non-interactive セッションは、
そのプラットフォームであなたが設定した権限設定を使います。watcher は権限を一切付与しません。

## watcher と話す

| 言うこと | 効果 |
|---|---|
| `status` | pull request ごとに 1 行、状態と開くコマンド付き |
| `snooze 2h` | その時刻まで通知なし。キューは動き続ける |
| 設定の変更 | `settings.json` に保存 |
| PR 12 は新しいセッションで | その PR の次の起動で新しいセッションを開く |
| `stop` | 監視を停止。開いているレビューセッションは動き続ける |

## Setting

`<data>/<repo>/settings.json` の `watch_review` 以下に保存されます:

| field | 既定値 | 意味 |
|---|---|---|
| `max_concurrent` | `5` | 同時にアクティブなレビューセッション数（実行中または回答待ち） |
| `poll_interval_seconds` | `60` | pull request を確認する間隔 |
| `notify.review_started` | `true` | レビューセッションが開いた |
| `notify.question` | `true` | セッションが回答を必要としている、または失敗した |
| `notify.draft_ready` | `true` | ドラフトのレビューがあなたの承認を待っている |
| `notify.posted` | `true` | レビューが投稿された |
| `notify.re_review` | `true` | 既存のセッションが再レビューのために resume された |
| `snooze_until` | `null` | この UTC 時刻まで通知をオフにする |
