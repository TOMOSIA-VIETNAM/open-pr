"""Unit tests for src/bin/open-pr.sh.

The script is the plugin's deterministic half, so unlike the prompt files it has a real
runtime to exercise. Vendor CLIs are replaced by shims on PATH that log their argv and
answer canned JSON; git runs for real against throwaway fixture repos, because the
worktree/gate/merge-base logic is exactly what must not be faked.

vendor_lint.py covers what shims cannot: that a flag exists on the real gh/glab.
"""

import json
import os
import stat
import subprocess
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


def test_a_config_that_is_not_a_json_object_stops_instead_of_reading_as_unset(tmp_path, monkeypatch):
    """jq 1.6 exits 0 on a parse error, so a broken config would read as "unset" and the
    --set that follows would overwrite whatever the user had in it."""
    conf = tmp_path / "broken-xdg" / "open-pr" / "config.json"
    conf.parent.mkdir(parents=True)
    conf.write_text("{broken")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "broken-xdg"))
    assert run("data-dir").returncode == 1, "a broken config must not read as unset (exit 7)"
    target = tmp_path / "never-created"
    assert run("data-dir", "--set", str(target)).returncode == 1
    assert conf.read_text() == "{broken", "--set overwrote a config it could not read"
    assert not target.exists(), "--set created the directory before checking the config"


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
    """GitHub keeps diff comments and conversation comments in separate id spaces: a
    reaction sent to the wrong one 404s. GitLab reacts on the note inside its MR."""
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

# ------------------------------------------------------------ triggers ----

HOSTILE = "/open-pr focus on $(touch /tmp/pwned) and `id` \"quoted\" 'single'\nsecond line"


