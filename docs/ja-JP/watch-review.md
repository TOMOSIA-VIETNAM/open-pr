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
   レビューセッションの数、レビューを依頼する方法（`/open-pr` またはあなたへのメンション）、受け取りたい
   トーストを尋ね、それらをそのリポジトリの `settings.json` に保存します。
3. Claude Code では、各リポジトリが trusted workspace でなければならず、そうでないとレビューセッションを
   起動できません。trust は親フォルダーから中のリポジトリへは引き継がれません。watcher は起動時にこれを
   確認し、一度 `claude` を開く必要があるリポジトリを一つずつ示します（`cd <repo> && claude` を実行し、
   trust の確認を承認します）。

1 つのウォッチャーが選んだすべてのリポジトリを監視します。各リポジトリは自分の設定（アクティブなセッション数の上限を含む）を持ちます。

## レビューを依頼する

pull request にコメントします:

```
/open-pr
/open-pr please look closely at the migration
```

`/open-pr` の後に書いたものは、どこを見るべきかのヒントです。データとして扱われるため、
レビューのやり方、投稿される内容、どの設定も変えられません。

pull request にツールのコマンドを出したくないプロジェクトは、代わりに「自分へのメンション」を選べます。
`@<your login>` で始まるコメントが、同僚に頼むようにレビューを依頼します — `@minh レビューお願いします`。
watcher はそのコメントを読み、この pull request のレビューを本当にあなたに頼んでいる場合だけ引き受けます。
`@minh ありがとう` は無視されます。

レビューを起動するのは write 権限を持つ人のコメントだけです（GitHub: owner・member・collaborator、
GitLab: Developer 以上）。Bitbucket では管理者以外が他ユーザーの権限を読めないため、
Bitbucket ではすべての `/open-pr` コメントがレビューを起動します — 問題になるならコメントできる人を制限してください。
プラグインが投稿したコメントでは起動しません。自分のコメントでは起動するので、1 人で開発者とレビュアーを兼ねられます。

## その後に起きること

- watcher がコメントに返信します — "reviewing (commit abc1234)"、依頼と同じ言語で — 依頼を引き受けた
  時点の pull request のコミットを示します。複数のマシンが同じリポジトリを監視している場合、この返信は
  ロックも兼ねます。最初の返信が勝ち、すでに返信があるのを見つけたマシンは手を引き、僅差の競争に負けたマシンは
  自分の返信を削除します。これは GitHub、GitLab、Bitbucket で同じように動作します。
- `review <owner>/<repo>#<number>` という名前のレビューセッションが開き、通常のレビューを実行します。
- アクティブなセッション数が上限に達すると、pull request はキューで待ちます。
- すでにセッションがある pull request に新しい依頼が来ると、その同じセッションを resume します。
  そのため再レビューは前回のコンテキストを引き継ぎます。
- レビューを公開するかドラフトのままにするかは、watcher に別の指示をしない限り
  `auto_submit_review` に従います。ドラフトがあなた抜きで公開されることはありません。
- 結果を報告したセッションは、あなたのものです。あなたがそのセッションで会話を続けていても watcher は
  それについて何も言わず、そこであなたが書いた内容を読むこともありません。その pull request への次の依頼で
  watcher に戻ります。

## セッションを開く

画面右上のトーストが、いま何が起きているかを知らせます — "Reviewing PR #12"、
"Posted review on PR #12 — 1 🔴 2 🟠"、"LGTM on PR #12"、承認待ちのドラフト、回答が必要なセッション —
トーストをクリックすると pull request が開き、マウスを乗せている間は表示が続き、複数のトーストは縦に積み重なります。トーストの "1h" ボタンで 1 時間トーストをオフにできます。
対応が必要なときは、セッションを開くコマンドが表示されます。macOS では watcher が自分でトーストを描画するため、通知の権限は
不要です。Linux では `notify-send` を使います。すべてのチャット行にセッションを開くコマンドが付きます:

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

## メニューバー（macOS）

watcher の実行中は、macOS のメニューバーに `open-pr` の項目が表示され、進行中のレビュー数が付きます
（`open-pr ·2`）。そのメニューには次の内容が並びます:

- 進行中のレビュー — クリックすると pull request が開きます。そのセッションを開くコマンドをコピーすることもできます。
- 直近 10 件のトースト。複数が同時に届いても見逃しません — クリックするとその pull request が開きます。
- スヌーズ: 30 分、1 時間、明日 9:00 まで、またはトーストを再びオンにする。

最後の watcher が停止してから数分後に自動で消えます。Windows と Linux にはメニューバーはありません。
同じことはチャットで watcher に頼んでください（`status`、`snooze 1h`）。

## watcher と話す

| 言うこと | 効果 |
|---|---|
| `status` | pull request ごとに 1 行、状態と開くコマンド付き |
| `snooze 2h` / `resume toasts` | その時刻までこのマシンでトーストなし — トーストの "1h" やメニューバーのスヌーズと同じスイッチ。キューは動き続ける |
| 設定の変更 | `settings.json` に保存 |
| PR 12 は新しいセッションで | その PR の次の起動で新しいセッションを開く |
| `stop` | 監視を停止。開いているレビューセッションは動き続ける |

## レート制限

ポーリング 1 回ごとに数回の API 呼び出しがかかります。GitHub では 3 回、GitLab と Bitbucket では 1 回に加えて、
前回のポーリング以降に更新された pull request 1 件ごとに 1 回です。ホストがアカウントのレート制限を返すと、watcher は
間隔を 2 倍にし（最大 15 分）、次にポーリングが成功した後で `poll_interval_seconds` に戻ります。

## Setting

`<data>/<repo>/settings.json` の `watch_review` 以下に保存されます:

| field | 既定値 | 意味 |
|---|---|---|
| `max_concurrent` | `5` | 同時にアクティブなレビューセッション数（実行中または回答待ち） |
| `poll_interval_seconds` | `60` | pull request を確認する間隔 |
| `notify.review_started` | `true` | トースト: レビューセッションが開いた |
| `notify.question` | `true` | トースト: セッションが回答を必要としている、または失敗した |
| `notify.draft_ready` | `true` | トースト: ドラフトのレビューがあなたの承認を待っている |
| `notify.posted` | `true` | トースト: レビューが投稿された、または LGTM |
| `notify.re_review` | `true` | トースト: 既存のセッションが再レビューのために resume された |
| `trigger` | `/open-pr` | レビューを依頼する方法: `/open-pr`、または watcher を実行しているアカウントへのメンションなら `@me` |
