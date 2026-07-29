# e2e

Unit tests check the prompt graph as text. They cannot tell you whether a real review, on a real PR,
still comes out right — that needs a real vendor, a real PR and a real agent run. This directory holds
the fixture and the checklist for that.

## Who can run it

**Anyone, with their own credentials.** There is no shared test repo and no shared secret, because a
shared repo would need shared write access. Instead `bootstrap.sh` CREATES the fixture in whichever
namespace your own `gh` / `glab` is logged into. Your PAT, your throwaway repo, your teardown.

Practical consequences:

- Authenticated for GitHub only? The GitLab half is skipped with a message. Nothing to configure.
- Contributors do not need anything from the maintainer.
- CI does not run this. It costs a real model run and posts to a real vendor, and a fork PR gets no
  secrets. `.github/workflows/e2e.yml` exists for the maintainer to trigger by hand.

## Prerequisites

| vendor | CLI | scope needed |
|---|---|---|
| GitHub | `gh auth login` | `repo` — create a private repo, open a PR |
| GitLab | `glab auth login` | `api` — same, plus MR creation |

Plus the plugin installed in the Claude Code session you will run the review from.

## Run

```bash
e2e/bootstrap.sh                 # both vendors you are logged in for
e2e/bootstrap.sh --vendor github
```

It prints the PR/MR URL and the exact command to paste. Then work through `checklist.md`, which maps
every planted defect to the code path it exercises, so a miss tells you WHICH rule regressed.

```bash
e2e/bootstrap.sh --teardown      # delete the fixture repo when done
```

`--recreate` replaces an existing fixture. The script refuses any repo name that does not contain
`open-pr-test`, so it cannot delete something real by accident.

## What the fixture plants

9 defects across 5 files, each aimed at a different path: the Rails template, the embedded-prompt
overlay on a `.py`, the agent-instructions template on a `.md`, the large-dump-file guard, and the
PR-template checklist. `fixtures/base/` is the state of `main`; `fixtures/pr/` overwrites it on the
branch, so the diff is what gets reviewed.

Being model output, a review is never byte-identical twice — assert on shape, which is what the
checklist does.
