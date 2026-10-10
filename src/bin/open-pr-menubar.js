// macOS menu bar item for `/open-pr:menubar` (a status item needs no permission). It
// polls, in every data directory given, the files the watcher writes:
//   <data>/<repo>/watch/heartbeat    a watcher counts as watching the repo while this is fresh
//   <data>/<repo>/watch/state.json   sessions, one row per PR and role (review | fix); active = not
//                                           finished, working or question; `findings` = a fix row offering
//                                           "Fix now" until a fix session opens; PRs in `hidden` get no row
//   <data>/<repo>/watch/feed.jsonl   notifications; a PR role's latest one, when newer than its
//                                           session's state, is its row's text
//   <data>/<repo>/watch/watcher.json the terminal tab whose watcher watches the repo, and
//                                           the repo_dir/remote "Remove from list" passes to `hide` and
//                                           "Fix now" to `fix-now`
//   <data>/<repo>/watch/stop         written by "Stop"; the watcher's `wait` consumes it
//   <data>/<repo>/watch/quota.json   the host's rate limit as the last poll read it (see QUOTA)
//   <data>/<repo>/settings.json      the repo's watch.poll_interval_seconds (see STALE); the settings
//                                           panel reads and writes it through `open-pr-watch.sh settings`
//   heartbeat, watcher.json, stop and quota.json belong to the wait serving both roles; a wait serving one
//   role has its own, suffixed (heartbeat-fix, watcher-fix.json, stop-fix — see SETS)
//   snooze file                             toasts off until then; the Snooze menu writes it too
// It stays until the user closes it (the menu, or `menubar --close`); watching goes on either way.
// argv: snooze file, pid file, heartbeat age (seconds) past which a repo is not watched, data dirs,
// then the absolute path of open-pr-watch.sh.
// File contents are data only: shown as menu titles, opened when they are http(s) URLs, copied
// as text, written into a .command file or passed to osascript as argv after matching OPEN_CMD,
// passed to osascript as argv after matching TAB_ID, turned into `claude attach` after matching
// SESSION_ID, or passed to open-pr-watch.sh as argv after matching isDir/REMOTE/digits or a
// SETTINGS key and one of its values — never spliced into source.
ObjC.import('Cocoa');

var REFRESH = 3, ROWS = 10, CLIP = 70, HEADER_W = 300;
// A watcher row (a view item, so laid out by hand): height, and where its text starts.
var ROW_H = 36, ROW_TEXT_X = 35;   // icon and text in line with the plain items and PR rows
// Points a menu row spends beside its subtitle: indent, icon, submenu arrow.
var SUBTITLE_PAD = 100;
// The only shape of `open` (see open_cmd in open-pr-watch.sh) allowed into a Terminal script.
var OPEN_CMD = /^[a-z-]+ (attach|resume|-r|--resume|--conversation) [A-Za-z0-9._-]+$/;
// iTerm's unique id (the part of ITERM_SESSION_ID after ':') or a Terminal tab's tty.
var TAB_ID = /^[A-Za-z0-9\/._-]{1,128}$/;
var SESSION_ID = /^[0-9a-f-]{8,64}$/;   // watcher.json session_id: the Claude Code session running the watcher
var REMOTE = /^[A-Za-z0-9._-]+$/;
// The role sets a `wait` serves, by the suffix of its files; one wait per repo and role.
var SETS = [{ sfx: '', roles: ['review', 'fix'] }, { sfx: '-review', roles: ['review'] }, { sfx: '-fix', roles: ['fix'] }];
// A row removed stays out until state.json lists it hidden (hide runs in the background).
var HIDE_PENDING = 30000, FIX_PENDING = 120000;   // ms a click shows before the watcher acts on it
var dataDirs = [], snoozeFile = '', pidFile = '', fresh = 2700, watchScript = '', pendingHide = {}, pendingFix = {};
var item = null, target = null, icons = {}, rowParts = {}, stopParts = {}, litRow = null, menuOpen = false;

// A watcher row says "no poll for …" once its newest heartbeat is older than STALE.factor × the
// interval it polls at: this machine's "Poll every" choice, else the slowest of its repos' setting
// (default STALE.poll) and STALE.idle — an idle repo slows to that (IDLE_POLL in open-pr-watch.sh).
var STALE = { factor: 2, poll: 180, idle: 600 };
var KIND = {   // SF Symbol, label — by a session's last_state (lgtm_chat as lgtm); the symbol alone tells the state, in the menu's own colour
    working:  ['circle.dotted', 'Reviewing'],
    fixing:   ['circle.dotted', 'Fixing'],
    findings: ['wrench.and.screwdriver', 'New findings — Fix now'],
    fix_requested: ['clock', 'Fix requested — starting'],
    fixed:    ['checkmark.circle', 'Fixed'],
    question: ['questionmark.bubble', 'Needs your answer'],
    draft:    ['doc.badge.clock', 'Draft waiting'],
    posted:   ['checkmark.bubble', 'Posted'],
    lgtm:     ['checkmark.seal', 'LGTM'],
    failed:   ['exclamationmark.triangle', 'Failed'],
    stopped:  ['exclamationmark.triangle', 'Stopped'],
    nothing:  ['hourglass', 'Nothing new to review'],
    answered: ['text.bubble', 'Answered']
};
// A row shows whichever happened last: the session's state or the PR's latest feed line (a
// disabled event writes no line, so that line can be older than the state). A line wins through
// the kind of its event: a question asked from inside a still-working session is newer than
// "working", and the row must stop saying "Reviewing".
// A watcher row's terminal icon tint and role word, by the role it serves: review and fix groups
// tell apart at a glance. Its rows belong to it and carry no role.
var ROLE_LOOK = { review: [[0.04, 0.42, 0.9], 'Review'], fix: [[0.8, 0.38, 0.02], 'Fix'], '': [null, 'Review + fix'] };
var ROLE_RANK = { '': 0, '-review': 1, '-fix': 2 };   // a project's watchers: both roles, review, fix
var EVENT_KIND = { review_started: 'working', re_review: 'working', question: 'question',
                   draft_ready: 'draft', posted: 'posted', findings: 'findings', error: 'failed' };
// by TERM_PROGRAM: menu name, bundle id, app a session opens in (see openIn)
var TERMS = {
    'iTerm.app':      ['iTerm', 'com.googlecode.iterm2', 'iTerm'],
    'Apple_Terminal': ['Terminal', 'com.apple.Terminal', 'Terminal'],
    'ghostty':        ['Ghostty', 'com.mitchellh.ghostty', 'Ghostty'],
    'WezTerm':        ['WezTerm', 'com.github.wez.wezterm', 'WezTerm'],
    'WarpTerminal':   ['Warp', 'dev.warp.Warp-Stable', 'Terminal']
};
// `on run argv`: the tab id or command arrives as an argument, never as source. Automation
// permission is asked once; without it the app was already brought forward (goToTab).
// FOCUS returns "found" so a closed tab can be told apart from a found one.
var FOCUS = {
    'iTerm.app': [
        'on run argv',
        'tell application id "com.googlecode.iterm2"',
        'repeat with w in windows',
        'repeat with t in tabs of w',
        'repeat with s in sessions of t',
        'if (unique id of s) is (item 1 of argv) then',
        'select w', 'select t', 'select s', 'activate', 'return "found"',
        'end if', 'end repeat', 'end repeat', 'end repeat', 'end tell', 'end run'],
    'Apple_Terminal': [
        'on run argv',
        'tell application id "com.apple.Terminal"',
        'repeat with w in windows',
        'repeat with t in tabs of w',
        'if (tty of t) is (item 1 of argv) then',
        'set selected of t to true', 'set index of w to 1', 'activate', 'return "found"',
        'end if', 'end repeat', 'end repeat', 'end tell', 'end run']
};
// `write text` types into the user's login shell, so PATH has `claude`.
var ITERM_NEW_TAB = ['on run argv', 'tell application id "com.googlecode.iterm2"', 'activate',
    'if (count of windows) > 0 then', 'tell current window to create tab with default profile',
    'else', 'create window with default profile', 'end if',
    'tell current session of current window to write text (item 1 of argv)', 'end tell', 'end run'];

