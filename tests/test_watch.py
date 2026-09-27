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
    triggers) cat "$FAKE_HOME/triggers.jsonl" 2>/dev/null || true ;;
    settings) cat "$FAKE_HOME/settings.json" 2>/dev/null || printf '{}\n' ;;
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
    for sub in ("wait", "spawn", "status", "next", "forget", "paths", "notify"):
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


def test_wait_reports_a_session_state_change_once(w):
    sp = w.spawn(5)
    assert w.run("wait", "--once").stdout == "", "a fresh session is already known to be working"
    w.claude_set(sp["id"], "done")
    w.status_file(5, state="posted", url="https://github.com/o/r/pull/5")
    ev = w.jsonl("wait", "--once")
    assert ev == [{"event": "session", "repo": "o/r", "pr": 5, "state": "posted", "open": f"claude attach {sp['id']}"}]
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


def test_notify_skips_during_snooze_and_resumes_after(w):
    w.settings(snooze_until="2999-01-01T00:00:00Z")
    assert notify(w)["reason"] == "snoozed"
    w.settings(snooze_until="2000-01-01T00:00:00.000Z")
    assert notify(w)["sent"] is True


def test_osascript_gets_the_text_as_argv_never_as_source(w):
    text = 'say "hi" & do shell script "touch /tmp/x" $(id) `id`'
    assert notify(w, text=text)["via"] == "osascript"
    rec = w.recorded("osascript")
    assert rec["argv"] == ["-", "open-pr · r", text]


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
    assert w.recorded("notify-send")["argv"] == ["--", "open-pr · r", "-rf text"]


def test_notify_without_a_notifier_prints_to_stderr(w, tmp_path):
    r = w.run("notify", "--event", "posted", "--text-file", w.prompt("hello", "n.txt"),
              path=_minimal_path(w, tmp_path, False))
    assert json.loads(r.stdout)["via"] == "stderr" and "[open-pr · r] hello" in r.stderr


def test_notify_rejects_an_unknown_event(w):
    r = w.run("notify", "--event", "nope", "--text-file", w.prompt("x"), check=False)
    assert r.returncode == 1 and "review_started" in r.stderr
