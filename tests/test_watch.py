"""Unit tests for src/bin/open-pr-watch.sh.

The script is copied into a temp bin/ beside a fake open-pr.sh (it resolves the sibling by its
own dirname); each platform CLI is a PATH shim recording argv and cwd. The fake `claude` starts
a copy under a new id when resuming a still-listed session or with an extra flag, as the real one.
"""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WATCH = REPO / "src" / "bin" / "open-pr-watch.sh"

FAKE_OPEN_PR = r"""#!/bin/sh
printf '%s\n' "$*" >> "$FAKE_HOME/open-pr.calls"
case "$1" in
    data-dir) if [ "${2:-}" = --all ]; then printf '%s\n' "$FAKE_HOME/data" "$FAKE_HOME/data2" ${FAKE_DATA3:+"$FAKE_DATA3"}
              else printf '%s\n' "$FAKE_HOME/data"; fi ;;
    repo-target) printf '%s\n' "$*" >> "$FAKE_HOME/repo-target.args"
                 printf 'vendor=github\nowner=o\nrepo=r\nhost=github.com\n' ;;
    triggers) printf '%s\n' "$*" >> "$FAKE_HOME/triggers.args"
              # quota.json: what --quota-file gets, a rate-limited poll included
              qf=$(printf '%s\n' "$@" | sed -n '/^--quota-file$/{n;p;}')
              [ -z "$qf" ] || [ ! -f "$FAKE_HOME/quota.json" ] || cp "$FAKE_HOME/quota.json" "$qf"
              # triggers.rc: one outcome per call, consumed in order — 9 = rate limited, 1 = no
              # network, quiet = nothing
              if [ -s "$FAKE_HOME/triggers.rc" ]; then
                  rc=$(head -n 1 "$FAKE_HOME/triggers.rc")
                  sed 1d "$FAKE_HOME/triggers.rc" > "$FAKE_HOME/triggers.rc.n"; mv "$FAKE_HOME/triggers.rc.n" "$FAKE_HOME/triggers.rc"
                  case "$rc" in
                      9) printf 'rate limited\n' >&2; exit 9 ;;
                      1) printf 'error connecting to api.github.com\n' >&2; exit 1 ;;
                      quiet) exit 0 ;;
                  esac
              fi
              mf=$(printf '%s\n' "$@" | sed -n '/^--mark-file$/{n;p;}')
              [ -z "$mf" ] || cat "$FAKE_HOME/mark.txt" > "$mf" 2>/dev/null || : > "$mf"
              ff=$(printf '%s\n' "$@" | sed -n '/^--findings-file$/{n;p;}')
              [ -z "$ff" ] || cat "$FAKE_HOME/findings.jsonl" > "$ff" 2>/dev/null || : > "$ff"
              # --backlog: backlog.jsonl, what `triggers --backlog` prints
              case " $* " in *" --backlog "*) cat "$FAKE_HOME/backlog.jsonl" 2>/dev/null || true ;;
                  *) cat "$FAKE_HOME/triggers.jsonl" 2>/dev/null || true ;; esac ;;
    # open.txt: the open PR numbers; absent = the call fails (open.rc: its exit code, default 1)
    open-prs) [ -f "$FAKE_HOME/open.txt" ] || { printf 'open-prs down\n' >&2; exit "$(cat "$FAKE_HOME/open.rc" 2>/dev/null || echo 1)"; }
              cat "$FAKE_HOME/open.txt" ;;
    settings) cat "$FAKE_HOME/settings.json" 2>/dev/null || printf '{}\n' ;;
    account) cat "$FAKE_HOME/account.txt" 2>/dev/null || printf 'UNKNOWN\n' ;;
    *) exit 1 ;;
esac
"""

# Headless CLI recorder: argv + cwd to <name>.<n>.json, canned output, optional sleep to hold the pid.
RECORDER = r"""#!/usr/bin/env python3
import json, os, sys, time
name = os.path.basename(sys.argv[0])
home = os.environ["FAKE_HOME"]
n = len([f for f in os.listdir(home) if f.startswith(name + ".") and f.endswith(".json")])
dest = os.path.join(home, f"{name}.{n}.json")
with open(dest + ".tmp", "w") as fh:          # atomic: a test polling for dest never reads it half-written
    json.dump({"argv": sys.argv[1:], "cwd": os.getcwd()}, fh)
os.replace(dest + ".tmp", dest)
if name == "agent" and sys.argv[1:] == ["create-chat"]:
    print("chat-abc")
    sys.exit(0)
out = os.path.join(home, f"{name}.out")
if os.path.exists(out):
    sys.stdout.write(open(out).read())
    sys.stdout.flush()
# on screen, as the real ones say so (FAKE_NO_UI: never, as one that crashes or hangs first):
# the toast creates its last argv, the menu bar writes its pid to its pid file
a = sys.argv[1:]
if name == "osascript" and len(a) > 4 and not os.environ.get("FAKE_NO_UI"):
    time.sleep(float(os.environ.get("FAKE_UI_DELAY", "0")))
    if a[2].endswith("open-pr-toast.js") and a[-1].endswith("/shown"):
        open(a[-1], "w").close()
    elif a[2].endswith("open-pr-menubar.js"):
        with open(a[4] + ".tmp", "w") as fh:
            fh.write(f"{os.getpid()}\n")
        os.replace(a[4] + ".tmp", a[4])
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""

FAKE_CLAUDE = r"""#!/usr/bin/env python3
import json, os, sys
home = os.environ["FAKE_HOME"]
db_path = os.path.join(home, "claude.db.json")
db = json.load(open(db_path)) if os.path.exists(db_path) else {"sessions": [], "n": 0}
a = sys.argv[1:]
with open(os.path.join(home, "claude.calls"), "a") as fh:
    fh.write(json.dumps({"argv": a, "cwd": os.getcwd()}) + "\n")
ACTIVE = ("working", "blocked", "done")
if a[:1] == ["--bg"] and os.environ.get("FAKE_CLAUDE_UNTRUSTED"):
    print("Workspace not trusted. Run `claude` in %s once and accept the trust prompt, then retry." % os.getcwd())
    sys.exit(1)

def save():
    json.dump(db, open(db_path, "w"))

def new(name):
    db["n"] += 1
    sid = "%08x" % (0xabc000 + db["n"])
    s = {"id": sid, "sessionId": sid + "-0000-4000-8000-000000000000", "name": name,
         "state": os.environ.get("FAKE_CLAUDE_STATE", "working"), "cwd": os.getcwd()}
    db["sessions"].append(s)
    return s

if a == ["agents", "--json"] and "FAKE_CLAUDE_LIST" in os.environ:
    sys.stdout.write(os.environ["FAKE_CLAUDE_LIST"])
elif a[:2] == ["agents", "--json"]:
    for s in db["sessions"]:   # FAKE_CLAUDE_LINGER: listed for that many more listings after `stop`
        if s.get("linger"):
            s["linger"] -= 1
            if not s["linger"]:
                s["state"] = "stopped"
    rows = db["sessions"] if "--all" in a else [s for s in db["sessions"] if s["state"] in ACTIVE]
    print(json.dumps(rows))
elif a[:1] == ["stop"]:
    for s in db["sessions"]:
        if s["id"] == a[1]:
            s["linger"] = int(os.environ.get("FAKE_CLAUDE_LINGER", "0"))
            if not s["linger"]:
                s["state"] = "stopped"
elif a[:1] == ["--bg"] and "--resume" in a:
    sid = a[a.index("--resume") + 1]
    s = next(s for s in db["sessions"] if s["sessionId"] == sid)
    if len(a) != 4 or s["state"] in ACTIVE or os.environ.get("FAKE_CLAUDE_COPY"):
        c = new(None)
        print("started a copy of the session")
        print("backgrounded · %s · (no name)" % c["id"])
    else:
        s["state"] = "working"
        print("\x1b[2mbackgrounded · %s · %s\x1b[0m" % (s["id"], s["name"]))
elif a[:2] == ["--bg", "-n"]:
    s = new(a[2])
    print("backgrounded · %s · %s" % (s["id"], s["name"]))
else:
    sys.exit(2)
save()
"""

HEADLESS = ("codex", "gemini", "agent", "agy", "osascript", "notify-send")


def make_exe(path, body):
    # not `env python3`: a version-manager shim costs ~200ms per call
    path.write_text(body.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def w(tmp_path):
    """A watch sandbox: bin/ with the script + fake open-pr.sh, fakes/ on PATH, a repo dir."""
    return Watch(tmp_path)


class Watch:
    def __init__(self, tmp):
        self.home = tmp / "home"
        self.home.mkdir()
        self.bin = tmp / "bin"
        self.bin.mkdir()
        shutil.copy(WATCH, self.bin / "open-pr-watch.sh")
        make_exe(self.bin / "open-pr.sh", FAKE_OPEN_PR)
        self.fakes = tmp / "fakes"
        self.fakes.mkdir()
        make_exe(self.fakes / "claude", FAKE_CLAUDE)
        for name in HEADLESS:
            make_exe(self.fakes / name, RECORDER)
        self.repo = tmp / "repo"
        self.repo.mkdir()
        self.sd = self.home / "data" / "r" / "watch"
        self.watch = tmp / "xdg" / "open-pr" / "watch"
        self.env = dict(os.environ, FAKE_HOME=str(self.home), XDG_CONFIG_HOME=str(tmp / "xdg"),
                        PATH=f"{self.fakes}{os.pathsep}{os.environ['PATH']}")
        self.children = []

    def run(self, *args, env_extra=None, path=None, check=True, cwd=None):
        env = dict(self.env, **(env_extra or {}))
        if path is not None:
            env["PATH"] = path
        r = subprocess.run(["sh", str(self.bin / "open-pr-watch.sh"), *args], capture_output=True,
                           text=True, cwd=cwd or self.repo, env=env, timeout=90)
        if check and r.returncode != 0:
            raise AssertionError(f"open-pr-watch.sh {' '.join(args)} exit {r.returncode}:\n{r.stderr}")
        return r

    def jsonl(self, *args, **kw):
        return [json.loads(line) for line in self.run(*args, **kw).stdout.splitlines() if line.strip()]

    def settings(self, **watch):
        (self.home / "settings.json").write_text(json.dumps({"watch": watch}))

    def triggers(self, *rows):
        (self.home / "triggers.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    def state(self):
        return json.loads((self.sd / "state.json").read_text())

    def put_state(self, st):
        self.sd.mkdir(parents=True, exist_ok=True)
        (self.sd / "state.json").write_text(json.dumps(st))

    def prompt(self, text, name="p.txt"):
        p = self.home / name
        p.write_text(text)
        return str(p)

    def spawn(self, pr, runner="claude", text="review it", extra=(), **kw):
        return self.jsonl("spawn", "--runner", runner, "--pr", str(pr), "--name",
                          f"review o/r#{pr}", "--prompt-file", self.prompt(text, f"p{pr}.txt"),
                          *extra, **kw)[0]

    def claude_db(self):
        return json.loads((self.home / "claude.db.json").read_text())

    def claude_set(self, cid, state, status=None):
        """status: the `claude agents` turn status (idle | busy); None leaves it out."""
        db = self.claude_db()
        for s in db["sessions"]:
            if s["id"] == cid:
                s["state"] = state
                s.pop("status", None)
                if status:
                    s["status"] = status
        (self.home / "claude.db.json").write_text(json.dumps(db))

    def claude_calls(self, with_cwd=False):
        rows = [json.loads(l) for l in (self.home / "claude.calls").read_text().splitlines()]
        return rows if with_cwd else [r["argv"] for r in rows]

    def recorded(self, name, n=0, timeout=10):
        f = self.home / f"{name}.{n}.json"
        end = time.time() + timeout
        while not f.exists() and time.time() < end:
            time.sleep(0.05)
        assert f.exists(), f"{name} was never invoked"
        return json.loads(f.read_text())

    def status_file(self, pr, **body):
        self.sd.mkdir(parents=True, exist_ok=True)
        (self.sd / f"pr-{pr}.status.json").write_text(json.dumps(body))

    def wait_dead(self, pid, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
            time.sleep(0.05)
        raise AssertionError(f"pid {pid} still alive")


def trig(cid, at, pr=1, body="/open-pr look at auth"):
    return {"pr": pr, "url": f"https://github.com/o/r/pull/{pr}", "comment_id": cid, "user": "dev",
            "created_at": at, "body": body, "authorized": "yes"}


# ------------------------------------------------------------------ help ----

def test_help_prints_every_subcommand(w):
    r = w.run("--help")
    assert r.stdout.startswith("usage: open-pr-watch.sh")
    for sub in ("wait", "spawn", "here", "status", "next", "forget", "hide", "paths", "notify", "trust", "snooze", "menubar"):
        assert f"\n  {sub}" in r.stdout


def test_unknown_runner_lists_the_valid_ones(w):
    r = w.run("spawn", "--runner", "vim", "--pr", "1", "--name", "x",
              "--prompt-file", w.prompt("x"), check=False)
    assert r.returncode == 1
    assert "claude codex gemini cursor antigravity" in r.stderr


def test_paths_names_the_files_a_review_session_writes(w):
    out = dict(l.split("=", 1) for l in w.run("paths", "--pr", "7").stdout.splitlines())
    assert out["dir"] == str(w.sd)
    assert out["status_file"] == str(w.sd / "pr-7.status.json")
    assert out["prompts"] == str(w.sd / "prompts")



def test_watch_state_is_kept_out_of_the_memory_repo(w):
    """State and prompt files quote PR comments; the review-memory repo commits `<repo>/` whole."""
    w.run("paths", "--pr", "7")
    w.run("paths", "--pr", "8")
    gi = (w.sd.parent.parent / ".gitignore").read_text().splitlines()
    assert gi.count("watch/") == 1


def test_every_data_dir_and_settings_call_names_the_watched_repo(w):
    """Started above two workspaces, each repo resolves its own data dir, never the cwd's."""
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    w.run("wait", "--once")
    w.run("notify", "--event", "posted", "--text-file", w.prompt("x"))
    calls = [l for l in (w.home / "open-pr.calls").read_text().splitlines()
             if l.split(" ", 1)[0] in ("data-dir", "settings")]
    assert {l.split(" ", 1)[0] for l in calls} == {"data-dir", "settings"}
    for c in calls:
        assert c.endswith(f"--repo-dir {w.repo.resolve()}"), c


def test_remote_reaches_repo_target(w):
    """A clone with a remote per vendor is watched through the remote the user chose, not origin."""
    w.run("paths", "--pr", "7", "--remote", "github")
    w.run("paths", "--pr", "7")
    args = (w.home / "repo-target.args").read_text().splitlines()
    assert args[0].endswith("--remote github") and "--remote" not in args[1]

# ---------------------------------------------------------------- wait ----

def last_triggers_call(w):
    return (w.home / "triggers.args").read_text().splitlines()[-1]


@pytest.mark.parametrize("stored,account,want", [
    (None, None, "--token /open-pr"),
    ("/review", None, "--token /review"),
    ("@me", "Alice", "--token @Alice"),
])
def test_wait_passes_the_repos_trigger_token(w, stored, account, want):
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    if stored:
        w.settings(trigger=stored)
    if account:
        (w.home / "account.txt").write_text(account + "\n")
    w.run("wait", "--once")
    call = last_triggers_call(w)
    assert f" {want} " in call + " " and "--mark-file" in call
    if stored == "@me":
        acc = [l for l in (w.home / "open-pr.calls").read_text().splitlines() if l.startswith("account")]
        assert acc == ["account --vendor github --owner o --repo r --host github.com"]


def test_a_mention_of_me_needs_a_readable_account(w):
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    w.settings(trigger="@me")
    r = w.run("wait", "--once", check=False)
    assert r.returncode == 1 and "@me" in r.stderr and "cannot be read" in r.stderr
    assert not (w.home / "triggers.args").exists(), "no poll runs on a trigger nobody can type"


def test_first_wait_starts_the_cursor_at_now_without_replaying_history(w):
    w.triggers(trig("1", "2020-01-01T00:00:00Z"))
    assert w.run("wait", "--once").stdout == ""
    st = w.state()
    assert st["cursor"] > "2020-01-01T00:00:00Z" and st["seen"] == []
    assert w.run("wait", "--once").stdout == "", "a comment older than the first run was replayed"


def test_a_new_trigger_is_emitted_once_across_polls(w):
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    w.triggers(trig("11", "2026-01-01T00:00:05Z"))
    ev = w.jsonl("wait", "--once")
    assert ev == [{"event": "trigger", "repo": "o/r", **trig("11", "2026-01-01T00:00:05Z")}]
    assert w.run("wait", "--once").stdout == ""
    since = [l for l in (w.home / "open-pr.calls").read_text().splitlines() if l.startswith("triggers")][-1]
    assert "--since 2026-01-01T00:00:04Z" in since, "--since is strict: a comment in the cursor's second is lost"