// docs/images/logo/favicon.svg (viewBox 128×128).
var MOTH = [
    ['#FFC49E', [54,36, 6,12, 2,54, 24,90, 50,84]], ['#FFC49E', [78,84, 104,90, 126,54, 122,12, 74,36]],
    ['#FF8A50', [54,40, 14,28, 10,52, 50,76]],      ['#FF8A50', [78,76, 118,52, 114,28, 74,40]],
    ['#FF8A50', [56,32, 64,27, 30,6, 21,16]],       ['#FF8A50', [107,16, 98,6, 64,27, 72,32]],
    ['#A32C06', [55,26, 73,26, 71,94, 64,110, 57,94]]
];
// Rate limits, from each wait's quota.json (open-pr.sh triggers --quota-file, plus host and at):
// {vendor, host, window, limit, remaining, reset, near_limit, calls, at}. The header shows the
// tightest measured one; "Poll every" estimates requests per hour at each interval as
// Σ calls of each wait's last poll × polls per hour, per host (a GitHub 304 costs nothing, so a
// quiet GitHub repo costs ~0), and marks ⚠ past QUOTA.warn of that host's hourly limit
// (limit × 3600 / window: GitLab counts per minute).
var QUOTA = { warn: 0.5, low: 0.3, critical: 0.1 };
var VENDOR_NAME = { github: 'GitHub', gitlab: 'GitLab', bitbucket: 'Bitbucket' };
var VENDOR_HOST = { github: 'github.com', gitlab: 'gitlab.com', bitbucket: 'bitbucket.org' };
// A watched repo's settings panel, by group: [key, label, options]. options = [[value, segment label,
// tooltip?]…] for a pick, EVENTS for one checkbox per watch.notify.<event>, none for one checkbox. Only
// these keys and values reach `open-pr-watch.sh settings --set` (settingArgs); open-pr.sh checks them again.
var EVENTS = [['review_started', 'Review started'], ['question', 'Question'], ['draft_ready', 'Draft ready'],
              ['posted', 'Posted'], ['re_review', 'Re-review'], ['findings', 'New findings'], ['error', 'Error']];
var SETTINGS = [
    ['Watch', [
        ['watch.max_concurrent', 'Sessions at once', [[1, '1'], [2, '2'], [3, '3'], [5, '5'], [8, '8'], [10, '10']]],
        ['watch.poll_interval_seconds', 'Poll every', [[60, '1m'], [120, '2m'], [180, '3m'], [300, '5m'], [600, '10m']]],
        ['watch.trigger', 'Trigger', [['/open-pr', '/open-pr', 'A comment starting with /open-pr'], ['@me', '@me', 'A mention of you']]],
        ['watch.notify', 'Toasts', EVENTS]]],
    ['Review', [
        ['review.auto_submit_review', 'Post reviews without a draft'],
        ['review.post_lgtm', 'Post LGTM when nothing is found'],
        ['review.auto_resolve_fixed_findings', 'Resolve fixed findings'],
        ['review.review_ci_status', 'Warn about failing CI'],
        ['review.doctor_schedule', 'Doctor every', [['1 weeks', '1w', '1 week'], ['2 weeks', '2w', '2 weeks'], ['1 months', '1m', '1 month'],
                                                    ['3 months', '3m', '3 months'], ['never', 'Never']]]]]
];
// key → the values a click may write, as argv strings
var SETTING_VALUES = {};
SETTINGS.forEach(function (g) { g[1].forEach(function (k) {
    if (k[2] === EVENTS) EVENTS.forEach(function (e) { SETTING_VALUES[k[0] + '.' + e[0]] = ['true', 'false']; });
    else SETTING_VALUES[k[0]] = k[2] ? k[2].map(function (o) { return String(o[0]); }) : ['true', 'false'];
}); });
// <data>/<repo> → { mt: settings.json mtime, dir, remote, conf: what `settings` printed | null, at }
var settingsCache = {}, SETTINGS_RETRY = 60000;   // ms before a failed read is tried again
var EYESPOTS = [[26,32, 38,44, 26,56, 14,44], [114,44, 102,56, 90,44, 102,32]];

// The Stop button over its hand-drawn pill: darkens the pill while the pointer is on it.
ObjC.registerSubclass({
    name: 'OPRStopButton',
    superclass: 'NSButton',
    methods: {
        'mouseEntered:': { types: ['void', ['id']], implementation: function () { hoverStop(this, true); } },
        'mouseExited:': { types: ['void', ['id']], implementation: function () { hoverStop(this, false); } }
    }
});
ObjC.registerSubclass({
    name: 'OPRMenuTarget',
    methods: {
        'tick:': { types: ['void', ['id']], implementation: function () { refresh(); } },
        'openURL:': { types: ['void', ['id']], implementation: function (s) { openURL(unwrapString(s.representedObject)); } },
        'copyText:': { types: ['void', ['id']], implementation: function (s) { copyText(unwrapString(s.representedObject)); } },
        'openTerminal:': { types: ['void', ['id']], implementation: function (s) { openTerminal(parse(unwrapString(s.representedObject))); } },
        // sender: a control inside a watcherRow view; its item carries { go, stop }
        'goRow:': { types: ['void', ['id']], implementation: function (s) { rowAction(s, 'go'); } },
        'stopRow:': { types: ['void', ['id']], implementation: function (s) { rowAction(s, 'stop'); } },
        'menu:willHighlightItem:': { types: ['void', ['id', 'id']], implementation: function (m, mi) { highlightRow(mi); } },
        'menuWillOpen:': { types: ['void', ['id']], implementation: function () { menuOpen = true; } },
        'menuDidClose:': { types: ['void', ['id']], implementation: function () { menuOpen = false; highlightRow(null); } },
        'stopSession:': { types: ['void', ['id']], implementation: function (t) { stopSession(parse(unwrapString(t.userInfo))); } },
        'hide:': { types: ['void', ['id']], implementation: function (s) { hide(parse(unwrapString(s.representedObject))); } },
        'fixNow:': { types: ['void', ['id']], implementation: function (s) { fixNow(parse(unwrapString(s.representedObject))); } },
        'snooze:': { types: ['void', ['id']], implementation: function (s) { snooze(Number(s.tag)); } },
        'poll:': { types: ['void', ['id']], implementation: function (s) { poll(Number(s.tag)); } },
        // sender: a control in a settings panel (see controls)
        'setting:': { types: ['void', ['id']], implementation: function (s) { setSetting(s); } },
        'reveal:': { types: ['void', ['id']], implementation: function (s) { reveal(s); } },
        'quit:': { types: ['void', ['id']], implementation: function () { leave(); } }
    }
});

function run(argv) {
    snoozeFile = argv[0] || ''; pidFile = argv[1] || '';
    fresh = Number(argv[2]) || fresh;
    var rest = argv.slice(3), last = str(rest[rest.length - 1]);
    if (/^\/.*\/open-pr-watch\.sh$/.test(last)) {
        rest.pop();
        if ($.NSFileManager.defaultManager.fileExistsAtPath(last)) watchScript = last;
    }
    dataDirs = rest.filter(function (d) { return typeof d === 'string' && d !== ''; });
    var app = $.NSApplication.sharedApplication;
    app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
    icons.bar = mothImage(18, true);
    icons.header = mothImage(28, false);
    item = $.NSStatusBar.systemStatusBar.statusItemWithLength(-1);   // -1 = variable length
    item.button.setImage(icons.bar);
    item.button.setImagePosition($.NSImageLeft);
    item.button.setToolTip('open-pr');
    target = $.OPRMenuTarget.alloc.init;
    refresh();
    $.NSTimer.scheduledTimerWithTimeIntervalTargetSelectorUserInfoRepeats(REFRESH, target, 'tick:', null, true);
    app.run;
}

// ------------------------------------------------------------- reading ----
function unwrapString(o) { var v = ObjC.unwrap(o); return typeof v === 'string' ? v : ''; }
function readText(path) {
    var s = $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null);
    return s.isNil() ? '' : ObjC.unwrap(s);
}
function listDir(path) {
    var a = $.NSFileManager.defaultManager.contentsOfDirectoryAtPathError(path, null);
    return a.isNil() ? [] : ObjC.deepUnwrap(a);
}
function mtime(path) {   // seconds since 1970, 0 when there is no such file
    var at = $.NSFileManager.defaultManager.attributesOfItemAtPathError(path, null);
    if (at.isNil()) return 0;
    var d = at.objectForKey($.NSFileModificationDate);
    return d.isNil() ? 0 : d.timeIntervalSince1970;
}
function ageSeconds(path) { var t = mtime(path); return t ? Date.now() / 1000 - t : Infinity; }
function parse(text) { try { return JSON.parse(text); } catch (e) { return null; } }
function str(v) { return typeof v === 'string' ? v : ''; }
function p2(n) { return (n < 10 ? '0' : '') + n; }
function hhmm(d) { return p2(d.getHours()) + ':' + p2(d.getMinutes()); }
function when(d) {
    var today = new Date();
    if (d.toDateString() === today.toDateString()) return hhmm(d);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + hhmm(d);
}
function snoozedUntil() {
    var d = new Date(readText(snoozeFile).split('\n')[0].trim());
    return isNaN(d.getTime()) || d.getTime() <= Date.now() ? null : d;
}

