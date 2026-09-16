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


def test_checkout_gates_and_fetches_the_base_ref(fixture_repo):
    cwd = fixture_repo["tmp"]
    r = run("checkout", "--vendor", "github", "--owner", "o", "--repo", "r", "--pr", "5",
            "--repo-dir", str(fixture_repo["clone"]), "--head-sha", fixture_repo["head"],
            "--base", "main", cwd=cwd, check=True)
    vals = dict(line.split("=", 1) for line in r.stdout.splitlines())
    assert vals["head"] == fixture_repo["head"]
    wt = Path(vals["worktree"])
    assert wt.is_dir() and str(wt).startswith(str(cwd)), \
        "the worktree must root at the invocation directory"
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

def test_settings_applies_read_time_defaults(tmp_path):
    d = tmp_path / "notebooks" / "review" / "demo"
    d.mkdir(parents=True)
    (d / "settings.json").write_text(json.dumps(
        {"review": {"bootstrapped": True, "doctored": True, "doctor_schedule": "never"},
         "shared": {"output_language": "English"}}))
    out = json.loads(run("settings", "--repo", "demo", cwd=tmp_path, check=True).stdout)
    assert out["review"]["many_files_threshold"] == 30
    assert out["fix"]["auto_push"] is False
    # jq's // operator treats an explicit false as absent — a stored false must
    # never flip to the true default, or fix declines without asking
    (d / "settings.json").write_text(json.dumps(
        {"review": {"bootstrapped": True}, "fix": {"decline_needs_confirmation": False}}))
    flip = json.loads(run("settings", "--repo", "demo", cwd=tmp_path, check=True).stdout)
    assert flip["fix"]["decline_needs_confirmation"] is False, "explicit false flipped to true"
    (d / "settings.json").write_text(json.dumps(
        {"review": {"bootstrapped": True, "doctored": True, "doctor_schedule": "never"},
         "shared": {"output_language": "English"}}))
    assert out["doctor_due"] is False, '"never" is never due on a schedule'
    fresh = json.loads(run("settings", "--repo", "ghost", cwd=tmp_path, check=True).stdout)
    assert fresh["doctor_due"] is True, "an unbootstrapped repo is always due"
    # --dir reads the memory directory itself — the fix flow stands INSIDE a review
    # worktree, where a cwd-relative notebooks/review/<repo> resolves into the
    # reviewed tree and read defaults would silently re-trigger fix-bootstrap
    elsewhere = tmp_path / "worktree-standin"
    elsewhere.mkdir()
    byd = json.loads(run("settings", "--dir", str(d), cwd=elsewhere, check=True).stdout)
    assert byd["shared"]["output_language"] == "English", "--dir did not read the real file"


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
