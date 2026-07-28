# open-pr — PR review, by an agent that learns your project

[![Latest Release](https://img.shields.io/github/v/release/TOMOSIA-VIETNAM/open-pr?label=release)](https://github.com/TOMOSIA-VIETNAM/open-pr/releases)
[![License: MIT](https://img.shields.io/github/license/TOMOSIA-VIETNAM/open-pr)](./LICENSE)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-5A32A3)](https://claude.ai/code)

[Tiếng Việt](./README.vi.md) · **English** · [日本語](./README.ja.md)

A Claude Code plugin that reviews Pull/Merge Requests and remembers each repo's own conventions, so
reviews get closer to your project every time instead of repeating generic advice.

Works with **GitHub** (`.../pull/<n>`) and **GitLab** (`.../-/merge_requests/<n>`, self-hosted
included). Bitbucket is not supported yet.

## Requirements

- [Claude Code](https://claude.ai/code)
- [`gh`](https://cli.github.com/) logged in for GitHub PRs, or [`glab`](https://gitlab.com/gitlab-org/cli) for GitLab MRs — the review is posted through that account

## Install

```
/plugin marketplace add TOMOSIA-VIETNAM/open-pr
/plugin install open-pr@review-pr
```

Update later:

```
/plugin marketplace update review-pr
/plugin update open-pr@review-pr
```

Then `/reload-plugins` or start a new session. In a repo you set up with an older version, run
`/open-pr:update-plugin` once to bring its local config up to date.

## Use

Commands run only when you type them.

```
/open-pr:review https://github.com/<owner>/<repo>/pull/<n>
/open-pr:review https://gitlab.com/<owner>/<repo>/-/merge_requests/<n>
```

Reviews the PR and posts one review: an overview plus line comments where needed, each finding
tagged 🔴 MUST FIX / 🟠 SHOULD FIX / 🔵 SUGGESTION / 📝 NOTE. A clean PR gets **LGTM 🌟**.

The PR code is checked out into its own git worktree, so your current branch is never touched — you
can keep working while a review runs.

```
/open-pr:fix https://github.com/<owner>/<repo>/pull/<n>
```

Reads the findings from a previous review and fixes them **in your working directory**, one commit
per run. It asks before acting on 🔵/📝 findings, and replies on the PR once the code is pushed.

Extra words after the URL apply to that run only:

```
/open-pr:review https://github.com/org/repo/pull/123 focus on security
/open-pr:fix https://github.com/org/repo/pull/123 only the security parts
```

Several related PRs in one go — passed one after another, not in parallel:

```
/open-pr:review https://github.com/org/repo-a/pull/12 https://github.com/org/repo-b/pull/34
```

## First run on a repo

It asks a short batch of setup questions once (review language, post immediately or keep as a draft,
how often to re-read your convention docs, thresholds for large PRs), then reads whatever conventions
your repo already documents — README, CLAUDE.md, AGENTS.md, docs, wiki, cursor/copilot rules.

Everything it remembers lives in the repo you review, at `notebooks/review/<repo>/` — its own local
git, never pushed. The plugin adds that path to your `.gitignore`.

| To change | Edit |
|---|---|
| Your team's own review rules | `notebooks/review/<repo>/ALWAYS_RULE.md` — starts empty, write plain sentences |
| Review language, draft vs post, auto-resolve, refresh cycle, size thresholds | `notebooks/review/<repo>/settings.json` |

Or just say it in chat: **reconfigure review**, **doctor again**, or a new rule you want remembered.

Convention docs are re-read on a schedule (`doctor_schedule`: `"7 days"`, `"2 weeks"`, `"1 months"`
by default, or `"never"`) so memory doesn't go stale.

## Good to know

- Stacks covered: Rails, Vue, React, Python, Node.js, Lambda, PHP, Laravel, WordPress, Shell,
  Makefile, and markdown written as instructions for an AI agent. A new stack gets a template
  written on the spot.
- `/open-pr:review` never edits code, never closes or merges anything. Only `/open-pr:fix` writes
  code, and only in the directory you run it from.
- A rule suggested inside a PR comment is confirmed with you before it is remembered.
- Delegating a review to your own subagent? Have it `Read` the command file rather than retyping the
  rules — a paraphrase drifts.
