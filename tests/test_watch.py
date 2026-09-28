"""Unit tests for src/bin/open-pr-watch.sh.

The watch runtime reaches a code host only through its sibling open-pr.sh and an agent
platform only through that platform's CLI, so both are replaced here: the script is copied
into a temp bin/ beside a fake open-pr.sh (it resolves the sibling by its own dirname), and
each platform CLI is a shim on PATH that records its argv and cwd. The fake `claude` keeps
its sessions in a JSON file and behaves like the real one where it matters: a resume of a
session still listed as active, or with an extra flag, starts a copy under a new id.
"""

import json
import os
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
    data-dir) printf '%s\n' "$FAKE_HOME/data" ;;
    repo-target) printf '%s\n' "$*" >> "$FAKE_HOME/repo-target.args"
                 printf 'vendor=github\nowner=o\nrepo=r\nhost=github.com\n' ;;
    triggers) printf '%s\n' "$*" >> "$FAKE_HOME/triggers.args"
              # triggers.rc: one outcome per call, consumed in order — 9 = rate limited, quiet = nothing
              if [ -s "$FAKE_HOME/triggers.rc" ]; then
                  rc=$(head -n 1 "$FAKE_HOME/triggers.rc")
                  sed 1d "$FAKE_HOME/triggers.rc" > "$FAKE_HOME/triggers.rc.n"; mv "$FAKE_HOME/triggers.rc.n" "$FAKE_HOME/triggers.rc"
                  case "$rc" in 9) printf 'rate limited\n' >&2; exit 9 ;; quiet) exit 0 ;; esac
              fi
              mf=$(printf '%s\n' "$@" | sed -n '/^--mark-file$/{n;p;}')
              [ -z "$mf" ] || cat "$FAKE_HOME/mark.txt" > "$mf" 2>/dev/null || : > "$mf"
              cat "$FAKE_HOME/triggers.jsonl" 2>/dev/null || true ;;
    settings) cat "$FAKE_HOME/settings.json" 2>/dev/null || printf '{}\n' ;;
    account) cat "$FAKE_HOME/account.txt" 2>/dev/null || printf 'UNKNOWN\n' ;;
    *) exit 1 ;;
esac
"""

# One recorder for every headless CLI: argv + cwd to <name>.<n>.json, then whatever
# the per-CLI output file says, then an optional sleep so a test can hold the pid alive.
RECORDER = r"""#!/usr/bin/env python3
import json, os, sys, time
name = os.path.basename(sys.argv[0])
home = os.environ["FAKE_HOME"]
n = len([f for f in os.listdir(home) if f.startswith(name + ".") and f.endswith(".json")])
with open(os.path.join(home, f"{name}.{n}.json"), "w") as fh:
    json.dump({"argv": sys.argv[1:], "cwd": os.getcwd()}, fh)
if name == "agent" and sys.argv[1:] == ["create-chat"]:
    print("chat-abc")
    sys.exit(0)
out = os.path.join(home, f"{name}.out")
if os.path.exists(out):
    sys.stdout.write(open(out).read())
    sys.stdout.flush()
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
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

if a[:2] == ["agents", "--json"]:
    rows = db["sessions"] if "--all" in a else [s for s in db["sessions"] if s["state"] in ACTIVE]
    print(json.dumps(rows))
