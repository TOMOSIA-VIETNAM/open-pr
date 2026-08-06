# インストール

Claude Code・Cursor・Codex・Gemini CLI・Antigravity は、同じファイルから同じレビューを実行します。
違うのは入口だけで、このページはその入口の話です。各プラットフォームがどこまで検証済みかは下の表を
参照してください。

どのプラットフォームでも、GitHub の PR なら [`gh`](https://cli.github.com/)、GitLab の MR なら
[`glab`](https://gitlab.com/gitlab-org/cli) が必要です（インストール済み・ログイン済み）。レビューは
そのアカウントで投稿されます。

## 1 コマンド

Claude Code を含む、すべてのプラットフォーム:

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash
```

どのプラットフォームか対話で訊きます。先に渡すこともできます:

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --platform cursor
```

このスクリプト自体は何もしません: 最新のリリースタグで `~/.open-pr` に clone を置き、実際に設置する
`~/.open-pr/scripts/install-local.sh` に処理を渡すだけです。実行後そこで読めます — それが動いたコード
であり、`--uninstall --all` で元に戻せます。

リリースタグが固定するのは clone であって、この 1 行ではありません: `install.sh` は既定ブランチから
取得されるため、常に最新の取得スクリプトです。これも固定したい場合は URL を `main` ではなくタグに
向けてください。

ネットワーク越しのスクリプトを実行したくない場合は、下の 2 手が同じ内容で、間に「読む」が入るだけです。
このページの残りは、各プラットフォームで最終的に何が入るかの説明です。

## アンインストール

同じ 1 行に `--uninstall` を付けるだけです:

```bash
curl -fsSL https://raw.githubusercontent.com/TOMOSIA-VIETNAM/open-pr/main/install.sh | bash -s -- --uninstall
```

訊き方はインストール時と同じです — ベンダーごとに 1 行、番号は複数同時に指定でき、最後の選択肢が終了。
違いは実際に open-pr が入っているものだけを並べる点と、参照するものがなくなれば `~/.open-pr` も削除する
点です。プラットフォームを指定した場合
（`-s -- --uninstall --platform cursor`）は、ほかがまだ使うので clone は残します。

消えるのはこのスクリプトが入れたものだけです。同名で自作したスキルは報告のうえ残します。レビュー先の
リポジトリに書いたものには触れません — ページ末尾を参照してください。

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
| Claude Code | `claude plugin marketplace add` + `claude plugin install`、またはスラッシュ 2 つ | `--platform claude` | テスト済み |
| Cursor IDE | このリポジトリを team marketplace として import（admin・Teams/Enterprise） | `scripts/install-local.sh --platform cursor` | 未テスト |
| Cursor CLI（`cursor-agent`） | — | `scripts/install-local.sh --platform cursor-cli` | 未テスト |
| Codex | `codex plugin marketplace add` + `/plugins` | `scripts/install-local.sh` | 未テスト |
| Gemini CLI | `gemini extensions install <リポジトリ URL>` | `scripts/install-local.sh` | 未テスト |
| Antigravity | `agy plugin install <path>`（CLI のみ） | `scripts/install-local.sh` | 未テスト |

`テスト済み` は、実際のレビューを通し `e2e/checklist.md` で採点したことを意味します。`未テスト` は、
ファイルとマニフェストは所定の位置にあり、そのプラットフォームが公開している仕様に沿ってはいるものの、
まだ誰も実際のレビューを流していないという意味です — 実験的なものとして扱い、投稿されたレビューを必ず
確認してください。もし流したなら、結果がどうであれ issue を立てる価値があります。

## Claude Code

セッションを開かず、シェルから:

```bash
claude plugin marketplace add TOMOSIA-VIETNAM/open-pr
claude plugin install open-pr@open-pr
```

セッション内からなら:

```bash
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@open-pr
```

更新（どちらの経路でも）:

```bash
claude plugin update open-pr@open-pr    # または /plugin update open-pr@open-pr
/reload-plugins
/open-pr:upgrade
```

コマンドは名前空間付きで入ります: `/open-pr:review`、`/open-pr:fix`、`/open-pr:upgrade`、
`/open-pr:clean`。

## Cursor

IDE と CLI が読み込むものは同じではありません。プラグインに同梱されたスキルは `cursor-agent` に届かず
IDE だけが認識する、と報告されています。CLI ではスキルを単体で入れてください:

```bash
~/.open-pr/scripts/install-local.sh --platform cursor-cli   # スキルを ~/.cursor/skills へ
```

IDE の場合:

カタログ: Cursor のダッシュボードで Settings → Plugins → Team Marketplaces → Import を開き、この
リポジトリの URL を貼ります。Cursor は `.cursor-plugin/marketplace.json` を読み、以後は既定ブランチを
追います。team marketplace の作成は Teams・Enterprise プランの admin 操作なので、個人アカウントでは
下のローカル経路を使ってください。

ローカル: `scripts/install-local.sh --platform cursor` が両方を賄います。IDE にはプラグイン全体を
`~/.cursor/plugins/local/open-pr` に置きます。Cursor がまさにこの用途に確保しているディレクトリなので、
他のプラグインと同じようにトグル付きで一覧に出ます（実行後はウィンドウを再読み込み:
`Developer: Reload Window`）。CLI には上の段落どおりスキルを入れます。

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

CLI と IDE ではスキルを読む場所が違うため、使っているほうで経路が決まります。

CLI（`agy`）— プラグインとして入れます:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
agy plugin install ~/.open-pr
```

IDE — プラグインインストーラがないので、ローカル経路を使います。IDE がグローバルに読む
`~/.gemini/config/skills` に書き込みます:

```bash
~/.open-pr/scripts/install-local.sh --platform antigravity   # CLI 側のディレクトリも一緒に
```

どちらでもスキルはスラッシュコマンドになります: `/open-pr-review` と残りの 3 つ。

## ローカルインストール

Cursor・Codex・Gemini CLI・Antigravity で、カタログ経路が使えないとき:

```bash
git clone https://github.com/TOMOSIA-VIETNAM/open-pr ~/.open-pr
~/.open-pr/scripts/install-local.sh
```

1 コマンドの場合と結果は同じで、実行前にスクリプトを自分の目で読める点だけが違います。

既定では 4 つのスキルを `~/.agents/skills/` に入れます。Codex と Gemini CLI の両方が読む場所なので、
1 回の実行で 2 つを賄えます。残る 2 つには専用の置き場があります:

```bash
~/.open-pr/scripts/install-local.sh --platform cursor        # IDE のプラグイン用ディレクトリと CLI のスキル用ディレクトリ
~/.open-pr/scripts/install-local.sh --platform antigravity   # CLI のスキル用ディレクトリと IDE のそれ
```

同じベンダーでも IDE と CLI は別のディレクトリを読むため、この 2 つの名前で両方をカバーします。片方だけ
なら `cursor-ide`、`cursor-cli`、`antigravity-cli`、`antigravity-ide`。

複数同時も可能です。カンマ区切りかフラグの繰り返し、Claude Code を含む全部なら `all`:

```bash
~/.open-pr/scripts/install-local.sh --platform cursor,shared
~/.open-pr/scripts/install-local.sh --platform all
```

`--platform` を省くと対話で訊きます: Claude Code・Codex または Gemini CLI・Cursor・Antigravity・
すべて・どれでもない。数字を複数（`2 3`）入れれば複数選べ、空欄の Enter なら何も書かずに終了します。1 つでも
不正な番号があれば、何も設置せずに停止します。その他のフラグ: 任意の場所を指す `--target DIR`、symlink を辿らない
プラットフォーム向けの `--copy`、clone を pull してから入れ直す `--update`、設置したものだけを消す
`--uninstall`。`--uninstall --all` なら上記すべてのプラットフォームを一掃するので、4 か所に入れても
アンインストールは 1 コマンドで済みます。

対応は macOS と Linux のみです: symlink を作るため、Windows では開発者モードか管理者権限のシェルが
必要になります。

置かれるのは clone へのシンボリックリンクなので、全プラットフォームをまとめて更新するのはこれだけです:

```bash
git -C ~/.open-pr pull
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
