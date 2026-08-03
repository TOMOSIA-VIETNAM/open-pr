# open-pr — review PR bằng agent học convention dự án của bạn

[![Latest Release](https://img.shields.io/github/v/release/TOMOSIA-VIETNAM/open-pr?label=release)](https://github.com/TOMOSIA-VIETNAM/open-pr/releases)
[![License: MIT](https://img.shields.io/github/license/TOMOSIA-VIETNAM/open-pr)](./LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-5A32A3)](https://claude.ai/code)

**Tiếng Việt** · [English](./README.md) · [日本語](./README.ja.md)

Plugin Claude Code review Pull/Merge Request và ghi nhớ convention riêng của từng repo, nên review
càng dùng càng sát dự án chứ không lặp lại góp ý chung chung.

Hỗ trợ **GitHub** (`.../pull/<n>`) và **GitLab** (`.../-/merge_requests/<n>`, kể cả self-hosted).
Chưa hỗ trợ Bitbucket.

## Yêu cầu

- [Claude Code](https://claude.ai/code)
- [`gh`](https://cli.github.com/) đã login cho PR GitHub, hoặc [`glab`](https://gitlab.com/gitlab-org/cli) cho MR GitLab — review được post bằng account đó

## Cài

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@review-pr
```

Cập nhật sau này:

```
/plugin marketplace update review-pr
/plugin update open-pr@review-pr
```

Rồi `/reload-plugins` hoặc mở session mới. Repo đã setup bằng bản cũ → chạy `/open-pr:upgrade`
một lần để cập nhật config local.

## Dùng

Command chỉ chạy khi bạn tự gõ.

```
/open-pr:review https://github.com/<owner>/<repo>/pull/<n>
/open-pr:review https://gitlab.com/<owner>/<repo>/-/merge_requests/<n>
```

Review PR và post đúng 1 review: phần tổng quan + comment theo dòng khi cần, mỗi finding gắn
🔴 MUST FIX / 🟠 SHOULD FIX / 🔵 SUGGESTION / 📝 NOTE. PR sạch → **LGTM 🌟**.

Code của PR được checkout ra git worktree riêng nên không đụng tới branch bạn đang làm — vừa review
vừa code bình thường.

```
/open-pr:fix https://github.com/<owner>/<repo>/pull/<n>
```

Đọc finding từ lần review trước rồi sửa **trong working directory của bạn**, mỗi lần chạy gom 1
commit. Finding 🔵/📝 luôn hỏi bạn trước, và chỉ reply lên PR sau khi code đã push.

Thêm chữ sau URL để áp dụng riêng cho lần chạy đó:

```
/open-pr:review https://github.com/org/repo/pull/123 tập trung phần security
/open-pr:fix https://github.com/org/repo/pull/123 chỉ sửa phần security
```

Nhiều PR liên quan trong 1 lần — chạy lần lượt, không song song:

```
/open-pr:review https://github.com/org/repo-a/pull/12 https://github.com/org/repo-b/pull/34
```

## Lần đầu với 1 repo

Plugin hỏi 1 lượt ngắn (ngôn ngữ review, post ngay hay để draft, bao lâu đọc lại tài liệu convention,
ngưỡng PR quá lớn), rồi tự đọc convention repo bạn đã có sẵn — README, CLAUDE.md, AGENTS.md, docs,
wiki, cursor/copilot rules.

Mọi thứ ghi nhớ nằm trong repo được review, tại `notebooks/review/<repo>/` — git local riêng, không
push. Plugin tự thêm đường dẫn này vào `.gitignore`.

| Muốn đổi | Sửa ở |
|---|---|
| Rule riêng của team | `notebooks/review/<repo>/ALWAYS_RULE.md` — mặc định rỗng, viết câu bình thường |
| Ngôn ngữ review, draft/post, auto-resolve, chu kỳ đọc lại, ngưỡng file lớn | `notebooks/review/<repo>/settings.json` |

Hoặc nói thẳng trong chat: **reconfigure review**, **doctor again**, hoặc nêu 1 rule mới cần ghi nhớ.

Tài liệu convention được đọc lại theo chu kỳ (`doctor_schedule`: `"7 days"`, `"2 weeks"`, mặc định
`"1 months"`, hoặc `"never"`) để memory không bị cũ.

## Cần biết

- Stack đã có: Rails, Vue, React, Python, Node.js, Lambda, PHP, Laravel, WordPress, Shell, Makefile,
  và file markdown viết làm instruction cho AI agent. Stack mới sẽ được viết template ngay tại chỗ.
- `/open-pr:review` không sửa code, không close/merge gì cả. Chỉ `/open-pr:fix` mới ghi code, và chỉ
  trong thư mục bạn chạy nó.
- Rule xuất hiện trong comment của PR sẽ được hỏi lại bạn trước khi ghi nhớ.
- Tự viết prompt giao review cho subagent? Cho nó `Read` đúng file command thay vì chép tay lại rule
  — chép tay là lệch.
