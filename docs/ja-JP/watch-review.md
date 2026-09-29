# リポジトリを監視し、依頼があればレビューする

[← README](../../README.ja-JP.md)

`/open-pr:watch-review` は、実行したターミナルを 1 つ以上のリポジトリの watcher にします。開発者が
pull request にコメントしてレビューを依頼すると、あなたのマシンがその pull request 専用のレビュー
セッションを開き、あなたの対応が必要なときに知らせます。

## 初回実行の前に

1. 各リポジトリで一度 `/open-pr:review <any PR URL>` を実行します。レビュー memory が未セットアップの
   リポジトリを watcher は拒否します。複数のセッションが同時にセットアップしないようにするためです。
2. リポジトリ内、または複数のリポジトリを含むワークスペースで `/open-pr:watch-review` を実行します。
   見つかったすべてのリポジトリとリモートを一覧にし（ホストごとにリモートを持つクローンはリモートごとに
   表示）、監視するものを尋ねます。レビュー memory 設定済みのものが推奨されます。
   `/open-pr:watch-review owner/api owner/web`（または PR の URL）で直接指定できます。
3. リポジトリでの初回実行では、同時にアクティブにできるレビューセッションの数、レビューを依頼する方法
   （`/open-pr` またはあなたへのメンション）、受け取りたいトーストを尋ね、回答をそのリポジトリの
   `settings.json` に保存します。
4. レビューセッションは watcher を実行したフォルダーで起動します。そこで `/open-pr:review` を入力した
   場合と同じで、データディレクトリも trust も同じです。Claude Code ではそのフォルダーが trusted
   workspace でなければなりません。watcher は起動時に確認し、そうでなければ、そこで一度 `claude` を開いて
   trust の確認を承認するよう伝えます。

監視する各リポジトリは自分の設定（セッション数の上限を含む）を持ちます。1 台のマシンで 1 つのリポジトリを
監視する watcher は 1 つだけです。2 つ目はすでに監視しているプロセスを伝え、そのリポジトリには触れません。
ホストに接続できない状態が続くと（ネットワークなし、ログイン期限切れ）、watcher が知らせます。

## レビューを依頼する

pull request にコメントします:

```
/open-pr
/open-pr please look closely at the migration
```

`/open-pr` の後の文は、どこを見るべきかのヒントです。データとして扱われるため、レビューのやり方、投稿
される内容、どの設定も変えられません。

「自分へのメンション」トリガーでは、`@<your login>` で始まるコメントが代わりに依頼となるため、pull request
にツールのコマンドが表示されません。watcher は、この pull request のレビューを本当にあなたに頼んでいる
場合だけ引き受けます。`@minh レビューお願いします` は対象、`@minh ありがとう` は対象外です。

レビューを起動するのは write 権限を持つ人のコメントだけです:

| ホスト | 起動できる人 |
|---|---|
| GitHub | owner・member・collaborator |
| GitLab | Developer 以上 |
| Bitbucket | コメントできる人全員 — 管理者以外は他ユーザーの権限を読めないため、問題になるならコメントできる人を制限してください |

プラグインが投稿したコメントでは起動しません。自分のコメントでは起動するので、1 人で開発者とレビュアーを
兼ねられます。

## その後に起きること

- watcher がコメントに返信します — "reviewing (commit abc1234)"、依頼と同じ言語で — 引き受けたコミットを
  示します。複数のマシンが同じリポジトリを監視している場合、この返信がロックになります。最初の返信が勝ち、
  すでに返信を見つけたマシンは手を引き、僅差の競争に負けたマシンは自分の返信を削除します。
- `review <owner>/<repo>#<number>` という名前のセッションが通常のレビューを実行します。セッション数が上限に
  達すると、pull request はキューで待ちます。
- すでにセッションがある pull request への新しい依頼は、前回の指摘の再確認を求めるならそのセッションを
  resume し、最初からのレビューを求めるなら新しいセッションを開きます（pull request が先に進むと、古い
  コンテキストが誤解を招くため）。はっきりしないときは watcher があなたに尋ねます。