def test_a_wait_killed_before_its_state_write_emits_the_batch_again(w):
    """Killed between print and state rename (old state.json restored), the next wait reprints."""
    before = {"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []}
    w.put_state(before)
    w.triggers(trig("21", "2026-01-01T00:01:00Z"))
    first = w.jsonl("wait", "--once")
    w.put_state(before)
    assert w.jsonl("wait", "--once") == first
    assert w.run("wait", "--once").stdout == ""


def test_comments_sharing_one_created_at_are_each_emitted_once(w):
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    at = "2026-01-01T00:02:00Z"
    w.triggers(trig("31", at))
    assert [e["comment_id"] for e in w.jsonl("wait", "--once")] == ["31"]
    # a second comment lands in the same second, and GitLab-style fractions appear
    w.triggers(trig("31", at), trig("32", "2026-01-01T00:02:00.500Z"), trig("32", at))
    assert [e["comment_id"] for e in w.jsonl("wait", "--once")] == ["32"]
    assert w.state()["seen"] == ["31", "32"]
    assert w.run("wait", "--once").stdout == ""


def test_a_created_at_with_a_utc_offset_moves_the_cursor_in_utc(w):
    """Self-hosted GitLab prints +09:00; kept verbatim it breaks --since and string compares."""
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    w.triggers(trig("41", "2026-01-01T09:00:05.557+09:00"))
    assert [e["comment_id"] for e in w.jsonl("wait", "--once")] == ["41"]
    assert w.state()["cursor"] == "2026-01-01T00:00:05Z"
    r = w.run("wait", "--once", check=False)
    assert r.returncode == 0 and r.stdout == "", r.stderr
    assert "--since 2026-01-01T00:00:04Z" in (w.home / "triggers.args").read_text().splitlines()[-1]


def test_a_cursor_stored_with_an_offset_is_read_back_in_utc(w):
    """State written before the cursor was kept in UTC must not stop every later wait."""
    w.put_state({"cursor": "2026-01-01T09:00:05+09:00", "seen": ["41"], "sessions": {}, "queue": []})
    w.triggers(trig("41", "2026-01-01T09:00:05+09:00"), trig("42", "2026-01-01T00:00:06Z"))
    r = w.run("wait", "--once", check=False)
    assert r.returncode == 0, r.stderr
    assert [json.loads(l)["comment_id"] for l in r.stdout.splitlines()] == ["42"]


def test_wait_reports_a_session_state_change_once(w):
    sp = w.spawn(5)
    assert w.run("wait", "--once").stdout == "", "a fresh session is already known to be working"
    w.claude_set(sp["id"], "done")
    w.status_file(5, state="posted", url="https://github.com/o/r/pull/5")
    ev = w.jsonl("wait", "--once")
    assert ev == [{"event": "session", "repo": "o/r", "pr": 5, "role": "review", "state": "posted", "open": f"claude attach {sp['id']}"}]
    assert w.run("wait", "--once").stdout == ""



def test_each_result_answers_the_request_its_session_was_spawned_for(w):
    """Two requests on one PR: the newest claim is the second's, yet the first session's result
    answers the first; the session resumed for the second answers the second. A resume for no new
    request (a draft the user approved) keeps answering the one it served."""
    first, second = ("--comment-id", "41", "--kind", "top"), ("--comment-id", "42", "--kind", "line", "--thread-id", "40")
    sp = w.spawn(5, extra=first)
    w.run("wait", "--once")   # a role set's first run only starts its cursor
    assert w.spawn(5, extra=second)["queued"] is True, "the first review still runs"
    w.claude_set(sp["id"], "done")
    w.status_file(5, state="posted")
    ev = w.jsonl("wait", "--once")
    assert [e.get("request") for e in ev if e["event"] == "session"] == [{"comment_id": "41", "kind": "top", "thread_id": None}]
    nxt = w.jsonl("next")[0]
    assert (nxt["comment_id"], nxt["kind"], nxt["thread_id"]) == ("42", "line", "40"), "the queue keeps the request"
    w.spawn(5, extra=("--comment-id", nxt["comment_id"], "--kind", nxt["kind"], "--thread-id", nxt["thread_id"]))
    want = {"comment_id": "42", "kind": "line", "thread_id": "40"}
    assert w.state()["sessions"]["5:review"]["request"] == want
    w.claude_set(sp["id"], "done")
    w.status_file(5, state="draft")
    assert [e.get("request") for e in w.jsonl("wait", "--once") if e["event"] == "session"] == [want]
    w.spawn(5, text="the user approved publishing")
    assert w.state()["sessions"]["5:review"]["request"] == want
    assert w.jsonl("status", "--pr", "5")[0]["request"] == want


def test_a_session_recorded_without_a_request_reports_none(w):
    """A record from before spawn took the request: no `request`, so the watcher falls back to last-claim."""
    sp = w.spawn(6)
    w.run("wait", "--once")
    assert "request" not in w.state()["sessions"]["6:review"]
    w.claude_set(sp["id"], "done")
    w.status_file(6, state="posted")
    assert [e for e in w.jsonl("wait", "--once") if e["event"] == "session"][0].keys() == \
        {"event", "repo", "pr", "role", "state", "open"}


@pytest.mark.parametrize("bad", [("--comment-id", "9;id", "--kind", "top"), ("--comment-id", "9", "--kind", "both"),
                                 ("--comment-id", "9", "--kind", "line", "--thread-id", "a/../b"),
                                 ("--kind", "top"), ("--comment-id", "9")])
def test_spawn_refuses_a_malformed_request(w, bad):
    r = w.run("spawn", "--runner", "claude", "--pr", "7", "--name", "review o/r#7", "--prompt-file", w.prompt("x"),
              *bad, check=False)
    assert r.returncode == 4 and "invalid value" in r.stderr
    assert not (w.sd / "state.json").exists() or "7:review" not in w.state().get("sessions", {})


def test_a_running_wait_sees_a_session_change_between_its_own_polls(w):
    """A session listing cached across polls would report `working` forever."""
    w.settings(poll_interval_seconds=1)
    sp = w.spawn(5)
    assert w.run("wait", "--once").stdout == ""
    proc = subprocess.Popen(["sh", str(w.bin / "open-pr-watch.sh"), "wait"], cwd=w.repo, env=w.env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        time.sleep(2.5)                      # at least one poll with the session still working
        assert proc.poll() is None, "wait exited before anything changed"
        w.claude_set(sp["id"], "done")
        w.status_file(5, state="posted", url="https://github.com/o/r/pull/5")
        out, _ = proc.communicate(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert [json.loads(l)["state"] for l in out.splitlines() if l.strip()] == ["posted"]


def test_a_quiet_repo_moves_the_cursor_to_the_newest_comment_fetched(w):
    """Else every poll re-fetches every comment since the watcher started."""
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    (w.home / "mark.txt").write_text("2026-01-02T08:00:00Z\n")
    assert w.run("wait", "--once").stdout == ""
    assert w.state()["cursor"] == "2026-01-02T08:00:00Z"
    w.run("wait", "--once")
    assert "--since 2026-01-02T07:59:59Z" in (w.home / "triggers.args").read_text().splitlines()[-1]
    (w.home / "mark.txt").write_text("")
    w.run("wait", "--once")
    assert w.state()["cursor"] == "2026-01-02T08:00:00Z", "nothing fetched leaves the cursor alone"
    w.triggers(trig("21", "2026-01-02T08:00:00Z"))
    (w.home / "mark.txt").write_text("2026-01-02T08:00:00Z\n")
    assert [e["comment_id"] for e in w.jsonl("wait", "--once")] == ["21"], \
        "a trigger in the mark's own second still arrives once"
    assert w.run("wait", "--once").stdout == ""


def _long_wait(w, *roles):
    """A `wait` left running; roles = its `--roles` value, when given."""
    args = ("--roles", roles[0]) if roles else ()
    w.settings(poll_interval_seconds=30)
    w.run("wait", "--once", *args)                            # cursor set: nothing to deliver
    proc = subprocess.Popen(["sh", str(w.bin / "open-pr-watch.sh"), "wait", *args], cwd=w.repo, env=w.env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    w.children.append(proc)
    for _ in range(50):                  # exec keeps the pid: the copy has taken over when it writes it
        pf = w.sd / ("wait-fix.pid" if roles == ("fix",) else "wait-review.pid")
        if pf.exists() and pf.read_text().strip() == str(proc.pid):
            break
        time.sleep(0.1)
    return proc


def test_the_menu_bars_stop_file_ends_wait_with_exit_11(w):
    """Stop watcher writes it; a killed wait would read as a failure and be restarted."""
    proc = _long_wait(w)
    (w.sd / "stop").write_text("")
    out, err = proc.communicate(timeout=20)
    assert proc.returncode == 11 and "stopped from the menu bar" in err
    assert out == "", "no events"
    assert not (w.sd / "stop").exists(), "consumed"
    assert not (w.sd / "heartbeat").exists() and not (w.sd / "watcher.json").exists(), \
        "off the menu bar at once, not after the heartbeat goes stale"


def test_a_stale_stop_file_does_not_stop_a_new_wait(w):
    w.run("wait", "--once")
    (w.sd / "stop").write_text("")
    assert w.run("wait", "--once", check=False).returncode == 0
    assert not (w.sd / "stop").exists()


def test_a_second_wait_on_the_same_repo_is_refused(w):
    """Two waits would share state.json and split the triggers between them."""
    proc = _long_wait(w)
    try:
        r = w.run("wait", "--once", check=False)
        assert r.returncode == 10 and f"already watched for review on this machine (wait pid {proc.pid})" in r.stderr
    finally:
        proc.kill(); proc.wait()
    assert w.run("wait", "--once", check=False).returncode == 0, "a dead holder frees the repo"


def test_a_running_wait_survives_an_edit_of_its_script(w):
    """sh reads a script as it runs; an update under a long wait must not break it."""
    proc = _long_wait(w)
    try:
        script = w.bin / "open-pr-watch.sh"
        script.write_text(script.read_text().replace("cmd_wait()", "cmd_wait( ) ((( broken", 1))
        time.sleep(0.5)
        assert proc.poll() is None, proc.stderr.read() if proc.poll() is not None else ""
    finally:
        proc.kill(); proc.wait()

TERM_ENV = ("TERM_PROGRAM", "ITERM_SESSION_ID", "TERM_SESSION_ID", "CLAUDE_CODE_SESSION_ID")


def watcher_env(w, **env):
    base = {k: v for k, v in w.env.items() if k not in TERM_ENV}
    return dict(base, **env)


def test_a_backgrounded_watcher_keeps_its_terminal_app_but_not_its_tab(w):
    """After `claude` quits, the session runs on without terminal env; reopening it must still
    use the user's terminal, not fall back to Terminal."""
    w.env = watcher_env(w, TERM_PROGRAM="iTerm.app", ITERM_SESSION_ID="w0t0p3:1B2C-3D4E")
    w.run("wait", "--once")
    w.env = watcher_env(w)
    w.run("wait", "--once")
    rec = json.loads((w.sd / "watcher.json").read_text())
    assert (rec["term"], rec["term_session"]) == ("iTerm.app", "")

def test_wait_records_the_terminal_tab_it_runs_in(w):
    """The menu bar groups repos by this record and focuses the tab it names."""
    where = w.repo / "sub"
    where.mkdir()
    w.env = watcher_env(w, TERM_PROGRAM="iTerm.app", ITERM_SESSION_ID="w0t0p3:1B2C-3D4E",
                        TERM_SESSION_ID="other", CLAUDE_CODE_SESSION_ID="269289ac-1f2e-4d3c-9b8a-0123456789ab")
    r = w.run("wait", "--once", "--repo-dir", str(w.repo), cwd=where)
    rec = json.loads((w.sd / "watcher.json").read_text())
    assert set(rec) - {"host_pid"} == {"pid", "cwd", "term", "term_session", "tty", "session_id", "repo_dir", "remote", "script"}
    assert rec["script"] == str(w.bin / "open-pr-watch.sh"), "the plugin build the wait runs, not its private copy"
    assert rec["session_id"] == "269289ac-1f2e-4d3c-9b8a-0123456789ab", "what `claude attach` reopens"
    assert (rec["repo_dir"], rec["remote"]) == (str(w.repo), ""), "what the menu bar passes to hide"
    assert rec["cwd"] == str(where), "the directory the user runs the watcher from"
    assert rec["term"] == "iTerm.app" and rec["term_session"] == "w0t0p3:1B2C-3D4E"
    assert isinstance(rec["pid"], int)
    assert rec["tty"] == "" or re.fullmatch(r"[A-Za-z0-9/]+", rec["tty"]) and "?" not in rec["tty"]
    assert not list(w.sd.glob("watcher.json.*")), r.stderr

    w.env = watcher_env(w, TERM_PROGRAM="Apple_Terminal", TERM_SESSION_ID="7A1B-C2")
    w.run("wait", "--once")
    rec = json.loads((w.sd / "watcher.json").read_text())
    assert (rec["term"], rec["term_session"], rec["cwd"]) == ("Apple_Terminal", "7A1B-C2", str(w.repo))


@pytest.mark.parametrize("hostile", ['iTerm"$(touch pwned)', "a\nb", "x`id`", "a" * 200, "t;rm -rf ~"])
def test_a_hostile_terminal_value_is_recorded_as_empty(w, hostile):
    w.env = watcher_env(w, TERM_PROGRAM=hostile, ITERM_SESSION_ID=hostile, CLAUDE_CODE_SESSION_ID=hostile)
    w.run("wait", "--once")
    rec = json.loads((w.sd / "watcher.json").read_text())
    assert rec["term"] == "" and rec["term_session"] == "" and rec["session_id"] == ""
    assert not (w.repo / "pwned").exists() and not (w.sd / "pwned").exists()


# `ps -o <fields>= -p N` answered from FAKE_PS ("pid ppid tty comm" lines; `*` = any pid not listed,
# so the wait's own); any other ps call runs the real one.
FAKE_PS = r"""#!/usr/bin/env python3
import os, sys
a = sys.argv[1:]
table = os.environ.get("FAKE_PS")
if not table or "-o" not in a or "-p" not in a:
    os.execv("/bin/ps", ["ps"] + a)
fields = [f.rstrip("=") for f in a[a.index("-o") + 1].split(",")]
rows = {}
for line in table.splitlines():
    if line.strip():
        r = dict(zip(("pid", "ppid", "tty", "comm"), line.split(None, 3)))
        r["args"] = r.get("comm", "")
        rows[r["pid"]] = r
r = rows.get(a[a.index("-p") + 1]) or rows.get("*")
if r is None or any(f not in r for f in fields):
    os.execv("/bin/ps", ["ps"] + a)
print(" ".join(r[f] for f in fields))
"""


def with_ps(w, tree):
    d = w.home.parent / "psbin"
    d.mkdir(exist_ok=True)
    make_exe(d / "ps", FAKE_PS)
    return {"FAKE_PS": tree, "PATH": f"{d}{os.pathsep}{w.env['PATH']}"}


@pytest.mark.parametrize("tree, host", [
    ("* 7000003 ?? sh\n7000003 7000002 ?? node\n7000002 7000001 ttys007 /Users/x/.local/bin/claude\n"
     "7000001 50 ttys007 claude\n50 1 ttys007 zsh", 7000002),
    ("* 7000003 ?? sh\n7000003 7000001 ?? node\n7000001 1 ttys007 claude", 7000001),
    ("* 7000003 ?? sh\n7000003 7000001 ttys007 claude-helper\n7000001 1 ttys007 zsh", None),
    ("* 7000003 ?? sh\n7000003 1 ttys007 zsh", None),
    # an npm install: node running claude-code's cli.js
    ("* 7000003 ?? sh\n7000003 7000001 ?? sh\n7000001 50 ttys007 /usr/local/bin/node "
     "/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js --resume x\n50 1 ttys007 zsh", 7000001),
    ("* 7000003 ?? sh\n7000003 7000001 ttys007 node /srv/app/server.js\n7000001 1 ttys007 zsh", None),
])
def test_wait_records_the_claude_running_the_watcher(w, tree, host):
    """Between waits only that `claude` runs: the menu bar finds the watcher's tab by it."""
    w.env = watcher_env(w, **with_ps(w, tree))
    w.run("wait", "--once")
    rec = json.loads((w.sd / "watcher.json").read_text())
    assert rec.get("host_pid") == host, "the nearest `claude` ancestor, by its name; none ⇒ no field"
    assert rec["tty"] == "ttys007"


def test_a_directory_name_is_recorded_verbatim_as_data(w):
    odd = w.repo / 'a"b $(touch pwned) \\'
    odd.mkdir()
    w.env = watcher_env(w)
    w.run("wait", "--once", "--repo-dir", str(w.repo), cwd=odd)
    rec = json.loads((w.sd / "watcher.json").read_text())
    assert rec["cwd"] == str(odd) and rec["term"] == "" and rec["term_session"] == ""
    assert not list(w.repo.rglob("pwned"))


# ------------------------------------------------------- spawn / resume ----

def test_claude_spawn_records_the_session_and_its_open_command(w):
    sp = w.spawn(3, text="p")
    assert sp == {"pr": 3, "role": "review", "id": sp["id"], "open": f"claude attach {sp['id']}"}
    s = w.state()["sessions"]["3:review"]
    assert s["runner"] == "claude" and s["session_id"].startswith(sp["id"])
    assert s["name"] == "review o/r#3" and s["last_state"] == "working"
    assert w.claude_calls()[0] == ["--bg", "-n", "review o/r#3", "p"]


def test_spawn_on_a_claude_session_stops_waits_then_resumes_without_flags(w):
    sp = w.spawn(4)
    w.claude_set(sp["id"], "done")
    w.status_file(4, state="draft")
    again = w.spawn(4, text="second look")
    assert again == {"pr": 4, "role": "review", "id": sp["id"], "open": f"claude attach {sp['id']}", "resumed": True}
    calls = w.claude_calls()
    stop = calls.index(["stop", sp["id"]])
    sid = w.state()["sessions"]["4:review"]["session_id"]
    assert ["agents", "--json"] in calls[stop + 1:], "never waited for the session to leave the active list"
    assert calls[-1] == ["--bg", "--resume", sid, "second look"]
    assert not (w.sd / "pr-4.status.json").exists(), "a stale status file survived the relaunch"
    assert w.claude_db()["sessions"][0]["name"] == "review o/r#4"


# What `claude agents --json` printed while a resume waits for the stopped session to leave it.
@pytest.mark.parametrize("listing", ["", " \n", "[]", '[{"id": "other"}]', "{oops", "[] notice", "{}", "null",
                                     'Update available\n[{"id": "other"}]'])
def test_a_resume_reads_a_listing_without_the_session_as_none_running(w, listing):
    """`jq -e` exits 0 on no input under jq 1.6: an empty list then read as "still running" for 30 s.
    A listing that is not one JSON array reads as none running, never as a jq error that ends the run."""
    sp = w.spawn(4)
    w.claude_set(sp["id"], "done")
    w.status_file(4, state="draft")
    started = time.time()
    again = w.spawn(4, text="second look", env_extra={"FAKE_CLAUDE_LIST": listing})
    assert again["resumed"] and time.time() - started < 10


def test_a_resume_waits_while_the_stopped_session_is_still_listed(w):
    """Resumed while still listed, the CLI starts a copy instead."""
    sp = w.spawn(4)
    w.claude_set(sp["id"], "done")
    w.status_file(4, state="draft")
    again = w.spawn(4, text="second look", env_extra={"FAKE_CLAUDE_LINGER": "3"})
    assert again["resumed"] and "warning" not in again and again["id"] == sp["id"]
    calls = w.claude_calls()
    stop, resume = calls.index(["stop", sp["id"]]), [c[:2] for c in calls].index(["--bg", "--resume"])
    assert calls[stop + 1:resume].count(["agents", "--json"]) >= 3


def test_a_resume_that_starts_a_copy_is_reported_and_followed(w):
    sp = w.spawn(6)
    w.claude_set(sp["id"], "done")
    again = w.spawn(6, env_extra={"FAKE_CLAUDE_COPY": "1"})
    assert again["id"] != sp["id"] and "started a copy" in again["warning"]
    assert w.state()["sessions"]["6:review"]["id"] == again["id"]


def test_a_re_review_waits_while_the_session_still_runs(w):
    w.spawn(8)
    assert w.spawn(8, text="new") == {"pr": 8, "role": "review", "queued": True, "reason": "session still running"}
    assert "stop" not in [c[0] for c in w.claude_calls()]


def test_full_slots_queue_and_next_pops_after_a_session_finishes(w):
    w.settings(max_concurrent=1)
    first = w.spawn(1)
    assert w.spawn(2) == {"pr": 2, "role": "review", "queued": True, "reason": "all 1 slots busy"}
    assert w.run("next").stdout == ""
    w.claude_set(first["id"], "done")
    w.status_file(1, state="posted")
    popped = w.jsonl("next")
    assert popped[0].pop("queued_at").endswith("Z")
    assert popped == [{"pr": 2, "role": "review", "runner": "claude", "name": "review o/r#2",
                       "prompt_file": str(w.home / "p2.txt")}]
    assert w.state()["queue"] == []
    assert w.spawn(2)["id"]


def test_a_question_holds_its_slot(w):
    w.settings(max_concurrent=1)
    first = w.spawn(1)
    w.claude_set(first["id"], "blocked")
    assert w.spawn(2)["queued"] is True


def test_forget_makes_the_next_spawn_fresh(w):
    sp = w.spawn(9)
    w.claude_set(sp["id"], "done")
    assert w.jsonl("forget", "--pr", "9") == [{"pr": 9, "role": "review", "forgotten": True}]
    again = w.spawn(9)
    assert again["id"] != sp["id"] and "resumed" not in again


def test_spawn_cwd_runs_claude_there_and_a_resume_keeps_it(w):
    ws = w.home / "ws"
    ws.mkdir()
    sp = w.spawn(10, extra=("--cwd", str(ws)))
    assert w.claude_calls(with_cwd=True)[0]["cwd"] == str(ws.resolve())
    assert w.state()["sessions"]["10:review"]["cwd"] == str(ws.resolve())
    w.claude_set(sp["id"], "done")
    w.spawn(10, text="again")
    calls = w.claude_calls(with_cwd=True)
    stop = next(c for c in calls if c["argv"][:1] == ["stop"])
    assert stop["cwd"] == calls[-1]["cwd"] == str(ws.resolve())
    assert calls[-1]["argv"][:2] == ["--bg", "--resume"]


def test_spawn_cwd_runs_a_headless_runner_there_and_a_resume_keeps_it(w):
    ws = w.home / "ws"
    ws.mkdir()
    (w.home / "codex.out").write_text(json.dumps({"type": "thread.started", "thread_id": "th-1"}) + "\n")
    w.spawn(11, runner="codex", text="p", extra=("--cwd", str(ws)))
    rec = w.recorded("codex", 0)
    assert rec["argv"] == ["exec", "--json", "-C", str(ws.resolve()), "p"] and rec["cwd"] == str(ws.resolve())
    w.wait_dead(w.state()["sessions"]["11:review"]["pid"])
    w.status_file(11, state="draft")
    assert w.spawn(11, runner="codex", text="q")["resumed"] is True
    assert w.recorded("codex", 1)["cwd"] == str(ws.resolve())


def test_fresh_opens_a_new_session_and_leaves_the_old_one_running(w):
    sp = w.spawn(12)
    assert w.spawn(12, text="start over", extra=("--fresh",))["reason"] == "session still running", \
        "both would write the same status file"
    w.run("wait", "--once")                    # first poll only starts the cursor
    w.claude_set(sp["id"], "done")
    w.status_file(12, state="posted")
    w.run("wait", "--once")                    # delivers the result: the session is finished
    w.claude_set(sp["id"], "working")          # the user talks in the old session: not waited for
    again = w.spawn(12, text="start over", extra=("--fresh",))
    assert again["id"] != sp["id"] and "resumed" not in again and "queued" not in again
    assert "stop" not in [c[0] for c in w.claude_calls()]
    assert [c for c in w.claude_calls() if c[0] == "--bg"][-1] == ["--bg", "-n", "review o/r#12", "start over"]
    assert w.state()["sessions"]["12:review"]["id"] == again["id"]
    assert next(s for s in w.claude_db()["sessions"] if s["id"] == sp["id"])["state"] == "working"



def _age_replaced(w, seconds):
    st = w.state()
    for r in st["replaced"]:
        r["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))
    w.put_state(st)


def test_a_session_a_fresh_one_replaced_is_stopped_once_idle(w):
    """state.json no longer names it as the PR's session; without `replaced` nothing would ever stop it."""
    sp = finish(w, 12)
    again = w.spawn(12, text="start over", extra=("--fresh",))
    assert w.state()["replaced"] == [{"id": sp["id"], "role": "review", "at": w.state()["replaced"][0]["at"]}]
    w.claude_set(sp["id"], "done")
    w.run("wait", "--once")
    assert not any(c[:1] == ["stop"] for c in w.claude_calls()), "stopped before the idle period"
    _age_replaced(w, 3600)
    w.claude_set(sp["id"], "working")          # the user talks in it
    w.run("wait", "--once")
    assert not any(c[:1] == ["stop"] for c in w.claude_calls()), "stopped while in use"
    w.claude_set(sp["id"], "done")
    w.run("wait", "--once")
    assert [c for c in w.claude_calls() if c[:1] == ["stop"]] == [["stop", sp["id"]]], "only the replaced one"
    assert w.state()["replaced"] == []
    assert w.state()["sessions"]["12:review"]["id"] == again["id"]


def test_a_forgotten_session_is_stopped_once_idle(w):
    sp = finish(w, 7)
    w.run("forget", "--pr", "7")
    assert [r["id"] for r in w.state()["replaced"]] == [sp["id"]]
    _age_replaced(w, 3600)
    w.run("wait", "--once")
    assert [c for c in w.claude_calls() if c[:1] == ["stop"]] == [["stop", sp["id"]]]


# -------------------------------------------------------------- status ----

@pytest.mark.parametrize("claude_state,status_body,want", [
    ("working", None, "working"),
    ("blocked", None, "question"),
    ("failed", None, "failed"),
    ("stopped", None, "stopped"),
    ("done", {"state": "posted"}, "posted"),
    ("done", {"state": "draft"}, "draft"),
    ("done", {"state": "lgtm_chat"}, "lgtm_chat"),
    ("done", {"state": "nothing"}, "nothing"),
    ("done", {"state": "answered"}, "answered"),
    ("done", None, "failed"),
])
def test_status_maps_each_claude_state(w, claude_state, status_body, want):
    sp = w.spawn(12)
    w.claude_set(sp["id"], claude_state)
    if status_body:
        w.status_file(12, **status_body)
    row = w.jsonl("status", "--pr", "12")[0]
    assert (row["pr"], row["runner"], row["id"], row["state"]) == (12, "claude", sp["id"], want)
    assert row["open"] == f"claude attach {sp['id']}"
    assert ("note" in row) == (claude_state == "done" and status_body is None)


FAILED_422 = {"state": "failed", "note": "Post rejected (HTTP 422): a pending draft review exists on this PR.", "question": ""}


@pytest.mark.parametrize("status_body, age, want", [
    (FAILED_422, 0, "failed"),
    ({"state": "posted"}, 0, "posted"),
    ({"state": "question", "question": "Discard it?"}, 0, "question"),
    (FAILED_422, 3600, "question"),
    (None, 0, "question"),
])
def test_a_blocked_claude_session_reads_as_the_result_this_run_wrote(w, status_body, age, want):
    """A session that wrote its result, then ended its turn waiting at its prompt, lists as blocked:
    that result is the outcome. Only a file from before this run's start, none, or a question asks."""
    sp = w.spawn(12)
    assert w.run("wait", "--once").stdout == ""
    w.claude_set(sp["id"], "blocked")
    if status_body:
        w.status_file(12, **status_body)
        t = time.time() - age
        os.utime(w.sd / "pr-12.status.json", (t, t))
    assert w.jsonl("status", "--pr", "12")[0]["state"] == want
    assert [e["state"] for e in w.jsonl("wait", "--once")] == [want]


@pytest.mark.parametrize("status, status_body, want", [
    ("idle", {"state": "posted"}, "posted"),
    ("idle", None, "failed"),
    ("busy", {"state": "posted"}, "working"),
])
def test_a_working_claude_session_idle_at_its_prompt_has_finished(w, status, status_body, want):
    """A resumed or attached session that finished stays "working" + "idle", never "done"."""
    sp = w.spawn(12)
    assert w.run("wait", "--once").stdout == ""
    w.claude_set(sp["id"], "working", status)
    if status_body:
        w.status_file(12, **status_body)
    events = w.jsonl("wait", "--once")
    assert [e["state"] for e in events] == ([] if want == "working" else [want])
    if want == "failed":
        assert "ended without writing" in events[0]["note"]
    assert w.run("wait", "--once").stdout == "", "delivered once"


def test_a_finished_session_idle_at_its_prompt_is_not_in_use(w):
    sp = finish(w)
    w.claude_set(sp["id"], "working", "idle")
    assert w.spawn(5, text="again")["resumed"] is True


def test_headless_status_follows_the_pid_then_the_status_file(w):
    (w.home / "codex.out").write_text(json.dumps({"type": "thread.started", "thread_id": "th-1"}) + "\n")
    sp = w.spawn(13, runner="codex", env_extra={"FAKE_SLEEP": "30"})
    pid = w.state()["sessions"]["13:review"]["pid"]
    try:
        w.recorded("codex")
        row = w.jsonl("status")[0]
        assert row == {"pr": 13, "role": "review", "runner": "codex", "id": "th-1", "state": "working",
                       "open": "codex resume th-1"}
        assert sp["id"] is None and w.state()["sessions"]["13:review"]["id"] == "th-1", \
            "the id codex reports once running was not remembered"
    finally:
        os.kill(pid, 15)
    w.wait_dead(pid)
    assert w.jsonl("status")[0]["state"] == "failed"
    w.status_file(13, state="question", question="which base?")
    assert w.jsonl("status")[0]["state"] == "question"


# --------------------------------------------------- argv per runner ----

TRICKY = "look at $(rm -rf ~) and `id`\n'single' \"double\" $HOME \\ end"


@pytest.mark.parametrize("runner,cli,expect", [
    ("codex", "codex", lambda d, p, i: ["exec", "--json", "-C", d, p]),
    ("gemini", "gemini", lambda d, p, i: ["-p", p, "--session-id", i, "-o", "json"]),
    ("cursor", "agent", lambda d, p, i: ["-p", "--resume", "chat-abc", "--output-format", "json", p]),
    ("antigravity", "agy", lambda d, p, i: ["-p", p, "--output-format", "stream-json"]),
])
def test_headless_launch_passes_the_prompt_verbatim(w, runner, cli, expect):
    sp = w.spawn(20, runner=runner, text=TRICKY)
    n = 1 if runner == "cursor" else 0          # cursor's first call is create-chat
    rec = w.recorded(cli, n)
    assert rec["argv"] == expect(str(w.repo), TRICKY, sp["id"])
    assert rec["cwd"] == str(w.repo)
    if runner == "cursor":
        assert w.recorded("agent", 0)["argv"] == ["create-chat"]


def test_claude_launch_passes_the_prompt_verbatim(w):
    w.spawn(21, text=TRICKY)
    assert w.claude_calls()[0] == ["--bg", "-n", "review o/r#21", TRICKY]


@pytest.mark.parametrize("runner,cli,out,expect", [
    ("codex", "codex", {"type": "thread.started", "thread_id": "th-9"},
     lambda p, i: ["exec", "resume", "th-9", p]),
    ("gemini", "gemini", None, lambda p, i: ["-r", i, "-p", p]),
    ("cursor", "agent", None, lambda p, i: ["-p", "--resume", "chat-abc", "--output-format", "json", p]),
    ("antigravity", "agy", {"type": "init", "conversation_id": "conv-9"},
     lambda p, i: ["-p", p, "--conversation", "conv-9"]),
])
def test_headless_resume_reuses_the_session_id(w, runner, cli, out, expect):
    if out:
        (w.home / f"{cli}.out").write_text(json.dumps(out) + "\n")
    w.spawn(22, runner=runner)
    pid = w.state()["sessions"]["22:review"]["pid"]
    w.wait_dead(pid)
    w.status_file(22, state="question", question="?")
    again = w.spawn(22, runner=runner, text=TRICKY)
    sid = w.state()["sessions"]["22:review"]["id"]
    assert again["resumed"] is True and again["id"] == sid
    # cursor launched with two calls (create-chat, then the run); the others with one
    resume = w.recorded(cli, 2 if runner == "cursor" else 1)
    assert resume["argv"] == expect(TRICKY, sid) and resume["cwd"] == str(w.repo)
    assert again["open"] == {"codex": "codex resume th-9", "gemini": f"gemini -r {sid}",
                             "cursor": "agent --resume chat-abc",
                             "antigravity": "agy --conversation conv-9"}[runner]


# -------------------------------------------------------------- notify ----

def notify(w, event="posted", text="PR #3 posted", **kw):
    f = w.prompt(text, "note.txt")
    return w.jsonl("notify", "--event", event, "--text-file", f, **kw)[0]


def test_a_quiet_notify_writes_the_feed_line_and_no_toast(w):
    """An answered question's outcome: the menu bar must stop showing the question."""
    f = w.prompt("#49: re-review requested", "note.txt")
    out = w.jsonl("notify", "--event", "posted", "--text-file", f, "--pr", "49", "--role", "fix", "--quiet")
    assert out == [{"event": "posted", "sent": False, "reason": "quiet"}]
    assert not list(w.home.glob("osascript.*.json"))
    line = json.loads((w.sd / "feed.jsonl").read_text().splitlines()[-1])
    assert (line["pr"], line["role"], line["event"], line["summary"]) == (49, "fix", "posted", "#49: re-review requested")


def test_notify_skips_a_disabled_event(w):
    w.settings(notify={"posted": False, "question": True})
    assert notify(w) == {"event": "posted", "sent": False, "reason": "event disabled"}
    assert not list(w.home.glob("osascript.*.json"))
    assert notify(w, event="question")["sent"] is True


def test_notify_is_skipped_while_this_machine_is_snoozed(w):
    w.run("snooze", "--for", "1h")
    assert notify(w) == {"event": "posted", "sent": False, "reason": "snoozed"}
    assert not list(w.home.glob("osascript.*.json"))
    w.run("snooze", "--until", "2000-01-01T00:00:00.000Z")
    assert notify(w)["sent"] is True
    w.run("snooze", "--off")
    assert notify(w)["sent"] is True


def test_osascript_gets_the_text_as_argv_never_as_source(w):
    text = 'say "hi" & do shell script "touch /tmp/x" $(id) `id`'
    assert notify(w, text=text + "\nclaude attach 1")["via"] == "toast"
    rec = w.recorded("osascript")            # waits: the toast is detached from the watcher
    assert rec["argv"][:2] == ["-l", "JavaScript"] and rec["argv"][2].endswith("open-pr-toast.js")
    assert rec["argv"][3:7] == ["open-pr · o/r", text, "claude attach 1", "posted"]
    assert rec["argv"][10] == str(w.watch / "snooze_until"), \
        "the toast's 1h control writes the one snooze file every notifier reads"



@pytest.mark.parametrize("env, log", [({"FAKE_NO_UI": "1", "FAKE_EXIT": "139"}, "open-pr-toast.js exited 139\n"),
                                      ({"FAKE_NO_UI": "1", "FAKE_SLEEP": "60"}, "open-pr-toast.js exited 143\n")])
def test_a_toast_that_never_reaches_the_screen_is_not_reported_sent(w, tmp_path, env, log):
    """A crash (SIGSEGV) or a hang before the toast is drawn: the hung one is stopped."""
    started = time.time()
    out = notify(w, env_extra=dict(env, TMPDIR=str(tmp_path)))
    assert time.time() - started < 15
    assert out == {"event": "posted", "sent": False, "reason": "toast not shown", "log": str(w.watch / "toast.log")}
    deadline = time.time() + 5
    while not (w.watch / "toast.log").read_text().endswith(log) and time.time() < deadline:
        time.sleep(0.1)
    assert (w.watch / "toast.log").read_text().endswith(log), "the shell may name the signal first"
    assert json.loads((w.sd / "feed.jsonl").read_text().splitlines()[-1])["summary"] == "PR #3 posted", "the feed line stays"


def test_a_toast_that_crashes_after_it_showed_leaves_its_exit_code_in_the_log(w, tmp_path):
    assert notify(w, env_extra={"FAKE_EXIT": "139", "TMPDIR": str(tmp_path)})["via"] == "toast"
    deadline = time.time() + 5
    while (w.watch / "toast.log").read_text() == "" and time.time() < deadline:
        time.sleep(0.1)
    assert (w.watch / "toast.log").read_text() == "open-pr-toast.js exited 139\n"


def test_a_toast_on_screen_late_within_its_bound_is_sent_and_logs_nothing(w, tmp_path):
    started = time.time()
    out = notify(w, env_extra={"FAKE_UI_DELAY": "3", "TMPDIR": str(tmp_path)})
    assert out == {"event": "posted", "sent": True, "via": "toast"} and time.time() - started >= 3
    w.wait_dead(int((tmp_path / "open-pr-toast" / "0" / "pid").read_text()))
    assert (w.watch / "toast.log").read_text() == "", "a toast that exits 0 appends nothing"
    assert json.loads((w.sd / "feed.jsonl").read_text().splitlines()[-1])["summary"] == "PR #3 posted"


def test_a_toast_in_a_reused_slot_is_judged_by_its_own_marker(w, tmp_path):
    """Eight toasts on screen: the ninth takes slot 0, whose toast already created `shown`."""
    me = str(os.getpid())
    for n in range(8):
        (tmp_path / "open-pr-toast" / str(n)).mkdir(parents=True)
        (tmp_path / "open-pr-toast" / str(n) / "pid").write_text(me + "\n")
    (tmp_path / "open-pr-toast" / "0" / "shown").write_text("")
    out = notify(w, env_extra={"FAKE_NO_UI": "1", "FAKE_EXIT": "139", "TMPDIR": str(tmp_path)})
    assert (out["sent"], out.get("reason")) == (False, "toast not shown"), out


def test_toasts_stack_in_free_slots_and_carry_the_pr_url(w, tmp_path):
    """A new toast takes the first free slot; a slot frees when its toast exits."""
    env = {"TMPDIR": str(tmp_path), "FAKE_SLEEP": "30"}
    f = w.prompt("Reviewing #3\nfix: x", "t.txt")
    for _ in range(2):
        w.run("notify", "--event", "review_started", "--text-file", f, "--url", "https://h/o/r/pull/3",
              env_extra=env)
    first, second = w.recorded("osascript", 0), w.recorded("osascript", 1)
    assert (first["argv"][7], second["argv"][7]) == ("0", "1")
    assert first["argv"][9] == "https://h/o/r/pull/3"
    os.kill(int((tmp_path / "open-pr-toast" / "0" / "pid").read_text()), 9)
    time.sleep(0.3)
    w.run("notify", "--event", "posted", "--text-file", f, env_extra=env)
    assert w.recorded("osascript", 2)["argv"][7] == "0", "the slot of an exited toast is reused"
    for d in (tmp_path / "open-pr-toast").iterdir():
        try:
            os.kill(int((d / "pid").read_text()), 9)
        except (OSError, ValueError):
            pass

# osascript argv[11:] = the toast's focus, open command, term, term_session, tty, session_id, pid.
def test_notify_focus_hands_the_toast_where_a_click_goes(w):
    sp = w.spawn(3)
    (w.sd / "watcher.json").write_text(json.dumps(
        {"pid": 1, "cwd": "/x", "term": "iTerm.app", "term_session": "w0t0p0:AB-12", "tty": "ttys004",
         "session_id": "269289ac-1f2e", "host_pid": 7}))
    url = "https://github.com/o/r/pull/3"
    w.run("notify", "--event", "question", "--text-file", w.prompt("PR #3 needs you", "q.txt"),
          "--pr", "3", "--url", url, "--focus", "session")
    rec = w.recorded("osascript")["argv"]
    assert rec[9] == url
    assert rec[11:19] == ["session", f"claude attach {sp['id']}", "iTerm.app", "w0t0p0:AB-12", "ttys004", "269289ac-1f2e", "1", "7"]
    assert rec[19:23] == ["", "", "", ""], "only a findings toast carries Fix now"


# osascript argv[18:] = what the toast's "Fix now" runs: open-pr-watch.sh fix-now for that repo and PR.
def test_a_findings_toast_offers_fix_now_for_its_repo_and_pr(w):
    w.run("notify", "--event", "findings", "--text-file", w.prompt("#3: 2 🟠", "f.txt"), "--pr", "3",
          "--role", "fix", "--remote", "origin")
    rec = w.recorded("osascript")["argv"]
    assert rec[19:23] == [str(w.bin / "open-pr-watch.sh"), str(w.repo.resolve()), "origin", "3"]
    assert json.loads((w.sd / "feed.jsonl").read_text().splitlines()[-1])["role"] == "fix"


def test_notify_focus_defaults_to_the_pr_and_rejects_an_unknown_one(w):
    assert notify(w)["sent"] is True
    assert w.recorded("osascript")["argv"][11:19] == ["pr", "", "", "", "", "", "", ""], "no --pr, no watcher.json"
    r = w.run("notify", "--event", "posted", "--text-file", w.prompt("x"), "--focus", "tab", check=False)
    assert r.returncode == 1 and "pr watcher session" in r.stderr


def test_notify_passes_no_open_command_or_tab_outside_their_shape(w):
    """They reach a .command file and osascript argv: anything else travels as an empty string."""
    w.put_state({"cursor": None, "seen": [], "queue": [],
                 "sessions": {"3:review": {"pr": 3, "role": "review", "runner": "claude", "open": "claude attach x; touch pwned"}}})
    (w.sd / "watcher.json").write_text(json.dumps(
        {"term": 'iTerm"$(id)', "term_session": "a b", "tty": "../../x y", "session_id": "ABC; claude", "pid": "1; id",
         "host_pid": "2; id"}))
    w.run("notify", "--event", "question", "--text-file", w.prompt("q"), "--pr", "3", "--focus", "session")
    assert w.recorded("osascript")["argv"][11:19] == ["session", "", "", "", "", "", "", ""]


def _minimal_path(w, tmp_path, with_notify_send):
    """PATH without the system osascript: only the tools the script needs."""
    sysbin = tmp_path / "sysbin"
    sysbin.mkdir()
    for tool in ("sh", "jq", "cat", "date", "mkdir", "mv", "rm", "sed", "grep", "tr", "head",
                 "tail", "sort", "dirname", "basename", "mktemp", "sleep", "python3", "env"):
        src = shutil.which(tool)
        if src:
            (sysbin / tool).symlink_to(src)
    if with_notify_send:
        shutil.copy(w.fakes / "notify-send", sysbin / "notify-send")
    return str(sysbin)


# `jq --version` as each release prints it; the floor is 1.6 (open-pr.sh holds the same table).
@pytest.mark.parametrize("version, ok", [
    ("jq-1.5", False), ("jq-1.5rc2", False), ("jq-1.0", False), ("jq version 1.4", False), ("jq version 1.3", False),
    ("jq-1.6", True), ("jq-1.6-159-apple-gcff5336-dirty", True), ("jq-1.7.1", True), ("jq-1.8.0", True),
    ("jq-1.10", True), ("jq-1.15", True), ("", True), ("garbage", True)])
def test_a_jq_older_than_1_6_is_refused(w, tmp_path, version, ok):
    d = tmp_path / "oldjq"
    d.mkdir()
    make_exe(d / "jq", f'#!/bin/sh\n[ "$1" = --version ] && {{ echo "{version}"; exit 0; }}\nexec "{shutil.which("jq")}" "$@"\n')
    r = w.run("snooze", "--off", path=f"{d}{os.pathsep}{w.env['PATH']}", check=False)
    if ok:
        assert r.returncode == 0, r.stderr
    else:
        assert r.returncode == 1 and f"jq 1.6 or newer is required, found {version}" in r.stderr


def test_notify_send_gets_title_and_text_after_a_double_dash(w, tmp_path):
    out = notify(w, text="-rf text", path=_minimal_path(w, tmp_path, True))
    assert out["via"] == "notify-send"
    assert w.recorded("notify-send")["argv"] == ["--", "open-pr · o/r", "-rf text"]


def test_notify_without_a_notifier_prints_to_stderr(w, tmp_path):
    r = w.run("notify", "--event", "posted", "--text-file", w.prompt("hello", "n.txt"),
              path=_minimal_path(w, tmp_path, False))
    assert json.loads(r.stdout)["via"] == "stderr" and "[open-pr · o/r] hello" in r.stderr


def test_notify_rejects_an_unknown_event(w):
    r = w.run("notify", "--event", "nope", "--text-file", w.prompt("x"), check=False)
    assert r.returncode == 1 and "review_started" in r.stderr


# --------------------------------------------------------------- trust ----

def trust(w, config, runner="claude", repo_dir=None, cwd=None):
    cfg = w.home / "claude.json"
    if config is None:
        cfg.unlink(missing_ok=True)
    else:
        cfg.write_text(config if isinstance(config, str) else json.dumps(config))
    args = ["trust", "--runner", runner] + (["--repo-dir", str(repo_dir)] if repo_dir else []) \
        + (["--cwd", str(cwd)] if cwd else [])
    return w.run(*args, env_extra={"OPEN_PR_CLAUDE_CONFIG": str(cfg)}).stdout.splitlines()


def test_trust_reads_claudes_own_record_for_the_exact_directory(w):
    repo = str(w.repo.resolve())
    parent = str(w.repo.resolve().parent)
    before = {"projects": {repo: {"hasTrustDialogAccepted": True}}}
    assert trust(w, before) == ["trusted"]
    assert json.loads((w.home / "claude.json").read_text()) == before, "trust never writes claude's file"
    assert trust(w, {"projects": {parent: {"hasTrustDialogAccepted": True}}}) == \
        ["untrusted", f"run: cd {repo} && claude"], "a trusted parent does not cover the repo"
    assert trust(w, {"projects": {repo: {"hasTrustDialogAccepted": False}}})[0] == "untrusted"
    assert trust(w, {}) == ["untrusted", f"run: cd {repo} && claude"]
    assert trust(w, None) == ["unknown"], "no config file"
    assert trust(w, "{not json") == ["unknown"]
    assert trust(w, before, repo_dir=w.home) == ["untrusted", f"run: cd {w.home.resolve()} && claude"]


def test_trust_cwd_checks_that_directory_instead_of_the_repo(w):
    repo, ws = str(w.repo.resolve()), str(w.home.resolve())
    assert trust(w, {"projects": {ws: {"hasTrustDialogAccepted": True}}}, cwd=w.home) == ["trusted"]
    assert trust(w, {"projects": {repo: {"hasTrustDialogAccepted": True}}}, cwd=w.home) == \
        ["untrusted", f"run: cd {ws} && claude"]


@pytest.mark.parametrize("runner", ["codex", "gemini", "cursor", "antigravity"])
def test_trust_is_not_applicable_to_headless_runners(w, runner):
    assert trust(w, None, runner=runner) == ["n/a"]


def test_an_untrusted_workspace_stops_spawn_with_exit_8(w):
    r = w.run("spawn", "--runner", "claude", "--pr", "3", "--name", "review o/r#3",
              "--prompt-file", w.prompt("p"), env_extra={"FAKE_CLAUDE_UNTRUSTED": "1"}, check=False)
    assert r.returncode == 8
    assert f"workspace not trusted: run `cd {w.repo.resolve()} && claude` once and accept the trust prompt" \
        in r.stderr
    assert not (w.sd / "state.json").exists() or not w.state()["sessions"], \
        "a refused launch records no session"


# ------------------------------------------------------------ finished ----

def finish(w, pr=5):
    """A claude session whose result `wait` has delivered."""
    sp = w.spawn(pr)
    assert w.run("wait", "--once").stdout == ""
    w.claude_set(sp["id"], "done")
    w.status_file(pr, state="posted", url=f"https://github.com/o/r/pull/{pr}")
    assert [e["state"] for e in w.jsonl("wait", "--once")] == ["posted"]
    return sp



def _age_result(w, pr, seconds):
    st = w.state()
    st["sessions"][f"{pr}:review"]["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))
    w.put_state(st)


def test_an_idle_finished_session_is_stopped_but_nothing_else(w):
    """An idle background session holds memory; stop keeps its conversation for attach/resume."""
    sp = finish(w)
    other = w.spawn(6)                                   # still reviewing: never stopped
    w.claude_set(sp["id"], "done")
    _age_result(w, 5, 60)
    w.run("wait", "--once")
    assert not any(c[:1] == ["stop"] for c in w.claude_calls()), "stopped before the idle period"
    _age_result(w, 5, 3600)
    w.run("wait", "--once")
    stops = [c for c in w.claude_calls() if c[:1] == ["stop"]]
    assert stops == [["stop", sp["id"]]], "only the watcher's own finished, idle session"
    assert w.state()["sessions"]["5:review"]["parked"] is True
    w.run("wait", "--once")
    assert [c for c in w.claude_calls() if c[:1] == ["stop"]] == stops, "stopped once"
    assert other["id"] != sp["id"]


def test_a_session_the_user_talks_in_is_not_stopped(w):
    sp = finish(w)
    _age_result(w, 5, 3600)
    w.claude_set(sp["id"], "working")
    w.run("wait", "--once")
    assert not any(c[:1] == ["stop"] for c in w.claude_calls())

def test_a_finished_session_stays_silent_while_the_user_chats_in_it(w):
    """The user's own turns there must not toast "needs an answer" or "posted" again."""
    sp = finish(w)
    assert w.state()["sessions"]["5:review"]["finished"] is True
    for live in ("working", "blocked", "done"):
        w.claude_set(sp["id"], live)
        assert w.run("wait", "--once").stdout == "", f"a finished session reported {live}"
    assert w.jsonl("status") == [{"pr": 5, "role": "review", "runner": "claude", "id": sp["id"], "state": "posted",
                                  "open": f"claude attach {sp['id']}", "finished": True}]


def test_a_draft_the_user_publishes_in_a_finished_session_reports_posted(w):
    """The menu bar row must leave "draft waiting" once the session rewrites its status file."""
    sp = w.spawn(5)
    assert w.run("wait", "--once").stdout == ""
    w.claude_set(sp["id"], "done")
    w.status_file(5, state="draft")
    assert [e["state"] for e in w.jsonl("wait", "--once")] == ["draft"]
    w.claude_set(sp["id"], "working")
    assert w.run("wait", "--once").stdout == ""
    w.status_file(5, state="posted")
    assert [e["state"] for e in w.jsonl("wait", "--once")] == ["posted"]
    assert w.state()["sessions"]["5:review"]["last_state"] == "posted"
    assert w.run("wait", "--once").stdout == ""


def test_a_resumed_session_reports_again(w):
    sp = finish(w)
    w.claude_set(sp["id"], "done")
    again = w.spawn(5, text="second look")
    assert again["resumed"] is True
    assert w.state()["sessions"]["5:review"]["finished"] is False
    assert w.run("wait", "--once").stdout == ""
    w.claude_set(sp["id"], "blocked")
    assert [e["state"] for e in w.jsonl("wait", "--once")] == ["question"]


def test_a_new_request_never_cuts_a_conversation_in_a_finished_session(w):
    """A new request queues instead of `claude stop`; `wait` says `ready` once it is idle."""
    sp = finish(w)
    w.claude_set(sp["id"], "working")
    out = w.spawn(5, text="second look")
    assert out.get("queued") is True and out["reason"] == "session in use"
    assert not any(c[:1] == ["stop"] for c in w.claude_calls()), "the conversation was stopped"
    assert w.run("wait", "--once").stdout == "", "not ready while the user is still talking"
    w.claude_set(sp["id"], "done")
    assert [(e["event"], e["pr"]) for e in w.jsonl("wait", "--once")] == [("ready", 5)]
    assert w.jsonl("next")[0]["pr"] == 5


def test_a_question_left_unanswered_holds_a_new_request_only_for_a_while(w):
    """After the grace period a new request goes ahead (stop + resume), not queued forever."""
    sp = finish(w)
    w.claude_set(sp["id"], "blocked")
    assert w.spawn(5, text="again")["reason"] == "session in use"
    assert w.run("wait", "--once").stdout == "", "within the grace period"
    st = w.state()
    st["queue"][0]["queued_at"] = "2026-01-01T00:00:00Z"   # queued long ago
    w.put_state(st)
    assert [(e["event"], e["pr"]) for e in w.jsonl("wait", "--once")] == [("ready", 5)]
    assert w.spawn(5, text="again")["resumed"] is True

def test_a_finished_session_holds_no_slot_whatever_its_live_state(w):
    w.settings(max_concurrent=1)
    sp = finish(w, 1)
    w.claude_set(sp["id"], "working")
    assert "queued" not in w.spawn(2)


def test_spawn_keeps_what_the_menu_bar_shows(w):
    url = "https://github.com/o/r/pull/3"
    sp = w.jsonl("spawn", "--runner", "claude", "--pr", "3", "--name", "review o/r#3",
                 "--prompt-file", w.prompt("p"), "--url", url)[0]
    s = w.state()["sessions"]["3:review"]
    assert (s["repo"], s["url"], s["open"], s["finished"]) == ("o/r", url, f"claude attach {sp['id']}", False)


def test_last_state_at_follows_each_state_change(w):
    """The menu bar weighs it against the newest feed line to pick the row's state."""
    sp = w.spawn(5)
    s = w.state()["sessions"]["5:review"]
    assert s["last_state_at"] == s["started_at"], "spawn records when the state became working"
    st = w.state()
    st["sessions"]["5:review"]["last_state_at"] = "2026-01-01T00:00:00Z"
    w.put_state(st)
    w.run("wait", "--once")
    assert w.state()["sessions"]["5:review"]["last_state_at"] == "2026-01-01T00:00:00Z", "unchanged state"
    w.claude_set(sp["id"], "blocked")
    assert [e["state"] for e in w.jsonl("wait", "--once")] == ["question"]
    at = w.state()["sessions"]["5:review"]["last_state_at"]
    assert at > "2026-01-01T00:00:00Z" and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", at)


# ---------------------------------------------------------- rate limit ----

def test_wait_once_passes_a_rate_limit_through_and_still_beats(w):
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    (w.home / "triggers.rc").write_text("9\n")
    r = w.run("wait", "--once", check=False)
    assert r.returncode == 9 and "rate limited" in r.stderr
    assert (w.sd / "heartbeat").exists(), "the menu bar would count this repo as no longer watched"


def test_wait_backs_off_on_a_rate_limit_and_recovers(w):
    w.settings(poll_interval_seconds=1)
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    (w.home / "triggers.rc").write_text("9\n9\nquiet\n9\n")
    w.triggers(trig("51", "2026-01-01T00:00:05Z"))
    r = w.run("wait")
    assert [json.loads(l)["comment_id"] for l in r.stdout.splitlines()] == ["51"]
    assert [l for l in r.stderr.splitlines() if "rate limited" in l] == [
        "rate limited — next poll in 2s", "rate limited — next poll in 4s",
        "rate limited — next poll in 2s"], "doubles per limit; a good poll resets to the interval"



def test_a_failure_that_persists_ends_the_wait_so_the_watcher_can_say_so(w):
    """No network (or a sandbox) used to leave `wait` retrying forever while the chat looked idle."""
    w.settings(poll_interval_seconds=1)
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    (w.home / "triggers.rc").write_text("1\nquiet\n1\n1\n1\n")
    r = w.run("wait", check=False)
    assert r.returncode == 1 and "triggers failed 3 polls in a row" in r.stderr, r.stderr
    assert r.stderr.count("retrying next poll") == 3, "a success in between resets the count"

def test_the_backoff_stops_at_fifteen_minutes(w):
    w.settings(poll_interval_seconds=500)
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    (w.home / "triggers.rc").write_text("9\n")
    proc = subprocess.Popen(["sh", str(w.bin / "open-pr-watch.sh"), "wait"], cwd=w.repo, env=w.env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        line = proc.stderr.readline()
    finally:
        os.killpg(proc.pid, 9)
        proc.wait()
    assert line.strip() == "rate limited — next poll in 900s"



def test_the_repo_setting_is_the_only_poll_interval(w):
    """No machine-wide override: the settings panel's "Apply to all" writes each repo's setting."""
    r = w.run("poll", "--seconds", "30", check=False)
    assert r.returncode == 1 and "unknown subcommand" in r.stderr
    for f in (WATCH, MENUBAR):
        assert "poll_seconds" not in f.read_text(), f


def test_a_running_wait_re_reads_the_repos_settings_at_each_poll(w):
    """A change made in the menu bar mid-wait (interval, slots) applies from the next poll."""
    w.settings(poll_interval_seconds=15)
    w.run("wait", "--once")                                    # cursor set
    calls = lambda: sum(1 for l in (w.home / "open-pr.calls").read_text().splitlines() if l.startswith("settings "))
    before = calls()
    proc = subprocess.Popen(["sh", str(w.bin / "open-pr-watch.sh"), "wait"], cwd=w.repo, env=w.env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    w.children.append(proc)
    try:
        time.sleep(18)                                         # 2 polls, 15 s apart
        assert calls() - before >= 3, "read once at start, then cached for the life of the wait"
    finally:
        proc.kill(); proc.wait()


def test_settings_names_the_repo_and_passes_a_write_through_to_open_pr(w):
    (w.home / "settings.json").write_text(json.dumps({"watch": {"max_concurrent": 3}}))
    assert w.jsonl("settings")[0] == {"watch": {"max_concurrent": 3}}
    w.run("settings", "--set", "watch.max_concurrent", "--value", "8")
    last = (w.home / "open-pr.calls").read_text().splitlines()[-1]
    assert last == f"settings --repo r --repo-dir {w.repo.resolve()} --set watch.max_concurrent --value 8"
    assert w.run("settings", "--set", "watch.max_concurrent", check=False).returncode == 1, "--set needs --value"


# -------------------------------------------------------------- snooze ----

def test_snooze_for_until_and_off_share_one_machine_file(w):
    f = w.watch / "snooze_until"
    out = w.jsonl("snooze", "--for", "2h30m")[0]
    left = datetime.fromisoformat(out["snooze_until"].replace("Z", "+00:00")) - datetime.now(timezone.utc)
    assert 9000 - 60 < left.total_seconds() <= 9000
    assert f.read_text() == out["snooze_until"] + "\n"
    assert w.jsonl("snooze", "--until", "2026-01-01T09:00:00+09:00") == [{"snooze_until": "2026-01-01T00:00:00Z"}]
    assert f.read_text() == "2026-01-01T00:00:00Z\n"
    assert w.jsonl("snooze", "--off") == [{"snooze_until": None}] and not f.exists()
    assert w.jsonl("snooze", "--off") == [{"snooze_until": None}], "resuming twice is fine"
    assert not (w.home / "data").exists(), "machine-wide files stay out of every data directory"
    for bad in (["--for", "soon"], ["--for", "0m"], ["--for", "1h;id"], ["--until", "tomorrow"]):
        assert w.run("snooze", *bad, check=False).returncode == 4, bad
    for bad in ([], ["--off", "--for", "1h"]):
        assert w.run("snooze", *bad, check=False).returncode == 1, bad


# ---------------------------------------------------------------- feed ----

def test_notify_feeds_the_last_fifty_notifications_sent_or_snoozed(w):
    w.sd.mkdir(parents=True)
    (w.sd / "feed.jsonl").write_text("".join(json.dumps({"summary": f"old {i}"}) + "\n" for i in range(50)))
    w.settings(notify={"question": False})
    f = w.prompt("PR #3 posted\nclaude attach 1", "n.txt")
    w.run("notify", "--event", "question", "--text-file", f, "--pr", "3")
    assert len((w.sd / "feed.jsonl").read_text().splitlines()) == 50, "a disabled event is no notification"
    w.run("notify", "--event", "posted", "--text-file", f, "--pr", "3", "--url", "https://h/o/r/pull/3")
    w.run("snooze", "--for", "1h")
    w.run("notify", "--event", "review_started", "--text-file", w.prompt("Reviewing #4", "m.txt"))
    rows = [json.loads(l) for l in (w.sd / "feed.jsonl").read_text().splitlines()]
    assert len(rows) == 50 and rows[0] == {"summary": "old 2"}
    at = rows[-2].pop("at")
    assert datetime.fromisoformat(at.replace("Z", "+00:00")).tzinfo is not None
    assert rows[-2] == {"repo": "o/r", "pr": 3, "role": "review", "event": "posted", "summary": "PR #3 posted",
                        "detail": "claude attach 1", "url": "https://h/o/r/pull/3", "focus": "pr"}
    assert (rows[-1]["event"], rows[-1]["pr"], rows[-1]["url"], rows[-1]["detail"]) == \
        ("review_started", None, None, ""), "a snoozed notification is still recent history"


@pytest.mark.parametrize("focus", ["pr", "watcher", "session", None])
def test_a_feed_line_keeps_where_its_click_goes(w, focus):
    """The menu bar sends a question's row where the user answers it, as the toast does."""
    extra = ("--focus", focus) if focus else ()
    w.run("notify", "--event", "question", "--text-file", w.prompt("5 old /open-pr triggers"), "--pr", "3", "--quiet", *extra)
    assert json.loads((w.sd / "feed.jsonl").read_text().splitlines()[-1])["focus"] == (focus or "pr")


def test_a_feed_line_is_never_written_for_an_unknown_focus(w):
    r = w.run("notify", "--event", "question", "--text-file", w.prompt("q"), "--focus", "tab", "--quiet", check=False)
    assert r.returncode == 1 and not (w.sd / "feed.jsonl").exists()


def test_notify_rejects_a_pr_that_is_not_a_number(w):
    r = w.run("notify", "--event", "posted", "--text-file", w.prompt("x"), "--pr", "3;id", check=False)
    assert r.returncode == 4


# ------------------------------------------------------------- menubar ----

def test_menubar_without_osascript_is_no_equivalent(w, tmp_path):
    r = w.run("menubar", path=_minimal_path(w, tmp_path, False))
    assert r.stdout == "NO-EQUIVALENT\n"


def test_a_menu_bar_that_exits_at_start_is_reported_not_started(w):
    """Inside a shell sandbox osascript cannot reach the window server and exits at once."""
    r = w.run("menubar", env_extra={"FAKE_NO_UI": "1"}, check=False)
    assert r.returncode == 1 and r.stdout == "" and "sandbox off" in r.stderr
    assert not (w.watch / "menubar.pid").exists()
    assert w.run("menubar", env_extra={"FAKE_SLEEP": "30"}).stdout == "started\n", "a later start is not blocked"
    os.kill(int((w.watch / "menubar.pid").read_text()), 9)


def test_a_menu_bar_that_shows_no_item_is_stopped_not_reported_started(w):
    """A process merely alive is no item in the menu bar: one hung before its item exists."""
    started = time.time()
    r = w.run("menubar", env_extra={"FAKE_NO_UI": "1", "FAKE_SLEEP": "60"}, check=False)
    assert r.returncode == 1 and r.stdout == "" and "showed no item in 10 s" in r.stderr
    assert str(w.watch / "menubar.log") in r.stderr
    assert time.time() - started < 20
    assert not (w.watch / "menubar.pid").exists()
    out = subprocess.run(["pgrep", "-f", f"open-pr-menubar.js {w.watch}"], capture_output=True, text=True).stdout
    assert out == "", "the hung menu bar was left running"


def test_a_menu_bar_whose_item_shows_late_within_its_bound_is_started(w):
    started = time.time()
    try:
        assert w.run("menubar", env_extra={"FAKE_UI_DELAY": "6", "FAKE_SLEEP": "30"}).stdout == "started\n"
        assert time.time() - started >= 6
        assert w.run("menubar").stdout == "running\n"
    finally:
        os.kill(int((w.watch / "menubar.pid").read_text()), 9)


def test_menubar_closes_on_request(w):
    env = {"FAKE_SLEEP": "30"}
    assert w.run("menubar", env_extra=env).stdout == "started\n"
    pid = int((w.watch / "menubar.pid").read_text())
    assert w.run("menubar", "--close").stdout == "closed\n"
    w.wait_dead(pid)
    assert not (w.watch / "menubar.pid").exists()
    assert w.run("menubar", "--close").stdout == "not running\n"

def test_a_data_dir_mapped_after_the_menubar_started_restarts_it(w):
    """A watcher on a repo under a new `data_dirs` root writes where the running menu bar never looks."""
    env = {"FAKE_SLEEP": "30"}
    assert w.run("menubar", env_extra=env).stdout == "started\n"
    old = int((w.watch / "menubar.pid").read_text())
    try:
        assert w.run("menubar", env_extra=env).stdout == "running\n"
        assert w.run("menubar", env_extra={**env, "FAKE_DATA3": str(w.home / "data3")}).stdout == "started\n"
        w.wait_dead(old)
        assert w.recorded("osascript", 1)["argv"][-2] == str(w.home / "data3")
    finally:
        for f in (w.watch / "menubar.pid",):
            try: os.kill(int(f.read_text()), 9)
            except (OSError, ValueError): pass


def test_menubar_runs_detached_once_per_machine(w):
    env = {"FAKE_SLEEP": "30"}
    watch = w.watch
    started = time.time()
    assert w.run("menubar", env_extra=env).stdout == "started\n"
    assert time.time() - started < 10, "menubar waited on the menu bar process"
    assert (REPO / "src" / "bin" / "open-pr-menubar.js").is_file()
    rec = w.recorded("osascript")
    assert rec["argv"] == ["-l", "JavaScript", str(w.bin / "open-pr-menubar.js"),
                           str(watch / "snooze_until"), str(watch / "menubar.pid"), "2700",
                           str(w.home / "data"), str(w.home / "data2"), str(w.bin / "open-pr-watch.sh")], \
        "the menu bar scans every data directory the config knows, one per argv element, then gets " \
        "the script its Remove from list runs"
    pid = int((watch / "menubar.pid").read_text())
    try:
        assert w.run("menubar", env_extra=env).stdout == "running\n"
        assert not (w.home / "osascript.1.json").exists(), "a second menu bar was started"
    finally:
        os.kill(pid, 9)
        w.wait_dead(pid)
    assert w.run("menubar", env_extra=env).stdout == "started\n", "a dead pid is not a running menu bar"
    pid = int((watch / "menubar.pid").read_text())
    os.kill(pid, 9)
    w.wait_dead(pid)
    (watch / "menubar.pid").write_text(f"{os.getpid()}\n")
    assert w.run("menubar", env_extra=env).stdout == "started\n", "a reused pid is not the menu bar"
    os.kill(int((watch / "menubar.pid").read_text()), 9)


def test_a_menubar_older_than_its_build_says_so_and_restarts_only_on_request(w):
    """A plugin update rewrites open-pr-menubar.js (a new install directory, or in place): a menu bar
    started before it runs the old code. A watcher's start runs `menubar` too: it never restarts it."""
    env = {"FAKE_SLEEP": "30"}
    js = w.bin / "open-pr-menubar.js"
    js.write_text("")
    t = time.time()
    os.utime(js, (t - 100, t - 100))
    assert w.run("menubar", env_extra=env).stdout == "started\n"
    old = int((w.watch / "menubar.pid").read_text())
    try:
        assert w.run("menubar", env_extra=env).stdout == "running\n", "a build older than the start is none"
        os.utime(w.watch / "menubar.dirs", (t - 60, t - 60))   # it started at t - 60 …
        os.utime(js, (t - 50, t - 50))                         # … and the plugin updated after
        assert w.run("menubar", env_extra=env).stdout == "out of date\n"
        os.kill(old, 0)
        assert not (w.home / "osascript.1.json").exists(), "it was restarted on its own"
        assert w.run("menubar", "--restart", env_extra=env).stdout == "started\n"
        w.wait_dead(old)
        new = int((w.watch / "menubar.pid").read_text())
        assert new != old and w.recorded("osascript", 1)["argv"][2] == str(js)
        assert w.run("menubar", env_extra=env).stdout == "running\n", "the one started runs this build"
    finally:
        for pid in (old, int((w.watch / "menubar.pid").read_text() or 0)):
            try: os.kill(pid, 9)
            except (OSError, ValueError): pass


# ------------------------------------------------------------ hide / closed PRs ----

def tracked(w, pr=5):
    """A spawned session with the cursor started: the first `wait` does nothing else."""
    sp = w.spawn(pr)
    assert w.run("wait", "--once").stdout == ""
    return sp


def open_prs_calls(w):
    f = w.home / "open-pr.calls"
    return [l for l in f.read_text().splitlines() if l.startswith("open-prs")] if f.exists() else []


def test_waiters_reclaiming_one_dead_state_lock_never_hold_it_together(w):
    """Every waiter sees the same dead holder; were two to hold the lock at once, one write is lost."""
    w.put_state({"cursor": None, "seen": [], "sessions": {}, "queue": []})
    dead = subprocess.Popen(["true"])
    dead.wait()
    (w.sd / ".lock").mkdir()
    (w.sd / ".lock" / "pid").write_text(f"{dead.pid}\n")
    procs = [subprocess.Popen(["sh", str(w.bin / "open-pr-watch.sh"), "hide", "--pr", str(n)], cwd=w.repo, env=w.env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True) for n in range(1, 9)]
    codes = [(p.wait(timeout=60), p.stderr.read()) for p in procs]
    assert all(c == 0 for c, _ in codes), codes
    assert w.state()["hidden"] == list(range(1, 9))
    assert not list(w.sd.glob(".lock*")), "a reclaimed lock left a renamed copy behind"


def test_a_state_lock_that_never_got_its_pid_is_reclaimed(w):
    w.put_state({"cursor": None, "seen": [], "sessions": {}, "queue": []})
    (w.sd / ".lock").mkdir()
    start = time.time()
    w.run("hide", "--pr", "3")
    assert 4 <= time.time() - start < 20 and w.state()["hidden"] == [3]


def test_hide_is_idempotent_and_a_new_request_brings_the_row_back(w):
    sp = w.spawn(5)
    assert w.jsonl("hide", "--pr", "5") == [{"pr": 5, "hidden": True}]
    assert w.jsonl("hide", "--pr", "5") == [{"pr": 5, "hidden": True}]
    w.run("hide", "--pr", "9")
    assert w.state()["hidden"] == [5, 9]
    assert w.jsonl("status")[0] == {"pr": 5, "role": "review", "runner": "claude", "id": sp["id"], "state": "working",
                                    "open": f"claude attach {sp['id']}", "hidden": True}, "hidden, still tracked"
    w.spawn(5, text="again")
    assert w.state()["hidden"] == [9]
    assert "hidden" not in w.jsonl("status")[0]
    assert w.run("hide", "--pr", "x", check=False).returncode == 4


def test_wait_asks_which_prs_are_open_at_most_every_ten_minutes(w):
    tracked(w)
    assert open_prs_calls(w) == []
    (w.home / "open.txt").write_text("5\n")
    w.run("wait", "--once")
    assert len(open_prs_calls(w)) == 1 and open_prs_calls(w)[0].startswith("open-prs --vendor github --owner o --repo r")
    w.run("wait", "--once")
    assert len(open_prs_calls(w)) == 1, "checked again within 600 s"
    st = w.state()
    st["open_checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 601))
    w.put_state(st)
    w.run("wait", "--once")
    assert len(open_prs_calls(w)) == 2
    assert w.state().get("hidden", []) == [], "an open PR stays listed"


def test_nothing_tracked_asks_the_vendor_nothing(w):
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    w.run("wait", "--once")
    assert open_prs_calls(w) == []


def test_a_merged_pr_is_hidden_and_its_idle_session_stopped(w):
    sp = finish(w, 5)                                   # finished just now: no idle wait applies
    st = w.state()
    st.pop("open_checked_at", None)                     # finish's own polls had no open list
    st["queue"] = [{"key": "5:review", "pr": 5, "role": "review", "runner": "claude", "name": "review o/r#5", "prompt_file": "/p"},
                   {"key": "12:review", "pr": 12, "role": "review", "runner": "claude", "name": "review o/r#12", "prompt_file": "/q"}]
    st["titles"] = {"5": "Gone", "12": "Still open"}
    w.put_state(st)
    w.sd.joinpath("feed.jsonl").write_text(json.dumps({"at": "2026-01-01T00:00:00Z", "repo": "o/r", "pr": 8,
                                                       "event": "posted", "summary": "Posted"}) + "\n")
    (w.home / "open.txt").write_text("12\n")
    w.run("wait", "--once")
    st = w.state()
    assert st["hidden"] == [5, 8], "a feed-only row goes too"
    assert [q["pr"] for q in st["queue"]] == [12], "a closed PR's queued request is dropped"
    assert st["titles"] == {"12": "Still open"}
    assert st["sessions"]["5:review"]["closed"] is True and st["sessions"]["5:review"]["parked"] is True
    assert [c for c in w.claude_calls() if c[:1] == ["stop"]] == [["stop", sp["id"]]]


def test_a_closed_prs_working_session_is_stopped_only_once_idle(w):
    sp = tracked(w)
    (w.home / "open.txt").write_text("")
    w.run("wait", "--once")
    assert w.state()["sessions"]["5:review"]["closed"] is True and w.state()["hidden"] == [5]
    assert not any(c[:1] == ["stop"] for c in w.claude_calls()), "a working review is never cut"
    w.claude_set(sp["id"], "done")
    w.status_file(5, state="posted")
    assert [e["state"] for e in w.jsonl("wait", "--once")] == ["posted"]
    assert [c for c in w.claude_calls() if c[:1] == ["stop"]] == [["stop", sp["id"]]], "no idle wait"


def test_a_closed_prs_session_the_user_talks_in_is_not_stopped(w):
    sp = finish(w)
    w.claude_set(sp["id"], "working")
    st = w.state()
    st.pop("open_checked_at", None)
    w.put_state(st)
    (w.home / "open.txt").write_text("")
    w.run("wait", "--once")
    assert w.state()["sessions"]["5:review"]["closed"] is True
    assert not any(c[:1] == ["stop"] for c in w.claude_calls()), "in use"
    w.claude_set(sp["id"], "done")
    w.run("wait", "--once")
    assert [c for c in w.claude_calls() if c[:1] == ["stop"]] == [["stop", sp["id"]]]


@pytest.mark.parametrize("rc", ["1", "9"])
def test_a_failed_open_check_is_skipped_until_the_next_slot(w, rc):
    tracked(w)
    (w.home / "open.rc").write_text(rc)
    r = w.run("wait", "--once")
    assert r.stdout == "", "no event"
    lines = [l for l in r.stderr.splitlines() if "open-prs" in l]
    assert lines == ([] if rc == "9" else ["open-pr-watch.sh: open-prs failed (exit 1), next check in 600s: open-prs down"])
    assert w.state().get("hidden", []) == [] and w.state()["open_checked_at"]
    w.run("wait", "--once")
    assert len(open_prs_calls(w)) == 1


def test_an_open_check_rate_limit_backs_off_like_triggers(w):
    w.settings(poll_interval_seconds=1)
    w.spawn(5)
    (w.home / "open.rc").write_text("9")
    (w.home / "triggers.rc").write_text("quiet\n")
    w.triggers(trig("51", "2099-01-01T00:00:05Z"))
    r = w.run("wait")
    assert "rate limited — next poll in 2s" in r.stderr
    assert [json.loads(l)["comment_id"] for l in r.stdout.splitlines()] == ["51"]


# ------------------------------------------------------------ fix role ----

def finding(pr=5, review="70", **kw):
    return {"pr": pr, "url": f"https://github.com/o/r/pull/{pr}", "head_branch": "feat/x", "review_id": review, "comment_id": "10",
            "thread_id": None, "kind": "line", "user": "rev", "created_at": "2026-01-01T00:00:10Z",
            "counts": {"🟠": 2, "🔵": 4}, **kw}


def fix_ready(w, *rows):
    """Every role set's cursor at one time: a wait of any `--roles` delivers what follows it."""
    c = "2026-01-01T00:00:00Z"
    w.put_state({"cursor": c, "seen": [], "sessions": {}, "queue": [],
                 "cursors": {"review": {"cursor": c, "seen": []}, "fix": {"cursor": c, "seen": []}}})
    (w.home / "findings.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_wait_asks_for_findings_on_the_users_own_prs_or_only_the_listed_ones(w):
    fix_ready(w)
    (w.home / "account.txt").write_text("dev\n")
    w.run("wait", "--once")
    call = last_triggers_call(w)
    assert "--findings-file " in call and call.endswith("--fix-author dev")
    assert f"--cache-dir {w.sd / 'etags'}" in call, "GitHub polls are conditional on the kept ETags"
    w.run("wait", "--once", "--fix-prs", "5,7")
    call = last_triggers_call(w)
    assert "--fix-author" not in call and call.endswith("--fix-prs 5,7")
    w.run("wait", "--once", "--roles", "review")
    assert "--findings-file" not in last_triggers_call(w)
    assert w.run("wait", "--once", "--roles", "deploy", check=False).returncode == 4


def test_a_new_review_with_findings_is_delivered_once_and_kept_for_the_menu_bar(w):
    fix_ready(w, finding())
    ev = w.jsonl("wait", "--once")
    assert ev == [{"event": "findings", "repo": "o/r", "pr": 5, "review_id": "70", "counts": {"🟠": 2, "🔵": 4},
                   "url": "https://github.com/o/r/pull/5", "head_branch": "feat/x", "comment_id": "10",
                   "thread_id": None, "user": "rev"}]
    assert w.run("wait", "--once").stdout == "", "a review is delivered once"
    assert w.state()["findings"]["5"]["review_id"] == "70"
    w.spawn(5, extra=("--role", "fix"))
    assert "5" not in w.state().get("findings", {}), "a fix session takes the pending findings"
    row = w.jsonl("status", "--pr", "5", "--role", "fix")[0]
    assert row["findings"]["comment_id"] == "10" and row["findings"]["user"] == "rev", \
        "what a re-review request replies to"


def test_wait_keeps_each_prs_title_for_the_menu_bar_and_hands_the_watcher_none(w):
    fix_ready(w, finding(title="Add retry"))
    w.triggers(dict(trig("c1", "2026-01-01T00:00:05Z", pr=7), title="Fix login"))
    ev = w.jsonl("wait", "--once")
    assert sorted(e["event"] for e in ev) == ["findings", "trigger"] and not [e for e in ev if "title" in e]
    assert w.state()["titles"] == {"5": "Add retry", "7": "Fix login"}


def test_a_fix_run_in_the_watchers_own_session_is_tracked_until_its_status_file_says_how_it_ended(w):
    fix_ready(w, finding())
    w.run("wait", "--once")
    assert w.jsonl("here", "--pr", "5", "--url", "https://github.com/o/r/pull/5") == [{"pr": 5, "role": "fix", "runner": "here"}]
    assert "5" not in w.state().get("findings", {}), "it takes the pending findings, as a fix session does"
    row = w.jsonl("status", "--pr", "5", "--role", "fix")[0]
    assert (row["runner"], row["id"], row["state"], row["open"], row["findings"]["comment_id"]) == ("here", None, "working", None, "10")
    assert w.run("wait", "--once").stdout == "", "working is no change"
    w.run("fix-now", "--pr", "5")
    assert w.run("wait", "--once").stdout == "", "a Fix now click while it runs opens nothing"
    assert w.run("here", "--pr", "5", check=False).returncode == 1, "one fix of a PR at a time"
    r = w.run("spawn", "--runner", "claude", "--role", "fix", "--pr", "5", "--name", "fix o/r#5",
              "--prompt-file", w.prompt("fix it", "p5.txt"), check=False)
    assert r.returncode == 1 and "watcher's own session" in r.stderr, "no background fix over one running here"
    (w.sd / "pr-5-fix.status.json").write_text(json.dumps({"state": "fixed", "counts": {"fixed": 2, "declined": 0}}))
    assert w.jsonl("wait", "--once") == [{"event": "session", "repo": "o/r", "pr": 5, "role": "fix", "state": "fixed", "open": None}]
    assert w.state()["sessions"]["5:fix"]["finished"] is True
    assert w.run("here", "--pr", "x", check=False).returncode == 4


def test_a_background_fix_after_one_run_here_opens_a_new_session(w):
    w.run("here", "--pr", "5")
    (w.sd / "pr-5-fix.status.json").write_text(json.dumps({"state": "fixed"}))
    out = w.spawn(5, extra=("--role", "fix"))
    assert "resumed" not in out and out["open"].startswith("claude attach ")
    assert w.state()["sessions"]["5:fix"]["runner"] == "claude"
    assert not (w.sd / "pr-5-fix.status.json").exists(), "the new session writes its own"


def test_removing_a_pr_takes_it_out_of_the_fix_role(w):
    fix_ready(w, finding(review="80"))
    w.run("hide", "--pr", "5")
    assert w.run("wait", "--once").stdout == ""
    assert w.state()["fix_prs"] == {"5": "off"}


def test_asking_for_a_review_of_ones_own_pr_enrolls_it_in_the_fix_role(w):
    fix_ready(w)
    (w.home / "account.txt").write_text("Dev\n")
    w.triggers(dict(trig("41", "2026-01-01T00:00:05Z", pr=6), pr_author="dev", user="dev"),
               dict(trig("42", "2026-01-01T00:00:06Z", pr=7), pr_author="other", user="dev"))
    ev = w.jsonl("wait", "--once", "--fix-prs", "5")
    assert [e["comment_id"] for e in ev] == ["41", "42"] and "pr_author" not in ev[0]
    assert w.state()["fix_prs"] == {"6": "enrolled"}
    w.run("wait", "--once", "--fix-prs", "5")
    assert last_triggers_call(w).endswith("--fix-prs 5,6")


def test_a_review_only_watcher_moves_its_cursor_without_trigger_events_for_fix(w):
    fix_ready(w, finding())
    w.triggers(trig("41", "2026-01-01T00:00:05Z"))
    ev = w.jsonl("wait", "--once", "--roles", "fix")
    assert [e["event"] for e in ev] == ["findings"], "the fix role alone takes no review request"
    assert w.state()["cursors"]["fix"]["cursor"] == "2026-01-01T00:00:05Z"


def test_fix_now_is_delivered_by_the_running_wait_with_the_pending_findings(w):
    fix_ready(w, finding())
    w.run("wait", "--once")
    assert w.jsonl("fix-now", "--pr", "5") == [{"pr": 5, "fix_now": True}]
    ev = w.jsonl("wait", "--once")
    assert ev == [{"event": "fix_now", "repo": "o/r", "pr": 5, "url": "https://github.com/o/r/pull/5",
                   "head_branch": "feat/x", "review_id": "70", "counts": {"🟠": 2, "🔵": 4}, "comment_id": "10", "thread_id": None,
                   "user": "rev"}]
    assert w.run("wait", "--once").stdout == "", "a click is delivered once"
    assert w.run("fix-now", "--pr", "5;id", check=False).returncode == 4


def test_a_fix_now_click_while_that_fix_session_runs_opens_nothing(w):
    """A second click (or the toast's after the menu bar's) must not queue a second fix run."""
    fix_ready(w, finding())
    w.run("wait", "--once")
    w.run("fix-now", "--pr", "5")
    w.run("fix-now", "--pr", "5")
    assert [e["event"] for e in w.jsonl("wait", "--once")] == ["fix_now"], "two clicks before delivery are one"
    w.spawn(5, extra=("--role", "fix"))
    w.run("wait", "--once")
    w.run("fix-now", "--pr", "5")
    assert w.run("wait", "--once").stdout == ""
    assert not (w.sd / "fix_now" / "5").exists(), "the dropped click stays pending and wakes every poll"


def test_a_dropped_click_and_a_delivered_one_in_one_poll_are_told_apart(w):
    """Each click is matched to its own PR: the one whose fix session runs is used up, the other
    delivered once."""
    fix_ready(w, finding(), finding(pr=6, review="71"))
    w.run("wait", "--once")
    w.spawn(5, extra=("--role", "fix"))
    w.run("wait", "--once")
    w.run("fix-now", "--pr", "5")
    w.run("fix-now", "--pr", "6")
    assert [(e["event"], e["pr"]) for e in w.jsonl("wait", "--once")] == [("fix_now", 6)]
    assert not (w.sd / "fix_now" / "5").exists() and not (w.sd / "fix_now" / "6").exists()
    assert w.run("wait", "--once").stdout == ""


def test_a_fix_now_click_wakes_a_sleeping_wait(w):
    fix_ready(w)
    (w.watch).mkdir(parents=True, exist_ok=True)
    p = _long_wait(w)
    time.sleep(1)
    w.run("fix-now", "--pr", "5")
    out, _ = p.communicate(timeout=20)
    assert json.loads(out.splitlines()[0])["event"] == "fix_now"


def test_a_pr_holds_a_review_and_a_fix_session_side_by_side(w):
    fix_ready(w)
    rv = w.spawn(5)
    fx = w.jsonl("spawn", "--runner", "claude", "--pr", "5", "--role", "fix", "--name", "fix o/r#5",
                 "--prompt-file", w.prompt("/open-pr:fix u", "pf.txt"))[0]
    assert fx["role"] == "fix" and fx["id"] != rv["id"] and "resumed" not in fx
    assert sorted(w.state()["sessions"]) == ["5:fix", "5:review"]
    paths = dict(l.split("=", 1) for l in w.run("paths", "--pr", "5", "--role", "fix").stdout.splitlines())
    assert paths["status_file"] == str(w.sd / "pr-5-fix.status.json")
    w.claude_set(fx["id"], "done")
    (w.sd / "pr-5-fix.status.json").write_text(json.dumps({"state": "fixed", "counts": {"fixed": 2}}))
    rows = {r["role"]: r["state"] for r in w.jsonl("status", "--pr", "5")}
    assert rows == {"review": "working", "fix": "fixed"}
    assert [e for e in w.jsonl("wait", "--once") if e["event"] == "session"] == \
        [{"event": "session", "repo": "o/r", "pr": 5, "role": "fix", "state": "fixed", "open": f"claude attach {fx['id']}"}]
    assert w.jsonl("forget", "--pr", "5", "--role", "fix") == [{"pr": 5, "role": "fix", "forgotten": True}]
    assert list(w.state()["sessions"]) == ["5:review"]


# ------------------------------------------- a review and a fix watcher ----
# One machine runs `/open-pr:watch review` in one tab and `/open-pr:watch fix` in another: one
# `wait` per repo and role.

def test_a_review_wait_and_a_fix_wait_watch_one_repo_side_by_side(w):
    rv = _long_wait(w, "review")
    try:
        assert w.run("wait", "--once", "--roles", "fix", check=False).returncode == 0
        for roles in ("review", "review,fix"):
            r = w.run("wait", "--once", "--roles", roles, check=False)
            assert r.returncode == 10 and f"for review on this machine (wait pid {rv.pid})" in r.stderr, roles
        fx = _long_wait(w, "fix")
        r = w.run("wait", "--once", "--roles", "fix", check=False)
        assert r.returncode == 10 and f"for fix on this machine (wait pid {fx.pid})" in r.stderr
        assert rv.poll() is None and fx.poll() is None
    finally:
        for p in w.children:
            p.kill(); p.wait()
    (w.sd / "wait-fix.pid").write_text("999999\n")
    assert w.run("wait", "--once", "--roles", "fix", check=False).returncode == 0, "a dead holder frees its role"


def backlog(w, *rows):
    (w.home / "backlog.jsonl").write_text("".join(json.dumps(dict(r, backlog=True, superseded=[])) + "\n" for r in rows))


def backlog_calls(w):
    return sum(1 for l in (w.home / "open-pr.calls").read_text().splitlines()
               if l.startswith("triggers") and "--backlog" in l.split())


def test_a_request_made_before_the_first_start_is_delivered_as_backlog(w):
    """The reviewer starts watching a day after the dev asked: the PR still holds the request."""
    backlog(w, trig("5", "2025-01-01T00:00:00Z"))
    (w.home / "mark.txt").write_text("2025-01-02T00:00:00Z")
    ev = w.jsonl("wait", "--once", "--backlog")
    assert ev == [{"event": "trigger", "repo": "o/r", **trig("5", "2025-01-01T00:00:00Z"), "backlog": True, "superseded": []}]
    assert w.state()["cursor"] == "2025-01-02T00:00:00Z", "a first run starts at the newest comment read, not at now"
    assert w.run("wait", "--once").stdout == "", "without --backlog the pass does not run"
    assert backlog_calls(w) == 1


def test_a_backlog_pass_with_nothing_pending_keeps_an_existing_cursor(w):
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    assert w.run("wait", "--once", "--backlog").stdout == ""
    assert w.state()["cursor"] == "2026-01-01T00:00:00Z", "the poll, not the pass, moves a cursor that exists"


def test_a_skipped_backlog_trigger_is_never_delivered_again_but_a_newer_one_is(w):
    backlog(w, trig("5", "2025-01-01T00:00:00Z"))
    assert w.jsonl("skip", "--comment-ids", "5,3") == [{"skipped": ["5", "3"]}]
    assert w.run("wait", "--once", "--backlog").stdout == "", "skipped: not asked again on a restart"
    w.triggers(trig("3", "2026-01-01T00:00:04Z"), trig("5", "2026-01-01T00:00:05Z"), trig("6", "2026-01-01T00:00:06Z"))
    w.put_state(dict(w.state(), cursor="2026-01-01T00:00:00Z", seen=[]))
    assert [e["comment_id"] for e in w.jsonl("wait", "--once")] == ["6"], "a stale cursor never brings it back"
    backlog(w, trig("7", "2026-01-02T00:00:00Z"))
    assert [e["comment_id"] for e in w.jsonl("wait", "--once", "--backlog")] == ["7"], "a newer request on that PR"
    assert w.state()["skipped"] == ["3", "5"]
    for bad in ("5;id", "", "a,1"):
        assert w.run("skip", "--comment-ids", bad, check=False).returncode in (1, 4), bad


def test_the_backlog_pass_runs_once_per_wait_not_per_poll(w):
    w.settings(poll_interval_seconds=1)
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    proc = subprocess.Popen(["sh", str(w.bin / "open-pr-watch.sh"), "wait", "--backlog"], cwd=w.repo, env=w.env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    w.children.append(proc)
    try:
        end = time.time() + 20
        calls = w.home / "open-pr.calls"
        while time.time() < end and (not calls.exists() or sum(1 for l in calls.read_text().splitlines()
                                                                if l.startswith("triggers")) < 4):
            time.sleep(0.2)
    finally:
        proc.kill(); proc.wait()
    polls = sum(1 for l in (w.home / "open-pr.calls").read_text().splitlines() if l.startswith("triggers"))
    assert polls >= 4 and backlog_calls(w) == 1


def test_a_failed_backlog_pass_is_tried_again_before_the_next_poll(w):
    w.settings(poll_interval_seconds=1)
    w.put_state({"cursor": "2026-01-01T00:00:00Z", "seen": [], "sessions": {}, "queue": []})
    (w.home / "triggers.rc").write_text("1\n")
    backlog(w, trig("5", "2025-01-01T00:00:00Z"))
    proc = subprocess.Popen(["sh", str(w.bin / "open-pr-watch.sh"), "wait", "--backlog"], cwd=w.repo, env=w.env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    w.children.append(proc)
    out, err = proc.communicate(timeout=30)
    assert proc.returncode == 0 and [json.loads(l)["comment_id"] for l in out.splitlines()] == ["5"]
    assert "backlog pass failed (exit 1)" in err and backlog_calls(w) == 2


def test_a_fix_only_wait_runs_no_backlog_pass(w):
    backlog(w, trig("5", "2025-01-01T00:00:00Z"))
    assert w.run("wait", "--once", "--backlog", "--roles", "fix").stdout == ""
    assert backlog_calls(w) == 0, "it delivers no trigger"


def test_each_role_wait_keeps_its_own_cursor(w):
    fix_ready(w)
    w.triggers(trig("61", "2026-01-01T00:00:05Z"))
    assert w.run("wait", "--once", "--roles", "fix").stdout == ""
    ev = w.jsonl("wait", "--once", "--roles", "review")
    assert [e["comment_id"] for e in ev] == ["61"], "the fix wait moving its cursor took the trigger"
    st = w.state()
    assert st["cursors"]["review"]["cursor"] == st["cursors"]["fix"]["cursor"] == "2026-01-01T00:00:05Z"
    assert st["cursor"] == "2026-01-01T00:00:00Z", "the both-roles cursor is a third one"
    del st["cursors"]["fix"]
    w.put_state(st)
    assert w.run("wait", "--once", "--roles", "fix").stdout == ""
    assert w.state()["cursors"]["fix"]["cursor"] > "2026-01-01T00:00:05Z", "a new role set starts at now"


def test_a_session_change_reaches_the_wait_of_its_role_only(w):
    fix_ready(w)
    rv = w.spawn(5)
    fx = w.spawn(6, extra=("--role", "fix"))
    w.claude_set(rv["id"], "done")
    w.status_file(5, state="posted")
    w.claude_set(fx["id"], "done")
    (w.sd / "pr-6-fix.status.json").write_text(json.dumps({"state": "fixed"}))
    ev = w.jsonl("wait", "--once", "--roles", "fix")
    assert [(e["pr"], e["state"]) for e in ev] == [(6, "fixed")], "the fix wait took the review's change"
    assert w.state()["sessions"]["5:review"]["last_state"] == "working"
    ev = w.jsonl("wait", "--once", "--roles", "review")
    assert [(e["pr"], e["state"]) for e in ev] == [(5, "posted")]
    assert w.run("wait", "--once", "--roles", "fix").stdout == ""


def test_a_queued_session_is_ready_for_and_popped_by_the_wait_of_its_role(w):
    fix_ready(w)
    w.settings(max_concurrent=1)
    rv = w.spawn(1)
    assert w.spawn(2, extra=("--role", "fix"))["queued"] is True, "both roles share the slots"
    w.claude_set(rv["id"], "done")
    w.status_file(1, state="posted")
    ev = w.jsonl("wait", "--once", "--roles", "review")
    assert [e["event"] for e in ev] == ["session"], "a fix session's turn told to the review wait"
    assert w.run("next", "--roles", "review").stdout == ""
    assert [e["event"] for e in w.jsonl("wait", "--once", "--roles", "fix")] == ["ready"]
    assert w.jsonl("next", "--roles", "fix")[0]["role"] == "fix"


def test_fix_now_reaches_only_a_wait_serving_fix(w):
    fix_ready(w, finding())
    w.run("wait", "--once", "--roles", "fix")
    w.run("fix-now", "--pr", "5")
    assert w.run("wait", "--once", "--roles", "review").stdout == ""
    assert (w.sd / "fix_now" / "5").exists(), "the review wait consumed the click"
    assert [e["event"] for e in w.jsonl("wait", "--once", "--roles", "fix")] == ["fix_now"]


def test_each_watcher_keeps_its_own_record_heartbeat_and_stop_file(w):
    w.env = watcher_env(w, TERM_PROGRAM="iTerm.app", ITERM_SESSION_ID="w0t0p1:AA")
    w.run("wait", "--once", "--roles", "review")
    w.env = watcher_env(w, TERM_PROGRAM="iTerm.app", ITERM_SESSION_ID="w0t0p2:BB")
    w.run("wait", "--once", "--roles", "fix")
    tab = lambda f: json.loads((w.sd / f).read_text())["term_session"]
    assert (tab("watcher-review.json"), tab("watcher-fix.json")) == ("w0t0p1:AA", "w0t0p2:BB")
    assert (w.sd / "heartbeat-review").exists() and (w.sd / "heartbeat-fix").exists()
    assert not (w.sd / "watcher.json").exists()
    # the toast's `watcher` focus goes to the tab of the event's role
    w.run("notify", "--event", "error", "--text-file", w.prompt("x"), "--role", "fix", "--focus", "watcher")
    assert w.recorded("osascript")["argv"][14] == "w0t0p2:BB"
    w.run("wait", "--once")
    assert sorted(f.name for f in w.sd.glob("watcher*.json")) == ["watcher.json"], \
        "a wait serving both roles replaces the records of the waits it now stands for"
    assert not (w.sd / "heartbeat-fix").exists()


def test_stop_watcher_stops_only_the_wait_it_names(w):
    rv = _long_wait(w, "review")
    fx = _long_wait(w, "fix")
    try:
        (w.sd / "stop-fix").write_text("")
        _, err = fx.communicate(timeout=20)
        assert fx.returncode == 11 and "stopped from the menu bar" in err
        time.sleep(1)
        assert rv.poll() is None, "the review wait stopped with the fix one"
        assert not (w.sd / "stop-fix").exists()
    finally:
        for p in w.children:
            if p.poll() is None:
                p.kill(); p.wait()


MENUBAR = REPO / "src" / "bin" / "open-pr-menubar.js"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_menu_bar_lists_each_role_watcher_with_the_rows_of_its_role(w):
    w.put_state({"cursor": None, "seen": [], "queue": [], "titles": {"5": "Add retry\nto sync"}, "sessions": {
        "5:review": {"pr": 5, "role": "review", "repo": "o/r", "last_state": "working"},
        "6:fix": {"pr": 6, "role": "fix", "repo": "o/r", "last_state": "working"}}})
    for sfx, ts in (("-review", "w0t0p1:AA"), ("-fix", "w0t0p2:BB")):
        (w.sd / f"watcher{sfx}.json").write_text(json.dumps(
            {"pid": 1, "cwd": "/x", "term": "iTerm.app", "term_session": ts, "tty": "", "session_id": ""}))
        (w.sd / f"heartbeat{sfx}").write_text("")
    got = _menubar_js(w, "return JSON.stringify(scan().repos.map(function (g) { return [g.name, g.watchers.map(function (x) {"
                         " return [x.key, x.rows.map(function (r) { return r.title; })]; })]; }));")
    assert got == [["r", [["s:w0t0p1:AA-review", ["#5 Add retry to sync"]], ["s:w0t0p2:BB-fix", ["#6"]]]]], \
        "one group for the repo; review, then fix; a PR's title from state, else its number"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_menu_bar_groups_by_repo_and_a_watcher_of_several_repos_sits_in_each(w):
    tab = {"pid": 1, "cwd": "/x/tms", "term": "iTerm.app", "term_session": "w0t0p1:AA", "tty": "", "session_id": ""}
    for repo in ("zeta", "Alpha"):
        d = w.home / "data" / repo / "watch"
        d.mkdir(parents=True, exist_ok=True)
        (d / "watcher.json").write_text(json.dumps(tab))
        (d / "heartbeat").write_text("")
    got = _menubar_js(w, "return JSON.stringify(scan().repos.map(function (g) {"
                         " return [g.name, g.folders, g.watchers.map(function (x) { return [x.key, x.only, x.dirs.length]; })]; }));")
    assert got == [["Alpha", ["tms"], [["s:w0t0p1:AA", False, 1]]], ["zeta", ["tms"], [["s:w0t0p1:AA", False, 1]]]], \
        "sorted by name; Stop there leaves the watcher's session running for its other repo"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_done_line_never_outranks_a_session_still_working(w):
    """An answered question, the session reviewing on: the row says reviewing, not posted."""
    old = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 120))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        "143:review": {"pr": 143, "role": "review", "repo": "o/r", "last_state": "working", "last_state_at": old}}})
    (w.sd / "watcher.json").write_text(json.dumps({"pid": 1, "cwd": "/x", "term": "iTerm.app", "term_session": "w0t0p1:AA"}))
    (w.sd / "heartbeat").write_text("")
    (w.sd / "feed.jsonl").write_text(json.dumps({"at": now, "repo": "o/r", "pr": 143, "role": "review",
                                                 "event": "posted", "summary": "answered, reviewing on"}) + "\n")
    got = _menubar_js(w, "return JSON.stringify(scan().repos[0].watchers[0].rows.map(function (r) { return r.kind; }));")
    assert got == ["working"]


def _menubar_js(w, body, script=False):
    """The menu bar's own functions run headless: its run() (the status item, the app run) replaced
    by `body`. script: it runs the sandbox's open-pr-watch.sh (beside the fake open-pr.sh), as the
    real one is handed its own."""
    ws = json.dumps(str(w.bin / "open-pr-watch.sh")) if script else "''"
    js = MENUBAR.read_text().replace("function run(argv) {", "function runApp(argv) {", 1) + (
        f"\nfunction run() {{ dataDirs = [{json.dumps(str(w.home / 'data'))}]; fresh = 2700; watchScript = {ws}; {body} }}")
    f = w.home / "menubar-headless.js"
    f.write_text(js)
    out = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", str(f)], capture_output=True, text=True,
                         timeout=30, env=w.env)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# `ps -A -o pid=,ppid=,tty=`: a watcher's wait (400) under `claude` in a tab (ttys007), and one in a
# background session (520) under a daemon's own pty (ttys002) that inherited the tab's ITERM_SESSION_ID.
PS = "1 0 ??\n200 1 ttys007\n300 200 ??\n400 300 ??\n500 200 ??\n510 500 ttys002\n520 510 ??\n"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_click_focuses_the_watchers_tab_only_while_its_wait_still_runs_there(w):
    """liveTab: what FOCUS must match — the tab id and the tty the wait runs on — or null (claude attach)."""
    it = lambda pids: {"term": "iTerm.app", "term_session": "w0t1p2:AB-12", "tty": "ttys007", "pids": pids}
    ap = lambda tty, pids: {"term": "Apple_Terminal", "term_session": "", "tty": tty, "pids": pids}
    cases = [it([400]), it([520]), it([999]), it([]), ap("ttys007", [400]), ap("ttys002", [400]),
             ap("ttys007", [999, 400])]
    got = _menubar_js(w, f"return JSON.stringify([{json.dumps(cases)}.map(function (c) {{ return liveTab(c, {json.dumps(PS)}); }}),"
                         f" liveTab({json.dumps(it([400]))}, null)]);")
    assert got == [[["AB-12", "/dev/ttys007"],
                    ["AB-12", "/dev/ttys002"],   # iTerm answers with tab AB-12's own tty: not ttys002 ⇒ not found
                    None, None,
                    ["/dev/ttys007", "/dev/ttys007"],
                    None,                         # ttys002 was reused by another tab: the wait runs on ttys007
                    ["/dev/ttys007", "/dev/ttys007"]],
                   None]


# A watcher between waits: its `claude` (200) runs in the tab (ttys007), no wait. 610: a `claude` on ttys002.
PS_HOST = "1 0 ??\n200 1 ttys007\n600 1 ttys002\n610 600 ttys002\n"
SID = "269289ac-1f2e-4d3c-9b8a-0123456789ab"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_watcher_between_waits_keeps_its_tab_live_by_its_claude(w):
    it = lambda hosts: {"term": "iTerm.app", "term_session": "w0t1p2:AB-12", "tty": "ttys007", "pids": [400], "hosts": hosts}
    ap = lambda hosts: {"term": "Apple_Terminal", "term_session": "", "tty": "ttys007", "pids": [400], "hosts": hosts}
    cases = [it([200]), it([610]), it([999]), it([]), ap([200]), ap([610])]
    got = _menubar_js(w, f"return JSON.stringify({json.dumps(cases)}.map(function (c) {{ return liveTab(c, {json.dumps(PS_HOST)}); }}));")
    assert got == [["AB-12", "/dev/ttys007"],
                   ["AB-12", "/dev/ttys002"],   # iTerm answers with tab AB-12's own tty: not ttys002 ⇒ not found
                   None, None,
                   ["/dev/ttys007", "/dev/ttys007"],
                   None]                        # its `claude` runs in another tab: not this one


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_watcher_session_whose_tab_is_gone_is_attached_resumed_or_left_alone(w):
    """Never `--resume` while the watcher's `claude` runs: that would be a second copy of its session."""
    job = lambda **k: json.dumps([dict({"id": "269289ac", "sessionId": SID, "kind": "background"}, **k)])
    cases = [
        ([200], job(), ""),                                   # its claude runs (in some tab)
        ([999], job(), "claude attach 269289ac"),             # gone from the tab, a background job now
        ([999], job(id="abcdef12"), "claude attach abcdef12"),
        ([999], job(id="x; id"), "claude attach 269289ac"),
        ([999], "[]", f"claude --resume {SID}"),              # nothing runs it
        ([999], job(sessionId="other"), f"claude --resume {SID}"),
        ([999], job(kind="interactive"), f"claude --resume {SID}"),
        # a listing that cannot be read may hide the job: attach (it only fails), never a second copy
        ([999], "not json", "claude attach 269289ac"),
        ([999], '{"id": 1}', "claude attach 269289ac"),
        ([999], "Update available\n[]", "claude attach 269289ac"),
        ([999], "[1, null]", f"claude --resume {SID}"),
        ([999], None, "claude attach 269289ac"),              # no listing: never resume blind
        ([], "[]", "claude attach 269289ac"),                 # no host recorded (an older record)
    ]
    got = _menubar_js(w, "var calls = 0; return JSON.stringify(" + json.dumps(cases) + ".map(function (c) {"
                         " return reopen({ session_id: " + json.dumps(SID) + ", hosts: c[0] }, " + json.dumps(PS_HOST) + ","
                         " function () { calls++; return c[1]; }); }).concat([calls,"
                         " reopen({ session_id: 'ABC; id', hosts: [999] }, '', function () { return '[]'; }),"
                         " reopen({ session_id: " + json.dumps(SID) + ", hosts: [999] }, null, function () { return '[]'; })]));")
    assert got[:len(cases)] == [c[2] for c in cases]
    assert got[len(cases)] == len(cases) - 2, "no listing read while the host runs or when none is recorded"
    assert got[len(cases) + 1:] == ["", ""], "a session id outside its shape; ps unreadable ⇒ the host may run"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_click_on_a_watcher_between_waits_focuses_its_tab_and_starts_nothing(w):
    go = {"term": "iTerm.app", "term_session": "w0t1p2:AB-12", "tty": "ttys007", "session_id": SID, "pids": [400], "hosts": [200]}
    run = lambda answer, hosts, agents: _menubar_js(w, """var log = [];
        spawn = function (p, a) { log.push(['spawn', p]); return true; };
        openIn = function (t, c) { log.push(['openIn', c]); return true; };
        output = function (p, a) { log.push(['output', p, a[0]]);
            return p === '/bin/ps' ? """ + json.dumps(PS_HOST) + """ : p === '/usr/bin/osascript' ? """ + json.dumps(answer) +
            """ : """ + json.dumps(agents) + """; };
        goToTab(""" + json.dumps(dict(go, hosts=hosts)) + """);
        return JSON.stringify(log);""")
    found = run("found", [200], "[]")
    assert ["output", "/usr/bin/osascript", "-e"] in found and not [x for x in found if x[0] == "openIn"]
    refused = run(None, [200], "[]")
    assert not [x for x in refused if x[0] == "openIn"], "a lookup still waiting on permission: the tab may be there"
    closed = run("", [200], "[]")
    assert not [x for x in closed if x[0] == "openIn"], "its claude still runs: no second copy"
    gone = run("", [999], "[]")
    assert ["openIn", f"claude --resume {SID}"] in gone
    assert ["output", "/usr/bin/env", "claude"] in gone


def test_the_toast_and_the_menu_bar_find_a_tab_and_draw_severity_marks_the_same_way():
    toast = (REPO / "src" / "bin" / "open-pr-toast.js").read_text()
    body = lambda src, name: re.search(rf"^function {name}\(.*?^\}}$", src, re.S | re.M).group(0)
    for name in ("tabId", "hostTty", "liveTab", "reopen", "smallMarks"):
        assert body(toast, name) == body(MENUBAR.read_text(), name), name
    for src in (toast, MENUBAR.read_text()):
        assert "'if (unique id of s) is (item 1 of argv) and (tty of s) is (item 2 of argv) then',\n" \
               "        'select t', 'select s', 'select w', 'activate', 'return \"found\"'," in src


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_menu_bar_shows_the_tightest_quota_and_warns_before_a_fast_poll(w):
    soon = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 1800))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    w.sd.mkdir(parents=True, exist_ok=True)
    (w.sd / "heartbeat").write_text("")
    (w.sd / "watcher.json").write_text(json.dumps({"pid": 1, "cwd": "/x"}))
    (w.sd / "quota.json").write_text(json.dumps(
        {"vendor": "github", "host": "github.com", "window": 3600, "measured": True, "limit": 5000,
         "remaining": 1200, "reset": soon, "near_limit": None, "calls": 3, "at": now}))
    got = _menubar_js(w, "var q = scan().quotas; return JSON.stringify("
                         "[gauge(q), estimate(q, 15), estimate(q, 180), estimate([], 15)]);")
    assert got[0] == {"ratio": 0.24, "text": "GitHub API 1,200/5,000", "level": "low"}
    assert got[1:] == ["  ≈720/h", "  ≈60/h", ""], "720/h is under half of 5000/h"
    (w.sd / "quota.json").write_text(json.dumps(
        {"vendor": "gitlab", "host": "gitlab.com", "window": 60, "limit": 10, "remaining": 0,
         "reset": None, "calls": 5, "at": now}))
    got = _menubar_js(w, "var q = scan().quotas; return JSON.stringify([gauge(q).level, estimate(q, 15)]);")
    assert got == ["critical", "  ≈1,200/h ⚠"], "a per-minute limit is converted to per hour (600/h)"


def test_wait_keeps_the_hosts_quota_per_role_set_even_when_rate_limited(w):
    fix_ready(w)
    w.run("wait", "--once")
    assert not (w.sd / "quota.json").exists(), "no quota read, nothing kept"
    (w.home / "quota.json").write_text(json.dumps({"vendor": "github", "limit": 5000, "remaining": 7, "calls": 3}))
    w.run("wait", "--once", "--roles", "fix")
    q = json.loads((w.sd / "quota-fix.json").read_text())
    assert (q["remaining"], q["host"]) == (7, "github.com") and q["at"].endswith("Z")
    (w.home / "triggers.rc").write_text("9\n")
    (w.home / "quota.json").write_text(json.dumps({"vendor": "github", "limit": 5000, "remaining": 0, "calls": 1}))
    w.run("wait", "--once", check=False)
    assert json.loads((w.sd / "quota.json").read_text())["remaining"] == 0


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_watcher_row_names_its_role_and_says_when_it_last_polled(w):
    w.sd.mkdir(parents=True, exist_ok=True)
    for sfx, cwd in (("-review", "/x/r"), ("-fix", "/x/tms")):
        (w.sd / f"watcher{sfx}.json").write_text(json.dumps(
            {"pid": 1, "cwd": cwd, "term": "iTerm.app", "term_session": "w0t0p" + sfx + ":A", "tty": "", "session_id": ""}))
        (w.sd / f"heartbeat{sfx}").write_text("")
    old = time.time() - 1500   # past 2 × the 600 s an idle repo may poll at
    os.utime(w.sd / "heartbeat-fix", (old, old))
    got = _menubar_js(w, "var g = scan().repos[0]; return JSON.stringify([g.folders, g.watchers.map(function (x) {"
                         " return [x.sfx, watcherLine(x)]; })]);")
    assert got == [["tms"], [["-review", [["Review", "role"], [" · iTerm · polled just now", ""]]],
                             ["-fix", [["Fix", "role"], [" · iTerm · ", ""], ["no poll for 25m — check the watcher tab", "warn"]]]]], \
        "a workspace folder goes to the repo's tooltip, not the row"


def _watched(w, repo_dir=True):
    w.sd.mkdir(parents=True, exist_ok=True)
    (w.sd / "heartbeat").write_text("")
    (w.sd / "watcher.json").write_text(json.dumps(
        {"pid": 1, "cwd": "/x", "repo_dir": str(w.repo) if repo_dir else "", "remote": "origin"}))


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
@pytest.mark.parametrize("review, next_in, want", [
    ({"doctored": True, "doctored_at": "2026-07-13T10:00:00Z", "doctor_schedule": "1 months"}, 3 * 86400 - 60,
     "Doctor: Jul 13, 2026 · next in 3 days"),
    ({"doctored": True, "doctored_at": "2026-07-13T10:00:00Z", "doctor_schedule": "1 months"}, -60,
     "Doctor: Jul 13, 2026 · due now"),
    ({"doctored": True, "doctored_at": "2026-07-13T10:00:00Z", "doctor_schedule": "never"}, None,
     "Doctor: Jul 13, 2026 · not scheduled"),
    ({"bootstrapped": True}, None, "Doctor: never run"),
])
def test_the_menu_bar_reads_each_repos_settings_and_says_when_its_doctor_runs(w, review, next_in, want):
    _watched(w)
    at = None if next_in is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + next_in))
    (w.home / "settings.json").write_text(json.dumps(
        {"review": review, "watch": {"max_concurrent": 2}, "doctor_next_at": at}))
    got = _menubar_js(w, "return JSON.stringify(scan().repos.map(function (g) {"
                         " return g.settings.map(function (r) { return [r.name, r.doctor, r.conf.watch.max_concurrent]; }); }));",
                      script=True)
    assert got == [[["r", want, 2]]]
    calls = (w.home / "open-pr.calls").read_text().splitlines()
    assert f"settings --repo r --repo-dir {w.repo.resolve()}" in calls, "read through open-pr.sh settings"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_menu_bar_offers_no_settings_for_a_repo_it_cannot_name(w):
    _watched(w, repo_dir=False)
    (w.home / "settings.json").write_text(json.dumps({"review": {}, "watch": {}}))
    assert _menubar_js(w, "return JSON.stringify(scan().repos[0].settings);", script=True) == []


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_settings_click_hands_open_pr_watch_only_a_listed_key_and_value(w):
    ok = {"repo_dir": str(w.repo), "remote": "origin"}
    cases = [dict(ok, key="watch.max_concurrent", value="8"), dict(ok, key="watch.notify.posted", value="false"),
             dict(ok, key="review.doctor_schedule", value="2 weeks"), dict(ok, key="watch.trigger", value="@me"),
             dict(ok, key="watch.max_concurrent", value="7"), dict(ok, key="review.many_files_threshold", value="9"),
             dict(ok, key="watch.notify.bogus", value="true"), dict(ok, key="watch.trigger", value="@alice"),
             dict(ok, key="watch.notify.posted", value="true; rm -rf ~"),
             dict(ok, remote="a b", key="review.post_lgtm", value="false"),
             dict(ok, repo_dir="/no/such/dir", key="review.post_lgtm", value="false")]
    got = _menubar_js(w, f"return JSON.stringify({json.dumps(cases)}.map(settingArgs));", script=True)
    base = [str(w.bin / "open-pr-watch.sh"), "settings", "--repo-dir", str(w.repo), "--remote", "origin", "--set"]
    assert got[:4] == [base + ["watch.max_concurrent", "--value", "8"], base + ["watch.notify.posted", "--value", "false"],
                       base + ["review.doctor_schedule", "--value", "2 weeks"], base + ["watch.trigger", "--value", "@me"]]
    assert got[4:] == [None] * 7, "a value the menu does not offer, an unlisted key, or a bad repo reached argv"


# The settings panel's controls, from the global `controls`: [key, state] — a pick's state is its
# segment labels with the selected one in [brackets] and a disabled one in (parens), a checkbox's
# its state (-1 mixed).
PANEL_DUMP = """var dump = function () { return Object.keys(controls).map(function (h) { var c = controls[h], v = c.view;
    if (!c.key) return null;
    if (!c.values) return [c.key, Number(v.state)];
    var a = []; for (var i = 0; i < v.segmentCount; i++) { var l = ObjC.unwrap(v.labelForSegment(i));
        l = v.isEnabledForSegment(i) ? l : '(' + l + ')'; a.push(v.isSelectedForSegment(i) ? '[' + l + ']' : l); }
    return [c.key, a.join(' ')]; }).filter(Boolean); };"""


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_settings_panel_shows_each_current_value(w):
    _watched(w)
    (w.home / "settings.json").write_text(json.dumps({
        "review": {"doctored": False, "post_lgtm": True, "auto_submit_review": False, "doctor_schedule": "7 days"},
        "watch": {"max_concurrent": 5, "poll_interval_seconds": 180, "trigger": "@alice",
                  "notify": {e: e != "posted" for e in ("review_started", "question", "draft_ready", "posted",
                                                       "re_review", "findings", "error")}}}))
    got = _menubar_js(w, PANEL_DUMP + """var x = scan().repos[0].settings[0], p = settingsPanel(x, []);
        return JSON.stringify(dump());""", script=True)
    by = dict(got)
    assert by["watch.max_concurrent"] == "1 2 3 [5] 8 10"
    assert by["watch.poll_interval_seconds"] == "1m 2m [3m] 5m 10m"
    assert by["watch.trigger"] == "/open-pr @me [(@alice)]", "a typed login shows, unchanged and disabled"
    assert by["review.doctor_schedule"] == "1w 2w 1m 3m Never [(7 days)]"
    assert (by["watch.notify.posted"], by["watch.notify.question"]) == (0, 1)
    assert (by["review.post_lgtm"], by["review.auto_submit_review"]) == (1, 0)
    assert by["review.review_ci_status"] == -1, "unset: decided per review by its CI checks"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_panel_control_writes_its_key_and_shows_the_value_read_back(w):
    _watched(w)
    (w.home / "settings.json").write_text(json.dumps({"review": {"post_lgtm": True}, "watch": {"max_concurrent": 5}}))
    got = _menubar_js(w, PANEL_DUMP + """var x = scan().repos[0].settings[0], p = settingsPanel(x, []);
        var by = function (k) { return Object.keys(controls).map(function (h) { return controls[h]; })
            .filter(function (c) { return c.key === k; })[0].view; };
        var seg = by('watch.max_concurrent'); seg.setSelectedSegment(4); setSetting(seg);
        setSetting(by('review.post_lgtm'));
        return JSON.stringify(dump());""", script=True)
    calls = [l for l in (w.home / "open-pr.calls").read_text().splitlines() if "--set" in l]
    base = f"settings --repo r --repo-dir {w.repo.resolve()} --set"
    assert calls == [f"{base} watch.max_concurrent --value 8", f"{base} review.post_lgtm --value false"]
    assert dict(got)["watch.max_concurrent"] == "1 2 3 [5] 8 10", "the panel shows the file, which the fake left as it was"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_gear_shows_a_repos_settings_inline_under_its_row_and_hides_them(w):
    _watched(w)
    (w.home / "settings.json").write_text(json.dumps({"review": {}, "watch": {"max_concurrent": 5}}))
    # run() is left out: the header icon it draws is drawn here
    got = _menubar_js(w, PANEL_DUMP + """icons.header = mothImage(28, false);
        var m = build(scan()), titles = function () { var a = [];
            for (var i = 0; i < m.numberOfItems; i++) a.push(ObjC.unwrap(m.itemAtIndex(i).title)); return a; };
        var row = m.itemArray.js.filter(function (mi) { return !mi.view.isNil() && rowParts[mi.view.hash]; })[0];
        var gear = rowParts[row.view.hash].gear, before = titles();
        toggleSettings(gear.button);
        var open = titles(), pressed = !!gear.pressed, shown = dump();
        toggleSettings(gear.button);
        return JSON.stringify({ submenu: !row.submenu.isNil(), before: before, open: open, after: titles(),
            pressed: pressed, released: !gear.pressed, shown: shown });""", script=True)
    at = got["before"].index("r")
    assert not got["submenu"], "hovering the row opens nothing"
    assert got["open"] == got["before"][:at + 1] + ["r"] + got["before"][at + 1:], "the panel sits right under its row"
    assert dict(got["shown"])["watch.max_concurrent"] == "1 2 3 [5] 8 10"
    assert got["after"] == got["before"] and got["pressed"] and got["released"]


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_header_says_how_often_the_watched_repos_poll(w):
    _watched(w)
    (w.home / "data" / "r" / "settings.json").write_text(json.dumps({"watch": {"poll_interval_seconds": 300}}))
    got = _menubar_js(w, "return JSON.stringify([scan().polls, pollSpan([]), pollSpan([180]), pollSpan([60, 300, 180]),"
                         " pollSpan([30, 300])]);")
    assert got == [[300], "", "every 3m", "every 1–5m", "every 30s–5m"]


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_apply_to_all_writes_the_offered_interval_once_to_each_repo_it_can_name(w):
    ok = {"repo_dir": str(w.repo), "remote": "origin"}
    s = {"repos": [{"settings": [{"repo": "a", "arg": ok}, {"repo": "b", "arg": dict(ok, remote="")}]},
                      {"settings": [{"repo": "a", "arg": ok}, {"repo": "c", "arg": dict(ok, repo_dir="/no/such/dir")}]}]}
    got = _menubar_js(w, f"var s = {json.dumps(s)}; return JSON.stringify([applyArgs(s, 120), applyArgs(s, 45)]);", script=True)
    tail = ["settings", "--repo-dir", str(w.repo)]
    assert got[0] == [[str(w.bin / "open-pr-watch.sh")] + tail + ["--remote", "origin", "--set", "watch.poll_interval_seconds", "--value", "120"],
                      [str(w.bin / "open-pr-watch.sh")] + tail + ["--set", "watch.poll_interval_seconds", "--value", "120"]]
    assert got[1] == [], "a value the Poll control does not offer reaches no repo"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_apply_to_all_in_a_panel_writes_its_interval_and_shows_it_read_back(w):
    _watched(w)
    (w.home / "settings.json").write_text(json.dumps({"review": {}, "watch": {"poll_interval_seconds": 300}}))
    got = _menubar_js(w, PANEL_DUMP + """shown = scan(); var p = settingsPanel(shown.repos[0].settings[0], []);
        var b = Object.keys(controls).map(function (h) { return controls[h]; }).filter(function (c) { return c.applyAll; })[0];
        applyAll({ hash: Object.keys(controls).filter(function (h) { return controls[h] === b; })[0] });
        return JSON.stringify([dump(), ObjC.unwrap(p.cost.stringValue)]);""", script=True)
    calls = [l for l in (w.home / "open-pr.calls").read_text().splitlines() if "--set" in l]
    assert calls == [f"settings --repo r --repo-dir {w.repo.resolve()} --set watch.poll_interval_seconds --value 300"]
    assert dict(got[0])["watch.poll_interval_seconds"] == "1m 2m 3m [5m] 10m"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_fix_run_here_shows_as_fixing_here_and_opens_the_watchers_tab(w):
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        "5:fix": {"pr": 5, "role": "fix", "runner": "here", "id": None, "open": None, "repo": "o/r",
                  "last_state": "working", "last_state_at": "2026-01-01T00:00:00Z"}}})
    (w.sd / "watcher.json").write_text(json.dumps({"pid": 1, "cwd": "/x", "term": "iTerm.app", "term_session": "w0t0p1:AA"}))
    (w.sd / "heartbeat").write_text("")
    got = _menubar_js(w, """icons.header = mothImage(28, false);
        var s = scan(), r = s.repos[0].watchers[0].rows[0], m = build(s);
        var mi = m.itemArray.js.filter(function (x) { return ObjC.unwrap(x.title) === '#5'; })[0], sub = [];
        for (var i = 0; i < mi.submenu.numberOfItems; i++) { var it = mi.submenu.itemAtIndex(i);
            sub.push([ObjC.unwrap(it.title), it.isEnabled && !it.target.isNil(), unwrapString(it.representedObject)]); }
        return JSON.stringify([r.kind, r.text.split(' · ')[0], sub]);""")
    assert got[0:2] == ["fixing_here", "Fixing here"]
    go = [x for x in got[2] if x[0] == "Open session in iTerm"]
    assert go and go[0][1] and json.loads(go[0][2])["term_session"] == "w0t0p1:AA"
    assert not [x for x in got[2] if x[0].startswith("Copy command")], "no session command to copy"


