"""Unit tests for src/bin/open-pr.sh.

The script is the plugin's deterministic half, so unlike the prompt files it has a real
runtime to exercise. Vendor CLIs are replaced by shims on PATH that log their argv and
answer canned JSON; git runs for real against throwaway fixture repos, because the
worktree/gate/merge-base logic is exactly what must not be faked.

vendor_lint.py covers what shims cannot: that a flag exists on the real gh/glab.
"""

import json
import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "src" / "bin" / "open-pr.sh"


def run(*args, cwd=None, env_extra=None, check=False):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([str(CLI), *args], capture_output=True, text=True,
                       cwd=cwd, env=env, timeout=60)
    if check and r.returncode != 0:
        raise AssertionError(f"open-pr.sh {' '.join(args)} failed:\n{r.stderr}")
    return r


def make_shim(dirp, name, body):
    p = dirp / name
    p.write_text("#!/bin/sh\n" + body)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Every run reads its data directory from an isolated user-level config, never the
    developer's real one."""
    conf = tmp_path / "xdg"
    data = tmp_path / "open-pr-data"
    (conf / "open-pr").mkdir(parents=True)
    (conf / "open-pr" / "config.json").write_text(json.dumps({"data_dir": str(data)}))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(conf))
    return data


# ------------------------------------------------------------------ help ----

@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_prints_the_contract_without_any_dependency(flag, tmp_path):
    """--help must answer even where jq is missing — it is how a user learns what to install."""
    (tmp_path / "cat").symlink_to(subprocess.run(["sh", "-c", "command -v cat"], capture_output=True,
                                                 text=True, check=True).stdout.strip())
    r = subprocess.run(["/bin/sh", str(CLI), flag], capture_output=True, text=True,
                       env={"PATH": str(tmp_path)})   # cat only — no jq, no vendor CLI
    assert r.returncode == 0 and r.stdout.startswith("usage: open-pr.sh"), r.stderr
    for header in ("Common options:", "Subcommands:", "Exit codes:"):
        assert header in r.stdout


def test_unknown_subcommand_points_at_help():
    r = run("nope")
    assert r.returncode == 1 and "see --help" in r.stderr


# ------------------------------------------------------------ selftest ----

# Stands in for macOS: `uname -s` says Darwin, and osascript does what the menu bar and the toast
# do once on screen — the menu bar writes its pid to its pid file, the toast creates its last argv
# — unless FAKE_NO_UI (one that crashed or hung first). Never a real window in this suite.
FAKE_OSASCRIPT = """printf '%s\\n' "$*" >> "$FAKE_LOG"
if [ -z "${FAKE_NO_UI:-}" ]; then
    case "$3" in
        *open-pr-menubar.js) printf '%s\\n' "$$" > "$6" ;;
        *open-pr-toast.js) for a; do last=$a; done; : > "$last" ;;
    esac
fi
[ -z "${FAKE_SIGNAL:-}" ] || kill -"$FAKE_SIGNAL" $$
[ -z "${FAKE_SLEEP:-}" ] || exec sleep "$FAKE_SLEEP"
exit "${FAKE_EXIT:-0}"
"""
SELFTEST_LINE = r"^(ok|fail|skip) (platform|tools|jq|jxa): .+$"


@pytest.fixture
def mac(tmp_path):
    d = tmp_path / "macbin"
    d.mkdir()
    real = subprocess.run(["sh", "-c", "command -v uname"], capture_output=True, text=True, check=True).stdout.strip()
    make_shim(d, "uname", f'[ "$1" = -s ] && {{ echo Darwin; exit 0; }}\nexec "{real}" "$@"\n')
    make_shim(d, "osascript", FAKE_OSASCRIPT)
    log = tmp_path / "osascript.log"
    return {"PATH": f"{d}{os.pathsep}{os.environ['PATH']}", "FAKE_LOG": str(log), "TMPDIR": str(tmp_path)}, log


