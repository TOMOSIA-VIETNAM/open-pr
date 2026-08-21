# Thương hiệu

[← README](../../README.vi-VN.md)

Mark là một con bướm đêm. Tháng 9/1947, nhóm vận hành Harvard Mark II gắp một con ra khỏi relay và dán
vào logbook, ghi là *"trường hợp thực tế đầu tiên tìm thấy bug"*. Một tool đi bắt bug thì lấy chính con
bug làm mark, và hai đốm mắt trên cánh trước cũng là đôi mắt đang review.

![Toàn bộ biến thể, trên nền sáng và nền tối](../images/logo/brand-sheet.svg)

## File

| File | Dùng ở đâu |
| --- | --- |
| [`logo.svg`](../images/logo/logo.svg) | Mark trên nền sáng |
| [`logo-dark.svg`](../images/logo/logo-dark.svg) | Mark trên nền tối — tone tối nhất được nâng lên để thân không lẫn vào trang |
| [`logo-lockup.svg`](../images/logo/logo-lockup.svg) | Mark kèm wordmark, nằm ngang. Đây là bản header của README dùng |
| [`logo-lockup-dark.svg`](../images/logo/logo-lockup-dark.svg) | Cùng lockup đó, cho nền tối |
| [`favicon.svg`](../images/logo/favicon.svg) | Mọi chỗ nhỏ — một bản vẽ riêng, đã giản lược |
| [`brand-sheet.svg`](../images/logo/brand-sheet.svg) | Chính sheet ở trên |

## Luật

- Chỉ polygon phẳng: không gradient, không stroke, không glow, không bo góc.
- Bốn tone của một hue, đúng những tone in trên sheet. Không thêm màu nào khác vào palette.
- Dưới khoảng 24px thì dùng `favicon.svg`, không bao giờ thu nhỏ `logo.svg` — các facet nhỏ sẽ nhoè
  thành một khối. Bản giản lược đó giữ lại râu dù gần như không thấy, vì thiếu râu thì đôi cánh chỉ còn
  là hai khối vô danh.
- Chừa quanh mark một khoảng trống ít nhất bằng chiều rộng một cánh.
- Mark tự mang màu của nó. Không đặt lên nền có màu, không đổi màu mark cho khớp nền.

## Sinh lại file

Mọi file trong `images/logo/` đều do một script viết ra từ một định nghĩa hình học duy nhất:

```sh
python3 docs/images/logo/build-moth-assets.py
```

Sửa toạ độ trong script đó, đừng sửa SVG — để các biến thể không lệch nhau. Script idempotent: chạy trên
một checkout không thay đổi thì ghi lại đúng byte cũ.