def _question_row(w, feed, state_at="2026-01-01T00:00:00Z"):
    """The #5 row's click (its represented object) and submenu titles, its newest feed line `feed`."""
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        "5:review": {"pr": 5, "role": "review", "runner": "claude", "repo": "o/r", "url": "https://github.com/o/r/pull/5",
                     "open": "claude attach abc12345", "last_state": "working", "last_state_at": state_at}}})
    (w.sd / "watcher.json").write_text(json.dumps({"pid": 1, "cwd": "/x", "term": "iTerm.app", "term_session": "w0t0p1:AA"}))
    (w.sd / "heartbeat").write_text("")
    (w.sd / "feed.jsonl").write_text(json.dumps(dict({"at": "2026-01-01T00:01:00Z", "repo": "o/r", "pr": 5, "role": "review",
                                                      "event": "question", "summary": "#5 needs you"}, **feed)) + "\n")
    got = _menubar_js(w, """icons.header = mothImage(28, false);
        var m = build(scan()), mi = m.itemArray.js.filter(function (x) { return ObjC.unwrap(x.title) === '#5'; })[0], sub = [];
        for (var i = 0; i < mi.submenu.numberOfItems; i++) sub.push(ObjC.unwrap(mi.submenu.itemAtIndex(i).title));
        return JSON.stringify([unwrapString(mi.representedObject), !mi.target.isNil(), sub]);""")
    return (json.loads(got[0]) if got[0].startswith("{") else got[0]), got[1], got[2]


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_row_for_the_watchers_own_question_answers_in_the_watchers_tab(w):
    click, live, sub = _question_row(w, {"focus": "watcher"})
    assert live and click["term_session"] == "w0t0p1:AA", "the row's click goes to the watcher's tab"
    assert sub[:2] == ["Answer in iTerm", "Open pull request"]


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_row_for_a_sessions_question_opens_that_session(w):
    click, live, sub = _question_row(w, {"focus": "session"})
    assert live and click == {"open": "claude attach abc12345", "term": "iTerm.app"}
    assert "Answer in iTerm" not in sub and "Open session in iTerm" in sub