def test_selftest_prints_one_line_per_registered_check(mac):
    env, log = mac
    r = run("selftest", env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert [l.split()[1] for l in lines] == ["platform:", "tools:", "jq:", "jxa:"]
    assert all(__import__("re").match(SELFTEST_LINE, l) for l in lines), lines
    assert lines[3] == "ok jxa: menu bar ok, toast ok"
    calls = log.read_text().splitlines()
    assert len(calls) == 2 and all(c.split()[3] == "--probe" for c in calls), \
        "both scripts start hidden, in probe mode"
    tmp = env["TMPDIR"]
    assert all(a.startswith(tmp) for c in calls for a in c.split() if a.startswith("/") and "/bin/" not in a), \
        "the probe writes only into its own temp dir, never a watcher's state"
    assert not list(Path(tmp).glob("open-pr-selftest.*")), "the probe left its temp dir behind"


@pytest.mark.parametrize("env, says", [({"FAKE_NO_UI": "1"}, "menu bar: exit 0, no item"),
                                       ({"FAKE_EXIT": "139"}, "menu bar: exit 139")])
def test_a_menu_bar_or_toast_that_never_shows_fails_selftest(mac, env, says):
    base, _ = mac
    r = run("selftest", env_extra={**base, **env})
    assert r.returncode == 1
    jxa = r.stdout.splitlines()[3]
    assert jxa.startswith("fail jxa: ") and says in jxa and "toast: exit" in jxa, jxa


def test_a_hung_probe_is_stopped_within_its_bound(mac):
    base, log = mac
    started = time.time()
    r = run("selftest", env_extra={**base, "FAKE_NO_UI": "1", "FAKE_SLEEP": "60"})
    assert r.returncode == 1 and time.time() - started < 20
    out = subprocess.run(["pgrep", "-f", "sleep 60"], capture_output=True, text=True).stdout.split()
    mine = [p for p in out if str(base["TMPDIR"]) in subprocess.run(
        ["ps", "-o", "command=", "-p", p], capture_output=True, text=True).stdout]
    assert not mine and "fail jxa:" in r.stdout


def test_selftest_reports_a_jq_older_than_1_6_and_still_runs_every_check(mac, tmp_path):
    base, _ = mac
    real = subprocess.run(["sh", "-c", "command -v jq"], capture_output=True, text=True, check=True).stdout.strip()
    d = tmp_path / "oldjq"
    d.mkdir()
    make_shim(d, "jq", f'[ "$1" = --version ] && {{ echo jq-1.5; exit 0; }}\nexec "{real}" "$@"\n')
    r = run("selftest", env_extra={**base, "PATH": f"{d}{os.pathsep}{base['PATH']}"})
    assert r.returncode == 1
    lines = r.stdout.splitlines()
    assert lines[2] == "fail jq: jq-1.5: 1.6 or newer is required" and len(lines) == 4


def test_a_jq_that_crashes_is_reported_as_a_crash_never_as_a_broken_config(mac, tmp_path, data_dir):
    """Reading "not a JSON object" the user would delete a config no jq ever read."""
    base, _ = mac
    d = tmp_path / "segvjq"
    d.mkdir()
    make_shim(d, "jq", "kill -SEGV $$\n")
    env = {**base, "PATH": f"{d}{os.pathsep}{base['PATH']}"}
    r = run("data-dir", env_extra=env)
    assert r.returncode == 139 and "killed by a signal" in r.stderr and "delete it" not in r.stderr
    r = run("selftest", env_extra=env)
    assert r.returncode == 1 and r.stdout.splitlines()[2].startswith("fail jq: jq --version exited 139")
    # dash (sh on Debian/Ubuntu) prints "Segmentation fault" on stderr; it must not reach the line
    if shutil.which("dash"):
        r = subprocess.run(["dash", str(CLI), "selftest"], capture_output=True, text=True,
                           env={**os.environ, **env}, timeout=60)
        assert r.returncode == 1 and r.stdout.splitlines()[2] == "fail jq: jq --version exited 139 "


def test_selftest_probes_the_jq_idioms_not_only_the_version(mac, tmp_path):
    """A jq that reports a good version but passes `-e -n input` on empty input would let an empty
    config read as unset."""
    base, _ = mac
    real = subprocess.run(["sh", "-c", "command -v jq"], capture_output=True, text=True, check=True).stdout.strip()
    d = tmp_path / "oddjq"
    d.mkdir()
    make_shim(d, "jq", f'[ "$1 $2 $3" = "-e -n input | type == \\"object\\"" ] && exit 0\nexec "{real}" "$@"\n')
    r = run("selftest", env_extra={**base, "PATH": f"{d}{os.pathsep}{base['PATH']}"})
    assert r.returncode == 1
    assert r.stdout.splitlines()[2].startswith("fail jq: ") and "passes on empty input" in r.stdout


def test_selftest_fails_a_jq_that_reads_malformed_json_as_valid(mac, tmp_path):
    """The watcher reads a `claude agents` listing through `[inputs]`: a jq exiting 0 on a parse error
    would hand a half-read listing on as if it were whole."""
    base, _ = mac
    real = subprocess.run(["sh", "-c", "command -v jq"], capture_output=True, text=True, check=True).stdout.strip()
    d = tmp_path / "laxjq"
    d.mkdir()
    make_shim(d, "jq", f'[ "$1 $2 $3" = "-c -n [inputs]" ] && {{ echo "[]"; exit 0; }}\nexec "{real}" "$@"\n')
    r = run("selftest", env_extra={**base, "PATH": f"{d}{os.pathsep}{base['PATH']}"})
    assert r.returncode == 1
    assert r.stdout.splitlines()[2].startswith("fail jq: ") and "[inputs] passes malformed JSON" in r.stdout


def selftest(env, shell=None, *args):
    """`selftest` under `shell` (None: the script's own shebang): every check prints exactly one
    line, whatever fails or crashes."""
    cmd = [shell, str(CLI)] if shell else [str(CLI)]
    r = subprocess.run([*cmd, "selftest", *args], capture_output=True, text=True,
                       env={**os.environ, **env}, timeout=60)
    lines = r.stdout.splitlines()
    assert len(lines) == 4 and all(__import__("re").match(SELFTEST_LINE, l) for l in lines), r.stdout + r.stderr
    return r, dict(l.split(": ", 1)[0].split()[::-1] for l in lines), lines


SHELLS = [None] + (["dash"] if shutil.which("dash") else [])


@pytest.fixture
def linux(tmp_path):
    """`uname -s` says Linux: no menu bar or toast to probe."""
    d = tmp_path / "linuxbin"
    d.mkdir()
    real = shutil.which("uname")
    make_shim(d, "uname", f'[ "$1" = -s ] && {{ echo Linux; exit 0; }}\nexec "{real}" "$@"\n')
    return {"PATH": f"{d}{os.pathsep}{os.environ['PATH']}", "TMPDIR": str(tmp_path)}


@pytest.mark.parametrize("shell", SHELLS)
def test_selftest_skips_the_menu_bar_probe_off_macos_and_still_passes(linux, shell):
    r, st, lines = selftest(linux, shell)
    assert r.returncode == 0 and st == {"platform": "ok", "tools": "ok", "jq": "ok", "jxa": "skip"}, lines
    assert lines[3] == "skip jxa: not macOS" and lines[0].startswith("ok platform: Linux ")


@pytest.mark.parametrize("shell", SHELLS)
def test_selftest_on_macos_passes_every_check_under_each_shell(mac, shell):
    env, _ = mac
    r, st, _ = selftest(env, shell)
    assert r.returncode == 0 and set(st.values()) == {"ok"}


@pytest.mark.parametrize("shell", SHELLS)
def test_a_probe_killed_by_a_signal_fails_its_line_and_nothing_else_prints(mac, shell):
    """dash names the signal on stderr; the line carries the exit code only."""
    env, _ = mac
    r, st, lines = selftest({**env, "FAKE_SIGNAL": "SEGV"}, shell)
    assert r.returncode == 1 and st == {"platform": "ok", "tools": "ok", "jq": "ok", "jxa": "fail"}
    assert lines[3].startswith("fail jxa: menu bar: exit 139") and "toast: exit 139" in lines[3], lines[3]
    assert "Segmentation" not in r.stdout


# Each tool alone missing from PATH: git and jq fail the run, a vendor CLI is reported absent.
@pytest.mark.parametrize("gone, fails, word", [
    (None, set(), ""), ("git", {"tools"}, "git:MISSING"), ("jq", {"tools", "jq"}, "jq:MISSING"),
    ("curl", set(), "curl:absent"), ("gh", set(), "gh:absent"), ("glab", set(), "glab:absent")])
def test_selftest_names_each_missing_tool_and_fails_only_for_a_required_one(tmp_path, gone, fails, word):
    d = tmp_path / "only"
    d.mkdir()
    real_uname = shutil.which("uname")
    make_shim(d, "uname", f'[ "$1" = -s ] && {{ echo Linux; exit 0; }}\nexec "{real_uname}" "$@"\n')
    for t in ("tr", "cat", "sh"):
        (d / t).symlink_to(shutil.which(t))
    for t in ("git", "curl", "gh", "glab"):
        if t != gone:
            make_shim(d, t, "exit 0\n")
    if gone != "jq":
        (d / "jq").symlink_to(shutil.which("jq"))
    r, st, lines = selftest({"PATH": str(d)})
    assert r.returncode == (1 if fails else 0)
    assert {c for c, v in st.items() if v == "fail"} == fails, lines
    tools = [l for l in lines if " tools: " in l][0]
    assert word in tools and tools.count("MISSING") + tools.count("absent") == (1 if gone else 0), tools
    if gone == "jq":
        assert lines[2] == "fail jq: jq missing"


def test_selftest_takes_no_option():
    r = run("selftest", "--repo", "x")
    assert r.returncode == 4 and r.stdout == "" and "takes no option" in r.stderr


# ---------------------------------------------------------------- target ----

@pytest.mark.parametrize("url,vendor,owner,repo,n", [
    ("https://github.com/o/r/pull/12", "github", "o", "r", "12"),
    ("https://github.com/o/r/pull/12/files?tab=1", "github", "o", "r", "12"),
    ("https://gitlab.example.co.jp/g/p/-/merge_requests/3", "gitlab", "g", "p", "3"),
    ("https://bitbucket.org/w/r/pull-requests/7", "bitbucket", "w", "r", "7"),
])
def test_target_parses_every_vendor_shape(url, vendor, owner, repo, n):
    r = run("target", url, check=True)
    vals = dict(line.split("=", 1) for line in r.stdout.splitlines())
    assert (vals["vendor"], vals["owner"], vals["repo"], vals["pull_number"]) == \
        (vendor, owner, repo, n)


@pytest.mark.parametrize("url", [
    "https://evil.com/x/pull/1",
    "https://github.com/o/r/pull/abc",
    "https://github.com/o;rm -rf ~/r/pull/1",
    "not a url",
    "",
])
def test_target_rejects_what_it_cannot_prove(url):
    assert run("target", url).returncode == 4


# ------------------------------------------------------- git fixtures ----

@pytest.fixture
def fixture_repo(tmp_path):
    """An `origin` bare repo with main + a PR ref, and a clone standing on main."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "seed"
    work.mkdir()
    g = lambda *a, cwd=work: subprocess.run(
        ["git", *a], cwd=cwd, capture_output=True, text=True, check=True)
    g("init", "-b", "main")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    (work / "a.txt").write_text("base line 1\nbase line 2\n")
    g("add", "a.txt")
    g("commit", "-m", "base")
    g("checkout", "-b", "feature")
    (work / "a.txt").write_text("base line 1\nchanged line 2\n")
    g("commit", "-am", "change")
    head = g("rev-parse", "HEAD").stdout.strip()
    g("checkout", "main")
    subprocess.run(["git", "clone", "--bare", str(work), str(origin)],
                   capture_output=True, check=True)
    # GitHub-style PR ref on the remote
    subprocess.run(["git", "-C", str(origin), "update-ref", "refs/pull/5/head", head],
                   capture_output=True, check=True)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", str(origin), str(clone)], capture_output=True, check=True)
    return {"clone": clone, "head": head, "tmp": tmp_path}


def test_checkout_gates_and_fetches_the_base_ref(fixture_repo, data_dir):
    cwd = fixture_repo["tmp"]
    r = run("checkout", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--repo-dir", str(fixture_repo["clone"]), "--head-sha", fixture_repo["head"],
            "--base", "main", cwd=cwd, check=True)
    vals = dict(line.split("=", 1) for line in r.stdout.splitlines())
    assert vals["head"] == fixture_repo["head"]
    wt = Path(vals["worktree"])
    assert wt.is_dir() and wt.parent == data_dir / "r" / "worktrees", \
        "the worktree must root at the data directory, outside the reviewed repo"
    # the explicit refspec created origin/main inside the worktree's ref space
    mb = subprocess.run(["git", "-C", str(wt), "merge-base", "origin/main", "HEAD"],
                        capture_output=True, text=True)
    assert mb.returncode == 0 and mb.stdout.strip(), "origin/<base> was not created"


def test_checkout_fetches_from_the_remote_matching_the_pr_host(fixture_repo):
    """A workspace clone can carry one remote per vendor with `origin` pointing at the
    WRONG one — a blind `origin` fetch lands the wrong tree and the gate then rejects a
    perfectly reviewable PR. The remote is picked by matching host + owner/repo against
    the EFFECTIVE url (remote -v, insteadOf applied) — the endpoint fetch will really hit."""
    clone = fixture_repo["clone"]
    origin_url = subprocess.run(["git", "-C", str(clone), "remote", "get-url", "origin"],
                                capture_output=True, text=True, check=True).stdout.strip()
    # the matching remote: a local bare mirror whose PATH ends in github.com/o/r
    mirror = fixture_repo["tmp"] / "mirrors" / "github.com" / "o" / "r"
    mirror.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "--bare", "--mirror", origin_url, str(mirror)],
                   capture_output=True, check=True)
    # origin now impersonates another vendor over SSH — a blind origin fetch would die
    subprocess.run(["git", "-C", str(clone), "remote", "set-url", "origin",
                    "git@bitbucket.org:other/elsewhere.git"], check=True)
    subprocess.run(["git", "-C", str(clone), "remote", "add", "gh", str(mirror)], check=True)
    r = run("checkout", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--host", "github.com", "--repo-dir", str(clone),
            "--head-sha", fixture_repo["head"], "--base", "main",
            cwd=fixture_repo["tmp"], check=True)
    assert dict(l.split("=", 1) for l in r.stdout.splitlines())["head"] == fixture_repo["head"], \
        "checkout must fetch from the remote whose URL matches the PR's host+owner/repo"
    assert "bitbucket.org" not in r.stderr, "the wrong-vendor origin was still contacted"


def test_checkout_detaches_locally_when_the_head_sha_is_already_present(fixture_repo):
    """API credentials and git-over-SSH credentials are different things: a machine can
    fetch PR data over the API while every git remote is SSH-denied. The head SHA is
    content-addressed, so when an earlier fetch already brought the commit, checkout
    detaches straight to it with zero network instead of dying on the fetch."""
    clone = fixture_repo["clone"]
    # every remote is now unreachable; the feature commit is in the clone already
    subprocess.run(["git", "-C", str(clone), "remote", "set-url", "origin",
                    "git@gitlab.example.invalid:x/y.git"], check=True)
    r = run("checkout", "--vendor", "gitlab", "--owner", "x", "--repo", "y", "--pr", "4",
            "--host", "gitlab.example.invalid", "--repo-dir", str(clone),
            "--head-sha", fixture_repo["head"], "--base", "main",
            cwd=fixture_repo["tmp"], check=True)
    assert dict(l.split("=", 1) for l in r.stdout.splitlines())["head"] == fixture_repo["head"]


def test_checkout_exits_2_when_the_tree_cannot_match(fixture_repo):
    r = run("checkout", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--repo-dir", str(fixture_repo["clone"]),
            "--head-sha", "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "--base", "main", cwd=fixture_repo["tmp"])
    assert r.returncode == 2
    assert "deadbeef" in r.stderr and "does not match" in r.stderr


def test_checkout_accepts_a_short_head_sha_prefix(fixture_repo):
    """Bitbucket reports a 12-char hash; the gate prefix-matches, never equality."""
    r = run("checkout", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--repo-dir", str(fixture_repo["clone"]), "--head-sha", fixture_repo["head"][:12],
            "--base", "main", cwd=fixture_repo["tmp"], check=True)
    assert dict(l.split("=", 1) for l in r.stdout.splitlines())["head"] == fixture_repo["head"]


# --------------------------------------------------------- verify-line ----

def test_verify_line_right_prints_the_worktree_line(fixture_repo):
    r = run("checkout", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--repo-dir", str(fixture_repo["clone"]), "--head-sha", fixture_repo["head"],
            "--base", "main", cwd=fixture_repo["tmp"], check=True)
    wt = dict(l.split("=", 1) for l in r.stdout.splitlines())["worktree"]
    right = run("verify-line", "--worktree", wt, "--path", "a.txt", "--line", "2",
                "--side", "RIGHT", "--base", "main", check=True)
    assert right.stdout.strip() == "changed line 2"
    # LEFT reads the merge-base blob — the OLD content, though the file changed on head
    left = run("verify-line", "--worktree", wt, "--path", "a.txt", "--line", "2",
               "--side", "LEFT", "--base", "main", check=True)
    assert left.stdout.strip() == "base line 2"
    gone = run("verify-line", "--worktree", wt, "--path", "nope.txt", "--line", "1",
               "--side", "RIGHT", "--base", "main", check=True)
    assert gone.stdout.startswith("UNCONFIRMABLE")
    for side in ("RIGHT", "LEFT"):
        eof = run("verify-line", "--worktree", wt, "--path", "a.txt", "--line", "99",
                  "--side", side, "--base", "main", check=True)
        assert eof.stdout.startswith("UNCONFIRMABLE"), \
            f"{side}: a line past EOF is the off-by-N this check exists to catch"
    # a 0-byte file: grep -c exits 1 on zero lines, which set -e once turned into a
    # silent death with no UNCONFIRMABLE and nothing on stderr
    (Path(wt) / "empty.txt").write_text("")
    empty = run("verify-line", "--worktree", wt, "--path", "empty.txt", "--line", "1",
                "--side", "RIGHT", "--base", "main", check=True)
    assert empty.stdout.startswith("UNCONFIRMABLE"), "an empty file must report, never die silently"
    # a BLANK line inside the file is a valid anchor, not an EOF miss
    (Path(wt) / "b.txt").write_text("x\n\ny\n")
    blank = run("verify-line", "--worktree", wt, "--path", "b.txt", "--line", "2",
                "--side", "RIGHT", "--base", "main", check=True)
    assert blank.stdout == "\n" and "UNCONFIRMABLE" not in blank.stdout, \
        "a blank line in range must verify as blank content, never as past-EOF"


def test_verify_line_left_is_unconfirmable_without_a_merge_base(fixture_repo, tmp_path):
    lone = tmp_path / "lone"
    lone.mkdir()
    for a in (["init", "-b", "x"], ["config", "user.email", "t@t"],
              ["config", "user.name", "t"], ["commit", "--allow-empty", "-m", "x"]):
        subprocess.run(["git", *a], cwd=lone, capture_output=True, check=True)
    r = run("verify-line", "--worktree", str(lone), "--path", "a.txt", "--line", "1",
            "--side", "LEFT", "--base", "main", check=True)
    assert r.stdout.startswith("UNCONFIRMABLE"), \
        "a missing origin/<base> must downgrade, not silently read the index"


# ---------------------------------------------------------------- post ----

PAYLOAD = {
    "body": "overview $(echo pwned) `id`",
    "commit_id": "a" * 40,
    "comments": [
        {"path": "a.txt", "line": 2, "side": "RIGHT", "body": "right side $HOME"},
        {"path": "a.txt", "line": 1, "side": "LEFT", "body": "left side"},
    ],
}


@pytest.fixture
def shims(tmp_path):
    d = tmp_path / "bin"
    d.mkdir()
    log = tmp_path / "calls.log"
    make_shim(d, "gh", f'''printf '%s\\n' "gh $*" >> "{log}"
case "$*" in
  *reviews*--input*--jq\\ .id*|*--jq\\ .id*reviews*) cat > /dev/null; printf '777\\n' ;;
  *reviews*--input*) cat > /dev/null; printf '{{"id": 777, "state": "PENDING"}}\\n' ;;
  *user*) printf '{{"login": "bot"}}\\n' ;;
  *) printf '{{}}\\n' ;;
esac
''')
    make_shim(d, "glab", f'''printf '%s\\n' "glab $*" >> "{log}"
case "$*" in
  *merge_requests/9\\ *|*merge_requests/9) printf '{{"iid": 9, "diff_refs": {{"base_sha": "b1", "start_sha": "s1", "head_sha": "h1"}}}}\\n' ;;
  *draft_notes*) cat > /dev/null; printf '{{}}\\n' ;;
  *discussions/*) cat > /dev/null; printf '{{"id": 55}}\\n' ;;
  *) printf '[]\\n' ;;
esac
''')
    make_shim(d, "curl", f'''printf '%s\\n' "curl $*" >> "{log}"
for a in "$@"; do case "$a" in @*) cat "${{a#@}}" >> "{log}.bodies";; esac; done
printf '{{"id": 42, "values": [], "next": null}}\\n'
''')
    return {"path": str(d), "log": log, "tmp": tmp_path}


def env_for(shims):
    return {"PATH": shims["path"] + os.pathsep + os.environ["PATH"],
            "BITBUCKET_TOKEN": "tok-test"}


def test_post_github_creates_a_pending_review(shims, tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(PAYLOAD))
    r = run("post", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--payload", str(f), env_extra=env_for(shims), check=True)
    assert "review_id=777" in r.stdout and "state=PENDING" in r.stdout
    calls = shims["log"].read_text()
    assert "-X POST repos/o/r/pulls/5/reviews --input" in calls
    assert "pwned" not in calls, "payload text reached an argv — shell saw attacker content"


@pytest.mark.parametrize("text", ["  \n", "{}", "{broken", "[]", '"body"', "null",
                                  '{"body": "b", "commit_id": "c", "comments": {}}',
                                  '{"body": "b", "comments": []}'])
def test_post_refuses_a_payload_without_a_review_in_it(shims, tmp_path, text):
    f = tmp_path / "p.json"
    f.write_text(text)
    r = run("post", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--payload", str(f), env_extra=env_for(shims))
    assert r.returncode == 1 and "payload must carry body" in r.stderr
    assert not shims["log"].exists() or "pulls/5/reviews" not in shims["log"].read_text()


# `jq --version` as each release prints it (1.3 and older: "jq version …"); the floor is 1.6. An
# output no release prints is left to the idioms the scripts run, never refused on its spelling.
JQ_VERSIONS = [("jq-1.5", False), ("jq-1.5rc2", False), ("jq-1.0", False), ("jq version 1.4", False),
               ("jq version 1.3", False), ("jq-1.6", True), ("jq-1.6-159-apple-gcff5336-dirty", True),
               ("jq-1.7.1", True), ("jq-1.8.0", True), ("jq-1.10", True), ("jq-1.15", True),
               ("", True), ("garbage", True)]


@pytest.mark.parametrize("version, ok", JQ_VERSIONS)
def test_a_jq_older_than_1_6_is_refused_with_the_install_hint(tmp_path, version, ok):
    real = subprocess.run(["sh", "-c", "command -v jq"], capture_output=True, text=True, check=True).stdout.strip()
    d = tmp_path / "jqbin"
    d.mkdir()
    make_shim(d, "jq", f'[ "$1" = --version ] && {{ echo "{version}"; exit 0; }}\nexec "{real}" "$@"\n')
    r = run("data-dir", "--all", env_extra={"PATH": f"{d}{os.pathsep}{os.environ['PATH']}"})
    if ok:
        assert r.returncode == 0, r.stderr
    else:
        assert r.returncode == 1 and f"jq 1.6 or newer is required, found {version}" in r.stderr
        assert "brew install jq" in r.stderr


def test_post_gitlab_converts_each_comment_to_a_positioned_draft_note(shims, tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(PAYLOAD))
    run("post", "--vendor", "gitlab", "--owner", "o", "--repo", "r", "--pr", "9",
        "--payload", str(f), env_extra=env_for(shims), check=True)
    calls = shims["log"].read_text()
    assert calls.count("draft_notes --input") == 3, "2 LINE notes + 1 overview note"


def test_post_bitbucket_stages_nothing_and_publish_sends_overview_first(shims, tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(PAYLOAD))
    r = run("post", "--vendor", "bitbucket", "--owner", "o", "--repo", "r", "--pr", "7",
            "--payload", str(f), env_extra=env_for(shims), check=True)
    assert "UNPUBLISHED_LOCAL" in r.stdout
    assert not shims["log"].exists() or "comments" not in shims["log"].read_text(), \
        "bitbucket has no draft stage — post must not touch the PR"
    run("publish", "--vendor", "bitbucket", "--owner", "o", "--repo", "r", "--pr", "7",
        "--payload", str(f), env_extra=env_for(shims), check=True)
    bodies = (shims["tmp"] / "calls.log.bodies").read_text().splitlines()
    assert "overview" in bodies[0], "the overview posts FIRST"
    parsed = [json.loads(b) for b in bodies]
    assert parsed[1]["inline"] == {"path": "a.txt", "to": 2}, "RIGHT maps to inline.to"
    assert parsed[2]["inline"] == {"path": "a.txt", "from": 1}, "LEFT maps to inline.from"


# Every overview shape the review template makes, in any output language: the LGTM line, the LINE-only
# opening line, the full structure.
OVERVIEWS = ["**LGTM 🌟** (commit [aaaaaaa](https://x/c/a))",
             "Cảm ơn 🙏 — toàn bộ thay đổi đã được review tại commit [aaaaaaa](https://x/c/a).",
             "### 🤖【AI REVIEW】Overview\nThanks 🙏\n\n#### 🔴 MUST FIX\n🔴 x\n\n<!-- bot-finding -->"]


@pytest.mark.parametrize("overview", OVERVIEWS)
def test_post_and_publish_stamp_the_review_marker_on_every_overview(shims, tmp_path, overview):
    """The marker tells this plugin's review from anyone's, an LGTM line included; the prompt never writes it."""
    f = tmp_path / "p.json"
    f.write_text(json.dumps({**PAYLOAD, "body": overview}))
    log = shims["tmp"] / "calls.log.bodies"
    sent_bodies = lambda: [json.loads(b) for b in log.read_text().splitlines() if b.strip()]
    go = lambda op, vendor, pr: run(op, "--vendor", vendor, "--owner", "o", "--repo", "r", "--pr", pr,
                                    "--payload", str(f), env_extra=env_for(shims), check=True)
    serve(shims, "gh", [("pulls/5/reviews", {"id": 777})])
    go("post", "github", "5")
    sent = sent_bodies()[0]
    assert sent["body"] == overview + "\n\n<!-- bot-review -->" and sent["comments"] == PAYLOAD["comments"]
    log.unlink()
    serve(shims, "glab", [("draft_notes", {}),
                          ("merge_requests/9", {"iid": 9, "diff_refs": {"base_sha": "b", "start_sha": "s", "head_sha": "h"}})])
    go("post", "gitlab", "9")
    notes = [b["note"] for b in sent_bodies()]
    assert notes[-1] == overview + "\n\n<!-- bot-review -->", "the overview note, not a LINE note"
    assert all("bot-review" not in n for n in notes[:-1])
    log.unlink()
    serve(shims, "curl", [("comments", {"id": 42})])
    go("publish", "bitbucket", "7")
    parts = [b["content"]["raw"] for b in sent_bodies()]
    assert parts[0] == overview + "\n\n[bot-review]: #" and all("bot-review" not in p for p in parts[1:])
    assert json.loads(f.read_text())["body"] == overview, "the payload file stays as the review wrote it"


def test_post_verify_finds_the_stamped_overview(shims, tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(PAYLOAD))
    pv = lambda vendor, *extra: run("post-verify", "--vendor", vendor, "--owner", "o", "--repo", "r", "--pr", "5", *extra,
                                    env_extra=env_for(shims), check=True).stdout.splitlines()
    serve(shims, "glab", [
        ("merge_requests/5/draft_notes", []),
        ("merge_requests/5/notes?sort=desc", [
            {"id": 11, "body": PAYLOAD["body"] + "\n\n<!-- bot-review -->", "position": None, "system": False}]),
        ("merge_requests/5", {"web_url": "https://gitlab.com/o/r/-/merge_requests/5"}),
    ])
    assert pv("gitlab", "--payload", str(f)) == ["PUBLISHED", "url=https://gitlab.com/o/r/-/merge_requests/5#note_11"]
    serve(shims, "curl", [("pullrequests/5/comments?pagelen=100", {"values": [
        {"id": 41, "content": {"raw": PAYLOAD["body"] + "\n\n[bot-review]: #"}, "inline": None, "deleted": False,
         "links": {"html": {"href": "https://bitbucket.org/o/r/pull-requests/5/_/diff#comment-41"}}}], "next": None})])
    assert pv("bitbucket", "--marker", "[bot-finding]: #", "--payload", str(f))[-1] == \
        "url=https://bitbucket.org/o/r/pull-requests/5/_/diff#comment-41"


# ------------------------------------------------- post: a pending draft ----
# GitHub keeps one pending review per user per PR (a second POST is a 422); GitLab's bulk publish
# would send a leftover draft note out with the new review. Either way `post` stops first.

OUR_DRAFT = "### 🤖【AI REVIEW】Overview\nThanks 🙏\n\n<!-- bot-review -->"
GH_PENDING = lambda body: [("reviews?per_page", [
    {"id": 1, "state": "COMMENTED", "commit_id": "c" * 40, "body": "LGTM", "user": {"login": "bot"}},
    {"id": 900, "state": "PENDING", "commit_id": "b" * 40, "body": body, "user": {"login": "bot"}}])]
GL_PENDING = lambda *notes: [
    ("draft_notes?per_page", list(notes)),
    ("merge_requests/9", {"iid": 9, "diff_refs": {"base_sha": "b", "start_sha": "s", "head_sha": "h"}})]
GL_LINE = {"id": 31, "note": "🔵 x\n\n<!-- bot-finding -->", "commit_id": None, "position": {"head_sha": "d" * 40}}
GL_OVERVIEW = {"id": 32, "note": "**LGTM 🌟** (commit x)", "commit_id": None, "position": None}
GL_HUMAN = {"id": 33, "note": "my own note, not sent yet", "commit_id": None, "position": None}


def _post(shims, tmp_path, vendor, pr):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(PAYLOAD))
    return run("post", "--vendor", vendor, "--owner", "o", "--repo", "r", "--pr", pr, "--payload", str(f),
               env_extra=env_for(shims))


def _discard(shims, vendor, pr, draft_id):
    return run("discard", "--vendor", vendor, "--owner", "o", "--repo", "r", "--pr", pr, "--draft-id", draft_id,
               env_extra=env_for(shims))


@pytest.mark.parametrize("body, ours", [(OUR_DRAFT, "true"), ("**LGTM 🌟** (commit x)", "true"),
                                        ("Half-written notes of my own", "false")])
def test_post_github_stops_on_the_callers_pending_review_and_names_it(shims, tmp_path, body, ours):
    serve(shims, "gh", GH_PENDING(body))
    r = _post(shims, tmp_path, "github", "5")
    assert r.returncode == 8, r.stderr
    assert r.stdout.splitlines() == ["draft_id=900", "commit=" + "b" * 40, f"ours={ours}"]
    assert "-X POST" not in shims["log"].read_text(), "nothing posted beside the draft"


def test_post_gitlab_never_sends_leftover_draft_notes_out_with_a_new_review(shims, tmp_path):
    serve(shims, "glab", GL_PENDING(GL_LINE, GL_OVERVIEW))
    r = _post(shims, tmp_path, "gitlab", "9")
    assert r.returncode == 8, r.stderr
    assert r.stdout.splitlines() == ["draft_id=31,32", "commit=" + "d" * 40, "ours=true"]
    calls = shims["log"].read_text()
    assert "-X POST" not in calls and "bulk_publish" not in calls
    serve(shims, "glab", GL_PENDING(GL_LINE, GL_HUMAN))
    assert _post(shims, tmp_path, "gitlab", "9").stdout.splitlines()[-1] == "ours=false", \
        "one note the plugin did not write makes the set a person's"


def test_post_without_a_pending_draft_posts_as_before(shims, tmp_path):
    serve(shims, "gh", [("reviews?per_page", [{"id": 1, "state": "COMMENTED", "body": "x", "user": {"login": "bot"}}]),
                        ("-X POST repos/o/r/pulls/5/reviews", "777\n")])
    r = _post(shims, tmp_path, "github", "5")
    assert r.returncode == 0 and r.stdout.startswith("review_id=777"), r.stderr
    serve(shims, "glab", GL_PENDING())
    assert _post(shims, tmp_path, "gitlab", "9").returncode == 0


def test_discard_removes_only_the_plugins_own_draft_it_was_named(shims, tmp_path):
    serve(shims, "gh", GH_PENDING(OUR_DRAFT))
    r = _discard(shims, "github", "5", "900")
    assert (r.returncode, r.stdout) == (0, "DISCARDED\n"), r.stderr
    assert "gh api -X DELETE repos/o/r/pulls/5/reviews/900" in shims["log"].read_text()
    serve(shims, "gh", [("reviews/900/events", "COMMENTED\n")])
    r = run("publish", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5", "--review-id", "900",
            env_extra=env_for(shims))
    assert r.stdout == "COMMENTED\n", "publishing the draft as it is: the case's other answer"
    assert "-X POST repos/o/r/pulls/5/reviews/900/events -f event=COMMENT" in shims["log"].read_text()
    serve(shims, "glab", GL_PENDING(GL_LINE, GL_OVERVIEW))
    assert _discard(shims, "gitlab", "9", "31,32").stdout == "DISCARDED\n"
    calls = shims["log"].read_text()
    assert "-X DELETE projects/o%2Fr/merge_requests/9/draft_notes/31" in calls
    assert "-X DELETE projects/o%2Fr/merge_requests/9/draft_notes/32" in calls
    assert _discard(shims, "bitbucket", "7", "1").stdout == "NO-EQUIVALENT\n"


@pytest.mark.parametrize("vendor, pr, routes, draft_id", [
    ("github", "5", GH_PENDING("Half-written notes of my own"), "900"),
    ("github", "5", GH_PENDING(OUR_DRAFT), "901"),
    ("gitlab", "9", GL_PENDING(GL_LINE, GL_HUMAN), "31,33"),
    ("gitlab", "9", GL_PENDING(GL_LINE, GL_OVERVIEW, GL_HUMAN), "31,32"),
])
def test_discard_refuses_a_persons_draft_or_one_it_was_not_shown(shims, vendor, pr, routes, draft_id):
    serve(shims, {"github": "gh", "gitlab": "glab"}[vendor], routes)
    r = _discard(shims, vendor, pr, draft_id)
    assert r.returncode == 1 and r.stdout == ""
    calls = shims["log"].read_text()
    assert "per_page" in calls, "read the draft again before acting on it"
    assert "DELETE" not in calls, "a person's pending review stays untouched"


def test_reply_bodies_travel_by_file_never_argv(shims, tmp_path):
    body = tmp_path / "b.md"
    body.write_text("thanks `$(reboot)`")
    run("reply", "--vendor", "bitbucket", "--owner", "o", "--repo", "r", "--pr", "7",
        "--comment-id", "3", "--body-file", str(body), env_extra=env_for(shims), check=True)
    assert "reboot" not in shims["log"].read_text(), "reply text reached an argv"
    sent = (shims["tmp"] / "calls.log.bodies").read_text()
    assert json.loads(sent)["parent"] == {"id": 3}, "a reply without parent lands top-level"


def test_gitlab_reply_body_travels_by_file_and_lands_in_the_discussion(shims, tmp_path):
    body = tmp_path / "b.md"
    body.write_text("thanks `$(reboot)`")
    run("reply", "--vendor", "gitlab", "--owner", "o", "--repo", "r", "--pr", "9",
        "--comment-id", "3", "--thread-id", "abc123", "--body-file", str(body),
        env_extra=env_for(shims), check=True)
    calls = shims["log"].read_text()
    assert "reboot" not in calls, "reply text reached glab's argv"
    assert "discussions/abc123/notes --input" in calls, \
        "a GitLab reply lands in the DISCUSSION, via --input"


def test_bitbucket_without_credentials_stops_with_setup_help(shims, tmp_path):
    env = {"PATH": shims["path"] + os.pathsep + os.environ["PATH"]}
    for var in ("BITBUCKET_TOKEN", "BITBUCKET_EMAIL", "BITBUCKET_API_TOKEN"):
        env[var] = ""
    r = run("account", "--vendor", "bitbucket", "--owner", "o", "--repo", "r", "--pr", "7",
            env_extra=env)
    assert r.returncode == 6 and "BITBUCKET_EMAIL" in r.stderr


# ------------------------------------------------------------- context ----

def test_context_orders_head_before_diff_whatever_the_caller_asked(shims, tmp_path):
    make_shim(Path(shims["path"]), "gh", '''case "$*" in
  *headRefOid*) printf 'abc123\\n' ;;
  *--name-only*) printf 'a.txt\\n' ;;
  *pulls/5/files*) printf 'diff --git a/a.txt b/a.txt\\n+x\\n' ;;
  *) printf '{}\\n' ;;
esac
''')
    r = run("context", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--max-patch-bytes", "1000", "--sections", "diff,head",
            env_extra=env_for(shims), check=True)
    assert r.stdout.index("## Head SHA") < r.stdout.index("## Diff"), \
        "Head SHA must be fetched before the Diff it describes"


# ------------------------------------------------- settings and stacks ----

def test_data_dir_is_set_once_and_read_everywhere(tmp_path, monkeypatch):
    """Memory and worktrees live in one user-chosen directory outside every repo. Unset is
    its own exit code so the caller asks instead of guessing a directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "fresh-xdg"))
    unset = run("data-dir")
    assert unset.returncode == 7, "an unset data directory must be told apart from any other error"
    assert run("settings", "--repo", "demo").returncode == 7, "settings must not guess a directory"
    tilde = run("data-dir", "--set", "~/open-pr-data", check=True).stdout.strip()
    assert tilde == str(home / "open-pr-data") and Path(tilde).is_dir(), "~ must expand to HOME"
    assert run("data-dir", cwd=tmp_path, check=True).stdout.strip() == tilde, \
        "the stored value must be read back from any directory"
    rel = run("data-dir", "--set", "rel-data", cwd=home, check=True).stdout.strip()
    assert rel == str(home / "rel-data"), "a relative path is stored absolute, never cwd-relative"


