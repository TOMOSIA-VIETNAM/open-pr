# ブランド

[← README](../../README.ja-JP.md)

マークはガです。1947 年 9 月、Harvard Mark II を動かしていたチームがリレーから 1 匹を取り出し、
*「bug が実際に見つかった最初の事例」* としてログブックに貼り付けました。bug を狩るツールは bug 自身を
マークに据え、前翅の眼状紋はレビューする目を兼ねます。

![明るい背景と暗い背景での全バリエーション](../images/logo/brand-sheet.svg)

## ファイル

| ファイル | 使う場所 |
| --- | --- |
| [`logo.svg`](../images/logo/logo.svg) | 明るい背景のマーク |
| [`logo-dark.svg`](../images/logo/logo-dark.svg) | 暗い背景のマーク — 胴が紙面に沈まないよう最も暗いトーンを持ち上げてある |
| [`logo-lockup.svg`](../images/logo/logo-lockup.svg) | マーク + ワードマークの横組み。README のヘッダーが使うのはこれ |
| [`logo-lockup-dark.svg`](../images/logo/logo-lockup-dark.svg) | 同じロックアップの暗い背景版 |
| [`favicon.svg`](../images/logo/favicon.svg) | 小さい用途すべて — 簡略化した別の図 |
| [`brand-sheet.svg`](../images/logo/brand-sheet.svg) | 上のシート |

## ルール

- フラットなポリゴンのみ: グラデーション、ストローク、グロー、角丸は使わない。
- 1 色相 4 トーン、シートに載っているものだけ。ほかの色はパレットに加えない。
- およそ 24px 未満では `favicon.svg` を使い、`logo.svg` の縮小は使わない — 細かいファセットが潰れる。
  その簡略図はほとんど見えなくなっても触角を残している。触角がないと翼が正体不明の 2 つの塊に見える。
- マークの周囲に、少なくとも翼 1 枚分の余白を取る。
- マークは自前の色を持つ。色の付いた面に置かない、面に合わせて色を変えない。

## 再生成

`images/logo/` のファイルはすべて、1 つのジオメトリ定義から 1 つのスクリプトが書き出す:

```sh
python3 docs/images/logo/build-moth-assets.py
```

SVG ではなくスクリプト内の座標を編集する。そうすればバリアント同士がずれない。スクリプトは冪等で、
変更のないチェックアウトに対して実行しても同じバイト列を書き直す。