function isDir(p) {
    if (typeof p !== 'string' || p.charAt(0) !== '/') return false;
    var at = $.NSFileManager.defaultManager.attributesOfItemAtPathError(p, null);
    return !at.isNil() && ObjC.unwrap(at.objectForKey($.NSFileType)) === ObjC.unwrap($.NSFileTypeDirectory);
}
function basename(p) { return p.replace(/\/+$/, '').split('/').pop() || p; }
// One per watcher tab and role set: the waits of one watcher (one per repo) share its tab.
function watcherOf(w, set) {
    w = w && typeof w === 'object' ? w : {};
    var term = str(w.term), ts = str(w.term_session), tty = str(w.tty), cwd = str(w.cwd), sid = str(w.session_id);
    var t = TERMS[term], tab = ts ? 's:' + ts : tty ? 't:' + tty : typeof w.pid === 'number' ? 'p:' + w.pid : '';
    return { key: tab ? tab + set.sfx : '',
             cwdName: cwd ? basename(cwd) : '', termName: term ? (t ? t[0] : term) : '',
             role: set.sfx.replace('-', ''), start: 0, beat: Infinity, poll: 0,
             term: term, term_session: ts, tty: tty, session_id: sid, app: t ? t[2] : 'Terminal', sfx: set.sfx,
             repos: [], dirs: [], rows: [], settings: [] };
}

function scan() {
    var out = { repos: 0, watchers: [], active: 0, quotas: [] }, byKey = {};
    dataDirs.forEach(function (data) { listDir(data).forEach(function (name) {
        if (typeof name !== 'string' || name.charAt(0) === '.') return;
        var dir = data + '/' + name + '/watch';
        var live = SETS.filter(function (set) { return ageSeconds(dir + '/heartbeat' + set.sfx) <= fresh; });
        if (!live.length) return;
        out.repos++;
        var wj = null, at = {};
        live.forEach(function (set) {
            var j = parse(readText(dir + '/watcher' + set.sfx + '.json')), wr = watcherOf(j, set);
            wj = wj || j;
            if (!byKey[wr.key]) { byKey[wr.key] = wr; out.watchers.push(wr); }
            at[set.sfx] = byKey[wr.key];
            // when this wait started: the watcher record is written at each start
            at[set.sfx].start = Math.max(at[set.sfx].start, Date.now() - ageSeconds(dir + '/watcher' + set.sfx + '.json') * 1000);
            at[set.sfx].repos.push(name);
            at[set.sfx].beat = Math.min(at[set.sfx].beat, ageSeconds(dir + '/heartbeat' + set.sfx));
            at[set.sfx].poll = Math.max(at[set.sfx].poll, repoPoll(data + '/' + name));
            at[set.sfx].dirs.push(dir);
            var q = parse(readText(dir + '/quota' + set.sfx + '.json'));
            if (q && typeof q === 'object' && VENDOR_NAME[q.vendor]) out.quotas.push(q);
        });
        // a row goes to the watcher serving its role, else (no wait serves it) the repo's first one
        var to = function (role) {
            var set = live.filter(function (x) { return x.roles.indexOf(role) >= 0; })[0] || live[0];
            return at[set.sfx];
        };
        // what "Remove from list" hands `hide` for this repo
        var repoDir = wj && typeof wj === 'object' ? str(wj.repo_dir) : '', remote = wj && typeof wj === 'object' ? str(wj.remote) : '';
        var conf = repoSettings(data + '/' + name, repoDir, remote);
        if (conf) live.forEach(function (set) {
            at[set.sfx].settings.push({ name: name, repo: data + '/' + name, conf: conf, doctor: doctorLine(conf), arg: { repo_dir: repoDir, remote: remote } });
        });
        var rows = {};
        var st = parse(readText(dir + '/state.json'));
        var ss = st && typeof st.sessions === 'object' && st.sessions ? st.sessions : {};
        var hidden = {};
        (st && Array.isArray(st.hidden) ? st.hidden : []).forEach(function (n) { if (typeof n === 'number') hidden[n] = true; });
        var gone = function (pr) {
            var at = pendingHide[repoDir + '#' + pr];
            return hidden[pr] || (at && Date.now() - at < HIDE_PENDING);
        };
        var prArg = function (pr) { return JSON.stringify({ repo_dir: repoDir, remote: remote, pr: Number(pr) }); };
        var row = function (repo, pr, role) {
            var k = repo + '#' + pr + ':' + role;
            return rows[k] || (rows[k] = { title: repo + (pr ? ' #' + pr : ''), pr: pr, role: role, session: false, state: '',
                active: false, url: '', open: '', hide: pr ? prArg(pr) : '', fix: '', stateAt: 0 });
        };
        Object.keys(ss).forEach(function (key) {
            var s = ss[key], m = /^([0-9]+):(review|fix)$/.exec(key);
            if (!m || !s || typeof s !== 'object' || gone(m[1])) return;
            var r = row(str(s.repo) || name, m[1], m[2]), state = str(s.last_state);
            r.session = true;
            r.state = m[2] === 'fix' && state === 'working' ? 'fixing' : state;
            r.active = s.finished !== true && (state === 'working' || state === 'question');
            r.url = str(s.url); r.open = str(s.open);
            r.stateAt = ms(s.last_state_at) || Math.max(ms(s.started_at), ms(s.finished_at));
        });
        var fd = st && typeof st.findings === 'object' && st.findings ? st.findings : {};
        Object.keys(fd).forEach(function (pr) {
            var f = fd[pr];
            if (!/^[0-9]+$/.test(pr) || !f || typeof f !== 'object' || gone(pr)) return;
            var r = row(str(f.repo) || name, pr, 'fix'), at = ms(f.at);
            if (at < r.stateAt) return;
            r.session = true; r.state = 'findings'; r.stateAt = at; r.active = true;
            r.findings = counts(f.counts); r.fix = prArg(pr);
            if (!r.url) r.url = str(f.url);
        });
        readText(dir + '/feed.jsonl').split('\n').forEach(function (line) {
            var f = parse(line);
            if (!f || typeof f !== 'object' || !str(f.summary)) return;
            var repo = str(f.repo) || name, pr = typeof f.pr === 'number' ? String(f.pr) : '';
            if (pr && gone(pr)) return;
            var r = row(repo, pr, f.role === 'fix' ? 'fix' : 'review');
            if (!r.feed || str(f.at) >= str(r.feed.at)) r.feed = f;
            if (!r.url) r.url = str(f.url);
        });
        Object.keys(rows).forEach(function (k) {
            var r = rows[k], w = to(r.role);
            // a repo-wide line (a failed start, a poll error) from before this watcher started is over
            if (!r.hide && !r.session && r.feed && ms(r.feed.at) < w.start) return;
            finish(r);
            // clicked: no second Fix now until the fix session shows (or the click is stale)
            var clicked = pendingFix[repoDir + '#' + r.pr];
            if (r.kind === 'findings' && clicked && Date.now() - clicked < FIX_PENDING) {
                r.kind = 'fix_requested'; r.fix = ''; r.active = true;
                r.text = KIND.fix_requested[1] + ' · ' + when(new Date(clicked));
            }
            w.rows.push(r);
        });
    }); });
    out.watchers.forEach(function (w) {
        // review rows, then fix rows; each part: waiting on the user first, then the latest
        w.rows.sort(function (a, b) { return ((a.role === 'fix') - (b.role === 'fix')) || (b.active - a.active) || (b.at - a.at); });
        w.rows = w.rows.slice(0, ROWS);
        w.rows.forEach(function (r) { if (r.active) out.active++; });
    });
    // by project, so a project's review and fix watchers sit together; then role, then tab
    var key = function (w) { return [w.repos.slice().sort().join(',').toLowerCase(), ROLE_RANK[w.sfx], (w.cwdName + ' ' + w.termName).toLowerCase()]; };
    out.watchers.sort(function (a, b) {
        var x = key(a), y = key(b);
        for (var i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
        return 0;
    });
    return out;
}
// One host per vendor + host name.
function hostOf(q) { return q.vendor + '|' + (str(q.host) || VENDOR_HOST[q.vendor]); }
function hostName(q) { var h = str(q.host); return h && h !== VENDOR_HOST[q.vendor] ? h : VENDOR_NAME[q.vendor]; }
function num(v) { return typeof v === 'number' && isFinite(v) && v >= 0 ? v : null; }
// Still the current window: its reset is ahead, or (no reset) it was read within one window.
function current(q) {
    var r = ms(q.reset), win = num(q.window) || 3600;
    return r ? r > Date.now() : Date.now() - ms(q.at) < win * 1000;
}
// The tightest measured quota → { text, level: '' | 'low' | 'critical' }, or null.
function gauge(quotas) {
    var best = null;
    quotas.forEach(function (q) {
        if (!current(q)) return;
        var l = num(q.limit), r = num(q.remaining);
        var g = l && r !== null ? { ratio: r / l, text: hostName(q) + ' API ' + r.toLocaleString('en-US') + '/' + l.toLocaleString('en-US') + ' left' }
              : q.near_limit === true ? { ratio: QUOTA.low - 0.01, text: hostName(q) + ' API near its limit' } : null;
        if (g && (!best || g.ratio < best.ratio)) best = g;
    });
    if (!best) return null;
    best.level = best.ratio < QUOTA.critical ? 'critical' : best.ratio < QUOTA.low ? 'low' : '';
    return best;
}
// Requests per hour polling every `seconds` → ' ≈N/h', plus ' ⚠' past QUOTA.warn of the
// host's hourly limit; the busiest host speaks. '' with no quota read yet.
function estimate(quotas, seconds) {
    var hosts = {};
    quotas.forEach(function (q) {
        var h = hosts[hostOf(q)] || (hosts[hostOf(q)] = { calls: 0, hourly: null });
        h.calls += num(q.calls) || 0;
        var l = num(q.limit), w = num(q.window);
        if (l && w) h.hourly = Math.max(h.hourly || 0, l * 3600 / w);
    });
    var worst = null;
    Object.keys(hosts).forEach(function (k) {
        var h = hosts[k], perHour = Math.round(h.calls * 3600 / seconds), share = h.hourly ? perHour / h.hourly : 0;
        if (!worst || share > worst.share || (share === worst.share && perHour > worst.perHour)) worst = { perHour: perHour, share: share };
    });
    return worst ? '  ≈' + worst.perHour.toLocaleString('en-US') + '/h' + (worst.share > QUOTA.warn ? ' ⚠' : '') : '';
}
// The repo's settings as `open-pr-watch.sh settings` prints them (read-time defaults applied), read
// again only once settings.json changes; null when its watcher left no repo_dir to name it by.
function repoSettings(repo, dir, remote) {
    if (!watchScript || !isDir(dir) || (remote && !REMOTE.test(remote))) return null;
    var mt = mtime(repo + '/settings.json'), c = settingsCache[repo];
    if (c && c.mt === mt && c.dir === dir && c.remote === remote && (c.conf || Date.now() - c.at < SETTINGS_RETRY)) return c.conf;
    var conf = parse(output('/bin/sh', repoArgs({ repo_dir: dir, remote: remote }, 'settings')) || '');
    conf = conf && typeof conf === 'object' && conf.watch && conf.review ? conf : null;
    settingsCache[repo] = { mt: mt, dir: dir, remote: remote, conf: conf, at: Date.now() };
    return conf;
}
function valueAt(conf, key) {
    return key.split('.').reduce(function (o, k) { return o && typeof o === 'object' ? o[k] : undefined; }, conf);
}
// "Doctor: <when it last ran> · next in N days" (or due now), from open-pr.sh's doctor_next_at.
function doctorLine(c) {
    var r = c.review || {}, last = ms(r.doctored_at), next = ms(c.doctor_next_at);
    if (r.doctored !== true) return 'Doctor: never run';
    var head = 'Doctor: ' + (last ? new Date(last).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) + ' · ' : '');
    if (r.doctor_schedule === 'never') return head + 'not scheduled';
    if (!next || next <= Date.now()) return head + 'due now';
    var n = Math.ceil((next - Date.now()) / 86400000);
    return head + 'next in ' + n + (n === 1 ? ' day' : ' days');
}
function repoPoll(repoDir) {
    var st = parse(readText(repoDir + '/settings.json')), v = st && st.watch ? st.watch.poll_interval_seconds : null;
    return typeof v === 'number' && v >= 1 ? v : STALE.poll;
}
function age(sec) { return sec < 3600 ? Math.floor(sec / 60) + 'm' : Math.floor(sec / 3600) + 'h'; }
// A watcher row's subtitle as [text, warn] parts: role, terminal, the folder it runs in when that
// is not its one repo, then when it last polled.
function watcherLine(w) {
    var head = (ROLE_LOOK[w.role] || ROLE_LOOK[''])[1] + (w.termName ? ' · ' + w.termName : '') +
               (w.cwdName && !(w.repos.length === 1 && w.repos[0] === w.cwdName) ? ' · in ' + w.cwdName : '');
    if (!isFinite(w.beat)) return [[head, false]];
    var every = pollSeconds() || Math.max(w.poll, STALE.idle);
    if (w.beat > STALE.factor * every) return [[head + ' · ', false], ['no poll for ' + age(w.beat) + ' — check the watcher tab', true]];
    return [[head + ' · polled ' + (w.beat < 60 ? 'just now' : age(w.beat) + ' ago'), false]];
}
function ms(t) { var n = new Date(str(t)).getTime(); return isNaN(n) ? 0 : n; }
// findings counts {"🟠": 2} → "2 🟠 · 4 🔵", severity order
function counts(c) {
    c = c && typeof c === 'object' ? c : {};
    return ['🔴', '🟠', '🔵', '📝'].filter(function (e) { return typeof c[e] === 'number' && c[e] > 0; })
        .map(function (e) { return c[e] + ' ' + e; }).join(' · ');
}
// A row's kind (key of KIND), text and latest activity. Same second: the line wins, its summary
// says more than the state label.
function finish(r) {
    var f = r.feed, fat = f ? ms(f.at) : 0, kind;
    if (r.session && (!f || fat < r.stateAt)) {
        f = null;
        kind = r.state === 'lgtm_chat' ? 'lgtm' : r.state;
    } else kind = f ? EVENT_KIND[str(f.event)] || '' : '';
    // A posted review with no findings: its summary starts with LGTM.
    if (kind === 'posted' && f && /^LGTM\b/i.test(str(f.summary))) kind = 'lgtm';
    // Counted and listed first like an active session: it waits on the user.
    if (f && kind === 'question') r.active = true;
    var at = Math.max(r.stateAt, fat);
    r.kind = kind;
    r.at = at;
    // a feed line saying "fixed" or "posted" after the findings ends the Fix now offer
    if (kind !== 'findings') r.fix = '';
    else if (!r.fix && r.hide) r.fix = r.hide;
    var label = KIND[kind] ? KIND[kind][1] : kind;
    if (kind === 'findings' && r.findings) label = r.findings + ' — Fix now';
    r.text = (f ? str(f.summary) : label) + (at ? ' · ' + when(new Date(at)) : '');
    return r;
}