@pytest.mark.parametrize("text", ["{broken", "  \n", "[]", '"data_dir"', "1", "null", '[{"data_dir": "/x"}]'])
def test_a_config_that_is_not_a_json_object_stops_instead_of_reading_as_unset(tmp_path, monkeypatch, text):
    """jq 1.6 exits 0 on a parse error, and `jq -e` there exits 0 on a file holding no value at
    all, so a broken config would read as "unset" and the --set that follows would overwrite
    whatever the user had in it."""
    conf = tmp_path / "broken-xdg" / "open-pr" / "config.json"
    conf.parent.mkdir(parents=True)
    conf.write_text(text)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "broken-xdg"))
    assert run("data-dir").returncode == 1, "a broken config must not read as unset (exit 7)"
    target = tmp_path / "never-created"
    assert run("data-dir", "--set", str(target)).returncode == 1
    assert conf.read_text() == text, "--set overwrote a config it could not read"
    assert not target.exists(), "--set created the directory before checking the config"


def test_an_empty_config_file_reads_as_unset_and_set_fills_it(tmp_path, monkeypatch):
    conf = tmp_path / "empty-xdg" / "open-pr" / "config.json"
    conf.parent.mkdir(parents=True)
    conf.write_text("")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-xdg"))
    assert run("data-dir").returncode == 7
    target = tmp_path / "d"
    assert run("data-dir", "--set", str(target), check=True).stdout.strip() == str(target)
    assert json.loads(conf.read_text())["data_dir"] == str(target)


@pytest.mark.parametrize("sig, code", [("SEGV", 139), ("KILL", 137), ("ABRT", 134)])
def test_a_jq_killed_reading_the_config_never_says_delete_it(tmp_path, sig, code):
    """The config is intact; only the jq that read it died. --set must not overwrite it either."""
    d = tmp_path / "sigjq"
    d.mkdir()
    real = shutil.which("jq")
    make_shim(d, "jq", f'[ "$1" = --version ] && exec "{real}" "$@"\nkill -{sig} $$\n')
    env = {"PATH": f"{d}{os.pathsep}{os.environ['PATH']}"}
    conf = Path(os.environ["XDG_CONFIG_HOME"]) / "open-pr" / "config.json"
    before = conf.read_text()
    for args in (("data-dir",), ("data-dir", "--set", str(tmp_path / "never"))):
        r = run(*args, env_extra=env)
        assert r.returncode == code and f"jq exited {code} (killed by a signal)" in r.stderr, r.stderr
        assert "delete it" not in r.stderr
    assert conf.read_text() == before and not (tmp_path / "never").exists()


def _conf(tmp_path, monkeypatch, **body):
    xdg = tmp_path / "map-xdg"
    (xdg / "open-pr").mkdir(parents=True, exist_ok=True)
    (xdg / "open-pr" / "config.json").write_text(json.dumps(body))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    return xdg / "open-pr" / "config.json"


def test_data_dir_is_picked_by_the_longest_root_above_the_repo(tmp_path, monkeypatch):
    """A repo uses the entry whose root is its nearest ancestor; under no root, the default."""
    ws, inner, other = tmp_path / "ws", tmp_path / "ws" / "client-b", tmp_path / "elsewhere"
    for d in (ws / "repo", inner / "repo", other):
        d.mkdir(parents=True)
    _conf(tmp_path, monkeypatch, data_dir="/d/default",
          data_dirs=[{"root": str(inner), "dir": "/d/b"}, {"root": str(ws) + "/", "dir": "/d/a"}])

    def at(d):
        return run("data-dir", "--repo-dir", str(d), check=True).stdout.strip()

    assert at(ws) == "/d/a", "the root itself is covered"
    assert at(ws / "repo") == "/d/a"
    assert at(inner / "repo") == "/d/b", "the nested (longer) root wins whatever the array order"
    assert at(other) == "/d/default", "a repo under no root falls back to data_dir"
    assert run("data-dir", cwd=inner / "repo", check=True).stdout.strip() == "/d/b", \
        "without --repo-dir the cwd is the location"
    (tmp_path / "ws-sibling").mkdir()
    assert at(tmp_path / "ws-sibling") == "/d/default", "a root is a path prefix by component only"
    link = tmp_path / "link"
    link.symlink_to(inner)
    assert at(link / "repo") == "/d/b", "a symlinked path resolves to the root it points into"


def test_data_dir_not_covered_anywhere_exits_7(tmp_path, monkeypatch):
    (tmp_path / "ws").mkdir()
    (tmp_path / "out").mkdir()
    _conf(tmp_path, monkeypatch, data_dirs=[{"root": str(tmp_path / "ws"), "dir": "/d/a"}])
    assert run("data-dir", "--repo-dir", str(tmp_path / "ws"), check=True).stdout.strip() == "/d/a"
    assert run("data-dir", "--repo-dir", str(tmp_path / "out")).returncode == 7, \
        "no root above and no default is 'not set for here', not another error"
    assert run("settings", "--repo", "r", "--repo-dir", str(tmp_path / "out")).returncode == 7


def test_add_root_replaces_its_entry_and_all_lists_each_dir_once(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "ws").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    conf = _conf(tmp_path, monkeypatch)
    assert run("data-dir", "--all").returncode == 7, "nothing known is 'not set'"
    first = run("data-dir", "--add-root", "~/ws", "--dir", "mem-a", cwd=home, check=True).stdout.strip()
    assert first == str(home / "mem-a") and Path(first).is_dir(), "--dir expands like --set"
    second = run("data-dir", "--add-root", "ws", "--dir", "~/mem-b", cwd=home, check=True).stdout.strip()
    rows = json.loads(conf.read_text())["data_dirs"]
    assert rows == [{"root": str((home / "ws").resolve()), "dir": second}], "the same root is replaced"
    run("data-dir", "--set", "~/mem-b", check=True)
    run("data-dir", "--add-root", str(tmp_path), "--dir", "~/mem-c", check=True)
    assert run("data-dir", "--all", check=True).stdout.splitlines() == \
        [str(home / "mem-b"), str(home / "mem-c")], "one line per distinct data directory"
    assert run("data-dir", "--add-root", str(tmp_path / "ghost"), "--dir", "x").returncode == 1, \
        "a root that does not exist is refused"
    assert run("data-dir", "--add-root", str(home)).returncode == 1, "--add-root needs --dir"
    assert run("data-dir", "--all", "--set", "x").returncode == 1


def test_settings_reads_the_data_dir_of_the_repo_it_names(tmp_path, monkeypatch):
    (tmp_path / "ws-a").mkdir()
    (tmp_path / "ws-b").mkdir()
    a, b = tmp_path / "mem-a", tmp_path / "mem-b"
    _conf(tmp_path, monkeypatch, data_dirs=[{"root": str(tmp_path / "ws-a"), "dir": str(a)},
                                            {"root": str(tmp_path / "ws-b"), "dir": str(b)}])
    (b / "demo").mkdir(parents=True)
    (b / "demo" / "settings.json").write_text(json.dumps({"review": {"many_files_threshold": 7}}))
    out = json.loads(run("settings", "--repo", "demo", "--repo-dir", str(tmp_path / "ws-b"),
                         cwd=tmp_path / "ws-a", check=True).stdout)
    assert out["memory_dir"] == str(b / "demo") and out["review"]["many_files_threshold"] == 7, \
        "--repo-dir, not the cwd, picks the data directory"
    here = json.loads(run("settings", "--repo", "demo", cwd=tmp_path / "ws-a", check=True).stdout)
    assert here["memory_dir"] == str(a / "demo") and here["memory_found"] is False


def test_find_memory_reports_existing_memory_one_repo_deep(tmp_path):
    """The data-dir cases offer existing notebooks/review/ memory for import. The search is the
    script's, so no prompt types a find and no stray cd can move where it looks."""
    ws = tmp_path / "ws"
    (ws / "notebooks" / "review" / "repo-b").mkdir(parents=True)
    (ws / "repo-a" / "notebooks" / "review" / "repo-a" / "worktrees" / "pr1-1" / "notebooks" /
     "review" / "repo-a").mkdir(parents=True)
    (ws / "node_modules" / "x" / "notebooks" / "review").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(ws / "repo-a")], check=True)

    def lines(*args, cwd):
        return run("find-memory", *args, cwd=cwd, check=True).stdout.splitlines()

    bare = lines(cwd=ws)
    assert bare[0] == f"suggest={ws}/notebooks/review", "outside any repo the cwd holds the memory"
    assert sorted(bare[1:]) == sorted([f"found={ws}/notebooks/review",
                                       f"found={ws}/repo-a/notebooks/review"]), \
        "one repo deep counts; node_modules and worktree checkouts never do"
    inside = lines(cwd=ws / "repo-a")
    assert inside[0] == f"suggest={ws}/notebooks/review", "inside a repo, memory goes beside it"
    assert lines("--repo", "repo-a", cwd=ws) == [f"found={ws}/repo-a/notebooks/review/repo-a"]
    assert lines("--repo", "ghost", cwd=ws) == [], "nothing found prints nothing"
    assert run("find-memory", "--repo", "a b", cwd=ws).returncode == 4


def test_settings_applies_read_time_defaults(tmp_path, data_dir):
    d = data_dir / "demo"
    d.mkdir(parents=True)
    (d / "settings.json").write_text(json.dumps(
        {"review": {"bootstrapped": True, "doctored": True, "doctor_schedule": "never"},
         "shared": {"output_language": "English"}}))
    out = json.loads(run("settings", "--repo", "demo", cwd=tmp_path, check=True).stdout)
    assert out["review"]["many_files_threshold"] == 30
    assert out["review"]["post_lgtm"] is True, "a clean review is posted unless the repo opted out"
    assert out["fix"]["auto_push"] is False
    # jq's // operator treats an explicit false as absent — a stored false must
    # never flip to the true default, or fix declines without asking
    (d / "settings.json").write_text(json.dumps(
        {"review": {"bootstrapped": True}, "fix": {"decline_needs_confirmation": False}}))
    flip = json.loads(run("settings", "--repo", "demo", cwd=tmp_path, check=True).stdout)
    assert flip["fix"]["decline_needs_confirmation"] is False, "explicit false flipped to true"
    (d / "settings.json").write_text(json.dumps(
        {"review": {"bootstrapped": True, "post_lgtm": False}}))
    off = json.loads(run("settings", "--repo", "demo", cwd=tmp_path, check=True).stdout)
    assert off["review"]["post_lgtm"] is False, \
        "explicit false flipped to true — the repo would get the LGTM review it opted out of"
    assert out["doctor_due"] is False, '"never" is never due on a schedule'
    fresh = json.loads(run("settings", "--repo", "ghost", cwd=tmp_path, check=True).stdout)
    assert fresh["doctor_due"] is True, "an unbootstrapped repo is always due"
    # memory kept elsewhere must be distinguishable from a never-bootstrapped repo: the
    # resolved directory and whether it existed ride along with the values
    assert fresh["memory_found"] is False and fresh["memory_dir"] == str(data_dir / "ghost"), \
        "settings must say which directory it read and that nothing was there"
    assert out["memory_found"] is True and out["memory_dir"] == str(d), \
        "a real read reports the directory it found"
    # the cwd plays no part: a run from inside some other tree reads the same file
    elsewhere = tmp_path / "worktree-standin"
    elsewhere.mkdir()
    there = json.loads(run("settings", "--repo", "demo", cwd=elsewhere, check=True).stdout)
    assert there["memory_found"] is True, "settings resolved memory relative to the cwd"


def test_stacks_maps_extensions_and_overlays(tmp_path):
    (tmp_path / "artisan").write_text("")
    r = run("stacks", "--repo-dir", str(tmp_path),
            "app/models/u.rb", "x.vue", "a/b.tsx", "functions/f/index.js",
            "app/Http/Controllers/A.php", "notes.md", check=True)
    rows = dict(line.split("\t") for line in r.stdout.splitlines())
    assert rows["app/models/u.rb"] == "rails"
    assert rows["x.vue"] == "vue"
    assert rows["a/b.tsx"] == "react"
    assert rows["functions/f/index.js"] == "nodejs,lambda-common"
    assert rows["app/Http/Controllers/A.php"] == "laravel"
    assert rows["notes.md"].startswith("-"), "a human .md carries NO stack (v1 behaviour)"
    assert "judge" in rows["notes.md"], "an .md is the caller's judgment, never guessed"
    bad = run("stacks", "--vendor", "gitlab", "x.py")
    assert bad.returncode == 1 and "takes only --repo-dir" in bad.stderr, \
        "an unknown option must die loudly, never reach basename as a path"
    spaced = run("stacks", "--repo-dir", str(tmp_path), "a dir/with space.rb", check=True)
    assert spaced.stdout.split("\t")[0] == "a dir/with space.rb", \
        "a path with a space must survive as ONE argument"


def test_markers_and_commit_urls_stay_vendor_true():
    assert run("marker", "--vendor", "github", "--kind", "finding",
               check=True).stdout == "<!-- bot-finding -->\n"
    assert run("marker", "--vendor", "bitbucket", "--kind", "reply",
               check=True).stdout == "[bot-reply]: #\n"
    assert run("marker", "--vendor", "gitlab", "--kind", "claim", "--comment-id", "12",
               check=True).stdout == "<!-- bot-claim:12 -->\n"
    assert run("marker", "--vendor", "bitbucket", "--kind", "claim", "--comment-id", "12",
               check=True).stdout == "[bot-claim:12]: #\n"
    assert run("marker", "--vendor", "github", "--kind", "claim").returncode == 1, \
        "a claim marker names the comment it locks"
    assert run("marker", "--vendor", "github", "--kind", "claim", "--comment-id", "1 x").returncode == 4
    url = run("commit-url", "--vendor", "bitbucket", "--owner", "w", "--repo", "r",
              "--sha", "a" * 40, check=True).stdout
    assert "/commits/" in url, "bitbucket's commit path is /commits/ plural — /commit/ 404s"


def test_bitbucket_threads_group_replies_under_their_root(shims, tmp_path):
    """The first shipped jq iterated the ELEMENT inside map(f), indexing numbers with
    "parent" — exit 5 on any PR with one comment, which broke fix.md Step 3 and
    re-review on Bitbucket entirely."""
    page = json.dumps({"values": [
        {"id": 1, "parent": None, "resolution": None, "deleted": False},
        {"id": 2, "parent": {"id": 1}, "resolution": None, "deleted": False},
        {"id": 3, "parent": None, "resolution": {"type": "x"}, "deleted": False},
    ], "next": None})
    make_shim(Path(shims["path"]), "curl", f"printf '%s\\n' '{page}'\n")
    r = run("context", "--vendor", "bitbucket", "--owner", "w", "--repo", "r", "--pr", "7",
            "--sections", "threads", env_extra=env_for(shims), check=True)
    rows = [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]
    assert {"thread_id": 1, "resolved": False, "comment_ids": [1, 2]} in rows
    assert {"thread_id": 3, "resolved": True, "comment_ids": [3]} in rows


def test_bitbucket_reviews_carry_the_top_level_overview(shims, tmp_path):
    """Bitbucket has no review object: the overview — and every FILE finding inside it —
    is a top-level comment. Before this, "Reviews" said NO-EQUIVALENT and fix.md could
    never see a FILE finding on Bitbucket."""
    page = json.dumps({"values": [
        {"id": 9, "parent": None, "inline": None, "deleted": False,
         "content": {"raw": "overview [bot-finding]: #"}, "user": {"nickname": "bot"}},
        {"id": 10, "parent": None, "inline": {"path": "a", "to": 1}, "deleted": False,
         "content": {"raw": "line"}, "user": {"nickname": "bot"}},
    ], "next": None})
    make_shim(Path(shims["path"]), "curl", f"printf '%s\\n' '{page}'\n")
    r = run("context", "--vendor", "bitbucket", "--owner", "w", "--repo", "r", "--pr", "7",
            "--sections", "reviews", env_extra=env_for(shims), check=True)
    rows = [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]
    assert rows == [{"id": 9, "body": "overview [bot-finding]: #", "user": "bot", "state": "COMMENTED"}], \
        "only the top-level non-inline comment is a review row"