- レビューを公開するかドラフトのままにするかは、watcher に別の指示をしない限り `auto_submit_review` で
  決まります。ドラフトがあなた抜きで公開されることはありません。
- 結果を報告したセッションはあなたのものです。その pull request への次の依頼まで、watcher はそれについて
  何も言わず、そこであなたが書いた内容を読むこともありません。
- 結果を報告してから 30 分アイドルのままの Claude Code レビューセッションは、メモリ解放のため停止されます。
  会話は残るので、`claude attach <id>` も後の再レビューも使えます。watcher が開いていないセッションには触れません。

## セッションを開く

画面右上のトーストが、いま何が起きているかを知らせます — "Reviewing PR #12"、"Posted review on PR #12 —
1 🔴 2 🟠"、"LGTM on PR #12"、承認待ちのドラフト、回答が必要なセッション。クリックすると pull request が
開き、マウスを乗せている間は表示が続きます。トーストの "1h" で 1 時間トーストをオフにできます。対応が
必要なときは、セッションを開くコマンドが表示されます。macOS では watcher が自分でトーストを描画します
（通知の権限は不要）。Linux では `notify-send` を使います。

すべてのチャット行にセッションを開くコマンドが付きます:

| プラットフォーム | セッションの種類 | 開き方 |
|---|---|---|
| Claude Code | interactive、バックグラウンドで実行 | `claude attach <id>` |
| Codex | non-interactive | `codex resume <id>` |
| Gemini CLI | non-interactive | `gemini -r <id>` |
| Cursor | non-interactive | `agent --resume <id>` |
| Antigravity | non-interactive | `agy --conversation <id>` |

Claude Code では、回答（または権限の許可）が必要なセッションは、あなたが attach するまで待ちます。他の
プラットフォームでは、セッションは質問を残して停止し、watcher があなたに尋ねて、その回答で resume します。

watcher は shell sandbox の外で動きます。sandbox の中ではポーリングがホストに届かず、Claude Code の
バックグラウンドセッションは起動中のまま止まります。non-interactive セッションは、そのプラットフォームで
あなたが設定した権限設定を使います。watcher は権限を一切付与しません。

## メニューバー（macOS）

watcher が起動すると、メニューバーに蛾のアイコンと進行中のレビュー数が表示されます。マシン全体で 1 つだけで、
すべての watcher が対象です。`/open-pr:menubar close`（またはメニューの Quit）まで残り、`/open-pr:menubar`
で再表示できます。メニューには次の内容が並びます:

- 進行中のレビュー（watcher ごとにグループ化: `<folder> · <terminal>`）— グループの "Go to watcher tab" で
  その terminal のタブが前面に出ます（iTerm と Terminal では、macOS が一度だけ Automation の権限を求めた
  あと、そのタブそのものを選択します。それ以外では terminal アプリが前面に出ます）。各レビューからは、
  pull request を開く、その watcher が動いている terminal でセッションを開く、コマンドをコピーする、の
  いずれかができます。
- 直近 10 件のトースト — クリックするとその pull request が開きます。
- スヌーズ: 30 分、1 時間、明日 9:00 まで、またはトーストを再びオンにする。

Windows と Linux では、チャットで watcher に頼んでください（`status`、`snooze 1h`）。

## watcher と話す

| 言うこと | 効果 |
|---|---|
| `status` | pull request ごとに 1 行、状態と開くコマンド付き |
| `snooze 2h` / `resume toasts` | その時刻までこのマシンでトーストなし — トーストの "1h" やメニューバーのスヌーズと同じスイッチ。キューは動き続ける |
| 設定の変更 | `settings.json` に保存 |
| PR 12 は新しいセッションで | その PR の次の起動で新しいセッションを開く |
| `stop` | 監視を停止。開いているレビューセッションは動き続ける |

## レート制限

ポーリング 1 回ごとの API 呼び出しは、GitHub では 3 回、GitLab と Bitbucket では 1 回に加えて前回の
ポーリング以降に更新された pull request 1 件ごとに 1 回です。ホストがレート制限を返すと、watcher は間隔を
2 倍にし（最大 15 分）、次にポーリングが成功した後で `poll_interval_seconds` に戻ります。

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