// -------------------------------------------------------------- images ----
function hexColor(h) {
    var n = parseInt(h.slice(1), 16);
    return $.NSColor.colorWithSRGBRedGreenBlueAlpha((n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255, 1);
}
function rgb(c) { return $.NSColor.colorWithSRGBRedGreenBlueAlpha(c[0], c[1], c[2], 1); }
function polygon(pts, k) {   // SVG y grows downward, AppKit's upward
    var p = $.NSBezierPath.bezierPath;
    for (var i = 0; i < pts.length; i += 2) {
        var pt = $.NSMakePoint(pts[i] * k, (128 - pts[i + 1]) * k);
        if (i === 0) p.moveToPoint(pt); else p.lineToPoint(pt);
    }
    p.closePath;
    return p;
}
// 3× bitmap for sharpness. A template image is one flat colour the menu bar tints, so the
// eyespots are cleared to holes to stay visible.
function mothImage(pt, template) {
    var px = pt * 3, k = px / 128;
    var rep = $.NSBitmapImageRep.alloc.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(
        null, px, px, 8, 4, true, false, 'NSDeviceRGBColorSpace', 0, 0);
    var ctx = $.NSGraphicsContext.graphicsContextWithBitmapImageRep(rep);
    $.NSGraphicsContext.saveGraphicsState;
    $.NSGraphicsContext.setCurrentContext(ctx);
    MOTH.forEach(function (m) {
        (template ? $.NSColor.blackColor : hexColor(m[0])).set;
        polygon(m[1], k).fill;
    });
    if (template) ctx.setCompositingOperation($.NSCompositingOperationClear);
    else hexColor('#A32C06').set;
    EYESPOTS.forEach(function (e) { polygon(e, k).fill; });
    ctx.flushGraphics;
    $.NSGraphicsContext.restoreGraphicsState;
    rep.setSize($.NSMakeSize(pt, pt));
    var img = $.NSImage.alloc.initWithSize($.NSMakeSize(pt, pt));
    img.addRepresentation(rep);
    img.setTemplate(template);
    return img;
}
// A template symbol: drawn in the menu's text colour, as the plain items' icons are.
// Description '': JXA passes null as NSNull, which AppKit rejects; VoiceOver reads the item title.
function symbol(spec) {
    if (icons[spec[0]]) return icons[spec[0]];
    var img = $.NSImage.imageWithSystemSymbolNameAccessibilityDescription(spec[0], '');
    if (img.isNil()) return null;
    img.setTemplate(true);
    return (icons[spec[0]] = img);
}

function blank() {
    return icons.blank || (icons.blank = $.NSImage.alloc.initWithSize($.NSMakeSize(16, 16)));
}

// ---------------------------------------------------------------- menu ----
// A settings read waits on a task while the run loop turns, so the timer can fire inside it. An open
// menu is left as it is: a settings panel writes while it stays open, and updates its own controls.
var refreshing = false;
function refresh() {
    if (refreshing || menuOpen) return;
    refreshing = true;
    try {
        var s = scan();
        item.button.setTitle(s.active ? String(s.active) : '');
        item.setMenu(build(s));
    } finally { refreshing = false; }
}

function clip(t) { return t.length > CLIP ? t.slice(0, CLIP - 1) + '…' : t; }
// Auto-enabling greys out a submenu parent that has no action.
function newMenu(title) {
    var m = $.NSMenu.alloc.initWithTitle(title);
    m.setAutoenablesItems(false);
    return m;
}
function add(menu, title, action, value, tag) {
    var mi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(clip(title), action || null, '');
    mi.setEnabled(!!action);
    if (action) {
        mi.setTarget(target);
        if (value !== undefined) mi.setRepresentedObject($(value));
        if (tag !== undefined) mi.setTag(tag);
    }
    menu.addItem(mi);
    return mi;
}
// Native subtitle from macOS 14.4; before that, the same two lines as an attributed title.
// The menu does not widen for a native subtitle, which then runs under the submenu arrow.
function subtitle(mi, text) {
    if (mi.respondsToSelector('setSubtitle:')) {
        var menu = mi.menu, w = $(clip(text)).sizeWithAttributes($({ NSFont: $.NSFont.menuFontOfSize(11) })).width;
        if (!menu.isNil() && w + SUBTITLE_PAD > menu.minimumWidth) menu.setMinimumWidth(w + SUBTITLE_PAD);
        mi.setSubtitle(clip(text));
        return;
    }
    var s = $.NSMutableAttributedString.alloc.initWithStringAttributes(ObjC.unwrap(mi.title) + '\n',
        $({ NSFont: $.NSFont.menuFontOfSize(0) }));
    s.appendAttributedString($.NSAttributedString.alloc.initWithStringAttributes(clip(text),
        $({ NSFont: $.NSFont.menuFontOfSize(11), NSColor: $.NSColor.secondaryLabelColor })));
    mi.setAttributedTitle(s);
}
function label(text, font, color, x, y) {
    var f = $.NSTextField.labelWithString(text);
    f.setFont(font);
    f.setTextColor(color);
    f.setLineBreakMode($.NSLineBreakByTruncatingTail);
    f.setFrame($.NSMakeRect(x, y, HEADER_W - x - 14, 17));
    return f;
}
function headerView(repos, watchers, until, quota) {
    var up = quota ? 14 : 0;   // a third line for the quota gauge
    var v = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, HEADER_W, 48 + up));
    var iv = $.NSImageView.imageViewWithImage(icons.header);
    iv.setFrame($.NSMakeRect(14, 10 + up / 2, 28, 28));
    v.addSubview(iv);
    v.addSubview(label('open-pr', $.NSFont.boldSystemFontOfSize(13), $.NSColor.labelColor, 52, 24 + up));
    var line = (repos ? 'Watching ' + repos + (repos === 1 ? ' repo' : ' repos') : 'Not watching') + ' · ' +
               (watchers > 1 ? watchers + ' watchers · ' : '') +
               (until ? 'toasts off until ' + hhmm(until) : 'toasts on');
    v.addSubview(label(line, $.NSFont.systemFontOfSize(11), $.NSColor.secondaryLabelColor, 52, 7 + up));
    if (quota) {
        var c = quota.level === 'critical' ? $.NSColor.systemRedColor
              : quota.level === 'low' ? $.NSColor.systemOrangeColor : $.NSColor.secondaryLabelColor;
        v.addSubview(label(quota.text, $.NSFont.systemFontOfSize(11), c, 52, 6));
    }
    return v;
}