def test_push_targets_the_remote_matching_the_pr_host(fixture_repo):
    """fix once said `git push origin HEAD:<branch>` — on a clone with one remote per
    vendor that pushes a GitHub PR's commits to Bitbucket. push resolves the remote by
    the PR's host, and a failure must surface instead of being worked around."""
    clone = fixture_repo["clone"]
    origin_url = subprocess.run(["git", "-C", str(clone), "remote", "get-url", "origin"],
                                capture_output=True, text=True, check=True).stdout.strip()
    mirror = fixture_repo["tmp"] / "push-mirrors" / "github.com" / "o" / "r"
    mirror.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "--bare", origin_url, str(mirror)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(clone), "remote", "set-url", "origin",
                    "git@bitbucket.org:other/elsewhere.git"], check=True)
    subprocess.run(["git", "-C", str(clone), "remote", "add", "gh", str(mirror)], check=True)
    # a new commit on a detached HEAD, pushed as HEAD:feature
    subprocess.run(["git", "-C", str(clone), "checkout", "--detach", fixture_repo["head"]],
                   capture_output=True, check=True)
    (clone / "new.txt").write_text("x\n")
    subprocess.run(["git", "-C", str(clone), "add", "new.txt"], check=True)
    subprocess.run(["git", "-C", str(clone), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "fix"], capture_output=True, check=True)
    new = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    r = run("push", "--vendor", "github", "--owner", "o", "--repo", "r",
            "--host", "github.com", "--branch", "feature", "--dir", str(clone), check=True)
    assert "bitbucket.org" not in r.stderr, "the wrong-vendor origin was contacted"
    tip = subprocess.run(["git", "-C", str(mirror), "rev-parse", "refs/heads/feature"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert tip == new, "the commit did not land on the matching remote's branch"
    # failure path: no matching remote, unreachable origin -> non-zero + honest message
    bad = run("push", "--vendor", "gitlab", "--owner", "x", "--repo", "y",
              "--host", "gitlab.example.invalid", "--branch", "feature", "--dir", str(clone))
    assert bad.returncode != 0 and "never works around" in bad.stderr


# ------------------------------------------------------------ react ----

def test_react_top_uses_the_conversation_comment_endpoint(shims):
    """GitHub diff and conversation comments are separate id spaces (wrong one 404s); GitLab
    reacts on the note inside its MR."""
    base = ("--owner", "o", "--repo", "r", "--comment-id", "11", "--emoji", "eyes")
    serve(shims, "glab", [("award_emoji", {"id": 1})])
    run("react", "--vendor", "github", "--pr", "5", *base, env_extra=env_for(shims), check=True)
    run("react", "--vendor", "github", "--pr", "5", *base, "--kind", "top",
        env_extra=env_for(shims), check=True)
    run("react", "--vendor", "gitlab", "--pr", "9", *base, env_extra=env_for(shims), check=True)
    calls = shims["log"].read_text()
    assert "repos/o/r/pulls/comments/11/reactions" in calls, "line (the default) stays on pulls/comments"
    assert "repos/o/r/issues/comments/11/reactions" in calls, "top goes to issues/comments"
    assert "projects/o%2Fr/merge_requests/9/notes/11/award_emoji" in calls, \
        "a GitLab MR note's award_emoji lives under its merge request"
    assert run("react", "--vendor", "github", "--pr", "5", *base, "--kind", "x",
               env_extra=env_for(shims)).returncode == 4


# ---------------------------------------------------------- repo-target ----

@pytest.mark.parametrize("remote,vendor,owner,repo,host", [
    ("https://github.com/o/r.git", "github", "o", "r", "github.com"),
    ("git@github.com:o/r.git", "github", "o", "r", "github.com"),
    ("ssh://git@github.com/o/r", "github", "o", "r", "github.com"),
    ("https://oauth2:tok@gitlab.example.co.jp/g/p.git", "gitlab", "g", "p", "gitlab.example.co.jp"),
    ("git@gitlab.example.co.jp:g/p.git", "gitlab", "g", "p", "gitlab.example.co.jp"),
    ("ssh://git@gitlab.com:2222/g/p.git", "gitlab", "g", "p", "gitlab.com"),
    ("https://user@bitbucket.org/w/r.git", "bitbucket", "w", "r", "bitbucket.org"),
    ("git@bitbucket.org:w/r.git", "bitbucket", "w", "r", "bitbucket.org"),
])
def test_repo_target_reads_the_remote_of_the_directory(tmp_path, remote, vendor, owner, repo, host):
    d = tmp_path / "w"
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    subprocess.run(["git", "-C", str(d), "remote", "add", "origin", remote], check=True)
    vals = dict(l.split("=", 1) for l in run("repo-target", "--repo-dir", str(d),
                                             check=True).stdout.splitlines())
    assert vals == {"vendor": vendor, "owner": owner, "repo": repo, "host": host}


def test_repo_target_exits_5_when_no_remote_proves_a_repo(tmp_path):
    d = tmp_path / "w"
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    assert run("repo-target", "--repo-dir", str(d)).returncode == 5, "no remote at all"
    subprocess.run(["git", "-C", str(d), "remote", "add", "up", "https://gitlab.com/a/b/c.git"], check=True)
    assert run("repo-target", "--repo-dir", str(d)).returncode == 5, \
        "a nested group is not owner/repo — every other subcommand would reject it"
    subprocess.run(["git", "-C", str(d), "remote", "set-url", "up", "/srv/mirror.git"], check=True)
    assert run("repo-target", "--repo-dir", str(d)).returncode == 5, "a local path names no host"
    subprocess.run(["git", "-C", str(d), "remote", "set-url", "up", "git@github.com:o/r.git"], check=True)
    assert "vendor=github" in run("repo-target", "--repo-dir", str(d), check=True).stdout, \
        "with no origin, the only remote there is counts"



def test_repo_target_remote_picks_one_of_several(tmp_path):
    """A fixture clone carries a remote per vendor; origin is not always the one to watch."""
    d = tmp_path / "w"
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    for name, url in (("origin", "git@bitbucket.org:w/r.git"), ("github", "git@github.com:o/r.git")):
        subprocess.run(["git", "-C", str(d), "remote", "add", name, url], check=True)
    out = run("repo-target", "--repo-dir", str(d), "--remote", "github", check=True).stdout
    assert "vendor=github" in out and "owner=o" in out
    assert "vendor=bitbucket" in run("repo-target", "--repo-dir", str(d), check=True).stdout
    assert run("repo-target", "--repo-dir", str(d), "--remote", "nope").returncode == 5


def test_list_repos_prints_every_hosted_remote_below_the_directory(tmp_path):
    ws = tmp_path / "ws"
    a, b, plain = ws / "a", ws / "group" / "b", ws / "notes"
    plain.mkdir(parents=True)
    for d in (a, b):
        subprocess.run(["git", "init", "-q", str(d)], check=True)
    subprocess.run(["git", "-C", str(a), "remote", "add", "origin", "git@bitbucket.org:w/a.git"], check=True)
    subprocess.run(["git", "-C", str(a), "remote", "add", "github", "https://github.com/o/a.git"], check=True)
    subprocess.run(["git", "-C", str(a), "remote", "add", "local", "/srv/mirror.git"], check=True)
    subprocess.run(["git", "-C", str(b), "remote", "add", "origin", "git@gitlab.example.com:g/b.git"], check=True)
    rows = [l.split("\t") for l in run("list-repos", "--dir", str(ws), check=True).stdout.splitlines()]
    got = sorted((r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows)
    assert got == sorted([
        (str(a.resolve()), "github", "github", "o", "a", "github.com"),
        (str(a.resolve()), "origin", "bitbucket", "w", "a", "bitbucket.org"),
        (str(b.resolve()), "origin", "gitlab", "g", "b", "gitlab.example.com"),
    ]), "a local-path remote names no host and is skipped"
    assert all(len(r) == 7 for r in rows)

def test_list_repos_finds_a_git_worktree_it_runs_in_and_skips_those_below(tmp_path):
    """A watcher started inside .claude/worktrees/<x> (a git worktree: .git is a file) lists it."""
    main = tmp_path / "main"
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    subprocess.run(["git", "-C", str(main), "remote", "add", "origin", "https://github.com/o/a.git"], check=True)
    subprocess.run(["git", "-C", str(main), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                    "--allow-empty", "-m", "x"], check=True)
    wt = main / ".claude" / "worktrees" / "feat"
    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt)], check=True)
    rows = [l.split("\t")[0] for l in run("list-repos", "--dir", str(wt), check=True).stdout.splitlines()]
    assert rows == [str(wt.resolve())]
    rows = [l.split("\t")[0] for l in run("list-repos", "--dir", str(main), check=True).stdout.splitlines()]
    assert rows == [str(main.resolve())], "a worktree below the scanned directory is not a repo to watch"

# ------------------------------------------------------------ triggers ----

HOSTILE = "/open-pr focus on $(touch /tmp/pwned) and `id` \"quoted\" 'single'\nsecond line"


class Seq(list):
    """Items answered in turn, then the last one again: one listing read before and after a write."""


def serve(shims, name, routes):
    """Vendor CLI shim answering canned JSON picked by an argv substring; request bodies
    (`--input F`, curl's `--data @F`) are appended to calls.log.bodies."""
    d = Path(shims["tmp"]) / f"{name}-routes"
    d.mkdir(exist_ok=True)
    cases = []
    for i, (pat, payload) in enumerate(routes):
        if isinstance(payload, tuple):   # (exit code, stderr)
            cases.append(f'  *"{pat}"*) printf "%s\\n" "{payload[1]}" >&2; exit {payload[0]} ;;')
            continue
        items = payload if isinstance(payload, Seq) else [payload]
        for k, item in enumerate(items):   # a str is raw text: what the real CLI prints after its own --jq
            (d / f"{i}.{k}.json").write_text(item if isinstance(item, str) else json.dumps(item))
        cases.append(f'''  *"{pat}"*) n=$(cat "{d}/{i}.n" 2>/dev/null || echo 0)
      f="{d}/{i}.$n.json"; [ -f "$f" ] || f="{d}/{i}.{len(items) - 1}.json"
      echo $((n + 1)) > "{d}/{i}.n"; cat "$f" ;;''')
    make_shim(Path(shims["path"]), name, f'''printf '%s\\n' "{name} $*" >> "{shims['log']}"
prev=""
for a in "$@"; do
  if [ "$prev" = --input ] && [ "$a" != - ]; then cat "$a" >> "{shims['log']}.bodies"; echo >> "{shims['log']}.bodies"; fi
  case "$prev/$a" in --data/@*) cat "${{a#@}}" >> "{shims['log']}.bodies"; echo >> "{shims['log']}.bodies" ;; esac
  prev="$a"
done
case "$*" in
{chr(10).join(cases)}
  *) printf '[]\\n' ;;
esac
''')


def triggers(shims, vendor, *extra, check=True):
    # a workspace token has no identity: the Bitbucket account reads UNKNOWN
    env = {**env_for(shims), "BITBUCKET_EMAIL": "", "BITBUCKET_API_TOKEN": ""}
    r = run("triggers", "--vendor", vendor, "--owner", "o", "--repo", "r", *extra,
            env_extra=env, check=check)
    return r if not check else [json.loads(l) for l in r.stdout.splitlines()]


GH_ROUTES = [
    ("pulls?state=open", [{"number": 5, "html_url": "https://github.com/o/r/pull/5", "title": "Add retry"}]),
    ("issues/comments", [
        {"id": 1, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:03Z", "body": HOSTILE},
        {"id": 2, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:04Z", "body": "please /open-pr later"},
        {"id": 3, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "bot"},
         "created_at": "2026-01-01T00:00:05Z", "body": "/open-pr from myself"},
        {"id": 4, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "alt"},
         "created_at": "2026-01-01T00:00:06Z", "body": "/open-pr quoted <!-- bot-finding -->"},
        {"id": 5, "issue_url": "https://api.github.com/repos/o/r/issues/8", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:07Z", "body": "/open-pr on a closed PR or an issue"},
        {"id": 6, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "stranger"},
         "created_at": "2026-01-01T00:00:01Z", "body": "  /open-pr"},
        {"id": 7, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:08Z", "body": "/open-prx not the trigger"},
        {"id": 8, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:09Z", "body": "/open-pr:review is the plugin command, run it locally"},
    ]),
    ("pulls/comments", [
        {"id": 90, "pull_request_url": "https://api.github.com/repos/o/r/pulls/5", "user": {"login": "col"},
         "created_at": "2026-01-01T00:00:02Z", "body": "/open-pr this hunk"},
    ]),
    ("api user", "bot\n"),
    ("collaborators/dev/permission", {"permission": "write", "role_name": "write"}),
    ("collaborators/bot/permission", {"permission": "admin", "role_name": "admin"}),
    ("collaborators/col/permission", {"permission": "write", "role_name": "maintain"}),
    ("collaborators/stranger/permission", {"permission": "read", "role_name": "read"}),
]


def test_triggers_github_emits_only_real_triggers_oldest_first(shims):
    serve(shims, "gh", GH_ROUTES)
    rows = triggers(shims, "github")
    assert [r["comment_id"] for r in rows] == ["6", "90", "1", "3"], \
        "mid-body mentions, marked comments, non-open PRs, /open-prx and /open-pr:… never trigger; " \
        "the watcher's own account may ask (one person can be developer and reviewer)"
    assert rows[0]["authorized"] == "no", "a read-only user has no write access"
    assert rows[1] == {"pr": 5, "url": "https://github.com/o/r/pull/5", "title": "Add retry", "pr_author": None, "comment_id": "90", "kind": "line",
                       "thread_id": None, "user": "col", "created_at": "2026-01-01T00:00:02Z", "body": "/open-pr this hunk",
                       "authorized": "yes"}
    assert rows[2]["kind"] == "top" and rows[2]["authorized"] == "yes"
    assert rows[2]["body"] == HOSTILE, "an attacker-controlled body must come out byte-for-byte"
    assert not Path("/tmp/pwned").exists()
    assert "pwned" not in shims["log"].read_text(), "a comment body reached an argv"


def test_triggers_github_checks_write_access_once_per_author_of_a_trigger(shims):
    """author_association says OWNER/MEMBER/COLLABORATOR for any org member and read-only
    collaborators; only the repository permission says who can write. A custom role's
    role_name is its own name; permission carries the base role it extends."""
    comment = lambda i, login, body: {"id": i, "issue_url": "https://api.github.com/repos/o/r/issues/5",
                                      "user": {"login": login}, "created_at": f"2026-01-01T00:00:0{i}Z", "body": body}
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "https://github.com/o/r/pull/5"}]),
        ("issues/comments", [comment(1, "dev", "/open-pr"), comment(2, "dev", "/open-pr again"),
                             comment(3, "triager", "/open-pr"), comment(4, "gone", "/open-pr"),
                             comment(5, "lurker", "no trigger here"), comment(6, "ci[bot]", "/open-pr"),
                             comment(7, "custom", "/open-pr")]),
        ("collaborators/dev/permission", {"permission": "write", "role_name": "write"}),
        ("collaborators/triager/permission", {"permission": "read", "role_name": "triage"}),
        ("collaborators/custom/permission", {"permission": "write", "role_name": "release-manager"}),
        ("collaborators/gone/permission", (1, "gh: Not Found (HTTP 404)")),
    ])
    rows = triggers(shims, "github")
    assert {r["comment_id"]: r["authorized"] for r in rows} == \
        {"1": "yes", "2": "yes", "3": "no", "4": "no", "6": "no", "7": "yes"}
    calls = shims["log"].read_text()
    assert calls.count("collaborators/dev/permission") == 1, "one lookup per distinct author"
    assert "lurker" not in calls, "only an author of a trigger is looked up"
    assert "ci[bot]" not in calls, "a login outside GitHub's shape never reaches argv"


def test_triggers_github_stops_when_the_permission_cannot_be_read(shims):
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "u"}]),
        ("issues/comments", [{"id": 1, "issue_url": "https://api.github.com/repos/o/r/issues/5",
                              "user": {"login": "dev"}, "created_at": "2026-01-01T00:00:01Z", "body": "/open-pr"}]),
        ("collaborators/dev/permission", (1, "gh: HTTP 502")),
    ])
    r = triggers(shims, "github", check=False)
    assert r.returncode == 1 and r.stdout == "", "a failed lookup must not be judged either way"


def test_triggers_mark_file_holds_the_newest_comment_fetched(shims, tmp_path):
    """Non-trigger comments count too: the watcher's cursor moves on a repo with no triggers."""
    serve(shims, "gh", GH_ROUTES)
    mark = tmp_path / "mark"
    triggers(shims, "github", "--mark-file", str(mark))
    assert mark.read_text().strip() == "2026-01-01T00:00:09Z"

def test_triggers_since_is_strict_and_narrows_the_fetch(shims):
    serve(shims, "gh", GH_ROUTES)
    rows = triggers(shims, "github", "--since", "2026-01-01T00:00:02Z")
    assert [r["comment_id"] for r in rows] == ["1", "3"], "a comment AT the cursor was already handled"
    assert "since=2026-01-01T00:00:02Z" in shims["log"].read_text()
    # an offset form of the same instant compares by time, not by string
    rows = triggers(shims, "github", "--since", "2026-01-01T09:00:02.5+09:00")
    assert [r["comment_id"] for r in rows] == ["1", "3"]
    bad = triggers(shims, "github", "--since", "yesterday", check=False)
    assert bad.returncode == 1 and "ISO-8601" in bad.stderr


def test_triggers_gitlab_checks_write_access_once_per_author(shims):
    notes = [
        {"id": 11, "system": False, "type": None, "author": {"username": "dev", "id": 7},
         "created_at": "2026-01-01T00:00:01.000Z", "body": "/open-pr"},
        {"id": 12, "system": False, "type": "DiffNote", "position": {"new_line": 3},
         "author": {"username": "dev", "id": 7}, "created_at": "2026-01-01T00:00:02.000Z", "body": HOSTILE},
        {"id": 13, "system": False, "type": None, "author": {"username": "guest", "id": 8},
         "created_at": "2026-01-01T00:00:03.000Z", "body": "/open-pr please"},
        {"id": 14, "system": False, "type": None, "author": {"username": "outsider", "id": 9},
         "created_at": "2026-01-01T00:00:04.000Z", "body": "/open-pr hi"},
        {"id": 15, "system": True, "type": None, "author": {"username": "dev", "id": 7},
         "created_at": "2026-01-01T00:00:05.000Z", "body": "/open-pr added 1 commit"},
        {"id": 16, "system": False, "type": None, "author": {"username": "bot", "id": 1},
         "created_at": "2026-01-01T00:00:06.000Z", "body": "/open-pr self"},
    ]
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": 9, "web_url": "https://gitlab.com/o/r/-/merge_requests/9"}]),
        ("merge_requests/9/discussions", [{"id": f"d{n['id']}", "notes": [n]} for n in notes]),
        ("members/all/7", {"access_level": 30}),
        ("members/all/8", {"access_level": 20}),
        ("members/all/9", (1, "glab: 404 Not Found (HTTP 404)")),
        ("members/all/1", {"access_level": 40}),
        ("user", {"username": "bot"}),
    ])
    rows = triggers(shims, "gitlab")
    got = {r["comment_id"]: (r["kind"], r["authorized"]) for r in rows}
    assert got == {"11": ("top", "yes"), "12": ("line", "yes"), "13": ("top", "no"), "14": ("top", "no"),
                   "16": ("top", "yes")}, \
        "Developer+ is yes; Reporter and non-members are no; system notes never trigger; own notes do"
    assert [r for r in rows if r["comment_id"] == "12"][0]["body"] == HOSTILE
    assert {r["comment_id"]: r["thread_id"] for r in rows}["12"] == "d12", \
        "each GitLab note carries its discussion id — a reply lands in the discussion"
    calls = shims["log"].read_text()
    assert calls.count("members/all/7") == 1, "one membership call per distinct author"
    assert "pwned" not in calls


def test_triggers_gitlab_stops_when_membership_cannot_be_read(shims):
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": 9, "web_url": "u"}]),
        ("merge_requests/9/discussions", [{"id": "d1", "notes": [{"id": 1, "author": {"username": "dev", "id": 7},
                                           "created_at": "2026-01-01T00:00:01Z", "body": "/open-pr"}]}]),
        ("members/all/7", (1, "glab: 502 Bad Gateway")),
        ("user", {"username": "bot"}),
    ])
    r = triggers(shims, "gitlab", check=False)
    assert r.returncode == 1 and r.stdout == "", "a failed lookup must not be judged either way"


def test_triggers_bitbucket_marks_authorization_unknown(shims):
    pages = {
        "pullrequests?state=OPEN": {"values": [{"id": 7, "links": {"html": {"href": "https://bitbucket.org/o/r/pull-requests/7"}}}], "next": None},
        "pullrequests/7/comments": {"values": [
            {"id": 21, "content": {"raw": HOSTILE}, "user": {"nickname": "dev"}, "inline": None,
             "created_on": "2026-01-01T00:00:02.123456+00:00", "deleted": False},
            {"id": 22, "content": {"raw": "/open-pr line"}, "user": {"nickname": "dev"},
             "inline": {"path": "a", "to": 1}, "created_on": "2026-01-01T00:00:01.000001+00:00", "deleted": False},
            {"id": 23, "content": {"raw": "/open-pr gone"}, "user": {"nickname": "dev"}, "inline": None,
             "created_on": "2026-01-01T00:00:03+00:00", "deleted": True},
            {"id": 24, "content": {"raw": "/open-pr x [bot-reply]: #"}, "user": {"nickname": "dev"},
             "inline": None, "created_on": "2026-01-01T00:00:04+00:00", "deleted": False},
        ], "next": None},
    }
    serve(shims, "curl", list(pages.items()))
    rows = triggers(shims, "bitbucket")
    assert [(r["comment_id"], r["kind"], r["authorized"]) for r in rows] == \
        [("22", "line", "UNKNOWN"), ("21", "top", "UNKNOWN")], \
        "deleted and marker-carrying comments drop out; order is by time, fraction included"
    assert rows[1]["body"] == HOSTILE and rows[1]["url"] == "https://bitbucket.org/o/r/pull-requests/7"
    assert "pwned" not in shims["log"].read_text()


def test_triggers_token_picks_the_trigger_and_a_mention_ignores_case(shims):
    at = lambda i, body: {"id": i, "issue_url": "https://api.github.com/repos/o/r/issues/5",
                          "user": {"login": "dev"}, "created_at": f"2026-01-01T00:00:0{i}Z",
                          "body": body}
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "https://github.com/o/r/pull/5"}]),
        ("issues/comments", [at(1, "@reviewer please look"), at(2, "@REVIEWER"), at(3, "@reviewer2 no"),
                             at(4, "cc @reviewer mid-body"), at(5, "/open-pr"), at(6, "/Review x"),
                             at(7, "/review"), at(8, "@reviewer claimed\n\n<!-- bot-claim:99 -->")]),
    ])
    rows = triggers(shims, "github", "--token", "@Reviewer")
    assert [r["comment_id"] for r in rows] == ["1", "2"], \
        "a login matches in any case, and only as the whole first word"
    rows = triggers(shims, "github", "--token", "/review")
    assert [r["comment_id"] for r in rows] == ["7"], "a /word token keeps its case"
    rows = triggers(shims, "github")
    assert [r["comment_id"] for r in rows] == ["5"], "the default token is /open-pr"
    for bad in ("open-pr", "/Open", "/open pr", "@", "@-x", "/open-pr;id", "$(id)"):
        r = triggers(shims, "github", "--token", bad, check=False)
        assert r.returncode == 1 and "--token" in r.stderr, bad


def test_triggers_drop_claim_replies_in_either_marker_form(shims):
    """A claim reply quotes the trigger it locks; it must never become a trigger itself."""
    pages = {
        "pullrequests?state=OPEN": {"values": [{"id": 7, "links": {"html": {"href": "u7"}}}], "next": None},
        "pullrequests/7/comments": {"values": [
            {"id": 31, "content": {"raw": "/open-pr go"}, "user": {"nickname": "dev"}, "inline": None,
             "created_on": "2026-01-01T00:00:01+00:00", "deleted": False},
            {"id": 32, "content": {"raw": "/open-pr go\n\n[bot-claim:99]: #"}, "user": {"nickname": "bot"},
             "inline": None, "created_on": "2026-01-01T00:00:02+00:00", "deleted": False},
            {"id": 33, "content": {"raw": "/open-pr go <!-- bot-claim:98 -->"}, "user": {"nickname": "bot"},
             "inline": None, "created_on": "2026-01-01T00:00:03+00:00", "deleted": False},
        ], "next": None},
    }
    serve(shims, "curl", list(pages.items()))
    rows = triggers(shims, "bitbucket")
    assert [(r["comment_id"], r["thread_id"]) for r in rows] == [("31", None)]



