# e2e

Unit tests check the prompt graph as text. They cannot tell you whether a real review, on a real PR,
still comes out right — that needs a real vendor, a real PR and a real agent run. This directory holds
the fixture and the checklist for that.

## The ritual

One e2e run belongs to one PR of this project.

```bash
pip install -r requirements-dev.txt        # once, for the unit suite
e2e/bootstrap.sh --pr 20                   # fixture PR/MR on every vendor you are logged in for
```

It prints the fixture URL and the exact `/open-pr:review` command, and records the URL in this
project's PR #20 description under an `<!-- e2e-fixtures -->` block, so the PR carries its own evidence.

```bash
python3 scripts/vendor_lint.py --pr 20     # every documented Fetch command runs, read-only, free
```

Run that before spending a model call: a broken vendor command makes every checklist row fail for a
reason unrelated to the rules under test.

Then run `/open-pr:review <fixture url>` in a Claude Code session with the plugin installed, and work
through `checklist.md`. It maps every planted defect to the code path it exercises, so a miss tells you
WHICH rule regressed rather than just "the review looked worse".

For the `/open-pr:fix` half, get a working copy on the fixture branch — this writes nothing to the
remote, so a review already posted keeps its commit anchors:

```bash
e2e/bootstrap.sh --pr 20 --checkout --clone-dir /tmp/fixture
```

FORBIDDEN meanwhile: re-running the seeding mode on a `--pr` whose review is already posted. It
force-pushes the branch and strands the anchors that review points at.

```bash
e2e/bootstrap.sh --pr 20 --teardown        # close the fixture PR/MR, delete its branch
```

Teardown never touches the repo itself — only the PR and the branch it created.

## Targets and access

`targets.env` names the fixture repos:

| vendor | repo |
|---|---|
| GitHub | `tms-minhtang1/open-pr-test` |
| GitLab | `minhtang1/open-pr-test` |

Both are public, so anyone can read the resulting review. Pushing needs write access, which is the one
thing a contributor may not have. Both paths work:

- **Write access** → run the commands above as they are.
- **No write access** → fork the fixture repo and pass `--repo <your-fork>`. The script checks the
  permission up front and tells you which of the two applies, rather than failing at push time.

Logged in for GitHub only? The GitLab half skips with a message — nothing to configure. To add GitLab:

```bash
glab auth login --hostname gitlab.com     # paste a PAT with the `api` scope
```

CI never runs e2e: it costs a real model call and posts to a real vendor, and a fork PR is given no
secrets. `.github/workflows/e2e.yml` exists so the maintainer can drive the same fixture by hand.

## What the fixture plants

9 defects across 5 files, each aimed at a different path: the Rails template, the embedded-prompt
overlay on a `.py`, agent-instructions on a `.md`, the large-dump-file guard, and the PR-template
checklist. `fixtures/base/` is the state of `main`, `fixtures/pr/` overwrites it on the branch, and that
difference is the diff under review. The 40KB dump is generated at bootstrap, not committed here.

Being model output, a review is never byte-identical twice — assert on shape, which is what the
checklist does.