elif a[:1] == ["stop"]:
    for s in db["sessions"]:
        if s["id"] == a[1]:
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
    # the running interpreter, not `env python3`: a version-manager shim costs ~200ms per
    # call, and the fake CLIs are called many times per test
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
        self.sd = self.home / "data" / "r" / "watch-review"
        self.env = dict(os.environ, FAKE_HOME=str(self.home),
                        PATH=f"{self.fakes}{os.pathsep}{os.environ['PATH']}")
        self.children = []

    def run(self, *args, env_extra=None, path=None, check=True):
        env = dict(self.env, **(env_extra or {}))
        if path is not None:
            env["PATH"] = path
        r = subprocess.run(["sh", str(self.bin / "open-pr-watch.sh"), *args], capture_output=True,
                           text=True, cwd=self.repo, env=env, timeout=90)
        if check and r.returncode != 0:
            raise AssertionError(f"open-pr-watch.sh {' '.join(args)} exit {r.returncode}:\n{r.stderr}")
        return r

    def jsonl(self, *args, **kw):
        return [json.loads(line) for line in self.run(*args, **kw).stdout.splitlines() if line.strip()]

    def settings(self, **watch_review):
        (self.home / "settings.json").write_text(json.dumps({"watch_review": watch_review}))

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

    def spawn(self, pr, runner="claude", text="review it", **kw):
        return self.jsonl("spawn", "--runner", runner, "--pr", str(pr), "--name",
                          f"review o/r#{pr}", "--prompt-file", self.prompt(text, f"p{pr}.txt"), **kw)[0]

    def claude_db(self):
        return json.loads((self.home / "claude.db.json").read_text())

    def claude_set(self, cid, state):
        db = self.claude_db()
        for s in db["sessions"]:
            if s["id"] == cid:
                s["state"] = state
        (self.home / "claude.db.json").write_text(json.dumps(db))

    def claude_calls(self):
        return [json.loads(l)["argv"] for l in (self.home / "claude.calls").read_text().splitlines()]

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
    for sub in ("wait", "spawn", "status", "next", "forget", "paths", "notify", "trust", "snooze", "menubar"):
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
    assert gi.count("watch-review/") == 1


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
    assert call.endswith(want) and "--mark-file" in call
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
    """Delivery is committed by the state rename after the print. A wait killed in between
    leaves the old state.json — exactly what restoring it here reproduces — so the next wait
    must print the same comment again rather than lose it."""
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
    """Self-hosted GitLab prints created_at in its own zone (+09:00). The cursor must be
    stored in UTC: an offset kept verbatim breaks the next poll's --since and compares
    wrongly as a string against Z timestamps."""
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
    assert ev == [{"event": "session", "repo": "o/r", "pr": 5, "state": "posted", "open": f"claude attach {sp['id']}"}]
    assert w.run("wait", "--once").stdout == ""



def test_a_running_wait_sees_a_session_change_between_its_own_polls(w):
    """`wait` polls many times in one process; a listing cached from its first poll would keep
    reporting `working` until some trigger made it exit."""
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
    """No trigger for days must not leave --since at the watcher's start: every poll would
    re-fetch every comment since then."""
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

# ------------------------------------------------------- spawn / resume ----

def test_claude_spawn_records_the_session_and_its_open_command(w):
    sp = w.spawn(3, text="p")
    assert sp == {"pr": 3, "id": sp["id"], "open": f"claude attach {sp['id']}"}
    s = w.state()["sessions"]["3"]
    assert s["runner"] == "claude" and s["session_id"].startswith(sp["id"])
    assert s["name"] == "review o/r#3" and s["last_state"] == "working"
    assert w.claude_calls()[0] == ["--bg", "-n", "review o/r#3", "p"]


def test_spawn_on_a_claude_session_stops_waits_then_resumes_without_flags(w):
    sp = w.spawn(4)
    w.claude_set(sp["id"], "done")
    w.status_file(4, state="draft")
    again = w.spawn(4, text="second look")
    assert again == {"pr": 4, "id": sp["id"], "open": f"claude attach {sp['id']}", "resumed": True}
    calls = w.claude_calls()
    stop = calls.index(["stop", sp["id"]])
    sid = w.state()["sessions"]["4"]["session_id"]
    assert ["agents", "--json"] in calls[stop + 1:], "never waited for the session to leave the active list"
    assert calls[-1] == ["--bg", "--resume", sid, "second look"]
    assert not (w.sd / "pr-4.status.json").exists(), "a stale status file survived the relaunch"
    assert w.claude_db()["sessions"][0]["name"] == "review o/r#4"


def test_a_resume_that_starts_a_copy_is_reported_and_followed(w):
    sp = w.spawn(6)
    w.claude_set(sp["id"], "done")
    again = w.spawn(6, env_extra={"FAKE_CLAUDE_COPY": "1"})
    assert again["id"] != sp["id"] and "started a copy" in again["warning"]
    assert w.state()["sessions"]["6"]["id"] == again["id"]