def gh_issue(cid, pr, login, at, body):
    return {"id": cid, "issue_url": f"https://api.github.com/repos/o/r/issues/{pr}", "user": {"login": login},
            "created_at": at, "body": body}


def gh_line(cid, pr, login, at, body, reply_to=None, review=None):
    return {"id": cid, "pull_request_url": f"https://api.github.com/repos/o/r/pulls/{pr}", "user": {"login": login},
            "created_at": at, "body": body, "in_reply_to_id": reply_to, "pull_request_review_id": review}


GH_PERMS = [("collaborators/dev/permission", {"permission": "write"}),
            ("collaborators/col/permission", {"permission": "write"}),
            ("collaborators/stranger/permission", {"permission": "read"})]


def test_triggers_github_drops_a_claimed_trigger_top_level_or_in_its_thread(shims):
    """The poll after a stale cursor: every trigger answered by a claim reply stays answered."""
    t = lambda s: f"2026-01-01T00:00:{s:02d}Z"
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "u5"}, {"number": 6, "html_url": "u6"}]),
        ("issues/comments", [
            gh_issue(10, 5, "dev", t(0), "/open-pr old, never claimed"),
            gh_issue(11, 5, "dev", t(1), "/open-pr review"),
            gh_issue(12, 5, "bot", t(2), "> /open-pr review\n\nTaking a look\n\n<!-- bot-claim:11 -->"),
            gh_issue(13, 5, "dev", t(5), "/open-pr again"),
            gh_issue(14, 5, "dev", t(6), "an unrelated lock <!-- bot-claim:777 -->"),
            gh_issue(20, 6, "dev", t(0), "/open-pr on another PR")]),
        ("pulls/comments", [
            gh_line(90, 5, "col", t(3), "/open-pr this hunk"),
            gh_line(91, 5, "bot", t(4), "Đang xem\n\n<!-- bot-claim:90 -->", reply_to=90)]),
    ] + GH_PERMS)
    rows = triggers(shims, "github")
    assert [r["comment_id"] for r in rows] == ["20", "13"], \
        "11 and 90 are claimed; 10 predates the PR's newest claimed trigger; 13 is new; a marker for " \
        "another id and another PR's claims leave a trigger alone"


def test_triggers_count_a_claim_marker_whoever_posted_it(shims):
    """The same rule as `claim`: any comment carrying bot-claim:<C> locks C, so a quoted marker does too."""
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "u5"}]),
        ("issues/comments", [gh_issue(13, 5, "dev", "2026-01-01T00:00:05Z", "/open-pr"),
                             gh_issue(14, 5, "stranger", "2026-01-01T00:00:06Z", "quoting <!-- bot-claim:13 -->")]),
    ] + GH_PERMS)
    assert triggers(shims, "github") == []


def test_triggers_gitlab_drops_a_claimed_note_top_level_or_in_its_discussion(shims):
    note = lambda i, at, body, diff=False: {"id": i, "system": False, "type": "DiffNote" if diff else None,
                                            "author": {"username": "dev", "id": 7},
                                            "created_at": f"2026-01-01T00:00:0{at}.000Z", "body": body}
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": 9, "web_url": "u9"}]),
        ("merge_requests/9/discussions", [
            {"id": "d1", "notes": [note(11, 1, "/open-pr"), note(12, 2, "Taking a look\n\n<!-- bot-claim:11 -->")]},
            {"id": "d2", "notes": [note(13, 3, "/open-pr hunk", True), note(14, 4, "<!-- bot-claim:13 -->", True)]},
            {"id": "d3", "notes": [note(15, 5, "/open-pr new")]},
            {"id": "d4", "notes": [note(16, 6, "<!-- bot-claim:500 -->")]}]),
        ("members/all/7", {"access_level": 30}),
        ("user", {"username": "bot"}),
    ])
    assert [r["comment_id"] for r in triggers(shims, "gitlab")] == ["15"]


def test_triggers_bitbucket_drops_a_claimed_comment_top_level_or_inline(shims):
    c = lambda i, at, raw, parent=None, inline=None: {
        "id": i, "content": {"raw": raw}, "user": {"nickname": "dev"}, "inline": inline, "deleted": False,
        "created_on": f"2026-01-01T00:00:0{at}+00:00", "parent": {"id": parent} if parent else None}
    serve(shims, "curl", list({
        "pullrequests?state=OPEN": {"values": [{"id": 7, "links": {"html": {"href": "u7"}}}], "next": None},
        "pullrequests/7/comments": {"values": [
            c(31, 1, "/open-pr"), c(32, 2, "Taking a look\n\n[bot-claim:31]: #", parent=31),
            c(33, 3, "/open-pr line", inline={"path": "a", "to": 1}),
            c(34, 4, "[bot-claim:33]: #", parent=33, inline={"path": "a", "to": 1}),
            c(35, 5, "/open-pr new"), c(36, 6, "[bot-claim:500]: #")], "next": None},
    }.items()))
    assert [r["comment_id"] for r in triggers(shims, "bitbucket")] == ["35"]


def test_triggers_backlog_github_reads_each_open_prs_comments_and_keeps_one_request_per_pr(shims):
    """A request made before the watcher ever ran is still pending: the PR, not the clock, says so."""
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "u5"}, {"number": 6, "html_url": "u6"}]),
        ("issues/5/comments", [gh_issue(1, 5, "dev", "2025-01-01T00:00:00Z", "/open-pr first"),
                               gh_issue(2, 5, "dev", "2025-02-01T00:00:00Z", "/open-pr second"),
                               gh_issue(7, 5, "stranger", "2025-03-01T00:00:00Z", "/open-pr no write access")]),
        ("pulls/5/comments", [gh_line(8, 5, "col", "2025-01-15T00:00:00Z", "/open-pr hunk")]),
        ("issues/6/comments", [gh_issue(3, 6, "dev", "2025-01-01T00:00:00Z", "/open-pr"),
                               gh_issue(4, 6, "bot", "2025-01-02T00:00:00Z", "<!-- bot-claim:3 -->")]),
    ] + GH_PERMS)
    rows = triggers(shims, "github", "--backlog")
    assert [(r["comment_id"], r["backlog"], r["superseded"], r["created_at"]) for r in rows] == \
        [("2", True, ["1", "8"], "2025-02-01T00:00:00Z")], \
        "PR 5: its newest trigger by a writer, the older ones superseded; PR 6: claimed"
    log = shims["log"].read_text()
    assert "repos/o/r/issues/comments" not in log and "since=" not in log, "never the repo-wide listing"
    assert "issues/8/" not in log, "a closed PR is not fetched"
    r = triggers(shims, "github", "--backlog", "--since", "2026-01-01T00:00:00Z", check=False)
    assert r.returncode == 1 and "--backlog" in r.stderr


def test_triggers_backlog_gitlab_and_bitbucket_list_every_open_pr_whatever_its_age(shims):
    note = lambda i, body, at: {"id": i, "system": False, "author": {"username": "dev", "id": 7},
                                "created_at": at, "body": body}
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": 9, "web_url": "u9"}]),
        ("merge_requests/9/discussions", [{"id": "d1", "notes": [note(11, "/open-pr a", "2025-01-01T00:00:00Z")]},
                                          {"id": "d2", "notes": [note(12, "/open-pr b", "2025-01-02T00:00:00Z")]}]),
        ("members/all/7", {"access_level": 30}),
    ])
    rows = triggers(shims, "gitlab", "--backlog")
    assert [(r["comment_id"], r["thread_id"], r["superseded"]) for r in rows] == [("12", "d2", ["11"])]
    assert "updated_after" not in shims["log"].read_text()
    serve(shims, "curl", list({
        "pullrequests?state=OPEN": {"values": [{"id": 7, "links": {"html": {"href": "u7"}}}], "next": None},
        "pullrequests/7/comments": {"values": [
            {"id": 31, "content": {"raw": "/open-pr"}, "user": {"nickname": "dev"}, "inline": None,
             "created_on": "2025-01-01T00:00:00+00:00", "deleted": False}], "next": None},
    }.items()))
    rows = triggers(shims, "bitbucket", "--backlog")
    assert [(r["comment_id"], r["backlog"], r["superseded"]) for r in rows] == [("31", True, [])]
    assert "q=updated_on" not in shims["log"].read_text()

RATE_LIMITS = [
    ("github", "gh", [("pulls?state=open", (1, "gh: API rate limit exceeded for user ID 1. (HTTP 403)"))]),
    ("github", "gh", [("pulls?state=open", [{"number": 5, "html_url": "u5"}]),
                      ("issues/comments", (1, "gh: You have exceeded a secondary rate limit. (HTTP 403)"))]),
    ("github", "gh", [("pulls?state=open", (1, "gh: API rate limit exceeded (HTTP 429)"))]),
    ("gitlab", "glab", [("merge_requests?state=opened", (1, "glab: 429 Too Many Requests (HTTP 429)"))]),
    ("gitlab", "glab", [
        ("merge_requests?state=opened", [{"iid": 9, "web_url": "u"}]),
        ("merge_requests/9/discussions", [{"id": "d1", "notes": [{"id": 1, "author": {"username": "dev", "id": 7},
                                           "created_at": "2026-01-01T00:00:01Z", "body": "/open-pr"}]}]),
        ("members/all/7", (1, "glab: 429 Too Many Requests (HTTP 429)"))]),
    ("bitbucket", "curl", [("pullrequests?state=OPEN", (22, "curl: (22) The requested URL returned error: 429"))]),
    ("bitbucket", "curl", [
        ("pullrequests?state=OPEN", {"values": [{"id": 7, "links": {"html": {"href": "u7"}}}], "next": None}),
        ("pullrequests/7/comments", (22, "curl: (22) The requested URL returned error: 429"))]),
]


@pytest.mark.parametrize("vendor,cli,routes", RATE_LIMITS)
def test_triggers_exits_9_on_a_vendor_rate_limit(shims, vendor, cli, routes):
    serve(shims, cli, routes)
    r = triggers(shims, vendor, check=False)
    assert (r.returncode, r.stdout) == (9, "") and "rate limited" in r.stderr, r.stderr


@pytest.mark.parametrize("vendor,cli,routes", [
    ("github", "gh", [("pulls?state=open", (1, "gh: Resource not accessible by integration (HTTP 403)"))]),
    ("gitlab", "glab", [("merge_requests?state=opened", (1, "glab: 500 Internal Server Error (HTTP 500)"))]),
    ("bitbucket", "curl", [("pullrequests?state=OPEN", (22, "curl: (22) The requested URL returned error: 403"))]),
])
def test_triggers_keeps_any_other_failure_as_it_is(shims, vendor, cli, routes):
    serve(shims, cli, routes)
    r = triggers(shims, vendor, check=False)
    assert r.returncode not in (0, 9) and routes[0][1][1] in r.stderr


def test_triggers_bitbucket_lists_only_the_prs_updated_since(shims):
    """One comments call per open PR each poll would eat the hourly quota on a busy repo."""
    serve(shims, "curl", [("pullrequests?state=OPEN", {"values": [], "next": None})])
    triggers(shims, "bitbucket", "--since", "2026-01-01T09:00:02+09:00")
    assert "pullrequests?state=OPEN&pagelen=50&fields=next,values.id,values.links.html.href,values.title" \
           ",values.author.nickname,values.source.branch.name,values.updated_on&q=updated_on%20%3E%202026-01-01T00%3A00%3A02%2B00%3A00" in shims["log"].read_text()
    shims["log"].write_text("")
    triggers(shims, "bitbucket")
    assert "q=updated_on" not in shims["log"].read_text()


# --------------------------------------------- triggers: answered by a review ----
# A review this plugin published after a trigger answers it, whether a watcher or a manual
# `/open-pr:review` posted it: the person who reviewed by hand and then starts a watcher is not asked again.

def gh_review(rid, at, body, state="COMMENTED"):
    return {"id": rid, "state": state, "submitted_at": at, "body": body, "user": {"login": "bot"}}


T = lambda s: f"2026-01-01T00:00:{s:02d}Z"
MARK_GH = "\n\n<!-- bot-finding -->"
GH_ANSWERED = [
    ("pulls?state=open", [{"number": n, "html_url": f"u{n}"} for n in (5, 6, 7, 8, 9, 10, 11)]),
    ("issues/comments", [
        gh_issue(50, 5, "dev", T(1), "/open-pr"),
        gh_issue(60, 6, "dev", T(1), "/open-pr"),
        gh_issue(70, 7, "dev", T(0), "/open-pr before the review"),
        gh_issue(71, 7, "dev", T(3), "/open-pr after the review"),
        gh_issue(80, 8, "dev", T(1), "/open-pr"),
        gh_issue(90, 9, "dev", T(1), "/open-pr"),
        gh_issue(100, 10, "dev", T(2), "/open-pr"),
        gh_issue(110, 11, "dev", T(1), "no request here")]),
    # a LINE-only review: its body says nothing, its line comment keeps the draft's creation time
    ("pulls/comments", [gh_line(61, 6, "bot", T(0), "🔵 x" + MARK_GH, review=601)]),
    ("pulls/5/reviews", [gh_review(501, T(3), "### Overview\n🔴 x" + MARK_GH)]),
    ("pulls/6/reviews", [gh_review(601, T(3), "")]),
    ("pulls/7/reviews", [gh_review(701, T(2), "🔴 x" + MARK_GH)]),
    ("pulls/8/reviews", [gh_review(801, None, "🔴 x" + MARK_GH, state="PENDING")]),
    ("pulls/9/reviews", [gh_review(901, T(3), "LGTM, a human's review")]),
    ("pulls/10/reviews", [gh_review(1001, T(2), "🔴 x" + MARK_GH)]),
    ("pulls/11/reviews", [gh_review(1101, T(3), "🔴 x" + MARK_GH)]),
] + GH_PERMS


def test_triggers_github_a_plugin_review_after_a_trigger_answers_it(shims):
    serve(shims, "gh", GH_ANSWERED)
    rows = triggers(shims, "github")
    assert [r["comment_id"] for r in rows] == ["80", "90", "100", "71"], \
        "5: a marked review body after it; 6: a review whose line comment is marked (submitted_at, not the " \
        "draft's time); 7: only the trigger older than the review; 8: a draft answers nothing; 9: a human's " \
        "review; 10: the same second is no proof the review saw the request"
    log = shims["log"].read_text()
    assert sorted(re.findall(r"pulls/(\d+)/reviews", log), key=int) == ["5", "6", "7", "8", "9", "10"], \
        "one reviews call per PR with a candidate trigger, none for PR 11 that has no request"
    shims["log"].write_text("")
    triggers(shims, "github", "--since", T(9))
    assert "/reviews" not in shims["log"].read_text(), "a poll with no new request spends no reviews call"


def test_triggers_github_reads_a_prs_reviews_once_for_both_findings_and_the_answered_check(shims, tmp_path):
    serve(shims, "gh", GH_ANSWERED)
    triggers(shims, "github", "--findings-file", str(tmp_path / "f.jsonl"), "--fix-prs", "5,11")
    log = shims["log"].read_text()
    assert log.count("pulls/5/reviews") == 1, "the fix role and the answered check share one fetch"
    assert log.count("pulls/11/reviews") == 1, "a fix-role PR without a request: the findings fetch only"


def test_triggers_backlog_github_skips_a_pr_a_manual_review_already_answered(shims):
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "u5"}, {"number": 6, "html_url": "u6"}]),
        ("issues/5/comments", [gh_issue(50, 5, "dev", T(1), "/open-pr")]),
        ("issues/6/comments", [gh_issue(60, 6, "dev", T(1), "/open-pr")]),
        ("pulls/5/reviews", [gh_review(501, T(3), "**LGTM 🌟**" + MARK_GH)]),
        ("pulls/6/reviews", [gh_review(601, T(0), "🔴 x" + MARK_GH)]),
    ] + GH_PERMS)
    rows = triggers(shims, "github", "--backlog")
    assert [(r["comment_id"], r["superseded"]) for r in rows] == [("60", [])]


def gl_note(i, at, body, author="dev", uid=7, diff=False):
    return {"id": i, "system": False, "type": "DiffNote" if diff else None, "author": {"username": author, "id": uid},
            "created_at": f"2026-01-01T00:00:0{at}.000Z", "body": body}


@pytest.mark.parametrize("mode", [[], ["--backlog"]])
def test_triggers_gitlab_a_plugin_review_after_a_trigger_answers_it(shims, mode):
    mk = "\n\n<!-- bot-finding -->"
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": n, "web_url": f"u{n}"} for n in (9, 10, 12, 13, 14)]),
        ("merge_requests/9/discussions", [{"id": "a", "notes": [gl_note(91, 1, "/open-pr")]},
                                          {"id": "b", "notes": [gl_note(92, 3, "Overview\n🔴 x" + mk, "bot", 1)]}]),
        ("merge_requests/10/discussions", [{"id": "a", "notes": [gl_note(101, 1, "🔴 x" + mk, "bot", 1)]},
                                           {"id": "b", "notes": [gl_note(102, 3, "/open-pr")]}]),
        ("merge_requests/12/discussions", [{"id": "a", "notes": [gl_note(121, 2, "/open-pr")]},
                                           {"id": "b", "notes": [gl_note(122, 2, "🔴 x" + mk, "bot", 1)]}]),
        ("merge_requests/13/discussions", [{"id": "a", "notes": [gl_note(131, 1, "/open-pr")]},
                                           {"id": "b", "notes": [gl_note(132, 3, "LGTM, a human's note", "rev", 8)]}]),
        ("merge_requests/14/discussions", [{"id": "a", "notes": [gl_note(141, 1, "/open-pr")]},
                                           {"id": "b", "notes": [gl_note(142, 3, "🔵 x" + mk, "bot", 1, diff=True)]}]),
        ("members/all/7", {"access_level": 30}),
    ])
    assert sorted(r["comment_id"] for r in triggers(shims, "gitlab", *mode)) == ["102", "121", "131"], \
        "9: a marked overview after it; 14: a marked line note after it (a LINE-only review); 10: the review " \
        "predates it; 12: the same instant; 13: a human's note"


@pytest.mark.parametrize("mode", [[], ["--backlog"]])
def test_triggers_bitbucket_a_plugin_review_after_a_trigger_answers_it(shims, mode):
    mk = "\n\n[bot-finding]: #"
    c = lambda i, at, raw, nick="dev", inline=None: {
        "id": i, "content": {"raw": raw}, "user": {"nickname": nick}, "inline": inline, "deleted": False,
        "created_on": f"2026-01-01T00:00:0{at}+00:00", "parent": None}
    serve(shims, "curl", list({
        "pullrequests?state=OPEN": {"values": [{"id": n, "links": {"html": {"href": f"u{n}"}}} for n in (7, 8, 12, 13, 14)],
                                    "next": None},
        "pullrequests/7/comments": {"values": [c(71, 1, "/open-pr"), c(72, 3, "Overview\n🔴 x" + mk, "bot")], "next": None},
        "pullrequests/8/comments": {"values": [c(81, 1, "🔴 x" + mk, "bot"), c(82, 3, "/open-pr")], "next": None},
        "pullrequests/12/comments": {"values": [c(121, 2, "/open-pr"), c(122, 2, "🔴 x" + mk, "bot")], "next": None},
        "pullrequests/13/comments": {"values": [c(131, 1, "/open-pr"), c(132, 3, "LGTM, a human's", "rev")], "next": None},
        "pullrequests/14/comments": {"values": [c(141, 1, "/open-pr"),
                                                c(142, 3, "🔵 x" + mk, "bot", inline={"path": "a", "to": 1})], "next": None},
    }.items()))
    assert sorted(r["comment_id"] for r in triggers(shims, "bitbucket", *mode)) == ["121", "131", "82"]


# Reviews posted before the overview carried the review marker: the template's fixed opening (its
# heading, or the LGTM line) in a body posted AS the overview. A comment quoting it is no review.
LGTM_OLD = "**LGTM 🌟** (commit [aaaaaaa](https://x/c/a))"
HEADING_OLD = "### 🤖【AI REVIEW】Overview\nCảm ơn 🙏 — đã review toàn bộ tại commit [aaaaaaa](https://x/c/a)."
QUOTES = ["> **LGTM 🌟** (commit [aaaaaaa](https://x/c/a))\n\nagreed", "the bot said ### 🤖【AI REVIEW】Overview"]


