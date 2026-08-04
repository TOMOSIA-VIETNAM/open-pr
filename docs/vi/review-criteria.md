# Nó review những gì

[← README](../../README.vi.md)

| #   | Tiêu chí             | Nhìn vào                                                                                                                                                        |
| --- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Bug & logic**      | lỗi logic thấy được, edge case (rỗng/null/giới hạn), nhánh điều kiện và đường lỗi có được xử lý                                                                 |
| 2   | **Security**         | secret hardcode, input không kiểm tra đi thẳng vào query/command/render, thiếu check quyền ở hành động nhạy cảm                                                 |
| 3   | **Performance**      | gọi API/DB/tính toán lặp lại đáng cache hoặc batch, load cả tập dữ liệu lớn thay vì stream                                                                      |
| 4   | **Chất lượng code**  | tên có theo convention dự án, code trùng, một unit làm quá nhiều việc, tàn dư chết (block comment-out, flag/import không dùng, TODO trỏ tới task đã xoá)        |
| 5   | **Dễ bảo trì & đọc** | comment ở chỗ logic không hiển nhiên và nói đúng hiện tại (không kể lể quá khứ), test cover cả happy path lẫn error path, thiết kế còn chỗ cho thay đổi kế tiếp |


**Tiêu chí 6** là phần đặc thù framework/language, do template của từng stack nắm: Rails, Vue, React,
Python, Node.js, Lambda, PHP, Laravel, WordPress, Shell, Makefile, và cả file markdown viết làm
instruction cho AI agent. Gặp stack lạ, nó viết template ngay tại chỗ.

Thứ tự ưu tiên khi có xung đột: rule của team → memory đã học → template của stack → 5 tiêu chí trên.
Rule của team luôn thắng.