@pytest.mark.parametrize("feed", [{}, {"focus": "pr"}, {"focus": "tab"}, {"focus": 3}])
@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_question_row_without_a_known_focus_keeps_the_pull_request_click(w, feed):
    """An older feed line has no focus: its row stays as it was."""
    click, _, sub = _question_row(w, feed)
    assert click == "https://github.com/o/r/pull/5" and sub[0] == "Open pull request"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_question_the_session_moved_past_offers_no_answer(w):
    click, _, sub = _question_row(w, {"focus": "watcher"}, state_at="2026-01-01T00:02:00Z")
    assert click == "https://github.com/o/r/pull/5" and "Answer in iTerm" not in sub


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_show_settings_file_reveals_only_a_settings_file_in_a_data_dir(w):
    data = w.home / "data"
    (data / "r").mkdir(parents=True, exist_ok=True)
    (data / "r" / "settings.json").write_text("{}")
    (data / "r" / "other.json").write_text("{}")
    (data / "link").mkdir(exist_ok=True)
    os.symlink(w.home / "settings.json", data / "link" / "settings.json")
    (w.home / "settings.json").write_text("{}")
    cases = [f"{data}/r/settings.json", f"{data}/r/other.json", f"{data}/nope/settings.json", f"{data}/link/settings.json",
             f"{data}/r/../r/settings.json", f"{w.home}/settings.json", "data/r/settings.json", None]
    got = _menubar_js(w, f"return JSON.stringify({json.dumps(cases)}.map(revealable));")
    assert got == [f"{data}/r/settings.json"] + [""] * 7, "only <data>/<repo>/settings.json, a regular file"