def test_a_re_review_waits_while_the_session_still_runs(w):
    w.spawn(8)
    assert w.spawn(8, text="new") == {"pr": 8, "queued": True, "reason": "session still running"}
    assert "stop" not in [c[0] for c in w.claude_calls()]


def test_full_slots_queue_and_next_pops_after_a_session_finishes(w):
    w.settings(max_concurrent=1)
    first = w.spawn(1)
    assert w.spawn(2) == {"pr": 2, "queued": True, "reason": "all 1 slots busy"}
    assert w.run("next").stdout == ""
    w.claude_set(first["id"], "done")
    w.status_file(1, state="posted")
    popped = w.jsonl("next")
    assert popped == [{"pr": 2, "runner": "claude", "name": "review o/r#2",
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
    assert w.jsonl("forget", "--pr", "9") == [{"pr": 9, "forgotten": True}]
    again = w.spawn(9)
    assert again["id"] != sp["id"] and "resumed" not in again


# -------------------------------------------------------------- status ----

@pytest.mark.parametrize("claude_state,status_body,want", [
    ("working", None, "working"),
    ("blocked", None, "question"),
    ("failed", None, "failed"),
    ("stopped", None, "stopped"),
    ("done", {"state": "posted"}, "posted"),
    ("done", {"state": "draft"}, "draft"),
    ("done", {"state": "lgtm_chat"}, "lgtm_chat"),
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


def test_headless_status_follows_the_pid_then_the_status_file(w):
    (w.home / "codex.out").write_text(json.dumps({"type": "thread.started", "thread_id": "th-1"}) + "\n")
    sp = w.spawn(13, runner="codex", env_extra={"FAKE_SLEEP": "30"})
    pid = w.state()["sessions"]["13"]["pid"]
    try:
        w.recorded("codex")
        row = w.jsonl("status")[0]
        assert row == {"pr": 13, "runner": "codex", "id": "th-1", "state": "working",
                       "open": "codex resume th-1"}
        assert sp["id"] is None and w.state()["sessions"]["13"]["id"] == "th-1", \
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
    pid = w.state()["sessions"]["22"]["pid"]
    w.wait_dead(pid)
    w.status_file(22, state="question", question="?")
    again = w.spawn(22, runner=runner, text=TRICKY)
    sid = w.state()["sessions"]["22"]["id"]
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
    assert rec["argv"][10] == str(w.home / "data" / ".watch" / "snooze_until"), \
        "the toast's 1h control writes the one snooze file every notifier reads"



def test_toasts_stack_in_free_slots_and_carry_the_pr_url(w, tmp_path):
    """A toast still showing keeps its place; a new one takes the first free slot, and a slot
    frees when its toast exits — so toasts never cover each other."""
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

def trust(w, config, runner="claude", repo_dir=None):
    cfg = w.home / "claude.json"
    if config is None:
        cfg.unlink(missing_ok=True)
    else:
        cfg.write_text(config if isinstance(config, str) else json.dumps(config))
    args = ["trust", "--runner", runner] + (["--repo-dir", str(repo_dir)] if repo_dir else [])
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


def test_a_finished_session_stays_silent_while_the_user_chats_in_it(w):
    """After its result the session is the user's: their own turns there must not toast
    "needs an answer" or "posted" again."""
    sp = finish(w)
    assert w.state()["sessions"]["5"]["finished"] is True
    for live in ("working", "blocked", "done"):
        w.claude_set(sp["id"], live)
        assert w.run("wait", "--once").stdout == "", f"a finished session reported {live}"
    assert w.jsonl("status") == [{"pr": 5, "runner": "claude", "id": sp["id"], "state": "posted",
                                  "open": f"claude attach {sp['id']}", "finished": True}]


def test_a_resumed_session_reports_again(w):
    sp = finish(w)
    w.claude_set(sp["id"], "done")
    again = w.spawn(5, text="second look")
    assert again["resumed"] is True
    assert w.state()["sessions"]["5"]["finished"] is False
    assert w.run("wait", "--once").stdout == ""
    w.claude_set(sp["id"], "blocked")
    assert [e["state"] for e in w.jsonl("wait", "--once")] == ["question"]


def test_a_new_request_never_cuts_a_conversation_in_a_finished_session(w):
    """The user is talking in the finished session: a new request queues instead of
    `claude stop`-ing it, and `wait` says `ready` once the session is idle again."""
    sp = finish(w)
    w.claude_set(sp["id"], "working")
    out = w.spawn(5, text="second look")
    assert out.get("queued") is True and out["reason"] == "session in use"
    assert not any(c[:1] == ["stop"] for c in w.claude_calls()), "the conversation was stopped"
    assert w.run("wait", "--once").stdout == "", "not ready while the user is still talking"
    w.claude_set(sp["id"], "done")
    assert [(e["event"], e["pr"]) for e in w.jsonl("wait", "--once")] == [("ready", 5)]
    assert w.jsonl("next")[0]["pr"] == 5

def test_a_finished_session_holds_no_slot_whatever_its_live_state(w):
    w.settings(max_concurrent=1)
    sp = finish(w, 1)
    w.claude_set(sp["id"], "working")
    assert "queued" not in w.spawn(2)


def test_spawn_keeps_what_the_menu_bar_shows(w):
    url = "https://github.com/o/r/pull/3"
    sp = w.jsonl("spawn", "--runner", "claude", "--pr", "3", "--name", "review o/r#3",
                 "--prompt-file", w.prompt("p"), "--url", url)[0]
    s = w.state()["sessions"]["3"]
    assert (s["repo"], s["url"], s["open"], s["finished"]) == ("o/r", url, f"claude attach {sp['id']}", False)


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


# -------------------------------------------------------------- snooze ----

def test_snooze_for_until_and_off_share_one_machine_file(w):
    f = w.home / "data" / ".watch" / "snooze_until"
    out = w.jsonl("snooze", "--for", "2h30m")[0]
    left = datetime.fromisoformat(out["snooze_until"].replace("Z", "+00:00")) - datetime.now(timezone.utc)
    assert 9000 - 60 < left.total_seconds() <= 9000
    assert f.read_text() == out["snooze_until"] + "\n"
    assert w.jsonl("snooze", "--until", "2026-01-01T09:00:00+09:00") == [{"snooze_until": "2026-01-01T00:00:00Z"}]
    assert f.read_text() == "2026-01-01T00:00:00Z\n"
    assert w.jsonl("snooze", "--off") == [{"snooze_until": None}] and not f.exists()
    assert w.jsonl("snooze", "--off") == [{"snooze_until": None}], "resuming twice is fine"
    assert ".watch/" in (w.home / "data" / ".gitignore").read_text().splitlines()
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
    assert rows[-2] == {"repo": "o/r", "pr": 3, "event": "posted", "summary": "PR #3 posted",
                        "detail": "claude attach 1", "url": "https://h/o/r/pull/3"}
    assert (rows[-1]["event"], rows[-1]["pr"], rows[-1]["url"], rows[-1]["detail"]) == \
        ("review_started", None, None, ""), "a snoozed notification is still recent history"


def test_notify_rejects_a_pr_that_is_not_a_number(w):
    r = w.run("notify", "--event", "posted", "--text-file", w.prompt("x"), "--pr", "3;id", check=False)
    assert r.returncode == 4


# ------------------------------------------------------------- menubar ----

def test_menubar_without_osascript_is_no_equivalent(w, tmp_path):
    r = w.run("menubar", path=_minimal_path(w, tmp_path, False))
    assert r.stdout == "NO-EQUIVALENT\n"


def test_menubar_runs_detached_once_per_machine(w):
    env = {"FAKE_SLEEP": "30"}
    watch = w.home / "data" / ".watch"
    started = time.time()
    assert w.run("menubar", env_extra=env).stdout == "started\n"
    assert time.time() - started < 10, "menubar waited on the menu bar process"
    assert (REPO / "src" / "bin" / "open-pr-menubar.js").is_file()
    rec = w.recorded("osascript")
    assert rec["argv"] == ["-l", "JavaScript", str(w.bin / "open-pr-menubar.js"), str(w.home / "data"),
                           str(watch / "snooze_until"), str(watch / "menubar.pid"), "2700"]
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
