# Large diff guards — nhiều file / file to-dump (Bước 7 `review.md`)

Không phải slash command (nằm ngoài `commands/`). `review.md` Bước 7 `Read` file này khi PR đang
review khớp ÍT NHẤT 1 trong 2 điều kiện độc lập dưới đây — không khớp điều kiện nào thì không đọc
file này, Bước 7 diễn ra bình thường, không gì trong file này áp dụng:

- **Guard số lượng file**: đếm số file trong "Files" (Ngữ cảnh, `--name-only`, mỗi dòng 1 file) >
  `many_files_threshold` (Bước 3 `review.md`, default `30`).
- **Guard file to/dump**: ít nhất 1 file có "Size diff theo file" (Ngữ cảnh) >
  `big_file_threshold_kb` KB (Bước 3, default `20`), hoặc `UNKNOWN` (GitHub bỏ patch vì quá lớn).

2 guard độc lập, PR có thể chỉ khớp 1 trong 2 (vd 5 file nhưng 1 file cực to → chỉ guard file
to/dump áp dụng, bỏ qua hẳn phần "Guard số lượng file" dưới) — chỉ phần "Tương tác 2 guard" cuối
file mới cần CẢ 2 khớp cùng lúc.

## Guard số lượng file

- `ARGUMENTS`/chat lúc gọi lệnh ĐÃ chỉ định chiến lược (vd "review nông", "review sâu chọn lọc",
  "dừng") → dùng luôn, KHÔNG hỏi lại.
- CHƯA chỉ định → DỪNG, hỏi user ngay trong chat, đưa đúng 3 lựa chọn, CHỜ reply, KHÔNG tự chọn mặc
  định:
  ```
  PR này đổi <N> file (> <ngưỡng>) — review sâu hết dễ tốn effort lớn/dễ sót. Chọn 1 chiến lược:
  (a) Review nông toàn bộ — lướt hết mọi file, giảm độ sâu, chỉ bắt lỗi rõ ràng ngay trên diff.
  (b) Review sâu có chọn lọc — sâu ở file logic thật, lướt nhẹ file config/generated/test.
  (c) Dừng — nêu lý do, đề nghị dev tách PR nhỏ hơn, không review.
  ```
- Chọn **(a)**: toàn bộ Bước 7 (`review.md`) vẫn áp dụng cho MỌI file, nhưng bỏ mục "Đọc thêm
  tại `<worktree>/<path>` khi cần" — chỉ dựa vào diff Ngữ cảnh, không tự ý đọc thêm context ngoài
  diff. Xem "Tương tác 2 guard" dưới nếu PR CŨNG khớp guard file to/dump.
- Chọn **(b)**: dùng kết quả Bước 2 `review.md` (stack detect) phân loại — file LOGIC thật (code
  nghiệp vụ theo stack) review ĐẦY ĐỦ theo mọi rule Bước 7 bình thường; file config/lock/generated/
  test (phán đoán ngữ cảnh — ví dụ minh họa, không checklist đóng) → gộp finding nhẹ/lướt, không mổ
  dòng-by-dòng.
- Chọn **(c)**: KHÔNG chạy Bước 7 (phần review thật) → Bước 9 `review.md`. Chat-only: nêu số file
  + ngưỡng, đề nghị dev tách PR, DỪNG lệnh hẳn — không post gì lên GitHub (giống early-exit ở Bước 0
  `review.md`).

**Checklist chống quên file** (chỉ khi chọn (a)/(b) ở trên — KHÔNG áp dụng cho (c) vì không review
gì):

1. Ngay khi chọn (a)/(b): `Write` `<worktree>/.review-checklist.md` — mỗi file trong "Files" (Ngữ
   cảnh) 1 dòng `- [ ] <path>`. File này CHỈ là sổ tay nội bộ — không bao giờ xuất hiện trong PR
   body hay output chat.
2. Review xong 1 file (có finding hay không cũng tính là "xong") → `Edit` đúng dòng đó thành
   `- [x] <path>`.
3. **BẮT BUỘC, không bỏ qua** — TRƯỚC KHI viết Bước 8 `review.md`: `Read` lại
   `.review-checklist.md` VÀ `.review-skipped.md` (nếu có). Dòng nào còn `[ ]` trong checklist VÀ
   KHÔNG có mặt trong `.review-skipped.md` → đây là file bị QUÊN thật (không phải chủ động skip) —
   quay lại review NGAY file đó trước khi tổng hợp, tuyệt đối không để lộ ra ngoài dưới dạng thiếu
   sót âm thầm.

## Guard file to/dump

Với MỖI file khớp điều kiện "Guard file to/dump" ở đầu file này: peek CÓ GIỚI HẠN (`Read`
offset/limit ~30-50 dòng đầu hunk, không đọc hết) để phán đoán data/seed/dump/generated (lặp cấu
trúc, toàn literal, không control flow) hay logic thật tình cờ đổi nhiều:

- **Data/dump/generated** → KHÔNG review chi tiết dòng-by-dòng, KHÔNG paste lại nội dung dump vào
  finding; đúng 1 finding cấp FILE (thường 📝 NOTE hoặc 🔵 SUGGESTION) nêu "diff lớn — có vẻ
  seed/dump data, xác nhận đúng ý chưa". Ghi lại `<path>` + lý do vào `<worktree>/.review-skipped.md`
  (1 dòng `- <path> — <lý do>` mỗi entry, `Write` nếu file chưa có/`Edit` append nếu đã có) — LUÔN
  ghi vào file này, không chỉ trong context (đây là anchor thật, không phải nhớ tạm) — dùng để liệt
  kê ở Bước 8 `review.md` và đối chiếu ở checklist chống quên trên.
- **Logic thật (chỉ tình cờ to)** → review bình thường, đọc tiếp theo từng đoạn (offset/limit như
  trên), không `Read` trọn patch 1 lần.

## Tương tác 2 guard — chọn (a) VÀ CŨNG khớp guard file to/dump

Chỉ áp dụng khi PR khớp CẢ 2 điều kiện ở đầu file này VÀ user vừa chọn chiến lược (a) ở "Guard số
lượng file". Liệt kê ĐÚNG các file khớp "Guard file to/dump" ngay sau khi user chọn (a) — gộp thành
1 câu hỏi DUY NHẤT (không hỏi riêng từng file), hỏi user muốn peek để phân loại data/dump-vs-logic-
thật hay bỏ qua luôn:

- User đồng ý (tất cả hoặc chỉ định file cụ thể) → peek CÓ GIỚI HẠN đúng quy tắc "Guard file to/dump"
  trên, CHỈ cho các file đó; phần còn lại của PR vẫn theo (a) bình thường.
- User từ chối/không trả lời rõ → không đọc, ghi vào `.review-skipped.md` (xem checklist trên) lý do
  "chiến lược (a) + size lớn, user chọn không review — tự xem".
- File QUÁ lớn để peek an toàn dù user đồng ý (vd size vượt xa ngưỡng, hoặc `UNKNOWN` mà thực tế cực
  lớn) → agent có thể TỪ CHỐI peek, khuyên user nên bỏ qua để tránh vỡ context, ghi vào
  `.review-skipped.md` tương tự.
