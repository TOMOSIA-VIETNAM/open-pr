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
              cat "$FAKE_HOME/triggers.jsonl" 2>/dev/null || true ;;
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
    for sub in ("wait", "spawn", "status", "next", "forget", "hide", "paths", "notify", "trust", "snooze", "menubar"):
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
    assert set(rec) == {"pid", "cwd", "term", "term_session", "tty", "session_id", "repo_dir", "remote"}
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

# osascript argv[11:] = the toast's focus, open command, term, term_session, tty, session_id.
def test_notify_focus_hands_the_toast_where_a_click_goes(w):
    sp = w.spawn(3)
    (w.sd / "watcher.json").write_text(json.dumps(
        {"pid": 1, "cwd": "/x", "term": "iTerm.app", "term_session": "w0t0p0:AB-12", "tty": "ttys004",
         "session_id": "269289ac-1f2e"}))
    url = "https://github.com/o/r/pull/3"
    w.run("notify", "--event", "question", "--text-file", w.prompt("PR #3 needs you", "q.txt"),
          "--pr", "3", "--url", url, "--focus", "session")
    rec = w.recorded("osascript")["argv"]
    assert rec[9] == url
    assert rec[11:17] == ["session", f"claude attach {sp['id']}", "iTerm.app", "w0t0p0:AB-12", "ttys004", "269289ac-1f2e"]
    assert rec[17:] == ["", "", "", ""], "only a findings toast carries Fix now"


# osascript argv[17:] = what the toast's "Fix now" runs: open-pr-watch.sh fix-now for that repo and PR.
def test_a_findings_toast_offers_fix_now_for_its_repo_and_pr(w):
    w.run("notify", "--event", "findings", "--text-file", w.prompt("#3: 2 🟠", "f.txt"), "--pr", "3",
          "--role", "fix", "--remote", "origin")
    rec = w.recorded("osascript")["argv"]
    assert rec[17:] == [str(w.bin / "open-pr-watch.sh"), str(w.repo.resolve()), "origin", "3"]
    assert json.loads((w.sd / "feed.jsonl").read_text().splitlines()[-1])["role"] == "fix"


def test_notify_focus_defaults_to_the_pr_and_rejects_an_unknown_one(w):
    assert notify(w)["sent"] is True
    assert w.recorded("osascript")["argv"][11:17] == ["pr", "", "", "", "", ""], "no --pr, no watcher.json"
    r = w.run("notify", "--event", "posted", "--text-file", w.prompt("x"), "--focus", "tab", check=False)
    assert r.returncode == 1 and "pr watcher session" in r.stderr


def test_notify_passes_no_open_command_or_tab_outside_their_shape(w):
    """They reach a .command file and osascript argv: anything else travels as an empty string."""
    w.put_state({"cursor": None, "seen": [], "queue": [],
                 "sessions": {"3:review": {"pr": 3, "role": "review", "runner": "claude", "open": "claude attach x; touch pwned"}}})
    (w.sd / "watcher.json").write_text(json.dumps(
        {"term": 'iTerm"$(id)', "term_session": "a b", "tty": "../../x y", "session_id": "ABC; claude"}))
    w.run("notify", "--event", "question", "--text-file", w.prompt("q"), "--pr", "3", "--focus", "session")
    assert w.recorded("osascript")["argv"][11:17] == ["session", "", "", "", "", ""]


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



def test_poll_sets_this_machines_interval_with_a_floor(w):
    assert w.jsonl("poll", "--seconds", "30")[0] == {"poll_seconds": 30}
    assert (w.watch / "poll_seconds").read_text() == "30\n"
    assert w.jsonl("poll", "--seconds", "5")[0] == {"poll_seconds": 15}, "never below 15 s"
    assert w.jsonl("poll", "--off")[0] == {"poll_seconds": None}
    assert not (w.watch / "poll_seconds").exists()


