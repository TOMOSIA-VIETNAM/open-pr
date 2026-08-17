# Review những gì

[← README](../../README.vi-VN.md)

Sáu trục. **Team rule luôn thắng** cả sáu.

| # | Tiêu chí | Nhìn vào |
| --- | --- | --- |
| 1 | **Bugs & logic** | logic lỗi thấy được, edge case (empty / null / boundary), nhánh điều kiện và error path có được xử lý |
| 2 | **Security** | secret hardcode, input không validate đi thẳng vào query / command / render, thiếu check quyền ở hành động nhạy cảm |
| 3 | **Performance** | gọi API / DB / tính toán lặp lại đáng cache hoặc batch, load cả tập dữ liệu lớn thay vì stream |
| 4 | **Code quality** | tên theo convention dự án, code trùng, một unit làm quá nhiều việc, dead leftover (block comment-out, flag / import không dùng, TODO trỏ task đã xóa) |
| 5 | **Maintainability & readability** | comment ở chỗ logic không hiển nhiên và nói đúng hiện tại (không kể lể quá khứ), test cover happy path lẫn error path, thiết kế còn chỗ cho thay đổi kế tiếp |
| 6 | **Framework / language-specific** | template theo stack: Rails, Vue, React, Python, Node.js, Lambda, PHP, Laravel, WordPress, Shell, Makefile, và cả markdown dùng làm instruction cho AI agent. Stack lạ → viết template tại chỗ |

> [!IMPORTANT]
> Thứ tự khi **conflict**: team rule → memory đã học → template của stack → 5 tiêu chí trên. Team rule luôn thắng.

---

[Kết quả trông như thế nào](./demo.md) · [Cấu hình](./configuration.md)