def serve(shims, name, routes):
    """A vendor CLI shim answering canned JSON from files, picked by a substring of argv —
    bodies never pass through the shim's own shell text."""
    d = Path(shims["tmp"]) / f"{name}-routes"
    d.mkdir(exist_ok=True)
    cases = []
    for i, (pat, payload) in enumerate(routes):
        f = d / f"{i}.json"
        if isinstance(payload, tuple):   # (exit code, stderr)
            cases.append(f'  *"{pat}"*) printf "%s\\n" "{payload[1]}" >&2; exit {payload[0]} ;;')
        else:   # a str is raw text: what the real CLI prints after its own --jq
            f.write_text(payload if isinstance(payload, str) else json.dumps(payload))
            cases.append(f'  *"{pat}"*) cat "{f}" ;;')
    make_shim(Path(shims["path"]), name, f'''printf '%s\\n' "{name} $*" >> "{shims['log']}"
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
    ("pulls?state=open", [{"number": 5, "html_url": "https://github.com/o/r/pull/5"}]),
    ("issues/comments", [
        {"id": 1, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:03Z", "body": HOSTILE, "author_association": "MEMBER"},
        {"id": 2, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:04Z", "body": "please /open-pr later", "author_association": "MEMBER"},
        {"id": 3, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "bot"},
         "created_at": "2026-01-01T00:00:05Z", "body": "/open-pr from myself", "author_association": "OWNER"},
        {"id": 4, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "alt"},
         "created_at": "2026-01-01T00:00:06Z", "body": "/open-pr quoted <!-- bot-finding -->",
         "author_association": "MEMBER"},
        {"id": 5, "issue_url": "https://api.github.com/repos/o/r/issues/8", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:07Z", "body": "/open-pr on a closed PR or an issue",
         "author_association": "MEMBER"},
        {"id": 6, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "stranger"},
         "created_at": "2026-01-01T00:00:01Z", "body": "  /open-pr", "author_association": "NONE"},
        {"id": 7, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:08Z", "body": "/open-prx not the trigger", "author_association": "MEMBER"},
        {"id": 8, "issue_url": "https://api.github.com/repos/o/r/issues/5", "user": {"login": "dev"},
         "created_at": "2026-01-01T00:00:09Z", "body": "/open-pr:review is the plugin command, run it locally",
         "author_association": "MEMBER"},
    ]),
    ("pulls/comments", [
        {"id": 90, "pull_request_url": "https://api.github.com/repos/o/r/pulls/5", "user": {"login": "col"},
         "created_at": "2026-01-01T00:00:02Z", "body": "/open-pr this hunk", "author_association": "COLLABORATOR"},
    ]),
    ("api user", "bot\n"),
]


def test_triggers_github_emits_only_real_triggers_oldest_first(shims):
    serve(shims, "gh", GH_ROUTES)
    rows = triggers(shims, "github")
    assert [r["comment_id"] for r in rows] == ["6", "90", "1"], \
        "mid-body mentions, own comments, marked comments, non-open PRs, /open-prx and /open-pr:… never trigger"
    assert rows[0]["authorized"] == "no", "author_association NONE has no write access"
    assert rows[1] == {"pr": 5, "url": "https://github.com/o/r/pull/5", "comment_id": "90", "kind": "line",
                       "user": "col", "created_at": "2026-01-01T00:00:02Z", "body": "/open-pr this hunk",
                       "authorized": "yes"}
    assert rows[2]["kind"] == "top" and rows[2]["authorized"] == "yes"
    assert rows[2]["body"] == HOSTILE, "an attacker-controlled body must come out byte-for-byte"
    assert not Path("/tmp/pwned").exists()
    assert "pwned" not in shims["log"].read_text(), "a comment body reached an argv"


def test_triggers_since_is_strict_and_narrows_the_fetch(shims):
    serve(shims, "gh", GH_ROUTES)
    rows = triggers(shims, "github", "--since", "2026-01-01T00:00:02Z")
    assert [r["comment_id"] for r in rows] == ["1"], "a comment AT the cursor was already handled"
    assert "since=2026-01-01T00:00:02Z" in shims["log"].read_text()
    # an offset form of the same instant compares by time, not by string
    rows = triggers(shims, "github", "--since", "2026-01-01T09:00:02.5+09:00")
    assert [r["comment_id"] for r in rows] == ["1"]
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
        ("merge_requests/9/notes", notes),
        ("members/all/7", {"access_level": 30}),
        ("members/all/8", {"access_level": 20}),
        ("members/all/9", (1, "glab: 404 Not Found (HTTP 404)")),
        ("user", {"username": "bot"}),
    ])
    rows = triggers(shims, "gitlab")
    got = {r["comment_id"]: (r["kind"], r["authorized"]) for r in rows}
    assert got == {"11": ("top", "yes"), "12": ("line", "yes"), "13": ("top", "no"), "14": ("top", "no")}, \
        "Developer+ is yes; Reporter and non-members are no; system notes and own notes never trigger"
    assert [r for r in rows if r["comment_id"] == "12"][0]["body"] == HOSTILE
    calls = shims["log"].read_text()
    assert calls.count("members/all/7") == 1, "one membership call per distinct author"
    assert "pwned" not in calls


def test_triggers_gitlab_stops_when_membership_cannot_be_read(shims):
    serve(shims, "glab", [
        ("merge_requests?state=opened", [{"iid": 9, "web_url": "u"}]),
        ("merge_requests/9/notes", [{"id": 1, "author": {"username": "dev", "id": 7},
                                     "created_at": "2026-01-01T00:00:01Z", "body": "/open-pr"}]),
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


# ------------------------------------------------------- checkout lock ----

@pytest.fixture
def two_pr_repo(fixture_repo):
    """fixture_repo plus a second PR whose commit only the remote has, so both checkouts
    really fetch into the shared .git."""
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


# ------------------------------------------------------ watch_review ----

def test_settings_defaults_the_watch_review_node(data_dir, tmp_path):
    d = data_dir / "demo"
    d.mkdir(parents=True)
    defaults = {"max_concurrent": 5, "poll_interval_seconds": 60, "snooze_until": None,
                "notify": {"review_started": True, "question": True, "draft_ready": True,
                           "posted": True, "re_review": True}}
    (d / "settings.json").write_text(json.dumps({"review": {"bootstrapped": True}}))
    out = json.loads(run("settings", "--repo", "demo", check=True).stdout)
    assert out["watch_review"] == defaults and out["watch_review_configured"] is False
    (d / "settings.json").write_text(json.dumps({"watch_review": {
        "max_concurrent": 2, "notify": {"posted": False}, "snooze_until": "2026-02-01T00:00:00Z"}}))
    part = json.loads(run("settings", "--repo", "demo", check=True).stdout)
    assert part["watch_review_configured"] is True
    assert part["watch_review"] == {**defaults, "max_concurrent": 2, "snooze_until": "2026-02-01T00:00:00Z",
                                    "notify": {**defaults["notify"], "posted": False}}, \
        "stored values win, an explicit false stays false, missing subfields take their default"
