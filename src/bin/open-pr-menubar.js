// macOS menu bar item for `/open-pr:menubar` (a status item needs no permission). It
// polls, in every data directory given, the files the watcher writes:
//   <data>/<repo>/watch/heartbeat    a watcher counts as watching the repo while this is fresh
//   <data>/<repo>/watch/state.json   sessions, one row per PR and role (review | fix); active = not
//                                           finished, working or question; `findings` = a fix row offering
//                                           "Fix now" until a fix session opens; PRs in `hidden` get no row;
//                                           runner `here`: fixed in the watcher's own session (its tab)
//                                           `titles`: each PR's title, its row's title after #N
//   <data>/<repo>/watch/feed.jsonl   notifications; a PR role's latest one, when newer than its
//                                           session's state, is its row's text; a question's `focus`
//                                           (watcher | session) is where its row's click goes
//   <data>/<repo>/watch/watcher.json the terminal tab whose watcher watches the repo, the pids of
//                                           its wait and of its `claude` (liveTab), and the repo_dir/remote "Remove from list"
//                                           passes to `hide` and "Fix now" to `fix-now`
//   <data>/<repo>/watch/stop         written by "Stop"; the watcher's `wait` consumes it
//   <data>/<repo>/watch/quota.json   the host's rate limit as the last poll read it (see QUOTA)
//   <data>/<repo>/settings.json      the repo's watch.poll_interval_seconds (see STALE); the settings
//                                           panel reads and writes it through `open-pr-watch.sh settings`
//   heartbeat, watcher.json, stop and quota.json belong to the wait serving both roles; a wait serving one
//   role has its own, suffixed (heartbeat-fix, watcher-fix.json, stop-fix — see SETS)
//   snooze file                             toasts off until then; the Snooze menu writes it too
// It stays until the user closes it (the menu, or `menubar --close`); watching goes on either way.
// argv: snooze file, pid file (its pid is written there once the item is in the menu bar), heartbeat
// age (seconds) past which a repo is not watched, data dirs, then the absolute path of open-pr-watch.sh.
// A leading --probe (`open-pr.sh selftest`): the item hidden, its menu built once, any error fatal,
// the pid file written, then it quits.
// File contents are data only: shown as menu titles, opened when they are http(s) URLs, copied
// as text, written into a .command file or passed to osascript as argv after matching OPEN_CMD,
// passed to osascript as argv after matching TAB_ID, turned into `claude attach`/`--resume` after matching
// SESSION_ID, or passed to open-pr-watch.sh as argv after matching isDir/REMOTE/digits or a
// SETTINGS key and one of its values — never spliced into source.
ObjC.import('Cocoa');

// CLIP: characters of a menu title before "…"; SUB_W: points of a PR row's subtitle (past about 300
// a native subtitle keeps the height of a second line, though it draws one).
var REFRESH = 3, ROWS = 10, CLIP = 70, SUB_W = 280, HEADER_W = 340;
// Rows laid out by hand (view items): a repo row (height, where its name starts) and a watcher row
// (height, where its text starts: one indentation step in, its icon left of it).
var REPO = { h: 26, x: 14 }, ROW = { h: 24, text: 47 };
// A PR row's indentation level: its icon sits under its watcher row's text.
var PR_INDENT = 3;
// The pills (Stop, the settings gear): height, the gear's width.
var PILL = { h: 20, gear: 30 };
// Points a menu row spends beside its subtitle: indent, icon, submenu arrow.
var SUBTITLE_PAD = 140;
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
var item = null, icons = {}, rowParts = {}, pillParts = {}, litRow = null, menuOpen = false;
// The watcher row whose settings show inline under it: { row: its rowParts, items: the panel items,
// panels: settingsPanel's objects }; shown = the scan the open menu was built from.
var openPanel = null, shown = null;