# refresh() against a stand-in status item: what it sets as the badge and the menu.
REFRESH_STUB = """var bar = { title: null, menu: null };
    item = { setMenu: function (m) { bar.menu = m; }, button: { setTitle: function (t) { bar.title = String(t); } } };
    icons.header = mothImage(28, false);
    var titles = function () { var a = []; for (var i = 0; i < bar.menu.numberOfItems; i++) a.push(ObjC.unwrap(bar.menu.itemAtIndex(i).title)); return a; };"""


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_badge_counts_the_rows_shown_that_run_or_wait_for_an_answer(w):
    """A row waiting for Fix now, or one done, is nobody being busy: only running sessions, questions
    and a Fix now click being started count."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        "1:review": {"pr": 1, "role": "review", "last_state": "working", "last_state_at": now},
        "2:review": {"pr": 2, "role": "review", "last_state": "question", "last_state_at": now},
        "3:review": {"pr": 3, "role": "review", "last_state": "posted", "last_state_at": now}},
        "findings": {"4": {"at": now, "counts": {"🟠": 1}}, "5": {"at": now, "counts": {"🔵": 1}}}})
    _watched(w)
    got = _menubar_js(w, REFRESH_STUB + """pendingFix[__REPO__ + '#5'] = Date.now();
        refresh(); return JSON.stringify([bar.title, scan().repos[0].watchers[0].rows.map(function (r) { return r.kind; }).sort()]);"""
                      .replace("__REPO__", json.dumps(str(w.repo))))
    assert got[1] == ["findings", "fix_requested", "posted", "question", "working"]
    assert got[0] == "3", "working, question and fix_requested; not findings or posted"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_menu_that_fails_to_build_shows_a_minimal_one_and_no_badge(w):
    """Badge set before the menu was built: a build error left "1" beside a menu saying nothing runs."""
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        "1:review": {"pr": 1, "role": "review", "last_state": "working"}}})
    _watched(w)
    f = w.home / "menubar-headless.js"
    got = _menubar_js(w, REFRESH_STUB + """refresh(); var before = [bar.title, titles().length > 4];
        watcherItems = function () { throw new Error('boom'); };
        refresh(); return JSON.stringify([before, bar.title, titles()]);""")
    assert got[0] == ["1", True]
    assert got[1:] == ["", ["The menu failed to build — see menubar.log", "", "Quit menu bar"]]
    out = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", str(f)], capture_output=True, text=True, timeout=30, env=w.env)
    assert "open-pr menu bar: the menu failed to build: Error: boom" in out.stderr, "the error reaches menubar.log"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_the_menu_is_built_as_wide_as_the_settings_panel_its_gear_opens(w):
    """The gear inserts the panel into the menu already open, which keeps the width it opened with:
    with a short repo name the panel lost "Apply to all" and its right column."""
    _watched(w)
    (w.home / "settings.json").write_text(json.dumps({"review": {}, "watch": {"max_concurrent": 5}}))
    got = _menubar_js(w, """icons.header = mothImage(28, false);
        var s = scan(), m = build(s), x = s.repos[0].settings[0];
        return JSON.stringify([m.minimumWidth, settingsPanel(x, s.quotas, '').view.frame.size.width, HEADER_W]);""", script=True)
    assert got[0] >= got[1] > got[2], got


def _build(root, age):
    """A plugin build's bin/ under root: its scripts, the menu bar's written `age` seconds ago."""
    b = root / "bin"
    b.mkdir(parents=True)
    (b / "open-pr-watch.sh").write_text("")
    (b / "open-pr-menubar.js").write_text("")
    t = time.time() - age
    os.utime(b / "open-pr-menubar.js", (t, t))
    return str(b / "open-pr-watch.sh")


# The line the menu shows under its header, whether a click runs anything, and what: one per watcher
# record's `script` (None: the build the menu bar runs, updated in place since it started).
UPDATE = """var log = [];
    $.NSApplication.sharedApplication;   // warnColor reads NSApp, as in run()
    spawn = function (p, a) { log.push([p].concat(a)); return true; };
    launched = menubarTime(watchScript); __TOUCH__ refresh();
    var mi = bar.menu.itemAtIndex(1), t = ObjC.unwrap(mi.title);
    if (mi.isEnabled) bar.menu.performActionForItemAtIndex(1);
    return JSON.stringify([/updated/.test(t) ? t : '', mi.isEnabled, log, scan().update]);"""


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
@pytest.mark.parametrize("case", ["same", "newer", "older", "elsewhere", "missing", "in place"])
def test_the_menu_says_open_pr_was_updated_and_restarts_into_the_newest_build(w, tmp_path, case):
    """Every live watcher records the script its wait runs. One whose build is newer than the menu
    bar's start is an update; a click runs that build's `menubar --restart`, and only a sibling install
    of the one it runs (or itself) — any other path gets the line and no action."""
    (w.bin / "open-pr-menubar.js").write_text("")
    t = time.time() - 100
    os.utime(w.bin / "open-pr-menubar.js", (t, t))
    script = {"same": str(w.bin / "open-pr-watch.sh"), "in place": str(w.bin / "open-pr-watch.sh"),
              "newer": _build(tmp_path.parent / (tmp_path.name + "-new"), 0),
              "older": _build(tmp_path.parent / (tmp_path.name + "-old"), 500),
              "elsewhere": _build(tmp_path / "x" / "new", 0),
              "missing": str(tmp_path.parent / (tmp_path.name + "-gone") / "bin" / "open-pr-watch.sh")}[case]
    _watched(w)
    rec = json.loads((w.sd / "watcher.json").read_text())
    (w.sd / "watcher.json").write_text(json.dumps(dict(rec, script=script)))
    touch = "$.NSFileManager.defaultManager.setAttributesOfItemAtPathError($({ NSFileModificationDate: $.NSDate.date }), " \
            + json.dumps(str(w.bin / "open-pr-menubar.js")) + ", null);" if case == "in place" else ""
    got = _menubar_js(w, REFRESH_STUB + UPDATE.replace("__TOUCH__", touch), script=True)
    restart = {"newer": script, "in place": str(w.bin / "open-pr-watch.sh")}.get(case)
    if restart:
        assert got == ["open-pr was updated — Restart menu bar", True, [["/bin/sh", restart, "menubar", "--restart"]],
                       {"args": [restart, "menubar", "--restart"]}]
    elif case == "elsewhere":
        assert got == ["open-pr was updated — run /open-pr:menubar restart", False, [], {"args": None}]
    else:
        assert got[0] == "" and got[3] is None, "an older or missing build is no update"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_click_runs_only_a_script_of_a_sibling_install(w, tmp_path):
    new = _build(tmp_path.parent / (tmp_path.name + "-new"), 0)
    here = str(w.bin / "open-pr-watch.sh")
    up = str(tmp_path.parent)
    cases = [here, new, up + "/" + tmp_path.name + "-new/../" + tmp_path.name + "-new/bin/open-pr-watch.sh",
             up + "/./bin/open-pr-watch.sh", up + "//bin/open-pr-watch.sh", up + "/x\n/bin/open-pr-watch.sh",
             new.replace("open-pr-watch.sh", "open-pr.sh"), "bin/open-pr-watch.sh", ""]
    got = _menubar_js(w, f"return JSON.stringify({json.dumps(cases)}.map(buildScript));", script=True)
    assert got == [here, new, "", "", "", "", "", "", ""]



# One row per case: its state.json entry → the kind it shows, and whether the badge counts it.
BADGE_KINDS = [
    ({"1:review": {"last_state": "working"}}, "working", True),
    ({"1:review": {"last_state": "question"}}, "question", True),
    ({"1:fix": {"last_state": "working"}}, "fixing", True),
    ({"1:fix": {"last_state": "working", "runner": "here"}}, "fixing_here", True),
    ({"1:review": {"last_state": "posted"}}, "posted", False),
    ({"1:review": {"last_state": "draft"}}, "draft", False),
    ({"1:review": {"last_state": "lgtm_chat"}}, "lgtm", False),
    ({"1:review": {"last_state": "failed"}}, "failed", False),
    ({"1:review": {"last_state": "stopped"}}, "stopped", False),
    ({"1:review": {"last_state": "working", "finished": True}}, "working", True),
    ({}, None, False),
]


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
@pytest.mark.parametrize("sessions, kind, counted", BADGE_KINDS)
def test_the_badge_counts_each_kind_of_row_or_not(w, sessions, kind, counted):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        k: dict(v, pr=int(k.split(":")[0]), role=k.split(":")[1], last_state_at=now) for k, v in sessions.items()}})
    _watched(w)
    got = _menubar_js(w, REFRESH_STUB + """refresh();
        var rows = scan().repos.map(function (g) { return g.watchers[0].rows.map(function (r) { return r.kind; }); });
        return JSON.stringify([bar.title, rows]);""")
    assert got[1] == ([[kind]] if kind else [[]])
    assert got[0] == ("1" if counted else ""), "zero shows no number"


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
@pytest.mark.parametrize("n, hidden, shown", [(2, [2], 1), (10, [], 10), (11, [], 10), (12, [12], 10), (1, [1], 0)])
def test_the_badge_counts_only_the_rows_the_menu_shows(w, n, hidden, shown):
    """A removed PR has no row, and past ROWS rows a watcher shows none: the badge counts neither."""
    sessions = {f"{i}:review": {"pr": i, "role": "review", "last_state": "working",
                                "last_state_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 100 + i))}
                for i in range(1, n + 1)}
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": sessions, "hidden": hidden})
    _watched(w)
    got = _menubar_js(w, REFRESH_STUB + """refresh();
        var prs = titles().filter(function (t) { return /^#[0-9]+$/.test(t); });
        return JSON.stringify([bar.title, prs.length, ROWS]);""")
    assert got == [str(shown) if shown else "", shown, 10]


def _ago(sec):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - sec))


# The PR rows of the menu refresh() built: [title, indentation steps past a PR row's, subtitle, submenu titles].
PR_ITEMS = """var items = function () { var a = [];
        for (var i = 0; i < bar.menu.numberOfItems; i++) { var mi = bar.menu.itemAtIndex(i), sub = [], s = mi.submenu;
            if (mi.indentationLevel < PR_INDENT || ObjC.unwrap(mi.title) === 'No pull requests yet') continue;
            if (!s.isNil()) for (var j = 0; j < s.numberOfItems; j++) sub.push(ObjC.unwrap(s.itemAtIndex(j).title));
            // a state with severity marks is the title's second line (smallMarks needs an attributed title)
            var two = ObjC.unwrap(mi.title).split('\\n');
            a.push([two[0], mi.indentationLevel - PR_INDENT,
                    two[1] || (mi.respondsToSelector('subtitle') ? ObjC.unwrap(mi.subtitle) || '' : ''), sub]); }
        return a; };"""


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_prs_fix_row_nests_under_its_review_row_and_groups_keep_the_row_order(w):
    """A PR's review and fix rows sat apart, each placed by its own time. Now one PR is one group:
    review on top, its fix row one step further in, titled by its state alone; groups ordered as rows
    were (one waiting on the user first, then the newest of its rows). A PR with one row is as before,
    a fix row's state saying it is the fix."""
    url = lambda n: f"https://github.com/o/r/pull/{n}"
    w.put_state({"cursor": None, "seen": [], "queue": [], "titles": {"1": "One", "2": "Two", "3": "Three", "4": "Four"},
                 "sessions": {
                     "1:review": {"pr": 1, "role": "review", "last_state": "posted", "last_state_at": _ago(300), "url": url(1)},
                     "2:review": {"pr": 2, "role": "review", "last_state": "posted", "last_state_at": _ago(200), "url": url(2)},
                     "4:review": {"pr": 4, "role": "review", "last_state": "working", "last_state_at": _ago(500), "url": url(4)}},
                 "findings": {"1": {"at": _ago(100), "counts": {"🔵": 4}, "url": url(1)},
                              "3": {"at": _ago(400), "counts": {"🟠": 1}, "url": url(3)}}})
    _watched(w)
    got = _menubar_js(w, REFRESH_STUB + PR_ITEMS + "refresh(); return JSON.stringify(items());", script=True)
    got = [[t.split(" · ")[0], lvl, sub.split(" · ")[0], menu] for t, lvl, sub, menu in got]
    pr = ["Open pull request", "Remove from list"]
    assert got == [
        ["#1 One", 0, "Posted", pr],
        ["Fix: 4 🔵 — Fix now", 1, "", ["Fix now"] + pr],
        ["#3 Three", 0, "Fix: 1 🟠 — Fix now", ["Fix now"] + pr],
        ["#4 Four", 0, "Reviewing", pr],
        ["#2 Two", 0, "Posted", pr],
    ], got


# A feed summary (written for the toast, which needs the number) → the row's state under its title.
OWN_NUMBER = [
    (1914, "#1914: 4 🔵 SUGGESTION", "4 🔵 SUGGESTION"),
    (1915, "Đã post review #1915: 4 🔵", "Đã post review: 4 🔵"),
    (1916, "#1916 posted", "posted"),
    (1917, "bỏ qua #1913, xong #1917", "bỏ qua #1913, xong"),
    (1918, "LGTM", "LGTM"),
    (1919, "#19190: other PR", "#19190: other PR"),
    (1920, "Reviewed o/r#1920 — 1 🟠", "Reviewed — 1 🟠"),
    (None, "poll failed after #1914", "poll failed after #1914"),
]


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_a_rows_state_leaves_out_its_own_pr_number(w):
    """`#1914 Title` over `#1914: 4 🔵 …` said the number twice: a row's state drops its own PR's
    number, never another's, nor anything on the repo-wide row."""
    _watched(w)   # a repo-wide line older than the watcher is over: these are newer
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {}})
    (w.sd / "feed.jsonl").write_text("".join(json.dumps(
        {"at": _ago(-60), "repo": "o/r", "role": "review", "event": "posted", "summary": summary, **({"pr": pr} if pr else {})}) + "\n"
        for pr, summary, _ in OWN_NUMBER))
    got = _menubar_js(w, REFRESH_STUB + PR_ITEMS + "refresh(); return JSON.stringify(items());")
    seen = {t.split(" ")[0]: sub.rsplit(" · ", 1)[0] for t, _, sub, _ in got}
    assert seen == {(f"#{pr}" if pr else "Repository"): want for pr, _, want in OWN_NUMBER}


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
def test_severity_marks_are_drawn_smaller_than_the_text_around_them(w):
    """At the text's size a 🔵 outweighed the words of its line: in a row's state and in a nested fix
    row's title, each mark is drawn smaller than the text beside it, in its own colours."""
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        "1:review": {"pr": 1, "role": "review", "last_state": "posted", "last_state_at": _ago(300)}},
        "findings": {"1": {"at": _ago(100), "counts": {"🔵": 4}}, "2": {"at": _ago(200), "counts": {"🔴": 1, "📝": 2}}}})
    _watched(w)
    got = _menubar_js(w, REFRESH_STUB + """refresh(); var out = [];
        for (var i = 0; i < bar.menu.numberOfItems; i++) {
            var mi = bar.menu.itemAtIndex(i), a = mi.attributedTitle, t = a.isNil() ? '' : ObjC.unwrap(a.string), re = /🔴|🟠|🔵|📝/g, m;
            if (mi.indentationLevel < PR_INDENT || !t) continue;
            var size = function (k) { return a.attributeAtIndexEffectiveRange('NSFont', k, null).pointSize; };
            while ((m = re.exec(t))) out.push([t.split('\\n')[0].split(' ')[0], m[0], size(m.index) < size(m.index - 2)]);
        }
        return JSON.stringify(out);""")
    assert got == [["Fix:", "🔵", True], ["#2", "🔴", True], ["#2", "📝", True]], got


