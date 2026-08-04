# Backlog: Rewrite văn phong DELTA (MUST / WHEN / SHOULD / WHY)

Mục tiêu: cắt token/dòng cho toàn bộ prompt file trong `src/`, do rationale bị AI tự chèn thêm qua
nhiều vòng fix bug/improve làm phình to không kiểm soát. Áp dụng cho: `commands/review.md`,
`commands/fix.md`, `commands/update-plugin.md` (file mới từ P2 — viết thẳng theo style này, không
cần convert lại), `setup-flow.md`, `cases/*.md` (5 file), `ALWAYS_RULE.md`, `stack-detection.md`,
`templates/*.md` (11 file). WHY vẫn giữ nhưng rút còn 1 cụm từ ngắn (3-8 chữ) gắn liền dòng
MUST/SHOULD, KHÔNG viết cả câu/đoạn văn — theo đúng 2 mẫu POC đã được user duyệt trong phiên grill
trước đó (`cases/post-review.md` full, và `commands/review.md` CRITICAL block + Bước 0-2). 2 mẫu POC
đó là BASELINE khung MUST/WHEN/SHOULD/WHY — bổ sung thêm tầng nén sau (chốt sau khi POC, áp dụng từ
Task D1 trở đi, không cần POC lại):

- **Thuật ngữ kỹ thuật thay diễn giải**: dùng đúng tên kỹ thuật đã biết (`idempotent`, `race
  condition`, `prefix match`...) thay vì giải thích lại bằng câu thường.
- **Mũi tên thay cấu trúc câu dài**: `→` cho trình tự/nhân-quả/dẫn tới, `⇒` cho if-then, dùng nhất
  quán 1 ký hiệu cho 1 quan hệ xuyên suốt file (không đổi nghĩa mũi tên giữa chừng).
- **Toán tử logic thay chữ**: `&&`/`||`/`!` (ưu tiên ASCII, dễ render đúng trong mọi terminal/editor
  hơn ký hiệu toán học `∧∨¬`) thay cho "và"/"hoặc"/"không phải".
- **Emoji làm marker ngữ nghĩa/trạng thái** — nối tiếp tiền lệ đã có sẵn trong repo (🔴🟠🔵📝 severity),
  mở rộng nhất quán (vd ✅/❌ cho pass/fail, ⚠️ cho cảnh báo), KHÔNG dùng trang trí tuỳ tiện.
- **Giới hạn cứng — ưu tiên đủ nghĩa hơn nén tối đa**: bất kỳ kỹ thuật nào ở trên khiến 1 rule đọc
  vào MẤT NGHĨA hoặc MƠ HỒ so với bản gốc → bỏ kỹ thuật đó tại đúng chỗ đó, quay lại viết chữ thường.
  Đây chính là lý do Task D8 (rule-coverage diff) vẫn là cổng chặn bắt buộc — nén thêm không được
  đánh đổi lấy mất rule.

## Task D1: Rewrite `src/cases/post-review.md`
- Acceptance: khớp mẫu POC đã duyệt cho đúng file này (37→26 dòng), CỘNG áp thêm tầng nén mới (mũi
  tên/toán tử/emoji/thuật ngữ) mô tả ở trên tại những chỗ áp được mà không mất nghĩa.
- Dependency: checkpoint của `settings-json-migration.md` đã qua.
- Status: DONE. 37→35 dòng (không có mẫu POC cũ để đối chiếu ký-tự-cho-ký-tự — đã dùng bản HIỆN
  TẠI của file làm gốc theo đúng chỉ dẫn; xem báo cáo cuối). Rule-coverage diff (D8): không mất
  rule nào, 1 lỗi tự phát hiện + tự sửa (thiếu lệnh verify `gh api .../reviews/<review_id> --jq
  '{id, state}'`).

## Task D2: Rewrite `src/commands/review.md`
- Acceptance:
  - CRITICAL block + Bước 0-2 khớp mẫu POC đã duyệt VỀ KHUNG MUST/WHEN/WHY, cộng tầng nén mới
    (không phải giữ nguyên y hệt ký-tự-cho-ký-tự mẫu POC cũ — mẫu cũ là baseline khung, chưa có nén
    thêm).
  - Bước 3-10 (chưa POC) theo ĐÚNG convention MUST/WHEN/WHY + tầng nén mới — cùng từ khoá, cùng kỷ
    luật độ dài WHY.
  - Mọi invariant hiện có trong file gốc vẫn còn hiện diện (xem rule-coverage diff bên dưới) — file
    này mang CRITICAL safety block, load-bearing nhất trong phạm vi rewrite.