// A view item gets neither the item's action nor the menu's highlight: a transparent button over
// the left part takes the click, and the menu delegate (highlightRow) shows the highlight.
function watcherRow(title, parts, canGo, role) {
    // Drawn by hand (a pill + its word) under a transparent button: a bezel goes dark on the
    // selection colour, and its title with it.
    var stopFont = $.NSFont.systemFontOfSizeWeight($.NSFont.smallSystemFontSize, $.NSFontWeightMedium);
    var bw = Math.ceil($('Stop').sizeWithAttributes($({ NSFont: stopFont })).width) + 20, bh = 20, attrs = function (pt) { return $({ NSFont: $.NSFont.menuFontOfSize(pt) }); };
    var look = ROLE_LOOK[role] || ROLE_LOOK[''], tint = look[0] ? rgb(look[0]) : $.NSColor.labelColor;
    var sub = parts.map(function (x) { return x[0]; }).join('');
    var tw = Math.max($(clip(title)).sizeWithAttributes(attrs(0)).width, $(clip(sub)).sizeWithAttributes(attrs(11)).width);
    var w = Math.max(HEADER_W, ROW_TEXT_X + Math.ceil(tw) + 20 + bw + 14);   // 8 pt of it: the field's own inset
    var v = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, w, ROW_H));
    v.setAutoresizingMask($.NSViewWidthSizable);
    var bg = $.NSVisualEffectView.alloc.initWithFrame($.NSMakeRect(5, 0, w - 10, ROW_H));
    bg.setMaterial($.NSVisualEffectMaterialSelection);
    bg.setState($.NSVisualEffectStateActive);
    bg.setEmphasized(true);
    bg.setWantsLayer(true);
    bg.layer.setCornerRadius(4);
    bg.setAutoresizingMask($.NSViewWidthSizable);
    bg.setHidden(true);
    v.addSubview(bg);
    var iv = $.NSImageView.imageViewWithImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription('terminal', ''));
    iv.setContentTintColor(tint);
    iv.setFrame($.NSMakeRect(ROW_TEXT_X - 20, (ROW_H - 16) / 2, 16, 16));
    v.addSubview(iv);
    var right = w - ROW_TEXT_X - bw - 26;
    var t = label(clip(title), $.NSFont.menuFontOfSize(0), $.NSColor.labelColor, ROW_TEXT_X, ROW_H / 2);
    var st = label(clip(sub), $.NSFont.menuFontOfSize(11), $.NSColor.secondaryLabelColor, ROW_TEXT_X, ROW_H / 2 - 15);
    [t, st].forEach(function (f) {
        f.setFrame($.NSMakeRect(ROW_TEXT_X, f.frame.origin.y, right, 17));
        f.setAutoresizingMask($.NSViewWidthSizable);
        v.addSubview(f);
    });
    if (canGo) {
        var hit = $.NSButton.buttonWithTitleTargetAction('', target, 'goRow:');
        hit.setTransparent(true);
        hit.setFrame($.NSMakeRect(0, 0, w - bw - 18, ROW_H));
        hit.setAutoresizingMask($.NSViewWidthSizable);
        hit.setToolTip('Go to watcher tab');
        v.addSubview(hit);
    } else {
        t.setTextColor($.NSColor.disabledControlTextColor);
    }
    var pill = $.NSBox.alloc.initWithFrame($.NSMakeRect(w - bw - 14, (ROW_H - bh) / 2, bw, bh));
    pill.setBoxType($.NSBoxCustom);
    pill.setTitlePosition($.NSNoTitle);
    pill.setBorderWidth(0);
    pill.setCornerRadius(bh / 2);
    pill.setAutoresizingMask($.NSViewMinXMargin);
    v.addSubview(pill);
    var word = $.NSTextField.labelWithString('Stop');
    word.setFont(stopFont);
    var ww = Math.ceil(word.intrinsicContentSize.width) + 4;   // room for the last glyph's overhang
    word.setFrame($.NSMakeRect(w - bw - 14 + (bw - ww) / 2, (ROW_H - 16) / 2, ww, 16));
    word.setAutoresizingMask($.NSViewMinXMargin);
    v.addSubview(word);
    var stop = $.OPRStopButton.alloc.initWithFrame(pill.frame);
    stop.setTitle('');
    stop.setTarget(target);
    stop.setAction('stopRow:');
    stop.setTransparent(true);
    // InVisibleRect: the area follows the button; ActiveAlways: a menu window is never key
    stop.addTrackingArea($.NSTrackingArea.alloc.initWithRectOptionsOwnerUserInfo($.NSZeroRect,
        $.NSTrackingMouseEnteredAndExited | $.NSTrackingActiveAlways | $.NSTrackingInVisibleRect, stop, null));
    stop.setAutoresizingMask($.NSViewMinXMargin);
    stop.setToolTip('Stop watcher');
    v.addSubview(stop);
    // a warning part in orange: an attributed string, built up piece by piece (JXA does not bridge
    // NSAttributedString's initWithString… initializers)
    var subAttr = null;
    if (parts.some(function (x) { return x[1]; })) {
        subAttr = $.NSMutableAttributedString.alloc.init;
        // an attributed value brings its own line breaking: wrapped, a cut line falls out of sight
        var ps = $.NSMutableParagraphStyle.alloc.init;
        ps.setLineBreakMode($.NSLineBreakByTruncatingTail);
        var at = 0;
        parts.forEach(function (x) {
            var text = x[0];   // a long line is cut by the field (truncating tail)
            subAttr.mutableString.appendString(text);
            var r = $.NSMakeRange(at, text.length);
            subAttr.addAttributeValueRange('NSFont', $.NSFont.menuFontOfSize(11), r);
            subAttr.addAttributeValueRange('NSColor', x[1] ? $.NSColor.systemOrangeColor : $.NSColor.secondaryLabelColor, r);
            subAttr.addAttributeValueRange('NSParagraphStyle', ps, r);
            at += text.length;
        });
        st.setAttributedStringValue(subAttr);
    }
    rowParts[v.hash] = { bg: bg, icon: iv, tint: tint, title: t, sub: st, subText: sub, subAttr: subAttr, pill: pill, word: word, canGo: canGo };
    rowParts[v.hash].stopHash = stop.hash;
    stopParts[stop.hash] = rowParts[v.hash];
    paintStop(rowParts[v.hash], false);
    return v;
}
function highlightRow(mi) {
    if (litRow) paintRow(litRow, false);
    litRow = null;
    var v = mi && !mi.isNil() ? mi.view : null;
    var p = v && !v.isNil() ? rowParts[v.hash] : null;
    if (p && p.canGo) { litRow = p; paintRow(p, true); }
}
function paintRow(p, on) {
    p.bg.setHidden(!on);
    p.title.setTextColor(on ? $.NSColor.selectedMenuItemTextColor : $.NSColor.labelColor);
    if (on || !p.subAttr) {
        if (p.subAttr) p.sub.setStringValue(p.subText);
        p.sub.setTextColor(on ? $.NSColor.selectedMenuItemTextColor : $.NSColor.secondaryLabelColor);
    } else p.sub.setAttributedStringValue(p.subAttr);
    p.icon.setContentTintColor(on ? $.NSColor.selectedMenuItemTextColor : p.tint);
    paintStop(p, on);
}
// on: its row is highlighted. A pointer on the pill darkens it, as a pressed-looking button does.
function paintStop(p, on) {
    p.lit = on;
    p.pill.setFillColor(p.hover ? $.NSColor.colorWithWhiteAlpha(0, on ? 0.28 : 0.22)
                                : on ? $.NSColor.colorWithWhiteAlpha(1, 0.28) : $.NSColor.colorWithWhiteAlpha(0.5, 0.18));
    p.word.setTextColor(on ? $.NSColor.whiteColor : $.NSColor.labelColor);
}
function hoverStop(button, on) {
    var p = stopParts[button.hash];
    if (!p) return;
    p.hover = on;
    paintStop(p, !!p.lit);
}
function rowAction(sender, which) {
    var mi = sender.enclosingMenuItem;
    if (mi.isNil()) return;
    var o = parse(unwrapString(mi.representedObject));
    if (!mi.menu.isNil()) mi.menu.cancelTracking;
    if (!o) return;
    if (which === 'go') goToTab(o.go);
    else stopWatcher(o.stop);
}

