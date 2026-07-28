# open-pr — プロジェクトの規約を覚えるエージェントによる PR レビュー

[![Latest Release](https://img.shields.io/github/v/release/TOMOSIA-VIETNAM/open-pr?label=release)](https://github.com/TOMOSIA-VIETNAM/open-pr/releases)
[![License: MIT](https://img.shields.io/github/license/TOMOSIA-VIETNAM/open-pr)](./LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-5A32A3)](https://claude.ai/code)

[Tiếng Việt](./README.vi.md) · [English](./README.md) · **日本語**

Pull/Merge Request をレビューし、リポジトリごとの規約を記憶する Claude Code プラグインです。使うほど
一般論ではなくそのプロジェクトに沿ったレビューになります。

**GitHub**（`.../pull/<n>`）と **GitLab**（`.../-/merge_requests/<n>`、セルフホスト含む）に対応。
Bitbucket は未対応です。

## 必要なもの

- [Claude Code](https://claude.ai/code)
- GitHub の PR なら [`gh`](https://cli.github.com/)、GitLab の MR なら [`glab`](https://gitlab.com/gitlab-org/cli) にログイン済み — そのアカウントでレビューが投稿されます

## インストール

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@review-pr
```

更新:

```
/plugin marketplace update review-pr
/plugin update open-pr@review-pr
```

その後 `/reload-plugins`、または新しいセッションを開いてください。古いバージョンでセットアップした
リポジトリでは `/open-pr:update-plugin` を一度実行すると、ローカル設定が最新になります。

## 使い方

コマンドは自分で入力したときだけ実行されます。

```
/open-pr:review https://github.com/<owner>/<repo>/pull/<n>
/open-pr:review https://gitlab.com/<owner>/<repo>/-/merge_requests/<n>
```

PR をレビューし、レビューを 1 件だけ投稿します（概要＋必要な箇所への行コメント）。各指摘には
🔴 MUST FIX / 🟠 SHOULD FIX / 🔵 SUGGESTION / 📝 NOTE が付きます。問題なければ **LGTM 🌟**。

PR のコードは専用の git worktree にチェックアウトされるため、作業中のブランチには一切触りません。
レビュー中もそのまま作業を続けられます。

```
/open-pr:fix https://github.com/<owner>/<repo>/pull/<n>
```

前回のレビューの指摘を読み、**現在の作業ディレクトリ**で修正します。1 回の実行で 1 コミット。
🔵/📝 の指摘は必ず確認を取り、コードを push した後にだけ PR へ返信します。

URL の後ろに書いた指示は、その実行のみに適用されます:

```
/open-pr:review https://github.com/org/repo/pull/123 セキュリティを重点的に
/open-pr:fix https://github.com/org/repo/pull/123 セキュリティ部分だけ修正
```

関連する複数の PR をまとめて（並列ではなく順番に処理）:

```
/open-pr:review https://github.com/org/repo-a/pull/12 https://github.com/org/repo-b/pull/34
```

## リポジトリでの初回実行

短い初期設定（レビュー言語、即投稿かドラフトか、規約ドキュメントを読み直す間隔、大きすぎる PR の
しきい値）を一度だけ質問し、そのあとリポジトリに既にある規約 — README、CLAUDE.md、AGENTS.md、docs、
wiki、cursor/copilot rules — を読み取ります。

記憶した内容はレビュー対象リポジトリ内の `notebooks/review/<repo>/` に置かれます（独立したローカル
git、push はしません）。このパスはプラグインが `.gitignore` に追加します。

| 変更したいもの | 編集先 |
|---|---|
| チーム独自のレビュールール | `notebooks/review/<repo>/ALWAYS_RULE.md` — 初期状態は空。普通の文章で書けます |
| レビュー言語、ドラフト/即投稿、自動 resolve、読み直し間隔、大きいファイルのしきい値 | `notebooks/review/<repo>/settings.json` |

チャットで直接言うだけでも変更できます: **reconfigure review**、**doctor again**、または覚えて
ほしい新しいルール。

規約ドキュメントは定期的に読み直されます（`doctor_schedule`: `"7 days"`、`"2 weeks"`、既定は
`"1 months"`、`"never"`）。記憶が古くなるのを防ぐためです。

## 補足

- 対応スタック: Rails, Vue, React, Python, Node.js, Lambda, PHP, Laravel, WordPress, Shell,
  Makefile、および AI エージェント向け指示として書かれた markdown。未知のスタックはその場で
  テンプレートを作成します。
- `/open-pr:review` はコードを変更せず、close も merge もしません。コードを書くのは
  `/open-pr:fix` のみで、実行したディレクトリ内だけです。
- PR のコメント内に現れたルールは、記憶する前に必ず確認します。
- 自作プロンプトでサブエージェントにレビューを任せる場合は、ルールを書き写すのではなくコマンド
  ファイルそのものを `Read` させてください。書き写すとずれます。
