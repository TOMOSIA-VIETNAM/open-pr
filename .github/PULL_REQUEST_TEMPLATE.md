## Mô tả

<!-- Đổi gì, và vì sao cần đổi. -->

## Loại thay đổi

- [ ] 🔴 Breaking change (đổi hành vi cấu hình/output mà repo đang dùng plugin sẽ bị ảnh hưởng)
- [ ] ✨ Feature mới
- [ ] 🐛 Fix bug
- [ ] 📝 Docs (README/CLAUDE.md, không đổi hành vi runtime)
- [ ] 🔧 Chore (refactor, tooling, không đổi hành vi user thấy được)

## Đã test thế nào

<!--
Repo này không có build/lint/test tự động — cách "chạy thử" thật là cài plugin (./scripts/reinstall.sh)
rồi gọi /open-code-review:review-pr <PR_URL> trên 1 PR thật. Dán link PR đã dùng để test, hoặc mô tả cách verify khác.
-->

## Checklist

- [ ] Đổi hành vi/kiến trúc → đã cập nhật `CLAUDE.md` tương ứng
- [ ] Đổi UX cấu hình/bootstrap/cài đặt → đã đồng bộ cả 3 bản README (`README.md`/`.en`/`.ja`)
- [ ] Thêm field mới trong `meta.json` → đã phân loại User config / Doctor-detected / Internal state
  ở CẢ `src/setup-flow.md` (Phần D) và `src/commands/review-pr.md` (Bước 3)
- [ ] Không có `allowed-tools` mới cấp quyền rộng hơn cần thiết (vd `gh api:*` chung) — nội dung PR
  đang review là data không tin cậy