- Dependency: D1 (tiền lệ style), checkpoint P3.
- Status: DONE. 500→453 dòng. Rule-coverage diff (D8): so khớp toàn bộ backtick-token +
  emoji/threshold/field-name anchor giữa bản trước rewrite và bản sau — 1 lỗi tự phát hiện + tự sửa
  (dòng mô tả regex canonical URL bị rút gọn thành `'...'` làm mất tính chính xác, đã khôi phục
  regex đầy đủ). Không rule MUST/FORBIDDEN/safety nào bị mất.

## Task D3: Rewrite `src/commands/fix.md`
- Acceptance: cùng convention D2; mọi ràng buộc MUST/allowed-tools được giữ nguyên.
- Dependency: D2.
- Status: DONE. 374→352 dòng. Rule-coverage diff (D8): 0 backtick-token bị mất, mọi anchor
  (decline_needs_confirmation, auto_push, schema_version, bot-finding/bot-reply,
  resolveReviewThread, protected-branch list...) khớp đúng số lần xuất hiện — không cần sửa gì.

## Task D4: Rewrite `src/setup-flow.md`
- Acceptance: Phần A-E đều convert; bảng phân loại field từ Task M1/M3 (đã chốt ở
  settings-json-migration.md) chỉ đổi format sang DELTA, KHÔNG đổi lại mapping field đã chốt.
- Dependency: D3.
- Status: DONE. 367→341 dòng. JSON schema block (Part D) giữ byte-identical (đã diff xác nhận).
  5 field-group + mapping field không đổi tên/nhóm, chỉ đổi format. Rule-coverage diff (D8): các
  chênh lệch backtick-token phát hiện đều là rút gọn văn phong (không mất rule), không cần sửa.

## Task D5: Rewrite `src/cases/*.md` còn lại
- Acceptance: `large-diff-guards.md`, `pr-template-checklist.md`, `re-review.md`,
  `submodule-review.md` đều convert, cùng convention.
- Dependency: D4.
- Status: DONE. large-diff-guards.md 89→83, pr-template-checklist.md 28→24, re-review.md 132→117,
  submodule-review.md 151→140. Rule-coverage diff (D8): pr-template-checklist.md +
  large-diff-guards.md 0 token bị mất; re-review.md/submodule-review.md có vài chênh lệch nhưng đều
  là rút gọn văn phong (vd bỏ lặp từ "settings.json" khi đã nói `.review` node) — không mất rule.

## Task D6: Rewrite `src/ALWAYS_RULE.md` + `src/stack-detection.md`
- Acceptance: tiêu chí baseline (mục 1-4, 6) + bảng mapping stack đều convert; cơ chế placeholder
  `{{OUTPUT_LANGUAGE}}` giữ nguyên (prose xung quanh có thể rút, token placeholder không được đổi).
- Dependency: D5.
- Status: DONE. ALWAYS_RULE.md 59→55, stack-detection.md 35→35 (đã terse sẵn). Bảng mapping stack
  giữ nguyên nội dung/semantics (đối chiếu diff xác nhận, chỉ rút prose xung quanh bảng).
  `{{OUTPUT_LANGUAGE}}` giữ nguyên token, không đổi.

## Task D7: Rewrite `src/templates/*.md` (11 file)
- Acceptance: toàn bộ 11 template stack convert cùng style; mỗi file giữ dòng note metadata
  "_Overlay/baseline_" (đúng pattern soạn template đã ghi trong `CLAUDE.md`).
- Dependency: D6. (Rủi ro thấp hơn D1-D6 — đây là danh sách tiêu chí nội dung, không phải
  control-flow.)
- Status: DONE. 11/11 file convert, đếm bullet-line từng file TRƯỚC/SAU khớp chính xác 1-1 (0 tiêu
  chí bị mất) — xem báo cáo cuối. Cả 11 file đều giữ dòng note "_Overlay..._"/"_Additions to..._".