@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
@pytest.mark.parametrize("n", [10, 11])
def test_the_row_limit_counts_prs_and_the_badge_counts_each_nested_row(w, n):
    """ROWS is PRs shown, never rows: a PR is never split by the limit, and the badge counts both
    of its running rows."""
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        f"{i}:{role}": {"pr": i, "role": role, "last_state": "working", "last_state_at": _ago(100 - i)}
        for i in range(1, n + 1) for role in ("review", "fix")}})
    _watched(w)
    got = _menubar_js(w, REFRESH_STUB + PR_ITEMS + """refresh();
        return JSON.stringify([bar.title, items().map(function (x) { return [x[0].split(' · ')[0], x[1]]; })]);""")
    assert got[0] == "20"
    shown = list(range(n, n - 10, -1))
    assert got[1] == [x for i in shown for x in ([f"#{i}", 0], ["Fix: Fixing", 1])]


# A panel wider than the default one: a typed trigger shows as an extra segment, a repo held in
# several data dirs gets its path as a caption.
@pytest.mark.skipif(not shutil.which("osascript"), reason="macOS only")
@pytest.mark.parametrize("change", [
    "x.conf.watch.trigger = '@' + new Array(60).join('a');",
    "s.repos[0].settings.push({ name: x.name, repo: '/' + new Array(90).join('d') + '/r', conf: x.conf, arg: x.arg, doctor: x.doctor });",
])
def test_a_panel_widened_by_its_content_widens_the_menu_built_next(w, change):
    _watched(w)
    (w.home / "settings.json").write_text(json.dumps({"review": {}, "watch": {"max_concurrent": 5}}))
    got = _menubar_js(w, """icons.header = mothImage(28, false);
        var s = scan(), x = s.repos[0].settings[0], before = build(s).minimumWidth;
        s = scan(); x = s.repos[0].settings[0]; """ + change + """
        var widths = s.repos[0].settings.map(function (y) { return settingsPanel(y, s.quotas, caption(s.repos[0].settings, y)).view.frame.size.width; });
        return JSON.stringify([before, build(s).minimumWidth, Math.max.apply(null, widths)]);""", script=True)
    before, after, panel = got
    assert panel > before, "the case does not widen the panel"
    assert after >= panel, got


