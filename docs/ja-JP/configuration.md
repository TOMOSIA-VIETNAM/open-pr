# 設定

[← README](../../README.ja-JP.md)

リポジトリごとにプラグインが保持するもの、そしてそれを変える場所。

## データの置き場所

すべてのリポジトリの memory・settings・レビュー用 worktree は、一度だけ選ぶ **1 つのデータディレクトリ** に置かれます。どのリポジトリの外にもあるので、`.gitignore` への追記も `git status` の変化もありません。

```
~/workspace/notebooks/review/   ← データディレクトリ（自分で選ぶ）
├── .git                        学習内容のローカル履歴
├── repo-backend/               memory + settings + worktrees/
└── repo-frontend/
~/workspace/repo-backend/       ← 触れない
```

データディレクトリが未設定なら、最初のコマンドがそのパスを尋ねます。推奨はリポジトリのすぐ外側のディレクトリにある `notebooks/review/` です — `~/workspace/repo-backend` なら `~/workspace/notebooks/review/`。任意のパスも指定できます。リポジトリ内に既にある `notebooks/review/` はそこへ **コピー** され（worktree は除く）、元の場所にも残ります。その後も、データディレクトリにまだないリポジトリは立っている場所の下で同じように探され、見つかった `notebooks/review/<repo>/` の取り込みを提案します。選択は `~/.config/open-pr/config.json` の `data_dir` に保存されます — 場所を変えるにはこのファイルを編集します。

立つ場所はデータの置き場所に影響しません。複数リポジトリを含むワークスペースからなら、1 回の実行で **リポジトリ横断** PR をレビューできます（並列ではなく順番に）：

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` はワークスペースから呼べます（対象リポジトリを自分で見つける。そのリポジトリが PR のブランチ上にあることが条件）— または `review` がすでに作った worktree から。そこではセッションが対象 PR を知っているため URL は省略できます。

## Command

| コマンド | どこに立つか | 何を書くか |
| --- | --- | --- |
| `/open-pr:review` | リポジトリを含むワークスペース、またはリポジトリ内 — `git remote` で自動判別 | PR 上のコメント + `<data>/<repo>/` の memory |
| `/open-pr:fix` | そのリポジトリ内 / それを含むワークスペース — ただし **リポジトリが PR のブランチ上にあること** | リポジトリの実コード + PR への返信 |
| `/open-pr:upgrade` | どこでも — データディレクトリ内の全リポジトリ、または指定したもの | `<data>/<repo>/settings.json` |
| `/open-pr:clean` | どこでも | 何も書かない — `<data>/*/worktrees/*` だけを削除 |
| `/open-pr:feedback` | どこでも | ローカルには何も書かない — 本文を承認したあと、プラグイン自身の tracker に issue を 1 件 |

## Setting

以下の `<data>` はデータディレクトリです。学習した内容は `<data>/<repo>/memory.md` にインデックスされます（目次 — トークンを節約しつつ全体像は把握できる）。詳細は `<data>/<repo>/memories/*.md` にあります。

> [!NOTE]
> データディレクトリ全体は **独立したローカル git** で管理されます — remote なし、push もしない。レビューごとの memory の変化を追えます。

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
