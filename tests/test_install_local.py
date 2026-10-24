"""scripts/install-local.sh against a fake `claude` CLI: what it asks Claude Code to do."""
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "install-local.sh"

FAKE_CLAUDE = """#!/bin/sh
echo "$*" >> "$FAKE_LOG"
[ "$1 $2" = "plugin list" ] && [ -n "$FAKE_INSTALLED" ] && echo "open-pr@open-pr  user  enabled"
exit "${FAKE_EXIT:-0}"
"""


def run_claude_install(tmp_path, installed, fail=""):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)
    log = tmp_path / "claude.log"
    log.write_text("")
    env = {**os.environ, "HOME": str(tmp_path / "home"), "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
           "FAKE_LOG": str(log), "FAKE_INSTALLED": "1" if installed else "", "FAKE_EXIT": fail}
    r = subprocess.run(["bash", str(SCRIPT), "--platform", "claude"], capture_output=True, text=True,
                       env=env, stdin=subprocess.DEVNULL, timeout=60)
    return r, [l.split(" ")[:3] for l in log.read_text().splitlines()]


def test_a_first_install_adds_the_marketplace_and_installs(tmp_path):
    r, calls = run_claude_install(tmp_path, installed=False)
    assert r.returncode == 0, r.stderr
    assert ["plugin", "install", "open-pr@open-pr"] in calls
    assert ["plugin", "update", "open-pr@open-pr"] not in calls


def test_an_installed_copy_is_updated_to_this_checkout_not_left_as_it_was(tmp_path):
    """`claude plugin install` leaves an installed plugin at its old version."""
    r, calls = run_claude_install(tmp_path, installed=True)
    assert r.returncode == 0, r.stderr
    assert ["plugin", "update", "open-pr@open-pr"] in calls
    assert ["plugin", "install", "open-pr@open-pr"] not in calls
    assert "Restart Claude Code" in r.stdout


@pytest.mark.parametrize("installed", [False, True])
def test_a_failing_claude_cli_is_reported(tmp_path, installed):
    r, _ = run_claude_install(tmp_path, installed=installed, fail="1")
    assert r.returncode == 1 and "failed" in r.stderr