function build(s) {
    var m = newMenu('open-pr');
    m.setDelegate(target);
    rowParts = {}; stopParts = {}; litRow = null; controls = {};
    var until = snoozedUntil();
    var head = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent('open-pr', null, '');
    head.setView(headerView(s.repos, s.watchers.length, until, gauge(s.quotas)));
    m.addItem(head);

    // no section title: a menu indents the items under one
    m.addItem($.NSMenuItem.separatorItem);
    if (!s.watchers.length) add(m, 'Nothing yet');
    s.watchers.forEach(function (w, i) {
        if (i) m.addItem($.NSMenuItem.separatorItem);   // one block per watcher
        // A record from before watcher.json existed has no tab to show.
        if (w.key) {
            var go = TERMS[w.term] || SESSION_ID.test(w.session_id)
                ? { term: w.term, term_session: w.term_session, tty: w.tty, session_id: w.session_id } : null;
            var wt = w.repos.join(', ');
            var wi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(wt, null, '');
            wi.setRepresentedObject($(JSON.stringify({ go: go, stop: { dirs: w.dirs, sfx: w.sfx, session_id: w.session_id } })));
            wi.setView(watcherRow(wt, watcherLine(w), !!go, w.role));
            // hovering the row opens its settings: one repo's panel, or one item per repo leading to its own
            if (w.settings.length === 1) wi.setSubmenu(panelMenu(w.settings[0], s.quotas));
            else if (w.settings.length) {
                var sm = newMenu(wt);
                w.settings.forEach(function (x) { var ri = add(sm, x.name); ri.setSubmenu(panelMenu(x, s.quotas)); ri.setEnabled(true); });
                wi.setSubmenu(sm);
            }
            m.addItem(wi);
        }
        // a blank image of an icon's size puts the text in the rows' text column
        if (!w.rows.length) add(m, 'No pull requests yet').setImage(blank());
        w.rows.forEach(function (x) {
            var spec = KIND[x.kind];
            var mi = add(m, x.title, isURL(x.url) ? 'openURL:' : null, x.url);
            subtitle(mi, x.text);
            if (spec) mi.setImage(symbol(spec));
            // Offered in every state: `open` also reopens a finished or stopped session.
            var sub = newMenu(x.title);
            if (x.fix && prArgs(parse(x.fix), 'fix-now')) add(sub, 'Fix now', 'fixNow:', x.fix);
            if (isURL(x.url)) add(sub, 'Open pull request', 'openURL:', x.url);
            if (OPEN_CMD.test(x.open)) add(sub, 'Open session in ' + w.app, 'openTerminal:', JSON.stringify({ open: x.open, term: w.term }));
            if (x.open) add(sub, 'Copy command  ' + x.open, 'copyText:', x.open);
            if (x.hide && prArgs(parse(x.hide), 'hide')) add(sub, 'Remove from list', 'hide:', x.hide);
            if (sub.numberOfItems > 0) { mi.setSubmenu(sub); mi.setEnabled(true); }
        });
    });

    m.addItem($.NSMenuItem.separatorItem);
    var sub = newMenu('Snooze toasts');
    if (until) add(sub, 'Off until ' + when(until)).setState($.NSControlStateValueOn);
    add(sub, '30 minutes', 'snooze:', undefined, 30);
    add(sub, '1 hour', 'snooze:', undefined, 60);
    add(sub, 'Until 9:00 tomorrow', 'snooze:', undefined, -1);
    sub.addItem($.NSMenuItem.separatorItem);
    if (until) add(sub, 'Turn toasts back on', 'snooze:', undefined, 0);
    else add(sub, 'Toasts on').setState($.NSControlStateValueOn);
    var cur = pollSeconds(), ps = newMenu('Poll every');
    [[15, '15 seconds'], [30, '30 seconds'], [60, '1 minute'], [120, '2 minutes'], [180, '3 minutes'],
     [300, '5 minutes'], [600, '10 minutes']].forEach(function (o) {
        var mi = add(ps, o[1] + estimate(s.quotas, o[0]), 'poll:', undefined, o[0]);
        mi.setState(cur === o[0] ? $.NSControlStateValueOn : $.NSControlStateValueOff);
        if (s.quotas.length) mi.setToolTip('API requests per hour at this interval, from the last poll of each repo; ⚠ = over half the host\'s hourly limit');
    });
    ps.addItem($.NSMenuItem.separatorItem);
    add(ps, 'Repo setting', 'poll:', undefined, 0).setState(cur ? $.NSControlStateValueOff : $.NSControlStateValueOn);
    var pi = add(m, 'Poll every');
    pi.setSubmenu(ps);
    pi.setEnabled(true);
    pi.setImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription('arrow.clockwise', ''));
    var sn = add(m, 'Snooze toasts');
    sn.setSubmenu(sub);
    sn.setEnabled(true);
    sn.setImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription(until ? 'bell.slash' : 'bell', ''));
    add(m, 'Quit menu bar', 'quit:').setImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription('power', ''));
    return m;
}

