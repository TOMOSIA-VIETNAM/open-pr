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

`notebooks/review/`（memory + worktree）は、コマンドを入力した場所に **そのまま** 作られます。

| 立つ場所 | 結果 |
| --- | --- |
| **ワークスペース**（推奨） | リポジトリには触れない。リポジトリが横に並ぶ → 1 回の実行で **リポジトリ横断** PR をレビューできる（並列ではなく順番に） |
| **リポジトリ内** | `notebooks/review/` がプロジェクト内に置かれる。プラグインが `.gitignore` に 1 行追加するので `git status` は汚れない — ただしその 1 行はリポジトリへの実際の変更 |

```bash
cd ~/workspace
/open-pr:review https://github.com/org/repo-backend/pull/12 https://github.com/org/repo-frontend/pull/34
```

`/open-pr:fix` はワークスペースから呼べます（対象リポジトリを自分で見つける。そのリポジトリが PR のブランチ上にあることが条件）— または `review` がすでに作った worktree から。そこではセッションが対象 PR を知っているため URL は省略できます。

## Command

| コマンド | どこに立つか | 何を書くか |
| --- | --- | --- |
| `/open-pr:review` | リポジトリを含むワークスペース（推奨）、またはリポジトリ内 — `git remote` で自動判別 | PR 上のコメント + `notebooks/review/<repo>/` の memory |
| `/open-pr:fix` | そのリポジトリ内 / それを含むワークスペース — ただし **リポジトリが PR のブランチ上にあること** | リポジトリの実コード + PR への返信 |
| `/open-pr:upgrade` | 設定済みのワークスペースまたはリポジトリ — 複数あれば選択させる | `notebooks/review/<repo>/settings.json` |
| `/open-pr:clean` | 掃除したい `notebooks/review/` より上のどこか | 何も書かない — `notebooks/review/*/worktrees/*` だけを削除 |

## Setting

学習した内容は `notebooks/review/<repo>/memory.md` にインデックスされます（目次 — トークンを節約しつつ全体像は把握できる）。詳細は `notebooks/review/<repo>/memories/*.md` にあります。

> [!NOTE]
> `notebooks/review/` 全体は **独立したローカル git** で管理されます — remote なし、push もしない。レビューごとの memory の変化を追えます。

チームルールは普通の文章で `ALWAYS_RULE.md` に書きます（初期状態は空）。それ以外は `settings.json` にあります:

| Field | 意味 | 既定値 |
| --- | --- | --- |
| `shared.chat_language` | チャットで使う言語 | 自動判別 |
| `shared.output_language` | PR に投稿する言語 | 初回に質問して保存 |
| `review.auto_submit_review` | `true` = すぐ投稿、`false` = ドラフトにして確認できるようにする | `false` |
| `review.auto_resolve_fixed_findings` | 指摘が修正されたらスレッドを自動 resolve | `false` |
| `review.doctor_schedule` | 規約ドキュメントを読み直す間隔: `"{N} days"` \| `"{N} weeks"` \| `"{N} months"` \| `"never"` | `"1 months"` |
| `review.review_ci_status` | CI が失敗している場合に触れるか（警告のみ、修正は強制しない） | CI あり ⇒ `true` |
| `review.many_files_threshold` | この数を超えるファイル数の PR は大きすぎると警告 | `30` |
| `review.big_file_threshold_kb` | diff がこのサイズを超えるファイルは最初の読み取りから除外 | `20` |
| `fix.decline_needs_confirmation` | 指摘を見送る前に確認する | `true` |
| `fix.auto_push` | コミット後に自動で push する | `false` |

---

[インストール](./install.md) · [再レビュー / fix のフロー](./how-it-works.md) · [何をレビューするか](./review-criteria.md)