def test_triggers_github_an_overview_by_its_marker_or_template_opening_answers_a_trigger(shims):
    prs = (5, 6, 7, 8, 9)
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": n, "html_url": f"u{n}"} for n in prs]),
        ("issues/comments", [gh_issue(n * 10, n, "dev", T(1), "/open-pr") for n in prs]
         + [gh_issue(91, 9, "rev", T(3), LGTM_OLD)]),
        ("pulls/5/reviews", [gh_review(501, T(3), "**LGTM 🌟** (commit x)\n\n<!-- bot-review -->")]),
        ("pulls/6/reviews", [gh_review(601, T(3), LGTM_OLD)]),
        ("pulls/7/reviews", [gh_review(701, T(3), HEADING_OLD)]),
        ("pulls/8/reviews", [gh_review(801, T(3), QUOTES[0]), gh_review(802, T(3), QUOTES[1])]),
    ] + GH_PERMS)
    assert [r["comment_id"] for r in triggers(shims, "github")] == ["80", "90"], \
        "5: the stamped marker; 6, 7: an older review's fixed opening; 8: a review quoting it; " \
        "9: an issue comment is never a review"


@pytest.mark.parametrize("mode", [[], ["--backlog"]])
def test_triggers_gitlab_an_overview_by_its_marker_or_template_opening_answers_a_trigger(shims, mode):
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": n, "web_url": f"u{n}"} for n in (5, 6, 7, 8, 9)]),
        ("merge_requests/5/discussions", [{"id": "a", "notes": [gl_note(51, 1, "/open-pr")]},
                                          {"id": "b", "notes": [gl_note(52, 3, "**LGTM 🌟** x\n\n<!-- bot-review -->", "bot", 1)]}]),
        ("merge_requests/6/discussions", [{"id": "a", "notes": [gl_note(61, 1, "/open-pr")]},
                                          {"id": "b", "notes": [gl_note(62, 3, LGTM_OLD, "bot", 1)]}]),
        ("merge_requests/7/discussions", [{"id": "a", "notes": [gl_note(71, 1, "/open-pr")]},
                                          {"id": "b", "notes": [gl_note(72, 3, HEADING_OLD, "bot", 1)]}]),
        ("merge_requests/8/discussions", [{"id": "a", "notes": [gl_note(81, 1, "/open-pr")]},
                                          {"id": "b", "notes": [gl_note(82, 3, QUOTES[0], "rev", 8)]},
                                          {"id": "c", "notes": [gl_note(83, 3, QUOTES[1], "rev", 8)]}]),
        ("merge_requests/9/discussions", [{"id": "a", "notes": [gl_note(91, 1, "/open-pr"),
                                                                gl_note(92, 3, LGTM_OLD, "rev", 8)]}]),
        ("members/all/7", {"access_level": 30}),
    ])
    assert sorted(r["comment_id"] for r in triggers(shims, "gitlab", *mode)) == ["81", "91"], \
        "5: the stamped marker; 6, 7: an older overview's fixed opening; 8: a note quoting it; " \
        "9: a reply inside a discussion is no overview"


@pytest.mark.parametrize("mode", [[], ["--backlog"]])
def test_triggers_bitbucket_an_overview_by_its_marker_or_template_opening_answers_a_trigger(shims, mode):
    c = lambda i, at, raw, nick="dev", parent=None: {
        "id": i, "content": {"raw": raw}, "user": {"nickname": nick}, "inline": None, "deleted": False,
        "created_on": f"2026-01-01T00:00:0{at}+00:00", "parent": {"id": parent} if parent else None}
    serve(shims, "curl", list({
        "pullrequests?state=OPEN": {"values": [{"id": n, "links": {"html": {"href": f"u{n}"}}} for n in (5, 6, 7, 8, 9)],
                                    "next": None},
        "pullrequests/5/comments": {"values": [c(51, 1, "/open-pr"), c(52, 3, "**LGTM 🌟** x\n\n[bot-review]: #", "bot")],
                                    "next": None},
        "pullrequests/6/comments": {"values": [c(61, 1, "/open-pr"), c(62, 3, LGTM_OLD, "bot")], "next": None},
        "pullrequests/7/comments": {"values": [c(71, 1, "/open-pr"), c(72, 3, HEADING_OLD, "bot")], "next": None},
        "pullrequests/8/comments": {"values": [c(81, 1, "/open-pr"), c(82, 3, QUOTES[0], "rev"), c(83, 3, QUOTES[1], "rev")],
                                    "next": None},
        "pullrequests/9/comments": {"values": [c(91, 1, "/open-pr"), c(92, 3, LGTM_OLD, "rev", parent=91)], "next": None},
    }.items()))
    assert sorted(r["comment_id"] for r in triggers(shims, "bitbucket", *mode)) == ["81", "91"]


# ------------------------------------------------------- triggers: ETags ----

def etag_gh(shims, pages, etag='W/"e1"', not_modified=True, headers="X-Ratelimit-Remaining: 4999\\r\\n"):
    """gh answering `api -i` like the real one: status line + headers + body; a matching
    If-None-Match gets `304` and exit 1 (gh treats every status > 299 as an error)."""
    d = Path(shims["tmp"]) / "etag-pages"
    d.mkdir(exist_ok=True)
    cases = []
    for i, (pat, body) in enumerate(pages):
        (d / f"{i}.json").write_text(json.dumps(body))
        cases.append(f'  *"{pat}"*) f="{d}/{i}.json" ;;')
    make_shim(Path(shims["path"]), "gh", f'''printf '%s\\n' "gh $*" >> "{shims['log']}"
f=""
case "$*" in
{chr(10).join(cases)}
esac
[ -n "$f" ] || {{ printf '[]\\n'; exit 0; }}
case "$*" in
  *'If-None-Match: {etag}'*) if [ "{1 if not_modified else ''}" = 1 ]; then
        printf 'HTTP/2.0 304 Not Modified\\r\\nEtag: {etag}\\r\\n{headers}\\r\\n'; printf 'gh: HTTP 304\\n' >&2; exit 1; fi ;;
esac
case "$*" in
  *" -i "*) printf 'HTTP/2.0 200 OK\\r\\nEtag: {etag}\\r\\n{headers}\\r\\n' ;;
esac
cat "$f"
''')


ETAG_PAGES = [
    ("pulls?state=open", [{"number": 5, "html_url": "https://github.com/o/r/pull/5", "user": {"login": "dev"},
                           "updated_at": "2026-01-01T00:00:09Z"}]),
    ("issues/comments", [{"id": 1, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
                          "created_at": "2026-01-01T00:00:03Z", "body": "/open-pr"}]),
    ("pulls/comments", []),
    ("pulls/5/reviews", []),
    ("collaborators/dev/permission", {"permission": "write", "role_name": "write"}),
]


def test_triggers_github_sends_the_kept_etag_and_a_304_serves_the_cached_body(shims, tmp_path):
    etag_gh(shims, ETAG_PAGES)
    cache = tmp_path / "etags"
    first = triggers(shims, "github", "--cache-dir", str(cache))
    log = shims["log"].read_text()
    assert "If-None-Match" not in log, "nothing cached yet: a plain request"
    shims["log"].write_text("")
    again = triggers(shims, "github", "--cache-dir", str(cache))
    assert again == first and [r["comment_id"] for r in again] == ["1"]
    assert again[0]["pr_author"] == "dev"
    assert shims["log"].read_text().count('If-None-Match: W/"e1"') == 5, \
        "every poll GET is conditional, the reviews of a PR with a trigger and the permission lookup of " \
        "its author included"


def test_triggers_github_never_sends_a_cached_etag_outside_its_shape(shims, tmp_path):
    etag_gh(shims, ETAG_PAGES, etag='W/e1;id')
    cache = tmp_path / "etags"
    triggers(shims, "github", "--cache-dir", str(cache))
    shims["log"].write_text("")
    triggers(shims, "github", "--cache-dir", str(cache))
    assert "If-None-Match" not in shims["log"].read_text()


def test_triggers_github_fetches_a_paged_listing_whole_and_uncached(shims, tmp_path):
    make_shim(Path(shims["path"]), "gh", f'''printf '%s\\n' "gh $*" >> "{shims['log']}"
case "$*" in
  *" -i "*) printf 'HTTP/2.0 200 OK\\r\\nEtag: "x"\\r\\nLink: <https://api.github.com/x?page=2>; rel="next"\\r\\n\\r\\n[]' ;;
  *--paginate*pulls?state=open*) printf '[{{"number": 5, "html_url": "u5"}}][{{"number": 6, "html_url": "u6"}}]' ;;
  *) printf '[]' ;;
esac
''')
    triggers(shims, "github", "--cache-dir", str(tmp_path / "etags"))
    assert "--paginate repos/o/r/pulls?state=open" in shims["log"].read_text()
    assert not list((tmp_path / "etags").glob("*.body")), "a partial page is never cached"


def test_triggers_github_conditional_request_still_exits_9_on_a_rate_limit(shims, tmp_path):
    make_shim(Path(shims["path"]), "gh", '''printf 'HTTP/2.0 403 Forbidden\\r\\nX-Ratelimit-Remaining: 0\\r\\n\\r\\n{}'
printf 'gh: API rate limit exceeded (HTTP 403)\\n' >&2; exit 1
''')
    r = triggers(shims, "github", "--cache-dir", str(tmp_path / "etags"), check=False)
    assert r.returncode == 9 and r.stdout == ""


# ------------------------------------------------------- triggers: quota ----

def quota(shims, tmp_path, vendor, *extra, check=True):
    q = tmp_path / "quota.json"
    q.unlink(missing_ok=True)
    r = triggers(shims, vendor, "--quota-file", str(q), *extra, check=check)
    return json.loads(q.read_text()) if q.exists() else None, r


GH_QUOTA = "X-RateLimit-Limit: 5000\\r\\nX-RateLimit-Remaining: 4812\\r\\nX-RateLimit-Reset: 1767225600\\r\\n"


def test_quota_github_reads_the_headers_of_the_polls_own_requests(shims, tmp_path):
    etag_gh(shims, ETAG_PAGES, headers=GH_QUOTA)
    cache = str(tmp_path / "etags")
    q, _ = quota(shims, tmp_path, "github", "--cache-dir", cache)
    assert q == {"vendor": "github", "window": 3600, "measured": True, "limit": 5000, "remaining": 4812,
                 "reset": "2026-01-01T00:00:00Z", "near_limit": None, "calls": 5}
    assert shims["log"].read_text().count("gh ") == 5, \
        "no request is added to read the quota: PRs, 2 comment listings, the reviews of the PR with a " \
        "trigger, its author's permission"
    q, _ = quota(shims, tmp_path, "github", "--cache-dir", cache)
    assert q["remaining"] == 4812 and q["calls"] == 0, "a 304 carries the headers and costs nothing"


def test_quota_github_without_headers_keeps_the_documented_limit_and_drops_hostile_values(shims, tmp_path):
    etag_gh(shims, ETAG_PAGES, headers="X-RateLimit-Remaining: 5; touch /tmp/pwned\\r\\n")
    q, _ = quota(shims, tmp_path, "github", "--cache-dir", str(tmp_path / "etags"))
    assert (q["measured"], q["limit"], q["remaining"], q["reset"]) == (False, 5000, None, None)
    assert not Path("/tmp/pwned").exists()


@pytest.mark.parametrize("value, limit", [("0", 0), ("1", 1), ("999999999999", 999999999999),
                                          ("9999999999999", 5000), ("abc", 5000), ("-1", 5000), ("1e3", 5000),
                                          ("50 00", 5000), ("5000; touch /tmp/pwned", 5000), ("", 5000)])
def test_quota_limit_header_kept_only_as_a_bounded_whole_number(shims, tmp_path, value, limit):
    """A header outside 1-12 digits falls back to the vendor's documented limit, as no header does."""
    etag_gh(shims, ETAG_PAGES, headers=f"X-RateLimit-Limit: {value}\\r\\n")
    q, _ = quota(shims, tmp_path, "github", "--cache-dir", str(tmp_path / "etags"))
    assert (q["limit"], q["measured"]) == (limit, limit != 5000 or value == "5000")
    assert not Path("/tmp/pwned").exists()


def test_quota_survives_a_rate_limit_exit(shims, tmp_path):
    make_shim(Path(shims["path"]), "gh", '''printf 'HTTP/2.0 403 Forbidden\\r\\nX-Ratelimit-Limit: 5000\\r\\nX-Ratelimit-Remaining: 0\\r\\n\\r\\n{}'
printf 'gh: API rate limit exceeded (HTTP 403)\\n' >&2; exit 1
''')
    q, r = quota(shims, tmp_path, "github", "--cache-dir", str(tmp_path / "etags"), check=False)
    assert r.returncode == 9 and (q["limit"], q["remaining"]) == (5000, 0)


def test_quota_gitlab_reads_every_page_header_and_keeps_the_bodies(shims, tmp_path):
    # as glab 1.110 prints `api -i --paginate`: status line, headers, blank line, body — per page
    page = lambda rem, body, nxt="": (f"HTTP/1.1 200 OK\r\nRatelimit-Limit: 2000\r\nRatelimit-Remaining: {rem}\r\n"
                                      f"Ratelimit-Reset: 1767225600\r\n{nxt}\r\n" + json.dumps(body) + "\n")
    note = {"id": 11, "author": {"username": "dev", "id": 7}, "created_at": "2026-01-01T00:00:01Z",
            "body": HOSTILE + "\nHTTP/1.1 200 OK\nRatelimit-Remaining: 1"}
    d = tmp_path / "gl-pages"
    d.mkdir()
    (d / "mrs").write_text(page(1990, [{"iid": 9, "web_url": "u9"}], 'Link: <x?page=2>; rel="next"\r\n')
                           + page(1989, [{"iid": 10, "web_url": "u10"}]))
    (d / "d9").write_text(page(1988, [{"id": "d1", "notes": [note]}]))
    (d / "d10").write_text(page(1987, []))
    make_shim(Path(shims["path"]), "glab", f'''printf '%s\\n' "glab $*" >> "{shims['log']}"
case "$*" in
  *" -i "*merge_requests\\?state=opened*) cat "{d}/mrs" ;;
  *" -i "*merge_requests/9/discussions*) cat "{d}/d9" ;;
  *" -i "*merge_requests/10/discussions*) cat "{d}/d10" ;;
  *members/all/7*) printf '{{"access_level": 30}}' ;;
  *) printf '[]' ;;
esac
''')
    q, r = quota(shims, tmp_path, "gitlab")
    assert [x["body"] for x in r] == [note["body"]], "a body is data, never a header line"
    assert q == {"vendor": "gitlab", "window": 60, "measured": True, "limit": 2000, "remaining": 1987,
                 "reset": "2026-01-01T00:00:00Z", "near_limit": None, "calls": 5}, \
        "2 listing pages + 2 discussions + 1 membership; the last response's headers win"


def test_quota_gitlab_without_headers_knows_no_limit(shims, tmp_path):
    serve(shims, "glab", [("merge_requests?state=opened", [])])
    q, _ = quota(shims, tmp_path, "gitlab")
    assert (q["measured"], q["limit"], q["remaining"], q["calls"]) == (False, None, None, 1)


def test_quota_bitbucket_reads_the_dumped_headers(shims, tmp_path):
    make_shim(Path(shims["path"]), "curl", f'''printf '%s\\n' "curl $*" >> "{shims['log']}"
prev=""; for a in "$@"; do [ "$prev" != -D ] || printf 'HTTP/2 200\\r\\nX-RateLimit-Limit: 1000\\r\\nX-RateLimit-NearLimit: true\\r\\n\\r\\n' > "$a"; prev="$a"; done
printf '{{"values": [], "next": null}}'
''')
    q, _ = quota(shims, tmp_path, "bitbucket")
    assert (q["measured"], q["limit"], q["remaining"], q["near_limit"], q["window"]) == (True, 1000, None, True, 3600)
    serve(shims, "curl", [("pullrequests?state=OPEN", {"values": [], "next": None})])
    q, _ = quota(shims, tmp_path, "bitbucket")
    assert (q["measured"], q["limit"], q["near_limit"], q["calls"]) == (False, 1000, None, 1)


# ----------------------------------------------------- triggers: findings ----

MF, MR = "<!-- bot-finding -->", "<!-- bot-reply -->"
OVERVIEW = ("### Overview\nThanks 🙏\n\n#### 🔴 MUST FIX\n🔴 **`a.rb`** — nil deref\n\n" + MF +
            "\n\n#### 🔵 SUGGESTION\n🔵 **`b.rb`** — rename\n\n" + MF + "\n")


def test_findings_github_groups_one_review_with_its_line_and_file_findings(shims, tmp_path):
    line = lambda i, body, at, review=70, reply_to=None, pr=5: {
        "id": i, "pull_request_url": f"https://api.github.com/repos/o/r/pulls/{pr}", "user": {"login": "rev"},
        "created_at": at, "body": body, "pull_request_review_id": review,
        "in_reply_to_id": reply_to}
    serve(shims, "gh", [
        ("pulls?state=open", [
            {"number": 5, "html_url": "https://github.com/o/r/pull/5", "title": "Add retry", "user": {"login": "Dev"}, "head": {"ref": "feat/x"},
             "updated_at": "2026-01-01T00:01:00Z"},
            {"number": 6, "html_url": "https://github.com/o/r/pull/6", "user": {"login": "other"}, "updated_at": "2026-01-01T00:01:00Z"},
            {"number": 7, "html_url": "https://github.com/o/r/pull/7", "user": {"login": "dev"}, "updated_at": "2025-12-01T00:00:00Z"}]),
        ("pulls/comments", [
            line(10, "🟠 **SHOULD FIX** guard it\n\n" + MF, "2026-01-01T00:00:10Z"),
            line(11, "🟠 x\n\n" + MF, "2026-01-01T00:00:10Z"),
            line(12, "Fixed\n\n" + MR, "2026-01-01T00:00:20Z", reply_to=11),
            line(13, "📝 old\n\n" + MF, "2025-12-31T00:00:00Z", review=60),
            line(14, "🔴 other PR\n\n" + MF, "2026-01-01T00:00:10Z", review=71, pr=6),
        ]),
        ("pulls/5/reviews", [{"id": 70, "state": "COMMENTED", "user": {"login": "rev"}, "body": OVERVIEW,
                              "submitted_at": "2026-01-01T00:00:10Z"},
                             {"id": 69, "state": "PENDING", "user": {"login": "rev"}, "body": OVERVIEW,
                              "submitted_at": None}]),
    ])
    out = tmp_path / "findings"
    triggers(shims, "github", "--since", "2026-01-01T00:00:00Z", "--findings-file", str(out), "--fix-author", "dev")
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert rows == [{"pr": 5, "url": "https://github.com/o/r/pull/5", "title": "Add retry", "head_branch": "feat/x", "review_id": "70", "comment_id": "10",
                     "thread_id": None, "kind": "line", "user": "rev", "created_at": "2026-01-01T00:00:10Z",
                     "counts": {"🔴": 1, "🟠": 1, "🔵": 1}}], \
        "a replied finding, a finding before --since and another author's PR do not count; the " \
        "heading emoji is not a finding"
    log = shims["log"].read_text()
    assert "pulls/5/reviews" in log and "pulls/7/reviews" not in log and "pulls/6/reviews" not in log, \
        "reviews are fetched only for the user's own PRs updated since"


def test_findings_github_counts_a_draft_reviews_older_line_comments_once_it_is_published(shims, tmp_path):
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "u5", "user": {"login": "dev"}, "updated_at": "2026-01-02T00:00:00Z"}]),
        ("pulls/comments", [{"id": 10, "pull_request_url": "https://api.github.com/repos/o/r/pulls/5", "user": {"login": "rev"},
                             "created_at": "2025-12-31T00:00:00Z", "body": "🟠 x\n\n" + MF, "pull_request_review_id": 70}]),
        ("pulls/5/reviews", [{"id": 70, "state": "COMMENTED", "user": {"login": "rev"}, "body": "**LGTM** none",
                              "submitted_at": "2026-01-01T12:00:00Z"}]),
    ])
    out = tmp_path / "findings"
    triggers(shims, "github", "--since", "2026-01-01T00:00:00Z", "--findings-file", str(out), "--fix-author", "dev")
    assert [(json.loads(l)["review_id"], json.loads(l)["counts"]) for l in out.read_text().splitlines()] == \
        [("70", {"🟠": 1})], "the comment was written as a draft before --since, published after"


def test_findings_listed_prs_count_whoever_wrote_them(shims, tmp_path):
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 6, "html_url": "u6", "user": {"login": "other"}, "updated_at": "2026-01-01T00:01:00Z"}]),
        ("pulls/comments", [{"id": 14, "pull_request_url": "https://api.github.com/repos/o/r/pulls/6", "user": {"login": "rev"},
                             "created_at": "2026-01-01T00:00:10Z", "body": "🔴 y\n\n" + MF, "pull_request_review_id": 71}]),
    ])
    out = tmp_path / "findings"
    triggers(shims, "github", "--findings-file", str(out), "--fix-prs", "3,6")
    assert [json.loads(l)["review_id"] for l in out.read_text().splitlines()] == ["71"]
    assert triggers(shims, "github", "--findings-file", str(out), "--fix-prs", "6;id", check=False).returncode == 4