function span(sec) { return sec % 60 ? sec + ' seconds' : sec / 60 + (sec === 60 ? ' minute' : ' minutes'); }
// A settings panel's controls by hash: { p: its panel, key, view, values: what each segment writes }
// for a pick, the same without values for a checkbox, { reveal: its settings.json } for its button.
var controls = {};
var PANEL = { pad: 16, label: 120, row: 30, check: 22 };   // points: side padding, label column, row steps
// x: { name, repo, conf, arg }. One view item: a click on a control inside it leaves the menu open,
// where a plain item's action closes it.
function panelMenu(x, quotas) {
    var m = newMenu(x.name), mi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(x.name, null, '');
    mi.setView(settingsPanel(x, quotas));
    m.addItem(mi);
    return m;
}
function text(t, font, color) {
    var f = $.NSTextField.labelWithString(t);
    f.setFont(font);
    f.setTextColor(color);
    f.setLineBreakMode($.NSLineBreakByTruncatingTail);
    return f;
}
function control(p, v, key, values) {
    var c = controls[v.hash] = { p: p, key: key, view: v, values: values };
    p.ctl.push(c);
    return v;
}
function checkbox(p, key, title) { return control(p, $.NSButton.checkboxWithTitleTargetAction(title, target, 'setting:'), key); }
// Laid out top-down as [view, x, top, width, height]; width undefined: its fitting width, 0: to the right
// padding, -1: to the right padding, at least its fitting width;
// frames are set once the size is known, as AppKit's y grows upward.
function settingsPanel(x, quotas) {
    var p = { x: x, quotas: quotas, ctl: [] }, at = [], top = 10, pad = PANEL.pad, col = pad + PANEL.label;
    var put = function (v, l, wd, h, dy) { at.push([v, l, top + (dy || 0), wd, h]); return v; };
    var second = $.NSColor.secondaryLabelColor, small = $.NSFont.systemFontOfSize(11);
    SETTINGS.forEach(function (g, i) {
        put(text(g[0], $.NSFont.systemFontOfSizeWeight(11, $.NSFontWeightSemibold), second), pad, undefined, 14, i ? 6 : 0);
        top += i ? 26 : 20;
        g[1].forEach(function (k) {
            if (!k[2]) { put(checkbox(p, k[0], k[1]), pad, undefined, 18); top += PANEL.check; return; }
            put(text(k[1], $.NSFont.systemFontOfSize(13), $.NSColor.labelColor), pad, PANEL.label - 8, 17, 3);
            if (k[2] === EVENTS) {   // two columns, row by row
                var boxes = EVENTS.map(function (e) { var b = checkbox(p, k[0] + '.' + e[0], e[1]); b.sizeToFit; return b; });
                var cw = Math.max.apply(null, boxes.map(function (b) { return b.frame.size.width; }));
                boxes.forEach(function (b, j) { put(b, col + (j % 2) * (cw + 12), cw, 18, 2 + Math.floor(j / 2) * PANEL.check); });
                top += Math.ceil(EVENTS.length / 2) * PANEL.check + 4;
                return;
            }
            var seg = $.NSSegmentedControl.segmentedControlWithLabelsTrackingModeTargetAction(
                $(k[2].map(function (o) { return o[1]; })), $.NSSegmentSwitchTrackingSelectOne, target, 'setting:');
            k[2].forEach(function (o, j) {
                var tip = k[0] === 'watch.poll_interval_seconds' ? span(o[0]) + estimate(quotas, o[0]) : o[2];
                if (tip) seg.setToolTipForSegment(tip, j);
            });
            put(control(p, seg, k[0], k[2].map(function (o) { return o[0]; })), col, undefined, 24);
            top += PANEL.row;
            if (k[0] === 'watch.poll_interval_seconds') { p.cost = put(text('', small, second), col, -1, 14, -4); top += 14; }
        });
    });
    var sep = $.NSBox.alloc.initWithFrame($.NSMakeRect(0, 0, 10, 1));
    sep.setBoxType($.NSBoxSeparator);
    put(sep, pad, 0, 1, 2);
    top += 12;
    var steth = $.NSImageView.imageViewWithImage(symbol(['stethoscope']));
    steth.setContentTintColor(second);
    put(steth, pad, 14, 14, 1);
    p.doctor = put(text('', small, second), pad + 20, -1, 14, 1);
    top += 22;
    p.reveal = $.NSButton.buttonWithTitleTargetAction('Show settings file', target, 'reveal:');
    p.reveal.setControlSize($.NSControlSizeSmall);
    p.reveal.setFont($.NSFont.systemFontOfSize($.NSFont.smallSystemFontSize));
    controls[p.reveal.hash] = { reveal: x.repo + '/settings.json' };
    put(p.reveal, pad - 6, undefined, 22);   // a bezel's own inset: its border lines up with the text above
    top += 30;
    showPanel(p, x.conf);   // first, so a segment shown only for a value set in a chat is measured
    var w = 0;
    at.forEach(function (a) {
        if (a[3] === undefined || a[3] < 0) { a[0].sizeToFit; w = Math.max(w, a[1] + a[0].frame.size.width + pad); }
        if (a[3] === undefined) a[3] = a[0].frame.size.width;
        else if (a[3] > 0) w = Math.max(w, a[1] + a[3] + pad);
    });
    var v = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, w, top));
    at.forEach(function (a) {
        a[0].setFrame($.NSMakeRect(a[1], top - a[2] - a[4], a[3] > 0 ? a[3] : w - a[1] - pad, a[4]));
        v.addSubview(a[0]);
    });
    return v;
}
// A value no control offers (set in a chat): an extra segment, selected and disabled.
function shortValue(key, v) {
    return key === 'watch.poll_interval_seconds' && typeof v === 'number' ? (v % 60 ? v + 's' : v / 60 + 'm') : String(v);
}
// Sets every control of panel p from conf, the repo's settings as `settings` printed them.
function showPanel(p, conf) {
    p.conf = conf;
    p.ctl.forEach(function (c) {
        var cur = valueAt(conf, c.key), v = c.view;
        if (!c.values) {
            // review_ci_status unset: on when the PR has CI checks, decided per review
            v.setAllowsMixedState(cur === undefined);
            v.setState(cur === undefined ? $.NSControlStateValueMixed : cur === true ? $.NSControlStateValueOn : $.NSControlStateValueOff);
            v.setToolTip(cur === undefined ? 'Not set: on when the pull request has CI checks' : '');
            return;
        }
        var i = c.values.indexOf(cur), n = c.values.length, extra = i < 0 && cur !== undefined && cur !== null;
        v.setSegmentCount(n + (extra ? 1 : 0));
        if (extra) {
            v.setLabelForSegment(shortValue(c.key, cur), n);
            v.setEnabledForSegment(false, n);
            v.setToolTipForSegment('Set in a chat', n);
        }
        v.setSelectedSegment(extra ? n : i);
        v.sizeToFit;
    });
    if (p.cost) {
        var sec = pollSeconds(), e = typeof valueAt(conf, 'watch.poll_interval_seconds') === 'number' ? estimate(p.quotas, valueAt(conf, 'watch.poll_interval_seconds')).trim() : '';
        p.cost.setStringValue(sec ? 'This machine polls every ' + span(sec) + ' (Poll every)' : e ? 'API cost ' + e : '');
        p.cost.setTextColor(!sec && / ⚠$/.test(e) ? $.NSColor.systemOrangeColor : $.NSColor.secondaryLabelColor);
    }
    p.doctor.setStringValue(doctorLine(conf));
    p.reveal.setEnabled(!!revealable(p.x.repo + '/settings.json'));
}

