# /open-pr:review — Agent Review Pull Request Github

[![Latest Release](https://img.shields.io/github/v/release/TOMOSIA-VIETNAM/open-pr?label=release)](https://github.com/TOMOSIA-VIETNAM/open-pr/releases)
[![License: MIT](https://img.shields.io/github/license/TOMOSIA-VIETNAM/open-pr)](./LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-5A32A3)](https://claude.ai/code)

[Tiếng Việt](./README.vi.md) · [English](./README.md) · **日本語**

GitHub の Pull Request を**一貫した基準で**レビューする方法を Agent に教えるプラグイン — 使うほどあなたのプロジェクトを正しく理解します。

初回は既存の規約（README、CLAUDE.md、AGENTS.md、docs、wiki…）を読み込みます。以降は常にそのリポジトリ固有のルールを適用し、チャットで追加ルールを入力すればすぐにそのリポジトリのメモリへ記憶します — 一般的なルールを押し付けず、実際の規約に忠実です。

提案が PR コメント上にしか存在しない場合は？ 記憶する前にあなたへ確認します（PR 経由で偽のルールが混入するのを防ぐため）。

プロジェクトの規約は固定ではありません — `/open-pr:review` のたびに、更新時期が来ていればプラグインが規約ドキュメントを読み直し、メモリが古くならないようにします。スケジュールの詳細：[規約の更新サイクル](#規約の更新サイクル)。

## 事前準備

- [Claude Code](https://claude.ai/code) をインストール済み
- [`gh`](https://cli.github.com/) にログイン済み（`gh auth login`）— プラグインはこのアカウントでレビューを投稿します

## インストール

Claude Code のセッション内で：

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@review-pr
```

## 最新版へ更新

`plugin.json` は `version` を宣言していません（プロジェクトは活発に開発中）— `main` への新しいコミットごとに 1 つのビルドになります。インストール済みなら最新版を取得：

```
/plugin marketplace update review-pr
/plugin update open-pr@review-pr
```

その後 `/reload-plugins`（または新しい Claude Code セッションを開く）で再読み込みします。

すでにセットアップ済みのリポジトリなら、そのリポジトリ内で `/open-pr:update-plugin` を実行してください
— 新バージョンが必要とする設定移行（あれば）を自動取得して適用するので、次のレビュー/fix を待たずに
古いリポジトリの設定を追いつかせられます。

## 使い方

スラッシュコマンドは**入力したときだけ実行されます** — Claude が勝手に `/open-pr:review` を呼ぶことはありません。

```
/open-pr:review https://github.com/<owner>/<repo>/pull/<number>
```

`/files`、`/changes`、クエリ文字列付きの URL… すべて動作します — 有効な PR リンクを含んでさえいれば OK です。

URL の直後に指示を追加すると、**その実行のみ**に適用されます（保存済みの設定は変更しません）。例：

```
/open-pr:review https://github.com/org/repo/pull/123 focus on security
```

**並行作業でもブランチを壊す心配なし。** レビューのたびに、PR のコードは専用の [git worktree](https://git-scm.com/docs/git-worktree) へチェックアウトされます — あなたが作業中のリポジトリのブランチ／ワーキングツリーは変更されません。現在のブランチで通常どおりコミット／編集しながら、複数の `/open-pr:review` セッション（同時に複数の PR）を開けます。

**関連する複数の PR を1回の呼び出しでレビュー**（例：1つの機能が2つのリポジトリに跨る場合）— 同じ呼び出しに複数の URL を渡すと、プラグインは順番に（並行ではなく）1件ずつ処理します。並行にしない理由は、共有 API contract のような PR 間の関連に気づける可能性を残すためです：

```
/open-pr:review https://github.com/org/repo-a/pull/12 https://github.com/org/repo-b/pull/34
```

**サブエージェントにレビュー作業を委任するプロンプトを自分で書く場合？** ルールを手で要約しないでください — そのサブエージェントに実際のコマンドファイル（プラグインキャッシュ内）を `Read` させ、それに従わせてください。サブエージェントはあなたのようにスラッシュコマンドを「入力」する手段を持たないため、手で要約したプロンプトは実際の PR に投稿する段階でルール/フォーマットがずれる原因になりやすいです。

## セットアップ未実施のリポジトリでの初回

プラグインは**一度だけ**質問します（リポジトリに CI があるかどうかで 6 問または 7 問 — 質問 5 を参照）：

1. レビューの**言語**（vi / en / ja）
2. **レビューを今すぐ投稿するか下書きにするか？**（`auto_submit_review`）— `true`：全員がすぐに見られる；`false`（デフォルト）：GitHub 上の下書きで、自分で Submit する
3. **古い指摘が修正されたらスレッドを自動クローズするか？**（`auto_resolve_fixed_findings`）— デフォルト `false`
4. **プロジェクト規約を再スキャンする頻度は？** — 下記の[規約の更新サイクル](#規約の更新サイクル)を参照（デフォルトは **1 か月**ごと）
5. **CI の実際の状態を照合するか？**（`review_ci_status`）— **この PR に CI check が1つでもある場合のみ質問**（CI が無いリポジトリではこの質問はスキップされ、自動的に `false` になります）；質問された場合のデフォルトは `true`；失敗した check があれば概要に一言警告（必須修正としては数えない）
6. **レビュー戦略を確認する変更ファイル数のしきい値？**（`many_files_threshold`）— デフォルト **30**；この数を超えて変更する PR では、浅く全体をレビューするか、重要な部分だけ深くレビューするか、あるいは中断して PR 分割を提案するか、方針を尋ねます
7. **巨大/ダンプファイルとみなすファイルごとのサイズしきい値？**（`big_file_threshold_kb`）— デフォルト **20**（KB、目安 ~5,000 token、1 token ≈ 4 文字の粗い換算）；このしきい値を超える変更ファイル（例：`package-lock.json`）は簡易分類のみ行い、行ごとの詳細レビューはしません — 質問 6 の変更ファイル数のしきい値とは独立しています

この 7 問とは別に、プラグインは**チャットで使う言語**も自動判定します — 判定できない場合のみ質問し、
リポジトリごとに記憶します。質問 1（レビューコメント自体の言語）とは独立しています。

その後、既存の規約ドキュメントを読み込み、以降の実行のために記憶します。

**その設定が生まれる前から使っているリポジトリの場合は？** 次回のレビューはそのまま動きます — 足りない項目はデフォルト値にフォールバックするだけです。設定ファイル自体を追いつかせたい場合は、そのリポジトリで `/open-pr:update-plugin` を実行してください。7 つの設定のうちどれかを変更したい場合（レビューを待たずいつでも可）— チャットで「レビュー設定を変更」（または同様の表現）と伝えると、プラグインが現在の値を表示し、どのフィールドを変更するか尋ねます。

記憶データはレビュー対象のリポジトリ内、`notebooks/review/<リポジトリ名>/`（ローカル専用の git、push されない）にあります。このディレクトリはプロジェクトの `.gitignore` に入れておくとよいでしょう — 無ければプラグインが自動で追加します。

## 仕組み（概要）

```
/open-pr:review <PR_URL>
        │
        ▼
PR のコードを専用の worktree へチェックアウト（作業中のブランチには触れない）
        │
        ▼
変更部分をレビュー：
  • 一般的な技術ルール
  • このリポジトリ固有の規約 / メモリ
        │
        ▼
1 件のレビューを投稿：概要 + 行ごとのコメント（必要なとき）
  • 重要度は emoji で表示：🔴 MUST FIX / 🟠 SHOULD FIX / 🔵 SUGGESTION / 📝 NOTE
  • きれいな PR → **LGTM 🌟**、細かい粗探しはしない
```

多くのスタックに対応：Rails、Vue、React、Python、Node.js、Lambda、PHP、Laravel、WordPress、Shell、Makefile、そして AI エージェントに指示するための markdown ファイル（skill/command/CLAUDE.md/AGENTS.md/cursor rules など）（新しいスタックに出会うと自動で拡張）。

**レビュー + コメントのみ。** PR のクローズ／マージ、ブランチの切り替え、コードの代筆はしません。

## 規約の更新サイクル

プロジェクトの規約は時とともに変化します。プラグインは `/open-pr:review` の実行時に**定期的に読み直す**ことができ、メモリが古くならないようにします。

| 希望 | `doctor_schedule` に設定 |
|------|--------------------------|
| 毎週 | `"1 weeks"` または `"7 days"` |
| 隔週 | `"2 weeks"` |
| 毎月（デフォルト） | `"1 months"` |
| 四半期ごと | `"3 months"` |
| 自動で読み直さない | `"never"` |

`notebooks/review/<repo>/settings.json` の `review` ノードで編集します — フィールドの隣に簡単な説明の `_comments` 行があります。スケジュールを待たずに**今すぐ**読み直したい場合：チャットで **doctor lại** /  **規約を再スキャン** と伝えてください。

## 使用開始後のカスタマイズ

一度以上レビューしたリポジトリで：

| 変更したいもの | 編集場所 |
|----------------|----------|
| デフォルト言語 | `notebooks/review/<repo>/ALWAYS_RULE.md` — `Output language` ブロック |
| 今すぐ投稿／下書き、スレッド自動解決、規約の再読み込みサイクル | `notebooks/review/<repo>/settings.json` の `review` ノード |
| チーム固有のルール | `ALWAYS_RULE.md` の追加ルール節、またはチャットで伝えて lesson を記録 |

## レビュー後に使う：`/open-pr:fix`

`/open-pr:review` はレビュー＋コメントのみで、代わりにコードを直しません。レビュー済みの PR に対して次を呼びます：

```
/open-pr:fix https://github.com/<owner>/<repo>/pull/<number>
```

`/open-pr:review` と違い、こちらは **dev 向けで実際にコードを編集します**。専用の worktree ではなく、いま作業中のディレクトリで直接実行します — bot が残した指摘を読み、重要度に応じて修正するか見送るかを判断し（🔵 SUGGESTION／📝 NOTE は必ず先に確認）、学習済みのプロジェクト規約に沿ってコードを直し、まとめて 1 コミットにし、PR の各指摘へ返信します。どこで動くか・何を自動でやるか・何を先に確認するかは、そのリポジトリで初めて呼んだときにコマンド内で確認できます（設定を 2 問だけ、一度だけ質問）。

その実行だけ範囲を絞りたい場合は、指示を追加します。例：

```
/open-pr:fix https://github.com/org/repo/pull/123 セキュリティ部分だけ直して
```