// A watcher row says "no poll for …" once its newest heartbeat is older than STALE.factor × the
// interval it polls at: the slowest of its repos' setting (default STALE.poll) and STALE.idle — an
// idle repo slows to that (IDLE_POLL in open-pr-watch.sh).
var STALE = { factor: 2, poll: 180, idle: 600 };
var KIND = {   // SF Symbol, label — by a session's last_state (lgtm_chat as lgtm); the symbol alone tells the state, in the menu's own colour
    working:  ['circle.dotted', 'Reviewing'],
    fixing:   ['circle.dotted', 'Fixing'],
    fixing_here: ['circle.dotted', 'Fixing here'],
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
// A watcher row's terminal icon tint and role word, by the role it serves: review and fix watchers
// tell apart at a glance. Its PR rows belong to it; a fix row's state starts "Fix: ".
var ROLE_LOOK = { review: [[0.04, 0.42, 0.9], 'Review'], fix: [[0.8, 0.38, 0.02], 'Fix'], '': [null, 'Review + fix'] };
var ROLE_RANK = { '': 0, '-review': 1, '-fix': 2 };   // a repo's watchers: both roles, review, fix
// The badge: rows shown whose session runs, waits for the user's answer, or is starting on a Fix now
// click. A `findings` row waits for nobody: Fix now is the user's to choose.
var BUSY = { working: 1, fixing: 1, fixing_here: 1, fix_requested: 1, question: 1 }, busy = 0;
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
// FOCUS returns "found" so a closed tab can be told apart from a found one. argv: the tab id and
// the tty the watcher runs on (liveTab). w, t and s are positional references ("item 1 of every
// window"): `select w` moves the window to the front, so it comes last or t and s resolve in
// another window.
var FOCUS = {
    'iTerm.app': [
        'on run argv',
        'tell application id "com.googlecode.iterm2"',
        'repeat with w in windows',
        'repeat with t in tabs of w',
        'repeat with s in sessions of t',
        'if (unique id of s) is (item 1 of argv) and (tty of s) is (item 2 of argv) then',
        'select t', 'select s', 'select w', 'activate', 'return "found"',
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
// tightest measured one; the settings panel's Poll control estimates requests per hour at each interval as
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

// Every Cocoa callback is a JS function behind a block: a control's or menu item's target is an
// NSBlockOperation whose `main` runs it, timers and notifications take a block. No ObjC subclass:
// registering one hangs osascript on an Intel Mac. A target is held weakly, so each operation is
// kept here while a menu that can show it lives: the current menu's and the one it replaced (an
// action may run while a refresh swaps the menu).
var ops = [], opsBefore = [];
function act(fn) { var op = $.NSBlockOperation.blockOperationWithBlock(fn); ops.push(op); return op; }
// While the menu is open (tracking runs its own run loop mode, so the timer is in the common modes):
// the highlight of a watcher row and the hover of a pill, which a view item gets from nobody else.
var TRACK = 0.05, tracker = null;

function run(argv) {
    var probe = argv[0] === '--probe';
    if (probe) argv = argv.slice(1);
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
    // its own autosave name: the hidden state macOS keeps for it never reaches the real item's
    if (probe) { item.setAutosaveName('open-pr-selftest'); item.setVisible(false); }
    item.button.setImage(icons.bar);
    item.button.setImagePosition($.NSImageLeft);
    item.button.setToolTip('open-pr');
    // object $() (nil): any menu, ours told by isOurs. A JS null crosses the bridge as NSNull, which no menu is.
    var nc = $.NSNotificationCenter.defaultCenter, main = $.NSOperationQueue.mainQueue;
    nc.addObserverForNameObjectQueueUsingBlock($.NSMenuDidBeginTrackingNotification, $(), main, function (n) {
        if (isOurs(n.object)) menuOpened();
    });
    nc.addObserverForNameObjectQueueUsingBlock($.NSMenuDidEndTrackingNotification, $(), main, function (n) {
        if (isOurs(n.object)) menuClosed();
    });
    if (probe) item.setMenu(build(scan()));   // throws, where refresh() would show brokenMenu
    refresh();
    $.NSTimer.scheduledTimerWithTimeIntervalRepeatsBlock(REFRESH, true, function () { refresh(); });
    // `menubar` waits for this: the item is in the menu bar
    if (pidFile) $(String($.NSProcessInfo.processInfo.processIdentifier) + '\n').writeToFileAtomicallyEncodingError(pidFile, true, $.NSUTF8StringEncoding, null);
    if (probe) { $.NSStatusBar.systemStatusBar.removeStatusItem(item); return; }
    app.run;
}
function isOurs(menu) { return !!item && !menu.isNil() && !item.menu.isNil() && menu.isEqual(item.menu); }
function menuOpened() {
    menuOpen = true;
    if (tracker) tracker.invalidate;
    tracker = $.NSTimer.timerWithTimeIntervalRepeatsBlock(TRACK, true, function () { track(); });
    $.NSRunLoop.currentRunLoop.addTimerForMode(tracker, $.NSRunLoopCommonModes);
}
function menuClosed() {
    if (tracker) { tracker.invalidate; tracker = null; }
    menuOpen = false;
    highlightRow(null);
    Object.keys(pillParts).forEach(function (h) { var q = pillParts[h]; if (q.hover) { q.hover = false; paintPill(q, !!q.lit); } });
    closeSettings();
}
// One tracking step: repaints only what changed since the last.
function track() {
    var m = item.menu;
    if (m.isNil()) return;
    highlightRow(m.highlightedItem);
    var at = $.NSEvent.mouseLocation;
    Object.keys(pillParts).forEach(function (h) {
        var q = pillParts[h], r = screenRect(q.button);
        var on = !!r && at.x >= r.origin.x && at.x <= r.origin.x + r.size.width && at.y >= r.origin.y && at.y <= r.origin.y + r.size.height;
        if (on !== !!q.hover) { q.hover = on; paintPill(q, !!q.lit); }
    });
}
// A view's frame on screen, or null while it is in no window. Through the content view: a nil
// view to convertRect:toView: crashes the bridge.
function screenRect(v) {
    var w = v.window;
    if (w.isNil()) return null;
    var c = w.contentView, r = v.convertRectToView(v.bounds, c), o = c.frame.origin;
    return w.convertRectToScreen($.NSMakeRect(r.origin.x + o.x, r.origin.y + o.y, r.size.width, r.size.height));
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
// A watcher's wait on one repo: one per watcher tab and role set in each repo group (a watcher with
// several repos has one in each group). key: its tab and role set, the same in every group.
function watcherOf(w, set) {
    w = w && typeof w === 'object' ? w : {};
    var term = str(w.term), ts = str(w.term_session), tty = str(w.tty), cwd = str(w.cwd), sid = str(w.session_id);
    var t = TERMS[term], tab = ts ? 's:' + ts : tty ? 't:' + tty : typeof w.pid === 'number' ? 'p:' + w.pid : '';
    return { key: tab ? tab + set.sfx : '',
             cwdName: cwd ? basename(cwd) : '', termName: term ? (t ? t[0] : term) : '',
             role: set.sfx.replace('-', ''), start: 0, beat: Infinity, poll: 0, only: true,
             term: term, term_session: ts, tty: tty, session_id: sid, app: t ? t[2] : 'Terminal', sfx: set.sfx, pids: [], hosts: [],
             dirs: [], rows: [] };
}

// → { repos: [{ name, folders, settings, watchers }] by name, quotas, polls }: one group per
// watched repo (its data dirs merged), its watchers by role, each with its PR rows.
function scan() {
    var out = { repos: [], quotas: [], polls: [] }, groups = {}, repoCount = {};
    dataDirs.forEach(function (data) { listDir(data).forEach(function (name) {
        if (typeof name !== 'string' || name.charAt(0) === '.') return;
        var dir = data + '/' + name + '/watch';
        var live = SETS.filter(function (set) { return ageSeconds(dir + '/heartbeat' + set.sfx) <= fresh; });
        if (!live.length) return;
        var g = groups[name];
        if (!g) { g = groups[name] = { name: name, folders: [], settings: [], watchers: [], byKey: {} }; out.repos.push(g); }
        out.polls.push(repoPoll(data + '/' + name));
        var wj = null, at = {};
        live.forEach(function (set) {
            var j = parse(readText(dir + '/watcher' + set.sfx + '.json')), wr = watcherOf(j, set);
            wj = wj || j;
            if (!g.byKey[wr.key]) {
                g.byKey[wr.key] = wr; g.watchers.push(wr);
                repoCount[wr.key] = (repoCount[wr.key] || 0) + 1;
                // a workspace watcher: the folder it runs in is not this repo
                if (wr.cwdName && wr.cwdName !== name && g.folders.indexOf(wr.cwdName) < 0) g.folders.push(wr.cwdName);
            }
            var e = at[set.sfx] = g.byKey[wr.key];
            // when this wait started: the watcher record is written at each start
            e.start = Math.max(e.start, Date.now() - ageSeconds(dir + '/watcher' + set.sfx + '.json') * 1000);
            if (j && typeof j === 'object' && typeof j.pid === 'number') e.pids.push(j.pid);
            if (j && typeof j === 'object' && typeof j.host_pid === 'number') e.hosts.push(j.host_pid);
            e.beat = Math.min(e.beat, ageSeconds(dir + '/heartbeat' + set.sfx));
            e.poll = Math.max(e.poll, repoPoll(data + '/' + name));
            e.dirs.push(dir);
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
        if (conf) g.settings.push({ name: name, repo: data + '/' + name, conf: conf, doctor: doctorLine(conf), arg: { repo_dir: repoDir, remote: remote } });
        var rows = {};
        var st = parse(readText(dir + '/state.json'));
        var ss = st && typeof st.sessions === 'object' && st.sessions ? st.sessions : {};
        var titles = st && typeof st.titles === 'object' && st.titles ? st.titles : {};
        var hidden = {};
        (st && Array.isArray(st.hidden) ? st.hidden : []).forEach(function (n) { if (typeof n === 'number') hidden[n] = true; });
        var gone = function (pr) {
            var at = pendingHide[repoDir + '#' + pr];
            return hidden[pr] || (at && Date.now() - at < HIDE_PENDING);
        };
        var prArg = function (pr) { return JSON.stringify({ repo_dir: repoDir, remote: remote, pr: Number(pr) }); };
        // a line about the whole repo (a failed start, a poll error) has no PR
        var row = function (pr, role) {
            var k = pr + ':' + role;
            return rows[k] || (rows[k] = { title: pr ? '#' + pr + (str(titles[pr]) ? ' ' + oneLine(titles[pr]) : '') : 'Repository',
                pr: pr, role: role, session: false, state: '',
                active: false, url: '', open: '', hide: pr ? prArg(pr) : '', fix: '', stateAt: 0 });
        };
        Object.keys(ss).forEach(function (key) {
            var s = ss[key], m = /^([0-9]+):(review|fix)$/.exec(key);
            if (!m || !s || typeof s !== 'object' || gone(m[1])) return;
            var r = row(m[1], m[2]), state = str(s.last_state);
            r.session = true;
            r.here = s.runner === 'here';
            r.state = m[2] === 'fix' && state === 'working' ? (r.here ? 'fixing_here' : 'fixing') : state;
            r.active = s.finished !== true && (state === 'working' || state === 'question');
            r.url = str(s.url); r.open = str(s.open);
            r.stateAt = ms(s.last_state_at) || Math.max(ms(s.started_at), ms(s.finished_at));
        });
        var fd = st && typeof st.findings === 'object' && st.findings ? st.findings : {};
        Object.keys(fd).forEach(function (pr) {
            var f = fd[pr];
            if (!/^[0-9]+$/.test(pr) || !f || typeof f !== 'object' || gone(pr)) return;
            var r = row(pr, 'fix'), at = ms(f.at);
            if (at < r.stateAt) return;
            r.session = true; r.state = 'findings'; r.stateAt = at; r.active = true;
            r.findings = counts(f.counts); r.fix = prArg(pr);
            if (!r.url) r.url = str(f.url);
        });
        readText(dir + '/feed.jsonl').split('\n').forEach(function (line) {
            var f = parse(line);
            if (!f || typeof f !== 'object' || !str(f.summary)) return;
            var pr = typeof f.pr === 'number' ? String(f.pr) : '';
            if (pr && gone(pr)) return;
            var r = row(pr, f.role === 'fix' ? 'fix' : 'review');
            if (!r.feed || str(f.at) >= str(r.feed.at)) r.feed = f;
            if (!r.url) r.url = str(f.url);
        });
        Object.keys(rows).forEach(function (k) {
            var r = rows[k], w = to(r.role);
            // a repo-wide line from before this watcher started is over
            if (!r.hide && !r.session && r.feed && ms(r.feed.at) < w.start) return;
            finish(r);
            // clicked: no second Fix now until the fix session shows (or the click is stale)
            var clicked = pendingFix[repoDir + '#' + r.pr];
            if (r.kind === 'findings' && clicked && Date.now() - clicked < FIX_PENDING) {
                r.kind = 'fix_requested'; r.fix = ''; r.active = true;
                r.time = ' · ' + when(new Date(clicked));
                r.text = KIND.fix_requested[1] + r.time;
            }
            w.rows.push(r);
        });
    }); });
    var low = function (t) { return t.toLowerCase(); };
    out.repos.sort(function (a, b) { return low(a.name) < low(b.name) ? -1 : low(a.name) > low(b.name) ? 1 : 0; });
    out.repos.forEach(function (g) {
        delete g.byKey;
        g.watchers.forEach(function (w) {
            // Stop ends the watcher's session only when this is its one repo
            w.only = repoCount[w.key] === 1;
            // waiting on the user first, then the latest; a PR's rows side by side where its first
            // one falls, review on top and its fix row nested under it; ROWS PRs shown, never split.
            // A repo-wide row is its own group.
            w.rows.sort(function (a, b) { return (b.active - a.active) || (b.at - a.at); });
            var prs = [], of = {};
            w.rows.forEach(function (r) {
                var k = r.pr || ':' + r.role;
                if (!of[k]) prs.push(of[k] = []);
                of[k].push(r);
            });
            w.rows = [].concat.apply([], prs.slice(0, ROWS).map(function (g) {
                if (g.length > 1) { if (g[0].role === 'fix') g.reverse(); g[1].nested = true; }
                return g;
            }));
        });
        // both roles, review, fix; then by tab
        var key = function (w) { return [ROLE_RANK[w.sfx], low(w.cwdName + ' ' + w.termName)]; };
        g.watchers.sort(function (a, b) {
            var x = key(a), y = key(b);
            for (var i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
            return 0;
        });
    });
    return out;
}
// Text from a file shown as a menu title: one line.
function oneLine(t) { return str(t).replace(/\s+/g, ' ').trim(); }
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
        var g = l && r !== null ? { ratio: r / l, text: hostName(q) + ' API ' + r.toLocaleString('en-US') + '/' + l.toLocaleString('en-US') }
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
// A watcher row's line as [text, kind] parts, kind '' | 'role' | 'warn': role, terminal, then when it
// last polled.
function watcherLine(w) {
    var parts = [[(ROLE_LOOK[w.role] || ROLE_LOOK[''])[1], 'role']], head = w.termName ? ' · ' + w.termName : '';
    if (!isFinite(w.beat)) return head ? parts.concat([[head, '']]) : parts;
    var every = Math.max(w.poll, STALE.idle);
    if (w.beat > STALE.factor * every) return parts.concat([[head + ' · ', ''], ['no poll for ' + age(w.beat) + ' — check the watcher tab', 'warn']]);
    return parts.concat([[head + ' · polled ' + (w.beat < 60 ? 'just now' : age(w.beat) + ' ago'), '']]);
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
    // A "done" line cannot outrank a session still running: its state says what is happening.
    if (f && r.session && r.active && r.state !== 'question' && (kind === 'posted' || kind === 'lgtm')) {
        f = null;
        kind = r.state === 'lgtm_chat' ? 'lgtm' : r.state;
    }
    // Counted and listed first like an active session: it waits on the user.
    if (f && kind === 'question') r.active = true;
    // where the user answers it: the watcher's tab, or the session (as the toast's click)
    r.focus = f && kind === 'question' && (f.focus === 'watcher' || f.focus === 'session') ? f.focus : '';
    var at = Math.max(r.stateAt, fat);
    r.kind = kind;
    r.at = at;
    // a feed line saying "fixed" or "posted" after the findings ends the Fix now offer
    if (kind !== 'findings') r.fix = '';
    else if (!r.fix && r.hide) r.fix = r.hide;
    var label = KIND[kind] ? KIND[kind][1] : kind;
    if (kind === 'findings' && r.findings) label = r.findings + ' — Fix now';
    r.time = at ? ' · ' + when(new Date(at)) : '';
    r.text = (f ? str(f.summary) : label) + r.time;
    return r;
}

// -------------------------------------------------------------- images ----
function hexColor(h) {
    var n = parseInt(h.slice(1), 16);
    return $.NSColor.colorWithSRGBRedGreenBlueAlpha((n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255, 1);
}
function rgb(c) { return $.NSColor.colorWithSRGBRedGreenBlueAlpha(c[0], c[1], c[2], 1); }
// A warning in text: the system orange is too light to read on a light menu, so a darker one there.
function warnColor() {
    var a = $.NSApp.effectiveAppearance.bestMatchFromAppearancesWithNames($([$.NSAppearanceNameAqua, $.NSAppearanceNameDarkAqua]));
    return ObjC.unwrap(a) === ObjC.unwrap($.NSAppearanceNameDarkAqua) ? $.NSColor.systemOrangeColor : rgb([0.7, 0.29, 0]);
}
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
// The badge and the menu change together, the menu first: a menu that fails to build is logged
// (menubar.log), a minimal one shows, and the badge counts nothing it does not show.
var refreshing = false;
function refresh() {
    if (refreshing || menuOpen) return;
    refreshing = true;
    try {
        var m;
        try { m = build(scan()); } catch (e) {
            console.log('open-pr menu bar: the menu failed to build: ' + e);
            m = brokenMenu();
        }
        item.setMenu(m);
        item.button.setTitle(busy ? String(busy) : '');
    } finally { refreshing = false; }
}
function brokenMenu() {
    busy = 0;
    var m = newMenu('open-pr');
    add(m, 'The menu failed to build — see menubar.log');
    m.addItem($.NSMenuItem.separatorItem);
    add(m, 'Quit menu bar', leave);
    return m;
}

function clip(t, n) { n = n || CLIP; return t.length > n ? t.slice(0, n - 1) + '…' : t; }
// Auto-enabling greys out a submenu parent that has no action.
function newMenu(title) {
    var m = $.NSMenu.alloc.initWithTitle(title);
    m.setAutoenablesItems(false);
    return m;
}
// fn(value) runs on a click; no fn: a line that does nothing. value is also the item's represented object.
function add(menu, title, fn, value) {
    var mi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(clip(title), fn ? 'main' : null, '');
    mi.setEnabled(!!fn);
    if (fn) {
        mi.setTarget(act(function () { fn(value); }));
        if (value !== undefined) mi.setRepresentedObject($(value));
    }
    menu.addItem(mi);
    return mi;
}
// fn of the object a JSON value holds
function json(fn) { return function (v) { fn(parse(v)); }; }
// Native subtitle from macOS 14.4; before that, the same two lines as an attributed title. One line,
// cut with "…" at SUB_W before its tail (the time), which stays whole: the menu widens to fit it (a
// native subtitle does not widen it, and runs under the submenu arrow).
function subtitle(mi, text, tail) {
    var font = $.NSFont.menuFontOfSize(12), width = function (t) { return $(t).sizeWithAttributes($({ NSFont: font })).width; };
    tail = tail && text.slice(-tail.length) === tail ? tail : '';
    var head = oneLine(text.slice(0, text.length - tail.length));
    text = head + tail;
    if (width(text) > SUB_W) {   // the longest head that fits with its "…" and the tail
        var lo = 0, hi = head.length;
        while (lo < hi) { var mid = Math.ceil((lo + hi) / 2); if (width(head.slice(0, mid) + '…' + tail) <= SUB_W) lo = mid; else hi = mid - 1; }
        text = head.slice(0, lo).replace(/\s+$/, '') + '…' + tail;
    }
    if (mi.respondsToSelector('setSubtitle:')) {
        var menu = mi.menu, w = width(text);
        if (!menu.isNil() && w + SUBTITLE_PAD > menu.minimumWidth) menu.setMinimumWidth(w + SUBTITLE_PAD);
        mi.setSubtitle(text);
        return;
    }
    mi.setAttributedTitle(attributed([[ObjC.unwrap(mi.title) + '\n', $.NSFont.menuFontOfSize(0), $.NSColor.labelColor],
                                      [text, $.NSFont.menuFontOfSize(11), $.NSColor.secondaryLabelColor]], false));
}
// parts [[text, font, colour]…] → one attributed string, built piece by piece (JXA does not bridge
// NSAttributedString's initWithString… initializers). cut: one line, its tail cut with "…" (an
// attributed value brings its own line breaking, and a wrapped line falls out of sight).
function attributed(parts, cut) {
    var s = $.NSMutableAttributedString.alloc.init, at = 0, ps = null;
    if (cut) { ps = $.NSMutableParagraphStyle.alloc.init; ps.setLineBreakMode($.NSLineBreakByTruncatingTail); }
    parts.forEach(function (x) {
        s.mutableString.appendString(x[0]);
        var r = $.NSMakeRange(at, x[0].length);
        s.addAttributeValueRange('NSFont', x[1], r);
        s.addAttributeValueRange('NSColor', x[2], r);
        if (ps) s.addAttributeValueRange('NSParagraphStyle', ps, r);
        at += x[0].length;
    });
    return s;
}
function label(text, font, color, x, y) {
    var f = $.NSTextField.labelWithString(text);
    f.setFont(font);
    f.setTextColor(color);
    f.setLineBreakMode($.NSLineBreakByTruncatingTail);
    f.setFrame($.NSMakeRect(x, y, HEADER_W - x - 14, 17));
    return f;
}
function textWidth(t, font) { return Math.ceil($(t).sizeWithAttributes($({ NSFont: font })).width) + 4; }
// The repos' poll settings → "every 3m", or "every 1–5m" when they differ; '' for none.
function pollSpan(polls) {
    if (!polls.length) return '';
    var lo = Math.min.apply(null, polls), hi = Math.max.apply(null, polls);
    var f = function (v) { return v % 60 ? v + 's' : v / 60 + 'm'; };
    return 'every ' + (lo === hi ? f(hi) : (lo % 60 || hi % 60 ? f(lo) : lo / 60) + '–' + f(hi));
}
// One line: the moth, "open-pr", and on the right a bell-slash while toasts are snoozed, the quota
// gauge and the poll interval; those go on a second line when they do not fit beside the name.
function headerView(until, quota, polls) {
    var small = $.NSFont.systemFontOfSize(11), second = $.NSColor.secondaryLabelColor, bold = $.NSFont.boldSystemFontOfSize(13);
    var parts = [];   // [view, width, tooltip]
    if (until) {
        var bell = $.NSImageView.imageViewWithImage(symbol(['bell.slash']));
        bell.setContentTintColor(second);
        parts.push([bell, 14, 'Toasts off until ' + when(until)]);
        var u = 'until ' + hhmm(until) + (quota || polls ? ' ·' : '');
        parts.push([label(u, small, second, 0, 0), textWidth(u, small), 'Toasts off until ' + when(until)]);
    }
    if (quota) {
        var qt = quota.text + (polls ? ' ·' : '');
        parts.push([label(qt, small, quota.level === 'critical' ? $.NSColor.systemRedColor
                          : quota.level === 'low' ? warnColor() : second, 0, 0), textWidth(qt, small),
                    'API requests left in the host\'s current rate-limit window']);
    }
    if (polls) parts.push([label(polls, small, second, 0, 0), textWidth(polls, small), 'How often the watched repos poll (an idle repo slows to every ' + STALE.idle / 60 + 'm)']);
    var rw = parts.reduce(function (n, x) { return n + x[1] + 2; }, 0);
    var nx = 40, nw = textWidth('open-pr', bold);
    var one = nx + nw + 16 + rw + 14 <= HEADER_W, h = one ? 30 : 46, w = Math.max(HEADER_W, nx + rw + 14);
    var v = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, w, h));
    v.setAutoresizingMask($.NSViewWidthSizable);
    var iv = $.NSImageView.imageViewWithImage(icons.header);
    iv.setFrame($.NSMakeRect(14, h - 25, 20, 20));
    v.addSubview(iv);
    var name = label('open-pr', bold, $.NSColor.labelColor, nx, h - 23);
    name.setFrame($.NSMakeRect(nx, h - 23, nw, 17));
    v.addSubview(name);
    // right-aligned on the first line, else left-aligned under the name
    var x = one ? w - 14 - rw : nx, y = one ? h - 22 : 6;
    parts.forEach(function (p) {
        var ph = p[1] === 14 ? 14 : 15;
        p[0].setFrame($.NSMakeRect(x, y + (p[1] === 14 ? 1 : 0), p[1], ph));
        if (one) p[0].setAutoresizingMask($.NSViewMinXMargin);
        p[0].setToolTip(p[2]);
        v.addSubview(p[0]);
        x += p[1] + 2;
    });
    return v;
}

// A repo group's first row: the repo's name, and the gear that shows its settings inline under it
// (settings: as scan() lists them). folders: the workspace folders its watchers run in (tooltip).
function repoRow(name, folders, settings, quotas) {
    var font = $.NSFont.systemFontOfSizeWeight($.NSFont.systemFontSize, $.NSFontWeightSemibold);
    var gw = settings.length ? PILL.gear : 0, w = Math.max(HEADER_W, REPO.x + textWidth(name, font) + 20 + gw + 14);
    var v = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, w, REPO.h));
    v.setAutoresizingMask($.NSViewWidthSizable);
    var t = label(name, font, $.NSColor.labelColor, REPO.x, (REPO.h - 17) / 2);
    t.setFrame($.NSMakeRect(REPO.x, (REPO.h - 17) / 2, w - REPO.x - gw - 26, 17));
    t.setAutoresizingMask($.NSViewWidthSizable);
    if (folders.length) t.setToolTip('Watched from ' + folders.join(', '));
    v.addSubview(t);
    var p = { canGo: false, settings: settings, quotas: quotas };
    if (gw) {
        var gear = $.NSImageView.imageViewWithImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription('gearshape', 'Settings'));
        gear.image.setTemplate(true);
        p.gear = pill(v, p, w - gw - 14, gw, gear, 14, 14, toggleSettings, 'Settings of ' + name, REPO.h);
    }
    rowParts[v.hash] = p;
    return v;
}
// A watcher row (a view item gets neither the item's action nor the menu's highlight): a transparent
// button over the left part takes the click, and track() shows the highlight.
// parts: watcherLine's.
function watcherRow(parts, canGo, role) {
    var stopFont = $.NSFont.systemFontOfSizeWeight($.NSFont.smallSystemFontSize, $.NSFontWeightMedium);
    var bw = textWidth('Stop', stopFont) + 16, font = $.NSFont.menuFontOfSize(0);
    var look = ROLE_LOOK[role] || ROLE_LOOK[''], tint = look[0] ? rgb(look[0]) : $.NSColor.labelColor;
    var plain = parts.map(function (x) { return x[0]; }).join('');
    var w = Math.max(HEADER_W, ROW.text + textWidth(plain, font) + 20 + bw + 14);
    var v = $.NSView.alloc.initWithFrame($.NSMakeRect(0, 0, w, ROW.h));
    v.setAutoresizingMask($.NSViewWidthSizable);
    var bg = $.NSVisualEffectView.alloc.initWithFrame($.NSMakeRect(5, 0, w - 10, ROW.h));
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
    iv.setFrame($.NSMakeRect(ROW.text - 21, (ROW.h - 16) / 2, 16, 16));
    v.addSubview(iv);
    var line = label(plain, font, $.NSColor.labelColor, ROW.text, (ROW.h - 17) / 2);
    line.setFrame($.NSMakeRect(ROW.text, (ROW.h - 17) / 2, w - ROW.text - bw - 26, 17));
    line.setAutoresizingMask($.NSViewWidthSizable);
    var lineAttr = attributed(parts.map(function (x) {
        return [x[0], x[1] === 'role' ? font : $.NSFont.menuFontOfSize(12),
                x[1] === 'warn' ? warnColor() : x[1] === 'role' ? $.NSColor.labelColor : $.NSColor.secondaryLabelColor];
    }), true);
    line.setAttributedStringValue(lineAttr);
    v.addSubview(line);
    if (canGo) {   // ends 4 pt short of the pill, so its hit area stays its own
        var hit = $.NSButton.buttonWithTitleTargetAction('', act(function () { rowAction(hit, 'go'); }), 'main');
        hit.setTransparent(true);
        hit.setFrame($.NSMakeRect(0, 0, w - bw - 18, ROW.h));
        hit.setAutoresizingMask($.NSViewWidthSizable);
        hit.setToolTip('Go to watcher tab');
        v.addSubview(hit);
    } else {
        line.setAlphaValue(0.5);
    }
    var p = { bg: bg, icon: iv, tint: tint, line: line, plain: plain, lineAttr: lineAttr, canGo: canGo };
    var word = $.NSTextField.labelWithString('Stop');
    word.setFont(stopFont);
    var ww = Math.ceil(word.intrinsicContentSize.width) + 4;   // room for the last glyph's overhang
    p.stop = pill(v, p, w - bw - 14, bw, word, ww, 16, function (b) { rowAction(b, 'stop'); }, 'Stop watcher', ROW.h);
    rowParts[v.hash] = p;
    return v;
}
// A pill at x (bw wide) in a row rh high, holding `content` (cw × ch, centred by frame: the alignment
// constant is wrong on Apple silicon) under a transparent button whose click runs fn(button); track()
// darkens it while the pointer is on it. Drawn by hand: a bezel goes dark on the selection colour, and
// its title with it.
function pill(v, row, x, bw, content, cw, ch, fn, tip, rh) {
    var bh = PILL.h, box = $.NSBox.alloc.initWithFrame($.NSMakeRect(x, (rh - bh) / 2, bw, bh));
    box.setBoxType($.NSBoxCustom);
    box.setTitlePosition($.NSNoTitle);
    box.setBorderWidth(0);
    box.setCornerRadius(bh / 2);
    box.setAutoresizingMask($.NSViewMinXMargin);
    v.addSubview(box);
    content.setFrame($.NSMakeRect(x + (bw - cw) / 2, (rh - ch) / 2, cw, ch));
    content.setAutoresizingMask($.NSViewMinXMargin);
    v.addSubview(content);
    var b = $.NSButton.alloc.initWithFrame(box.frame);
    b.setTitle('');
    b.setTarget(act(function () { fn(b); }));
    b.setAction('main');
    b.setTransparent(true);
    b.setAutoresizingMask($.NSViewMinXMargin);
    b.setToolTip(tip);
    v.addSubview(b);
    var q = pillParts[b.hash] = { box: box, content: content, button: b, row: row };
    paintPill(q, false);
    return q;
}
// mi: the menu's highlighted item (nil or null: none); the watcher row it is shows as selected.
function highlightRow(mi) {
    var v = mi && !mi.isNil() ? mi.view : null;
    var p = v && !v.isNil() ? rowParts[v.hash] : null;
    if (!p || !p.canGo) p = null;
    if (p === litRow) return;
    if (litRow) paintRow(litRow, false);
    litRow = p;
    if (p) paintRow(p, true);
}
function paintRow(p, on) {
    p.bg.setHidden(!on);
    if (on) { p.line.setStringValue(p.plain); p.line.setTextColor($.NSColor.selectedMenuItemTextColor); }
    else p.line.setAttributedStringValue(p.lineAttr);
    p.icon.setContentTintColor(on ? $.NSColor.selectedMenuItemTextColor : p.tint);
    paintPill(p.stop, on);
}
// on: its row is highlighted. A pointer on the pill darkens it, as a pressed-looking button does;
// a pressed pill (the gear while its panel is open) takes the accent colour.
function paintPill(q, on) {
    q.lit = on;
    q.box.setFillColor(q.pressed ? (on ? $.NSColor.colorWithWhiteAlpha(1, q.hover ? 0.55 : 0.42)
                                       : $.NSColor.controlAccentColor.colorWithAlphaComponent(q.hover ? 0.8 : 1))
                     : q.hover ? $.NSColor.colorWithWhiteAlpha(0, on ? 0.28 : 0.22)
                     : on ? $.NSColor.colorWithWhiteAlpha(1, 0.28) : $.NSColor.colorWithWhiteAlpha(0.5, 0.18));
    var c = on || q.pressed ? $.NSColor.whiteColor : $.NSColor.labelColor;
    if (q.content.respondsToSelector('setTextColor:')) q.content.setTextColor(c);
    else q.content.setContentTintColor(c);
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
// The gear: shows the repo's settings inline under its row (one panel per data dir that holds the
// repo, captioned by its path when there are several), or hides them; one repo's panel open at a
// time. The menu stays open.
function toggleSettings(sender) {
    var q = pillParts[sender.hash], mi = sender.enclosingMenuItem;
    if (!q || mi.isNil() || mi.menu.isNil()) return;
    var was = openPanel && openPanel.row === q.row;
    closeSettings();
    if (was) return;
    var menu = mi.menu, at = Number(menu.indexOfItem(mi));
    openPanel = { row: q.row, items: q.row.settings.map(function (x, i) {
        // re-read: the menu is not rebuilt while open, so x.conf may be older than the file
        var y = { name: x.name, repo: x.repo, arg: x.arg, conf: repoSettings(x.repo, x.arg.repo_dir, x.arg.remote) || x.conf };
        var pi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(x.name, null, ''), p = settingsPanel(y, q.row.quotas, caption(q.row.settings, x));
        pi.setView(p.view);
        menu.insertItemAtIndex(pi, at + 1 + i);
        return { item: pi, panel: p };
    }) };
    openPanel.panels = openPanel.items.map(function (o) { return o.panel; });
    openPanel.items = openPanel.items.map(function (o) { return o.item; });
    q.pressed = true;
    paintPill(q, !!q.lit);
}
// A panel's title line: its data dir, when the repo has one in each of several.
function caption(settings, x) { return settings.length > 1 ? x.repo : ''; }
// The width of x's panel, measured on a panel built aside; again only once what it shows changes.
var panelWidths = {};
function panelWidth(x, quotas, cap) {
    var k = JSON.stringify([x.conf, quotas, cap]), c = panelWidths[x.repo];
    if (!c || c.k !== k) {
        var keep = controls, n = ops.length;
        controls = {};
        c = panelWidths[x.repo] = { k: k, w: settingsPanel(x, quotas, cap).view.frame.size.width };
        controls = keep; ops.length = n;
    }
    return c.w;
}
function closeSettings() {
    if (!openPanel) return;
    openPanel.items.forEach(function (pi) { if (!pi.menu.isNil()) pi.menu.removeItem(pi); });
    var g = openPanel.row.gear;
    openPanel = null;
    if (g) { g.pressed = false; paintPill(g, !!g.lit); }
}

function build(s) {
    var m = newMenu('open-pr');
    opsBefore = ops; ops = [];
    rowParts = {}; pillParts = {}; litRow = null; openPanel = null; controls = {}; shown = s; busy = 0;
    var until = snoozedUntil();
    var head = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent('open-pr', null, '');
    head.setView(headerView(until, gauge(s.quotas), pollSpan(s.polls)));
    m.addItem(head);

    m.addItem($.NSMenuItem.separatorItem);
    if (!s.repos.length) add(m, 'Not watching any repository');
    s.repos.forEach(function (g, i) {
        if (i) m.addItem($.NSMenuItem.separatorItem);   // one group per repo
        var gi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(g.name, null, '');
        gi.setView(repoRow(g.name, g.folders, g.settings, s.quotas));
        m.addItem(gi);
        g.watchers.forEach(function (w) { watcherItems(m, w); });
        // the menu keeps the width it opened with: room for the widest panel its gear may show
        g.settings.forEach(function (x) {
            m.setMinimumWidth(Math.max(m.minimumWidth, panelWidth(x, s.quotas, caption(g.settings, x))));
        });
    });

    m.addItem($.NSMenuItem.separatorItem);
    var sub = newMenu('Snooze toasts');
    if (until) add(sub, 'Off until ' + when(until)).setState($.NSControlStateValueOn);
    add(sub, '30 minutes', snooze, 30);
    add(sub, '1 hour', snooze, 60);
    add(sub, 'Until 9:00 tomorrow', snooze, -1);
    sub.addItem($.NSMenuItem.separatorItem);
    if (until) add(sub, 'Turn toasts back on', snooze, 0);
    else add(sub, 'Toasts on').setState($.NSControlStateValueOn);
    var sn = add(m, 'Snooze toasts');
    sn.setSubmenu(sub);
    sn.setEnabled(true);
    sn.setImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription(until ? 'bell.slash' : 'bell', ''));
    add(m, 'Quit menu bar', leave).setImage($.NSImage.imageWithSystemSymbolNameAccessibilityDescription('power', ''));
    return m;
}
// A watcher's row, then its PR rows one indentation step in (their icons under its text); a fix
// row nested under its PR's review row one more step, its state as its title.
function watcherItems(m, w) {
    // A record from before watcher.json existed has no tab to show.
    var go = w.key && (TERMS[w.term] || SESSION_ID.test(w.session_id))
        ? { term: w.term, term_session: w.term_session, tty: w.tty, session_id: w.session_id, pids: w.pids, hosts: w.hosts } : null;
    if (w.key) {
        var parts = watcherLine(w), wt = parts.map(function (x) { return x[0]; }).join('');
        var wi = $.NSMenuItem.alloc.initWithTitleActionKeyEquivalent(wt, null, '');
        wi.setRepresentedObject($(JSON.stringify({ go: go, stop: { dirs: w.dirs, sfx: w.sfx, session_id: w.only ? w.session_id : '' } })));
        wi.setView(watcherRow(parts, !!go, w.role));
        m.addItem(wi);
    }
    // a blank image of an icon's size puts the text in the rows' text column
    if (!w.rows.length) {
        var none = add(m, 'No pull requests yet');
        none.setImage(blank());
        none.setIndentationLevel(PR_INDENT);
    }
    w.rows.forEach(function (x) {
        var spec = KIND[x.kind];
        if (BUSY[x.kind]) busy++;
        // A click goes where the user acts: a question's answer, else the pull request.
        var session = OPEN_CMD.test(x.open) ? JSON.stringify({ open: x.open, term: w.term }) : '';
        var answer = x.focus === 'watcher' && go ? JSON.stringify(go) : '';
        var text = x.role === 'fix' ? 'Fix: ' + x.text : x.text, title = x.nested ? oneLine(text) : x.title;
        var mi = answer ? add(m, title, json(goToTab), answer)
            : x.focus === 'session' && session ? add(m, title, json(openTerminal), session)
            : add(m, title, isURL(x.url) ? openURL : null, x.url);
        mi.setIndentationLevel(PR_INDENT + (x.nested ? 1 : 0));
        if (!x.nested) subtitle(mi, text, x.time);
        mi.setImage(spec ? symbol(spec) : blank());
        // Offered in every state: `open` also reopens a finished or stopped session.
        var sub = newMenu(x.title);
        if (answer) add(sub, 'Answer in ' + w.app, json(goToTab), answer);
        if (x.fix && prArgs(parse(x.fix), 'fix-now')) add(sub, 'Fix now', json(fixNow), x.fix);
        if (isURL(x.url)) add(sub, 'Open pull request', openURL, x.url);
        if (session) add(sub, 'Open session in ' + w.app, json(openTerminal), session);
        if (x.here && go) add(sub, 'Open session in ' + w.app, json(goToTab), JSON.stringify(go));
        if (x.open) add(sub, 'Copy command  ' + x.open, copyText, x.open);
        if (x.hide && prArgs(parse(x.hide), 'hide')) add(sub, 'Remove from list', json(hide), x.hide);
        if (sub.numberOfItems > 0) { mi.setSubmenu(sub); mi.setEnabled(true); }
    });
}

function span(sec) { return sec % 60 ? sec + ' seconds' : sec / 60 + (sec === 60 ? ' minute' : ' minutes'); }
// A settings panel's controls by hash: { p: its panel, key, view, values: what each segment writes }
// for a pick, the same without values for a checkbox, { reveal: its settings.json } for its button.
var controls = {};
var PANEL = { pad: 16, label: 120, row: 30, check: 22 };   // points: side padding, label column, row steps
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
function checkbox(p, key, title) {
    var b = $.NSButton.checkboxWithTitleTargetAction(title, act(function () { setSetting(b); }), 'main');
    return control(p, b, key);
}
// x: { name, repo, conf, arg }; caption: a title line on top (the repo, when a watcher has several).
// The view of one menu item: a click on a control inside it leaves the menu open, where a plain
// item's action closes it.
// Laid out top-down as [view, x, top, width, height]; width undefined: its fitting width, 0: to the right
// padding, -1: to the right padding, at least its fitting width;
// frames are set once the size is known, as AppKit's y grows upward.
function settingsPanel(x, quotas, caption) {
    var p = { x: x, quotas: quotas, ctl: [] }, at = [], top = 10, pad = PANEL.pad, col = pad + PANEL.label;
    var put = function (v, l, wd, h, dy) { at.push([v, l, top + (dy || 0), wd, h]); return v; };
    var second = $.NSColor.secondaryLabelColor, small = $.NSFont.systemFontOfSize(11);
    if (caption) { put(text(caption, $.NSFont.boldSystemFontOfSize(13), $.NSColor.labelColor), pad, -1, 17); top += 24; }
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
                $(k[2].map(function (o) { return o[1]; })), $.NSSegmentSwitchTrackingSelectOne, act(function () { setSetting(seg); }), 'main');
            k[2].forEach(function (o, j) {
                var tip = k[0] === 'watch.poll_interval_seconds' ? span(o[0]) + estimate(quotas, o[0]) : o[2];
                if (tip) seg.setToolTipForSegment(tip, j);
            });
            put(control(p, seg, k[0], k[2].map(function (o) { return o[0]; })), col, undefined, 24);
            if (k[0] === 'watch.poll_interval_seconds') {   // placed right of the control once it is sized
                var b = $.NSButton.buttonWithTitleTargetAction('Apply to all', act(function () { applyAll(b); }), 'main');
                b.setControlSize($.NSControlSizeSmall);
                b.setFont($.NSFont.systemFontOfSize($.NSFont.smallSystemFontSize));
                b.setToolTip('Poll every repo this menu shows at this interval');
                controls[b.hash] = { p: p, applyAll: true };
                put(b, col, undefined, 22, 1);
                p.apply = { seg: seg, at: at[at.length - 1] };
            }
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
    p.reveal = $.NSButton.buttonWithTitleTargetAction('Show settings file', act(function () { reveal(p.reveal); }), 'main');
    p.reveal.setControlSize($.NSControlSizeSmall);
    p.reveal.setFont($.NSFont.systemFontOfSize($.NSFont.smallSystemFontSize));
    controls[p.reveal.hash] = { reveal: x.repo + '/settings.json' };
    put(p.reveal, pad - 6, undefined, 22);   // a bezel's own inset: its border lines up with the text above
    top += 30;
    showPanel(p, x.conf);   // first, so a segment shown only for a value set in a chat is measured
    if (p.apply) p.apply.at[1] = col + p.apply.seg.frame.size.width + 8;
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
    p.view = v;
    return p;
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
        var e = typeof valueAt(conf, 'watch.poll_interval_seconds') === 'number' ? estimate(p.quotas, valueAt(conf, 'watch.poll_interval_seconds')).trim() : '';
        p.cost.setStringValue(e ? 'API cost ' + e : '');
        p.cost.setToolTip('API requests per hour at this interval, from the last poll of each repo; ⚠ = over half the host\'s hourly limit');
        p.cost.setTextColor(/ ⚠$/.test(e) ? warnColor() : $.NSColor.secondaryLabelColor);
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
// The tty of pid or of its nearest ancestor that has one, as ancestor_tty in open-pr-watch.sh
// records it; '' once pid is gone. ps: the output of `ps -A -o pid=,ppid=,tty=`.
function hostTty(ps, pid) {
    var up = {};
    String(ps || '').split('\n').forEach(function (l) {
        var f = l.trim().split(/\s+/);
        if (f.length === 3) up[f[0]] = f;
    });
    for (var p = String(pid), i = 0; up[p] && i < 15; p = up[p][1], i++) {
        if (!/^(\?\??|-)$/.test(up[p][2])) return up[p][2];
    }
    return '';
}
// [tab id, its tty] while a watcher pid — its wait, or the `claude` running it (between waits no wait
// runs) — still runs on the tty of the tab recorded, else null: the tab is closed, or it now runs
// something else — the user quit `claude` there (the session went on in the background), or a
// background session inherited the tab of the `claude` that started it.
function liveTab(w, ps) {
    var id = tabId(w), pids = w.pids.concat(w.hosts || []);
    if (!TAB_ID.test(id)) return null;
    for (var i = 0; i < pids.length; i++) {
        var t = hostTty(ps, pids[i]), tty = '/dev/' + t;
        if (t && TAB_ID.test(tty) && (w.term !== 'Apple_Terminal' || tty === id)) return [id, tty];
    }
    return null;
}
// What brings back a watcher session whose tab was not found, or '' while its `claude` runs (the session
// is open in a tab; a resume would start a second copy). Listed by `claude agents --json` (agents():
// its output, null when it did not run) as a background job ⇒ attach; not listed ⇒ resume. No host
// recorded, or no listing ⇒ attach: resuming blind might start that copy.
function reopen(w, ps, agents) {
    var hosts = w.hosts || [], up = String(ps || '').split('\n').map(function (l) { return l.trim().split(/\s+/)[0]; });
    if (!SESSION_ID.test(w.session_id)) return '';
    if (hosts.some(function (h) { return ps === null || up.indexOf(String(h)) >= 0; })) return '';
    var attach = 'claude attach ' + w.session_id.slice(0, 8), out = hosts.length ? agents() : null, list = [];
    if (out === null) return attach;
    // A listing that cannot be read may hide the job: attach only fails, a resume would copy it.
    try { list = JSON.parse(out); } catch (e) { return attach; }
    if (!Array.isArray(list)) return attach;
    var job = list.filter(function (a) {
        return a && a.sessionId === w.session_id && (a.kind === undefined || a.kind === 'background');
    })[0];
    if (!job) return 'claude --resume ' + w.session_id;
    return /^[0-9a-f]{8,64}$/.test(job.id) ? 'claude attach ' + job.id : attach;
}
// A tab that is gone (the user quit `claude`, which keeps the watcher's session running in the
// background) is reopened (reopen); each watcher names its own session.
function goToTab(w) {
    if (!w || typeof w !== 'object') return;
    w = { term: str(w.term), term_session: str(w.term_session), tty: str(w.tty), session_id: str(w.session_id),
          pids: Array.isArray(w.pids) ? w.pids : [], hosts: Array.isArray(w.hosts) ? w.hosts : [] };
    var t = TERMS[w.term];
    // Needs no permission, so the app comes forward even when the tab lookup is refused. Via
    // LaunchServices: an accessory app's own activate request is ignored by macOS.
    if (t) spawn('/usr/bin/open', ['-b', t[1]]);
    var ps = output('/bin/ps', ['-A', '-o', 'pid=,ppid=,tty=']);
    var src = FOCUS[w.term], tab = src ? liveTab(w, ps) : null;
    var found = tab ? output('/usr/bin/osascript', script(src).concat(tab)) : '';
    // null: the lookup failed or is still waiting on a permission prompt — the tab may be there.
    var cmd = found === '' ? reopen(w, ps, function () { return output('/usr/bin/env', ['claude', 'agents', '--json']); }) : '';
    if (cmd) openIn(w.term, cmd, snoozeFile);
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
    // A wait that already exited leaves its heartbeat until it goes stale: nobody would read the
    // stop file, so the row is taken off here.
    var ps = ' ' + output('/bin/ps', ['-A', '-o', 'pid=']).split(/\s+/).join(' ') + ' ';
    var fm = $.NSFileManager.defaultManager, gone = 0;
    dirs.forEach(function (d) {
        var j = parse(readText(d + '/watcher' + sfx + '.json'));
        if (j && typeof j.pid === 'number' && ps.indexOf(' ' + j.pid + ' ') >= 0) return;
        fm.removeItemAtPathError(d + '/heartbeat' + sfx, null);
        fm.removeItemAtPathError(d + '/watcher' + sfx + '.json', null);
        gone++;
    });
    if (gone) refresh();
    var sid = str(o.session_id);
    if (dirs.length && SESSION_ID.test(sid)) stopLater({ dirs: dirs, sfx: sfx, session_id: sid, tries: 0 });
}
function stopLater(o) {
    $.NSTimer.scheduledTimerWithTimeIntervalRepeatsBlock(3, false, function () { stopSession(o); });
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
// "Apply to all": the poll interval of the panel the click came from, written to every repo the open
// menu shows, then each open panel set from its file read afresh. The menu stays open.
function applyAll(sender) {
    var c = controls[sender.hash];
    if (!c || !c.p || !shown) return;
    applyArgs(shown, valueAt(c.p.conf, 'watch.poll_interval_seconds')).forEach(function (a) { output('/bin/sh', a); });
    settingsCache = {};
    (openPanel ? openPanel.panels : [c.p]).forEach(function (p) {
        showPanel(p, repoSettings(p.x.repo, p.x.arg.repo_dir, p.x.arg.remote) || p.conf);
    });
}
// The `settings --set watch.poll_interval_seconds` argv for each repo group's settings of scan s, once each; a value
// the Poll control does not offer, or a repo settingArgs refuses, yields none.
function applyArgs(s, value) {
    var seen = {}, out = [];
    s.repos.forEach(function (g) { g.settings.forEach(function (x) {
        if (seen[x.repo]) return;
        seen[x.repo] = true;
        var a = settingArgs({ repo_dir: x.arg.repo_dir, remote: x.arg.remote, key: 'watch.poll_interval_seconds', value: String(value) });
        if (a) out.push(a);
    }); });
    return out;
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
function leave() {
    var me = String($.NSProcessInfo.processInfo.processIdentifier);
    if (readText(pidFile).trim() === me) $.NSFileManager.defaultManager.removeItemAtPathError(pidFile, null);
    if (item) $.NSStatusBar.systemStatusBar.removeStatusItem(item);
    $.NSApplication.sharedApplication.terminate(null);
}
