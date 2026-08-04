# 設定

[← README](../../README.ja.md)

リポジトリごとにプラグインが保持するもの、そしてそれを変える場所。

## どこに立つか

```
✅ ワークスペースにいる                      ❌ リポジトリの中にいる
─────────────────────────                    ─────────────────────────
workspace/            ← ここで入力           repo-backend/         ← ここで入力
├── notebooks/review/  memory + worktree     ├── notebooks/review/  memory がプロジェクト内に入る
│   ├── repo-backend/  どのリポジトリの外    ├── .gitignore         +1 行 — 実際の変更
│   └── repo-frontend/                       └── src/
├── repo-backend/     ← 余計なファイル 0
└── repo-frontend/    ← 余計なファイル 0     (repo-frontend? 見えない)
```

`notebooks/review/`（memory + worktree）は、コマンドを入力した場所にそのまま作られます。リポジトリの中で
入力すればプロジェクト内に置かれます。プラグインが `.gitignore` に 1 行追加するので `git status` は汚れ
ませんが、その 1 行はリポジトリへの実際の変更です。

ワークスペースから実行すればリポジトリには一切触れません。さらにリポジトリが横に並んでいるため、リポジトリ
をまたいだレビューができます — 1 つの機能に属する複数の PR を、並列ではなく順番に 1 回の実行で。
`repo-backend` の中からは `repo-frontend` は見えません:

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` もワークスペースから実行できます。対象リポジトリを自分で見つけてその中で修正します
（そのリポジトリが PR のブランチ上にあることが条件）。

記憶した内容は `notebooks/review/<repo>/memory.md` に目次のようにインデックスされます。詳細を読み込まずに
済むのでトークンを節約でき、それでも何を学んだかの全体像は把握できます。詳細は
`notebooks/review/<repo>/memories/*.md` に 1 件ずつ保存されます。`notebooks/review/` 全体は独立した
ローカル git で管理され（remote なし、push もしない）、レビューごとの memory の変化を追えます。

チーム独自のルールは普通の文章で `ALWAYS_RULE.md` に書きます（初期状態は空）。それ以外は
`settings.json` にあります:


| Field                                | 意味                                                                                      | 既定値               |
| ------------------------------------ | ----------------------------------------------------------------------------------------- | -------------------- |
| `shared.chat_language`               | チャットで使う言語                                                                        | 自動判別             |
| `shared.output_language`             | PR に投稿する言語                                                                         | 初回に質問して保存   |
| `review.auto_submit_review`          | `true` = すぐ投稿、`false` = ドラフトにして確認できるようにする                           | `false`              |
| `review.auto_resolve_fixed_findings` | 指摘が修正されたらスレッドを自動 resolve                                                  | `false`              |
| `review.doctor_schedule`             | 規約ドキュメントを読み直す間隔: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"`       |
| `review.review_ci_status`            | CI が失敗している場合に触れるか（警告のみ、修正は強制しない）                             | CI あり ⇒ `true`     |
| `review.many_files_threshold`        | この数を超えるファイル数の PR は大きすぎると警告                                          | `30`                 |
| `review.big_file_threshold_kb`       | diff がこのサイズを超えるファイルは最初の読み取りから除外                                 | `20`                 |
| `fix.decline_needs_confirmation`     | 指摘を見送る前にあなたへ確認する                                                          | `true`               |
| `fix.auto_push`                      | コミット後に自動で push する                                                              | `false`              |