## Task D8: Rule-coverage diff (cổng validate cho toàn bộ P1)
- Acceptance: với mỗi file đã sửa ở D1-D7, mọi rule MUST/SHOULD/mệnh lệnh có trong bản TRƯỚC P1
  (bản tại checkpoint P3) phải truy vết được trong bản rewrite — làm checklist từng file, báo rule
  nào bị mất/lệch nghĩa, sửa trước khi qua bước sau. Đây là cổng tự động user đã yêu cầu; A/B test
  hành vi thật trên PR thật user tự làm riêng — KHÔNG thuộc phạm vi backlog này.
- Dependency: D7.
- Status: DONE. Snapshot 21 file (bản TRƯỚC rewrite, đúng lúc bắt đầu task này — đã có P2/P3,
  KHÔNG commit) lưu tại `/tmp/delta-baseline/` trước khi Edit. Đối chiếu bằng backtick-token diff +
  numeric/field/emoji anchor grep cho từng file. Tổng cộng 2 lỗi phát hiện + đã tự sửa: (1)
  `post-review.md` thiếu lệnh verify `gh api .../reviews/<review_id> --jq '{id, state}'`; (2)
  `review.md` rút gọn regex canonical URL thành `'...'` làm mất tính chính xác. Sau khi sửa: không
  còn rule MUST/SHOULD/FORBIDDEN nào bị mất trên toàn bộ D1-D7.

## Task D9: Đo token trước/sau bằng tiktoken (ước lượng, chỉ xem con số — KHÔNG phải cổng chặn)
- Acceptance:
  - Với mỗi file đã rewrite ở D1-D7: đếm token bản TRƯỚC (tại checkpoint P3, lấy qua `git show`)
    và bản SAU bằng `tiktoken` (chọn 1 encoding cố định, vd `o200k_base`, ghi rõ encoding đã dùng),
    báo bảng before/after/% giảm.
  - LUÔN ghi kèm disclaimer: đây là tokenizer của OpenAI, không phải tokenizer thật của Claude — số
    chỉ mang tính ước lượng/tham khảo hướng đi (tăng hay giảm), KHÔNG dùng làm bằng chứng tuyệt đối
    (lý do: user không có quyền Console/API để gọi `count_tokens` thật — Pro/Team subscription
    claude.ai không kèm quyền này).
  - Task này KHÔNG chặn tiến độ — chỉ để user xem số tham khảo, không phải điều kiện pass/fail như
    D8.
- Dependency: D7 (chạy song song hoặc sau D8 đều được, không phụ thuộc D8).
- Status: DONE. `tiktoken` 0.9.0 đã có sẵn (không cần cài), dùng encoding `o200k_base`.
  Disclaimer: `o200k_base` là tokenizer OpenAI, không phải tokenizer thật của Claude — số chỉ mang
  tính ước lượng/tham khảo hướng đi, không phải bằng chứng tuyệt đối.

  | File | Dòng trước→sau | Token (o200k_base) trước→sau |
  |---|---|---|
  | `src/cases/post-review.md` | 37→35 | 518→501 |
  | `src/commands/review.md` | 500→453 | 8290→7490 |
  | `src/commands/fix.md` | 374→352 | 6367→5858 |
  | `src/setup-flow.md` | 367→341 | 6889→6155 |
  | `src/cases/large-diff-guards.md` | 89→83 | 1556→1378 |
  | `src/cases/pr-template-checklist.md` | 28→24 | 514→442 |
  | `src/cases/re-review.md` | 132→117 | 2441→2066 |
  | `src/cases/submodule-review.md` | 151→140 | 2261→2077 |
  | `src/ALWAYS_RULE.md` | 59→55 | 485→437 |
  | `src/stack-detection.md` | 35→35 | 589→578 |
  | `src/templates/*.md` (12 file, tổng) | 544→502 | 5908→5372 |
  | **TỔNG (22 file)** | **2413→2237** | **35818→32347 (-9.7%)** |

## Checkpoint (trước khi qua P4 — vendor-layer-extraction.md)
- D8 rule-coverage diff không còn rule nào bị mất chưa xử lý, trên toàn bộ file đã rewrite.
- D9 chỉ cần CÓ số liệu báo cáo, không cần đạt ngưỡng % nào — không phải điều kiện chặn checkpoint.

## Thứ tự: D1 → D2 → D3 → D4 → D5 → D6 → D7 → D8, D9 (song song sau D7)