def test_findings_gitlab_reads_them_from_the_discussions_already_fetched(shims, tmp_path):
    note = lambda i, body, pos=None: {"id": i, "system": False, "type": "DiffNote" if pos else None, "position": pos,
                                      "author": {"username": "rev", "id": 3}, "created_at": f"2026-01-01T00:00:{i:02d}Z", "body": body}
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": 9, "web_url": "https://gitlab.com/o/r/-/merge_requests/9",
                                          "author": {"username": "dev"}, "source_branch": "feat/g",
                                          "updated_at": "2026-01-01T00:01:00Z"}]),
        ("merge_requests/9/discussions", [
            {"id": "d1", "notes": [note(11, "🟠 a\n\n" + MF, {"new_line": 3})]},
            {"id": "d2", "notes": [note(12, "🔵 b\n\n" + MF, {"new_line": 4}), note(13, "done\n\n" + MR)]},
            {"id": "d3", "notes": [note(14, OVERVIEW)]},
        ]),
    ])
    out = tmp_path / "findings"
    triggers(shims, "gitlab", "--findings-file", str(out), "--fix-author", "dev")
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert [(r["review_id"], r["thread_id"], r["head_branch"], r["counts"]) for r in rows] == \
        [("c11", "d1", "feat/g", {"🟠": 1, "🔴": 1, "🔵": 1})], "one review per PR; the replied discussion drops out"
    assert "reviews" not in shims["log"].read_text(), "no request beyond the poll's own"


def test_findings_bitbucket_takes_replies_by_parent(shims, tmp_path):
    bmf, bmr = "[bot-finding]: #", "[bot-reply]: #"
    serve(shims, "curl", [
        ("pullrequests?state=OPEN", {"values": [{"id": 7, "links": {"html": {"href": "u7"}}, "author": {"nickname": "dev"},
                                                 "source": {"branch": {"name": "feat/b"}},
                                                 "updated_on": "2026-01-01T00:01:00+00:00"}], "next": None}),
        ("pullrequests/7/comments", {"values": [
            {"id": 21, "content": {"raw": "🔴 a\n\n" + bmf}, "user": {"nickname": "rev"}, "inline": {"path": "a", "to": 1},
             "created_on": "2026-01-01T00:00:02+00:00", "deleted": False},
            {"id": 22, "content": {"raw": "🟠 b\n\n" + bmf}, "user": {"nickname": "rev"}, "inline": {"path": "a", "to": 2},
             "created_on": "2026-01-01T00:00:03+00:00", "deleted": False},
            {"id": 23, "content": {"raw": "ok\n\n" + bmr}, "user": {"nickname": "dev"}, "inline": None, "parent": {"id": 22},
             "created_on": "2026-01-01T00:00:04+00:00", "deleted": False},
        ], "next": None}),
    ])
    out = tmp_path / "findings"
    triggers(shims, "bitbucket", "--findings-file", str(out), "--fix-author", "dev")
    assert [(json.loads(l)["comment_id"], json.loads(l)["head_branch"], json.loads(l)["counts"])
            for l in out.read_text().splitlines()] == [("21", "feat/b", {"🔴": 1})]


# ------------------------------------------------------------ open-prs ----

def open_prs(shims, vendor, check=True):
    r = run("open-prs", "--vendor", vendor, "--owner", "o", "--repo", "r", env_extra=env_for(shims), check=check)
    return r if not check else r.stdout.split()


def test_open_prs_github_lists_every_open_pr(shims):
    serve(shims, "gh", [("pulls?state=open", "5\n12\n")])
    assert open_prs(shims, "github") == ["5", "12"]
    assert "gh api --paginate repos/o/r/pulls?state=open&per_page=100 --jq .[].number" in shims["log"].read_text()


def test_open_prs_gitlab_reads_every_page_of_opened_mrs(shims):
    serve(shims, "glab", [("merge_requests?state=opened", '[{"iid": 3}, {"iid": 4}]\n[{"iid": 9}]\n')])
    assert open_prs(shims, "gitlab") == ["3", "4", "9"]
    assert "--paginate projects/o%2Fr/merge_requests?state=opened&per_page=100" in shims["log"].read_text()


def test_open_prs_bitbucket_follows_next(shims):
    nxt = "https://api.bitbucket.org/2.0/repositories/o/r/pullrequests?state=OPEN&page=2"
    serve(shims, "curl", [("pullrequests?state=OPEN", Seq([{"values": [{"id": 7}], "next": nxt},
                                                           {"values": [{"id": 8}], "next": None}]))])
    assert open_prs(shims, "bitbucket") == ["7", "8"]
    assert "page=2" in shims["log"].read_text()


@pytest.mark.parametrize("vendor,cli,routes", [
    ("github", "gh", [("pulls?state=open", (1, "gh: API rate limit exceeded for user ID 1. (HTTP 403)"))]),
    ("gitlab", "glab", [("merge_requests?state=opened", (1, "glab: 429 Too Many Requests (HTTP 429)"))]),
    ("bitbucket", "curl", [("pullrequests?state=OPEN", (22, "curl: (22) The requested URL returned error: 429"))]),
])
def test_open_prs_exits_9_on_a_vendor_rate_limit(shims, vendor, cli, routes):
    serve(shims, cli, routes)
    r = open_prs(shims, vendor, check=False)
    assert (r.returncode, r.stdout) == (9, "") and "rate limited" in r.stderr, r.stderr


def test_open_prs_keeps_any_other_failure_as_it_is(shims):
    serve(shims, "glab", [("merge_requests?state=opened", (1, "glab: 500 Internal Server Error (HTTP 500)"))])
    r = open_prs(shims, "gitlab", check=False)
    assert r.returncode not in (0, 9) and "HTTP 500" in r.stderr


# --------------------------------------------------------------- claim ----

def claim(shims, vendor, body_file, *extra, check=True):
    r = run("claim", "--vendor", vendor, "--owner", "o", "--repo", "r", "--pr", "5",
            "--comment-id", "9", "--body-file", str(body_file), *extra,
            env_extra=env_for(shims), check=check)
    return r.stdout.strip() if check else r


@pytest.fixture
def claim_body(tmp_path):
    f = tmp_path / "claim.md"
    f.write_text("Reviewing on `$(hostname)` — ends `id`")
    return f


def gh_comment(cid, login, at, body):
    return {"id": cid, "user": {"login": login}, "created_at": at, "body": body}


def test_claim_with_no_prior_claim_posts_and_wins(shims, claim_body):
    ours = gh_comment(500, "me", "2026-01-01T00:00:05Z", "x\n\n<!-- bot-claim:9 -->")
    serve(shims, "gh", [
        ("-X POST repos/o/r/issues/5/comments", ours),
        ("api repos/o/r/issues/comments/9", {"user": {"login": "dev"}, "body": "/open-pr @me look",
                                             "html_url": "https://github.com/o/r/pull/5#issuecomment-9"}),
        ("repos/o/r/issues/5/comments?per_page=100", Seq([
            [gh_comment(9, "dev", "2026-01-01T00:00:01Z", "/open-pr"),
             gh_comment(10, "x", "2026-01-01T00:00:02Z", "<!-- bot-claim:95 --> another trigger's lock")],
            [ours]])),
        ("repos/o/r/pulls/5/comments?per_page=100", []),
    ])
    assert claim(shims, "github", claim_body, "--kind", "top") == "claimed 500"
    sent = json.JSONDecoder().raw_decode((shims["tmp"] / "calls.log.bodies").read_text())[0]
    assert sent == {"body": "> /open-pr @me look\n>\n> https://github.com/o/r/pull/5#issuecomment-9\n\n"
                            "Reviewing on `$(hostname)` — ends `id`\n\n<!-- bot-claim:9 -->\n"}, \
        "a GitHub conversation comment has no thread: the request is quoted verbatim, with its URL; " \
        "the body file travels verbatim, the claim marker appended"
    assert "hostname" not in shims["log"].read_text(), "the claim body reached an argv"
    assert "DELETE" not in shims["log"].read_text()


def test_claim_backs_off_when_a_claim_already_exists(shims, claim_body):
    serve(shims, "gh", [
        ("repos/o/r/issues/5/comments?per_page=100", []),
        ("repos/o/r/pulls/5/comments?per_page=100",
         [gh_comment(70, "other", "2026-01-01T00:00:03Z", "on it\n\n<!-- bot-claim:9 -->")]),
    ])
    assert claim(shims, "github", claim_body, "--kind", "line") == "taken other"
    assert "POST" not in shims["log"].read_text(), "a claim already there means nothing is posted"


def test_claim_that_loses_the_race_deletes_its_own_reply(shims, claim_body):
    """Two machines both posted a claim: the earliest wins, the loser deletes its reply."""
    ours = gh_comment(501, "me", "2026-01-01T00:00:05Z", "x\n\n<!-- bot-claim:9 -->")
    theirs = gh_comment(502, "other", "2026-01-01T00:00:04.5Z", "y\n\n<!-- bot-claim:9 -->")
    serve(shims, "gh", [
        ("-X POST repos/o/r/pulls/5/comments/9/replies", ours),
        ("-X DELETE", ""),
        ("repos/o/r/issues/5/comments?per_page=100", []),
        ("repos/o/r/pulls/5/comments?per_page=100", Seq([[], [ours, theirs]])),
    ])
    assert claim(shims, "github", claim_body, "--kind", "line") == "taken other"
    assert "-X DELETE repos/o/r/pulls/comments/501" in shims["log"].read_text()


def test_claim_ties_on_time_go_to_the_lower_id(shims, claim_body):
    at = "2026-01-01T00:00:05Z"
    ours = gh_comment(600, "me", at, "<!-- bot-claim:9 -->")
    serve(shims, "gh", [
        ("-X POST repos/o/r/issues/5/comments", ours),
        ("-X DELETE", ""),
        ("repos/o/r/issues/5/comments?per_page=100",
         Seq([[], [gh_comment(601, "other", at, "<!-- bot-claim:9 -->")]])),
        ("repos/o/r/pulls/5/comments?per_page=100", []),
    ])
    assert claim(shims, "github", claim_body, "--kind", "top") == "claimed 600", \
        "our reply counts even before the listing shows it, and the lower id breaks the tie"


def test_claim_gitlab_posts_into_the_discussion_and_deletes_the_note(shims, claim_body):
    note = lambda nid, user, at: {"id": nid, "author": {"username": user}, "created_at": at,
                                  "body": "z\n\n<!-- bot-claim:9 -->", "system": False}
    ours = note(801, "me", "2026-01-01T09:00:05.000+09:00")
    serve(shims, "glab", [
        ("-X POST -H Content-Type: application/json projects/o%2Fr/merge_requests/5/discussions/abc/notes", ours),
        ("-X POST -H Content-Type: application/json projects/o%2Fr/merge_requests/5/notes", ours),
        ("-X DELETE", ""),
        ("merge_requests/5/discussions?per_page=100",
         Seq([[], [{"id": "abc", "notes": [ours, note(800, "other", "2026-01-01T00:00:04Z")]}]])),
    ])
    assert claim(shims, "gitlab", claim_body, "--kind", "line", "--thread-id", "abc") == "taken other", \
        "created_at compares by instant: +09:00 05s is after Z 04s"
    calls = shims["log"].read_text()
    assert "merge_requests/5/discussions/abc/notes --input" in calls
    assert "-X DELETE projects/o%2Fr/merge_requests/5/notes/801" in calls
    shims["log"].unlink()
    serve(shims, "glab", [
        ("-X POST -H Content-Type: application/json projects/o%2Fr/merge_requests/5/notes", ours),
        ("merge_requests/5/discussions?per_page=100", []),
    ])
    assert claim(shims, "gitlab", claim_body, "--kind", "top") == "claimed 801"
    assert "projects/o%2Fr/merge_requests/5/notes --input" in shims["log"].read_text(), \
        "no thread given: a top-level MR note"


def test_claim_bitbucket_replies_under_the_trigger_and_deletes_by_id(shims, claim_body):
    row = lambda cid, nick, at: {"id": cid, "user": {"nickname": nick}, "created_on": at,
                                 "content": {"raw": "w\n\n[bot-claim:9]: #"}, "deleted": False}
    ours = row(901, "me", "2026-01-01T00:00:05.000001+00:00")
    serve(shims, "curl", [
        ("-X POST", ours),
        ("-X DELETE", ""),
        ("pullrequests/5/comments?pagelen=100", Seq([
            {"values": [], "next": None},
            {"values": [ours, row(900, "other", "2026-01-01T00:00:05+00:00")], "next": None}])),
    ])
    assert claim(shims, "bitbucket", claim_body, "--kind", "top") == "taken other"
    sent = json.loads((shims["tmp"] / "calls.log.bodies").read_text().splitlines()[0])
    assert sent["parent"] == {"id": 9} and sent["content"]["raw"].endswith("\n\n[bot-claim:9]: #\n")
    calls = shims["log"].read_text()
    assert "-X DELETE https://api.bitbucket.org/2.0/repositories/o/r/pullrequests/5/comments/901" in calls


def test_claim_rejects_what_it_cannot_prove(shims, claim_body, tmp_path):
    assert claim(shims, "github", claim_body, check=False).returncode == 1, "--kind is required"
    assert claim(shims, "github", claim_body, "--kind", "x", check=False).returncode == 4
    assert claim(shims, "gitlab", claim_body, "--kind", "top", "--thread-id", "a/../b",
                 check=False).returncode == 4
    empty = tmp_path / "empty.md"
    empty.write_text("")
    assert claim(shims, "github", empty, "--kind", "top", check=False).returncode == 1



def test_claim_github_answers_a_trigger_made_in_a_review_thread_at_its_root(shims, claim_body):
    """GitHub takes no reply to a reply: a trigger posted inside a thread is claimed at the root."""
    ours = {**gh_comment(502, "me", "2026-01-01T00:00:05Z", "x\n\n<!-- bot-claim:9 -->"),
            "pull_request_url": "https://api.github.com/repos/o/r/pulls/5", "in_reply_to_id": 4}
    serve(shims, "gh", [
        ("-X POST repos/o/r/pulls/5/comments/4/replies", ours),
        ("repos/o/r/issues/5/comments?per_page=100", []),
        ("repos/o/r/pulls/5/comments?per_page=100", Seq([[], [ours]])),
    ])
    assert claim(shims, "github", claim_body, "--kind", "line", "--thread-id", "4") == "claimed 502"
    sent = json.JSONDecoder().raw_decode((shims["tmp"] / "calls.log.bodies").read_text())[0]
    assert sent["body"].endswith("<!-- bot-claim:9 -->\n"), "the marker still names the trigger, not the root"


def test_triggers_pick_up_a_request_posted_as_a_thread_reply(shims):
    """A re-review request lands inside the original request's thread; it must still trigger and
    carry what `claim` needs to answer in that thread."""
    serve(shims, "gh", [
        ("pulls?state=open", [{"number": 5, "html_url": "https://github.com/o/r/pull/5"}]),
        ("pulls/comments", [
            {"id": 40, "pull_request_url": "https://api.github.com/repos/o/r/pulls/5", "user": {"login": "dev"},
             "created_at": "2026-01-01T00:00:02Z", "body": "/open-pr re-review",
             "in_reply_to_id": 4}]),
    ])
    assert [(r["comment_id"], r["kind"], r["thread_id"]) for r in triggers(shims, "github")] == [("40", "line", "4")]
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": 9, "web_url": "u"}]),
        ("merge_requests/9/discussions", [{"id": "d1", "notes": [
            {"id": 1, "author": {"username": "dev", "id": 7}, "created_at": "2026-01-01T00:00:01Z", "body": "/open-pr"},
            {"id": 2, "author": {"username": "bot", "id": 1}, "created_at": "2026-01-01T00:00:02Z",
             "body": "on it <!-- bot-claim:1 -->"},
            {"id": 3, "author": {"username": "dev", "id": 7}, "created_at": "2026-01-01T00:00:03Z",
             "body": "/open-pr re-review"}]}]),
        ("members/all/7", {"access_level": 30}),
    ])
    rows = triggers(shims, "gitlab", "--since", "2026-01-01T00:00:01Z")
    assert [(r["comment_id"], r["thread_id"]) for r in rows] == [("3", "d1")]
    serve(shims, "curl", [
        ("pullrequests?state=OPEN", {"values": [{"id": 7, "links": {"html": {"href": "u7"}}}], "next": None}),
        ("pullrequests/7/comments", {"values": [
            {"id": 33, "content": {"raw": "/open-pr re-review"}, "user": {"nickname": "dev"}, "inline": None,
             "parent": {"id": 31}, "created_on": "2026-01-01T00:00:03+00:00", "deleted": False}], "next": None}),
    ])
    assert [(r["comment_id"], r["thread_id"]) for r in triggers(shims, "bitbucket")] == [("33", None)], \
        "Bitbucket replies to any comment: claim's parent is the request itself"


# ---------------------------------------------------------- last-claim ----

def last_claim(shims, vendor):
    r = run("last-claim", "--vendor", vendor, "--owner", "o", "--repo", "r", "--pr", "5",
            env_extra=env_for(shims), check=True)
    return json.loads(r.stdout) if r.stdout.strip() else None


def test_last_claim_github_points_into_the_newest_claims_thread(shims):
    review = lambda cid, at, body, reply_to=None: {
        **gh_comment(cid, "x", at, body), "pull_request_url": "https://api.github.com/repos/o/r/pulls/5",
        "in_reply_to_id": reply_to}
    serve(shims, "gh", [
        ("repos/o/r/issues/5/comments?per_page=100", [
            gh_comment(9, "dev", "2026-01-01T00:00:01Z", "/open-pr"),
            gh_comment(10, "bot", "2026-01-01T00:00:02Z", "> /open-pr\n\non it\n\n<!-- bot-claim:9 -->")]),
        ("repos/o/r/pulls/5/comments?per_page=100", [
            review(20, "2026-01-01T00:00:03Z", "/open-pr this hunk"),
            review(21, "2026-01-01T00:00:04Z", "on it <!-- bot-claim:20 -->", 20),
            review(30, "2026-01-01T00:00:05Z", "/open-pr re-review", 20),
            review(31, "2026-01-01T00:00:06Z", "on it <!-- bot-claim:30 -->", 20)]),
    ])
    assert last_claim(shims, "github") == {"comment_id": "30", "kind": "line", "thread_id": "20"}
    serve(shims, "gh", [
        ("repos/o/r/issues/5/comments?per_page=100", [
            gh_comment(9, "dev", "2026-01-01T00:00:01Z", "/open-pr"),
            gh_comment(10, "bot", "2026-01-01T00:00:02Z", "on it\n\n<!-- bot-claim:9 -->")]),
        ("repos/o/r/pulls/5/comments?per_page=100", []),
    ])
    assert last_claim(shims, "github") == {"comment_id": "9", "kind": "top", "thread_id": None}, \
        "a conversation comment has no thread: the follow-up is top-level"


def test_last_claim_gitlab_and_bitbucket_name_the_trigger_and_its_thread(shims):
    serve(shims, "glab", [("merge_requests/5/discussions?per_page=100", [
        {"id": "d1", "notes": [
            {"id": 11, "author": {"username": "dev"}, "created_at": "2026-01-01T00:00:01Z", "body": "/open-pr"},
            {"id": 12, "author": {"username": "bot"}, "created_at": "2026-01-01T00:00:02Z",
             "body": "on it\n\n<!-- bot-claim:11 -->"}]},
        {"id": "d2", "notes": [{"id": 13, "author": {"username": "dev"}, "created_at": "2026-01-01T00:00:09Z",
                                "body": "unrelated"}]}])])
    assert last_claim(shims, "gitlab") == {"comment_id": "11", "kind": "top", "thread_id": "d1"}
    serve(shims, "curl", [("pullrequests/5/comments?pagelen=100", {"values": [
        {"id": 21, "content": {"raw": "/open-pr"}, "user": {"nickname": "dev"}, "inline": None,
         "created_on": "2026-01-01T00:00:01+00:00", "deleted": False},
        {"id": 22, "content": {"raw": "on it\n\n[bot-claim:21]: #"}, "user": {"nickname": "bot"}, "inline": None,
         "created_on": "2026-01-01T00:00:02+00:00", "deleted": False}], "next": None})])
    assert last_claim(shims, "bitbucket") == {"comment_id": "21", "kind": "top", "thread_id": None}


def test_last_claim_prints_nothing_when_no_claim_exists(shims):
    serve(shims, "gh", [
        ("repos/o/r/issues/5/comments?per_page=100", [gh_comment(9, "dev", "2026-01-01T00:00:01Z", HOSTILE)]),
        ("repos/o/r/pulls/5/comments?per_page=100", []),
    ])
    assert last_claim(shims, "github") is None
    assert "pwned" not in shims["log"].read_text()


# -------------------------------------------------------------- report ----

