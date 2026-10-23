"""Unit tests for src/bin/open-pr-session-title.sh, the UserPromptSubmit hook that names a
session after the PRs given to /open-pr:review or /open-pr:fix.

Each case pipes the hook's JSON input into the script, as Claude Code does, and reads stdout.
The script runs beside the real open-pr.sh, whose `pr-ref` turns each URL into a ref.
"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
SCRIPT = SRC / "bin" / "open-pr-session-title.sh"

GH = "https://github.com/acme/api/pull/12"
GL = "https://gitlab.com/group/sub/web/-/merge_requests/7"
BB = "https://bitbucket.org/team/app/pull-requests/3"
BBS = "https://bb.example.com/projects/PRJ/repos/core/pull-requests/45"


def run(stdin):
    p = subprocess.run(["sh", str(SCRIPT)], input=stdin.encode(), capture_output=True, timeout=60)
    assert p.returncode == 0, p.stderr
    assert p.stderr == b"", "a hook's stderr reaches the user"
    return p.stdout


def title(prompt, **extra):
    out = run(json.dumps({"prompt": prompt, **extra}))
    if not out:
        return None
    body = json.loads(out)
    assert body["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    return body["hookSpecificOutput"]["sessionTitle"]


def test_one_pr_per_vendor_and_role():
    assert title(f"/open-pr:review {GH}") == "review api #12"
    assert title(f"/open-pr:fix {GL}") == "fix web !7"
    assert title(f"/open-pr:review {BB}") == "review app #3"
    assert title(f"/open-pr:fix {BBS}") == "fix core #45"


def test_every_pr_in_prompt_order_without_duplicates():
    prompt = f"/open-pr:review {BB} {GH}/files\n{GL}/diffs {GH}#issuecomment-1 {BBS} {BB} focus on auth"
    assert title(prompt) == "review app #3, api #12, web !7, core #45"


def test_owner_shows_only_when_two_repos_share_a_name():
    assert title("/open-pr:review https://github.com/a/web/pull/1 "
                 f"https://gitlab.com/b/web/-/merge_requests/2 {GH}") == "review a/web #1, b/web !2, api #12"
    assert title("/open-pr:review https://github.com/a/web/pull/1 https://github.com/a/web/pull/2") \
        == "review web #1, web #2"


def test_a_user_title_is_kept():
    for name in ("my name", "review api #12"):
        assert run(json.dumps({"prompt": f"/open-pr:review {GL}", "session_title": name})) == b"", name


def test_other_prompts_are_left_alone():
    for prompt in (f"review {GH}", f"/open-pr:watch {GH}", f"/open-pr:reviewer {GH}",
                   f"please /open-pr:review {GH}", "/open-pr:review", "/open-pr:fix no url here"):
        assert run(json.dumps({"prompt": prompt})) == b"", prompt


def test_prompt_text_is_never_executed(tmp_path):
    marker = tmp_path / "ran"
    evil = (f"/open-pr:review https://github.com/o/$(touch {marker})/pull/1 "
            f"https://github.com/o/`touch {marker}`/pull/2 https://github.com/o/r;touch\x1b[31m/pull/3 "
            f"'\"$HOME\"' {GH}")
    assert title(evil) == "review api #12", "a URL pr-ref cannot read is dropped"
    assert not marker.exists(), "the prompt was evaluated"


def test_a_long_list_is_cut_at_a_ref_boundary():
    urls = " ".join(f"https://github.com/o/repository-number-{i}/pull/{i}" for i in range(25))
    t = title(f"/open-pr:fix {urls}")
    assert len(t.encode()) <= 200 and t.endswith(", …"), t
    refs = t[len("fix "):-len(", …")].split(", ")
    assert refs == [f"repository-number-{i} #{i}" for i in range(len(refs))], refs

    huge = title(f"/open-pr:review https://github.com/o/{'x' * 300}/pull/1")
    assert len(huge.encode()) <= 200 and huge.endswith("…"), huge


def test_bad_input_never_blocks_the_prompt():
    for stdin in ("", "not json", "[1,2]", '"str"', '{"prompt": 5}', "{"):
        assert run(stdin) == b"", stdin


def test_the_plugin_registers_the_hook():
    """Claude Code loads hooks/hooks.json from the plugin root, which is src/ (only src/ ships)."""
    hooks = json.loads((SRC / "hooks" / "hooks.json").read_text())["hooks"]
    cmds = [h["command"] for group in hooks["UserPromptSubmit"] for h in group["hooks"]]
    assert cmds, "no UserPromptSubmit hook"
    for cmd in cmds:
        m = re.fullmatch(r'sh "\$\{CLAUDE_PLUGIN_ROOT\}/(bin/[\w.-]+\.sh)"', cmd)
        assert m, f"the hook must run a script under the plugin root: {cmd}"
        assert (SRC / m.group(1)).is_file(), f"{m.group(1)} does not exist"