def test_a_running_wait_picks_up_a_faster_poll_within_seconds(w):
    """Chosen in the menu bar mid-wait: no waiting out the old interval."""
    w.settings(poll_interval_seconds=300)
    w.run("wait", "--once")                                    # cursor set
    proc = subprocess.Popen(["sh", str(w.bin / "open-pr-watch.sh"), "wait"], cwd=w.repo, env=w.env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    w.children.append(proc)
    try:
        time.sleep(2)
        w.run("poll", "--seconds", "15")
        w.triggers(trig("61", "2099-01-01T00:00:00Z"))
        out, _ = proc.communicate(timeout=40)              # 15 s, not 300 s
    finally:
        if proc.poll() is None:
            proc.kill()
    assert [json.loads(l)["comment_id"] for l in out.splitlines() if l.strip()] == ["61"]

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


# ------------------------------------------------------------ hide / closed PRs ----

def tracked(w, pr=5):
    """A spawned session with the cursor started: the first `wait` does nothing else."""
    sp = w.spawn(pr)
    assert w.run("wait", "--once").stdout == ""
    return sp


def open_prs_calls(w):
    f = w.home / "open-pr.calls"
    return [l for l in f.read_text().splitlines() if l.startswith("open-prs")] if f.exists() else []


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
    w.put_state(st)
    w.sd.joinpath("feed.jsonl").write_text(json.dumps({"at": "2026-01-01T00:00:00Z", "repo": "o/r", "pr": 8,
                                                       "event": "posted", "summary": "Posted"}) + "\n")
    (w.home / "open.txt").write_text("12\n")
    w.run("wait", "--once")
    st = w.state()
    assert st["hidden"] == [5, 8], "a feed-only row goes too"
    assert [q["pr"] for q in st["queue"]] == [12], "a closed PR's queued request is dropped"
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
    return {"pr": pr, "url": f"https://github.com/o/r/pull/{pr}", "review_id": review, "comment_id": "10",
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
                   "url": "https://github.com/o/r/pull/5", "comment_id": "10", "thread_id": None, "user": "rev"}]
    assert w.run("wait", "--once").stdout == "", "a review is delivered once"
    assert w.state()["findings"]["5"]["review_id"] == "70"
    w.spawn(5, extra=("--role", "fix"))
    assert "5" not in w.state().get("findings", {}), "a fix session takes the pending findings"
    row = w.jsonl("status", "--pr", "5", "--role", "fix")[0]
    assert row["findings"]["comment_id"] == "10" and row["findings"]["user"] == "rev", \
        "what a re-review request replies to"


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
                   "review_id": "70", "counts": {"🟠": 2, "🔵": 4}, "comment_id": "10", "thread_id": None,
                   "user": "rev"}]
    assert w.run("wait", "--once").stdout == "", "a click is delivered once"
    assert w.run("fix-now", "--pr", "5;id", check=False).returncode == 4


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
    w.put_state({"cursor": None, "seen": [], "queue": [], "sessions": {
        "5:review": {"pr": 5, "role": "review", "repo": "o/r", "last_state": "working"},
        "6:fix": {"pr": 6, "role": "fix", "repo": "o/r", "last_state": "working"}}})
    for sfx, ts in (("-review", "w0t0p1:AA"), ("-fix", "w0t0p2:BB")):
        (w.sd / f"watcher{sfx}.json").write_text(json.dumps(
            {"pid": 1, "cwd": "/x", "term": "iTerm.app", "term_session": ts, "tty": "", "session_id": ""}))
        (w.sd / f"heartbeat{sfx}").write_text("")
    # scan() alone: the app's own run() renamed, its Cocoa target class (registering it outside an
    # app run hangs osascript) left out
    src = re.sub(r"^ObjC\.registerSubclass\(\{.*?^\}\);$", "", MENUBAR.read_text(), count=1, flags=re.S | re.M)
    js = src.replace("function run(argv) {", "function runApp(argv) {", 1) + (
        f"\nfunction run() {{ dataDirs = [{json.dumps(str(w.home / 'data'))}]; fresh = 2700;"
        " return JSON.stringify(scan().watchers.map(function (x) {"
        " return { key: x.key, sfx: x.sfx, rows: x.rows.map(function (r) { return r.title; }) }; })); }")
    f = w.home / "scan.js"
    f.write_text(js)
    out = subprocess.run(["osascript", "-l", "JavaScript", str(f)], capture_output=True, text=True, timeout=30)
    got = {x["sfx"]: (x["key"], x["rows"]) for x in json.loads(out.stdout)}
    assert got == {"-review": ("s:w0t0p1:AA-review", ["o/r #5"]), "-fix": ("s:w0t0p2:BB-fix", ["o/r #6"])}, out.stderr