def report(shims, vendor, body_file, *extra, cid="9"):
    r = run("report", "--vendor", vendor, "--owner", "o", "--repo", "r", "--pr", "5",
            "--comment-id", cid, "--body-file", str(body_file), *extra, env_extra=env_for(shims), check=True)
    return r.stdout.strip()


@pytest.fixture
def report_body(tmp_path):
    f = tmp_path / "report.md"
    f.write_text("Posted the review (commit `$(id)`): 1 🟠 SHOULD FIX — https://github.com/o/r/pull/5#pullrequestreview-77")
    return f


def test_report_github_answers_a_conversation_trigger_once_quoting_it(shims, report_body):
    """The result goes where the claim went, once per request: a report already on the trigger (a
    re-poll, a restart, another machine) posts nothing; its marker is its own, never a claim's."""
    ours = gh_comment(600, "me", "2026-01-01T00:00:09Z", "x")
    claimed = [gh_comment(9, "dev", "2026-01-01T00:00:01Z", "/open-pr"),
               gh_comment(10, "me", "2026-01-01T00:00:02Z", "on it\n\n<!-- bot-claim:9 -->")]
    serve(shims, "gh", [
        ("-X POST repos/o/r/issues/5/comments", ours),
        ("api repos/o/r/issues/comments/9", {"body": "/open-pr", "html_url": "https://github.com/o/r/pull/5#issuecomment-9"}),
        ("repos/o/r/issues/5/comments?per_page=100", claimed),
        ("repos/o/r/pulls/5/comments?per_page=100", []),
    ])
    assert report(shims, "github", report_body, "--kind", "top") == "posted 600"
    sent = json.JSONDecoder().raw_decode((shims["tmp"] / "calls.log.bodies").read_text())[0]["body"]
    assert sent == ("> /open-pr\n>\n> https://github.com/o/r/pull/5#issuecomment-9\n\n"
                    + report_body.read_text() + "\n\n<!-- bot-report:9 -->\n")
    assert "bot-claim" not in sent and "$(id)" not in shims["log"].read_text()
    shims["log"].unlink()
    serve(shims, "gh", [
        ("repos/o/r/issues/5/comments?per_page=100", claimed + [gh_comment(600, "me", "2026-01-01T00:00:09Z", sent)]),
        ("repos/o/r/pulls/5/comments?per_page=100", []),
    ])
    assert report(shims, "github", report_body, "--kind", "top") == "reported 600"
    assert "POST" not in shims["log"].read_text()
    assert last_claim(shims, "github") == {"comment_id": "9", "kind": "top", "thread_id": None}, \
        "a report is no claim"


def test_report_on_a_later_request_gets_its_own_reply_in_its_thread(shims, report_body):
    line = lambda cid, at, body, to=None: {**gh_comment(cid, "x", at, body),
                                          "pull_request_url": "https://api.github.com/repos/o/r/pulls/5", "in_reply_to_id": to}
    serve(shims, "gh", [
        ("-X POST repos/o/r/pulls/5/comments/20/replies", gh_comment(700, "me", "2026-01-01T00:00:09Z", "x")),
        ("repos/o/r/issues/5/comments?per_page=100", []),
        ("repos/o/r/pulls/5/comments?per_page=100", [
            line(20, "2026-01-01T00:00:01Z", "/open-pr"),
            line(21, "2026-01-01T00:00:02Z", "on it <!-- bot-claim:20 -->", 20),
            line(22, "2026-01-01T00:00:03Z", "done <!-- bot-report:20 -->", 20),
            line(30, "2026-01-01T00:00:04Z", "/open-pr re-review", 20),
            line(31, "2026-01-01T00:00:05Z", "on it <!-- bot-claim:30 -->", 20)]),
    ])
    assert report(shims, "github", report_body, "--kind", "line", "--thread-id", "20", cid="30") == "posted 700"
    assert "-X POST repos/o/r/pulls/5/comments/20/replies" in shims["log"].read_text(), \
        "GitHub takes no reply to a reply: the thread's root"


def test_report_gitlab_and_bitbucket_reply_where_the_claim_did(shims, report_body):
    note = {"id": 801, "author": {"username": "me"}, "created_at": "2026-01-01T00:00:05Z", "body": "x", "system": False}
    serve(shims, "glab", [
        ("-X POST -H Content-Type: application/json projects/o%2Fr/merge_requests/5/discussions/abc/notes", note),
        ("merge_requests/5/discussions?per_page=100", []),
    ])
    assert report(shims, "gitlab", report_body, "--kind", "top", "--thread-id", "abc") == "posted 801"
    assert json.loads((shims["tmp"] / "calls.log.bodies").read_text())["body"].endswith("\n\n<!-- bot-report:9 -->\n")
    (shims["tmp"] / "calls.log.bodies").unlink()
    row = {"id": 901, "user": {"nickname": "me"}, "created_on": "2026-01-01T00:00:05+00:00", "content": {"raw": "x"}}
    serve(shims, "curl", [("-X POST", row), ("pullrequests/5/comments?pagelen=100", {"values": [], "next": None})])
    assert report(shims, "bitbucket", report_body, "--kind", "top") == "posted 901"
    sent = json.loads((shims["tmp"] / "calls.log.bodies").read_text().splitlines()[0])
    assert sent["parent"] == {"id": 9} and sent["content"]["raw"].endswith("\n\n[bot-report:9]: #\n")


def test_triggers_drop_a_report_reply(shims):
    """A report answers a request; whatever it opens with, it never becomes one."""
    serve(shims, "curl", [
        ("pullrequests?state=OPEN", {"values": [{"id": 7, "links": {"html": {"href": "u7"}}}], "next": None}),
        ("pullrequests/7/comments", {"values": [
            {"id": 31, "content": {"raw": "/open-pr go"}, "user": {"nickname": "dev"}, "inline": None,
             "created_on": "2026-01-01T00:00:01+00:00", "deleted": False},
            {"id": 34, "content": {"raw": "/open-pr done: LGTM\n\n[bot-report:31]: #"}, "user": {"nickname": "bot"},
             "inline": None, "created_on": "2026-01-01T00:00:04+00:00", "deleted": False}], "next": None})])
    assert [r["comment_id"] for r in triggers(shims, "bitbucket")] == ["31"]


def test_post_verify_names_the_published_reviews_url_on_each_vendor(shims, tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(PAYLOAD))
    pv = lambda vendor, *extra: run("post-verify", "--vendor", vendor, "--owner", "o", "--repo", "r", "--pr", "5", *extra,
                                    env_extra=env_for(shims), check=True).stdout.splitlines()
    serve(shims, "gh", [("repos/o/r/pulls/5/reviews/77", {"id": 77, "state": "COMMENTED",
                                                           "html_url": "https://github.com/o/r/pull/5#pullrequestreview-77"})])
    assert pv("github", "--review-id", "77") == ['{"id":77,"state":"COMMENTED"}', "url=https://github.com/o/r/pull/5#pullrequestreview-77"]
    serve(shims, "gh", [("repos/o/r/pulls/5/reviews/77", {"id": 77, "state": "PENDING", "html_url": "https://x/y"})])
    assert pv("github", "--review-id", "77") == ['{"id":77,"state":"PENDING"}'], "a draft has no review to link"
    serve(shims, "glab", [
        ("merge_requests/5/draft_notes", []),
        ("merge_requests/5/notes?sort=desc", [
            {"id": 12, "body": "a line finding", "position": {"new_line": 2}, "system": False},
            {"id": 11, "body": PAYLOAD["body"] + "\n", "position": None, "system": False},
            {"id": 10, "body": PAYLOAD["body"], "position": None, "system": False}]),
        ("merge_requests/5", {"web_url": "https://gitlab.com/o/r/-/merge_requests/5"}),
    ])
    assert pv("gitlab", "--payload", str(f)) == ["PUBLISHED", "url=https://gitlab.com/o/r/-/merge_requests/5#note_11"]
    serve(shims, "curl", [("pullrequests/5/comments?pagelen=100", {"values": [
        {"id": 41, "content": {"raw": PAYLOAD["body"]}, "inline": None, "deleted": False,
         "links": {"html": {"href": "https://bitbucket.org/o/r/pull-requests/5/_/diff#comment-41"}}},
        {"id": 42, "content": {"raw": "f [bot-finding]: #"}, "inline": {"path": "a.txt", "to": 2}, "deleted": False,
         "links": {"html": {"href": "https://bitbucket.org/o/r/pull-requests/5/_/diff#comment-42"}}}], "next": None})])
    assert pv("bitbucket", "--marker", "[bot-finding]: #", "--payload", str(f)) == [
        '{"id":42,"path":"a.txt","line":2}', "url=https://bitbucket.org/o/r/pull-requests/5/_/diff#comment-41"]


def test_reply_github_line_with_a_thread_answers_its_root(shims, tmp_path):
    f = tmp_path / "b.md"
    f.write_text("/open-pr re-review")
    serve(shims, "gh", [("-X POST repos/o/r/pulls/5/comments/20/replies", {"id": 40})])
    r = run("reply", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5", "--comment-id", "30",
            "--kind", "line", "--thread-id", "20", "--body-file", str(f), env_extra=env_for(shims), check=True)
    assert r.stdout.strip() == "40"


# ------------------------------------------------------- checkout lock ----

@pytest.fixture
def two_pr_repo(fixture_repo):
    """A second PR whose commit only the remote has, so both checkouts really fetch."""
    tmp = fixture_repo["tmp"]
    g = lambda *a: subprocess.run(["git", *a], cwd=tmp / "seed", capture_output=True, text=True, check=True)
    g("checkout", "-b", "other", "main")
    (tmp / "seed" / "b.txt").write_text("b\n")
    g("add", "b.txt")
    g("commit", "-m", "other")
    head6 = g("rev-parse", "HEAD").stdout.strip()
    subprocess.run(["git", "-C", str(tmp / "seed"), "push", "-q", str(tmp / "origin.git"),
                    f"{head6}:refs/pull/6/head"], check=True, capture_output=True)
    return {**fixture_repo, "head6": head6}


def checkout_cmd(repo, pr, head, *extra):
    return ["checkout", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", pr,
            "--repo-dir", str(repo), "--head-sha", head, "--base", "main", *extra]


def test_concurrent_checkouts_of_one_repo_both_succeed(two_pr_repo):
    clone = two_pr_repo["clone"]
    procs = [subprocess.Popen([str(CLI), *checkout_cmd(clone, pr, head)], cwd=two_pr_repo["tmp"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
             for pr, head in (("5", two_pr_repo["head"]), ("6", two_pr_repo["head6"]))]
    outs = [p.communicate(timeout=120) + (p.returncode,) for p in procs]
    for out, errs, code in outs:
        assert code == 0, errs
    heads = sorted(dict(l.split("=", 1) for l in o.splitlines())["head"] for o, _, _ in outs)
    assert heads == sorted([two_pr_repo["head"], two_pr_repo["head6"]])
    assert not (clone / ".git" / "open-pr-checkout.lock").exists(), "the lock outlived its checkout"


def test_checkout_times_out_on_a_held_lock_and_reclaims_a_dead_one(two_pr_repo):
    clone = two_pr_repo["clone"]
    lock = clone / ".git" / "open-pr-checkout.lock"
    lock.mkdir()
    (lock / "pid").write_text(f"{os.getpid()}\n")   # a live holder
    r = run(*checkout_cmd(clone, "5", two_pr_repo["head"], "--lock-timeout", "1"), cwd=two_pr_repo["tmp"])
    assert r.returncode == 1 and "still holds" in r.stderr
    assert lock.exists(), "a waiter must never remove a live holder's lock"
    dead = subprocess.Popen(["true"])
    dead.wait()
    (lock / "pid").write_text(f"{dead.pid}\n")   # its holder is gone
    run(*checkout_cmd(clone, "5", two_pr_repo["head"], "--lock-timeout", "1"),
        cwd=two_pr_repo["tmp"], check=True)
    assert not lock.exists()


# ------------------------------------------------------ watch ----

def test_settings_defaults_the_watch_node(data_dir, tmp_path):
    d = data_dir / "demo"
    d.mkdir(parents=True)
    defaults = {"max_concurrent": 5, "poll_interval_seconds": 180, "trigger": "/open-pr",
                "notify": {"review_started": True, "question": True, "draft_ready": True,
                           "posted": True, "re_review": True, "findings": True, "error": True}}
    (d / "settings.json").write_text(json.dumps({"review": {"bootstrapped": True}}))
    out = json.loads(run("settings", "--repo", "demo", check=True).stdout)
    assert out["watch"] == defaults and out["watch_configured"] is False
    (d / "settings.json").write_text(json.dumps({"watch": {
        "max_concurrent": 2, "notify": {"posted": False}}}))
    part = json.loads(run("settings", "--repo", "demo", check=True).stdout)
    assert part["watch_configured"] is True
    assert part["watch"] == {**defaults, "max_concurrent": 2,
                                    "notify": {**defaults["notify"], "posted": False}}, \
        "stored values win, an explicit false stays false, missing subfields take their default"


def _demo_settings(data_dir, body):
    d = data_dir / "demo"
    d.mkdir(parents=True, exist_ok=True)
    (d / "settings.json").write_text(json.dumps(body))
    return d / "settings.json"


@pytest.mark.parametrize("key, value, path, want", [
    ("review.post_lgtm", "false", ["review", "post_lgtm"], False),
    ("watch.notify.question", "false", ["watch", "notify", "question"], False),
    ("watch.trigger", "@me", ["watch", "trigger"], "@me"),
    ("watch.max_concurrent", "8", ["watch", "max_concurrent"], 8),
    ("watch.poll_interval_seconds", "600", ["watch", "poll_interval_seconds"], 600),
    ("review.doctor_schedule", "2 weeks", ["review", "doctor_schedule"], "2 weeks"),
    ("review.doctor_schedule", "never", ["review", "doctor_schedule"], "never"),
])
def test_settings_set_writes_one_key_with_its_json_type(data_dir, key, value, path, want):
    f = _demo_settings(data_dir, {"schema_version": 1, "review": {"bootstrapped": True, "_comments": {"x": "y"}},
                                  "watch": {"max_concurrent": 2}})
    out = json.loads(run("settings", "--repo", "demo", "--set", key, "--value", value, check=True).stdout)
    stored = json.loads(f.read_text())
    node = stored
    for k in path:
        node = node[k]
    assert node == want, "a number or boolean stored as a string reads back as the wrong type"
    printed = out
    for k in path:
        printed = printed[k]
    assert printed == want, "the write prints the settings as they now read"
    assert stored["schema_version"] == 1 and stored["review"]["_comments"] == {"x": "y"}, \
        "a write touches its own key only"
    if key != "watch.max_concurrent":
        assert stored["watch"]["max_concurrent"] == 2


def test_settings_set_leaves_every_other_key_at_its_read_time_default(data_dir):
    f = _demo_settings(data_dir, {"review": {"bootstrapped": True}})
    out = json.loads(run("settings", "--repo", "demo", "--set", "watch.notify.posted", "--value", "false",
                         check=True).stdout)
    assert json.loads(f.read_text())["watch"] == {"notify": {"posted": False}}, "no default backfilled on disk"
    assert out["watch"]["notify"]["question"] is True and out["watch"]["max_concurrent"] == 5


@pytest.mark.parametrize("key, value", [
    ("review.many_files_threshold", "10"), ("schema_version", "2"), ("review.project_docs_found", "[]"),
    ("watch", "{}"), ("watch.notify.bogus", "true"), ("review.doctored_at", "2026-01-01"),
    ("review.post_lgtm", "yes"), ("review.post_lgtm", "true\nfalse"), ("watch.max_concurrent", "0"),
    ("watch.max_concurrent", "3.5"), ("watch.poll_interval_seconds", "-1"), ("watch.trigger", "x y"),
    ("watch.trigger", "@a;rm"), ("review.doctor_schedule", "2 fortnights"), ("review.doctor_schedule", "0 days"),
])
def test_settings_set_refuses_a_key_or_value_outside_the_allowlist_and_leaves_the_file(data_dir, key, value):
    f = _demo_settings(data_dir, {"review": {"post_lgtm": True}})
    before = f.read_bytes()
    r = run("settings", "--repo", "demo", "--set", key, "--value", value)
    assert r.returncode == 4 and r.stdout == ""
    assert f.read_bytes() == before
    assert [p.name for p in f.parent.iterdir()] == ["settings.json"], "refused after touching the directory"


def test_settings_set_never_creates_a_missing_file_or_rewrites_a_broken_one(data_dir):
    r = run("settings", "--repo", "ghost", "--set", "review.post_lgtm", "--value", "false")
    assert r.returncode == 1 and not (data_dir / "ghost" / "settings.json").exists()
    d = data_dir / "demo"
    d.mkdir(parents=True)
    (d / "settings.json").write_text("[1, 2]")
    assert run("settings", "--repo", "demo", "--set", "review.post_lgtm", "--value", "false").returncode == 1
    assert (d / "settings.json").read_text() == "[1, 2]"
    assert not [p for p in d.iterdir() if ".tmp." in p.name]
    assert run("settings", "--repo", "demo", "--value", "x").returncode == 1, "--value alone writes nothing"


def test_settings_set_renames_into_place_under_the_watchers_state_lock(data_dir):
    f = _demo_settings(data_dir, {"review": {"post_lgtm": True}})
    ino = f.stat().st_ino
    lock = f.parent / "watch" / ".lock"
    lock.mkdir(parents=True)
    holder = subprocess.Popen(["sleep", "30"])
    (lock / "pid").write_text(f"{holder.pid}\n")
    try:
        p = subprocess.Popen([str(CLI), "settings", "--repo", "demo", "--set", "review.post_lgtm", "--value", "false"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1.5)
        assert p.poll() is None and json.loads(f.read_text())["review"]["post_lgtm"] is True, \
            "wrote while the watcher held its state lock"
        holder.kill(); holder.wait()   # a dead holder's lock is reclaimed
        assert p.wait(timeout=20) == 0, p.stderr.read()
    finally:
        if holder.poll() is None:
            holder.kill(); holder.wait()
    assert json.loads(f.read_text())["review"]["post_lgtm"] is False
    assert f.stat().st_ino != ino, "rewritten in place: a concurrent reader can see half a file"
    assert not lock.exists(), "the lock outlives the write"


EVENTS = ("review_started", "question", "draft_ready", "posted", "re_review", "findings", "error")


def test_settings_set_writers_reclaiming_one_dead_lock_never_hold_it_together(data_dir):
    """Every waiter sees the same dead holder; were two to hold the lock at once, one write is lost."""
    f = _demo_settings(data_dir, {"watch": {}})
    lock = f.parent / "watch" / ".lock"
    lock.mkdir(parents=True)
    dead = subprocess.Popen(["true"])
    dead.wait()
    (lock / "pid").write_text(f"{dead.pid}\n")
    procs = [subprocess.Popen([str(CLI), "settings", "--repo", "demo", "--set", f"watch.notify.{e}", "--value", "false"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True) for e in EVENTS]
    assert all(p.wait(timeout=60) == 0 for p in procs)
    assert json.loads(f.read_text())["watch"]["notify"] == {e: False for e in EVENTS}
    assert not list(lock.parent.glob(".lock*")), "a reclaimed lock left a renamed copy behind"


def test_settings_set_reclaims_a_lock_that_never_got_its_pid(data_dir):
    """A holder killed between its mkdir and its pid write leaves an empty lock: taken over after 5 s."""
    f = _demo_settings(data_dir, {"review": {"post_lgtm": True}})
    (f.parent / "watch" / ".lock").mkdir(parents=True)
    start = time.time()
    assert run("settings", "--repo", "demo", "--set", "review.post_lgtm", "--value", "false").returncode == 0
    assert 4 <= time.time() - start < 20
    assert json.loads(f.read_text())["review"]["post_lgtm"] is False


@pytest.mark.parametrize("review, next_at, due", [
    ({"doctored": True, "doctored_at": "2026-01-01T09:00:00+09:00", "doctor_schedule": "2 weeks"},
     "2026-01-15T00:00:00Z", True),
    ({"doctored": True, "doctored_at": "2999-01-01T00:00:00Z", "doctor_schedule": "1 months"},
     "2999-01-31T00:00:00Z", False),
    ({"doctored": True, "doctored_at": "2999-01-01", "doctor_schedule": "7 days"}, "2999-01-08T00:00:00Z", False),
    ({"doctored": True, "doctored_at": "2999-01-01T00:00:00Z", "doctor_schedule": "never"}, None, False),
    ({"doctored": True, "doctored_at": "garbage"}, None, True),
    ({"bootstrapped": True}, None, True),
])
def test_settings_says_when_the_doctor_is_next_due(data_dir, review, next_at, due):
    _demo_settings(data_dir, {"review": review})
    out = json.loads(run("settings", "--repo", "demo", check=True).stdout)
    assert (out["doctor_next_at"], out["doctor_due"]) == (next_at, due), \
        "doctored_at is read in its own zone, not the machine's"