// ------------------------------------------------------------- actions ----
function isURL(u) { return /^https?:\/\/\S+$/.test(u); }
function openURL(u) { if (isURL(u)) $.NSWorkspace.sharedWorkspace.openURL($.NSURL.URLWithString(u)); }
function copyText(t) {
    if (!t) return;
    var pb = $.NSPasteboard.generalPasteboard;
    pb.clearContents;
    pb.setStringForType($(t), $.NSPasteboardTypeString);
}
function openTerminal(o) { if (o) openIn(str(o.term), str(o.open), snoozeFile); }
// Runs cmd in a new tab of the terminal `term` names. iTerm does not run a .command file handed to
// it (LaunchServices then falls back to Terminal), so it gets the command over AppleScript;
// Terminal opens the file via LaunchServices, which needs no Automation permission; Ghostty and
// WezTerm take it as a program; any other terminal ⇒ Terminal. The .command file sits next to
// the snooze file.
function openIn(term, cmd, snooze) {
    if (!OPEN_CMD.test(cmd)) return false;
    // no terminal recorded: prefer iTerm when it runs, as the user then works in it
    if (!term && $.NSRunningApplication.runningApplicationsWithBundleIdentifier('com.googlecode.iterm2').count > 0) term = 'iTerm.app';
    if (term === 'iTerm.app') return spawn('/usr/bin/osascript', script(ITERM_NEW_TAB).concat([cmd]));
    if (!snooze) return false;
    var dir = snooze.replace(/\/[^\/]*$/, '') + '/sessions', fm = $.NSFileManager.defaultManager;
    fm.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(dir, true, $({}), null);
    var path = dir + '/' + cmd.split(' ').pop() + '.command';
    if (!$('#!/bin/sh\n' + cmd + '\n').writeToFileAtomicallyEncodingError(path, true, $.NSUTF8StringEncoding, null)) return false;
    fm.setAttributesOfItemAtPathError($({ NSFilePosixPermissions: 493 }), path, null);   // 0755
    if (term === 'ghostty') return spawn('/usr/bin/open', ['-na', 'Ghostty', '--args', '-e', '/bin/sh', path]);
    if (term === 'WezTerm') return spawn('/usr/bin/open', ['-na', 'WezTerm', '--args', 'start', '--', '/bin/sh', path]);
    return $.NSWorkspace.sharedWorkspace.openFileWithApplication(path, 'Terminal');
}
function script(lines) { var a = []; lines.forEach(function (l) { a.push('-e', l); }); return a; }
function tabId(w) {
    if (w.term === 'iTerm.app') return w.term_session.split(':').pop();
    if (w.term === 'Apple_Terminal' && w.tty) return w.tty.charAt(0) === '/' ? w.tty : '/dev/' + w.tty;
    return '';
}
// A tab that is gone (the user quit `claude`, which keeps the watcher's session running in the
// background) is reopened with `claude attach`; each watcher names its own session.
function goToTab(w) {
    if (!w || typeof w !== 'object') return;
    w = { term: str(w.term), term_session: str(w.term_session), tty: str(w.tty), session_id: str(w.session_id) };
    var t = TERMS[w.term];
    // Needs no permission, so the app comes forward even when the tab lookup is refused. Via
    // LaunchServices: an accessory app's own activate request is ignored by macOS.
    if (t) spawn('/usr/bin/open', ['-b', t[1]]);
    var id = tabId(w), src = FOCUS[w.term];
    var found = src && TAB_ID.test(id) ? output('/usr/bin/osascript', script(src).concat([id])) : '';
    // null: the lookup failed or is still waiting on a permission prompt — the tab may be there.
    if (found === '' && SESSION_ID.test(w.session_id)) openIn(w.term, 'claude attach ' + w.session_id.slice(0, 8), snoozeFile);
}
function newTask(path, args) {
    var task = $.NSTask.alloc.init;
    task.setLaunchPath(path);
    task.setArguments($(args));
    task.setStandardError($.NSFileHandle.fileHandleWithNullDevice);
    return task;
}
function spawn(path, args) {
    var task = newTask(path, args);
    task.setStandardOutput($.NSFileHandle.fileHandleWithNullDevice);
    task.launch;
    return true;
}
// Trimmed stdout once the task exits 0, else null. The run loop keeps turning meanwhile, so the
// menu stays live while macOS shows a permission prompt.
function output(path, args) {
    var task = newTask(path, args), pipe = $.NSPipe.pipe, end = Date.now() + 60000;
    task.setStandardOutput(pipe);
    task.launch;
    while (task.isRunning && Date.now() < end) {
        $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.05));
    }
    if (task.isRunning || task.terminationStatus !== 0) return null;
    var out = $.NSString.alloc.initWithDataEncoding(pipe.fileHandleForReading.readDataToEndOfFile, $.NSUTF8StringEncoding);
    return ObjC.unwrap(out).trim();
}
// Each `wait` of the watcher exits on its stop file and the watcher session stops watching that
// repo. Killing a `wait` instead would read as a failure: an error toast, then a restart. Another
// role's wait on the same repo has its own stop file and goes on.
function stopFile(d, sfx) { return d + '/stop' + sfx; }
function stopWatcher(o) {
    if (!o || !Array.isArray(o.dirs)) return;
    var sfx = SETS.some(function (x) { return x.sfx === o.sfx; }) ? o.sfx : null;
    if (sfx === null) return;
    var dirs = o.dirs.filter(function (d) {
        return typeof d === 'string' && /\/watch$/.test(d) && d.indexOf('/../') < 0 && isDir(d)
            && dataDirs.some(function (data) { return d.indexOf(data + '/') === 0; });
    });
    dirs.forEach(function (d) { $('').writeToFileAtomicallyEncodingError(stopFile(d, sfx), true, $.NSUTF8StringEncoding, null); });
    var sid = str(o.session_id);
    if (dirs.length && SESSION_ID.test(sid)) stopLater({ dirs: dirs, sfx: sfx, session_id: sid, tries: 0 });
}
function stopLater(o) {
    $.NSTimer.scheduledTimerWithTimeIntervalTargetSelectorUserInfoRepeats(3, target, 'stopSession:', $(JSON.stringify(o)), false);
}
// A watcher session left running in the background (its user quit `claude`) has nobody to close
// it once its waits are stopped. Stopped once its waits consumed their stop files, or after 15 s.
function stopSession(o) {
    if (!o || !Array.isArray(o.dirs) || !SESSION_ID.test(str(o.session_id))) return;
    var fm = $.NSFileManager.defaultManager;
    var sfx = SETS.some(function (x) { return x.sfx === o.sfx; }) ? o.sfx : '';
    var pending = o.dirs.some(function (d) { return typeof d === 'string' && fm.fileExistsAtPath(stopFile(d, sfx)); });
    if (pending && o.tries < 4) { o.tries++; stopLater(o); return; }
    var list = parse(output('/usr/bin/env', ['claude', 'agents', '--json']) || '');
    var bg = Array.isArray(list) && list.some(function (a) {
        return a && a.kind === 'background' && a.sessionId === o.session_id;
    });
    if (bg) spawn('/usr/bin/env', ['claude', 'stop', o.session_id.slice(0, 8)]);
}
// `open-pr-watch.sh <sub>` argv naming the repo of o {repo_dir, remote}, or null when a value is outside its shape.
function repoArgs(o, sub) {
    if (!watchScript || !o || typeof o !== 'object') return null;
    var dir = str(o.repo_dir), remote = str(o.remote);
    if (!isDir(dir) || (remote && !REMOTE.test(remote))) return null;
    return [watchScript, sub, '--repo-dir', dir].concat(remote ? ['--remote', remote] : []);
}
// … for one PR (sub: hide | fix-now)
function prArgs(o, sub) {
    var a = repoArgs(o, sub), pr = o && o.pr;
    return a && typeof pr === 'number' && /^[0-9]+$/.test(String(pr)) ? a.concat(['--pr', String(pr)]) : null;
}
// … for a Settings click: a SETTINGS key and one of its values
function settingArgs(o) {
    var a = repoArgs(o, 'settings'), ok = o && SETTING_VALUES[str(o.key)];
    return a && ok && ok.indexOf(str(o.value)) >= 0 ? a.concat(['--set', o.key, '--value', o.value]) : null;
}
// A panel control's click: writes its key (the run loop turns meanwhile), then sets the panel from
// the file read afresh — a refused write puts the control back. The menu stays open.
function setSetting(sender) {
    var c = controls[sender.hash];
    if (!c || !c.p) return;
    var p = c.p, value = c.values ? c.values[sender.selectedSegment] : valueAt(p.conf, c.key) !== true;
    var args = value === undefined ? null : settingArgs({ repo_dir: p.x.arg.repo_dir, remote: p.x.arg.remote, key: c.key, value: String(value) });
    if (args) { output('/bin/sh', args); delete settingsCache[p.x.repo]; }
    showPanel(p, repoSettings(p.x.repo, p.x.arg.repo_dir, p.x.arg.remote) || p.conf);
}
// <data>/<repo>/settings.json when p is exactly that, a regular file in one of this menu bar's data dirs; else ''.
function revealable(p) {
    p = str(p);
    var m = /^(\/.+)\/[^\/]+\/settings\.json$/.exec(p);
    if (!m || /\/\.\.?\//.test(p) || dataDirs.indexOf(m[1]) < 0) return '';
    var at = $.NSFileManager.defaultManager.attributesOfItemAtPathError(p, null);   // a symlink is not followed
    return !at.isNil() && ObjC.unwrap(at.objectForKey($.NSFileType)) === ObjC.unwrap($.NSFileTypeRegular) ? p : '';
}
// Closes the menu, then shows the file selected in Finder.
function reveal(sender) {
    var c = controls[sender.hash], path = revealable(c && c.reveal);
    if (!path) return;
    if (item && !item.menu.isNil()) item.menu.cancelTracking;
    $.NSWorkspace.sharedWorkspace.activateFileViewerSelectingURLs($([$.NSURL.fileURLWithPath(path)]));
}
// The watcher's wait delivers it within seconds; the row turns to the fix session once it opens.
function fixNow(o) {
    var args = prArgs(o, 'fix-now');
    if (!args) return;
    spawn('/bin/sh', args);
    pendingFix[o.repo_dir + '#' + o.pr] = Date.now();
    refresh();
}
function hide(o) {
    var args = prArgs(o, 'hide');
    if (!args) return;
    spawn('/bin/sh', args);
    pendingHide[o.repo_dir + '#' + o.pr] = Date.now();
    refresh();
}
// minutes > 0: that long; -1: until 9:00 local tomorrow; 0: back on. Same format as
// `open-pr-watch.sh snooze`.
function snooze(minutes) {
    if (!snoozeFile) return;
    if (minutes === 0) {
        $.NSFileManager.defaultManager.removeItemAtPathError(snoozeFile, null);
    } else {
        var d = new Date();
        if (minutes > 0) d = new Date(d.getTime() + minutes * 60000);
        else { d.setDate(d.getDate() + 1); d.setHours(9, 0, 0, 0); }
        var iso = d.toISOString().replace(/\.\d+Z$/, 'Z');
        $(iso + '\n').writeToFileAtomicallyEncodingError(snoozeFile, true, $.NSUTF8StringEncoding, null);
    }
    refresh();
}
// Same file and floor as `open-pr-watch.sh poll`; 0 = back to each repo's setting.
function pollFile() { return snoozeFile ? snoozeFile.replace(/\/[^\/]*$/, '') + '/poll_seconds' : ''; }
function pollSeconds() { var n = parseInt(readText(pollFile()), 10); return n >= 15 ? n : 0; }
function poll(seconds) {
    var f = pollFile();
    if (!f) return;
    if (seconds === 0) $.NSFileManager.defaultManager.removeItemAtPathError(f, null);
    else $(Math.max(15, seconds) + '\n').writeToFileAtomicallyEncodingError(f, true, $.NSUTF8StringEncoding, null);
    refresh();
}
function leave() {
    var me = String($.NSProcessInfo.processInfo.processIdentifier);
    if (readText(pidFile).trim() === me) $.NSFileManager.defaultManager.removeItemAtPathError(pidFile, null);
    if (item) $.NSStatusBar.systemStatusBar.removeStatusItem(item);
    $.NSApplication.sharedApplication.terminate(null);
}
