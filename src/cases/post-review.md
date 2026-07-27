# Post-review — lỗi POST hoặc verify lệch (Bước 9 `review.md`)

Không phải slash command. `review.md` Bước 9 chỉ `Read` file này khi:

- lệnh `POST .../pulls/{pull_number}/reviews` trả lỗi (vd 422), **hoặc**
- verify `state` lệch kỳ vọng so với `auto_submit_review`.

Happy path (POST OK + state đúng) → không đọc file này.

## Khi POST lỗi

1. Đọc thông báo lỗi; đối chiếu schema Bước 9 (`comments[]` thiếu `line`? `line`/`side` sai nửa
   diff?).
2. Sửa payload → gọi lại **đúng 1 lần**.
3. Vẫn lỗi → DỪNG, báo lỗi thật cho user. Không thử thêm cách khác.
4. CẤM tạo/xoá review hoặc comment thử ("test", "isolate") trên PR thật để debug.
5. Lỗi vì `gh auth` chính là tác giả PR (GitHub hạn chế tự review) → chỉ báo user, không workaround.

Không dùng `gh pr review --comment` hay POST lẻ `/pulls/{n}/comments` — chỉ
`POST .../pulls/{n}/reviews`.

## Khi verify lệch

Sau `gh api .../reviews/<review_id> --jq '{id, state}'` (`<review_id>` lấy từ response POST ở Bước 9
— hoặc từ lần retry gọi lại ở mục trên nếu POST đầu lỗi. CẤM đổi qua `.../reviews --jq '.[-1] | ...'`
để "lấy review mới nhất" — nếu có review khác submit đúng lúc này, `.[-1]` trỏ NHẦM review của họ):

- `auto_submit_review: true` mà vẫn `PENDING` dù đã gửi `event` → submit:
  `gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/events -f event="COMMENT"`.
- `auto_submit_review: false` mà `state` không phải `PENDING` → báo user kết quả thật; không tự
  APPROVE/REQUEST_CHANGES hay post thêm review.

Không thêm bước verify khác (không re-fetch diff, không liệt kê lại comment, không tạo review test).
