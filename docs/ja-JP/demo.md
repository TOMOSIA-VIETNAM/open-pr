# 結果の見え方

[← README](../../README.ja-JP.md)

投稿されるレビューは結びついた **3 つの部分** を持ちます:

1. **Overview** — 差分全体が何を意味するかを、読み取った時点のコミットに紐づけ、重大度ごとにまとめたもの。FILE レベルの指摘はここに入ります（紐づける具体的な行がないため）。
2. **行コメント** — LINE レベルの指摘。それぞれ修正後のコードを `suggestion` ブロックで示すので、作者は PR の画面からそのままコミットできます。
3. **返信** — `/open-pr:fix` は push 後に同じスレッドで返信します。会話は問題が提起された場所に留まり、PR の先頭からやり直しになりません。

下の画像は、このリポジトリ自身の PR に投稿された実際のレビューで、言語はそのリポジトリの `settings.json` が選んだものです:

![Overview、suggested change を含む行コメント、fix push 後の返信](../images/review-demo-ja.png)

> [!NOTE]
> 言語は **リポジトリ** 単位であり、ユーザー単位ではありません。`shared.output_language` が PR に **POST** される内容を決めます — エージェントがチャットであなたと話す言語とは独立です。

同じレビューの [English](../demo.md)、[Tiếng Việt](../vi-VN/demo.md)、[简体中文](../zh-Hans/demo.md) もあります。

## 同じ実行を、各ベンダーで

`open-pr` が対応する各ベンダーでの、PR ページ全体を上から下まで: 先頭の Overview、指摘対象のコードに
付いた行コメント、そのまま適用できる `suggestion` ブロック、そして `/open-pr:fix` が push した後の返信。
各キャプチャの言語は、そのリポジトリの `settings.json` が選んだものです。

<details>
<summary><b>GitHub</b> — pull request、レビューは English で投稿</summary>

[![open-pr がレビューした GitHub の pull request。Overview から返信まで](../images/preview/github.png)](../images/preview/github.png)

</details>

<details>
<summary><b>GitLab</b> — merge request、レビューは Tiếng Việt で投稿</summary>

[![open-pr がレビューした GitLab の merge request。Overview から返信まで](../images/preview/gitlab.png)](../images/preview/gitlab.png)

</details>

<details>
<summary><b>Bitbucket Cloud</b> — pull request、レビューは 日本語 で投稿</summary>

[![open-pr がレビューした Bitbucket の pull request。Overview から返信まで](../images/preview/bitbucket.png)](../images/preview/bitbucket.png)

</details>

## Severity

これがレビュアーと作者のあいだの「契約」です:

| | レベル | `/open-pr:fix` |
| --- | --- | --- |
| 🔴 | MUST FIX | 自分で処理 |
| 🟠 | SHOULD FIX | 自分で処理 |
| 🔵 | SUGGESTION | 必ず先に **確認** |
| 📝 | NOTE | 必ず先に **確認** |

差分に言うことがない → **LGTM 🌟** の 1 行だけ、見出しなし。

---

[設定](./configuration.md) · [何をレビューするか](./review-criteria.md)
