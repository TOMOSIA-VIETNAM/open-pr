# 品牌

[← README](../../README.zh-Hans.md)

标志是一只蛾。1947 年 9 月，运行 Harvard Mark II 的团队从继电器里夹出一只，贴进日志本，写下
*“第一个真正找到 bug 的实例”*。一个专门抓 bug 的工具就以 bug 为标志，前翅上的眼斑同时也是做评审的那双眼睛。

![全部变体，在浅色与深色底上](../images/logo/brand-sheet.svg)

## 文件

| 文件 | 用在哪 |
| --- | --- |
| [`logo.svg`](../images/logo/logo.svg) | 浅色底上的标志 |
| [`logo-dark.svg`](../images/logo/logo-dark.svg) | 深色底上的标志 — 最深的那一档被提亮，躯干才不会沉进页面 |
| [`logo-lockup.svg`](../images/logo/logo-lockup.svg) | 标志加字标，横向排列。README 顶部用的就是这个 |
| [`logo-lockup-dark.svg`](../images/logo/logo-lockup-dark.svg) | 同一组合，深色底版本 |
| [`favicon.svg`](../images/logo/favicon.svg) | 任何小尺寸场合 — 另画的一版，已简化 |
| [`brand-sheet.svg`](../images/logo/brand-sheet.svg) | 上面那张总览图 |

## 规则

- 只用平面多边形：不用渐变、描边、发光、圆角。
- 同一色相的四档色，就是总览图上印出来的那几档。别的颜色都不进调色板。
- 大约 24px 以下用 `favicon.svg`，绝不缩小 `logo.svg` — 细小的切面会糊成一团。那版简化图即使触角几乎
  看不见也保留着，因为没有触角，两片翅膀就只是一对认不出来的色块。
- 标志周围至少留出一片翅膀宽度的空白。
- 标志自带颜色。不要放在有色底上，也不要为了配底色而改它的颜色。

## 重新生成

`images/logo/` 里的每个文件，都由一个脚本从同一份几何定义写出：

```sh
python3 docs/images/logo/build-moth-assets.py
```

改脚本里的坐标，而不是改 SVG，各个变体才不会走偏。脚本是幂等的：对没有改动的 checkout 运行一次，写出的
字节完全一样。