def _rosetta():
    return shutil.which("osascript") and subprocess.run(["arch", "-x86_64", "/usr/bin/true"], capture_output=True).returncode == 0


# The real menu bar and toast on screen, under each architecture a Mac runs osascript on: Intel's
# JXA bridge hung on an ObjC subclass and crashed on a layer colour that Apple silicon's took.
# Needs the window server: run outside a shell sandbox.
@pytest.mark.skipif(not _rosetta(), reason="macOS with Rosetta only")
@pytest.mark.parametrize("arch", ["x86_64", "arm64"])
def test_the_menu_bar_and_a_toast_reach_the_screen_on_each_architecture(tmp_path, arch):
    data = tmp_path / "data"
    data.mkdir()
    pf = tmp_path / "menubar.pid"
    bar = subprocess.Popen(["arch", f"-{arch}", "/usr/bin/osascript", "-l", "JavaScript", str(MENUBAR),
                            str(tmp_path / "snooze"), str(pf), "2700", str(data)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.time() + 20
        while time.time() < deadline and bar.poll() is None and not pf.exists():
            time.sleep(0.1)
        assert pf.exists(), f"no item in the menu bar (exit {bar.poll()}): {bar.stderr.read() if bar.poll() is not None else ''}"
        assert pf.read_text().strip() == str(bar.pid), "arch execs osascript: the pid is the menu bar's"
        time.sleep(1)
        assert bar.poll() is None, bar.stderr.read()
    finally:
        bar.kill()
        bar.wait()
    shown = tmp_path / "slot" / "shown"
    shown.parent.mkdir()
    toast = subprocess.run(["arch", f"-{arch}", "/usr/bin/osascript", "-l", "JavaScript",
                            str(REPO / "src" / "bin" / "open-pr-toast.js"), f"open-pr test ({arch})", "smoke test", "",
                            "findings", "0", "1", "", "", "pr", "", "", "", "", "", "", "", "", "", "", "", str(shown)],
                           capture_output=True, text=True, timeout=30)
    assert toast.returncode == 0 and shown.exists(), toast.stderr
