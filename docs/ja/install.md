# インストール

このプラグインが作られ、テストされているプラットフォームは Claude Code です。Cursor・Codex・Gemini
CLI・Antigravity も、同じファイルから同じレビューを実行します — 違うのは入口だけで、このページはその
入口の話です。

どのプラットフォームでも、GitHub の PR なら [`gh`](https://cli.github.com/)、GitLab の MR なら
[`glab`](https://gitlab.com/gitlab-org/cli) が必要です（インストール済み・ログイン済み）。レビューは
そのアカウントで投稿されます。

## どちらの入口を使うか

どのプラットフォームにも入口が 2 つあり、どちらもそのプラットフォーム自身が公開している読み込みの仕組み
です。違いは、ファイルが手元に届く経路です:

- **カタログ** — プラットフォーム自身のプラグイン／拡張インストーラをこのリポジトリに向けます。既定
  ブランチを追いかけるので、更新はプラットフォーム内のコマンド 1 つで済みます。
- **ローカル** — このリポジトリを clone して `scripts/install-local.sh` を実行します。カタログ経路が
  使えないとき用です: 申請が審査待ち、あるいはアカウントに import 権限がない場合。clone したリリース
  のまま止まり、pull するまで変わりません。

| プラットフォーム | カタログ | ローカル | 状態 |
| ---------------- | -------- | -------- | ---- |
| Claude Code | `/plugin marketplace add` + `/plugin install` | 不要 | テスト済み |
| Cursor | このリポジトリを team marketplace として import（admin・Teams/Enterprise） | `scripts/install-local.sh` | 未テスト |
| Codex | `codex plugin marketplace add` + `/plugins` | `scripts/install-local.sh` | 未テスト |
| Gemini CLI | `gemini extensions install <リポジトリ URL>` | `scripts/install-local.sh` | 未テスト |
| Antigravity | `agy plugin install <path>` | `scripts/install-local.sh` | 未テスト |

`テスト済み` は、実際のレビューを通し `e2e/checklist.md` で採点したことを意味します。`未テスト` は、
ファイルとマニフェストは所定の位置にあり、そのプラットフォームが公開している仕様に沿ってはいるものの、
まだ誰も実際のレビューを流していないという意味です — 実験的なものとして扱い、投稿されたレビューを必ず
確認してください。もし流したなら、結果がどうであれ issue を立てる価値があります。

## Claude Code

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

更新:

```bash
/plugin marketplace update open-pr
/plugin update open-pr@open-pr
/reload-plugins
/open-pr:upgrade
```

コマンドは名前空間付きで入ります: `/open-pr:review`、`/open-pr:fix`、`/open-pr:upgrade`、
`/open-pr:clean`。

## Cursor

カタログ: Cursor のダッシュボードで Settings → Plugins → Team Marketplaces → Import を開き、この
リポジトリの URL を貼ります。Cursor は `.cursor-plugin/marketplace.json` を読み、以後は既定ブランチを
追います。team marketplace の作成は Teams・Enterprise プランの admin 操作なので、個人アカウントでは
下のローカル経路を使ってください。

ローカル: `scripts/install-local.sh --platform cursor` はプラグイン全体を
`~/.cursor/plugins/local/open-pr` に置きます。Cursor がまさにこの用途に確保しているディレクトリなので、
他のプラグインと同じようにトグル付きで一覧に出ます。実行後はウィンドウを再読み込みしてください
（`Developer: Reload Window`）。

どちらの経路でも、4 つのコマンドは `/open-pr-review`、`/open-pr-fix`、`/open-pr-upgrade`、
`/open-pr-clean` として現れます。

## Codex

シェルから:

```bash
codex plugin marketplace add TOMOSIA-VIETNAM/open-pr
codex
```

そのあと Codex 内で `/plugins` を開き、インストールして有効化します。すでにセッション中なら、同じ 2 手を
スラッシュコマンドでも行えます:

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr
/reload-plugins
```

Codex はこのリポジトリの `.agents/plugins/marketplace.json` からカタログを読みます。OpenAI 自身の
プラグインディレクトリへの公開は別の任意チャネルで、インストールに必須ではありません。

Codex はスキルを `$` で明示的に呼びます: `$open-pr-review <PR URL>`。

## Gemini CLI

```bash
gemini extensions install https://github.com/TOMOSIA-VIETNAM/open-pr
```

更新:

```bash
gemini extensions update open-pr
```

カタログを介さず git リポジトリから直接入る唯一のプラットフォームです。コマンド（`/review`、`/fix`、
`/upgrade`、`/clean`、拡張名で名前空間化）と、同じ 4 つのスキルの両方を読み込みます。

## Antigravity

```bash
git clone --branch v1.0.0 https://github.com/TOMOSIA-VIETNAM/open-pr ~/open-pr
agy plugin install ~/open-pr
```

スキルは TUI のスラッシュコマンドになります: `/open-pr-review` と残りの 3 つ。

## ローカルインストール

Cursor・Codex・Gemini CLI・Antigravity で、カタログ経路が使えないとき:

```bash
git clone --branch v1.0.0 https://github.com/TOMOSIA-VIETNAM/open-pr ~/open-pr
~/open-pr/scripts/install-local.sh
```

既定ブランチではなくリリースタグを clone してください。意図して切られたバージョンが手に入ります。実行
する前にスクリプトを読んでください — まさにそのために、clone したリポジトリの中に置いてあります。ここ
にはダウンロードをシェルに流し込む手順は 1 つもありません。

既定では 4 つのスキルを `~/.agents/skills/` に入れます。Codex と Gemini CLI の両方が読む場所なので、
1 回の実行で 2 つを賄えます。残る 2 つには専用の置き場があります:

```bash
~/open-pr/scripts/install-local.sh --platform cursor        # プラグイン全体を Cursor のローカルプラグイン用ディレクトリへ
~/open-pr/scripts/install-local.sh --platform antigravity   # スキルを ~/.gemini/antigravity-cli/skills へ
```

その他のフラグ: 任意の場所を指す `--target DIR`、symlink を辿らないプラットフォーム向けの `--copy`、
設置したものだけを消す `--uninstall`。

置かれるのは clone へのシンボリックリンクなので、全プラットフォームをまとめて更新するのはこれだけです:

```bash
git -C ~/open-pr pull
```

`--copy` ではリンクがないため、pull のあとにスクリプトを再実行します。どちらの場合も、スクリプトは
自分が作っていないファイルには触りません: スキルやプラグインの置き場所に既に何かあれば、そこで止めて
知らせます。`--uninstall` もそのファイルは残します。プラグイン全体の `--copy` は追跡済みファイルだけを
持っていきます — `.git` も未追跡ファイルも含みません。

## プラットフォームを増やしても、リポジトリ側は何も変わりません

`/open-pr:upgrade`（あるいは `$open-pr-upgrade`、`/open-pr-upgrade`）は、レビューが
`notebooks/review/` 以下に書く per-repo 設定の話です。2 つ目のプラットフォームを入れても、その設定は
移行も移動も複製もされません: すべてのプラットフォームが同じ設定を読み、実行すべき移行はありません。
その設定の中身は [設定](./configuration.md) を参照してください。
