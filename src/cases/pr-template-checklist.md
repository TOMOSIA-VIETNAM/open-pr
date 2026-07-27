# PR template checklist — đối chiếu description với checklist tự đặt của dự án (Bước 7 `review.md`)

Không phải slash command (nằm ngoài `commands/`). `review.md` Bước 7 `Read` file này khi
`meta.json.pr_template_paths` (đọc ở Bước 3) không rỗng — rỗng (dự án không có PR template nào) thì
bỏ qua hoàn toàn, không đọc file này, không tạo finding nào cho mục này.

Khác 2 mục kiểm tra title/description và branch-ticket-prefix ở Bước 7 (chỉ overview, không tính
severity) — mục này CÓ tính là 1 finding cấp FILE trong 3 mức nghiêm trọng ở Bước 8, vì đây là vi
phạm 1 rule dự án đã tự đặt ra qua PR template, không chỉ là góp ý phong cách.

Đọc nội dung (các) file tại (các) path trong `pr_template_paths` bằng `Read` **tại `<worktree>/<path>`**
(worktree tạo ở Bước 1 của `review.md` — KHÔNG phải path trực tiếp ở pwd; `pr_template_paths` do doctor
detect trên cây thư mục pwd lúc setup, nhưng nội dung file THẬT của PR này phải đọc từ code đã
checkout trong worktree, phòng trường hợp chính PR đang review sửa luôn cả file template), đối chiếu
với `body` thật của PR (đã lấy ở block "Ngữ cảnh"). Tìm dấu hiệu còn sót lại chưa điền — vd checkbox `- [ ]`
còn chưa tick, hoặc 1 section của template còn nguyên văn bản hướng dẫn/placeholder/HTML-comment
gốc thay vì nội dung thật của PR. Đây là phán đoán ngữ cảnh, KHÔNG có danh sách cứng "mục nào bắt
buộc phải điền".

Phát hiện ≥1 chỗ chưa điền → gộp thành ĐÚNG 1 finding TỔNG HỢP (liệt kê các mục còn thiếu trong
cùng 1 finding, KHÔNG tách vụn mỗi checkbox thành 1 finding riêng) theo khung finding của Bước 7
(`🟠 <mô tả ngắn>` + dòng `**Gợi ý**` — KHÔNG label "Vấn đề"). Finding này xếp mức **🟠 SHOULD
FIX**, là finding cấp **FILE** (không gắn 1 dòng code cụ thể) nên vào body Bước 8 dưới heading
`#### 🟠 SHOULD FIX`, KHÔNG vào `comments[]` ở Bước 9.
