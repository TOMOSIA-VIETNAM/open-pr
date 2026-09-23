# 設定

[← README](../../README.ja-JP.md)

リポジトリごとにプラグインが保持するもの、そしてそれを変える場所。

## どこに立つか

memory・設定・レビュー用 worktree は **マシンごとに 1 か所** にまとまり、プロジェクト内には置かれません:

```
~/.open-pr-data/review/
├── .git/            学習内容のローカル履歴 — remote なし、push もしない
├── repo-backend/    memory.md · memories/ · templates/ · ALWAYS_RULE.md · settings.json · worktrees/
└── repo-frontend/
```

そのため、リポジトリを見つけられる場所ならどこでもコマンドを入力できます: リポジトリ内、またはそれを含むワークスペース（`git remote` で判別）。プロジェクトには何も書かれず、`.gitignore` にも行は追加されません。複数のリポジトリが並ぶワークスペースなら、1 回の実行で **リポジトリ横断** PR をレビューできます（並列ではなく順番に）:

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` も同じ場所から呼べます（リポジトリが PR のブランチ上にあること）— または `review` がすでに作った worktree から。そこではセッションが対象 PR を知っているため URL は省略できます。

> [!NOTE]
> ワークスペースに `~/.open-pr-data/review/` を置いていた旧ビルドから移る場合、自動では移動されません。学習内容を残すには一度だけ移動してください — `mkdir -p ~/.open-pr-data && mv notebooks/review ~/.open-pr-data/review` — そのあと `.gitignore` の `~/.open-pr-data/review/` 行を削除します。

## Command

| コマンド | どこに立つか | 何を書くか |
| --- | --- | --- |
| `/open-pr:review` | リポジトリ内、またはそれを含むワークスペース — `git remote` で自動判別 | PR 上のコメント + `~/.open-pr-data/review/<repo>/` の memory |
| `/open-pr:fix` | そのリポジトリ内 / それを含むワークスペース — ただし **リポジトリが PR のブランチ上にあること** | リポジトリの実コード + PR への返信 |
| `/open-pr:upgrade` | どこでも — 設定済みの全リポジトリ、または指定したものを更新 | `~/.open-pr-data/review/<repo>/settings.json` |
| `/open-pr:clean` | どこでも | 何も書かない — `~/.open-pr-data/review/*/worktrees/*` だけを削除 |
| `/open-pr:feedback` | どこでも | ローカルには何も書かない — 本文を承認したあと、プラグイン自身の tracker に issue を 1 件 |

## Setting

学習した内容は `~/.open-pr-data/review/<repo>/memory.md` にインデックスされます（目次 — トークンを節約しつつ全体像は把握できる）。詳細は `~/.open-pr-data/review/<repo>/memories/*.md` にあります。

> [!NOTE]
> `~/.open-pr-data/review/` 全体は **独立したローカル git** で管理されます — remote なし、push もしない。レビューごとの memory の変化を追えます。

チームルールは普通の文章で `ALWAYS_RULE.md` に書きます（初期状態は空）。それ以外は `settings.json` にあります:

| Field | 意味 | 既定値 |
| --- | --- | --- |
| `shared.chat_language` | チャットで使う言語 | 自動判別 |
| `shared.output_language` | PR に投稿する言語 | 初回に質問して保存 |
| `review.auto_submit_review` | `true` = すぐ投稿、`false` = 先に確認できるよう保留 — ドラフトがあるベンダーでは PR 上のドラフト、ドラフトのない Bitbucket ではチャット内に留まり PR は空のまま | `false` |
| `review.auto_resolve_fixed_findings` | 指摘が修正されたらスレッドを自動 resolve | `false` |
| `review.post_lgtm` | 指摘が 1 件もない結果を PR に投稿する。`false` ならチャットに表示するだけ | `true` |
| `review.doctor_schedule` | 規約ドキュメントを読み直す間隔: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"` |
| `review.review_ci_status` | CI が失敗している場合に触れるか（警告のみ、修正は強制しない） | CI あり ⇒ `true` |
| `review.many_files_threshold` | この数を超えるファイル数の PR は大きすぎると警告 | `30` |
| `review.big_file_threshold_kb` | diff がこのサイズを超えるファイルは最初の読み取りから除外 | `20` |
| `fix.decline_needs_confirmation` | 指摘を見送る前に確認する | `true` |
| `fix.auto_push` | コミット後に自動で push する | `false` |

---

[インストール](./install.md) · [再レビュー / fix のフロー](./how-it-works.md) · [何をレビューするか](./review-criteria.md)
